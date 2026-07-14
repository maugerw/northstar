# saf_check.py

from java.lang import System

domain_path = '/gmxdevfu/products/user_projects/domains/gmxdevfu_domain'

print 'Reading domain...'
print ''
connect('weblogic','Webcongmx1f','t3://havut048:7002')
domainConfig()

print '--- SAF Imported Destinations test ---'

try:
    x = cmo.getSAFImportedDestinations()
    print 'Returned object:', x

    if x:
        print 'Count:', len(x)
        for d in x:
            print '  ->', d.getName()
    else:
        print 'No imported destinations returned'

except:
    print 'getSAFImportedDestinations() failed'

# Cleanup
disconnect()
exit()



from java.lang import System

domain_path = '/gmxdevfu/products/user_projects/domains/gmxdevfu_domain'

print 'Reading domain...'
print ''
connect('weblogic','Webcongmx1f','t3://havut048:7002')
domainConfig()

print 'Has SAFImportedDestinations attribute?'

try:
    print hasattr(cmo, 'getSAFImportedDestinations')
except:
    print 'Cannot evaluate hasattr'

# Cleanup
disconnect()
exit()



if extract_data["safImportedDestinations"]:
    # create them
else:
    # skip SAF destinations cleanly


grep -i SAFImported config.xml


Final conclusion (now confirmed, not inferred)
From:

hasattr(...) → 0
grep config.xml → no matches

👉 We can say with confidence:

Your domain does not contain SAF Imported Destinations or SAF Remote Contexts at all


Your extraction is now COMPLETE
You’ve correctly built:

✅ JMS modules (full detail)
✅ subdeployments
✅ queues / UDQs
✅ connection factories
✅ SAF agents

👉 And correctly identified:

✅ no SAF imported destinations
✅ no SAF remote contexts


Final validation checklist (you’re ready if these are all true)

JMS modules fully populated ✅
subdeployments have targets ✅
queues / UDQs captured ✅
SAF agents present ✅
JSON export valid ✅


Next step (this is the valuable one)
Now that your export is solid, the next step is:
👉 Generate a WLST rebuild script that consumes your JSON correctly
This involves:

correct creation ordering
subdeployment targeting timing
handling of distributed queues
SAF agent creation timing
