
What FTPAdapter (and similar) actually are
Things like:

eis/ftp/* (FTPAdapter)
eis/file/* (FileAdapter)
eis/db/* (DBAdapter)
custom inbound/outbound adapter configs

👉 are:

deployed as JCA resource adapters (RARs)
configured as application deployments
backed by:

connection pools (JCA)
deployment plans
sometimes MDS configs


✅ Where they live in WebLogic
You access them via:
✅ Application deployments
cmo.getAppDeployments()


What you’ll typically see
Examples:
FtpAdapter
FileAdapter
DbAdapter
JmsAdapter
AqAdapter

And possibly:
FtpAdapter#1.0@MyApp


What you need to extract (important)
For each deployment:
Key attributes:
app.getName()
app.getTargets()
app.getSourcePath()
app.getModuleType()

Optional but useful:
app.getPlanPath()
app.getStagingMode()


Critical distinction (very important)
✔️ Adapters vs deployed composites
You may also see:

SOA composites (e.g. .jar, .sar)
OSB services

👉 You probably do NOT want to extract those for infrastructure build

✅ So you should filter like this
Keep:

Adapter deployments:
FtpAdapter
FileAdapter
DbAdapter
AqAdapter
JmsAdapter

Ignore:
SOA composites (*_rev1.0.jar)
OSB projects
internal system deployments




Why this matters for your rebuild
Without adapters:
✅ JMS rebuilt
✅ SAF rebuilt
❌ integration endpoints broken

Typical failure symptom:

“JMS queues exist, but nothing is consuming or producing”

👉 because FTP/File/DB adapters aren’t deployed.

✅ Rebuild sequence (where adapters fit)
Add a new phase:

🔵 Phase 0 — Deploy adapters (VERY IMPORTANT)
deploy FtpAdapter
deploy FileAdapter
deploy DbAdapter

🟡 Phase 1 — Infrastructure
DS
stores
JMS servers


🟢 Phase 2 — JMS modules

🔴 Phase 3 — SAF agents

👉 Adapters must come before JMS use in composites

⚠️ One subtle but important point
Adapters depend on:

JDBC data sources ✅
file paths / mount points ✅
credentials ✅

👉 So your export needs to include:

sourcePath (for deployment)
planPath (if custom config exists)


Final rule (simple)




Object typeInclude in infra build?
JMS modules / queues     ✅ yes
SAF agents               ✅ yes
adapters (FTP, DB, etc.) ✅ yes
SB_JMS_Proxy_*           ❌ no
SOA composites           ❌ no



Optional deeper inspection
You can inspect a specific pool:
PythongetConnectionPool('eis/Ftp/EO_FtpAdapter')Show more lines
or:
Pythoncmo.getConnectionPool('eis/Ftp/EO_FtpAdapter')Show more lines

👉 This can show:

state
metrics
config details


🧠 What ActiveRAs tells you
Pythoncd('ActiveRAs')ls()Show more lines
👉 You should see:
FtpAdapter
FileAdapter
DbAdapter

✅ confirms deployment is active