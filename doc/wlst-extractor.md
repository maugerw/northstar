Below is a **practical WLST offline extractor example** focused on **JMS + SAF**, aligned with how your IL estate structures things (modules, subdeployments, JNDI-critical naming, SAF agents, etc.).

This is not “production-ready tooling”, but it’s a **clean baseline you can extend into a real migration pipeline**.

***

# ✅ 1. Basic WLST extractor structure

Run with:

```bash
$MW_HOME/oracle_common/common/bin/wlst.sh extract_jms_saf.py
$WL_HOME/common/bin/wlst.sh extract_jms_saf.py
```

***

## 🔧 Script: extract JMS + SAF config

```python
# extract_jms_saf.py

from java.lang import System

domain_path = '/u01/oracle/user_projects/domains/your_domain'

# Output container
config = {
    "jmsModules": [],
    "safAgents": []
}

def get_targets(mbean):
    targets = []
    try:
        for t in mbean.getTargets():
            targets.append(t.getName())
    except:
        pass
    return targets


# -------------------------
# Load domain (OFFLINE)
# -------------------------
print 'Reading domain...'
readDomain(domain_path)


# -------------------------
# JMS MODULES
# -------------------------
print 'Extracting JMS Modules...'
cd('/JMSSystemResources')

for module in cmo.getJMSSystemResources():
    
    module_dict = {
        "name": module.getName(),
        "targets": get_targets(module),
        "subdeployments": [],
        "queues": [],
        "connectionFactories": []
    }

    # --- Subdeployments ---
    for sub in module.getSubDeployments():
        sub_dict = {
            "name": sub.getName(),
            "targets": [t.getName() for t in sub.getTargets()]
        }
        module_dict["subdeployments"].append(sub_dict)

    # --- JMS Resource ---
    jms_res = module.getJMSResource()

    # --- Queues ---
    for q in jms_res.getQueues():
        q_dict = {
            "name": q.getName(),
            "jndi": q.getJNDIName(),
            "subdeployment": q.getSubDeploymentName(),
        }
        module_dict["queues"].append(q_dict)

    # --- Connection Factories ---
    for cf in jms_res.getConnectionFactories():
        cf_dict = {
            "name": cf.getName(),
            "jndi": cf.getJNDIName(),
            "subdeployment": cf.getSubDeploymentName()
        }
        module_dict["connectionFactories"].append(cf_dict)

    config["jmsModules"].append(module_dict)


# -------------------------
# SAF AGENTS
# -------------------------
print 'Extracting SAF Agents...'
cd('/SAFAgents')

for saf in cmo.getSAFAgents():

    saf_dict = {
        "name": saf.getName(),
        "targets": get_targets(saf),
        "store": saf.getStore().getName() if saf.getStore() else None
    }

    config["safAgents"].append(saf_dict)


# -------------------------
# OUTPUT (simple print)
# -------------------------
print '\n=== EXTRACTED CONFIG ===\n'

for m in config["jmsModules"]:
    print 'JMS Module:', m["name"]
    print '  Targets:', m["targets"]

    print '  Subdeployments:'
    for s in m["subdeployments"]:
        print '    -', s["name"], '->', s["targets"]

    print '  Queues:'
    for q in m["queues"]:
        print '    -', q["name"], '| JNDI:', q["jndi"], '| Sub:', q["subdeployment"]

    print '  ConnectionFactories:'
    for cf in m["connectionFactories"]:
        print '    -', cf["name"], '| JNDI:', cf["jndi"]

    print ''

print 'SAF Agents:'
for s in config["safAgents"]:
    print '  -', s["name"], '| Targets:', s["targets"], '| Store:', s["store"]


# -------------------------
# Cleanup
# -------------------------
closeDomain()
```

***

# ✅ 2. What this extracts (mapped to your environment)

This script gives you:

## JMS layer (what you need for IL)

* JMS Modules
* Subdeployments (critical for targeting)
* Queues:
  * name
  * JNDI name ✅ (must match exactly in your estate)
  * subdeployment ✅ (maps to JMS Server / cluster)
* Connection Factories

👉 This matches what your release notes currently require you to manually recreate (modules, queues, JNDI, targets).

***

## SAF layer

* SAF Agents
* Targets (cluster/server)
* Store (file/JDBC)

👉 This aligns with your SAF setup pattern:

* agent + module + subdeployment + remote config

***

# ⚠️ 3. Gaps you will need to extend

This is where real-world complexity kicks in (and where most migrations fail).

***

## A. JMS (important extensions)

You’ll likely want to add:

```python
q.getRedeliveryLimit()
q.getExpirationPolicy()
q.getErrorDestination()
```

And for CFs:

```python
cf.getDefaultTargetingEnabled()
cf.getXAConnectionFactoryEnabled()
```

👉 These matter for:

* retry behaviour
* poison message handling

***

## B. SAF (critical missing pieces)

This script only extracts **SAF agents**, but in reality you also need:

* Remote SAF contexts
* Imported destinations
* Endpoint URLs

These live under:

```
/JMSSystemResources/<SAFModule>/JMSResource/<...>
```

👉 Meaning:
SAF is split across:

* SAFAgents (transport)
* JMS modules (destinations)

***

## C. Target resolution

Right now you only get target **names**:

```python
['WAMJMSServer1', 'WAMJMSServer2']
```

But in your environment, you should map:

* JMS Server → Managed Server → Cluster

👉 Otherwise deployments will mismatch.

***

# ✅ 4. Example output (what you’ll actually see)

```text
JMS Module: WAMJMSModule
  Targets: ['SOA_Cluster']

  Subdeployments:
    - WAM_JMS_Subdeployment -> ['WAMJMSServer1', 'WAMJMSServer2']

  Queues:
    - WAM_IPS_JMS_Q | JNDI: jms/WAM_IPS_JMS_Q | Sub: WAM_JMS_Subdeployment

  ConnectionFactories:
    - WAM_CF | JNDI: jms/WAM_CF

SAF Agents:
  - GIS_SAF_AGENT | Targets: ['SOA_Server1'] | Store: FileStore1
```

***

# 🧭 5. How to use this in a migration

## Step 1

Run extractor → capture output (or write JSON instead of print)

## Step 2

Transform into:

* WLST **create script**, OR
* declarative config (YAML/JSON)

## Step 3

Replay into target:

```python
create('WAMJMSModule', 'JMSSystemResource')
cd('JMSSystemResources/WAMJMSModule')
assign('JMSSystemResource', 'WAMJMSModule', 'Target', 'SOA_Cluster')
```

***

# ⚠️ 6. Key pitfalls (specific to your setup)

Based on your IL patterns:

### 1. Subdeployment → JMS server mismatch

* Most common failure
* Queue exists but **not bound to correct JMSServer**

***

### 2. JNDI mismatch

* Breaks:
  * DB adapters
  * SOA references
  * OSB pipelines

***

### 3. SAF silent failure

* Agent exists, but:
  * wrong endpoint
  * wrong remote context

👉 Messages accumulate locally

***

# ✅ 7. Suggested next step (high value)

Extend this script to:

* output **structured JSON**
* include:
  * JMS + SAF + JDBC
* feed into:
  * a **single environment build pipeline**

***

If you want, I can build the **matching WLST “recreate script generator”** so you can go full round-trip (extract → generate → apply), which is where this becomes genuinely production-usable.
