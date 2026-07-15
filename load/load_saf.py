# load_saf.py
#
# Phase 3: SAF agents and SAF imported destinations (with remote contexts).
#
# Dependency: SAF agents reference persistent stores created in Phase 1.
# SAF imported destinations reference SAF agents and may reference modules
# (SAF error handlings) created in Phase 2.
#
# SAF remote contexts are stored in extract_data['safRemoteContexts'] as a
# dict keyed by name; they are created inline before the imported destination
# that references them.
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


def _lookup_store(store_name):
    for path in ['/FileStores/', '/JDBCStores/']:
        try:
            mb = getMBean(path + store_name)
            if mb is not None:
                return mb
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# SAF agents
# ---------------------------------------------------------------------------

def _load_saf_agents(data, env):
    agents = get_list(data, 'safAgents')

    for saf in agents:
        name = get_str(saf, 'name')
        if not name:
            continue

        if _exists('/SAFAgents/' + name):
            print '  SAFAgent already exists, skipping: ' + name
            continue

        store_name = get_str(saf, 'store')
        service_type = get_str(saf, 'serviceType')
        retry_base = get(saf, 'retryDelayBase')
        retry_max = get(saf, 'retryDelayMaximum')
        retry_mult = get(saf, 'retryDelayMultiplier')
        ttl = get(saf, 'timeToLive')
        logging_enabled = get(saf, 'loggingEnabled')
        window_size = get(saf, 'windowSize')
        ack_interval = get(saf, 'acknowledgeInterval')
        raw_targets = get_list(saf, 'targets')

        if _is_dry_run(env):
            print '  [dry-run] Would create SAFAgent: ' + name
            continue

        print '  Creating SAFAgent: ' + name
        cd('/')
        create(name, 'SAFAgent')
        cd('/SAFAgents/' + name)

        if store_name:
            store_mbean = _lookup_store(store_name)
            if store_mbean:
                cmo.setStore(store_mbean)
            else:
                print '  WARNING: SAFAgent "' + name + '" references missing store "' + store_name + '"'

        if service_type:
            cmo.setServiceType(service_type)
        if retry_base is not None and int(retry_base) >= 0:
            cmo.setDefaultRetryDelayBase(long(retry_base))
        if retry_max is not None and int(retry_max) >= 0:
            cmo.setDefaultRetryDelayMaximum(long(retry_max))
        if retry_mult is not None:
            cmo.setDefaultRetryDelayMultiplier(long(retry_mult))
        if ttl is not None and int(ttl) >= 0:
            cmo.setDefaultTimeToLive(long(ttl))
        if logging_enabled is not None:
            cmo.setLoggingEnabled(bool(logging_enabled))
        if window_size is not None and int(window_size) > 0:
            cmo.setWindowSize(long(window_size))
        if ack_interval is not None and int(ack_interval) >= 0:
            cmo.setAcknowledgeInterval(long(ack_interval))

        _assign_targets('SAFAgent', name, raw_targets, env)


# ---------------------------------------------------------------------------
# SAF remote contexts
#
# Remote contexts are keyed by name in extract_data['safRemoteContexts'].
# In WebLogic they live at the domain level (/SAFRemoteContexts/<name>).
# ---------------------------------------------------------------------------

def _load_remote_context(rc_name, rc_dict, env):
    if _exists('/SAFRemoteContexts/' + rc_name):
        print '  SAFRemoteContext already exists, skipping: ' + rc_name
        return

    provider_url = get_str(rc_dict, 'providerURL')
    icf = get_str(rc_dict, 'initialContextFactory')
    connection_url = get_str(rc_dict, 'connectionURL')

    if _is_dry_run(env):
        print '  [dry-run] Would create SAFRemoteContext: ' + rc_name
        return

    print '  Creating SAFRemoteContext: ' + rc_name
    cd('/')
    create(rc_name, 'SAFRemoteContext')
    cd('/SAFRemoteContexts/' + rc_name)
    if provider_url:
        cmo.setProviderURL(provider_url)
    if icf:
        cmo.setInitialContextFactory(icf)
    if connection_url:
        cmo.setConnectionURL(connection_url)


# ---------------------------------------------------------------------------
# SAF imported destinations
#
# NOTE: In some WebLogic versions SAFImportedDestinations live at the domain
# level (/SAFImportedDestinations/<name>); in others they are children of JMS
# modules.  The extract reads them from cmo.getSAFImportedDestinations() at
# the domain level, so we create them at the domain level here.  Adjust if
# your domain version requires module-scoped SAF imported destinations.
# ---------------------------------------------------------------------------

def _load_saf_imported_destinations(data, env):
    dests = get_list(data, 'safImportedDestinations')
    remote_contexts = get(data, 'safRemoteContexts', {})

    for dest in dests:
        name = get_str(dest, 'name')
        if not name:
            continue

        # Ensure the remote context exists before creating the destination.
        rc_name = get_str(dest, 'remoteContext')
        if rc_name and rc_name in remote_contexts:
            _load_remote_context(rc_name, remote_contexts[rc_name], env)

        if _exists('/SAFImportedDestinations/' + name):
            print '  SAFImportedDestination already exists, skipping: ' + name
            continue

        remote_jndi = get_str(dest, 'remoteJNDIName')
        local_jndi = get_str(dest, 'localJNDIName')
        qos = get_str(dest, 'qos')
        ttl = get(dest, 'timeToLive')
        logging_enabled = get(dest, 'loggingEnabled')
        raw_targets = get_list(dest, 'targets')

        if _is_dry_run(env):
            print '  [dry-run] Would create SAFImportedDestination: ' + name
            continue

        print '  Creating SAFImportedDestination: ' + name
        cd('/')
        create(name, 'SAFImportedDestination')
        cd('/SAFImportedDestinations/' + name)

        if remote_jndi:
            cmo.setRemoteJNDIName(remote_jndi)
        if local_jndi:
            cmo.setLocalJNDIName(local_jndi)
        if qos:
            cmo.setQualityOfService(qos)
        if ttl is not None and int(ttl) >= 0:
            cmo.setTimeToLiveDefault(long(ttl))
        if logging_enabled is not None:
            cmo.setLoggingEnabled(bool(logging_enabled))

        if rc_name:
            rc_mbean = None
            try:
                rc_mbean = getMBean('/SAFRemoteContexts/' + rc_name)
            except Exception:
                pass
            if rc_mbean:
                cmo.setSAFRemoteContext(rc_mbean)
            else:
                print '  WARNING: SAFImportedDestination "' + name + '" references missing remote context "' + rc_name + '"'

        _assign_targets('SAFImportedDestination', name, raw_targets, env)


# ---------------------------------------------------------------------------
# Phase entry point
# ---------------------------------------------------------------------------

def load_saf(data, env):
    print ''
    print '=== Phase 3: SAF agents and imported destinations ==='

    dry_run = _is_dry_run(env)
    if not dry_run:
        edit()
        startEdit()
    try:
        print ''
        print '-- SAF agents --'
        _load_saf_agents(data, env)

        print ''
        print '-- SAF imported destinations --'
        _load_saf_imported_destinations(data, env)

        if not dry_run:
            save()
            activate()
            print ''
            print 'Phase 3 activated OK'
    except Exception:
        print 'ERROR in Phase 3: ' + str(sys.exc_info()[1])
        if not dry_run:
            try:
                cancelEdit('y')
            except Exception:
                pass
        raise
