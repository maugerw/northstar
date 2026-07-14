# jms_filters.py
#
# Pure (WLST-independent) filter configuration and classifiers.
# These have no dependency on the live WLST interpreter, so they can be
# imported and unit-tested in plain CPython/Jython 2.
#
# get_targets() is included here as a generic helper: it operates only on the
# mbean passed in as an argument (no reliance on WLST globals), so it is safe
# to share between the extraction modules.

# ===== FILTER CONFIGURATION =====
# NOTE: All patterns below MUST be lowercase. Matching is case-insensitive
# (names are lowercased before comparison), so do not add mixed/upper case here.
SYSTEM_MODULE_PREFIXES = [
    'soa', 'osb', 'bpm', 'bam', 'mds',
    'oim', 'oam', 'owsm', 'ums',
    'edn', 'mediator', 'bpel',
    'oracle', 'wlsb', 'wli', 'jrf', 'configwiz',
    'jmsresources',
]

SYSTEM_MODULE_SUBSTRINGS = [
    'wls', 'internal', 'system',
    '_auto_', 'wsee', 'weblogic', 'reliable',
    'wlsb', 'wli',
]

INTERNAL_QUEUE_PREFIXES = [
    'dist_', 'ora', 'wli', 'weblogic.wsee',
    'bpm', 'edn', 'ums', 'mediator', 'jrf',
]

INTERNAL_QUEUE_SUBSTRINGS = [
    '_auto', '_internal', 'system', 'asyncws', 'wsee',
]

SYSTEM_SAF_PREFIXES = [
    'soa', 'osb', 'bpm', 'oracle', 'ums',
    'edn', 'mediator', 'bpel', 'bam', 'jrf',
]

SYSTEM_SAF_SUBSTRINGS = [
    'internal', 'system', 'weblogic', '_auto', 'wsee', 'reliable',
]

SYSTEM_CF_SUBSTRINGS = ['weblogic', 'system', 'internal', 'wlsb']

# Stock Oracle SOA/technology adapters that ship with the domain. These are
# infrastructure objects and belong in the system export. A *custom* adapter
# (one that carries its own deployment/config plan) is routed to the user
# export instead - see is_system_adapter() and extract_adapters().
SYSTEM_ADAPTER_NAMES = [
    'fileadapter', 'ftpadapter', 'dbadapter', 'jmsadapter', 'aqadapter',
    'mqseriesadapter', 'socketadapter', 'umsadapter', 'coherenceadapter',
    'mftadapter', 'b2badapter', 'healthcareadapter', 'appadapter',
    'oracleappsadapter', 'sapadapter', 'restadapter', 'soadirectadapter',
    'ldapadapter', 'msmqadapter', 'siebeladapter', 'jdeworldadapter',
    'jdedwardsadapter', 'peoplesoftadapter', 'oracleebusinessadapter',
    'sfdcadapter', 'sabadapter', 'cdcadapter',
]

SYSTEM_ADAPTER_PREFIXES = ['oracle', 'soa', 'osb', 'mft', 'b2b']

SYSTEM_ADAPTER_SUBSTRINGS = ['internal', 'system', 'weblogic', '_auto']

# Source-path fragments that identify a stock adapter regardless of its name.
# Adapters that ship with the domain resolve their .rar under the Oracle home
# (e.g. .../soa/soa/connectors/XyzAdapter.rar), so a sourcePath that points
# into a connectors directory is a strong "system" signal.
SYSTEM_ADAPTER_SOURCE_SUBSTRINGS = ['/soa/connectors/', '\\soa\\connectors\\',
    '/connectors/', '\\connectors\\']

# Domain-level infrastructure (persistent stores, JMS servers, migratable
# targets, JDBC data sources). These names follow the same lowercase rule.
SYSTEM_INFRA_PREFIXES = [
    'soa', 'osb', 'bpm', 'bam', 'mds', 'oim', 'oam', 'owsm', 'ums',
    'edn', 'mediator', 'bpel', 'oracle', 'wlsb', 'jrf', 'configwiz',
    'orasdpm', 'opss', 'localsvctbl', 'wlsschema', 'sysman', 'ias',
    'leasing',
]

SYSTEM_INFRA_SUBSTRINGS = [
    'internal', 'system', 'weblogic', '_auto', 'wsee', 'reliable',
    'mds-', '-soa', 'opss', 'stb', 'orasdpm', 'jrf',
]
# ================================

def get_targets(mbean):
    targets = []
    try:
        tlist = mbean.getTargets()
        for t in tlist:
            targets.append(str(t.getName()))
    except Exception:
        pass
    return targets

def is_system_module(name):
    lname = name.lower()
    for prefix in SYSTEM_MODULE_PREFIXES:
        if lname.startswith(prefix):
            return 1
    for sub in SYSTEM_MODULE_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def is_soa_internal_queue(name):
    lname = name.lower()
    for prefix in INTERNAL_QUEUE_PREFIXES:
        if lname.startswith(prefix):
            return 1
    for sub in INTERNAL_QUEUE_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def is_system_saf(name):
    lname = name.lower()
    for prefix in SYSTEM_SAF_PREFIXES:
        if lname.startswith(prefix):
            return 1
    for sub in SYSTEM_SAF_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def is_system_connection_factory(name):
    lname = name.lower()
    for sub in SYSTEM_CF_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def is_system_adapter(name):
    lname = name.lower()
    # Exact stock adapter names.
    for stock in SYSTEM_ADAPTER_NAMES:
        if lname == stock:
            return 1
    for prefix in SYSTEM_ADAPTER_PREFIXES:
        if lname.startswith(prefix):
            return 1
    for sub in SYSTEM_ADAPTER_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def is_system_adapter_source(source):
    # A stock adapter is identified by its .rar resolving under the Oracle
    # home connectors directory. Returns 0 when source is None/empty.
    if not source:
        return 0
    lsource = source.lower()
    for sub in SYSTEM_ADAPTER_SOURCE_SUBSTRINGS:
        if sub in lsource:
            return 1
    return 0

def is_system_infra(name):
    lname = name.lower()
    for prefix in SYSTEM_INFRA_PREFIXES:
        if lname.startswith(prefix):
            return 1
    for sub in SYSTEM_INFRA_SUBSTRINGS:
        if sub in lname:
            return 1
    return 0

def derive_logical_name(name):
    if '_auto' in name:
        base = name.split('/')[-1]        # OraSDPMEngineRcvQ1_auto
        base = base.split('_auto')[0]
        return base
    return name
