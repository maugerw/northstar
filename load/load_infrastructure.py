# load_infrastructure.py
#
# Phase 1: domain-level infrastructure.
#
# Creates objects in dependency order within a single edit session:
#   1. JDBC data sources   (referenced by JDBC stores; passwords must be
#                           supplied via properties — passwordExported: false)
#   2. File stores         (no dependencies beyond targets)
#   3. JDBC stores         (reference data sources)
#   4. JMS servers         (reference persistent stores)
#   5. Migratable targets  (reference servers/clusters)
#
# WLST globals (edit, startEdit, activate, cancelEdit, create, assign,
# getMBean, cd, cmo) are used directly — this module must run inside WLST.
#
# env is the environment-mapping dict built from the properties file:
#   env['targets']    - {source_name: target_name} for server/cluster remapping
#   env['passwords']  - {datasource_name: password}
#   env['dry_run']    - True to log without making changes

import sys
from load_serialize import get, get_str, get_list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _exists(mbean_path):
    try:
        return getMBean(mbean_path) is not None
    except Exception:
        return False


def _is_dry_run(env):
    return get(env, 'dry_run', False)


# ---------------------------------------------------------------------------
# JDBC data sources
# ---------------------------------------------------------------------------

def _load_jdbc_data_sources(data, env):
    infra = get(data, 'infrastructure', {})
    sources = get_list(infra, 'jdbcDataSources')
    passwords = get(env, 'passwords', {})

    for ds in sources:
        name = get_str(ds, 'name')
        if not name:
            continue

        if _exists('/JDBCSystemResources/' + name):
            print '  JDBC data source already exists, skipping: ' + name
            continue

        jndi_names = get_list(ds, 'jndiNames')
        url = get_str(ds, 'url')
        driver = get_str(ds, 'driverName')
        global_tx = get_str(ds, 'globalTransactionsProtocol')
        init_cap = get(ds, 'initialCapacity')
        max_cap = get(ds, 'maxCapacity')
        min_cap = get(ds, 'minCapacity')
        test_table = get_str(ds, 'testTableName')
        test_on_reserve = get(ds, 'testConnectionsOnReserve')
        driver_props = get_list(ds, 'driverProperties')
        raw_targets = get_list(ds, 'targets')
        password = passwords.get(name, '')

        if not password:
            print '  WARNING: no password supplied for data source "' + name + '" (add password.' + name + ' to properties)'

        if _is_dry_run(env):
            print '  [dry-run] Would create JDBCSystemResource: ' + name
            continue

        print '  Creating JDBCSystemResource: ' + name
        cd('/')
        create(name, 'JDBCSystemResource')
        cd('/JDBCSystemResources/' + name)

        jr = cmo.getJDBCResource()

        # Data source params (JNDI names + transaction protocol)
        try:
            dsp = jr.getJDBCDataSourceParams()
            if jndi_names:
                import jarray
                import java.lang
                dsp.setJNDINames(jarray.array(jndi_names, java.lang.String))
            if global_tx:
                dsp.setGlobalTransactionsProtocol(global_tx)
        except Exception:
            print '  WARNING: could not set data source params for ' + name + ': ' + str(sys.exc_info()[1])

        # Driver params (URL, driver class, password, properties)
        try:
            dp = jr.getJDBCDriverParams()
            if url:
                dp.setUrl(url)
            if driver:
                dp.setDriverName(driver)
            if password:
                dp.setPassword(password)
            if driver_props:
                props = dp.getProperties()
                for p in driver_props:
                    p_name = get_str(p, 'name')
                    p_value = get_str(p, 'value')
                    if p_name:
                        prop = props.createProperty(p_name)
                        if p_value:
                            prop.setValue(p_value)
        except Exception:
            print '  WARNING: could not set driver params for ' + name + ': ' + str(sys.exc_info()[1])

        # Connection pool params
        try:
            cp = jr.getJDBCConnectionPoolParams()
            if init_cap is not None:
                cp.setInitialCapacity(int(init_cap))
            if max_cap is not None:
                cp.setMaxCapacity(int(max_cap))
            if min_cap is not None:
                cp.setMinCapacity(int(min_cap))
            if test_table:
                cp.setTestTableName(test_table)
            if test_on_reserve is not None:
                cp.setTestConnectionsOnReserve(bool(test_on_reserve))
        except Exception:
            print '  WARNING: could not set pool params for ' + name + ': ' + str(sys.exc_info()[1])

        _assign_targets('JDBCSystemResource', name, raw_targets, env)


# ---------------------------------------------------------------------------
# Persistent stores
# ---------------------------------------------------------------------------

def _load_persistent_stores(data, env):
    infra = get(data, 'infrastructure', {})
    stores = get_list(infra, 'persistentStores')

    for st in stores:
        name = get_str(st, 'name')
        store_type = get_str(st, 'type', 'FileStore')
        if not name:
            continue

        if store_type == 'FileStore':
            _load_file_store(st, env)
        else:
            _load_jdbc_store(st, env)


def _load_file_store(st, env):
    name = get_str(st, 'name')
    directory = get_str(st, 'directory')
    sync_policy = get_str(st, 'synchronousWritePolicy')
    raw_targets = get_list(st, 'targets')

    if _exists('/FileStores/' + name):
        print '  FileStore already exists, skipping: ' + name
        return

    if _is_dry_run(env):
        print '  [dry-run] Would create FileStore: ' + name
        return

    print '  Creating FileStore: ' + name
    cd('/')
    create(name, 'FileStore')
    cd('/FileStores/' + name)
    if directory:
        cmo.setDirectory(directory)
    if sync_policy:
        cmo.setSynchronousWritePolicy(sync_policy)
    _assign_targets('FileStore', name, raw_targets, env)


def _load_jdbc_store(st, env):
    name = get_str(st, 'name')
    ds_name = get_str(st, 'dataSource')
    prefix = get_str(st, 'prefixName')
    raw_targets = get_list(st, 'targets')

    if _exists('/JDBCStores/' + name):
        print '  JDBCStore already exists, skipping: ' + name
        return

    # Guard: the referenced data source must exist.
    ds_mbean = None
    if ds_name:
        try:
            ds_mbean = getMBean('/JDBCSystemResources/' + ds_name)
        except Exception:
            pass
        if ds_mbean is None:
            print '  WARNING: JDBCStore "' + name + '" references missing DataSource "' + ds_name + '" — skipping'
            return

    if _is_dry_run(env):
        print '  [dry-run] Would create JDBCStore: ' + name
        return

    print '  Creating JDBCStore: ' + name
    cd('/')
    create(name, 'JDBCStore')
    cd('/JDBCStores/' + name)
    if ds_mbean:
        cmo.setDataSource(ds_mbean)
    if prefix:
        cmo.setPrefixName(prefix)
    _assign_targets('JDBCStore', name, raw_targets, env)


# ---------------------------------------------------------------------------
# JMS servers
# ---------------------------------------------------------------------------

def _lookup_store(store_name):
    # A JMS server's persistent store can be a FileStore or a JDBCStore.
    for path in ['/FileStores/', '/JDBCStores/']:
        try:
            mb = getMBean(path + store_name)
            if mb is not None:
                return mb
        except Exception:
            pass
    return None


def _load_jms_servers(data, env):
    infra = get(data, 'infrastructure', {})
    servers = get_list(infra, 'jmsServers')

    for js in servers:
        name = get_str(js, 'name')
        if not name:
            continue

        if _exists('/JMSServers/' + name):
            print '  JMSServer already exists, skipping: ' + name
            continue

        store_name = get_str(js, 'persistentStore')
        bytes_max = get(js, 'bytesMaximum')
        msgs_max = get(js, 'messagesMaximum')
        paging_dir = get_str(js, 'pagingDirectory')
        raw_targets = get_list(js, 'targets')

        if _is_dry_run(env):
            print '  [dry-run] Would create JMSServer: ' + name
            continue

        print '  Creating JMSServer: ' + name
        cd('/')
        create(name, 'JMSServer')
        cd('/JMSServers/' + name)

        if store_name:
            store_mbean = _lookup_store(store_name)
            if store_mbean:
                cmo.setPersistentStore(store_mbean)
            else:
                print '  WARNING: JMSServer "' + name + '" references missing store "' + store_name + '"'

        # -1 means unlimited in WebLogic; omit the set so the default is kept.
        if bytes_max is not None and int(bytes_max) >= 0:
            cmo.setBytesMaximum(long(bytes_max))
        if msgs_max is not None and int(msgs_max) >= 0:
            cmo.setMessagesMaximum(long(msgs_max))
        if paging_dir:
            cmo.setPagingDirectory(paging_dir)

        _assign_targets('JMSServer', name, raw_targets, env)


# ---------------------------------------------------------------------------
# Migratable targets
# ---------------------------------------------------------------------------

def _load_migratable_targets(data, env):
    infra = get(data, 'infrastructure', {})
    mtargets = get_list(infra, 'migratableTargets')

    for mt in mtargets:
        name = get_str(mt, 'name')
        if not name:
            continue

        if _exists('/MigratableTargets/' + name):
            print '  MigratableTarget already exists, skipping: ' + name
            continue

        cluster_name = get_str(mt, 'cluster')
        preferred_server = get_str(mt, 'userPreferredServer')
        policy = get_str(mt, 'migrationPolicy')

        if _is_dry_run(env):
            print '  [dry-run] Would create MigratableTarget: ' + name
            continue

        print '  Creating MigratableTarget: ' + name
        cd('/')
        create(name, 'MigratableTarget')
        cd('/MigratableTargets/' + name)

        if cluster_name:
            cluster_mbean = None
            try:
                cluster_mbean = getMBean('/Clusters/' + _map_target(cluster_name, env))
            except Exception:
                pass
            if cluster_mbean:
                cmo.setCluster(cluster_mbean)

        if preferred_server:
            srv_mbean = None
            try:
                srv_mbean = getMBean('/Servers/' + _map_target(preferred_server, env))
            except Exception:
                pass
            if srv_mbean:
                cmo.setUserPreferredServer(srv_mbean)

        if policy:
            cmo.setMigrationPolicy(policy)


# ---------------------------------------------------------------------------
# Phase entry point
# ---------------------------------------------------------------------------

def load_infrastructure(data, env):
    print ''
    print '=== Phase 1: Infrastructure ==='

    edit()
    startEdit()
    try:
        print ''
        print '-- JDBC data sources --'
        _load_jdbc_data_sources(data, env)

        print ''
        print '-- Persistent stores --'
        _load_persistent_stores(data, env)

        print ''
        print '-- JMS servers --'
        _load_jms_servers(data, env)

        print ''
        print '-- Migratable targets --'
        _load_migratable_targets(data, env)

        if not _is_dry_run(env):
            save()
            activate()
            print ''
            print 'Phase 1 activated OK'
    except Exception:
        print 'ERROR in Phase 1: ' + str(sys.exc_info()[1])
        try:
            cancelEdit('y')
        except Exception:
            pass
        raise
