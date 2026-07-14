# extract_objects.py
#
# Thin WLST entry point.
#
# This script owns the only WLST-interpreter-specific work: connect(),
# domainConfig() and the file writes. All extraction logic lives in separate,
# importable modules that receive their dependencies (the live `cmo`
# configuration MBean and the data dicts) as arguments, so the WLST globals do
# not need to leak into those modules:
#
#   jms_filters.py        - config lists + is_system_* / derive_logical_name
#                           + get_targets (pure, no WLST deps)
#   jms_serialize.py      - to_json / to_long / to_boolean (pure)
#   jms_modules.py        - extract_jms_modules(cmo, extract_data, system_data)
#   jms_infrastructure.py - extract_infrastructure(cmo, extract_data, system_data)
#   jms_saf.py            - extract_saf_agents / extract_saf_imported_destinations
#   app_adapters.py       - extract_adapters(cmo, extract_data, system_data)
#                           + extract_adapter_runtime (read-only runtime pass)
#   jms_validate.py       - sort_user_data / validate_references (pure)
#
# Run with:  $MW_HOME/oracle_common/common/bin/wlst.sh extract_objects.py (or:  java weblogic.WLST extract_objects.py)
# The script directory is added to sys.path so the modules above resolve when
# invoked from any working directory.

import sys
import os

# Ensure the sibling modules are importable regardless of the current working
# directory. Under WLST, sys.argv[0] holds the script path.
try:
    _script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except Exception:
    _script_dir = os.getcwd()
if _script_dir and _script_dir not in sys.path:
    sys.path.append(_script_dir)

from jms_serialize import to_json
from jms_modules import extract_jms_modules
from jms_infrastructure import extract_infrastructure
from jms_saf import extract_saf_agents, extract_saf_imported_destinations
from app_adapters import extract_adapters, extract_adapter_runtime
from jms_validate import sort_user_data, validate_references

# Environment-specific settings (connection + output paths) are NOT hardcoded
# here; they live in a small properties file so the same script can be pointed
# at different environments without editing source. The file is resolved next
# to this script by default, or taken from the first command-line argument:
#
#   wlst extract_objects.py [path/to/extract_objects.properties]
DEFAULT_PROPERTIES_FILE = 'extract_objects.properties'

# Keys expected in the properties file (with sensible defaults where it makes
# sense; the connection values have no safe default and must be provided).
REQUIRED_KEYS = ['admin.user', 'admin.password', 'admin.url', 'output.file']


def load_properties(path):
    # Minimal key=value properties parser (avoids a hard dependency on
    # java.util.Properties so the loader stays unit-testable in CPython too).
    # Lines starting with '#' or ';' are comments; blank lines are ignored.
    props = {}
    f = open(path, 'r')
    try:
        for raw in f.readlines():
            line = raw.strip()
            if not line or line[0] == '#' or line[0] == ';':
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            props[key.strip()] = value.strip()
    finally:
        f.close()
    return props


def resolve_properties_path():
    # Explicit path as first arg wins; otherwise look next to this script.
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    return os.path.join(_script_dir, DEFAULT_PROPERTIES_FILE)


properties_path = resolve_properties_path()
if not os.path.exists(properties_path):
    print 'ERROR: properties file not found: ' + properties_path
    print 'Provide it next to extract_objects.py or pass its path as the first argument.'
    exit()

print 'Loading configuration from ' + properties_path
config = load_properties(properties_path)

_missing = []
for _k in REQUIRED_KEYS:
    if not config.get(_k):
        _missing.append(_k)
if _missing:
    print 'ERROR: missing required properties: ' + ', '.join(_missing)
    exit()

admin_user = config['admin.user']
admin_password = config['admin.password']
admin_url = config['admin.url']
domain_path = config.get('domain.path')
output_file = config['output.file']
# Default the system export next to the user export if not specified.
system_output_file = config.get('system.output.file')
if not system_output_file:
    system_output_file = output_file.replace('.json', '_system.json')


def new_extract_data():
    extract_data = {}
    extract_data["jmsModules"] = []
    extract_data["infrastructure"] = {}
    extract_data["infrastructure"]["persistentStores"] = []
    extract_data["infrastructure"]["jmsServers"] = []
    extract_data["infrastructure"]["migratableTargets"] = []
    extract_data["infrastructure"]["jdbcDataSources"] = []
    extract_data["safAgents"] = []
    extract_data["safImportedDestinations"] = []
    extract_data["safRemoteContexts"] = {}
    extract_data["adapterDeployments"] = []
    extract_data["validationWarnings"] = []
    return extract_data


def new_system_data():
    system_data = {}
    system_data["systemJmsModules"] = []
    system_data["soaInternalQueues"] = []
    system_data["systemSafAgents"] = []
    system_data["systemSafImportedDestinations"] = []
    system_data["systemConnectionFactories"] = []
    system_data["safRemoteContexts"] = {}
    system_data["systemInfrastructure"] = {}
    system_data["systemInfrastructure"]["persistentStores"] = []
    system_data["systemInfrastructure"]["jmsServers"] = []
    system_data["systemInfrastructure"]["migratableTargets"] = []
    system_data["systemInfrastructure"]["jdbcDataSources"] = []
    system_data["adapterDeployments"] = []
    # Read-only diagnostic capture of live adapter connection-pool state
    # (populated by extract_adapter_runtime via domainRuntime()). Never loaded
    # by the import script - see app_adapters.extract_adapter_runtime().
    system_data["adapterRuntimePools"] = []
    return system_data


def write_output(path, data, label):
    try:
        f = open(path, 'w')
        try:
            f.write(to_json(data))
        finally:
            f.close()
        print ''
        print label + ' written to ' + path
    except Exception:
        # Surface the real cause (e.g. missing directory / permission denied)
        # and re-raise so a failed export is not silently reported as success.
        print 'ERROR: Failed to write ' + label + ' to ' + path + ': ' + str(sys.exc_info()[1])
        raise


extract_data = new_extract_data()
system_data = new_system_data()

print 'Reading domain...'
print ''
connect(admin_user, admin_password, admin_url)

# Ensure the WLST session is always released, even if any extraction or write
# step raises - otherwise the session stays connected and the script hangs.
try:
    domainConfig()

    # =========================
    # EXTRACTION (cmo passed in as an argument to each module)
    # =========================
    extract_jms_modules(cmo, extract_data, system_data)
    extract_infrastructure(cmo, extract_data, system_data)
    extract_saf_agents(cmo, extract_data, system_data)
    extract_saf_imported_destinations(cmo, extract_data, system_data)
    extract_adapters(cmo, extract_data, system_data)

    # =========================
    # POST-PROCESSING (pure)
    # =========================
    sort_user_data(extract_data)
    validate_references(extract_data)

    # =========================
    # RUNTIME PASS (read-only, optional)
    # =========================
    # Switch from the config tree to the runtime tree to capture the *live*
    # adapter connection-pool state and diff it against the exported adapters.
    # This is best-effort: the managed server(s) may be down, so guard the
    # whole block and never let it fail the export. It runs AFTER
    # validate_references so it can append (not clobber) validationWarnings.
    print ''
    try:
        domainRuntime()
        extract_adapter_runtime(cmo, extract_data, system_data)
    except Exception:
        print 'NOTE: adapter runtime pass skipped (runtime unavailable): ' + str(sys.exc_info()[1])

    # =========================
    # WRITE OUTPUT
    # =========================
    write_output(output_file, extract_data, 'Export')
    write_output(system_output_file, system_data, 'System export')
finally:
    # Cleanup
    disconnect()

exit()
