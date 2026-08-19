#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""
gen_release_plan.py

Generates the two release-plan documents (condensed + detailed) for a given
environment's export.json, mirroring the hand-written gmx/dev plans byte-for-
byte in structure. Nothing in the output is hardcoded to a specific domain or
environment: every name, host, port, driver, transaction protocol, pool size,
queue/topic list, target set, and "untargeted / needs a password / needs a
pre-existing dependency" flag is derived from the export.json passed in. The
only invariant content is the WebLogic Admin Console click-path itself (same
UI regardless of environment) and a handful of structural facts that don't
vary: passwords are never exported, SOALocalTxDataSource-style system data
sources aren't captured by the extract and must already exist on the target.

Usage:
    python3 gen_release_plan.py environments/<domain>/<env>/export.json

Writes, alongside the input file:
    release-plan.md
    release-plan-detailed.md

Covers the full extract schema (jms_modules.py / jms_infrastructure.py /
jms_saf.py / app_adapters.py), not just the object types gmx/dev happens to
use — queues, uniform/plain distributed queues, topics, uniform/plain
distributed topics, templates, quotas, destination keys, foreign servers,
connection factories, and SAF error handlings are all rendered generically
per module, so a domain that uses topics or foreign servers gets a correct
plan without script changes.
"""

import io
import json
import os
import re
import sys
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Console-facing lookup tables. These describe the WebLogic Admin Console's
# own UI and are genuinely constant across environments/domains -- they are
# not migration-specific data.
# ---------------------------------------------------------------------------

DRIVER_INFO = {
    "oracle.jdbc.xa.client.OracleXADataSource": {
        "dbType": "Oracle",
        "label": "Oracle's Driver (Thin XA) for Service connections; "
                 "Versionless and Version Specific Connections",
    },
    "oracle.jdbc.OracleDriver": {
        "dbType": "Oracle",
        "label": "Oracle's Driver (Thin) for Service connections "
                 "(non-XA)",
    },
    "weblogic.jdbc.sqlserver.SQLServerDriver": {
        "dbType": "MS SQL Server",
        "label": "Microsoft's MS SQL Server Driver (Type 4 XA)",
    },
}

TX_PROTOCOL_STEPS = {
    "TwoPhaseCommit": (
        "leave **Supports Global Transactions** checked, and leave the "
        "radio on **Two-Phase Commit**"
    ),
    "OnePhaseCommit": (
        "leave **Supports Global Transactions** checked, but set the radio "
        "to **One-Phase Commit**"
    ),
    "None": (
        "**uncheck** \"Supports Global Transactions\" entirely -- this data "
        "source does not use a global transaction protocol"
    ),
}

SAF_SERVICE_TYPE_NOTE = {
    "Both": "this agent both sends and receives",
    "Sending-only": "this agent only sends (forwards outbound messages)",
    "Receiving-only": "this agent only receives (accepts imported messages)",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def load_export(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_oracle_url(url):
    """Extract host/port/db-identifier from an Oracle thin URL, whichever
    of the two common styles was used. Returns None if unrecognised (the
    generated doc falls back to asking the operator to read the URL
    directly rather than guessing)."""
    if not url:
        return None
    m = re.match(r"^jdbc:oracle:thin:@//([^:/]+):(\d+)/(.+)$", url)
    if m:
        return {"host": m.group(1), "port": m.group(2), "dbname": m.group(3)}
    m = re.match(r"^jdbc:oracle:thin:@([^:/]+):(\d+):(.+)$", url)
    if m:
        return {"host": m.group(1), "port": m.group(2), "dbname": m.group(3)}
    return None


def driver_props_dict(ds):
    return OrderedDict((p["name"], p["value"]) for p in ds.get("driverProperties", []))


def sqlserver_conn_fields(ds):
    props = driver_props_dict(ds)
    host = props.get("serverName")
    port = props.get("portNumber")
    dbname = props.get("databaseName")
    if not (host and port and dbname):
        m = re.match(r"^jdbc:weblogic:sqlserver://([^:;]+):(\d+)", ds.get("url") or "")
        if m:
            host = host or m.group(1)
            port = port or m.group(2)
    return host, port, dbname


def conn_fields(ds):
    """Return (host, port, dbname) for the Connection Properties wizard
    page, regardless of driver family."""
    driver = ds.get("driverName") or ""
    if "sqlserver" in driver.lower():
        return sqlserver_conn_fields(ds)
    parsed = parse_oracle_url(ds.get("url"))
    if parsed:
        return parsed["host"], parsed["port"], parsed["dbname"]
    return None, None, None


def db_user(ds):
    props = driver_props_dict(ds)
    return props.get("user")


def fmt_targets(targets):
    if not targets:
        return "tick nothing"
    return ", ".join("`%s`" % t for t in targets)


def bool_yesno(v):
    return "Yes" if v else "No"


def slug(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def common_dir_path(paths):
    """Python-2.7-compatible replacement for os.path.commonpath (added in
    3.4). Returns the deepest directory common to all given directory
    paths. Falls back to the first path's parent if there's no overlap
    (mirrors commonpath's behaviour of raising only on truly incompatible
    inputs, which doesn't apply here since these are all POSIX paths from
    the same export)."""
    if not paths:
        return ""
    if len(paths) == 1:
        return paths[0]
    split_paths = [p.split("/") for p in paths]
    common = []
    for parts in zip(*split_paths):
        if all(part == parts[0] for part in parts):
            common.append(parts[0])
        else:
            break
    result = "/".join(common)
    return result if result else paths[0]


# ---------------------------------------------------------------------------
# Environment-derived facts used by both documents (counts, gap detection,
# the set of infra target names that would need substituting on another
# domain).
# ---------------------------------------------------------------------------

def infra_target_names(data):
    """Every distinct non-migratable, non-empty *domain-topology* target
    name referenced anywhere in the export -- this is the set a reader
    must remap if their target domain uses different server/cluster names
    than the source.

    Deliberately excludes subdeployment targets: a subdeployment's target
    is sometimes a real cluster (domain topology) but is often the name of
    a JMS server or SAF agent that *this same plan creates* in Phase 3/4 --
    those are not pre-existing domain names to remap, they're object names
    to create exactly as written, and Phase 5 already spells out the exact
    target to pick for each one. Mixing the two would incorrectly tell the
    reader a created object's name is something they need to "match their
    domain" against.
    """
    names = set()

    def add_all(targets):
        for t in targets or []:
            if "(migratable)" not in t:
                names.add(t)

    infra = data.get("infrastructure", {})
    for ds in infra.get("jdbcDataSources", []):
        add_all(ds.get("targets"))
    for st in infra.get("persistentStores", []):
        add_all(st.get("targets"))
    for js in infra.get("jmsServers", []):
        add_all(js.get("targets"))
    for saf in data.get("safAgents", []):
        add_all(saf.get("targets"))
    for mod in data.get("jmsModules", []):
        add_all(mod.get("targets"))
    for ad in data.get("adapterDeployments", []):
        add_all(ad.get("targets"))

    # Strip out anything that is itself a JMS server or SAF agent name
    # created by this export (covers the case where a module's own
    # top-level target -- rare, but possible on some domains -- happens to
    # coincide with a created object name).
    created_object_names = set()
    for js in infra.get("jmsServers", []):
        created_object_names.add(js["name"])
    for saf in data.get("safAgents", []):
        created_object_names.add(saf["name"])
    names -= created_object_names

    return sorted(names)


def known_data_source_names(data):
    return set(ds["name"] for ds in data.get("infrastructure", {}).get("jdbcDataSources", []))


def external_store_dependencies(data):
    """JDBC stores whose dataSource isn't one of the data sources this
    export also captured -- i.e. a system/pre-existing data source the
    target domain must already have (SOALocalTxDataSource and friends)."""
    known = known_data_source_names(data)
    deps = []
    for st in data.get("infrastructure", {}).get("persistentStores", []):
        if st.get("type") == "JDBCStore":
            ds_name = st.get("dataSource")
            if ds_name and ds_name not in known:
                deps.append((st["name"], ds_name))
    return deps


def untargeted_saf_agents(data):
    return [s["name"] for s in data.get("safAgents", []) if not s.get("targets")]


def _render_extractor_warnings_body(data):
    """Body content shared by both documents' final section: referential-
    integrity warnings the extractor itself found (and safely nulled)
    during export, plus any SAF Imported Destinations captured -- a real
    WebLogic object type this generator does not yet have a validated
    click-through procedure for (no export has populated it before, so no
    procedure has been checked against a live console). Always rendered,
    even when empty, so a warning can never go silently missing on some
    future messier domain -- the reader always sees that this was checked.
    """
    out = []
    a = out.append

    warnings = data.get("validationWarnings") or []
    if warnings:
        a("⚠️ The extractor found %d referential-integrity issue(s) in the "
          "source domain's config and nulled the dangling reference before "
          "export (a safe default -- nothing broken is silently wired into "
          "this plan). Review each one and confirm on the source what it "
          "*should* reference before assuming this plan is complete:\n"
          % len(warnings))
        for w in warnings:
            a("- %s" % w)
        a("")
    else:
        a("No referential-integrity warnings were reported by the extractor "
          "for this export -- every destination/template/error-handling "
          "reference captured here resolved to a real object on the source "
          "domain.\n")

    imported = data.get("safImportedDestinations") or []
    remote_contexts = data.get("safRemoteContexts") or {}
    if imported:
        a("⚠️ This export also captured %d SAF Imported Destination(s) -- a "
          "real WebLogic object (Services → Messaging → Store-and-Forward "
          "Agents → Imported Destinations) that this generator does not "
          "yet have a validated click-through procedure for (no export has "
          "populated this field before now, so no procedure has been "
          "checked against a live console). Configure these manually on the "
          "target using the data below, and treat this as a **known gap** "
          "in the generator, not a completed phase:\n" % len(imported))
        a("| Name | Local JNDI | Remote JNDI | Remote Context | Targets |")
        a("|---|---|---|---|---|")
        for d in imported:
            a("| `%s` | `%s` | `%s` | `%s` | %s |" % (
                d["name"], d.get("localJNDIName"), d.get("remoteJNDIName"),
                d.get("remoteContext"),
                ", ".join(d.get("targets", [])) or "*(none)*"))
        a("")
        cited = sorted(set(d.get("remoteContext") for d in imported if d.get("remoteContext")))
        if cited:
            a("**Remote Context connection details referenced above:**\n")
            for name in cited:
                rc = remote_contexts.get(name)
                if rc:
                    a("- `%s`: Initial Context Factory `%s`, Connection URL "
                      "`%s`, Provider URL `%s`"
                      % (name, rc.get("initialContextFactory"),
                         rc.get("connectionURL"), rc.get("providerURL")))
                else:
                    a("- `%s`: ⚠️ referenced by an imported destination "
                      "above but no matching entry in the export's "
                      "safRemoteContexts -- confirm this remote context "
                      "still exists on the source domain." % name)
    else:
        a("No SAF Imported Destinations were captured in this export.\n")

    return out


def module_child_counts(mod):
    keys = ["queues", "uniformDistributedQueues", "distributedQueues",
            "topics", "uniformDistributedTopics", "distributedTopics",
            "connectionFactories", "templates", "quotas", "destinationKeys",
            "foreignServers", "safErrorHandlings"]
    return sum(len(mod.get(k, [])) for k in keys)


# ---------------------------------------------------------------------------
# CONDENSED plan (release-plan.md) -- procedure once, then data tables.
# Mirrors the structure of the original hand-written gmx/dev/release-plan.md.
# ---------------------------------------------------------------------------

def render_condensed(data, domain, env):
    infra = data.get("infrastructure", {})
    ds_list = infra.get("jdbcDataSources", [])
    stores = infra.get("persistentStores", [])
    file_stores = [s for s in stores if s["type"] == "FileStore"]
    jdbc_stores = [s for s in stores if s["type"] == "JDBCStore"]
    jms_servers = infra.get("jmsServers", [])
    saf_agents = data.get("safAgents", [])
    modules = data.get("jmsModules", [])
    adapters = data.get("adapterDeployments", [])

    out = []
    a = out.append

    a("# Release Plan — SOA Suite Domain JMS / Infrastructure Rebuild\n")
    a("**Domain / Environment:** `%s` / `%s`" % (domain, env))
    a("**Source of values:** `export.json` (generated by `extract_objects.py`)")
    a("**Target:** WebLogic Admin Console (manual deployment)")
    a("**Generated by:** `extract/gen_release_plan.py` -- re-run against a "
      "fresh export if the source domain's config changes.\n")
    a("---\n")

    a("## 1. Purpose & Scope\n")
    a("This plan recreates, on a target WebLogic/SOA Suite domain, the JMS "
      "and\nsupporting infrastructure configuration captured from the source "
      "domain:\n")
    a("- %d JDBC data sources" % len(ds_list))
    a("- %d persistent stores (%d file, %d JDBC)" % (len(stores), len(file_stores), len(jdbc_stores)))
    a("- %d JMS servers" % len(jms_servers))
    a("- %d SAF (Store-and-Forward) agents" % len(saf_agents))
    a("- %d JMS modules with their subdeployments, destinations and "
      "connection factories" % len(modules))
    a("- %d adapter deployments (redeploy + plan)\n" % len(adapters))
    a("**Out of scope:** SOA composites, OSB projects, system/internal "
      "objects (these\nbelong to the domain template / product install).\n")
    a("---\n")

    a("## 2. Prerequisites (complete before starting)\n")
    a("| # | Item | Notes |")
    a("|---|---|---|")
    a("| 2.1 | Admin Console URL + credentials | `http://<admin-host>:<port>/console` |")
    a("| 2.2 | Managed servers / clusters exist | %s (or target-domain equivalents) |"
      % ", ".join("`%s`" % t for t in infra_target_names(data)))
    if ds_list:
        a("| 2.3 | Database passwords | ⚠️ %d data-source passwords — obtain "
          "from vault / DBA (see §5 table) |" % len(ds_list))
    ext_deps = external_store_dependencies(data)
    for i, (store_name, ds_name) in enumerate(ext_deps):
        a("| 2.4.%d | `%s` present | Referenced by `%s`; not in this "
          "extract -- confirm it exists on target |" % (i + 1, ds_name, store_name))
    if adapters:
        a("| 2.5 | Adapter `.rar` + plan files staged | On a path reachable by the target domain (see §11) |")
    a("| 2.6 | Change of target names? | If server/cluster names differ on "
      "target, note the mapping and substitute throughout |")
    a("| 2.7 | Backup | Take a config backup / snapshot of the target domain "
      "before changes |\n")

    a("**Naming substitution:** wherever this plan uses %s,\nsubstitute the "
      "target-domain name if it differs. All other object names (data "
      "sources,\nstores, modules, queues) should be created **exactly as "
      "written** — applications look\nthem up by name/JNDI.\n"
      % ", ".join("`%s`" % t for t in infra_target_names(data)))
    a("---\n")

    a("## 3. Login & Edit Session\n")
    a("Perform once at the start; keep the session for a whole phase, then "
      "activate.\n")
    a("1. Browse to `http://<admin-host>:<port>/console`.")
    a("2. Log in with the admin account.")
    a("3. In the **Change Center** (top-left), click **Lock & Edit**.")
    a("   - All changes below are staged until you click **Activate Changes**.")
    a("4. At the end of each phase, click **Activate Changes**.")
    a("   - If a phase reports errors, use **Undo All Changes** and resolve "
      "before retrying.\n")
    a("> **Discipline:** activate at the end of each phase (not each object). "
      "This keeps\n> related changes atomic and makes rollback per-phase "
      "clean.\n")
    a("---\n")

    a("## 4. Execution Order (dependency chain)\n")
    a("Do the phases strictly in order — later objects reference earlier "
      "ones:\n")
    a("```")
    a("Phase 1  JDBC Data Sources         (referenced by JDBC stores, adapters)")
    a("Phase 2  Persistent Stores         (file + JDBC; reference data sources)")
    a("Phase 3  JMS Servers               (reference persistent stores)")
    a("Phase 4  SAF Agents                (reference persistent stores)")
    a("Phase 5  JMS Modules + children    (reference JMS servers / SAF agents via subdeployments)")
    a("Phase 6  Adapter Deployments       (reference data sources, JMS resources)")
    a("```\n")
    a("---\n")

    # ---- Phase 1: data sources ----
    a("## 5. Phase 1 — JDBC Data Sources\n")
    a("### Procedure (repeat for each data source in the table)\n")
    a("1. **Domain Structure → Services → Data Sources**.")
    a("2. Click **New → Generic Data Source**.")
    a("3. **Page 1:** Name / JNDI Name as per table; Database Type per "
      "driver family; click **Next**.")
    a("4. **Page 2 (Database Driver):** pick the driver matching the "
      "**Driver Class** in the table. Click **Next**.")
    a("5. **Page 3 (Transaction Options):** set per the **Tx Protocol** "
      "column. Click **Next**.")
    a("6. **Page 4 (Connection Properties):** enter database name/host/port/"
      "user/password as best matches. Click **Next**.")
    a("7. **Page 5 (Test):** ignore the assembled URL — it will be "
      "overwritten. Click **Next**.")
    a("8. **Page 6 (Targets):** tick the targets from the table. Click "
      "**Finish**.")
    a("9. **Post-step:** open **Configuration → Connection Pool** and set "
      "URL / Driver Class Name / Properties / Password exactly as the "
      "table, plus **Advanced** Test Table Name and Test Connections On "
      "Reserve, plus Initial/Max/Min capacity.\n")
    a("### Data\n")
    a("> ⚠️ = password required from vault/DBA. None of the %d passwords "
      "were exported.\n" % len(ds_list))
    for i, ds in enumerate(ds_list, 1):
        host, port, dbname = conn_fields(ds)
        props = driver_props_dict(ds)
        drv = DRIVER_INFO.get(ds.get("driverName"), {})
        a("#### 5.%d %s" % (i, ds["name"]))
        a("| Field | Value |")
        a("|---|---|")
        a("| Name / JNDI | `%s` / `%s` |" % (ds["name"], "; ".join(ds.get("jndiNames", []))))
        a("| Driver Class | `%s` |" % ds.get("driverName"))
        a("| Tx Protocol | %s |" % ds.get("globalTransactionsProtocol"))
        a("| URL | `%s` |" % ds.get("url"))
        a("| Properties | %s |" % (", ".join("`%s=%s`" % (k, v) for k, v in props.items()) or "*(none)*"))
        a("| Password | ⚠️ |")
        a("| Test Table | `%s` · Test on Reserve: **%s** |"
          % (ds.get("testTableName"), bool_yesno(ds.get("testConnectionsOnReserve"))))
        a("| Capacity (init/max/min) | %s / %s / %s |"
          % (ds.get("initialCapacity"), ds.get("maxCapacity"), ds.get("minCapacity")))
        a("| Targets | %s |\n" % fmt_targets(ds.get("targets")))
    a("**➡ Activate Changes. Verify:** each data source shows on the Data "
      "Sources list;\nfor targeted ones, Monitoring → Testing → **Test Data "
      "Source** returns success\n(requires correct password).\n")
    a("---\n")

    # ---- Phase 2: persistent stores ----
    a("## 6. Phase 2 — Persistent Stores\n")
    a("### 6a. File Stores\n")
    a("**Procedure (repeat per row):**")
    a("1. **Services → Persistent Stores → New → Create FileStore**.")
    a("2. **Name:** per table. **Target:** per table.")
    a("3. Open the store → set **Directory** (if specified) and **Advanced "
      "→ Synchronous Write Policy** per table. Save.\n")
    a("| Name | Directory | Sync Policy | Target |")
    a("|---|---|---|---|")
    for s in file_stores:
        a("| `%s` | %s | %s | `%s` |" % (
            s["name"],
            ("`%s`" % s["directory"]) if s.get("directory") else "*(default/blank)*",
            s.get("synchronousWritePolicy") or "*(default)*",
            ", ".join(s.get("targets", [])) or "*(none)*",
        ))
    a("")
    a("### 6b. JDBC Stores\n")
    a("**Procedure (repeat per row):**")
    a("1. **Services → Persistent Stores → New → Create JDBCStore**.")
    a("2. **Name / Target / Data Source:** per table.")
    a("3. If **Prefix** is given, open the store and set **Prefix Name**. "
      "Save.\n")
    a("| Name | Data Source | Prefix | Target |")
    a("|---|---|---|---|")
    ext_dep_names = dict(external_store_dependencies(data))
    for s in jdbc_stores:
        ds_note = s["dataSource"]
        if s["name"] in ext_dep_names:
            ds_note += " *(system DS — must pre-exist)*"
        a("| `%s` | `%s` | %s | `%s` |" % (
            s["name"], ds_note,
            ("`%s`" % s["prefixName"]) if s.get("prefixName") else "*(none)*",
            ", ".join(s.get("targets", [])),
        ))
    a("")
    if any("(migratable)" in t for s in jdbc_stores for t in s.get("targets", [])):
        a("> For the `(migratable)` targets, select the migratable target "
          "entry from the\n> target picker (e.g. as listed above), not the "
          "plain server.\n")
    a("**➡ Activate Changes. Verify:** all %d stores appear on the "
      "Persistent Stores list\nwith the correct targets.\n" % len(stores))
    a("---\n")

    # ---- Phase 3: JMS servers ----
    a("## 7. Phase 3 — JMS Servers\n")
    a("**Procedure (repeat per row):**")
    a("1. **Services → Messaging → JMS Servers → New**.")
    a("2. **Name:** per table. **Persistent Store:** select per table. "
      "Click **Next**.")
    a("3. **Target:** per table. Click **Finish**.")
    a("4. (Byte/message maxima are unlimited — leave defaults.)\n")
    a("| Name | Persistent Store | Target |")
    a("|---|---|---|")
    for js in jms_servers:
        a("| `%s` | `%s` | `%s` |" % (js["name"], js["persistentStore"], ", ".join(js.get("targets", []))))
    a("")
    a("**➡ Activate Changes. Verify:** %d JMS servers listed, each bound to "
      "its store,\nhealth OK after the next server restart (or immediately "
      "if dynamically deployed).\n" % len(jms_servers))
    a("---\n")

    # ---- Phase 4: SAF agents ----
    a("## 8. Phase 4 — SAF Agents\n")
    a("**Procedure (repeat per row):**")
    a("1. **Services → Messaging → Store-and-Forward Agents → New**.")
    a("2. **Name:** per table. **Persistent Store:** select per table. "
      "**Agent Type:** per table. Click **Next**.")
    a("3. **Target:** per table. Click **Finish**.")
    a("4. Open the agent → confirm/set the defaults below.\n")
    if saf_agents:
        s0 = saf_agents[0]
        a("**Common settings (all agents):** Retry Delay Base = %s ms · "
          "Retry Delay Max = %s ms · Retry Multiplier = %s · Acknowledge "
          "Interval = %s · Window Size = %s · Time-To-Live = %s · "
          "**Logging = %s**.\n"
          % (s0.get("retryDelayBase"), s0.get("retryDelayMaximum"),
             s0.get("retryDelayMultiplier"), s0.get("acknowledgeInterval"),
             s0.get("windowSize"), s0.get("timeToLive"),
             "ENABLED" if s0.get("loggingEnabled") else "DISABLED"))
    a("| Name | Agent Type | Store | Target |")
    a("|---|---|---|---|")
    for s in saf_agents:
        a("| `%s` | %s | `%s` | %s |" % (
            s["name"], s.get("serviceType"), s["store"],
            ", ".join(s.get("targets", [])) or "*(none — leave untargeted)*"))
    a("")
    untargeted = untargeted_saf_agents(data)
    if untargeted:
        a("> %s untargeted on the source (%s).\n> Recreate as untargeted to "
          "match; confirm with the app owner whether this is intended\n> "
          "before go-live.\n"
          % ("Agent is" if len(untargeted) == 1 else "Agents are",
             ", ".join("`%s`" % u for u in untargeted)))
    a("**➡ Activate Changes.**\n")
    a("---\n")

    # ---- Phase 5: JMS modules ----
    a("## 9. Phase 5 — JMS Modules\n")
    a("For each module: create the module + targets, add **subdeployments "
      "first**, then\ndestinations, then connection factories, then SAF "
      "error handlings.\n")
    a("### Generic procedures\n")
    a("**Create a module:**")
    a("1. **Services → Messaging → JMS Modules → New**.")
    a("2. **Name:** per module heading. Click **Next**.")
    a("3. **Targets:** tick the module target. Click **Next**, then "
      "**Finish**.\n")
    a("**Add a subdeployment:**")
    a("1. Open the module → **Subdeployments** tab → **New**.")
    a("2. **Subdeployment Name:** per table. Click **Next**.")
    a("3. **Targets:** tick the JMS server / SAF agent / cluster per table. "
      "Click **Finish**.\n")
    a("**Add a queue / distributed queue / topic:**")
    a("1. Open the module → **New**.")
    a("2. Select the destination type per table. Click **Next**.")
    a("3. **Name** + **JNDI Name** per table. Click **Next**.")
    a("4. **Subdeployment:** select per table (this also sets the target). "
      "Click **Finish**.")
    a("5. For distributed destinations, set **Load Balancing Policy** per "
      "table after creation.\n")
    a("**Add a connection factory (default targeting):**")
    a("1. Open the module → **New → Connection Factory**. Click **Next**.")
    a("2. **Name** + **JNDI Name** per table. Click **Next**.")
    a("3. **Targeting:** leave **Default Targeting** enabled unless a "
      "subdeployment is listed. Click **Finish**.\n")
    a("**Add a SAF error handling:**")
    a("1. Open the module → **New → SAF Error Handling**. Click **Next**.")
    a("2. **Name** per table, **Policy** per table. Click **Finish**.\n")
    a("---\n")

    for i, mod in enumerate(modules, 1):
        a("### 9.%d %s  — target %s" % (
            i, mod["name"], ", ".join("`%s`" % t for t in mod.get("targets", []))))
        subs = mod.get("subdeployments", [])
        if subs:
            a("**Subdeployments:** " + "; ".join(
                "`%s` → %s" % (s["name"], ", ".join("`%s`" % t for t in s.get("targets", [])))
                for s in subs))
        _render_module_child_tables(a, mod, mod.get("targets"))
        if module_child_counts(mod) == 0 and not subs:
            a("*(no children captured for this module)*")
        a("")
    a("**➡ Activate Changes. Verify:** each module lists its "
      "subdeployments and resources;\ndefault-targeted connection "
      "factories show **Default Targeting** on their Targets tab\n(no "
      "subdeployment).\n")
    a("---\n")

    # ---- Phase 6: adapters ----
    if adapters:
        a("## 10. Phase 6 — Adapter Deployments\n")
        a("> Redeploy each adapter with its plan, then review "
          "connection-instance content.\n> ⚠️ Connection-instance "
          "credentials (host/user/password) live **inside the plan XML** "
          "and were\n> **not exported** — they must be reviewed/updated "
          "for the target after redeploy.\n")
        a("**Procedure (repeat per adapter):**")
        a("1. **Deployments → Install** (or select existing adapter → "
          "**Update** to change the plan).")
        a("2. Browse to the **Source** `.rar` path (see table). Click "
          "**Next**.")
        a("3. Choose **Install this deployment as an application** (or "
          "update). Click **Next**.")
        a("4. Select **Targets** per table. Click **Next**.")
        a("5. Set the **Deployment Plan** path per table. Click "
          "**Finish**.")
        a("6. Open the deployed adapter → **Configuration → Outbound "
          "Connection Pools** →\n   expand each connection-instance JNDI "
          "(below) → review/set host, port, user,\n   password for the "
          "target environment. Save. Update the plan when prompted.\n")
        a("| Adapter | Source (.rar) | Plan | Targets |")
        a("|---|---|---|---|")
        for ad in adapters:
            a("| `%s` | `%s` | `%s` | %s |" % (
                ad["name"], ad["sourcePath"], ad["planPath"],
                ", ".join("`%s`" % t for t in ad.get("targets", []))))
        a("\n**Connection instances per adapter (verify each after "
          "redeploy):**\n")
        for ad in adapters:
            a("- **%s:** %s" % (ad["name"], ", ".join("`%s`" % c for c in ad.get("connectionInstances", []))))
        a("\n**➡ Activate Changes. Verify:** each adapter is **Active** "
          "under Deployments;\nconnection instances resolve (Deployments "
          "→ adapter → Testing / Monitoring).\n")
        a("---\n")

    # ---- Verification & rollback & gaps ----
    a("## 11. Post-Release Verification\n")
    a("| # | Check | How |")
    a("|---|---|---|")
    a("| 11.1 | All data sources healthy | Data Sources → each → "
      "Monitoring → Testing → Test |")
    a("| 11.2 | Persistent stores present | Persistent Stores list — %d "
      "entries |" % len(stores))
    a("| 11.3 | JMS servers running | JMS Servers → each → Monitoring "
      "(Health = OK) |")
    a("| 11.4 | JMS runtime bindings | Environment → Servers → *server* → "
      "View JNDI Tree — confirm each `jms/...` name is bound |")
    a("| 11.5 | SAF agents running | Store-and-Forward Agents → "
      "Monitoring |")
    default_targeted_cfs = [cf["name"] for mod in modules for cf in mod.get("connectionFactories", []) if cf.get("defaultTargetingEnabled")]
    if default_targeted_cfs:
        a("| 11.6 | CF default targeting | %s → Targets tab shows *Default "
          "Targeting* |" % ", ".join("`%s`" % c for c in default_targeted_cfs))
    if adapters:
        a("| 11.7 | Adapters active | Deployments — all %d adapters "
          "*Active* |" % len(adapters))
        a("| 11.8 | Adapter connection instances | Each adapter → Outbound "
          "Connection Pools — instances present and test OK |")
    a("")
    a("---\n")

    a("## 12. Rollback\n")
    a("- **Within a phase (before Activate):** Change Center → **Undo All "
      "Changes**.")
    a("- **After Activate:** delete the objects created in that phase "
      "(reverse order),\n  or restore the pre-change config backup taken "
      "in step 2.7.")
    a("- Objects are additive and independent of existing config, so a "
      "partial rollback\n  is low-risk provided nothing new was targeted "
      "over an existing object of the\n  same name.\n")
    a("---\n")

    a("## 13. Known Gaps / Manual Items\n")
    a("| Item | Action |")
    a("|---|---|")
    if ds_list:
        a("| JDBC passwords (×%d) | Supply from vault during Phase 1 "
          "post-step |" % len(ds_list))
    for store_name, ds_name in ext_deps:
        a("| `%s` data source | Referenced by `%s` — must pre-exist on "
          "target |" % (ds_name, store_name))
    if adapters:
        a("| Adapter connection-instance credentials | Review/update "
          "inside plan XML after Phase 6 |")
        a("| Adapter source/plan paths | Substitute target Oracle home for "
          "the source paths listed in §10 |")
    if untargeted:
        a("| Untargeted SAF agents | %s untargeted on source — confirm "
          "intended |" % ", ".join("`%s`" % u for u in untargeted))
    a("| Target names | Substitute if target domain uses different "
      "server/cluster names |")
    a("")
    a("---\n")

    a("## 14. Extractor Warnings & Uncovered Objects\n")
    a("Fields the *extractor* captures but this plan cannot fully turn "
      "into a click-through\nprocedure on its own -- read this section "
      "even when Sections 1-13 look complete.\n")
    out.extend(_render_extractor_warnings_body(data))

    return "\n".join(out) + "\n"


def _render_module_child_tables(a, mod, module_targets=None):
    if mod.get("queues"):
        a("**Queues:**")
        a("| Name | JNDI | Subdeployment |")
        a("|---|---|---|")
        for q in mod["queues"]:
            a("| `%s` | `%s` | `%s` |" % (q["name"], q["jndi"], q["subdeployment"]))
    if mod.get("uniformDistributedQueues"):
        a("**Uniform Distributed Queues:**")
        a("| Name | JNDI | Load Balancing | Subdeployment |")
        a("|---|---|---|---|")
        for q in mod["uniformDistributedQueues"]:
            a("| `%s` | `%s` | `%s` | `%s` |" % (
                q["name"], q["jndi"], q.get("loadBalancingPolicy") or "*(default)*", q["subdeployment"]))
    if mod.get("distributedQueues"):
        a("**Distributed Queues:**")
        a("| Name | JNDI | Load Balancing | Subdeployment |")
        a("|---|---|---|---|")
        for q in mod["distributedQueues"]:
            a("| `%s` | `%s` | `%s` | `%s` |" % (
                q["name"], q["jndi"], q.get("loadBalancingPolicy") or "*(default)*", q["subdeployment"]))
    if mod.get("topics"):
        a("**Topics:**")
        a("| Name | JNDI | Subdeployment |")
        a("|---|---|---|")
        for t in mod["topics"]:
            a("| `%s` | `%s` | `%s` |" % (t["name"], t["jndi"], t["subdeployment"]))
    if mod.get("uniformDistributedTopics"):
        a("**Uniform Distributed Topics:**")
        a("| Name | JNDI | Load Balancing | Subdeployment |")
        a("|---|---|---|---|")
        for t in mod["uniformDistributedTopics"]:
            a("| `%s` | `%s` | `%s` | `%s` |" % (
                t["name"], t["jndi"], t.get("loadBalancingPolicy") or "*(default)*", t["subdeployment"]))
    if mod.get("distributedTopics"):
        a("**Distributed Topics:**")
        a("| Name | JNDI | Load Balancing | Subdeployment |")
        a("|---|---|---|---|")
        for t in mod["distributedTopics"]:
            a("| `%s` | `%s` | `%s` | `%s` |" % (
                t["name"], t["jndi"], t.get("loadBalancingPolicy") or "*(default)*", t["subdeployment"]))
    if mod.get("connectionFactories"):
        a("**Connection Factories:**")
        a("| Name | JNDI | Targeting |")
        a("|---|---|---|")
        inherit_desc = ("inherits %s" % ", ".join("`%s`" % t for t in module_targets)) if module_targets else "inherits module target"
        for cf in mod["connectionFactories"]:
            targeting = ("**Default targeting** (%s)" % inherit_desc
                         if cf.get("defaultTargetingEnabled")
                         else "Subdeployment `%s`" % cf.get("subdeployment"))
            a("| `%s` | `%s` | %s |" % (cf["name"], cf["jndi"], targeting))
    if mod.get("templates"):
        a("**Templates:**")
        a("| Name | Redelivery Delay | Redelivery Limit | TTL | Priority |")
        a("|---|---|---|---|---|")
        for t in mod["templates"]:
            a("| `%s` | %s | %s | %s | %s |" % (
                t["name"], t.get("redeliveryDelay"), t.get("redeliveryLimit"),
                t.get("timeToLive"), t.get("priority")))
    if mod.get("quotas"):
        a("**Quotas:**")
        a("| Name | Bytes Max | Messages Max | Policy | Shared |")
        a("|---|---|---|---|---|")
        for q in mod["quotas"]:
            a("| `%s` | %s | %s | %s | %s |" % (
                q["name"], q.get("bytesMaximum"), q.get("messagesMaximum"),
                q.get("policy"), bool_yesno(q.get("shared"))))
    if mod.get("destinationKeys"):
        a("**Destination Keys:**")
        a("| Name | Property | Key Type | Direction |")
        a("|---|---|---|---|")
        for dk in mod["destinationKeys"]:
            a("| `%s` | %s | %s | %s |" % (
                dk["name"], dk.get("property"), dk.get("keyType"), dk.get("direction")))
    if mod.get("foreignServers"):
        a("**Foreign Servers:**")
        for fs in mod["foreignServers"]:
            a("- `%s` — Initial Context Factory: `%s`, Connection URL: "
              "`%s`, Default Targeting: %s"
              % (fs["name"], fs.get("initialContextFactory"), fs.get("connectionURL"),
                 bool_yesno(fs.get("defaultTargetingEnabled"))))
            for fd in fs.get("foreignDestinations", []):
                a("  - Foreign Destination `%s`: local `%s` → remote `%s`"
                  % (fd["name"], fd.get("localJNDIName"), fd.get("remoteJNDIName")))
            for fcf in fs.get("foreignConnectionFactories", []):
                a("  - Foreign Connection Factory `%s`: local `%s` → remote `%s`"
                  % (fcf["name"], fcf.get("localJNDIName"), fcf.get("remoteJNDIName")))
    if mod.get("safErrorHandlings"):
        a("**SAF Error Handlings:**")
        a("| Name | Policy |")
        a("|---|---|")
        for eh in mod["safErrorHandlings"]:
            a("| `%s` | `%s` |" % (eh["name"], eh.get("policy")))


# ---------------------------------------------------------------------------
# DETAILED plan (release-plan-detailed.md) -- every object spelled out as
# its own checklist, nothing left as "repeat for each row."
# ---------------------------------------------------------------------------

def render_detailed(data, domain, env):
    infra = data.get("infrastructure", {})
    ds_list = infra.get("jdbcDataSources", [])
    stores = infra.get("persistentStores", [])
    file_stores = [s for s in stores if s["type"] == "FileStore"]
    jdbc_stores = [s for s in stores if s["type"] == "JDBCStore"]
    jms_servers = infra.get("jmsServers", [])
    saf_agents = data.get("safAgents", [])
    modules = data.get("jmsModules", [])
    adapters = data.get("adapterDeployments", [])
    target_names = infra_target_names(data)
    ext_deps = external_store_dependencies(data)
    untargeted = untargeted_saf_agents(data)

    out = []
    a = out.append

    a("# Release Plan (Detailed, Step-by-Step) — SOA Suite Domain JMS / "
      "Infrastructure Rebuild\n")
    a("**Domain / Environment:** `%s` / `%s`" % (domain, env))
    a("**Audience:** this version assumes no familiarity with this "
      "specific migration.\nEvery object is written out individually — "
      "there is no \"repeat this procedure\nfor each row\" step. Work top "
      "to bottom, tick each box, do not skip ahead.\n")
    a("**Source of values:** `export.json` (generated by "
      "`extract_objects.py`), domain\n`%s` / environment `%s`." % (domain, env))
    a("**Target:** WebLogic Admin Console (manual, click-through "
      "deployment).")
    a("**Companion file:** `release-plan.md` in this same folder is the "
      "condensed\nversion of this plan (procedures + lookup tables).")
    a("**Generated by:** `extract/gen_release_plan.py` — re-run against a "
      "fresh export if\nthe source domain's config changes; do not hand-"
      "edit this file, edit the export\nor the generator instead.\n")
    a("---\n")

    a("## 0. Before You Start\n")
    a("- [ ] You have the Admin Console URL and an admin login for the "
      "**target**\n      domain.")
    a("- [ ] You know whether the target domain's server/cluster names "
      "match the\n      source domain's names exactly. The source names "
      "used throughout this\n      plan are: %s. **If your target uses "
      "different names, substitute your\n      names everywhere this plan "
      "says one of those names — object names\n      (data sources, "
      "stores, queues, etc.) are NOT renamed, only these\n      "
      "infrastructure names.**" % ", ".join("`%s`" % t for t in target_names))
    if ds_list:
        a("- [ ] You have the %d database passwords for the data sources "
          "in Phase 1\n      (from vault / DBA — none were exported from "
          "the source domain)." % len(ds_list))
    for store_name, ds_name in ext_deps:
        a("- [ ] You've confirmed `%s` already exists on the target domain "
          "(referenced\n      by persistent store `%s` — this plan does "
          "not create it)." % (ds_name, store_name))
    if adapters:
        a("- [ ] The %d adapter `.rar` files and %d deployment plan `.xml` "
          "files (Phase 6)\n      are staged somewhere the target Admin "
          "Server can read them." % (len(adapters), len(adapters)))
    a("- [ ] You've taken a config backup / snapshot of the target "
      "domain.")
    a("- [ ] **This plan is out of scope for:** SOA composites, OSB "
      "projects, and\n      any system/internal WebLogic objects that "
      "come from the domain\n      template or product install.\n")
    a("---\n")

    a("## 1. Starting an Edit Session\n")
    a("Do this once now, and again at the start of every Phase below (a "
      "Phase always\nends with **Activate Changes**, which closes the "
      "session).\n")
    a("1. [ ] Open a browser to the target Admin Console, e.g.\n       "
      "`http://<admin-host>:<port>/console`.")
    a("2. [ ] Log in with the admin account.")
    a("3. [ ] Top-left corner: find the **Change Center** panel.")
    a("4. [ ] Click **Lock & Edit**. The console now shows you are in an "
      "edit\n       session — everything you do below is staged, not "
      "live, until you\n       activate it.\n")
    a("**At the end of each Phase** (marked with a ➡ in this document):\n")
    a("5. [ ] Click **Activate Changes** in the Change Center.")
    a("6. [ ] If the console reports errors for that phase, click **Undo "
      "All\n       Changes**, fix the problem, and start that phase's "
      "steps again from\n       Lock & Edit.")
    a("7. [ ] If it succeeds, move to the next Phase and start a fresh "
      "Lock & Edit.\n")
    a("Do not activate mid-phase — a partially-created phase can leave "
      "dangling\nreferences.\n")
    a("---\n")

    a("## 2. Order of Work\n")
    a("Do the phases strictly in this order. Each later phase references "
      "objects\ncreated in an earlier one.\n")
    a("1. Phase 1 — %d JDBC Data Sources" % len(ds_list))
    a("2. Phase 2 — %d Persistent Stores (%d File Stores + %d JDBC "
      "Stores)" % (len(stores), len(file_stores), len(jdbc_stores)))
    a("3. Phase 3 — %d JMS Servers" % len(jms_servers))
    a("4. Phase 4 — %d SAF Agents" % len(saf_agents))
    a("5. Phase 5 — %d JMS Modules (with their subdeployments, queues, "
      "connection\n   factories, and SAF error handlings)" % len(modules))
    if adapters:
        a("6. Phase 6 — %d Adapter Deployments" % len(adapters))
    a("")
    a("---\n")

    # ---- PHASE 1 ----
    a("# PHASE 1 — JDBC Data Sources\n")
    a("Start a fresh **Lock & Edit** session (§1) before object 1.1 "
      "below.\n")
    a("For every data source in this phase you will do the same six-page "
      "wizard,\nthen a post-creation step to overwrite three fields the "
      "wizard doesn't set\ncorrectly (URL, Driver Class Name, Properties) "
      "plus the password and pool\nsizing. This is deliberate — the "
      "wizard's assembled values are not trusted;\nwhat you type in the "
      "**Post-Step** for each object below is the value that\nmust end up "
      "saved.\n")
    a("---\n")
    for i, ds in enumerate(ds_list, 1):
        a(_render_datasource_detailed(i, ds))
    a("---\n")
    a("## ➡ End of Phase 1\n")
    a("- [ ] Click **Activate Changes**.")
    a("- [ ] Verify: **Services → Data Sources** lists all %d: %s."
      % (len(ds_list), ", ".join("`%s`" % d["name"] for d in ds_list)))
    targeted_ds = [d for d in ds_list if d.get("targets")]
    untargeted_ds = [d for d in ds_list if not d.get("targets")]
    if targeted_ds:
        a("- [ ] For each of the %d **targeted** ones (%s), open it → "
          "**Monitoring → Testing** tab → select a target server →\n      "
          "click **Test Data Source**. Confirm success (this requires the\n"
          "      password to be correct)."
          % (len(targeted_ds), ", ".join("`%s`" % d["name"] for d in targeted_ds)))
    if untargeted_ds:
        a("- [ ] %s untargeted, so %s cannot be tested this way — just "
          "confirm %s appears in the list with the right URL."
          % (", ".join("`%s`" % d["name"] for d in untargeted_ds),
             "it" if len(untargeted_ds) == 1 else "they",
             "it" if len(untargeted_ds) == 1 else "they"))
    a("\n---\n")

    # ---- PHASE 2 ----
    a("# PHASE 2 — Persistent Stores\n")
    a("Start a fresh **Lock & Edit** session before object 2.1.\n")
    a("There are two kinds: **File Stores** (data written to disk files) "
      "and\n**JDBC Stores** (data written to a database table via a data "
      "source). Do\nall %d file stores first, then all %d JDBC stores — "
      "order between them\ndoesn't matter, but both must finish before "
      "Phase 3.\n" % (len(file_stores), len(jdbc_stores)))
    a("---\n")
    counter = 1
    for fs in file_stores:
        a(_render_filestore_detailed(2, counter, fs))
        counter += 1
    for js in jdbc_stores:
        a(_render_jdbcstore_detailed(2, counter, js, js["name"] in ext_dep_names_only(ext_deps)))
        counter += 1
    a("---\n")
    a("## ➡ End of Phase 2\n")
    a("- [ ] Click **Activate Changes**.")
    a("- [ ] Verify: **Services → Persistent Stores** lists all %d: the %d "
      "file\n      stores (%s) and the %d JDBC stores (%s), each with the "
      "target you set\n      above.\n"
      % (len(stores), len(file_stores),
         ", ".join("`%s`" % s["name"] for s in file_stores),
         len(jdbc_stores), ", ".join("`%s`" % s["name"] for s in jdbc_stores)))
    a("---\n")

    # ---- PHASE 3 ----
    a("# PHASE 3 — JMS Servers\n")
    a("Start a fresh **Lock & Edit** session before object 3.1. Each JMS "
      "server\nbelow references a persistent store created in Phase 2 — "
      "Phase 2 must be\nactivated first.\n")
    for i, js in enumerate(jms_servers, 1):
        a("## 3.%d JMS Server: `%s`\n" % (i, js["name"]))
        a("1. [ ] Domain Structure → **Services → Messaging → JMS Servers "
          "→ New**.")
        a("2. [ ] Name: `%s`." % js["name"])
        a("3. [ ] Persistent Store: `%s`. Click **Next**." % js["persistentStore"])
        a("4. [ ] Target: %s. Click **Finish**." % fmt_targets(js.get("targets")))
        a("5. [ ] Leave Bytes Maximum / Messages Maximum at their "
          "unlimited defaults —\n       no change needed.\n")
    a("---\n")
    a("## ➡ End of Phase 3\n")
    a("- [ ] Click **Activate Changes**.")
    a("- [ ] Verify: **Services → Messaging → JMS Servers** lists all %d: "
      "%s — each\n      bound to the persistent store you set."
      % (len(jms_servers), ", ".join("`%s`" % j["name"] for j in jms_servers)))
    a("- [ ] Check **Monitoring** tab for each — Health should read OK "
      "once the\n      target server has restarted (or immediately if "
      "this is a dynamic\n      cluster that doesn't require a restart).\n")
    a("---\n")

    # ---- PHASE 4 ----
    a("# PHASE 4 — SAF (Store-and-Forward) Agents\n")
    a("Start a fresh **Lock & Edit** session before object 4.1.\n")
    if saf_agents:
        s0 = saf_agents[0]
        a("**Every agent below shares these common advanced settings — "
          "set them on\neach agent after creating it, exactly as "
          "listed:**")
        a("- Retry Delay Base: `%s` ms" % s0.get("retryDelayBase"))
        a("- Retry Delay Maximum: `%s` ms" % s0.get("retryDelayMaximum"))
        a("- Retry Multiplier: `%s`" % s0.get("retryDelayMultiplier"))
        a("- Acknowledge Interval: `%s` (this is the console default — "
          "leave it alone)" % s0.get("acknowledgeInterval"))
        a("- Window Size: `%s`" % s0.get("windowSize"))
        a("- Time-To-Live: `%s` (unlimited)" % s0.get("timeToLive"))
        logging_state = "ENABLED" if s0.get("loggingEnabled") else "DISABLED"
        a("- **Logging: %s** ⚠️ %s\n" % (
            logging_state,
            "this is not the console default (default is disabled) — every "
            "one of the agents below must have logging turned ON."
            if s0.get("loggingEnabled") else
            "confirm this matches the console default before assuming no "
            "action is needed."))
    for i, saf in enumerate(saf_agents, 1):
        a("## 4.%d SAF Agent: `%s`\n" % (i, saf["name"]))
        a("1. [ ] Domain Structure → **Services → Messaging → "
          "Store-and-Forward Agents\n       → New**.")
        a("2. [ ] Name: `%s`." % saf["name"])
        a("3. [ ] Persistent Store: `%s`." % saf["store"])
        note = SAF_SERVICE_TYPE_NOTE.get(saf.get("serviceType"), "")
        a("4. [ ] Agent Type: **%s**%s. Click **Next**."
          % (saf.get("serviceType"), (" (%s)" % note) if note else ""))
        if saf.get("targets"):
            a("5. [ ] Target: %s. Click **Finish**." % fmt_targets(saf.get("targets")))
        else:
            a("5. [ ] Target: **tick nothing** — this agent is untargeted "
              "on the source\n       domain. Click **Finish**.")
        a("6. [ ] Open the agent → set the common settings listed above, "
          "including\n       **Logging = %s**. Save."
          % ("ENABLED" if saf.get("loggingEnabled") else "DISABLED"))
        if not saf.get("targets"):
            a("7. [ ] ⚠️ Note: leaving this untargeted matches the source, "
              "but confirm\n       with the application owner before "
              "go-live whether that's intended\n       or an oversight on "
              "the source domain.")
        a("")
    a("---\n")
    a("## ➡ End of Phase 4\n")
    a("- [ ] Click **Activate Changes**.")
    a("- [ ] Verify: **Services → Messaging → Store-and-Forward Agents** "
      "lists all %d:\n      %s."
      % (len(saf_agents), ", ".join("`%s`" % s["name"] for s in saf_agents)))
    a("- [ ] Open each and confirm Logging matches the value noted above "
      "— this is\n      easy to miss since it isn't always the console "
      "default.\n")
    a("---\n")

    # ---- PHASE 5 ----
    a("# PHASE 5 — JMS Modules\n")
    a("Start a fresh **Lock & Edit** session before object 5.1. Each "
      "module below\nis done completely (module → subdeployment(s) → "
      "destinations/CFs/error\nhandlings) before moving to the next "
      "module.\n")
    a("**General pattern for every module in this phase — the exact "
      "wizard steps\nyou'll repeat, spelled out once here for reference. "
      "Each module section\nbelow tells you exactly what values to type "
      "at each of these steps; you\ndon't need to look anything up "
      "elsewhere.**\n")
    a("- *Create the module itself:* **Services → Messaging → JMS Modules "
      "→ New**\n  → type Name → Next → tick Targets → Next → Finish.")
    a("- *Add a subdeployment* (do this before adding any destination "
      "that uses\n  it): open the module → **Subdeployments** tab → New "
      "→ type Subdeployment\n  Name → Next → tick the Targets (a JMS "
      "server, a SAF agent, or a cluster,\n  depending on the module) → "
      "Finish.")
    a("- *Add a Queue / Topic:* open the module → New → select the "
      "destination\n  type → Next → type Name and JNDI Name → Next → "
      "select the Subdeployment\n  → Finish.")
    a("- *Add a Distributed Queue/Topic (Uniform or plain):* same as "
      "above but\n  select the distributed variant → after Finish, open "
      "it and set Load\n  Balancing Policy.")
    a("- *Add a Connection Factory (default-targeted):* open the module "
      "→ New →\n  **Connection Factory** → Next → type Name and JNDI Name "
      "→ Next → on the\n  Targeting page, **leave \"Default Targeting "
      "Enabled\" checked and do not\n  select a Subdeployment** → "
      "Finish.")
    a("- *Add a SAF Error Handling:* open the module → New → **SAF Error "
      "Handling**\n  → Next → type Name → select Policy → Finish.\n")
    a("---\n")

    for i, mod in enumerate(modules, 1):
        a(_render_module_detailed(i, mod))
    a("---\n")
    a("## ➡ End of Phase 5\n")
    a("- [ ] Click **Activate Changes**.")
    a("- [ ] Verify each of the %d modules lists its subdeployment(s) and "
      "its\n      resources under **Services → Messaging → JMS Modules → "
      "[module\n      name]**." % len(modules))
    default_targeted_cfs = [cf["name"] for mod in modules for cf in mod.get("connectionFactories", []) if cf.get("defaultTargetingEnabled")]
    if default_targeted_cfs:
        a("- [ ] Verify the %d default-targeted connection factories\n      "
          "(%s) each show **Default\n      Targeting** on their **Targets** "
          "tab, with no subdeployment selected."
          % (len(default_targeted_cfs), ", ".join("`%s`" % c for c in default_targeted_cfs)))
    dist_names = []
    for mod in modules:
        for q in mod.get("uniformDistributedQueues", []) + mod.get("distributedQueues", []) + \
                 mod.get("uniformDistributedTopics", []) + mod.get("distributedTopics", []):
            dist_names.append((q["name"], q.get("loadBalancingPolicy")))
    for name, policy in dist_names:
        a("- [ ] Verify `%s`'s Load Balancing Policy shows **%s**." % (name, policy))
    a("\n---\n")

    # ---- PHASE 6 ----
    if adapters:
        a("# PHASE 6 — Adapter Deployments\n")
        a("Start a fresh **Lock & Edit** session before object 6.1. Every "
          "JMS module\nfrom Phase 5 must exist before you deploy adapters "
          "whose connection\ninstances reference JMS resources created "
          "there.\n")
        a("⚠️ **Every connection instance listed below has "
          "host/user/password/JNDI\ncredentials baked into its plan XML "
          "that were not exported from the source\ndomain.** After each "
          "adapter is redeployed, you must open its Outbound\nConnection "
          "Pools and manually review/set these for the target environment\n"
          "— the steps below tell you which connection instances to "
          "check, not what\nvalues to put in them (get those from the "
          "application owner / vault).\n")
        all_dirs = [os.path.dirname(ad["sourcePath"]) for ad in adapters] + \
                   [os.path.dirname(ad["planPath"]) for ad in adapters]
        common_root = common_dir_path(all_dirs)
        a("*(Source paths below use the source domain's Oracle home,\n"
          "`%s`\n(or a parent of it) — substitute your target Oracle\n"
          "home if the `.rar`/plan files are staged at a different path on "
          "the target\nhost.)*\n" % common_root)
        for i, ad in enumerate(adapters, 1):
            a(_render_adapter_detailed(i, ad))
        a("---\n")
        a("## ➡ End of Phase 6\n")
        a("- [ ] Click **Activate Changes**.")
        a("- [ ] Verify: **Deployments** shows %s all as **Active**."
          % ", ".join("`%s`" % ad["name"] for ad in adapters))
        a("- [ ] For each adapter, open **Testing** or **Monitoring** and "
          "confirm each\n      connection instance you configured above "
          "resolves successfully.\n")
        a("---\n")

    # ---- Full verification, rollback, gaps ----
    section_num = 8 if adapters else 7
    a("# %d. Full Post-Release Verification\n" % section_num)
    a("Go through every row below in order — do not skip any even if an "
      "earlier\nphase's own checklist already covered part of it.\n")
    step = 1
    a("%d. [ ] **Data Sources:** each of the %d → Monitoring → Testing → "
      "Test.\n       %s"
      % (step, len(ds_list),
         ("Success for the %d targeted ones; %s just needs to be\n       "
          "present (untargeted, can't be tested this way)."
          % (len(targeted_ds), ", ".join("`%s`" % d["name"] for d in untargeted_ds)))
         if untargeted_ds else "Success for all of them."))
    step += 1
    a("%d. [ ] **Persistent Stores:** all %d present in the list with "
      "correct\n       targets." % (step, len(stores)))
    step += 1
    a("%d. [ ] **JMS Servers:** all %d show Health = OK under Monitoring."
      % (step, len(jms_servers)))
    step += 1
    a("%d. [ ] **JMS runtime bindings:** Environment → Servers → *each "
      "server* →\n       **View JNDI Tree** — confirm every `jms/...` "
      "name from Phase 5\n       appears bound." % step)
    step += 1
    a("%d. [ ] **SAF Agents:** all %d show up under Monitoring with the "
      "correct\n       Logging setting." % (step, len(saf_agents)))
    step += 1
    if default_targeted_cfs:
        a("%d. [ ] **Connection Factory targeting:** %s — each shows "
          "**Default\n       Targeting** on its Targets tab (no "
          "subdeployment)."
          % (step, ", ".join("`%s`" % c for c in default_targeted_cfs)))
        step += 1
    if adapters:
        a("%d. [ ] **Adapters:** all %d show **Active** under "
          "Deployments." % (step, len(adapters)))
        step += 1
        total_ci = sum(len(ad.get("connectionInstances", [])) for ad in adapters)
        a("%d. [ ] **Adapter connection instances:** all %d present under "
          "their\n       respective Outbound Connection Pools and testing "
          "OK." % (step, total_ci))
        step += 1
    a("")
    a("---\n")

    a("# %d. Rollback\n" % (section_num + 1))
    a("- **Within a phase, before Activate Changes:** Change Center → "
      "**Undo All\n  Changes**. This discards everything staged in the "
      "current edit session.")
    a("- **After Activate Changes:** delete the objects created in that "
      "phase, in\n  reverse creation order, or restore the pre-change "
      "config backup taken in\n  §0.")
    a("- Objects created by this plan are additive and don't touch "
      "existing\n  config, so a partial rollback is low-risk — the only "
      "danger is if you\n  target something new over an existing object "
      "with the same name, which\n  none of these object names should "
      "collide with on a clean target domain.\n")
    a("---\n")

    a("# %d. Known Gaps — Confirm Before Go-Live\n" % (section_num + 2))
    a("| # | Item | What to do |")
    a("|---|---|---|")
    gnum = 1
    if ds_list:
        a("| %d | %d JDBC passwords | None were exported — get from "
          "vault/DBA before Phase 1's post-steps. |" % (gnum, len(ds_list)))
        gnum += 1
    for store_name, ds_name in ext_deps:
        a("| %d | `%s` | Must already exist on target — referenced by "
          "persistent store `%s` (Phase 2). |" % (gnum, ds_name, store_name))
        gnum += 1
    if adapters:
        a("| %d | Adapter connection-instance credentials | Baked into "
          "each plan XML, not exported — review/set all %d instances in "
          "Phase 6 before go-live. |"
          % (gnum, sum(len(ad.get("connectionInstances", [])) for ad in adapters)))
        gnum += 1
        a("| %d | Adapter source/plan paths | Substitute your target "
          "Oracle home for the source paths throughout Phase 6. |" % gnum)
        gnum += 1
    if untargeted:
        a("| %d | Untargeted SAF agents | %s — confirm with the app owner "
          "this is intentional, not an oversight, before matching it "
          "here. |"
          % (gnum, ", ".join("`%s`" % u for u in untargeted)))
        gnum += 1
    a("| %d | Target infrastructure names | If your target domain's %s "
      "differ, substitute your names everywhere those appear in this plan "
      "-- everything else (object names) must be created exactly as "
      "written. |"
      % (gnum, ", ".join("`%s`" % t for t in target_names)))
    a("")
    a("---\n")

    a("# %d. Extractor Warnings & Uncovered Objects\n" % (section_num + 3))
    a("Read this section even when every Phase above is ticked off. It "
      "covers two kinds of\nthing the extractor captured that the Phases "
      "above cannot fully turn into a\nclick-through procedure on their "
      "own:\n")
    a("1. **Referential-integrity warnings** -- the extractor found a "
      "reference (an error\n   destination, a subdeployment) that didn't "
      "resolve to a real object on the source\n   domain, and safely "
      "nulled it rather than exporting something broken. ")
    a("2. **SAF Imported Destinations** -- a real WebLogic object type "
      "this generator does\n   not yet have a validated click-through "
      "procedure for.\n")
    out.extend(_render_extractor_warnings_body(data))

    return "\n".join(out) + "\n"


def ext_dep_names_only(ext_deps):
    return set(store_name for store_name, _ in ext_deps)


def _render_datasource_detailed(i, ds):
    out = []
    a = out.append
    host, port, dbname = conn_fields(ds)
    props = driver_props_dict(ds)
    drv = DRIVER_INFO.get(ds.get("driverName"), {"dbType": "*(unrecognised driver -- pick manually)*", "label": ds.get("driverName")})
    tx_step = TX_PROTOCOL_STEPS.get(ds.get("globalTransactionsProtocol"),
                                     "set per the source's Tx Protocol value: `%s`" % ds.get("globalTransactionsProtocol"))
    jndi = "; ".join(ds.get("jndiNames", []))

    a("## 1.%d Data Source: `%s`\n" % (i, ds["name"]))
    a("**Wizard:**")
    a("1. [ ] Domain Structure (left tree) → **Services → Data Sources**.")
    a("2. [ ] Click **New → Generic Data Source**.")
    a("3. [ ] Page \"Create a New JDBC Data Source\":")
    a("   - Name: `%s`" % ds["name"])
    a("   - JNDI Name: `%s`" % jndi)
    a("   - Database Type: **%s**" % drv["dbType"])
    a("   - Click **Next**.")
    a("4. [ ] Page \"Database Driver\": choose the driver matching "
      "`%s`\n       — **%s**. Click **Next**." % (ds.get("driverName"), drv["label"]))
    a("5. [ ] Page \"Transaction Options\": %s. Click **Next**." % tx_step)
    a("6. [ ] Page \"Connection Properties\": enter (these only assemble a "
      "URL the\n       wizard shows you next — you will overwrite it in "
      "the Post-Step):")
    if dbname:
        a("   - Database Name: `%s`" % dbname)
    if host:
        a("   - Host Name: `%s`" % host)
    if port:
        a("   - Port: `%s`" % port)
    if props.get("user"):
        a("   - Database User Name: `%s`" % props["user"])
    a("   - Password / Confirm Password: leave blank for now (set in "
      "Post-Step).")
    a("   - Click **Next**.")
    a("7. [ ] Page \"Test Database Connection\": ignore the assembled URL "
      "shown\n       here — you do not need to click Test Configuration "
      "(it will fail\n       with no password). Click **Next**.")
    if ds.get("targets"):
        a("8. [ ] Page \"Select Targets\": tick %s. Click **Finish**." % fmt_targets(ds.get("targets")))
    else:
        a("8. [ ] Page \"Select Targets\": **tick nothing** — this data "
          "source is\n       untargeted on the source domain. Click "
          "**Finish**.")
    a("\n**Post-Step (open the data source you just created → "
      "Configuration tab):**")
    a("9. [ ] **Connection Pool** sub-tab — set:")
    a("   - URL: `%s`" % ds.get("url"))
    a("   - Driver Class Name: `%s`" % ds.get("driverName"))
    a("   - Properties: %s" % (", ".join("`%s=%s`" % (k, v) for k, v in props.items()) or "*(none)*"))
    a("   - Password: ⚠️ **obtain from vault/DBA** — set here and in "
      "Confirm Password.")
    a("   - Initial Capacity: `%s`" % ds.get("initialCapacity"))
    a("   - Maximum Capacity: `%s`" % ds.get("maxCapacity"))
    a("   - Minimum Capacity: `%s`" % ds.get("minCapacity"))
    a("10. [ ] **Connection Pool → Advanced** (expand the Advanced link):")
    a("   - Test Table Name: `%s`" % ds.get("testTableName"))
    a("   - Test Connections On Reserve: **%s**"
      % ("checked (Yes)" if ds.get("testConnectionsOnReserve") else "unchecked (No)"))
    a("11. [ ] Click **Save**.\n")
    return "\n".join(out)


def _render_filestore_detailed(phase, num, store):
    out = []
    a = out.append
    a("## %d.%d File Store: `%s`\n" % (phase, num, store["name"]))
    a("1. [ ] **Services → Persistent Stores → New → Create FileStore**.")
    a("2. [ ] Name: `%s`. Target: %s. Click **OK**."
      % (store["name"], fmt_targets(store.get("targets"))))
    a("3. [ ] Open the store you just created.")
    if store.get("directory"):
        a("4. [ ] Set **Directory**: `%s`." % store["directory"])
    else:
        a("4. [ ] Leave **Directory** at its default (blank).")
    a("5. [ ] Expand **Advanced** → set **Synchronous Write Policy** to "
      "**%s**." % (store.get("synchronousWritePolicy") or "*(default)*"))
    a("6. [ ] Click **Save**.\n")
    return "\n".join(out)


def _render_jdbcstore_detailed(phase, num, store, needs_pre_existing_dep):
    out = []
    a = out.append
    a("## %d.%d JDBC Store: `%s`\n" % (phase, num, store["name"]))
    a("1. [ ] **Services → Persistent Stores → New → Create JDBCStore**.")
    a("2. [ ] Name: `%s`." % store["name"])
    if store.get("targets") and any("(migratable)" in t for t in store["targets"]):
        a("3. [ ] Target: click the target picker and select the "
          "**migratable target**\n       entry named **`%s`** — not the "
          "plain server entry." % ", ".join(store["targets"]))
    else:
        a("3. [ ] Target: %s." % fmt_targets(store.get("targets")))
    dep_note = " ⚠️ — this must already exist on the target (referenced "\
               "but not exported by this extract; confirm before "\
               "proceeding)." if needs_pre_existing_dep else ""
    a("4. [ ] Data Source: **`%s`**%s" % (store.get("dataSource"), dep_note))
    if store.get("prefixName"):
        a("5. [ ] Click **OK**.")
        a("6. [ ] Open the store you just created → set **Prefix Name**: "
          "`%s`." % store["prefixName"])
        a("7. [ ] Click **Save**.\n")
    else:
        a("5. [ ] Prefix Name: leave blank (none specified for this "
          "store).")
        a("6. [ ] Click **OK**, then **Save** if prompted.\n")
    return "\n".join(out)


def _render_module_detailed(i, mod):
    out = []
    a = out.append
    a("## 5.%d Module: `%s`\n" % (i, mod["name"]))
    a("**Create the module:**")
    a("1. [ ] **Services → Messaging → JMS Modules → New**.")
    a("2. [ ] Name: `%s`. Click **Next**." % mod["name"])
    a("3. [ ] Targets: %s. Click **Next**, then **Finish**.\n"
      % fmt_targets(mod.get("targets")))

    step_counter = [4]

    def next_step():
        s = step_counter[0]
        step_counter[0] += 1
        return s

    for sub in mod.get("subdeployments", []):
        a("**Add subdeployment `%s`:**" % sub["name"])
        a("%d. [ ] Open the module → **Subdeployments** tab → **New**."
          % next_step())
        a("%d. [ ] Subdeployment Name: `%s`. Click **Next**."
          % (next_step(), sub["name"]))
        a("%d. [ ] Targets: %s. Click **Finish**.\n"
          % (next_step(), fmt_targets(sub.get("targets"))))

    def dest_block(items, label, kind, needs_lb):
        for item in items:
            a("**Add %s `%s`:**" % (label, item["name"]))
            a("%d. [ ] Open the module → **New** → select **%s**. Click "
              "**Next**." % (next_step(), kind))
            a("%d. [ ] Name: `%s`. JNDI Name: `%s`. Click **Next**."
              % (next_step(), item["name"], item["jndi"]))
            a("%d. [ ] Subdeployment: `%s`. Click **Finish**."
              % (next_step(), item.get("subdeployment")))
            if needs_lb and item.get("loadBalancingPolicy"):
                a("%d. [ ] Open the new destination → set **Load "
                  "Balancing Policy** to\n       **%s**. Save.\n"
                  % (next_step(), item["loadBalancingPolicy"]))
            else:
                a("")

    dest_block(mod.get("queues", []), "queue", "Queue", False)
    dest_block(mod.get("uniformDistributedQueues", []), "uniform distributed queue", "Distributed Queue → Uniform", True)
    dest_block(mod.get("distributedQueues", []), "distributed queue", "Distributed Queue", True)
    dest_block(mod.get("topics", []), "topic", "Topic", False)
    dest_block(mod.get("uniformDistributedTopics", []), "uniform distributed topic", "Distributed Topic → Uniform", True)
    dest_block(mod.get("distributedTopics", []), "distributed topic", "Distributed Topic", True)

    mod_targets = mod.get("targets")
    inherit_desc = ("inherits %s" % ", ".join("`%s`" % t for t in mod_targets)) if mod_targets else "inherits the module's target"
    for cf in mod.get("connectionFactories", []):
        a("**Add its Connection Factory `%s`%s:**"
          % (cf["name"], " (default targeting -- %s)" % inherit_desc if cf.get("defaultTargetingEnabled") else ""))
        a("%d. [ ] Open the module → **New** → select **Connection "
          "Factory**. Click\n       **Next**." % next_step())
        a("%d. [ ] Name: `%s`. JNDI Name: `%s`. Click **Next**."
          % (next_step(), cf["name"], cf["jndi"]))
        if cf.get("defaultTargetingEnabled"):
            a("%d. [ ] On the Targeting page: leave **Default Targeting "
              "Enabled** checked.\n       Do **not** select a "
              "subdeployment (this CF %s). Click **Finish**.\n" % (next_step(), inherit_desc))
        else:
            a("%d. [ ] On the Targeting page: select subdeployment `%s`. "
              "Click **Finish**.\n" % (next_step(), cf.get("subdeployment")))

    for eh in mod.get("safErrorHandlings", []):
        a("**Add its SAF Error Handling `%s`:**" % eh["name"])
        a("%d. [ ] Open the module → **New** → select **SAF Error "
          "Handling**. Click\n       **Next**." % next_step())
        a("%d. [ ] Name: `%s`." % (next_step(), eh["name"]))
        a("%d. [ ] Policy: **%s**. Click **Finish**.\n" % (next_step(), eh.get("policy")))

    for t in mod.get("templates", []):
        a("**Note — Template `%s`** (create via New → JMS Template if the "
          "target domain doesn't already inherit one): Redelivery Delay "
          "`%s`, Redelivery Limit `%s`, TTL `%s`, Priority `%s`.\n"
          % (t["name"], t.get("redeliveryDelay"), t.get("redeliveryLimit"),
             t.get("timeToLive"), t.get("priority")))

    for q in mod.get("quotas", []):
        a("**Note — Quota `%s`:** Bytes Max `%s`, Messages Max `%s`, "
          "Policy `%s`, Shared: %s.\n"
          % (q["name"], q.get("bytesMaximum"), q.get("messagesMaximum"),
             q.get("policy"), bool_yesno(q.get("shared"))))

    for dk in mod.get("destinationKeys", []):
        a("**Note — Destination Key `%s`:** Property `%s`, Key Type `%s`, "
          "Direction `%s`.\n"
          % (dk["name"], dk.get("property"), dk.get("keyType"), dk.get("direction")))

    for fs in mod.get("foreignServers", []):
        a("**Note — Foreign Server `%s`:** Initial Context Factory `%s`, "
          "Connection URL `%s`, Default Targeting: %s."
          % (fs["name"], fs.get("initialContextFactory"), fs.get("connectionURL"),
             bool_yesno(fs.get("defaultTargetingEnabled"))))
        for fd in fs.get("foreignDestinations", []):
            a("- Foreign Destination `%s`: local JNDI `%s` → remote JNDI "
              "`%s`." % (fd["name"], fd.get("localJNDIName"), fd.get("remoteJNDIName")))
        for fcf in fs.get("foreignConnectionFactories", []):
            a("- Foreign Connection Factory `%s`: local JNDI `%s` → "
              "remote JNDI `%s`." % (fcf["name"], fcf.get("localJNDIName"), fcf.get("remoteJNDIName")))
        a("")

    return "\n".join(out)


def _render_adapter_detailed(i, ad):
    out = []
    a = out.append
    a("## 6.%d Adapter: `%s`\n" % (i, ad["name"]))
    a("1. [ ] **Deployments → Install** (or select the existing `%s` →\n"
      "       **Update**, if one already exists from the domain template "
      "and you\n       are replacing its plan)." % ad["name"])
    a("2. [ ] Browse to the source `.rar`: `%s`. Click **Next**." % ad["sourcePath"])
    a("3. [ ] Choose **Install this deployment as an application** (or, "
      "if\n       updating, proceed with the update flow). Click "
      "**Next**.")
    a("4. [ ] Targets: tick %s. Click **Next**." % fmt_targets(ad.get("targets")))
    a("5. [ ] Deployment Plan path: `%s`. Click **Finish**." % ad["planPath"])
    cis = ad.get("connectionInstances", [])
    a("6. [ ] Open the deployed `%s` → **Configuration → Outbound\n"
      "       Connection Pools**. Review/set host, port, user, password "
      "for %s\n       %s:"
      % (ad["name"],
         "this connection instance" if len(cis) == 1 else "each of these %d connection instances" % len(cis),
         "below" if len(cis) == 1 else "below"))
    for ci in cis:
        a("   - [ ] `%s`" % ci)
    a("7. [ ] Save each change, and click **Update Plan** if the console "
      "prompts\n       you to persist the edit into the plan XML.\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: python3 gen_release_plan.py "
                          "environments/<domain>/<env>/export.json\n")
        sys.exit(1)

    export_path = sys.argv[1]
    if not os.path.isfile(export_path):
        sys.stderr.write("error: %s not found\n" % export_path)
        sys.exit(1)

    data = load_export(export_path)

    # Infer domain/env from the conventional path
    # environments/<domain>/<env>/export.json
    parts = os.path.normpath(export_path).split(os.sep)
    try:
        idx = parts.index("environments")
        domain, env = parts[idx + 1], parts[idx + 2]
    except (ValueError, IndexError):
        domain, env = "<domain>", "<env>"

    out_dir = os.path.dirname(export_path)
    condensed_path = os.path.join(out_dir, "release-plan.md")
    detailed_path = os.path.join(out_dir, "release-plan-detailed.md")

    condensed = render_condensed(data, domain, env)
    detailed = render_detailed(data, domain, env)

    with io.open(condensed_path, "w", encoding="utf-8") as f:
        f.write(condensed)
    with io.open(detailed_path, "w", encoding="utf-8") as f:
        f.write(detailed)

    print("Wrote %s (%d bytes)" % (condensed_path, len(condensed)))
    print("Wrote %s (%d bytes)" % (detailed_path, len(detailed)))


if __name__ == "__main__":
    main()
