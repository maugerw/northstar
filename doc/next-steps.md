# Next Steps — Loader & Extract

_Status note as of 2026-07-15. Update as items are done._

## Where things stand

- **Extract** (`extract/`): working and trusted. Booleans fixed (`to_boolean`
  now handles the Jython-2.2 primitive-boolean-as-int case), CF targeting
  understood (three CFs are default-targeted, not dangling — confirmed via
  `diag_cf_targeting.py`), `validate_references` now also checks connection
  factory subdeployment references. Latest export in `extract/out/` is clean
  (`validationWarnings: []`).
- **Release plan** (`extract/out/release-plan.md`): fleshed out into an
  executable, step-by-step console release document (procedures + data tables,
  dependency-ordered phases, verification + rollback). Backup path if the
  loader isn't used.
- **Loader** (`load/`): skeleton complete and dry-run ready. Phased
  (infra → JMS modules → SAF → adapters), idempotent (existence checks before
  create), per-phase edit/activate sessions, env-mapping properties
  (target remap, JDBC passwords, adapter paths), Jython-2.2-safe JSON reader.
  **Not yet run against a live domain.**

## Possible next steps (pick per priority)

### 1. Loader `except:` sweep — DO BEFORE ANY REAL RUN
The loader modules guard WLST calls (`create`, `assign`, `cmo` setters, `cd`)
with `except Exception:`. Under Jython 2.2, WLST can raise Java throwables
that do **not** subclass Python `Exception`, so a genuine WLST failure could
slip past these guards and abort a phase instead of logging a warning — or
worse, be silently swallowed elsewhere. This exact issue was seen in the
diagnostic (`getTargets`/`cd` throwing past `except Exception`).

**Action:** sweep `load/*.py` and change the WLST-guarding `except Exception:`
clauses to bare `except:`. Prefer bare `except:` only around genuine WLST
interpreter calls; keep specific handling where it matters. Re-verify each
phase's try/finally still cancels the edit session on failure.

### 2. Dry run against the source domain
`dry.run=true` never opens an edit session — it connects read-only and logs
what it *would* create. Against the source domain everything already exists,
so every object logs "skipping", but this exercises:
- properties parsing + env build
- JSON read of the real export (Jython 2.2 path)
- the full traverse/sequence with no attribute errors
- MBean existence-check paths (`getMBean(...)`)

**Action:** copy `load/load_objects.properties.template` →
`load_objects.properties`, fill in admin connection + `input.file`, set
`dry.run=true`, run:
`$MW_HOME/oracle_common/common/bin/wlst.sh load_objects.py`.
Best done *after* step 1 so throwables surface as warnings, not aborts.

### 3. CPython mock harness
For validating loader logic **without** any WebLogic. Write a plain-Python
runner that mocks the WLST builtins (`edit`, `startEdit`, `activate`,
`cancelEdit`, `create`, `assign`, `getMBean`, `cd`, `cmo`, `deploy`) and
records the call log against the real `export.json`. Won't catch MBean-path
errors, but catches parsing, sequencing, dependency-order and dry-run logic
bugs on any machine.

**Action:** `load/test/mock_wlst.py` (globals injector) + a runner that imports
the phase modules and asserts/records the create/assign/set call sequence.

### 4. Shadow deploy (live run with renamed objects)
After a successful dry run, do a live run against the domain but with all
object names suffixed (e.g. `MyQueue` → `MyQueue1`).  The renamed objects
won't exist yet, so every existence check misses and the full
create/assign/configure path executes for real — exercising the WLST code
that dry-run never touches — without disturbing the production objects.
The redundant `*1` objects can be deleted from the console afterward.

The cleanest implementation is a **thin pre-processing script** (separate from
the loader) that reads `export.json` and writes `export-shadow.json` with
a configurable suffix applied to every `name` field.  No loader code changes
required; the input file is what's renamed.  Feed `export-shadow.json` to the
loader via `input.file` in the properties file.

Things to be careful about:
- Object **references** (e.g. a JMS server's `persistentStore` pointing to a
  file store by name, or a destination's `subdeployment` field) must be
  suffixed consistently — the transform must rename both the definition and
  every reference to it, otherwise Phase 2+ will log "references missing X"
  warnings.
- `targets` (server/cluster names) should NOT be suffixed — those are real
  domain objects you're assigning to, not objects being created.
- JDBC passwords in the properties file still key off the data source name;
  update the keys to match the suffixed names.

**Action:** write `load/shadow_transform.py` — a plain CPython/Jython script
that accepts `export.json` + a suffix string and writes `export-shadow.json`
with all created-object names (and their intra-JSON references) renamed.
Verify by diffing the two files before running the loader against it.

## Recommended order

1 (except sweep) → 2 (dry run) gives the fastest real-world confidence, since a
clean environment to load into isn't available. 3 (mock harness) is the
portable safety net and is worth having regardless, but is lower priority than
getting a dry run through against the actual domain.
4 (shadow deploy) is the highest-confidence pre-production test available
short of loading into a separate dev domain; worth doing before any real
migration run.

## Also noted

- `to_boolean` fix corrected two things that *mattered*: CF default targeting
  and **all four SAF agents have logging ENABLED** (release plan was updated).
  Worth a diff-scan of any future extract for other flipped booleans.
- `diag_cf_targeting.py` retained in `extract/` for the record — read-only,
  reusable if another targeting anomaly appears.
