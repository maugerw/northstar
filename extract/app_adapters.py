# app_adapters.py
#
# The live configuration MBean (cmo) is passed in as an argument rather than
# relied on as a WLST global.

from jms_filters import get_targets, is_system_adapter, is_system_adapter_source
from jms_serialize import safe, to_long

def _sort_strings(items):
    # Sort a list of plain strings (e.g. targets / jndiNames) in place.
    if not items:
        return
    items.sort()

def extract_adapters(cmo, extract_data, system_data):
    print 'Extracting Adapters...'

    # App deployments live on the domain MBean; guard the call so a missing
    # accessor does not abort the whole extraction run.
    try:
        apps = cmo.getAppDeployments()
    except Exception:
        return

    for app in apps:

        name = str(app.getName())

        # filter only adapters (case-insensitive, like the rest of the codebase)
        if "adapter" in name.lower():

            app_dict = {}

            app_dict["name"] = name
            app_dict["targets"] = get_targets(app)

            source = None
            plan = None

            try:
                sp = app.getSourcePath()
                if sp:
                    source = str(sp)
            except Exception:
                pass

            try:
                pp = app.getPlanPath()
                if pp:
                    plan = str(pp)
            except Exception:
                pass

            app_dict["sourcePath"] = source
            app_dict["planPath"] = plan
            if plan is not None:
                app_dict["connectionInstances"] = extract_connection_instances(plan)

            # Route to user vs. system export.
            #
            # An adapter is treated as a *system* (stock) object when either
            # its name matches a known Oracle adapter OR its sourcePath
            # resolves under the Oracle home connectors directory (e.g.
            # .../soa/connectors/XyzAdapter.rar). Stock adapters carry no
            # custom config plan.
            #
            # A *custom* (user) adapter is identified by carrying its own
            # deployment/config plan (planPath) - a stock-named adapter with a
            # custom plan is exactly what the user-level import script needs,
            # so the plan wins and forces user routing.
            is_system = is_system_adapter(name) or is_system_adapter_source(source)
            if plan is not None or not is_system:
                extract_data["adapterDeployments"].append(app_dict)
            else:
                system_data["adapterDeployments"].append(app_dict)

def extract_connection_instances(plan_path):
    instances = {}
    f = open(plan_path, 'r')

    for line in f:
        if 'connection-instance/' in line and 'jndi-name="eis/' in line:
            start = line.find('jndi-name="') + 11
            end = line.find('"', start)
            jndi = line[start:end]
            instances[jndi] = 1

    f.close()

    for item in instances.keys():
        print 'item: ', item
    #return sorted(instances.keys())
    return _sort_strings(instances.keys())

def extract_adapter_runtime(domain_runtime, extract_data, system_data):
    # READ-ONLY runtime pass.
    #
    # This walks the domainRuntime() ConnectorService tree to capture the
    # *effective* (live) connection-pool configuration of each active resource
    # adapter, e.g.:
    #
    #   domainRuntime()/ServerRuntimes/<srv>/ConnectorServiceRuntime/
    #       ConnectorService/ActiveRAs/<ra>/ConnectionPools/<pool>
    #
    # IMPORTANT: this runtime state is captured purely as a diagnostic - it is
    # NOT something the user import script should "load". Runtime pool counts
    # are per-server/per-moment and are the merged result of the deployed .rar
    # (weblogic-ra.xml) + deployment plan. We keep it on the system side for
    # reference and use it to DIFF against the exported adapter deployments so
    # we can flag adapters whose configuration may live outside the plan (the
    # hand-deployed ftpadapter case).
    #
    # The whole pass is best-effort: the managed server(s) may be down, or the
    # runtime MBeans may be unavailable, so every navigation step is guarded.
    print 'Reading adapter runtime connection pools...'

    pools = []

    try:
        server_runtimes = domain_runtime.getServerRuntimes()
    except Exception:
        print 'server runtime fail'
        return

    if not server_runtimes:
        return

    for srt in server_runtimes:
        server_name = safe(srt, 'getName')

        try:
            csr = srt.getConnectorServiceRuntime()
        except Exception:
            csr = None
        if not csr:
            continue

        try:
            active_ras = csr.getActiveRAs()
        except Exception:
            active_ras = []
        if not active_ras:
            continue

        for ra in active_ras:
            ra_name = safe(ra, 'getName')

            try:
                ra_pools = ra.getConnectionPools()
            except Exception:
                ra_pools = []
            if not ra_pools:
                continue

            for cp in ra_pools:
                pool_dict = {}
                pool_dict["server"] = server_name
                pool_dict["activeRA"] = ra_name
                pool_dict["name"] = safe(cp, 'getName')
                pool_dict["poolName"] = safe(cp, 'getPoolName')
                pool_dict["connectionFactoryName"] = safe(cp, 'getConnectionFactoryName')
                pool_dict["jndiName"] = safe(cp, 'getJNDIName')
                pool_dict["initialCapacity"] = safe(cp, 'getInitialCapacity', to_long)
                pool_dict["maxCapacity"] = safe(cp, 'getMaxCapacity', to_long)
                pool_dict["activeConnections"] = safe(cp, 'getActiveConnectionsCurrentCount', to_long)
                pool_dict["freeConnections"] = safe(cp, 'getFreeConnectionsCurrentCount', to_long)
                pools.append(pool_dict)

    # Store the captured runtime state for reference only (diagnostic). It is
    # deliberately kept on the system side so the user import never tries to
    # replay live pool state.
    system_data["adapterRuntimePools"] = pools

    # Build the set of adapter names that were actually exported (user +
    # system) so we can diff the runtime RAs against them.
    exported = {}
    for a in extract_data.get("adapterDeployments", []):
        nm = a.get("name")
        if nm is not None:
            exported[str(nm).lower()] = 1
    for a in system_data.get("adapterDeployments", []):
        nm = a.get("name")
        if nm is not None:
            exported[str(nm).lower()] = 1

    # Append to the existing validation warnings (validate_references has
    # already run and populated this list); do not clobber it.
    warnings = extract_data.get("validationWarnings")
    if warnings is None:
        warnings = []
        extract_data["validationWarnings"] = warnings

    seen_ra = {}
    for p in pools:
        ra_name = p.get("activeRA")
        if ra_name is None:
            continue
        key = str(ra_name).lower()
        if key in seen_ra:
            continue
        seen_ra[key] = 1

        # An active RA name can carry a module/app qualifier (e.g.
        # 'MyApp#FtpAdapter'), so match by substring in either direction.
        matched = 0
        for ename in exported:
            if ename and (ename in key or key in ename):
                matched = 1
                break

        if not matched:
            w = ('Adapter runtime connection pool(s) found for active RA "' +
                 str(ra_name) + '" but no matching adapter deployment was ' +
                 'exported - configuration may live outside the deployment ' +
                 'plan (e.g. weblogic-ra.xml); review before import')
            warnings.append(w)
            print 'WARNING: ' + w
