# load_objects.py
#
# WLST entry point for importing a domain JMS/infrastructure extract produced
# by extract/extract_objects.py.
#
# Phases:
#   1. Infrastructure  — JDBC data sources, persistent stores, JMS servers,
#                        migratable targets  (load_infrastructure.py)
#   2. JMS modules     — modules, subdeployments, queues/topics/CFs/etc.
#                        (load_jms_modules.py)
#   3. SAF             — SAF agents, remote contexts, imported destinations
#                        (load_saf.py)
#   4. Adapters        — adapter redeploy where source/plan paths are available
#                        (load_adapters.py)
#
# Each phase runs in its own edit/activate session so that a failure in a
# later phase does not roll back earlier committed work.
#
# Configuration is read from a properties file (same format as the extract):
#
#   wlst.sh load_objects.py [path/to/load_objects.properties]
#
# See load_objects.properties.template for all available keys.
#
# Run with:
#   $MW_HOME/oracle_common/common/bin/wlst.sh load_objects.py
#   java weblogic.WLST load_objects.py

import sys
import os

try:
    _script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except Exception:
    _script_dir = os.getcwd()
if _script_dir and _script_dir not in sys.path:
    sys.path.append(_script_dir)

from load_serialize import read_json_file, get, get_str
from load_infrastructure import load_infrastructure
from load_jms_modules import load_jms_modules
from load_saf import load_saf
from load_adapters import load_adapters

DEFAULT_PROPERTIES_FILE = 'load_objects.properties'
REQUIRED_KEYS = ['admin.user', 'admin.password', 'admin.url', 'input.file']


def load_properties(path):
    props = {}
    f = open(path, 'r')
    try:
        for raw in f.readlines():
            line = raw.strip()
            if not line or line[0] in ('#', ';'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            props[key.strip()] = value.strip()
    finally:
        f.close()
    return props


def resolve_properties_path():
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    return os.path.join(_script_dir, DEFAULT_PROPERTIES_FILE)


def build_env(config):
    # Build the env dict that all phase modules receive.  Separates the
    # connection/IO config from the semantic environment-mapping config so
    # phase modules only see what they need.
    env = {}

    # Dry-run mode: log what would happen without making changes.
    env['dry_run'] = config.get('dry.run', 'false').lower() == 'true'

    # Target remapping: target.<source_name>=<target_name>
    targets = {}
    for k, v in config.items():
        if k.startswith('target.'):
            source = k[len('target.'):]
            targets[source] = v
    env['targets'] = targets

    # JDBC passwords: password.<datasource_name>=<password>
    passwords = {}
    for k, v in config.items():
        if k.startswith('password.'):
            ds_name = k[len('password.'):]
            passwords[ds_name] = v
    env['passwords'] = passwords

    # Adapter path overrides: adapter.sourcepath.<name> / adapter.planpath.<name>
    adapter_paths = {}
    for k, v in config.items():
        if k.startswith('adapter.sourcepath.') or k.startswith('adapter.planpath.'):
            adapter_paths[k[len('adapter.'):]] = v
    env['adapter_paths'] = adapter_paths

    # Which phases to run (default: all).
    env['phases'] = config.get('phases', '1,2,3,4')

    return env


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

properties_path = resolve_properties_path()
if not os.path.exists(properties_path):
    print 'ERROR: properties file not found: ' + properties_path
    print 'Provide it next to load_objects.py or pass its path as the first argument.'
    exit()

print 'Loading configuration from ' + properties_path
config = load_properties(properties_path)

missing = [k for k in REQUIRED_KEYS if not config.get(k)]
if missing:
    print 'ERROR: missing required properties: ' + ', '.join(missing)
    exit()

admin_user = config['admin.user']
admin_password = config['admin.password']
admin_url = config['admin.url']
input_file = config['input.file']

if not os.path.exists(input_file):
    print 'ERROR: input file not found: ' + input_file
    exit()

env = build_env(config)

if env['dry_run']:
    print ''
    print '*** DRY RUN MODE — no changes will be made ***'

print ''
print 'Reading extract from ' + input_file
data = read_json_file(input_file)
print 'Extract loaded OK'

if data.get('validationWarnings'):
    print ''
    print 'Validation warnings from extract:'
    for w in data['validationWarnings']:
        print '  ' + w

phases = [p.strip() for p in env['phases'].split(',')]

print ''
print 'Connecting to ' + admin_url + ' ...'
connect(admin_user, admin_password, admin_url)

try:
    if '1' in phases:
        load_infrastructure(data, env)

    if '2' in phases:
        load_jms_modules(data, env)

    if '3' in phases:
        load_saf(data, env)

    if '4' in phases:
        load_adapters(data, env)

    print ''
    print 'Load complete.'
finally:
    disconnect()

exit()
