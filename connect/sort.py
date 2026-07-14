


# sort by name

temp = []

for d in extract_data["safImportedDestinations"]:
    name = d["name"]
    if name is None:
        name = ''
    temp.append((name, d))

temp.sort()

sorted_dests = []

for t in temp:
    sorted_dests.append(t[1])

extract_data["safImportedDestinations"] = sorted_dests


# If there’s any chance "name" could be None or missing (rare but possible in SAF):
# Use a safe key:

temp = []

for d in extract_data["safImportedDestinations"]:
    name = d["name"]
    if name is None:
        name = ''
    temp.append((name, d))

temp.sort()

sorted_dests = []

for t in temp:
    sorted_dests.append(t[1])

extract_data["safImportedDestinations"] = sorted_dests


# Sometimes sorting purely by name isn’t optimal.
# Sort by remote context + name (more meaningful for rebuild)

temp = []

for d in extract_data["safImportedDestinations"]:
    rc = d["remoteContext"]
    if rc is None:
        rc = ''
    name = d["name"]
    if name is None:
        name = ''

    temp.append((rc + '_' + name, d))

temp.sort()

sorted_dests = []

for t in temp:
    sorted_dests.append(t[1])

extract_data["safImportedDestinations"] = sorted_dests

