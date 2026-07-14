# jms_infrastructure.py
#
# WLST-dependent extraction of domain-level infrastructure (Phase B):
# persistent stores, JMS servers, migratable targets and JDBC data sources.
#
# These objects are prerequisites the JMS/SAF layer references by name only,
# so a migration must create them first, in dependency order:
#   1. persistentStores  -> needed by jmsServers and safAgents
#   2. jmsServers        -> host non-distributed destinations
#   3. migratableTargets -> needed when servers/agents are pinned to them
#   4. jdbcDataSources   -> needed by JDBC stores (full definitions captured)
# Each is split into user-level (extract_data["infrastructure"]) vs system
# (system_data["systemInfrastructure"]) using is_system_infra().
#
# The live configuration MBean (cmo) is passed in as an argument rather than
# relied on as a WLST global.

from jms_filters import get_targets, is_system_infra
from jms_serialize import to_long, to_boolean, safe, _name_of


def extract_infrastructure(cmo, extract_data, system_data):
    _extract_persistent_stores(cmo, extract_data, system_data)
    _extract_jms_servers(cmo, extract_data, system_data)
    _extract_migratable_targets(cmo, extract_data, system_data)
    _extract_jdbc_data_sources(cmo, extract_data, system_data)


def _extract_persistent_stores(cmo, extract_data, system_data):
    # --- Persistent Stores (File + JDBC) ---
    print 'Extracting Persistent Stores...'
    try:
        file_stores = cmo.getFileStores()
        if file_stores:
            for fst in file_stores:
                st_dict = {}
                st_name = str(fst.getName())
                st_dict["name"] = st_name
                st_dict["type"] = "FileStore"
                st_dict["targets"] = get_targets(fst)

                st_dict["directory"] = safe(fst, 'getDirectory')
                st_dict["synchronousWritePolicy"] = safe(fst, 'getSynchronousWritePolicy')
                st_dict["dataSource"] = None
                st_dict["prefixName"] = None

                if is_system_infra(st_name):
                    system_data["systemInfrastructure"]["persistentStores"].append(st_dict)
                else:
                    extract_data["infrastructure"]["persistentStores"].append(st_dict)
    except Exception:
        pass

    try:
        jdbc_stores = cmo.getJDBCStores()
        if jdbc_stores:
            for jst in jdbc_stores:
                st_dict = {}
                st_name = str(jst.getName())
                st_dict["name"] = st_name
                st_dict["type"] = "JDBCStore"
                st_dict["targets"] = get_targets(jst)

                st_dict["directory"] = None
                st_dict["synchronousWritePolicy"] = None
                st_dict["dataSource"] = safe(jst, 'getDataSource', _name_of)
                st_dict["prefixName"] = safe(jst, 'getPrefixName')

                if is_system_infra(st_name):
                    system_data["systemInfrastructure"]["persistentStores"].append(st_dict)
                else:
                    extract_data["infrastructure"]["persistentStores"].append(st_dict)
    except Exception:
        pass


def _extract_jms_servers(cmo, extract_data, system_data):
    # --- JMS Servers (+ store mapping) ---
    print 'Extracting JMS Servers...'
    try:
        jms_servers = cmo.getJMSServers()
        if jms_servers:
            for js in jms_servers:
                js_dict = {}
                js_name = str(js.getName())
                js_dict["name"] = js_name
                js_dict["targets"] = get_targets(js)

                js_dict["persistentStore"] = safe(js, 'getPersistentStore', _name_of)
                js_dict["bytesMaximum"] = safe(js, 'getBytesMaximum', to_long)
                js_dict["messagesMaximum"] = safe(js, 'getMessagesMaximum', to_long)
                js_dict["pagingDirectory"] = safe(js, 'getPagingDirectory')

                if is_system_infra(js_name):
                    system_data["systemInfrastructure"]["jmsServers"].append(js_dict)
                else:
                    extract_data["infrastructure"]["jmsServers"].append(js_dict)
    except Exception:
        pass


def _extract_migratable_targets(cmo, extract_data, system_data):
    # --- Migratable Targets ---
    print 'Extracting Migratable Targets...'
    try:
        mtargets = cmo.getMigratableTargets()
        if mtargets:
            for mt in mtargets:
                mt_dict = {}
                mt_name = str(mt.getName())
                mt_dict["name"] = mt_name

                mt_dict["cluster"] = safe(mt, 'getCluster', _name_of)
                mt_dict["userPreferredServer"] = safe(mt, 'getUserPreferredServer', _name_of)
                mt_dict["migrationPolicy"] = safe(mt, 'getMigrationPolicy')

                if is_system_infra(mt_name):
                    system_data["systemInfrastructure"]["migratableTargets"].append(mt_dict)
                else:
                    extract_data["infrastructure"]["migratableTargets"].append(mt_dict)
    except Exception:
        pass


def _extract_jdbc_data_sources(cmo, extract_data, system_data):
    # --- JDBC Data Sources (full definitions) ---
    # Required by JDBC stores and by UMS/SOA datasources. On 14c the RCU/schema
    # prefix usually differs, so the URL / properties are captured for
    # remapping rather than verbatim copy. NOTE: passwords are intentionally
    # NOT exported (they are domain-encrypted and will not decrypt on the
    # target) - they must be re-entered or supplied separately during import.
    print 'Extracting JDBC Data Sources...'
    try:
        jdbc_resources = cmo.getJDBCSystemResources()
        if jdbc_resources:
            for jr in jdbc_resources:
                ds_dict = {}
                ds_name = str(jr.getName())
                ds_dict["name"] = ds_name
                ds_dict["targets"] = get_targets(jr)

                jndi_names = []
                url = None
                driver_name = None
                global_tx = None
                use_xa = None
                init_capacity = None
                max_capacity = None
                min_capacity = None
                test_table = None
                test_on_reserve = None
                driver_properties = []

                try:
                    res = jr.getJDBCResource()

                    # Data source params (JNDI + transaction protocol)
                    try:
                        dsp = res.getJDBCDataSourceParams()
                        if dsp:
                            try:
                                jn = dsp.getJNDINames()
                                if jn:
                                    for n in jn:
                                        jndi_names.append(str(n))
                            except Exception:
                                pass
                            global_tx = safe(dsp, 'getGlobalTransactionsProtocol')
                    except Exception:
                        pass

                    # Driver params (URL + driver class + properties)
                    try:
                        dp = res.getJDBCDriverParams()
                        if dp:
                            url = safe(dp, 'getUrl')
                            driver_name = safe(dp, 'getDriverName')
                            use_xa = safe(dp, 'isUseXADataSourceInterface', to_boolean)
                            try:
                                props = dp.getProperties()
                                if props:
                                    plist = props.getProperties()
                                    if plist:
                                        for p in plist:
                                            p_dict = {}
                                            p_dict["name"] = str(p.getName())
                                            p_dict["value"] = safe(p, 'getValue')
                                            driver_properties.append(p_dict)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Connection pool params (capacity + test settings)
                    try:
                        cp = res.getJDBCConnectionPoolParams()
                        if cp:
                            init_capacity = safe(cp, 'getInitialCapacity', to_long)
                            max_capacity = safe(cp, 'getMaxCapacity', to_long)
                            min_capacity = safe(cp, 'getMinCapacity', to_long)
                            test_table = safe(cp, 'getTestTableName')
                            test_on_reserve = safe(cp, 'isTestConnectionsOnReserve', to_boolean)
                    except Exception:
                        pass
                except Exception:
                    pass

                ds_dict["jndiNames"] = jndi_names
                ds_dict["url"] = url
                ds_dict["driverName"] = driver_name
                ds_dict["globalTransactionsProtocol"] = global_tx
                ds_dict["useXADataSourceInterface"] = use_xa
                ds_dict["initialCapacity"] = init_capacity
                ds_dict["maxCapacity"] = max_capacity
                ds_dict["minCapacity"] = min_capacity
                ds_dict["testTableName"] = test_table
                ds_dict["testConnectionsOnReserve"] = test_on_reserve
                ds_dict["driverProperties"] = driver_properties
                # Passwords are deliberately omitted (domain-encrypted; re-enter
                # on the target). Flag so the import script knows to
                # prompt/supply.
                ds_dict["passwordExported"] = False

                if is_system_infra(ds_name):
                    system_data["systemInfrastructure"]["jdbcDataSources"].append(ds_dict)
                else:
                    extract_data["infrastructure"]["jdbcDataSources"].append(ds_dict)
    except Exception:
        pass
