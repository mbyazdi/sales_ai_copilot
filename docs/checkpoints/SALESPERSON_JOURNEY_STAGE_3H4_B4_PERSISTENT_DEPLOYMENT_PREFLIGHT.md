# Stage 3H4-B4 — Persistent Demo deployment preflight

2026-10-16. READ-ONLY persistent audit; **NO-GO for deployment**.
`fast-track`, HEAD and freshly fetched `origin/fast-track`:
`8bdb2ca6150a27d217eade7bfce8dff3768a4694` (V3.0.22).
Approved uncommitted H4-B1/B2/B3 source was inspected and left unchanged.
Only this checkpoint and ignored/local audit artifacts were created.
No service stop/restart, persistent write/DDL/grant, Prepare Day or recovery ran.

## A. Verified environment and writer inventory

| Identity | Verified value |
| --- | --- |
| Container | `sales-ai-demo-postgres`, ID `69e311c315218d237f06f2d5b04395d63c30c24c0285ff18d6dbeeb7d66ab41c` |
| Image / volume | `sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3` / `sales_ai_demo_pgdata` |
| Database | `sales_ai_demo_db`, OID **16384**, UTF-8, exact owner-controlled marker |
| Endpoint / application | `127.0.0.1:5433` → container 5432 / `http://localhost:8900` |
| Generation | `6ae05c63-b9a3-4e85-a469-4643d3f76a27`, registry ACTIVE, maintenance null |
| Migrations | 50/50, graph SHA256 `f702fb67f632ac62b25555913ae95c88c23db64fee454c2dbe33c3931ed4992f` |
| Fixture | SYNTHETIC_DEMO_V1, complete, 101 owned records, preparation date 2026-10-15; definition SHA256 `c93994113eb2ac22275d91a21aff624d648376f2ed57cf714c4cc27e772730ef` |
| Reference locks | REFERENCE_LOCKS_V1, inspected live bodies/ownership/ACLs match protected registry; SQL SHA256 `7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1` |
| Control schema | `sales_ai_demo_control` ABSENT; no V2 or day journal deployed |
| Listener | PID 37632, Python redirector parent 16592, `scripts/demo/demo.py`; old health has no V2 worker signature |

Visits remain dated **2026-10-15**: C0003/1 PLANNED, C0005/2 IN_PROGRESS,
C0013/3 PLANNED, C0014/4 PLANNED, C0029/5 PLANNED. No SalesRequests.
C0005 therefore still blocks a later five-customer Prepare Day under Policy A.
Deployment must not resolve it, redate anything or prepare today automatically.

Observed Windows inventory: 28 project Python processes, 21 listening project
processes, including Demo plus 20 older previews. Captured process creation times
and ancestry are corroboration, not a quiescence certificate. Port 8770 changed
its serving child during the audit, illustrating why one PID snapshot is unsafe.

| Listener | PID at final inventory | Source/path classification |
| --- | --- | --- |
| 8900 | 37632 (parent 16592) | Dedicated Demo, old ungated worker |
| 8770 | 25236 | Old temporary isolated preview; other redirector/child processes also present |
| 8772 / 8774 / 8782 | 38256 / 28184 / 36688 | Older temporary preview scripts |
| 8783 / 8784 / 8785 | 36564 / 3492 / 11456 | DB preview / local-runtime launcher / logout-validation listener |
| 8786 / 8787 / 8789 | 13816 / 30396 / 5796 | DEMO-04 / quote / feedback previews |
| 8790 / 8791 / 8792 | 35964 / 37556 / 25584 | Basket / UI-04 / ordinary-basket previews |
| 8793 / 8794 | 32472 / 45344 | Review / Result previews |
| 8795 / 8796 | 38140 / 37808 | Polished Review / Result previews |
| 8797 / 8798 / 8799 | 39020 / 25020 / 45704 | Completion / E2E / finish-navigation previews |

These processes were NOT stopped, authenticated against, or certified as unable
to reconnect to Demo. Files on disk and listener names cannot prove their loaded
configuration. Other Python/LSP and a separate project's Django processes were
also observed; no separate named gunicorn/uwsgi/waitress/uvicorn worker was found.

- 209 scheduled tasks inspected: no action name/argument matching this project,
  5433 or 8900. Three shell-like built-in tasks were observed with no project
  hint. No matching Python/Django service or NSSM/WinSW application wrapper was
  identified. This is an observed configuration inventory, not proof that an
  arbitrary wrapper, future task or interactive console cannot start a writer.
- DBeaver PID 28392 is running. Ubuntu-24.04 and docker-desktop WSL distributions
  are running. Guest processes/cron and arbitrary interactive shell state are
  **not exhaustively attested**. Both PostgreSQL containers are running on their
  separate 5432/5433 endpoints; neither was restarted.
- Demo `pg_stat_activity` snapshot contained only this audit's maintenance client
  plus PostgreSQL background workers; zero prepared transactions. Django uses
  short-lived connections: zero idle clients does not exclude future reconnects.
- Three LOGIN roles have CONNECT: runtime, owner and bootstrap. Owner/runtime
  have no elevated flags or memberships. Bootstrap is the dedicated cluster
  superuser/CREATEDB/CREATEROLE administrator. Capability owner is NOLOGIN and
  unprivileged. Runtime can change Visit/request/line/session state and selected
  auth columns, and insert permitted append-only events; reference UPDATE and
  append-only UPDATE/DELETE remain denied.
- HBA has trust for container-local sockets/loopback and SCRAM for other hosts.
  Docker/WSL administrators can therefore access a privileged local channel.
  Credential possession, administrator access and direct SQL must be controlled
  explicitly; the cooperative application gate cannot constrain a superuser.

Potential non-HTTP writers: `bootstrap.py`, `initialize.py activate` (C0005 Start),
`provision.py`, capability installers, rollback probes, `validate.py`, account/
session validators, test runners and arbitrary Django shell/SQL clients. Existing
management commands include `seed_demo`, `seed_commercial_context_demo`,
`seed_sales_targets_demo`, `seed_daily_workspace_demo`, `reset_daily_workspace_demo`,
`seed_pre_visit_intelligence_demo`, `prepare_pre_visit_intelligence`,
`build_customer_360`, `build_recommendations`, and `build_product_associations`.
They are not protected merely by starting the Demo WSGI middleware. Freeze all
such operator entrypoints during deployment; never invoke them for this rollout.

**Complete writer quiescence/exclusive deployment ownership is NOT proven.**
No administrative fence, old-credential retirement, all-worker drain or exclusive
deployment lock was acquired during this read-only audit.

## B. Versioned installation and grant manifest

Candidate version: **H4_CONTROL_SCHEMA_V2_PREPARE_DAY_V1**. Eleven statements
captured from the actual B1/B3 disposable installers and executed in disposable
PostgreSQL. Canonical UTF-8/LF template SHA256:
`1d8b61614b62f95e4cc8d74b7acd02ab7d983d2acd546252fb13c1f2b7327874`.

Exact template follows. It is a specification, **not a persistent installer**:
placeholders must be bound safely from independently verified live identity by
a separately reviewed wrapper. Do not replace disposable guards or execute this
appendix manually to bypass missing rollout/recovery tooling.

```sql
-- H4_CONTROL_SCHEMA_V2_PREPARE_DAY_V1; verified owner connection; template, NOT a persistent installer.
CREATE SCHEMA sales_ai_demo_control;
REVOKE ALL ON SCHEMA sales_ai_demo_control FROM PUBLIC;
CREATE TABLE sales_ai_demo_control.admission (singleton boolean PRIMARY KEY CHECK(singleton),version text NOT NULL,generation uuid NOT NULL,database_oid oid NOT NULL,phase text NOT NULL,operation uuid,backend_pid integer,evidence_sha text,CHECK ((phase='ACTIVE' AND operation IS NULL AND backend_pid IS NULL AND evidence_sha IS NULL) OR (phase='PENDING' AND operation IS NOT NULL AND backend_pid IS NOT NULL AND evidence_sha IS NOT NULL AND evidence_sha ~ '^[0-9a-f]{64}$')));
CREATE TABLE sales_ai_demo_control.operations (operation uuid PRIMARY KEY,envelope jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE sales_ai_demo_control.results (operation uuid PRIMARY KEY REFERENCES sales_ai_demo_control.operations(operation),recovery_uuid uuid UNIQUE,envelope jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp());
INSERT INTO sales_ai_demo_control.admission VALUES(TRUE,'DEMO_MAINTENANCE_V2',{{GENERATION_UUID_LITERAL}},{{DATABASE_OID_LITERAL}},'ACTIVE',NULL,NULL,NULL);
GRANT USAGE ON SCHEMA sales_ai_demo_control TO {{RUNTIME_ROLE_IDENTIFIER}};
GRANT SELECT ON sales_ai_demo_control.admission TO {{RUNTIME_ROLE_IDENTIFIER}};
CREATE TABLE sales_ai_demo_control.prepared_days (operation uuid PRIMARY KEY REFERENCES sales_ai_demo_control.operations(operation),intent_sha text NOT NULL,generation uuid NOT NULL,target_date date NOT NULL,salesperson_id bigint NOT NULL,state text NOT NULL CHECK(state IN ('PREPARING','ALLOCATED','COMMITTED')),plan jsonb NOT NULL,allocation jsonb,result jsonb,owns_day boolean NOT NULL DEFAULT FALSE,CHECK ((state='PREPARING' AND allocation IS NULL AND result IS NULL AND NOT owns_day) OR (state='ALLOCATED' AND allocation IS NOT NULL AND result IS NULL AND NOT owns_day) OR (state='COMMITTED' AND allocation IS NOT NULL AND result IS NOT NULL)));
CREATE UNIQUE INDEX prepared_day_identity ON sales_ai_demo_control.prepared_days(generation,target_date,salesperson_id) WHERE owns_day;
CREATE TABLE sales_ai_demo_control.preparation_recoveries(id uuid PRIMARY KEY,operation uuid NOT NULL REFERENCES sales_ai_demo_control.prepared_days(operation),envelope jsonb NOT NULL);
```

Install in ONE owner transaction only after external writer fencing and proven
quiescence. Owner owns schema, five tables and indexes; no new sequence/function,
business-table grant, reference UPDATE or Django migration. Runtime receives
schema USAGE and SELECT on admission ONLY, with no grant option or CREATE.
PUBLIC has no schema access; runtime must have no table OR column privileges on
operations/results/prepared_days/preparation_recoveries. Inspect default ACLs,
memberships, table/column ACLs, all columns/CHECK/PK/FK/index definitions and exact
singleton identity. Unknown/partial/existing state stops; no IF NOT EXISTS,
overwrite, schema drop, automatic repair or reinitialization.

Preserve existing REFERENCE_LOCKS_V1 unchanged. If a new runtime identity is
approved, its narrowly reviewed existing journey privileges plus capability
EXECUTE/schema USAGE and gate SELECT need a new exact ACL registry. Old runtime
capability grants must not remain as extra ACLs: the inspector permits only the
capability owner and approved runtime. No direct reference UPDATE is proposed.

Pinned source SHA256 (must be rechecked before any later execution):

| File under scripts/demo | SHA256 |
| --- | --- |
| maintenance_gate.py | `8331cde01b7b54659123fcf66019385b83217e8cc2699c4d293d53d406b4cf52` |
| gate_recovery.py | `9a12dcc1fefc5b4a12b4eb14e238fdd18d0a4e59d72ca963268f40c68bd08e38` |
| prepare_day.py | `96d8a87d9dc3a218a88296afa208c531fc550d80f09836b59a8fdf4655be4fb3` |
| gate_readiness.py | `43a7234b57f2d8b27481b2f0dd571d1fa0cd36337c9d5f1a3e88a683c45c95f2` |
| demo.py | `d460596b80069b78889588fa7d7c0f2e24c969005b5b1d9372a1fb546fd9b25c` |
| generation.py | `4abefc180c373c9f4bd09363e2963fb68cd7f8b219fe38f901994d3057ead227` |

## C. Controlled rollout sequence and executable boundary

**There is no safe persistent install/recovery command in the current source.**
`install_disposable`, `recover_disposable` and `execute_disposable` deliberately
reject this persistent identity. Do not remove those guards or invent a command
name. B4 provides tested DDL and a blocked rollout contract; an executable
persistent wrapper and remaining controls require separate owner approval.

1. Approve a versioned rollout/recovery package and the exact runtime-identity
   policy. Capture a protected verified backup and signed before-state: all
   public/control rows, sequences, migrations, roles/ACLs/capabilities, generation,
   fixture and signing/session files, source/SQL hashes and worker identities.
   Existing B4 evidence is an audit baseline, not a substitute for fresh evidence
   at deployment. Never export password hashes/secrets into logs or Git.
2. Obtain exclusive operator control of owner/bootstrap/Docker/WSL/SQL clients,
   management commands, scheduled launchers and every application reconnect path.
   A separate process-held, DB-backed deployment owner lease plus durable signed
   phase journal is required. V2 request admission alone cannot drain OLD workers
   that never acquired its shared lock. Record fencing/recovery intent first.
3. Fence old credential identities against reconnect AND future DML before
   installing/activating V2. Recommended decision: a versioned runtime LOGIN for
   compatible workers, permanent retirement of the old role's login/DML rights,
   independent protected credentials and controlled launcher/profile access.
   This requires reviewed configuration/registry/capability-ACL changes; it is
   NOT approved or implemented by B4. Generation UUID, users/password hashes,
   Django signing key, cookie namespace and session rows remain unchanged.
   Temporarily restoring the same old credential is insufficient: old workers
   can reconnect. Direct owner/admin access still needs an operator freeze.
4. Only under that durable reconnect fence, stop the exact verified old worker
   tree and disable its relaunch sources through separately approved controls.
   Identify each process by source/build, creation time and ancestry, not PID
   alone. `demo.py stop` uses daemon request threads and proves port release,
   NOT request drain; do not treat its success as quiescence. Do not stop unrelated
   previews. Unclassified writers require investigation or an explicit stronger
   database/credential fence, never blanket process termination.
5. Prove all old DB transactions/connections are ended, no prepared transactions,
   no unidentified writers, no live maintenance owner and no reconnect path using
   a writable old identity. Revoking CONNECT/NOLOGIN does not stop already-open
   connections. Do not force-clear locks or infer rollback from port closure.
6. Recheck exact container/endpoint/OID/marker/generation/schema/fixtures/SQL and
   before-state. Acquire the verified owner/exclusive admission locks. Run only
   the eleven reviewed control/journal statements in ONE transaction; preserve
   external deployment fencing throughout. Existing/partial/PENDING objects stop
   for inspection; no blind rerun. No capability reinstall or Django migrate is
   needed for this currently verified Demo.
7. Independently reconcile the full installed catalog/ACL fingerprint, original
   public digests/sequences, and signed installation receipt. Publish protected
   deployment evidence safely. Installation, file publication, role/profile
   selection and worker launch are separate phases, **not one atomic rollout**.
8. Before any new traffic, require an executable full-package readiness gate:
   all five tables/constraints/indexes/ACLs, identity/fixture/capability/source
   hashes, trusted deployment journal and complete compatible-worker inventory.
   Current `verify_ready` checks admission only; current worker health fingerprints
   only maintenance_gate/gate_recovery. They cannot authorize the whole package.
9. Authorize admission explicitly only after all prerequisites are proven. Start
   only pinned compatible workers through the controlled launcher; compare
   loaded source and deployment identity for every worker. The future deployment
   design must reconcile PENDING/startup handling: current launcher refuses
   PENDING, so do not clear it just to start a worker or add a readiness bypass.
   Missing/uncertain deployment evidence must keep the deployment fenced across
   operator/worker restart. Ordinary startup must stay SELECT-only.
10. Validate fresh read paths and current/stale session/CSRF/generation behavior.
    Normal login/logout writes require explicit narrow authorization at that
    later step; B4 performs none. Preserve prior sessions and exact pending
    command UUID/payload/proof; never automatically retry a POST. Verify business
    digests/sequences unchanged, allowing only separately approved auth writes.
    Record final signed deployment evidence, then restore only approved traffic.
    Old-role fencing remains; do not re-enable ungated builds as a rollback shortcut.

Commands that exist and are safe to use for READ-ONLY inspection now:

```powershell
Set-Location 'D:\py project\sales_ai_copilot'
$demoPython = '.\venv\Scripts\python.exe'
& $demoPython -B scripts/demo/demo.py status
& $demoPython -B scripts/demo/gate_readiness.py  # Expected NO_GO until separately deployed
& $demoPython -B scripts/demo/deploy_lock_capabilities.py recheck
& $demoPython -B scripts/demo/plan.py prepare-day --dry-run --date 2026-10-17
```

The date is an explicit illustrative future date, not approval to prepare it.
Expected Policy A blocker is retained C0005. Do NOT run start/stop/restart,
provision/bootstrap/activate/migrate/install/prepare/recover during this audit.
Future deployment execution stops here until the missing guarded persistent
commands and role/all-worker fence are approved, implemented and tested.

Useful read-only operator SQL during an approved later window (connect using
protected configuration to the VERIFIED Demo; do not paste passwords):

```sql
SELECT current_database(),current_user,oid,shobj_description(oid,'pg_database')
FROM pg_database WHERE datname=current_database();
SELECT count(*) FROM django_migrations;
SELECT pid,usename,application_name,client_addr,client_port,state,xact_start
FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid();
SELECT * FROM pg_prepared_xacts WHERE database=current_database();
SELECT to_regnamespace('sales_ai_demo_control');
-- After verified installation only:
SELECT version,generation,database_oid,phase,operation,backend_pid,evidence_sha
FROM sales_ai_demo_control.admission;
```

These queries provide evidence, not proof against dormant clients or superusers.

## D. Recovery and rollback matrix

| Failure point | Required response |
| --- | --- |
| Baseline, backup, identity, source or writer inventory uncertain | STOP before any mutation; leave existing Demo running. No inferred quiescence. |
| Fence/drain interrupted or old writer still live | Retain durable deployment fence and original journal; classify transactions/reconnect identities. No automatic takeover or re-enable. |
| SQL failure before installation commit | Entire installation transaction rolls back; preserve fence/evidence and inspect catalog before another authorized attempt. Public rows/sequences must match. |
| Lost installation commit acknowledgement | Read catalog/OIDs/constraints/ACL fingerprint and original signed phase evidence. Never infer rollback or rerun CREATE/DROP blindly. |
| Installation committed, evidence publication interrupted | Keep traffic fenced. Reconcile committed SQL against original approved intent; publish only the proven receipt. No new baseline to mask uncertainty. |
| Profile/grant/worker activation partially completed | Fail closed under deployment journal; verify actual role, profile pins, capability registry and each process/connection before any continuation. No automatic reverse script. |
| Compatible startup fails or old worker appears | Fence new admissions, retain control/journal objects, prove drain and investigate. No ungated old-source fallback while V2 is required. |
| V2 PENDING owner alive or transaction uncertain | Preserve PENDING and all operation evidence; no PID/age-based unlock, automatic takeover or generic deployment state reset. |
| V2 owner dead, evidence unchanged | Later approved persistent recovery wrapper must acquire both owner and drained request locks and verify signed baseline/outcome. Current disposable recovery command must NOT be retargeted. |
| Prepare Day interrupted | Original plan/UUID, signed claim chain and allocation/result determine recovery. Missing/tampered evidence or unjournalled nextval gap stays fenced; no destructive rollback/sequence reset. |
| Business activity occurred after activation | Preserve new history and snapshots. Reconcile explicitly; no automatic backup restore, data merge or reset. Prefer compatible forward correction. |
| Return to pre-V2 source proposed | Separate decommission approval, complete writer fencing/drain and compatible privilege/profile contract required. Preserve all control/evidence rows; never drop them to bypass PENDING. |

## E. Disposable validation and limits

Eight focused experiments passed, zero failures/errors/skips, in
`test_stage3h3b3_3ed5a5a358714b6d8e1fd24d7214a866` (OID 55387), with independent
owner/runtime/capability roles. Database and roles were removed after validation.
All 50 migrations were applied ONLY there. Django check and migration drift clean.

1. Exact source installer DDL, five-table ownership/ACL inspection and unchanged
   public business/sequence state; outer rollback restores original control OIDs.
2. Injected interruption between gate and journal creation rolls back all DDL.
3. Repeat creation rejects DuplicateSchema, without overwriting existing state.
4. **Readiness finding:** after journals are absent, gate-only `verify_ready`
   still succeeds; Prepare Day context correctly refuses missing journals.
5. **Writer-fence finding:** an ungated runtime connection can UPDATE a Visit
   during PENDING. Probe rolled back, preserving all public rows/sequences.
6. **Connection finding:** REVOKE CONNECT denies a new connection but leaves an
   existing connection writable; probe rolled back and TEST grant restored.
7. **Retirement finding:** NOLOGIN denies new connections but not old sessions;
   restoring LOGIN lets the old credential reconnect. TEST role restored.
8. Existing disposable installers reject the persistent Demo identity before DDL.

Passing experiments **confirm these limitations**, not persistent rollout safety.
One additional affected SQL-export experiment passed after making the ignored
audit helper emit canonical UTF-8/LF bytes on Windows (1/1, zero errors/skips;
`reports/b2b3-029d3d0c181549cb925013985c9a0b68`, disposable DB/roles removed).
The checkpoint SQL appendix is byte-for-byte identical to that tested template.
Existing B3 evidence remains applicable because application/source hashes are
unchanged: 21 Prepare Day + 30 gate/journey tests and 7 JS tests. Those suites were
not repeated. B4 changed no JS. Syntax/whitespace checks and final preservation
verification accompany this checkpoint; no full suite.

Audit helper/SQL artifacts are ignored evidence only, not new runtime dependencies:
`venv/stage3h4-b4-artifacts/{audit.py,deployment_probes.py,sql-manifest.json,control_schema_v2_prepare_day_v1.template.sql}`.
The full template/source hashes are embedded above for clean-checkout review.
Protected inventory/baseline/SQL copies:
`D:\SalesAI-Demo\sales_ai_copilot\reports\h4-b4-237290287a6e4c488d68a2ff969b2b47`.
Disposable results/cleanup/before-after evidence:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-1b22365ea048495f913062716da96a70`.

## F. Preservation

Persistent Demo and production were queried READ ONLY. No authentication POST,
session change, business write, DDL/grant, service restart, new generation,
Prepare Day or C0005 completion was performed. Existing previews were left alone.
Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` retained; index empty.
No staging/commit/push. Unrelated DEMO-02 and prior B1/B2/B3 work preserved.
Final signed before-state comparison returned `READ_ONLY_PRESERVATION_VERIFIED`,
including persistent Demo/production data, credentials, sessions, generation,
fixtures, original SQLite, stash and index. `git diff --check`, Python syntax,
source/SQL fingerprints and checkpoint whitespace checks passed. The only new
repository-visible B4 file is this checkpoint; ignored audit helpers/artifacts
and protected reports introduce no application/runtime dependency.

## G. Recommendation and required approvals

**NO-GO for persistent deployment; preflight/report complete.** The SQL-only
installation transaction is validated, but a safe executable rollout is blocked:

1. Approve and implement an enforceable old-writer/reconnect retirement strategy
   and operator control of owner/bootstrap/Docker/WSL/direct SQL access. Current
   role/PID/port snapshots and shared credentials cannot provide that guarantee.
2. Approve a narrowly scoped persistent installer, signed deployment journal,
   comprehensive schema/source/ACL readiness and recovery entrypoints. Current
   guarded tools are disposable-only; leave them guarded.
3. Resolve all-worker launch, durable deployment fencing and PENDING/startup
   readiness before rollout. Do not silently clear PENDING or weaken locking.
4. Separately authorize the exact later deployment window, backup/recovery,
   required role/profile/registry changes and narrowly scoped auth validation.

No deployment, Prepare Day execution, reset, generation rotation or automatic
Visit resolution is authorized by this checkpoint.
