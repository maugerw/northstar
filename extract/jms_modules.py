# jms_modules.py
#
# WLST-dependent extraction of JMS system modules and their children
# (queues, distributed queues, connection factories, templates, topics,
# quotas, destination keys, foreign servers, SAF error handlings).
#
# WLST globals (cmo, etc.) are NOT relied on as module globals here; the live
# configuration MBean (cmo) is passed in as an argument so this module can be
# imported cleanly under WLST.

from jms_filters import get_targets, is_soa_internal_queue, \
    is_system_connection_factory, is_system_module, derive_logical_name
from jms_serialize import to_long, to_boolean, safe, _name_of


def _add_internal_queue(system_data, logical, raw_name):
    if logical not in [iq["name"] for iq in system_data["soaInternalQueues"]]:
        system_data["soaInternalQueues"].append({
            "name": logical,
            "source": raw_name
        })


def extract_jms_modules(cmo, extract_data, system_data):
    print 'Extracting JMS Modules...'

    modules = cmo.getJMSSystemResources()

    for module in modules:
        module_name = str(module.getName())
        # Classify the parent module up front so per-child decisions (notably
        # connection factories, item 6) can take the module's user/system
        # status into account rather than relying on the child name alone.
        module_is_system = is_system_module(module_name)
        module_dict = {}
        module_dict["name"] = module_name
        module_dict["targets"] = get_targets(module)
        module_dict["subdeployments"] = []
        module_dict["queues"] = []
        module_dict["uniformDistributedQueues"] = []
        module_dict["distributedQueues"] = []
        module_dict["connectionFactories"] = []
        module_dict["templates"] = []
        module_dict["topics"] = []
        module_dict["uniformDistributedTopics"] = []
        module_dict["distributedTopics"] = []
        module_dict["quotas"] = []
        module_dict["destinationKeys"] = []
        module_dict["foreignServers"] = []
        module_dict["safErrorHandlings"] = []

        # --- Subdeployments ---
        subdeps = module.getSubDeployments()
        for sub in subdeps:
            sub_dict = {}
            sub_dict["name"] = str(sub.getName())

            sub_targets = []
            try:
                for t in sub.getTargets():
                    sub_targets.append(str(t.getName()))
            except Exception:
                pass

            sub_dict["targets"] = sub_targets
            module_dict["subdeployments"].append(sub_dict)

        # --- JMS Resource ---
        jms_res = module.getJMSResource()

        # --- Queues ---
        queues = jms_res.getQueues()
        for q in queues:
            q_name = str(q.getName())

            if is_soa_internal_queue(q_name):
                logical = derive_logical_name(q_name)
                _add_internal_queue(system_data, logical, q_name)
                print 'SOA INTERNAL QUEUE:', logical
                continue

            q_dict = {}
            q_dict["name"] = q_name
            q_dict["jndi"] = str(q.getJNDIName())
            q_dict["subdeployment"] = str(q.getSubDeploymentName())

            q_dict["redeliveryDelay"] = safe(q, 'getRedeliveryDelay', to_long)
            q_dict["errorDestination"] = safe(q, 'getErrorDestination', _name_of)

            module_dict["queues"].append(q_dict)

        # --- Uniform Distributed Queues ---
        try:
            udqs = jms_res.getUniformDistributedQueues()
            if udqs:
                seen_logical = {}
                for udq in udqs:
                    raw_name = str(udq.getName())
                    if is_soa_internal_queue(raw_name):
                        logical = derive_logical_name(raw_name)

                        if logical not in seen_logical:
                            seen_logical[logical] = 1
                            _add_internal_queue(system_data, logical, raw_name)

                        print 'SOA INTERNAL QUEUE:', logical
                        continue

                    udq_dict = {}
                    udq_dict["name"] = raw_name
                    udq_dict["jndi"] = str(udq.getJNDIName())
                    udq_dict["subdeployment"] = str(udq.getSubDeploymentName())

                    udq_dict["loadBalancingPolicy"] = safe(udq, 'getLoadBalancingPolicy')
                    udq_dict["forwardingPolicy"] = safe(udq, 'getForwardingPolicy')
                    udq_dict["redeliveryDelay"] = safe(udq, 'getRedeliveryDelay', to_long)
                    udq_dict["errorDestination"] = safe(udq, 'getErrorDestination', _name_of)

                    module_dict["uniformDistributedQueues"].append(udq_dict)
        except Exception:
            pass

        # --- Distributed Queues ---
        try:
            dqs = jms_res.getDistributedQueues()
            if dqs:
                for dq in dqs:
                    raw_name = str(dq.getName())

                    if is_soa_internal_queue(raw_name):
                        logical = derive_logical_name(raw_name)
                        _add_internal_queue(system_data, logical, raw_name)
                        print 'SOA INTERNAL DQ:', logical
                        continue

                    dq_dict = {}
                    dq_dict["name"] = raw_name
                    dq_dict["jndi"] = str(dq.getJNDIName())
                    dq_dict["subdeployment"] = str(dq.getSubDeploymentName())

                    dq_dict["loadBalancingPolicy"] = safe(dq, 'getLoadBalancingPolicy')
                    dq_dict["forwardingPolicy"] = safe(dq, 'getForwardingPolicy')
                    dq_dict["redeliveryDelay"] = safe(dq, 'getRedeliveryDelay', to_long)
                    dq_dict["errorDestination"] = safe(dq, 'getErrorDestination', _name_of)

                    module_dict["distributedQueues"].append(dq_dict)
        except Exception:
            pass

        # --- Connection Factories ---
        # Item 6: a connection factory is treated as "system" only in relation
        # to its parent module. Previously any CF whose *name* matched
        # SYSTEM_CF_SUBSTRINGS was moved out into systemConnectionFactories,
        # which (a) left a user module exported missing a CF its applications
        # may rely on, and (b) double-counted the CF in the audit file when the
        # module itself was also classified system. Now the CF always stays
        # with its module; for a user module we additionally record a
        # lightweight, module-qualified audit reference so a system-looking CF
        # inside a user module stays visible for review without being stripped
        # from the clean user export.
        cfs = jms_res.getConnectionFactories()
        for cf in cfs:
            cf_name = str(cf.getName())
            cf_dict = {}
            cf_dict["name"] = cf_name
            cf_dict["jndi"] = str(cf.getJNDIName())
            cf_dict["subdeployment"] = str(cf.getSubDeploymentName())
            # Capture whether the CF targets the module's target directly
            # (default targeting) rather than via a subdeployment. When this is
            # true, a subdeployment name that does not resolve to a real
            # subdeployment object is expected, not a gap - validate_references
            # uses this to decide whether a dangling subdeployment reference is
            # a warning or benign default targeting.
            cf_dict["defaultTargetingEnabled"] = safe(cf, 'isDefaultTargetingEnabled', to_boolean)

            module_dict["connectionFactories"].append(cf_dict)

            # Audit-only reference (the CF is NOT removed from the module).
            # Skipped when the module is system, because the whole module_dict
            # already lands in systemJmsModules and adding it here too would
            # duplicate the entry in the audit file.
            if not module_is_system and is_system_connection_factory(cf_name):
                system_data["systemConnectionFactories"].append({
                    "name": cf_name,
                    "module": module_name,
                    "jndi": cf_dict["jndi"],
                })

        # --- JMS Templates ---
        # Many destinations derive quotas/delivery/redelivery settings from a
        # template, so the template must be exported for a faithful re-create.
        try:
            templates = jms_res.getTemplates()
            if templates:
                for tmpl in templates:
                    t_dict = {}
                    t_dict["name"] = str(tmpl.getName())

                    t_dict["redeliveryDelay"] = safe(tmpl, 'getRedeliveryDelay', to_long)
                    t_dict["redeliveryLimit"] = safe(tmpl, 'getRedeliveryLimit', to_long)
                    t_dict["errorDestination"] = safe(tmpl, 'getErrorDestination', _name_of)
                    t_dict["timeToLive"] = safe(tmpl, 'getTimeToLive', to_long)
                    t_dict["priority"] = safe(tmpl, 'getPriority', to_long)

                    module_dict["templates"].append(t_dict)
        except Exception:
            pass

        # --- Topics ---
        try:
            topics = jms_res.getTopics()
            if topics:
                for tp in topics:
                    tp_name = str(tp.getName())

                    if is_soa_internal_queue(tp_name):
                        logical = derive_logical_name(tp_name)
                        _add_internal_queue(system_data, logical, tp_name)
                        print 'SOA INTERNAL TOPIC:', logical
                        continue

                    tp_dict = {}
                    tp_dict["name"] = tp_name
                    tp_dict["jndi"] = str(tp.getJNDIName())
                    tp_dict["subdeployment"] = str(tp.getSubDeploymentName())
                    module_dict["topics"].append(tp_dict)
        except Exception:
            pass

        # --- Uniform Distributed Topics ---
        try:
            udts = jms_res.getUniformDistributedTopics()
            if udts:
                for udt in udts:
                    raw_name = str(udt.getName())

                    if is_soa_internal_queue(raw_name):
                        logical = derive_logical_name(raw_name)
                        _add_internal_queue(system_data, logical, raw_name)
                        print 'SOA INTERNAL UDT:', logical
                        continue

                    udt_dict = {}
                    udt_dict["name"] = raw_name
                    udt_dict["jndi"] = str(udt.getJNDIName())
                    udt_dict["subdeployment"] = str(udt.getSubDeploymentName())

                    udt_dict["loadBalancingPolicy"] = safe(udt, 'getLoadBalancingPolicy')
                    udt_dict["forwardingPolicy"] = safe(udt, 'getForwardingPolicy')
                    module_dict["uniformDistributedTopics"].append(udt_dict)
        except Exception:
            pass

        # --- Distributed Topics ---
        try:
            dts = jms_res.getDistributedTopics()
            if dts:
                for dt in dts:
                    raw_name = str(dt.getName())

                    if is_soa_internal_queue(raw_name):
                        logical = derive_logical_name(raw_name)
                        _add_internal_queue(system_data, logical, raw_name)
                        print 'SOA INTERNAL DT:', logical
                        continue

                    dt_dict = {}
                    dt_dict["name"] = raw_name
                    dt_dict["jndi"] = str(dt.getJNDIName())
                    dt_dict["subdeployment"] = str(dt.getSubDeploymentName())

                    dt_dict["loadBalancingPolicy"] = safe(dt, 'getLoadBalancingPolicy')
                    dt_dict["forwardingPolicy"] = safe(dt, 'getForwardingPolicy')
                    module_dict["distributedTopics"].append(dt_dict)
        except Exception:
            pass

        # --- Quotas ---
        # Destinations reference a quota by name; without the quota definition
        # the reference dangles on import.
        try:
            quotas = jms_res.getQuotas()
            if quotas:
                for quota in quotas:
                    qa_dict = {}
                    qa_dict["name"] = str(quota.getName())

                    qa_dict["bytesMaximum"] = safe(quota, 'getBytesMaximum', to_long)
                    qa_dict["messagesMaximum"] = safe(quota, 'getMessagesMaximum', to_long)
                    qa_dict["policy"] = safe(quota, 'getPolicy')
                    qa_dict["shared"] = safe(quota, 'isShared', to_boolean)
                    module_dict["quotas"].append(qa_dict)
        except Exception:
            pass

        # --- Destination Keys ---
        try:
            dkeys = jms_res.getDestinationKeys()
            if dkeys:
                for dk in dkeys:
                    dk_dict = {}
                    dk_dict["name"] = str(dk.getName())

                    dk_dict["property"] = safe(dk, 'getProperty')
                    dk_dict["keyType"] = safe(dk, 'getKeyType')
                    dk_dict["direction"] = safe(dk, 'getDirection')
                    module_dict["destinationKeys"].append(dk_dict)
        except Exception:
            pass

        # --- Foreign Servers ---
        # Critical for integrations: foreign JNDI links plus foreign
        # destinations and foreign connection factories (often used to bridge
        # to AQ / external brokers).
        try:
            fservers = jms_res.getForeignServers()
            if fservers:
                for fs in fservers:
                    fs_dict = {}
                    fs_dict["name"] = str(fs.getName())

                    fs_dict["initialContextFactory"] = safe(fs, 'getInitialContextFactory')
                    fs_dict["connectionURL"] = safe(fs, 'getConnectionURL')
                    fs_dict["jndiProperties"] = safe(fs, 'getJNDIProperties')
                    fs_dict["defaultTargetingEnabled"] = safe(fs, 'isDefaultTargetingEnabled', to_boolean)

                    # Foreign destinations
                    fs_dict["foreignDestinations"] = []
                    try:
                        fdests = fs.getForeignDestinations()
                        if fdests:
                            for fd in fdests:
                                fd_dict = {}
                                fd_dict["name"] = str(fd.getName())
                                fd_dict["localJNDIName"] = safe(fd, 'getLocalJNDIName')
                                fd_dict["remoteJNDIName"] = safe(fd, 'getRemoteJNDIName')
                                fs_dict["foreignDestinations"].append(fd_dict)
                    except Exception:
                        pass

                    # Foreign connection factories
                    fs_dict["foreignConnectionFactories"] = []
                    try:
                        fcfs = fs.getForeignConnectionFactories()
                        if fcfs:
                            for fcf in fcfs:
                                fcf_dict = {}
                                fcf_dict["name"] = str(fcf.getName())
                                fcf_dict["localJNDIName"] = safe(fcf, 'getLocalJNDIName')
                                fcf_dict["remoteJNDIName"] = safe(fcf, 'getRemoteJNDIName')
                                fs_dict["foreignConnectionFactories"].append(fcf_dict)
                    except Exception:
                        pass

                    module_dict["foreignServers"].append(fs_dict)
        except Exception:
            pass

        # --- SAF Error Handling ---
        # Referenced by SAF imported destinations; without it the SAF error
        # policy is lost on import.
        try:
            saf_eh = jms_res.getSAFErrorHandlings()
            if saf_eh:
                for eh in saf_eh:
                    eh_dict = {}
                    eh_dict["name"] = str(eh.getName())

                    eh_dict["policy"] = safe(eh, 'getPolicy')
                    eh_dict["errorDestination"] = safe(eh, 'getSAFErrorDestination', _name_of)
                    eh_dict["logFormat"] = safe(eh, 'getLogFormat')
                    module_dict["safErrorHandlings"].append(eh_dict)
        except Exception:
            pass

        if module_is_system:
            system_data["systemJmsModules"].append(module_dict)
        else:
            extract_data["jmsModules"].append(module_dict)
