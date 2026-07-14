import re

def extract_eis_references(plan_file):

    eis_set = {}

    f = open(plan_file, 'r')

    for line in f:
        if 'eis/' in line:
            matches = re.findall(r'eis/[^"< ]+', line)

            for m in matches:
                eis_set[m] = 1

    f.close()

    return eis_set




if eis_name in eis_map:
    print 'WARNING duplicate EIS:', eis_name



domainRuntime()

cd('/ConnectorComponentRuntime')
ls()

cd('/ConnectorComponentRuntime/FtpAdapter')
ls()




Practical checklist (this is what you want)
For each adapter:
✔ plan file exists
✔ contains connection-instance entries
✔ contains eis/... mappings
✔ deployed with plan
✔ environment values valid (paths, DS, etc.)
👉 If all true → ✅ safe


Final answer
❓ “how would i validate that every eis/... reference matches something in JMS/SAF/JNDI?”

👉 You don’t validate against JMS/SAF/JNDI at all.
Instead:
✅ validate against deployment plan
✅ validate connection-instance definitions exist
✅ optionally validate runtime adapter bindings after deploy


domainRuntime()
cd('/ConnectorComponentRuntime/FtpAdapter')
ls()

dr--   AdminServer
dr--   osb_server1
dr--   soa_server1




ConnectorServiceRuntime/ConnectorService

cd('FtpAdapter')
ls()


domainRuntime()
cd('/ServerRuntimes/osb_server1/ConnectorServiceRuntime/ConnectorService/ConnectionPools')
ls()
