# connect.py

# connect('weblogic','password','t3://hostname:7001')
connect('weblogic','Webcongmx1f','t3://havut048:7002')
domainConfig()

modules = cmo.getJMSSystemResources()

for m in modules:
    print m.getName()

disconnect()
