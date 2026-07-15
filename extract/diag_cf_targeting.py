# diag_cf_targeting.py
#
# Read-only diagnostic to settle how the three "dangling" connection factories
# are actually targeted, given their JNDI names ARE bound at runtime but our
# extract sees no resolving subdeployment / no default targeting / no direct
# targets.
#
# For each (module, cf) pair below it prints:
#   1. module.getSubDeployments() names          (what the extract trusts)
#   2. raw ls() of the SubDeployments MBean node  (ground truth in the tree)
#   3. the CF's SubDeploymentName / DefaultTargetingEnabled / Targets
#   4. whether /JMSSystemResources/<mod>/SubDeployments/<cfname> resolves,
#      and if so its own targets
#
# Reuses the same properties file as the extract for connection details:
#   wlst.sh diag_cf_targeting.py [path/to/extract_objects.properties]

import sys
import os

try:
    _script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except Exception:
    _script_dir = os.getcwd()

DEFAULT_PROPERTIES_FILE = 'extract_objects.properties'

# (module name, connection factory name)
PAIRS = [
    ('MNSAFJMSModule', 'MNSAFConnectionFactory'),
    ('MNSOARemoteJMSModule', 'MNSOARemoteCF'),
    ('WAMJMSModule', 'WAMJMSConnectionFactory'),
]


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


def names_of(mbeans):
    out = []
    if not mbeans:
        return out
    for m in mbeans:
        try:
            out.append(str(m.getName()))
        except Exception:
            out.append('<no-name>')
    return out


properties_path = resolve_properties_path()
if not os.path.exists(properties_path):
    print 'ERROR: properties file not found: ' + properties_path
    exit()

config = load_properties(properties_path)
connect(config['admin.user'], config['admin.password'], config['admin.url'])

try:
    domainConfig()
    # Capture a fixed reference to the domain MBean while we are at the root.
    # cd() below moves `cmo` around, so calling cmo.getJMSSystemResources()
    # inside the loop would fail on the 2nd/3rd iteration (cmo would be a JMS
    # resource node, not the domain). This fixed reference does not drift.
    cd('/')
    _domain = cmo

    for module_name, cf_name in PAIRS:
        print ''
        print '========================================================'
        print 'MODULE: ' + module_name + '   CF: ' + cf_name
        print '========================================================'

        # 1. What getSubDeployments() reports (what the extract uses).
        module_mbean = None
        for m in _domain.getJMSSystemResources():
            if str(m.getName()) == module_name:
                module_mbean = m
                break

        if module_mbean is None:
            print '  MODULE NOT FOUND via getJMSSystemResources()'
            continue

        print ''
        print '1. module.getSubDeployments() names:'
        print '   ' + str(names_of(module_mbean.getSubDeployments()))

        # 2. Raw ls() of the SubDeployments node (ground truth).
        print ''
        print '2. ls of /JMSSystemResources/' + module_name + '/SubDeployments :'
        try:
            cd('/JMSSystemResources/' + module_name + '/SubDeployments')
            ls()
        except:
            print '   (could not cd/ls: ' + str(sys.exc_info()[1]) + ')'

        # 3. CF attributes.
        print ''
        print '3. CF attributes:'
        cf_path = ('/JMSSystemResources/' + module_name + '/JMSResource/' +
                   module_name + '/ConnectionFactories/' + cf_name)
        try:
            cd(cf_path)
            print '   SubDeploymentName      = ' + str(cmo.getSubDeploymentName())
            # Bare except: WLST cmo calls can raise a Java throwable that does
            # not subclass Python Exception in Jython 2.2, so 'except Exception'
            # does not catch it.
            try:
                print '   DefaultTargetingEnabled= ' + str(cmo.isDefaultTargetingEnabled())
            except:
                print '   DefaultTargetingEnabled= <no accessor>'
            # A ConnectionFactory MBean has no getTargets() accessor at all
            # (targeting is via subdeployment or default targeting only), so we
            # deliberately do not call it here - it would throw.
        except:
            print '   (could not read CF at ' + cf_path + ': ' + str(sys.exc_info()[1]) + ')'

        # 4. Does a subdeployment named after the CF resolve directly?
        print ''
        print '4. direct navigate to SubDeployments/' + cf_name + ' :'
        sub_path = '/JMSSystemResources/' + module_name + '/SubDeployments/' + cf_name
        try:
            cd(sub_path)
            print '   RESOLVES. Targets = ' + str(names_of(cmo.getTargets()))
        except:
            print '   does NOT resolve: ' + str(sys.exc_info()[1])

finally:
    disconnect()

exit()
