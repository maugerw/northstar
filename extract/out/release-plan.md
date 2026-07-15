# Manual Release Plan — SOA Suite Domain JMS/Infrastructure
Generated from: `export.json`

This document provides step-by-step console instructions for manually recreating
the JMS infrastructure on a target WebLogic/SOA Suite domain. Follow the phases
in order — later phases depend on objects created in earlier ones.

**Items requiring manual input are marked ⚠️.**

---

## Notes Before Starting

- All console navigation assumes: **Domain Structure → Services → ...**
- After each object is created, use **Activate Changes** before proceeding to
  the next phase.
- Passwords are not exported and must be supplied from a separate source. ⚠️
- `JMS_DB_Store` references `SOALocalTxDataSource`, which is a SOA system data
  source and should already exist on the target domain. If it does not, create
  it first via the RCU schema or domain template.
- Several connection factories reference subdeployments
  (`MNSAFConnectionFactory`, `MNSOARemoteCF`, `WAMJMSConnectionFactory`) that
  were not captured in the extract — see the note in each module below.

---

## Phase 1 — JDBC Data Sources

**Console path:** Services → Data Sources → New → Generic Data Source / XA Data Source

> Create all data sources before persistent stores (JDBC stores reference them).

---

### 1.1 CommonAuditLog

| Field | Value |
|---|---|
| Name | `CommonAuditLog` |
| JNDI Name | `jdbc/CommonAuditLog` |
| Driver | `oracle.jdbc.xa.client.OracleXADataSource` |
| Transaction Protocol | `TwoPhaseCommit` |
| URL | `jdbc:oracle:thin:@porud455:1526:CBRMDEV` |
| DB User | `MAXIMO` |
| Password | ⚠️ supply separately |
| Test Table | `SQL ISVALID` |
| Test on Reserve | No |
| Initial Capacity | 1 |
| Max Capacity | 15 |
| Min Capacity | 1 |
| Targets | _(none — untargeted)_ |

---

### 1.2 FaultDataSource

| Field | Value |
|---|---|
| Name | `FaultDataSource` |
| JNDI Name | `jdbc/FaultIntegration_XA` |
| Driver | `weblogic.jdbc.sqlserver.SQLServerDriver` |
| Transaction Protocol | `TwoPhaseCommit` |
| URL | `jdbc:weblogic:sqlserver://AZUWDEV000536:1433;allowPortWithNamedInstance=true` |
| DB User | `oms_fault` |
| Password | ⚠️ supply separately |
| Test Table | `SQL SELECT 1` |
| Test on Reserve | No |
| Initial Capacity | 1 |
| Max Capacity | 15 |
| Min Capacity | 1 |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

**Driver Properties:**

| Name | Value |
|---|---|
| `allowPortWithNamedInstance` | `true` |
| `databaseName` | `Faults_DEV` |
| `portNumber` | `1433` |
| `serverName` | `AZUWDEV000536` |
| `user` | `oms_fault` |

---

### 1.3 SIMSOMSIntegration_XA

| Field | Value |
|---|---|
| Name | `SIMSOMSIntegration_XA` |
| JNDI Name | `jdbc/SIMSOMSIntegration_XA` |
| Driver | `oracle.jdbc.xa.client.OracleXADataSource` |
| Transaction Protocol | `TwoPhaseCommit` |
| URL | `jdbc:oracle:thin:@havud301:1526:SIMSDEV` |
| DB User | `sims2` |
| Password | ⚠️ supply separately |
| Test Table | `SQL ISVALID` |
| Test on Reserve | No |
| Initial Capacity | 1 |
| Max Capacity | 15 |
| Min Capacity | 1 |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

---

### 1.4 WAM2JMSLocalDataSource

| Field | Value |
|---|---|
| Name | `WAM2JMSLocalDataSource` |
| JNDI Name | `jdbc/WAM2JMSLocalDataSource` |
| Driver | `oracle.jdbc.OracleDriver` _(non-XA)_ |
| Transaction Protocol | `None` |
| URL | `jdbc:oracle:thin:@//havut049:1526/DBMRDV01` |
| DB User | `GIS_XREF` |
| Password | ⚠️ supply separately |
| Test Table | `SQL ISVALID` |
| Test on Reserve | No |
| Initial Capacity | 1 |
| Max Capacity | 15 |
| Min Capacity | 1 |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

---

### 1.5 WAM_XXCUST_XA

| Field | Value |
|---|---|
| Name | `WAM_XXCUST_XA` |
| JNDI Name | `jdbc/WAM_XXCUST_XA` |
| Driver | `oracle.jdbc.xa.client.OracleXADataSource` |
| Transaction Protocol | `OnePhaseCommit` |
| URL | `jdbc:oracle:thin:@havut049:1526:DBMRDV01` |
| DB User | `WAM_XXCUST` |
| Password | ⚠️ supply separately |
| Test Table | `SQL ISVALID` |
| Test on Reserve | No |
| Initial Capacity | 1 |
| Max Capacity | 3 |
| Min Capacity | 1 |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

---

### 1.6 XrefDataSource

| Field | Value |
|---|---|
| Name | `XrefDataSource` |
| JNDI Name | `jdbc/xref` |
| Driver | `oracle.jdbc.xa.client.OracleXADataSource` |
| Transaction Protocol | `TwoPhaseCommit` |
| URL | `jdbc:oracle:thin:@//havut049:1526/DBMRDV01` |
| DB User | `GIS_XREF` |
| Password | ⚠️ supply separately |
| Test Table | `SQL ISVALID` |
| Test on Reserve | No |
| Initial Capacity | 5 |
| Max Capacity | 150 |
| Min Capacity | 1 |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

---

## Phase 2 — Persistent Stores

**Console path:** Services → Persistent Stores → New → File Store / JDBC Store

> Create file stores first; JDBC stores reference data sources from Phase 1.

---

### 2.1 File Stores

| Name | Directory | Sync Policy | Target |
|---|---|---|---|
| `GIS_OSB_FileStore` | `GIS_OSB_FileStore` | `Direct-Write` | `osb_server1` |
| `GIS_SOA_FileStore` | _(default)_ | `Direct-Write` | `soa_server1` |
| `MNFileStore` | _(default)_ | `Direct-Write` | `osb_server1` |
| `MNSOARemoteFileStore` | _(default)_ | `Direct-Write` | `soa_server1` |
| `WAM2_JMS_FILE_STORE` | _(default)_ | `Direct-Write` | `osb_server1` |
| `WAMFileStore` | _(default)_ | `Direct-Write` | `osb_server1` |

> **GIS_OSB_FileStore**: directory is set to the relative path `GIS_OSB_FileStore`
> (will be created under the server's data directory). All others use the default.

---

### 2.2 JDBC Stores

| Name | Data Source | Prefix | Target |
|---|---|---|---|
| `JMS_DB_Store` | `SOALocalTxDataSource` _(system DS — must pre-exist)_ | _(none)_ | `AdminServer` |
| `WAM2JDBCStore_MS1` | `WAM2JMSLocalDataSource` | `WAM2Store_MS1` | `osb_server1 (migratable)` |
| `WAM2JDBCStore_MS2` | `WAM2JMSLocalDataSource` | `WAM2Store_MS2` | `soa_server1 (migratable)` |

> **WAM2JDBCStore_MS1/MS2** target migratable targets. These auto-exist on
> clustered servers; select them from the target picker.

---

## Phase 3 — JMS Servers

**Console path:** Services → Messaging → JMS Servers → New

| Name | Persistent Store | Bytes Max | Messages Max | Target |
|---|---|---|---|---|
| `GIS_OSB_JMS_Server` | `GIS_OSB_FileStore` | Unlimited | Unlimited | `osb_server1` |
| `GIS_SOA_JMS_Server` | `GIS_SOA_FileStore` | Unlimited | Unlimited | `soa_server1` |
| `MNSOARemoteJMSServer` | `MNSOARemoteFileStore` | Unlimited | Unlimited | `soa_server1` |
| `WAMJMSServer` | `WAMFileStore` | Unlimited | Unlimited | `osb_server1` |

---

## Phase 4 — SAF Agents

**Console path:** Services → Messaging → SAF Agents → New

| Name | Service Type | Store | Retry Base (ms) | Retry Max (ms) | Window | Target |
|---|---|---|---|---|---|---|
| `GIS_PublishChangeSet_SAF` | `Both` | `GIS_OSB_FileStore` | 20000 | 180000 | 10 | _(none)_ |
| `GIS_SAF_Agent` | `Sending-only` | `GIS_OSB_FileStore` | 20000 | 180000 | 10 | `osb_server1` |
| `GIS_SAF_SOA_Agent` | `Sending-only` | `GIS_SOA_FileStore` | 20000 | 180000 | 10 | `soa_server1` |
| `MNSAFAgent` | `Sending-only` | `MNFileStore` | 20000 | 180000 | 10 | _(none)_ |

All agents: Retry Multiplier = 1, Acknowledge Interval = -1 (default), Time To Live = 0 (unlimited), Logging = disabled.

---

## Phase 5 — JMS Modules

**Console path:** Services → Messaging → JMS Modules → New

For each module: create the module, target it, then add subdeployments before adding destinations.

---

### 5.1 GIS_OSB_JMS_Module

**Module target:** `osb_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `GIS_OSB_JMS_Subdeployment` | `GIS_OSB_JMS_Server` |

**Queues:**

| Name | JNDI | Subdeployment |
|---|---|---|
| `GIS_FileNotificationJMSQueue` | `jms/GIS_FileNotificationJMSQueue` | `GIS_OSB_JMS_Subdeployment` |
| `TempQueue` | `jms/TempQueue` | `GIS_OSB_JMS_Subdeployment` |

---

### 5.2 GIS_SAF_JMS_Module

**Module target:** `osb_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `GIS_SAF_JMS_Subdeployment` | `osb_cluster` |

**SAF Error Handlings:**

| Name | Policy | Error Destination |
|---|---|---|
| `GIS_ErrorHandlerSAF_SOA` | `Discard` | _(none)_ |

---

### 5.3 GIS_SAF_SOA_JMS_Module

**Module target:** `soa_server1`

**Subdeployments:**

| Name | Target |
|---|---|
| `GIS_SAF_SOA_Subdeployment` | `GIS_SAF_SOA_Agent` _(SAF Agent)_ |

_(No queues, topics, or connection factories.)_

---

### 5.4 GIS_SOA_JMS_Module

**Module target:** `soa_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `GIS_SOA_JMS_Subdeployment` | `GIS_SOA_JMS_Server` |

**Queues:**

| Name | JNDI | Subdeployment |
|---|---|---|
| `GIS_PublishChangeSetJMSQueue_SOA` | `jms/GIS_PublishChangeSetJMSQueue_SOA` | `GIS_SOA_JMS_Subdeployment` |
| `GIS_UpdateJobStatusJMSQueue_SOA` | `jms/GIS_UpdateJobStatusJMSQueue_SOA` | `GIS_SOA_JMS_Subdeployment` |

---

### 5.5 MNSAFJMSModule

**Module target:** `osb_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `MNSAFSubDeployment` | `MNSAFAgent` _(SAF Agent)_ |

**Connection Factories:**

| Name | JNDI | Targeting |
|---|---|---|
| `MNSAFConnectionFactory` | `jms/MNSAFConnectionFactory` | **Default targeting** (inherits module target `osb_cluster`) |

> Confirmed via diagnostic: `DefaultTargetingEnabled=true`. Tick "Default
> Targeting" on the CF — do NOT create a subdeployment for it. (The extract's
> stored `SubDeploymentName` of the CF's own name is WebLogic's inert
> placeholder and is ignored when default targeting is on.)

**SAF Error Handlings:**

| Name | Policy |
|---|---|
| `MNSAFErrorHandling` | `Log` |

---

### 5.6 MNSOARemoteJMSModule

**Module target:** `soa_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `MNSOARemoteSubDeploymentJmsModule` | `MNSOARemoteJMSServer` |

**Uniform Distributed Queues:**

| Name | JNDI | Load Balancing | Subdeployment |
|---|---|---|---|
| `MNSOARemoteQueue` | `jms/MNSOARemoteQueue` | `Round-Robin` | `MNSOARemoteSubDeploymentJmsModule` |

**Connection Factories:**

| Name | JNDI | Targeting |
|---|---|---|
| `MNSOARemoteCF` | `jms/MNSOARemoteCF` | **Default targeting** (inherits module target `soa_cluster`) |

> Confirmed via diagnostic: `DefaultTargetingEnabled=true`. Tick "Default
> Targeting"; do NOT create a subdeployment.

---

### 5.7 WAMJMSModule

**Module target:** `osb_cluster`

**Subdeployments:**

| Name | Target |
|---|---|
| `WAM_JMS_Subdeployment` | `WAMJMSServer` |

**Connection Factories:**

| Name | JNDI | Targeting |
|---|---|---|
| `WAMJMSConnectionFactory` | `jms/WAM_JMS_CF` | **Default targeting** (inherits module target `osb_cluster`) |

> Confirmed via diagnostic: `DefaultTargetingEnabled=true`. Tick "Default
> Targeting"; do NOT create a subdeployment.

**Queues:**

| Name | JNDI | Subdeployment |
|---|---|---|
| `WAM_CBRM_JMS_Q` | `jms/WAM_CBRM_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_Chime_JMS_Q` | `jms/WAM_Chime_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_EH_JMS_Q` | `jms/WAM_EH_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_HICI_JMS_Q` | `jms/WAM_HICI_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_IPS_JMS_Q` | `jms/WAM_IPS_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_MX_JMS_Q` | `jms/WAM_MX_JMS_Q` | `WAM_JMS_Subdeployment` |
| `WAM_SerialNum_JMS_Q` | `jms/WAM_SerialNum_JMS_Q` | `WAM_JMS_Subdeployment` |

---

## Phase 6 — Adapter Deployments

**Console path:** Deployments → Install (or Redeploy if already present)

These adapters have custom deployment plans containing connection instance
configuration. Redeploy each with its plan from the source domain, then
verify/update connection instance details (host, credentials) for the target
environment.

> ⚠️ Connection instance credentials (passwords, host names) are stored inside
> the plan files and were not exported. These **must be reviewed and updated**
> for the target environment after redeployment.

---

### 6.1 DbAdapter

| Field | Value |
|---|---|
| Source | `/gmxdevfu/products/middleware/soa/soa/connectors/DbAdapter.rar` |
| Plan | `/gmxdevfu/products/middleware/soa/soa/XrefPlan.xml` |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

**Connection instances in plan:**

| JNDI Name |
|---|
| `eis/DB/SIMSOMSIntegration_XA` |
| `eis/DB/WAM_XXCUST` |
| `eis/DB/WAM_XXCUST_XA` |
| `eis/DB/XREF` |

---

### 6.2 JmsAdapter

| Field | Value |
|---|---|
| Source | `/gmxdevfu/products/middleware/soa/soa/connectors/JmsAdapter.rar` |
| Plan | `/gmxdevfu/products/middleware/soa/soa/Plan.xml` |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

**Connection instances in plan:**

| JNDI Name | Notes |
|---|---|
| `eis/jms/MNSAFConnectionFactory` | maps to CF in MNSAFJMSModule |
| `eis/jms/MNSOARemoteCF` | maps to CF in MNSOARemoteJMSModule |
| `eis/jms/WAM_Chime_JMS_Q` | maps to queue in WAMJMSModule |
| `eis/jms/WAM_EH_JMS_Q` | maps to queue in WAMJMSModule |

> JMS modules (Phase 5) must exist before JmsAdapter connection instances are valid.

---

### 6.3 AqAdapter

| Field | Value |
|---|---|
| Source | `/gmxdevfu/products/middleware/soa/soa/connectors/AqAdapter.rar` |
| Plan | `/gmxdevfu/products/middleware/soa/soa/AQPlan.xml` |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

**Connection instances in plan:**

| JNDI Name |
|---|
| `eis/AQ/CommonAuditLog` |

---

### 6.4 FtpAdapter

| Field | Value |
|---|---|
| Source | `/gmxdevfu/products/middleware/soa/soa/connectors/FtpAdapter.rar` |
| Plan | `/gmxdevfu/products/middleware/soa/soa/EO_Plan.xml` |
| Targets | `AdminServer`, `osb_cluster`, `soa_cluster` |

**Connection instances in plan:**

| JNDI Name |
|---|
| `eis/Ftp/EO_FtpAdapter` |

---

## Open Items / Known Gaps

| Item | Detail |
|---|---|
| JDBC passwords | All 6 data sources — supply from vault/source team |
| ~~CF subdeployments~~ | RESOLVED — `MNSAFConnectionFactory`, `MNSOARemoteCF`, `WAMJMSConnectionFactory` are default-targeted (confirmed via diagnostic), not dangling. Use default targeting, no subdeployment. |
| `JMS_DB_Store` data source | References `SOALocalTxDataSource` (system DS) — must pre-exist on target |
| Adapter connection instance credentials | FTP host/user/password (`EO_FtpAdapter`), DB credentials inside XrefPlan/AQPlan, JMS credentials inside Plan.xml |
| SAF agents with no targets | `GIS_PublishChangeSet_SAF` and `MNSAFAgent` have empty target lists — verify this is intentional on source |
