# load_jms_modules.py
#
# Phase 2: JMS system modules and all their children.
#
# Creation order within each module:
#   subdeployments → quotas → templates → destinations (queues/UDQs/DQs/
#   topics/UDTs/DTs) → connection factories → foreign servers →
#   SAF error handlings
#
# Subdeployments target JMS servers (created in Phase 1) or clusters; module
# targets are server/cluster names that are remapped via env['targets'].
#
# WLST globals used directly — must run inside WLST.

import sys
from load_serialize import get, get_str, get_list


def _exists(mbean_path):
    try:
        return getMBean(mbean_path) is not None
    except Exception:
        return False


def _is_dry_run(env):
    return get(env, 'dry_run', False)


def _map_target(name, env):
    target_map = get(env, 'targets', {})
    return str(target_map.get(str(name), str(name)))


def _assign_targets(resource_type, resource_name, raw_targets, env):
    for t in raw_targets:
        mapped = _map_target(t, env)
        try:
            assign(resource_type, resource_name, 'Target', mapped)
        except Exception:
            print '  WARNING: could not assign target "' + mapped + '" to ' + resource_type + ' "' + resource_name + '": ' + str(sys.exc_info()[1])


# ---------------------------------------------------------------------------
# Module-level helpers (navigate into the JMSResource of a module)
# ---------------------------------------------------------------------------

def _jms_resource_path(module_name):
    return '/JMSSystemResources/' + module_name + '/JMSResource/' + module_name


def _cd_jms_resource(module_name):
    cd(_jms_resource_path(module_name))


# ---------------------------------------------------------------------------
# Subdeployments
# ---------------------------------------------------------------------------

def _load_subdeployments(module_name, subdeps, env):
    for sub in subdeps:
        sub_name = get_str(sub, 'name')
        if not sub_name:
            continue
        sub_targets = get_list(sub, 'targets')

        sub_path = '/JMSSystemResources/' + module_name + '/SubDeployments/' + sub_name
        if _exists(sub_path):
            print '    SubDeployment already exists, skipping: ' + sub_name
            continue

        print '    Creating SubDeployment: ' + sub_name
        cd('/JMSSystemResources/' + module_name)
        create(sub_name, 'SubDeployment')

        # Subdeployment targets may be JMS servers (created in Phase 1) or
        # clusters/servers.  The assign type differs.
        for t in sub_targets:
            mapped = _map_target(t, env)
            try:
                assign('JMSSystemResource.' + module_name + '.SubDeployment',
                       sub_name, 'Target', mapped)
            except Exception:
                print '    WARNING: could not assign target "' + mapped + '" to SubDeployment "' + sub_name + '": ' + str(sys.exc_info()[1])


# ---------------------------------------------------------------------------
# Quotas (referenced by destinations — create before destinations)
# ---------------------------------------------------------------------------

def _load_quotas(module_name, quotas):
    _cd_jms_resource(module_name)
    for qa in quotas:
        name = get_str(qa, 'name')
        if not name:
            continue
        quota_path = _jms_resource_path(module_name) + '/Quotas/' + name
        if _exists(quota_path):
            print '    Quota already exists, skipping: ' + name
            continue
        print '    Creating Quota: ' + name
        _cd_jms_resource(module_name)
        create(name, 'Quota')
        cd('Quotas/' + name)
        bytes_max = get(qa, 'bytesMaximum')
        msgs_max = get(qa, 'messagesMaximum')
        policy = get_str(qa, 'policy')
        shared = get(qa, 'shared')
        if bytes_max is not None and int(bytes_max) >= 0:
            cmo.setBytesMaximum(long(bytes_max))
        if msgs_max is not None and int(msgs_max) >= 0:
            cmo.setMessagesMaximum(long(msgs_max))
        if policy:
            cmo.setPolicy(policy)
        if shared is not None:
            cmo.setShared(bool(shared))


# ---------------------------------------------------------------------------
# Templates (referenced by destinations — create before destinations)
# ---------------------------------------------------------------------------

def _load_templates(module_name, templates):
    _cd_jms_resource(module_name)
    for tmpl in templates:
        name = get_str(tmpl, 'name')
        if not name:
            continue
        tmpl_path = _jms_resource_path(module_name) + '/Templates/' + name
        if _exists(tmpl_path):
            print '    Template already exists, skipping: ' + name
            continue
        print '    Creating Template: ' + name
        _cd_jms_resource(module_name)
        create(name, 'Template')
        cd('Templates/' + name)
        _set_delivery_params(tmpl)


def _set_delivery_params(obj):
    # Shared delivery/redelivery attributes used by templates and destinations.
    redeliver_delay = get(obj, 'redeliveryDelay')
    redeliver_limit = get(obj, 'redeliveryLimit')
    ttl = get(obj, 'timeToLive')
    priority = get(obj, 'priority')
    if redeliver_delay is not None and int(redeliver_delay) >= 0:
        cmo.setRedeliveryDelay(long(redeliver_delay))
    if redeliver_limit is not None and int(redeliver_limit) >= 0:
        cmo.setRedeliveryLimit(long(redeliver_limit))
    if ttl is not None and int(ttl) >= 0:
        cmo.setTimeToLive(long(ttl))
    if priority is not None and int(priority) >= 0:
        cmo.setPriority(long(priority))


# ---------------------------------------------------------------------------
# Destination helpers
# ---------------------------------------------------------------------------

def _set_destination_common(d):
    jndi = get_str(d, 'jndi')
    subdeployment = get_str(d, 'subdeployment')
    redeliver_delay = get(d, 'redeliveryDelay')
    if jndi:
        cmo.setJNDIName(jndi)
    if subdeployment and subdeployment != 'None':
        cmo.setSubDeploymentName(subdeployment)
    if redeliver_delay is not None and int(redeliver_delay) >= 0:
        cmo.setRedeliveryDelay(long(redeliver_delay))


def _set_distributed_params(d):
    lb = get_str(d, 'loadBalancingPolicy')
    fw = get_str(d, 'forwardingPolicy')
    if lb:
        cmo.setLoadBalancingPolicy(lb)
    if fw:
        cmo.setForwardingPolicy(fw)


# ---------------------------------------------------------------------------
# Destinations (queues / topics and their distributed variants)
# ---------------------------------------------------------------------------

def _load_destinations(module_name, module_dict):
    dest_specs = [
        ('queues',                  'Queue',                    'Queues'),
        ('uniformDistributedQueues','UniformDistributedQueue',  'UniformDistributedQueues'),
        ('distributedQueues',       'DistributedQueue',         'DistributedQueues'),
        ('topics',                  'Topic',                    'Topics'),
        ('uniformDistributedTopics','UniformDistributedTopic',  'UniformDistributedTopics'),
        ('distributedTopics',       'DistributedTopic',         'DistributedTopics'),
    ]
    for key, mbean_type, path_segment in dest_specs:
        for d in get_list(module_dict, key):
            name = get_str(d, 'name')
            if not name:
                continue
            dest_path = _jms_resource_path(module_name) + '/' + path_segment + '/' + name
            if _exists(dest_path):
                print '    ' + mbean_type + ' already exists, skipping: ' + name
                continue
            print '    Creating ' + mbean_type + ': ' + name
            _cd_jms_resource(module_name)
            create(name, mbean_type)
            cd(path_segment + '/' + name)
            _set_destination_common(d)
            if 'Distributed' in mbean_type:
                _set_distributed_params(d)


# ---------------------------------------------------------------------------
# Connection factories
# ---------------------------------------------------------------------------

def _load_connection_factories(module_name, cfs):
    for cf in cfs:
        name = get_str(cf, 'name')
        if not name:
            continue
        cf_path = _jms_resource_path(module_name) + '/ConnectionFactories/' + name
        if _exists(cf_path):
            print '    ConnectionFactory already exists, skipping: ' + name
            continue
        print '    Creating ConnectionFactory: ' + name
        _cd_jms_resource(module_name)
        create(name, 'ConnectionFactory')
        cd('ConnectionFactories/' + name)
        jndi = get_str(cf, 'jndi')
        subdeployment = get_str(cf, 'subdeployment')
        if jndi:
            cmo.setJNDIName(jndi)
        if subdeployment and subdeployment != 'None':
            cmo.setSubDeploymentName(subdeployment)


# ---------------------------------------------------------------------------
# Foreign servers
# ---------------------------------------------------------------------------

def _load_foreign_servers(module_name, fservers):
    for fs in fservers:
        name = get_str(fs, 'name')
        if not name:
            continue
        fs_path = _jms_resource_path(module_name) + '/ForeignServers/' + name
        if _exists(fs_path):
            print '    ForeignServer already exists, skipping: ' + name
            continue
        print '    Creating ForeignServer: ' + name
        _cd_jms_resource(module_name)
        create(name, 'ForeignServer')
        cd('ForeignServers/' + name)

        icf = get_str(fs, 'initialContextFactory')
        url = get_str(fs, 'connectionURL')
        default_tgt = get(fs, 'defaultTargetingEnabled')
        if icf:
            cmo.setInitialContextFactory(icf)
        if url:
            cmo.setConnectionURL(url)
        if default_tgt is not None:
            cmo.setDefaultTargetingEnabled(bool(default_tgt))

        # NOTE: jndiProperties is a Properties MBean — omitted in skeleton;
        # extend here if the environment uses foreign JNDI properties.

        for fd in get_list(fs, 'foreignDestinations'):
            fd_name = get_str(fd, 'name')
            if not fd_name:
                continue
            print '      Creating ForeignDestination: ' + fd_name
            create(fd_name, 'ForeignDestination')
            cd('ForeignDestinations/' + fd_name)
            local_jndi = get_str(fd, 'localJNDIName')
            remote_jndi = get_str(fd, 'remoteJNDIName')
            if local_jndi:
                cmo.setLocalJNDIName(local_jndi)
            if remote_jndi:
                cmo.setRemoteJNDIName(remote_jndi)
            cd('../..')

        for fcf in get_list(fs, 'foreignConnectionFactories'):
            fcf_name = get_str(fcf, 'name')
            if not fcf_name:
                continue
            print '      Creating ForeignConnectionFactory: ' + fcf_name
            create(fcf_name, 'ForeignConnectionFactory')
            cd('ForeignConnectionFactories/' + fcf_name)
            local_jndi = get_str(fcf, 'localJNDIName')
            remote_jndi = get_str(fcf, 'remoteJNDIName')
            if local_jndi:
                cmo.setLocalJNDIName(local_jndi)
            if remote_jndi:
                cmo.setRemoteJNDIName(remote_jndi)
            cd('../..')


# ---------------------------------------------------------------------------
# SAF error handlings
# ---------------------------------------------------------------------------

def _load_saf_error_handlings(module_name, error_handlings):
    for eh in error_handlings:
        name = get_str(eh, 'name')
        if not name:
            continue
        eh_path = _jms_resource_path(module_name) + '/SAFErrorHandlings/' + name
        if _exists(eh_path):
            print '    SAFErrorHandling already exists, skipping: ' + name
            continue
        print '    Creating SAFErrorHandling: ' + name
        _cd_jms_resource(module_name)
        create(name, 'SAFErrorHandling')
        cd('SAFErrorHandlings/' + name)
        policy = get_str(eh, 'policy')
        log_format = get_str(eh, 'logFormat')
        if policy:
            cmo.setPolicy(policy)
        if log_format:
            cmo.setLogFormat(log_format)
        # errorDestination is a reference to another destination; wire it up
        # in a post-processing pass if needed (destination must exist first).


# ---------------------------------------------------------------------------
# Phase entry point
# ---------------------------------------------------------------------------

def load_jms_modules(data, env):
    print ''
    print '=== Phase 2: JMS modules ==='

    modules = get_list(data, 'jmsModules')

    dry_run = _is_dry_run(env)
    if not dry_run:
        edit()
        startEdit()
    try:
        for module in modules:
            module_name = get_str(module, 'name')
            if not module_name:
                continue

            if _is_dry_run(env):
                print '  [dry-run] Would create JMSSystemResource: ' + module_name
                continue

            if _exists('/JMSSystemResources/' + module_name):
                print '  JMSSystemResource already exists, skipping module: ' + module_name
                continue

            print '  Creating JMSSystemResource: ' + module_name
            cd('/')
            create(module_name, 'JMSSystemResource')
            _assign_targets('JMSSystemResource', module_name, get_list(module, 'targets'), env)

            print '  -- Subdeployments --'
            _load_subdeployments(module_name, get_list(module, 'subdeployments'), env)

            print '  -- Quotas --'
            _load_quotas(module_name, get_list(module, 'quotas'))

            print '  -- Templates --'
            _load_templates(module_name, get_list(module, 'templates'))

            print '  -- Destinations --'
            _load_destinations(module_name, module)

            print '  -- Connection factories --'
            _load_connection_factories(module_name, get_list(module, 'connectionFactories'))

            print '  -- Foreign servers --'
            _load_foreign_servers(module_name, get_list(module, 'foreignServers'))

            print '  -- SAF error handlings --'
            _load_saf_error_handlings(module_name, get_list(module, 'safErrorHandlings'))

        if not dry_run:
            save()
            activate()
            print ''
            print 'Phase 2 activated OK'
    except Exception:
        print 'ERROR in Phase 2: ' + str(sys.exc_info()[1])
        if not dry_run:
            try:
                cancelEdit('y')
            except Exception:
                pass
        raise
