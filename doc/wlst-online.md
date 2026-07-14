
# WLST online script
# Usage idea:
#   wlst.sh recreate_jms_saf_online.py
#
# Before running, adjust ADMIN_URL / credentials or externalize them.

from migration_config import CONFIG

ADMIN_URL  = 't3://target-admin-host:7001'
ADMIN_USER = 'weblogic'
ADMIN_PWD  = 'replace_me'


# -------------------------
# Helpers
# -------------------------

def exists(path):
    try:
        return getMBean(path) is not None
    except:
        return False

def ensure_edit():
    edit()
    startEdit()

def save_and_activate():
    save()
    activate(block='true')

def cancel_if_needed():
    try:
        cancelEdit('y')
    except:
        pass

def ensure_jms_module(module_name, target_type, target_name):
    path = '/JMSSystemResources/%s' % module_name
    if not exists(path):
        print 'Creating JMS module:', module_name
        cd('/')
        cmo.createJMSSystemResource(module_name)
    else:
        print 'JMS module already exists:', module_name

    # target module
    print 'Targeting JMS module %s to %s/%s' % (module_name, target_type, target_name)
    try:
        assign('JMSSystemResource', module_name, target_type, target_name)
    except:
        print 'WARNING: assign may already exist for module', module_name

def ensure_subdeployment(module_name, sub_name, targets):
    sub_path = '/JMSSystemResources/%s/SubDeployments/%s' % (module_name, sub_name)
    cd('/JMSSystemResources/%s' % module_name)

    if not exists(sub_path):
        print 'Creating subdeployment:', sub_name
        cmo.createSubDeployment(sub_name)
    else:
        print 'Subdeployment already exists:', sub_name

    for t in targets:
        print 'Assigning subdeployment %s to %s/%s' % (sub_name, t['type'], t['name'])
        try:
            assign('SubDeployment', '%s/%s' % (module_name, sub_name), t['type'], t['name'])
        except:
            print 'WARNING: assign may already exist for subdeployment', sub_name, 'target', t['name']

def ensure_queue(module_name, queue_cfg):
    queue_name = queue_cfg['name']
    queue_path = '/JMSSystemResources/%s/JMSResource/%s/Queues/%s' % (
        module_name, module_name, queue_name
    )

    cd('/JMSSystemResources/%s/JMSResource/%s' % (module_name, module_name))

    if not exists(queue_path):
        print 'Creating queue:', queue_name
        cmo.createQueue(queue_name)
    else:
        print 'Queue already exists:', queue_name

    cd(queue_path)
    cmo.setJNDIName(queue_cfg['jndi'])
    cmo.setSubDeploymentName(queue_cfg['subdeployment'])

def ensure_cf(module_name, cf_cfg):
    cf_name = cf_cfg['name']
    cf_path = '/JMSSystemResources/%s/JMSResource/%s/ConnectionFactories/%s' % (
        module_name, module_name, cf_name
    )

    cd('/JMSSystemResources/%s/JMSResource/%s' % (module_name, module_name))

    if not exists(cf_path):
        print 'Creating connection factory:', cf_name
        cmo.createConnectionFactory(cf_name)
    else:
        print 'Connection factory already exists:', cf_name

    cd(cf_path)
    cmo.setJNDIName(cf_cfg['jndi'])
    cmo.setSubDeploymentName(cf_cfg['subdeployment'])

def lookup_store(store_cfg):
    store_type = store_cfg['type']
    store_name = store_cfg['name']

    if store_type == 'FileStore':
        return getMBean('/FileStores/%s' % store_name)
    elif store_type == 'JDBCStore':
        return getMBean('/JDBCStores/%s' % store_name)
    else:
        raise Exception('Unsupported store type: ' + store_type)

def ensure_saf_agent(saf_cfg):
    saf_name = saf_cfg['name']
    path = '/SAFAgents/%s' % saf_name

    if not exists(path):
        print 'Creating SAF agent:', saf_name
        cd('/')
        cmo.createSAFAgent(saf_name)
    else:
        print 'SAF agent already exists:', saf_name

    cd(path)

    # target SAF agent
    target_type = saf_cfg['target']['type']
    target_name = saf_cfg['target']['name']
    print 'Targeting SAF agent %s to %s/%s' % (saf_name, target_type, target_name)
    try:
        assign('SAFAgent', saf_name, target_type, target_name)
    except:
        print 'WARNING: assign may already exist for SAF agent', saf_name

    # attach persistent store if specified
    if 'store' in saf_cfg and saf_cfg['store']:
        store_mbean = lookup_store(saf_cfg['store'])
        if store_mbean is None:
            raise Exception('Store not found for SAF agent %s: %s/%s' % (
                saf_name, saf_cfg['store']['type'], saf_cfg['store']['name']
            ))
        cmo.setStore(store_mbean)


# -------------------------
# Main
# -------------------------

try:
    print 'Connecting to target admin server...'
    connect(ADMIN_USER, ADMIN_PWD, ADMIN_URL)

    ensure_edit()

    # JMS
    for module in CONFIG.get('jmsModules', []):
        ensure_jms_module(
            module['name'],
            module['target']['type'],
            module['target']['name']
        )

        for sub in module.get('subdeployments', []):
            ensure_subdeployment(module['name'], sub['name'], sub.get('targets', []))

        for q in module.get('queues', []):
            ensure_queue(module['name'], q)

        for cf in module.get('connectionFactories', []):
            ensure_cf(module['name'], cf)

    # SAF
    for saf in CONFIG.get('safAgents', []):
        ensure_saf_agent(saf)

    save_and_activate()
    print 'Completed successfully.'

except:
    print 'ERROR: apply failed'
    dumpStack()
    cancel_if_needed()
    raise