# jms_validate.py
#
# Pure (WLST-independent) post-processing of the assembled user export:
#   * sort_user_data()      - deterministic ordering of modules/agents/dests
#   * validate_references() - referential-integrity pass
# Both operate purely on the in-memory dicts, so they can be imported and
# unit-tested in plain CPython/Jython 2.


def _safe_key(value):
    # Stable, comparison-safe sort key: None sorts as empty string and the
    # value is always a string so mixed/None names never raise under Jython 2.
    if value is None:
        return ''
    return str(value)


def _sort_dicts_by_name(items):
    # Sort a list of dicts in place by their "name" field (deterministic).
    if not items:
        return
    temp = []
    for it in items:
        temp.append((_safe_key(it.get("name")), it))
    temp.sort()
    sorted_items = []
    for t in temp:
        sorted_items.append(t[1])
    items[:] = sorted_items


def _sort_strings(items):
    # Sort a list of plain strings (e.g. targets / jndiNames) in place.
    if not items:
        return
    items.sort()


# Per-module child collections that are lists of named dicts.
_MODULE_CHILD_LISTS = [
    "subdeployments", "queues", "uniformDistributedQueues",
    "distributedQueues", "connectionFactories", "templates", "topics",
    "uniformDistributedTopics", "distributedTopics", "quotas",
    "destinationKeys", "foreignServers", "safErrorHandlings",
]

# Infrastructure collections that are lists of named dicts.
_INFRA_CHILD_LISTS = [
    "persistentStores", "jmsServers", "migratableTargets", "jdbcDataSources",
]


def _sort_module(m):
    # Sort every named child collection inside a single JMS module, plus the
    # nested foreign-server children and any "targets" lists, so two exports of
    # the same module are byte-for-byte comparable.
    for key in _MODULE_CHILD_LISTS:
        if key in m:
            _sort_dicts_by_name(m[key])

    if "targets" in m and isinstance(m["targets"], list):
        _sort_strings(m["targets"])

    # Sort nested targets / foreign-server children.
    for key in _MODULE_CHILD_LISTS:
        for child in m.get(key, []):
            if isinstance(child, dict):
                if "targets" in child and isinstance(child["targets"], list):
                    _sort_strings(child["targets"])
                if "foreignDestinations" in child:
                    _sort_dicts_by_name(child["foreignDestinations"])
                if "foreignConnectionFactories" in child:
                    _sort_dicts_by_name(child["foreignConnectionFactories"])


def sort_user_data(extract_data):
    # Top-level JMS modules (and all of their children).
    _sort_dicts_by_name(extract_data["jmsModules"])
    for m in extract_data["jmsModules"]:
        _sort_module(m)

    # Domain-level infrastructure lists.
    infra = extract_data.get("infrastructure")
    if infra:
        for key in _INFRA_CHILD_LISTS:
            if key in infra:
                _sort_dicts_by_name(infra[key])
        # Sort nested targets / jndiNames / driverProperties for stability.
        for key in _INFRA_CHILD_LISTS:
            for item in infra.get(key, []):
                if not isinstance(item, dict):
                    continue
                if "targets" in item and isinstance(item["targets"], list):
                    _sort_strings(item["targets"])
                if "jndiNames" in item and isinstance(item["jndiNames"], list):
                    _sort_strings(item["jndiNames"])
                if "driverProperties" in item:
                    _sort_dicts_by_name(item["driverProperties"])

    # SAF agents.
    _sort_dicts_by_name(extract_data["safAgents"])
    for s in extract_data["safAgents"]:
        if "targets" in s and isinstance(s["targets"], list):
            _sort_strings(s["targets"])

    # SAF imported destinations: key on remoteContext + name so destinations
    # sharing a context stay grouped deterministically.
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
    for d in extract_data["safImportedDestinations"]:
        if "targets" in d and isinstance(d["targets"], list):
            _sort_strings(d["targets"])


def validate_references(extract_data):
    # Validate that every reference exported in the user file resolves to
    # another object present in the same user export. Dangling references (e.g.
    # an error destination that was filtered out as internal/system, or a
    # subdeployment that does not exist in the module) are nulled out and logged
    # as warnings so the import script never tries to wire something that is not
    # present.
    print 'Validating user export references...'

    # Build the set of all destination names exported at user level.
    user_destination_names = {}
    for m in extract_data["jmsModules"]:
        for q in m["queues"]:
            user_destination_names[q["name"]] = 1
        for udq in m["uniformDistributedQueues"]:
            user_destination_names[udq["name"]] = 1
        for dq in m["distributedQueues"]:
            user_destination_names[dq["name"]] = 1
        for tp in m["topics"]:
            user_destination_names[tp["name"]] = 1
        for udt in m["uniformDistributedTopics"]:
            user_destination_names[udt["name"]] = 1
        for dt in m["distributedTopics"]:
            user_destination_names[dt["name"]] = 1

    validation_warnings = []

    for m in extract_data["jmsModules"]:
        # Subdeployment names defined in this module.
        module_subdeps = {}
        for sub in m["subdeployments"]:
            module_subdeps[sub["name"]] = 1

        dest_lists = [
            m["queues"], m["uniformDistributedQueues"], m["distributedQueues"],
            m["topics"], m["uniformDistributedTopics"], m["distributedTopics"],
        ]
        for dlist in dest_lists:
            for d in dlist:
                err = d.get("errorDestination")
                if err is not None and err not in user_destination_names:
                    validation_warnings.append(
                        'Destination "' + d["name"] + '" in module "' + m["name"] +
                        '" references missing errorDestination "' + err + '" - reference nulled'
                    )
                    d["errorDestination"] = None

                sub = d.get("subdeployment")
                if sub is not None and sub != '' and sub != 'None' and sub not in module_subdeps:
                    validation_warnings.append(
                        'Destination "' + d["name"] + '" in module "' + m["name"] +
                        '" references missing subdeployment "' + sub + '" - reference nulled'
                    )
                    d["subdeployment"] = None

        # Templates only carry an errorDestination reference (not a
        # subdeployment).
        for t in m["templates"]:
            err = t.get("errorDestination")
            if err is not None and err not in user_destination_names:
                validation_warnings.append(
                    'Template "' + t["name"] + '" in module "' + m["name"] +
                    '" references missing errorDestination "' + err + '" - reference nulled'
                )
                t["errorDestination"] = None

        # SAF error handlings reference an error destination by name.
        for eh in m["safErrorHandlings"]:
            err = eh.get("errorDestination")
            if err is not None and err not in user_destination_names:
                validation_warnings.append(
                    'SAFErrorHandling "' + eh["name"] + '" in module "' + m["name"] +
                    '" references missing errorDestination "' + err + '" - reference nulled'
                )
                eh["errorDestination"] = None

    extract_data["validationWarnings"] = validation_warnings

    for w in validation_warnings:
        print 'WARNING: ' + w

    return validation_warnings
