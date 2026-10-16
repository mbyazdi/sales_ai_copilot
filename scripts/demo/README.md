# Persistent isolated local Demo

> **V3.0.22 is a source-only Demo infrastructure release. DO NOT deploy this
> build to the original PostgreSQL database (`sales_ai_db`, port 5432).**
> Backup/rollback preparation, migration 0003, reference-lock capability
> installation, existing-grant policy review, an executable readiness gate and
> deployment authorization must be separately approved and validated first.
> Generic Django checks and a source commit/push do not authorize deployment.
> See [B10](../../docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B10_FINAL_PRECOMMIT_AUDIT.md)
> for the exact prerequisite order and commit boundary.

Owner-approved B1 infrastructure plus B2-A insert-only synthetic preparation.
Windows reserves 8800–8899; the approved replacement is **8900**. No Windows
reservation, firewall, global environment or production settings are changed.

## Fresh installation order — B9-A

Fresh setup is an explicit operator workflow, separate from normal startup and
repeat bootstrap. Run only after authorization for a genuinely new dedicated
Demo target. Existing targets are never reset/reused by provisioning. Preload
the pinned PostgreSQL image first; provisioning intentionally uses `--pull never`.

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/provision.py --confirm-create-isolated-demo
& '.\venv\Scripts\python.exe' -B scripts/demo/deploy_lock_capabilities.py preflight
& '.\venv\Scripts\python.exe' -B scripts/demo/deploy_lock_capabilities.py install --approve-reference-locks-v1
# Enter the explicitly approved current Demo day in Asia/Tehran:
$demoDate = 'YYYY-MM-DD'
& '.\venv\Scripts\python.exe' -B scripts/demo/bootstrap.py --date $demoDate --confirm-database sales_ai_demo_db
& '.\scripts\demo\demo.ps1' check
& '.\scripts\demo\demo.ps1' start
```

Prerequisites and durable stages:

1. Provision the independent container/credentials, owner/runtime roles, reviewed
   50-migration schema and exact runtime grants. Publish the protected profile.
2. Explicit provisioning registers the initial generation only against that
   verified, empty database. A matching registration replays without rewriting;
   missing registration on populated data is rejected, never adopted.
3. Explicitly install the unchanged lock capabilities **before fixtures**. The
   preflight requires exact container/endpoint/DB OID/marker/roles/generation,
   source/migration fingerprints, 40 owner-controlled tables, zero non-framework
   rows and no orphaned TEST account/fixture files. No initial registry or SQL is
   installed by normal startup. Existing complete installations recheck read-only.
4. Explicit bootstrap verifies generation/capabilities/grants and today's
   approved date, inserts synthetic fixtures atomically and publishes the
   checksummed `fixtures_committed` manifest. No production data is read/cloned.
5. Bootstrap invokes the one-shot `initialize.py activate` child with runtime
   credentials. It uses Django's normal request middleware, password login,
   DB sessions, CSRF and the existing authorized Start API in-process; it needs
   no partially initialized HTTP server. There is no forced authentication,
   permission bypass, direct Visit status update or alternative Start lifecycle.
   Login, C0005 Start/snapshots and logout share an outer transaction. The child
   then publishes the `complete` manifest. Other four Visits remain PLANNED.
6. Normal startup requires valid generation, capability registry and complete
   fixture readiness. Read-only checks bind the manifest to the versioned source,
   explicit date, approved price/image fingerprints, recorded live PKs/fields and
   Visit/customer ownership. Decimal scale and aware timestamp offsets are
   canonicalized without rounding prices or ignoring changed values. Later
   legitimate Visit/request history remains outside bootstrap authority.

No original Demo-day fixture hash, timestamps, sequence values or database OIDs
are hardcoded as an approval for another installation. New target identities are
verified and recorded locally; fixture hashes derive from the reviewed source
and explicitly selected day. The fixed approved SQL and price dataset hashes
remain enforced. Existing protected manifests continue to validate unchanged.

Same-date/version bootstrap replay verifies existing rows/credentials and returns
NO_OP without activating C0005 again. A different date, foreign/missing records,
changed fixture fields, checksum/identity drift or incomplete manifest stops
without overwriting. This is not a Prepare Day or reset command.

### Interrupted initialization

Database commits and protected-file publication are separate steps, not atomic
promotion. Normal startup always fails closed on missing/incomplete state.

- Schema/profile complete but registry absent: after explicit identity/empty-data
  review, `initialize.py generation --confirm-database sales_ai_demo_db` can create
  only the first empty-generation registration. Existing valid registration is
  a read-only NO_OP; conflicting/invalid registration is never overwritten.
- Partial capability SQL/registry: inspect the installation journal and exact
  dependencies. Do not rerun blindly or grant an unlocked fallback. B7's manual,
  separately approved recovery policy remains in force.
- Fixture transaction/file publication failure: stop and inspect. Populated data
  without a valid manifest and orphaned credential files are not automatically
  adopted, deleted or regenerated.
- `fixtures_committed` with C0005 still PLANNED: diagnose the failure, then invoke
  `initialize.py activate --confirm-database sales_ai_demo_db` explicitly. Failed
  activation rolls back its auth/Visit/snapshot effects; PostgreSQL sequence gaps
  may remain and must not be reset. No automatic mutation retry occurs.
- C0005 already IN_PROGRESS while the manifest is incomplete: uncertain commit;
  stop for evidence review. The activation command refuses another Start and
  never infers/publishes success. Completed Visits are never reopened/redated.

Focused disposable initialization validation:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_initialization_postgres.py
```

This creates/removes two exact UUID-named test databases and independent temporary
owner/runtime/capability roles on the verified Demo cluster. It tests an empty
schema through ready state on two dates (second date is a controlled test clock),
repeat/conflict behavior and missing/mismatched startup inputs. It does not change
the persistent Demo, generation or running listener. Protected results are under
`reports/b9a-*`. B9-B removed historical reconciliation helper dependencies
(B8 #2). Non-Demo deployment remains gated by the B9-C boundary below.

## Daily use

From `D:\py project\sales_ai_copilot` in PowerShell:

```powershell
& '.\scripts\demo\demo.ps1' check
& '.\scripts\demo\demo.ps1' start
& '.\scripts\demo\demo.ps1' status
& '.\scripts\demo\demo.ps1' stop
```

Open **http://localhost:8900/accounts/login/**. Use `localhost`, not
`127.0.0.1`, in the browser. The listener binds only IPv4 loopback.
The persistent salesperson login is **demo-sp001-test** (SP001). Independent
manager and unassigned accounts are **demo-manager-test** and
**demo-unassigned-test**. Passwords are independently generated and stored only
in `D:\SalesAI-Demo\sales_ai_copilot\credentials\test-accounts.json` under
`accounts.salesperson`, `accounts.manager` and `accounts.unauthorized`.
Read that file locally with your editor; never paste passwords into Git/logs.
Use the normal login form. The manager page is `/management/`.

`start` launches a hidden background Django WSGI listener with local static-file
handling. It validates identity and migrations before serving. `stop` contacts
only the matching Demo listener through a protected control token; it never
kills a PID or stops PostgreSQL/other previews. A second `start` refuses an
occupied port; use `status` to inspect an already-running listener.

## Isolation and protected state

- Container: `sales-ai-demo-postgres`, PostgreSQL 17.11, `127.0.0.1:5433`.
- Database: `sales_ai_demo_db`; volume: `sales_ai_demo_pgdata`.
- Compose: `D:\docker\sales-ai-demo\compose.yaml` (secret-free).
- State: `D:\SalesAI-Demo\sales_ai_copilot\profile.json` (secret-free identity,
  endpoint and exact migration fingerprint).
- Credentials: that state's `credentials\` directory: independent
  `owner.json`, `runtime.json`, `bootstrap-password.txt`, `django-secret.key`,
  and `control-token.key`. Never copy these into the repository, command lines,
  screenshots or reports. ACLs allow only the current Windows user and SYSTEM.
- Logs, listener metadata and validation evidence: `run\` and `reports\`
  beneath the protected state directory.

`APP_PORT` in `common.py` fixes the approved port. Provisioning records the same
port in protected configuration; profile validation refuses disagreement. All
URLs, health checks, binding and trusted CSRF origin follow that profile.
Database identity is pinned separately to 5433, the Demo name, role, OID,
owner-controlled marker, container/image ID and labeled persistent volume.
SQLite fallback is prohibited **inside this launcher only**. Ordinary project
settings and development launchers are unchanged.

Normal Django authentication, CSRF middleware and DB-backed sessions remain in
use. The Demo has an independent signing key and `sales_ai_demo_session` cookie;
`csrftoken` is retained for existing application JS. DEBUG is off. This is a
loopback-only development server, not a public deployment.

## Restart and recovery

After Windows/Docker Desktop restart, start Docker Desktop normally, then run
`start`. The existing container uses `unless-stopped`; if it was explicitly
stopped, the launcher can start only its verified existing container. Missing
or replaced container/volume/marker, credentials or migration drift fails
closed. Do not substitute a production profile or rerun provisioning.

For an intentional Demo PostgreSQL restart:

```powershell
& '.\scripts\demo\demo.ps1' stop
& '.\scripts\demo\demo.ps1' restart-database
& '.\scripts\demo\demo.ps1' start
```

No normal command migrates, seeds, resets data, creates users or adjusts Visit
dates. Migration fingerprint changes require a separately authorized maintenance
procedure; there is no startup auto-upgrade. One-time `provision.py` requires
explicit confirmation and completely absent targets. It refuses existing state;
partial failure requires inspection, not an automatic cleanup/retry. Never run
`down -v`, prune, drop or reset as recovery.

## Runtime permissions and focused validation

The owner owns public schema/tables/sequences and applies migrations. Runtime
has no elevated flags, memberships, ownership, DDL or TEMP privilege. It can read
the application, create/update request headers/lines, update Visit lifecycle,
maintain DB sessions, and update only `last_login`/`password` on users. Snapshot,
feedback, receipt, acknowledgement, outcome and admin-log history permit
SELECT/INSERT only. Catalog, prices, inventory and business-history data are not
runtime-maintainable. B2 fixtures need explicit owner-controlled maintenance;
future additional runtime writes require a grant review.

With the Demo listener stopped, focused infrastructure validation is:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/validate.py
```

It checks the B1 empty-data baseline, identity/port/credential failure, occupied
port preservation, grants and denied DDL. Allowed writes are zero-row statements
inside rollback-only savepoints; no fixture or sequence value is generated.
This B1 validator asserts an empty baseline. **Do not rerun it against the
populated B2-A Demo.** Use the fixture validator below for the prepared baseline.

## Explicit synthetic preparation (B2-A)

Already prepared: `SYNTHETIC_DEMO_V1`, explicit date **2026-10-15**, Asia/Tehran.
It uses 14 committed product identities/images, the frozen DEMO_06_V1 prices,
five entirely synthetic customers, independent TEST users, inventory and saved
synthetic priorities. No production business rows/password hashes were cloned.
History/Customer360 starts honestly NEW/zero; no historic sales were fabricated.

The preparation command is separate from all normal startup commands:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/bootstrap.py --date 2026-10-15 --confirm-database sales_ai_demo_db
```

First preparation requires an empty Demo business baseline and today's explicit
Tehran date. All fixtures are inserted in one transaction. C0005 is then started
through the real session/CSRF-protected Start API, which captures its snapshots.
Partial failures stop for inspection, never overwrite or reset existing rows.

Repeat preparation with the same version/date verifies the protected manifest,
identities, exact numeric values and passwords and returns NO_OP. It does not
rehash/reset passwords, reprice, refresh recommendations, restart a Visit or
change timestamps/sequences. Decimal comparison ignores insignificant trailing
zeros only, never rounds. Evolved Visit status/results are deliberately excluded
from bootstrap authority; completed Visits are never redated or reopened.

The protected manifest is `fixtures\manifest.json`, with `manifest.sha256` beside
it. It contains creation identities, fixture data, prices and approved image
references; no password hashes. Account secrets remain in `credentials\`.
Audit evidence and numbered screenshots are in `reports\b2a\`.

Focused validation of the initial prepared baseline:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/validate_fixtures.py
```

It uses normal TEST login/logout and the runtime role. Business Add/completion
probes run in rolled-back transactions; the five initial Visits remain ready.
PostgreSQL identity sequences may have harmless gaps from rolled-back probes;
they are never reset. Do not use the initial-baseline validator after manually
advancing the scenarios and assume it will reset them.

A future Demo day needs separately approved non-destructive Visit preparation.
Normal startup never adjusts dates. Destructive reset/rebuild, broad fixture
maintenance and B2-B are **not implemented or authorized here**.

## Maintenance plans only (B2-B1)

These separate commands use the runtime role with server-enforced read-only,
repeatable-read transactions. They print JSON; there is **no execution or
confirmation flag**, login, migration, reset, restart or credential change.
Normal startup is unchanged.

```powershell
# Default date is calculated in Asia/Tehran, not the UTC or Windows calendar day.
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py prepare-day --dry-run
# Explicit future date, inspect only:
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py prepare-day --dry-run --date 2026-10-16
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py reset --dry-run --date 2026-10-16
# Focused read-only planner tests; no fixture or authentication writes:
& '.\venv\Scripts\python.exe' -B scripts/demo/tests_plans.py
```

Prepare-day proposes only missing PLANNED Visits, with no request/history writes.
Registered same-day open Visits are kept; closed Visits remain closed and signal
that the scenario is already used. Duplicates, unregistered same-day identities,
missing registered rows and inactive/unassigned customers block preparation.
An older IN_PROGRESS Visit remains untouched and blocks conflicting future-day
preparation. The whole plan proposes zero executable inserts until resolved by
an explicit authorized action; preparation never completes it. Assignment dates
do not add a new application eligibility rule.
Future execution would require serialized maintenance, an atomic insert/recheck
and a protected checksummed date-to-Visit ledger. No such executor/ledger is
created by these plans.

Reset proposes a fresh, independently validated candidate database on the
dedicated Demo cluster. It lists current counts and expected candidate counts
for every table. Old-generation deleted-row count is always zero: the current
database, credentials, snapshots, requests, receipts, acknowledgements and browser
profile remain retained. Candidate data would come only from synthetic definitions,
not DB cloning. Cleanup always requires separate later approval.

Current connection guards hardcode the active database, so a candidate **cannot
be activated by today's scripts**. Owner approval and implementation are needed
for an exact generation registry/profile switch, candidate creation/validation,
write fencing, confirmation and recovery. A plan binds the observed state,
identity, migrations, fixture checksums and target date; replan if any change.

Database session counts cannot reveal pending browser commands or in-flight
requests. B2-B2 adds server-authoritative session/document/command proofs below;
fresh browser storage and independent credentials remain additional safeguards,
not the authority. Preserve old pending commands for old-generation status
recovery; never replay them into a candidate. No profiles, cookies or pending
storage are cleared during dry-run.

## Generation safety foundation (B2-B2)

The protected `generation-state.json` binds the existing Demo UUID to the exact
profile/database OID/container/endpoint/migration fingerprint. It is current-state
registration, not a new generation or activation. Missing, changed or maintenance
state fails closed. Normal startup verifies it and never initializes/repairs it
automatically. New-host registration needs separate explicit provisioning.

Only the dedicated Demo runtime installs generation middleware. Normal Django
login/CSRF/session handling stays in place; successful login binds the session to
the active generation. Every unsafe request needs a signed generation proof, and
authenticated requests need a matching session binding. Legacy/unbound sessions
must explicitly log in again; no automatic session flush or database repair.

Demo HTML includes a non-visible transport script/proof. Native POST forms gain
a hidden proof; it is stripped before the application view. Legacy lifecycle
fetches carry the document's proof. Basket/feedback/submission/completion hooks
store proof metadata in the pending **outer envelope**, outside API payload/wire.
Retry/reload keeps the original proof, UUID and body. Old/unsigned pending data
is never upgraded to a fresh page proof. Server rejections are 403 stale session,
409 stale/missing command proof, or 503 uncertain maintenance. CSRF still applies.
Production and other previews do not load the Demo script/middleware; optional
hooks do nothing there. No prices, UI layout or domain API semantics changed.

After this current-generation security reload, refresh the login page and use
the protected TEST credentials normally. If an old command is pending, use its
read-only recovery path; never erase/restamp it to force a retry. Cookie rotation
or a fresh profile alone cannot authorize an old generation's command.

Candidate promotion is a **journalled multi-step operation, not atomic**.
`generation.py` provides only pure journal/registry validators: no executor or
promotion/reset CLI. Required order: PLANNED, CANDIDATE_VALIDATED,
RECOVERY_RECORDED, OLD_APP_QUIESCED, OLD_WRITES_FENCED, PROFILE_SELECTED,
NEW_APP_VALIDATED, COMPLETE. Every interruption remains mutation-blocked until
independent inspection/approval. Keep at least the previous healthy generation;
never clean it up as part of activation. Future evidence must come from actual
independent validation, not the synthetic unit-test journal fixtures.

Read-only/memory-only focused safety validation:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/tests_generation.py
& '.\venv\Scripts\python.exe' -B scripts/demo/tests_plans.py
node --test scripts/demo/generation_client.test.cjs
```

There is still no executable reset, candidate creation/promotion, Prepare Day,
automatic completion/redating, credential rotation or cleanup operation.

### B6/B7 reference-lock capabilities

Current PostgreSQL Feedback/Submit source uses `REFERENCE_LOCKS_V1`, defined in
`apps/core/sql/reference_locks_v1.sql`. There is no unlocked/owner-credential
fallback. B7 installed these capabilities only in the independently isolated
persistent Demo. Production remains unprovisioned; deployment there requires
separate approval. Read business paths do not acquire capability locks.

Run the disposable B3 + B6 real-session security/concurrency selection:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_generation_postgres.py --lock-capabilities
```

The runner verifies the independent Demo cluster, creates a UUID-named test DB,
applies 50 migrations there and installs the two functions in a private schema.
An ephemeral NOLOGIN owner has SELECT on only the referenced identity/link columns
and UPDATE(id) on five reference tables. Runtime gets only schema USAGE and exact
function EXECUTE, keeping direct reference writes denied. Both test DB and owner
role are removed after exact-identity verification. Before/after persistent
inventories and the version/source-SHA receipt are protected under `reports/b2b3-*`.
The disposable installer refuses persistent databases; existing valid installations
are checked read-only, never overwritten. No startup/bootstrap hook installs SQL.

Explicit persistent maintenance (only the approved, verified B7 Demo identity):

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/deploy_lock_capabilities.py preflight
& '.\venv\Scripts\python.exe' -B scripts/demo/deploy_lock_capabilities.py recheck
# First installation only, after separate authorization and quiescence:
& '.\venv\Scripts\python.exe' -B scripts/demo/deploy_lock_capabilities.py install --approve-reference-locks-v1
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_deployed_locks.py
& '.\venv\Scripts\python.exe' -B scripts/demo/demo.py start
```

The installer records recovery evidence before pausing only the verified Demo
listener. Roles/grants/functions commit in one PostgreSQL transaction; publishing
the protected `lock-capabilities.json` and `.sha256` registry and restarting are
separate journalled steps. Uncertain/partial state stops without repair or retry.
Repeat installation is a read-only no-op. Original public grants are preserved.
Manual rollback requires separate approval and dependency checks; exact evidence
and the no-CASCADE/no-data-restore plan are in protected `reports/b7-*`.

Demo preflight and every new runtime Django connection verify the registry,
source/version, pinned object OIDs, bodies, signatures, owner and permissions.
Missing/incompatible capabilities block startup or the connection before business
SQL. This guard is confined to the dedicated Demo profile. No production/default
settings change. `verify_deployed_locks.py` uses explicit transaction-local PKs and
forced rollback; it never calls nextval/setval or persists scenario changes.

For only the existing Feedback/Submit API SQLite regressions, guarded memory-only:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_reference_locks_sqlite.py
```

No Django migration was added. Future PostgreSQL deployment must separately
approve/version the SQL, owner and grants, verify capability bodies/ACLs alongside
Django migration state, and validate before admitting mutations. Django's existing
50-migration graph does not alone prove these extra SQL capabilities are installed.

## Repository-owned preservation evidence — B9-B

All required reconciliation code is now in `preservation.py` and the committed
`apps/core/reconciliation.py`. No command imports provisioning code from ignored
artifacts or reads a historical `preserved-files.json`. Installed Python packages
remain ordinary prerequisites; private reports are not executable dependencies.

There are two explicit evidence scopes:

- **Capability installation:** `installation_preservation` verifies the exact
  endpoint/container/OID/marker, schema ownership and registered active generation.
  EMPTY requires all non-framework tables empty and no orphan fixture/account
  files. PREPARED requires the current fixture manifest, approved source/date,
  recorded PKs/owned values and live relationships to agree. Both capture all
  public table digests and full operator-visible sequence state. Neither requires
  a production installation, its credentials or any previous report. Existing
  ACL/body/security checks still independently validate the permitted SQL changes.
- **Cross-environment validation:** the integration runners also preserve current
  Demo data, production canonical UTC table/metadata checksums, original SQLite,
  configured credentials, existing preview credential files, HEAD, stash and index.
  Production access is SELECT-only through `sales_ai_runtime`, using the protected
  `D:\docker\sales-ai-postgres\runtime-credentials\sales_ai_runtime.env` file.
  This extra cross-environment audit fails if that locally configured credential
  is unavailable; it is not required by fresh Demo provisioning. Runtime-visible
  production sequence NULLs explicitly mean restricted visibility, not verified
  operator sequence values. No new production privileges are granted.

Before-state records are exclusively created and HMAC-signed with the protected
Demo control key. They bind an operation UUID/purpose, exact installation and
generation, migration/SQL/tooling fingerprints and required file hashes. Keep
them under the protected external `reports/` directory. A file present at capture
becomes required on verification; deletion is not silently skipped. TEST fixture
and capability registries remain separate initialization authority.

For an explicitly NEW read-only audit (choose an unused protected file path):

```powershell
$evidence = 'D:\SalesAI-Demo\sales_ai_copilot\reports\NEW-OPERATION-before.json'
& '.\venv\Scripts\python.exe' -B scripts/demo/preservation.py capture --baseline $evidence --purpose owner-review
# Retain the exact operation UUID printed by capture:
& '.\venv\Scripts\python.exe' -B scripts/demo/preservation.py verify --baseline $evidence --purpose owner-review --operation '<recorded UUID>'
```

Missing, invalid, tampered, foreign or source-mismatched before-state evidence
always stops. Never recapture over an uncertain operation to declare it preserved.
Inspect its original journal, DB/container/generation and trusted evidence; seek
independent approval for recovery. If original evidence cannot be recovered,
historical preservation is unproven. A separately approved NEW operation may
capture current state, but cannot attest to earlier work. Ordinary startup does
not capture, repair or install anything.

Focused clean-source validation:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/tests_preservation.py
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_initialization_postgres.py --clean-source
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_generation_postgres.py --lock-capabilities
```

The first integration command copies reviewed source and tracked static assets
into protected temporary checkouts, excluding Git state, source SQLite, local
credentials, venv and private reports. Workers validate source checksums and exact
independent disposable DB/OID/marker/roles before writes. It exercises first
installation, repeat/conflict initialization, populated-install read-only checks
and missing/tampered/mismatched evidence. The second runner also uses fresh
independent owner/runtime roles, retains B3/B6/B7 assertions and removes its
disposable DB and roles. Neither runner modifies the persistent generation/data.

B8 blocker #2 is resolved. Blocker #3 (production capability deployment/rollout)
remains outside this work; no production capability installation is authorized.

## PostgreSQL deployment boundary — B9-C

The shared Feedback and Submit services require `REFERENCE_LOCKS_V1` on **every
PostgreSQL target using this source**, not just Demo. There is no missing-function
fallback, role-based bypass or compatibility feature flag. A successful ordinary
`manage.py check`, login, GET or migration run does not prove mutation readiness.

| Environment | Current readiness |
| --- | --- |
| Dedicated Demo, 5433 | All 50 migrations and verified V1 registry/functions/ACLs; use `demo.ps1 check` before serving. New runtime connections also validate capabilities. |
| Original `sales_ai_db`, 5432 | **NO-GO for this new mutation source:** 49 migrations, pending `0003_complete_visit_receipt`, no capability schema/functions. Ordinary startup has no capability gate. |
| Disposable PostgreSQL | Apply the full schema and explicitly install approved capabilities with independent roles in the identity-guarded test harness. Django migrations alone do not install them. |
| Isolated SQLite development/test | Existing SQLite transaction/CAS behavior remains; functions are PostgreSQL-only. This does not provide PostgreSQL-equivalent row locking or make the preserved original SQLite schema current. |

New REJECTED/LATER feedback calls the Recommendation → Product capability after
operational Visit/Request locking. New Submit calls the Customer → Grade → sorted
Products → Inventory capability after Visit/Request/Line locking. Existing saved
replay may return before reference locking after authorization; that is not proof
an installation can accept new commands. Catalog/quote/review/history reads and
basket/Visit operations do not directly call these capabilities. Their own schema,
authorization, revision and lifecycle requirements still apply.

**Recommended deployment contract (Option A, pending owner approval):** prepare
and validate each PostgreSQL target explicitly before admitting this source to
its mutation traffic. Require the complete approved migration graph, exact
versioned SQL bodies/signatures, dedicated NOLOGIN owner, fixed search_path,
bounded arguments, PUBLIC denial, explicit runtime EXECUTE, verified reference
privileges, pinned target/registry identities, recovery evidence and independent
least-privilege concurrency tests. Keep SQL installation out of ordinary startup.
Startup/readiness integration for the original profile is not implemented here.

The original runtime currently already has UPDATE on the five reference tables;
Demo does not. Those grants were **not** changed. The Demo inspector/installer
pins Demo identities and its stricter ACL contract: never retarget it by changing
constants or copying a Demo registry. Original deployment needs an approved
target-specific role/registry policy, including an explicit decision to harden
existing grants or document their compatibility implications. No new broad
runtime reference UPDATE grant is proposed.

An original-only legacy-locking branch (Option B) would change shared service
selection and requires separate architecture approval and equivalent concurrency
tests. It is not implemented. Holding the new source to the validated Demo/test
targets (Option C) is the temporary containment boundary; any original runtime
must use an independently verified compatible build/schema. No original process
was stopped, repinned or reconfigured by this task.

Missing capabilities currently raise PostgreSQL errors and roll back fresh
Feedback/Submit commands; ordinary API handlers do not translate these into a
special readiness response. Do not discover deployment readiness through a live
POST. Do not treat generic Django check success or the older 351-test gate as
validation of this later SQL dependency.

Rollback must pair a verified application build with its schema/capability
contract. Quiesce affected processes before changing dependencies, preserve
business history and generations, and inspect journals after uncertainty. Never
drop functions while dependent code is serving or use CASCADE, unlocked reads,
automatic grants, schema repair or data restoration as a compatibility fallback.
Original migration/capability installation, grant policy and executable admission
gate remain separately approved work. B8 blocker #3 is not claimed resolved.

See `docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B9C_POSTGRESQL_DEPLOYMENT_BOUNDARY.md`
for the execution-path inventory, options, focused evidence and owner decisions.
