
Absolutely — the most useful next step is a **round-trip pattern**:

1. **extract** source config
2. **store it as structured data**
3. **replay it into the target domain**

Oracle’s documentation explicitly says WLST can be used to **create and manage JMS servers and JMS system module resources**, and that JMS resources such as queues and connection factories are grouped and targeted via **subdeployments**. Oracle’s offline WLST docs also state that `readDomain(domainDirName)` opens an existing domain without connecting to a running server. [\[docs.oracle.com\]](https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/14.1.2/jmsad/wlst.html), [\[docs.oracle.com\]](https://docs.oracle.com/middleware/1221/wls/JMSAD/wlst.htm), [\[docs.oracle.com\]](https://docs.oracle.com/en/middleware/fusion-middleware/12.2.1.4/wlstg/domains.html)

That also fits what I found in your tenant: SSEN WAM 2 On-Premise Release Note and Management Plan R1.44.docx lists manual queue creation with **module, queue name, JNDI name, subdeployment, and targets**, and your [Updated IL\_Analysis\_For\_TechMigration file](https://outlook.office365.com/owa/?ItemID=AAMkADQ4OTI3YzA0LTYzMTctNDI0MC1hOWE0LTJlZDM5NzAwY2E2ZABGAAAAAAArBvJLM%2fdqQZQMvP31yAmIBwAe22zYgkMzTpR4qe2%2ftfUcAAAAAAEKAAA%2bYz%2bOCXJSTKW8LjUwCMh9AAYXOi1RAAA%3d\&exvsurl=1\&viewmodel=ReadMessageItem\&EntityRepresentationId=3f29e49c-7f4d-40aa-a686-bf55c2167b47) explicitly tracks **DB JNDI** and **JMS Queue** as dependencies. [\[SSEN WAM 2...Plan R1.44 \| Word\]](https://ssecom-my.sharepoint.com/personal/thupakula_mallikarjuna_sse_com/_layouts/15/Doc.aspx?sourcedoc=%7B570DE72E-14D5-48F9-9139-2E5710C6B63D%7D&file=SSEN%20WAM%202%20On-Premise%20Release%20Note%20and%20Management%20Plan%20R1.44.docx&action=default&mobileredirect=true&DefaultItemOpen=1), [\[Updated IL...ation file \| Outlook\]](https://outlook.office365.com/owa/?ItemID=AAMkADQ4OTI3YzA0LTYzMTctNDI0MC1hOWE0LTJlZDM5NzAwY2E2ZABGAAAAAAArBvJLM%2fdqQZQMvP31yAmIBwAe22zYgkMzTpR4qe2%2ftfUcAAAAAAEKAAA%2bYz%2bOCXJSTKW8LjUwCMh9AAYXOi1RAAA%3d&exvsurl=1&viewmodel=ReadMessageItem)

## Recommended shape

For your estate, I’d structure it like this:

* **offline extractor** → reads source domain
* **config file** → neutral structured representation
* **online apply script** → connects to target AdminServer and creates resources in a controlled edit session

That keeps extraction independent from the target environment, while making replay explicit and auditable. Oracle documents WLST both for **offline domain access** and for **managing JMS resources**. [\[docs.oracle.com\]](https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/14.1.2/jmsad/wlst.html), [\[docs.oracle.com\]](https://docs.oracle.com/en/middleware/fusion-middleware/12.2.1.4/wlstg/domains.html)

***

# 1) Suggested exported config file

This is a simple Python data file that your extractor can emit.

## `migration_config.py`

```python
CONFIG = {
    "jmsModules": [
        {
            "name": "WAMJMSModule",
            "target": {"type": "Cluster", "name": "SOA_Cluster"},
            "subdeployments": [
                {
                    "name": "WAM_JMS_Subdeployment",
                    "targets": [
                        {"type": "JMSServer", "name": "WAMJMSServer1"},
                        {"type": "JMSServer", "name": "WAMJMSServer2"}
                    ]
                }
            ],
            "queues": [
                {
                    "name": "WAM_IPS_JMS_Q",
                    "jndi": "jms/WAM_IPS_JMS_Q",
                    "subdeployment": "WAM_JMS_Subdeployment"
                }
            ],
            "connectionFactories": [
                {
                    "name": "WAM_CF",
                    "jndi": "jms/WAM_CF",
                    "subdeployment": "WAM_JMS_Subdeployment"
                }
            ]
        }
    ],
    "safAgents": [
        {
            "name": "GIS_SAF_AGENT",
            "target": {"type": "Server", "name": "SOA_Server1"},
            "store": {"type": "FileStore", "name": "FileStore1"}
        }
    ]
}
```

***

# 2) Suggested replay script

This is the **matching recreate/apply script**.  
I recommend making the **apply step online** so you can target a live AdminServer edit session explicitly.

## `recreate_jms_saf_online.py`

```python
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
```

***

# 3) Why I’d use this pattern in your environment

Your internal material shows that queue definitions in your releases are treated as explicit infrastructure items with **JNDI name**, **subdeployment**, and **targets**, and your migration analysis also tracks **DB JNDI** and **JMS Queue** as named dependencies. That is exactly the sort of configuration that benefits from a structured replay script instead of console rebuilds. [\[SSEN WAM 2...Plan R1.44 \| Word\]](https://ssecom-my.sharepoint.com/personal/thupakula_mallikarjuna_sse_com/_layouts/15/Doc.aspx?sourcedoc=%7B570DE72E-14D5-48F9-9139-2E5710C6B63D%7D&file=SSEN%20WAM%202%20On-Premise%20Release%20Note%20and%20Management%20Plan%20R1.44.docx&action=default&mobileredirect=true&DefaultItemOpen=1), [\[Updated IL...ation file \| Outlook\]](https://outlook.office365.com/owa/?ItemID=AAMkADQ4OTI3YzA0LTYzMTctNDI0MC1hOWE0LTJlZDM5NzAwY2E2ZABGAAAAAAArBvJLM%2fdqQZQMvP31yAmIBwAe22zYgkMzTpR4qe2%2ftfUcAAAAAAEKAAA%2bYz%2bOCXJSTKW8LjUwCMh9AAYXOi1RAAA%3d&exvsurl=1&viewmodel=ReadMessageItem)

Oracle’s JMS WLST documentation also explicitly describes:

* JMS system modules
* targets
* subdeployments
* queues
* connection factories  
  as the main building blocks for scripted management. [\[docs.oracle.com\]](https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/14.1.2/jmsad/wlst.html), [\[docs.oracle.com\]](https://docs.oracle.com/middleware/1221/wls/JMSAD/wlst.htm)

***

# 4) Important caveats before you use it

These are **my implementation cautions**, not claims from a cited source:

## A. Treat this as a **skeleton**

Different WebLogic versions and estate conventions can be a bit fussy around:

* `assign()` behaviour for subdeployments
* exact target type names
* whether a particular resource already exists with partial targeting

So I would treat the script above as:

* **correct shape**
* **good baseline**
* but still something to validate in a lower env first

## B. This does **not yet** cover all SAF detail

This recreates the **SAF Agent** itself.  
It does **not yet** recreate:

* remote SAF contexts
* imported destinations
* remote endpoint URLs
* SAF queue/module details

For a full SAF migration, you would extend the config and add matching creator functions.

## C. It does **not yet** cover JDBC/JNDI data sources

That should be added as a separate section, because your own material shows JNDI names are part of the dependency contract for integrations. [\[Updated IL...ation file \| Outlook\]](https://outlook.office365.com/owa/?ItemID=AAMkADQ4OTI3YzA0LTYzMTctNDI0MC1hOWE0LTJlZDM5NzAwY2E2ZABGAAAAAAArBvJLM%2fdqQZQMvP31yAmIBwAe22zYgkMzTpR4qe2%2ftfUcAAAAAAEKAAA%2bYz%2bOCXJSTKW8LjUwCMh9AAYXOi1RAAA%3d&exvsurl=1&viewmodel=ReadMessageItem)

## D. Keep deployments separate

In your estate, application deployment already appears to be handled separately via release artifacts and customization plans, while JMS resources are called out explicitly in release notes. [\[SSEN WAM 2...Plan R1.44 \| Word\]](https://ssecom-my.sharepoint.com/personal/thupakula_mallikarjuna_sse_com/_layouts/15/Doc.aspx?sourcedoc=%7B570DE72E-14D5-48F9-9139-2E5710C6B63D%7D&file=SSEN%20WAM%202%20On-Premise%20Release%20Note%20and%20Management%20Plan%20R1.44.docx&action=default&mobileredirect=true&DefaultItemOpen=1), [\[SSEN WAM 2...Plan R1.42 \| Word\]](https://ssecom-my.sharepoint.com/personal/thupakula_mallikarjuna_sse_com/_layouts/15/Doc.aspx?sourcedoc=%7B259ECFE0-39C4-445C-918E-A0A0BC420595%7D&file=SSEN%20WAM%202%20On-Premise%20Release%20Note%20and%20Management%20Plan%20R1.42.docx&action=default&mobileredirect=true&DefaultItemOpen=1)

That separation is sensible:

* **infra config first**
* **deployments second**
* **validation third**

***

# 5) The next useful extension

If you want to make this genuinely production-usable, the next increment would be:

1. modify the extractor so it writes **`migration_config.py`**
2. add **JDBC/data source extraction + replay**
3. extend SAF to include:
   * remote contexts
   * imported destinations
4. optionally generate a **diff report**:
   * source vs target module names
   * missing queues
   * mismatched JNDI
   * mismatched subdeployments

That would suit your risk-aware approach much better than a direct “clone and hope” migration.

If you want, I can do the **next concrete piece now**: a matching **JDBC/JNDI extractor + replay skeleton** so the pattern covers both JMS and datasource dependencies.
