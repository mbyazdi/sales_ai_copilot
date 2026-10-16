# Stage 3H4-B8 — Deferred infrastructure preservation audit

2026-10-16. **AUDIT ONLY. NOT DEPLOYED. Persistent Gate V2 / Prepare Day: NO-GO.**
Owner selected deferral after B7; management UI and strategy-policy work take
priority. This checkpoint preserves the decision and future resume instructions,
not permission to implement those next tasks or deploy infrastructure.

Branch `fast-track`; HEAD and fetched `origin/fast-track` both remain
`8bdb2ca6150a27d217eade7bfce8dff3768a4694` (V3.0.22). Index empty. No staging,
commit or push. The only project file created by B8 is this audit checkpoint;
all B1–B6 source/tests/docs remain unchanged. B7 was a read-only conversational
report and created no file; its approved deferral is recorded here.

## A. Inventory and exact candidate staging allowlist

Before B8: five modified infrastructure files, ten untracked source/test/JSON
files, six untracked H4 checkpoints; plus two protected exclusions. Adding this
checkpoint produces **22 candidate paths and two excluded visible paths**.
No file outside the exact following list belongs in the preservation commit.
This is a proposed allowlist, not authorization to stage or commit.

```text
scripts/demo/README.md
scripts/demo/demo.py
scripts/demo/generation.py
scripts/demo/lock_capabilities.py
scripts/demo/verify_generation_postgres.py
scripts/demo/control_bundle.py
scripts/demo/control_bundle_v1.json
scripts/demo/gate_readiness.py
scripts/demo/gate_recovery.py
scripts/demo/maintenance_gate.py
scripts/demo/prepare_day.py
scripts/demo/tests_control_bundle.py
scripts/demo/tests_gate_recovery.py
scripts/demo/tests_maintenance_gate.py
scripts/demo/tests_prepare_day.py
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B1_MAINTENANCE_GATE.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B2_GATE_RECOVERY_READINESS.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B3_PREPARE_DAY_EXECUTOR_RECOVERY.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B4_PERSISTENT_DEPLOYMENT_PREFLIGHT.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B5_WRITER_ISOLATION_DESIGN.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B6_READINESS_WRITER_ISOLATION.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H4_B8_DEFERRED_INFRASTRUCTURE_PRESERVATION_AUDIT.md
```

The first five paths are modified tracked files; the remaining 17 are new files.
If later approved, compare the staged path set to this list for exact equality;
review the complete dependency set together rather than staging startup hooks
without their inspectors, JSON contract or recovery/executor modules.

## B. Exclusions and security review

- `db.sqlite3`: intentionally modified relative to Git, untouched by this audit,
  NEVER stage/restore/migrate it.
- `docs/checkpoints/DEMO_02_VISUAL_ASSET_SELECTION_APPROVAL.md`: unrelated,
  untracked and preserved.
- All `venv/` helpers, screenshots, databases, test artifacts and reports,
  including `venv/stage3h4-b*-artifacts/`: private/ignored evidence only.
- All protected state under `D:\SalesAI-Demo\sales_ai_copilot\`, Docker Compose
  state under `D:\docker\sales-ai-demo\`, credentials, signing keys, .env files,
  runtime/listener state, backups and generated sessions/journals: outside the
  source boundary; never copy into Git.

Candidate files contain generated-secret code and credential-path names, not
actual passwords, password hashes, keys or connection URLs embedding secrets.
Private report paths in checkpoints are evidence references, not imports or
required historical initialization inputs. Absolute Windows paths identify the
approved local Demo environment; they are not portable credentials or arbitrary
database selectors. The current target remains deliberately Windows/Demo-scoped.
No new image, binary database, compiled file, schema migration or .env is selected.

## C. Dependency closure and compatibility

| Area | Source/dependencies required to resume |
| --- | --- |
| Admission | maintenance_gate; outer Django transaction includes session persistence; shared request lock, durable PENDING and owner lease |
| Recovery | gate_recovery; purpose-specific signed evidence, exact operation/identity/source, drained locks and outcome verification |
| Prepare Day | prepare_day; plan, initialization, bootstrap, preservation and public-state reconciliation; separate signed journal |
| Readiness | control_bundle plus JSON; gate_readiness; startup integration in demo/generation |
| Validation | four new test modules and modified disposable runner; existing generation/capability/deployment tests and source fixtures |
| SQL | Gate V2 DDL in maintenance_gate.install_disposable; day DDL in prepare_day.install_disposable; complete eleven-statement template in B4; catalog contract JSON |

Existing helpers `common.py`, `plan.py`, `preservation.py`, `provision.py`,
`bootstrap.py`, `initialization.py`, `deploy_lock_capabilities.py`,
`tests_generation_postgres.py`, `tests_lock_capabilities.py` and
`tests_lock_deployment.py` are already committed at V3.0.22. Existing application
models/services, pricing data, requirements and the reference-lock adapter/SQL
are also committed dependencies, not extra staging candidates. No imports from
ignored provisioning artifacts or mandatory historical private reports were found.

Versions/fingerprints:

- Admission `DEMO_MAINTENANCE_V2`; day protocol `PREPARE_DAY_V1`.
- Bundle `H4_CONTROL_SCHEMA_V2_PREPARE_DAY_V1`: five owner-controlled tables,
  13 constraints and seven indexes. Runtime has schema USAGE and SELECT on
  admission only; no private-journal privileges or DDL.
- JSON SHA256: `ee02a1439c026c7f4ef03808f20020ca167cc6b5b34a6a6026eedfb1eacc9b76`.
- B4 canonical DDL template SHA256:
  `1d8b61614b62f95e4cc8d74b7acd02ab7d983d2acd546252fb13c1f2b7327874`.
  It is a specification, NOT an executable persistent rollout installer.
- Committed `apps/core/sql/reference_locks_v1.sql` unchanged, SHA256
  `7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.

**Compatibility caveat: the Demo launcher source intentionally changed.**
`demo.preflight` now requires complete ACTIVE Gate V2 readiness;
`generation.install` installs the outer admission middleware; worker health
reports loaded source/contract evidence. `lock_capabilities.inspect` accepts an
explicit runtime while retaining its previous default and strict checks. The
runner provisions objects ONLY in verified disposable PostgreSQL.

Persistent Demo is still the unchanged older loaded process, PID 37632 at
`localhost:8900`, database `sales_ai_demo_db:5433`, active generation
`6ae05c63-b9a3-4e85-a469-4643d3f76a27`. Its control schema is absent. **Restarting
it from this edited source would fail closed. Source preservation is not runtime
restart compatibility.** There is no new feature flag, unlocked fallback or
automatic installation. Do not restart/redeploy it from a preservation commit.
Any pinned V3.0.22 runtime/restart arrangement requires separate identity/profile
review and authorization; do not infer one already exists from the running PID.

No application views/services/models, base Django settings, production launcher,
templates, static JS/CSS or migration files are changed. The new admission path
is installed by dedicated Demo configuration/tests, not by ordinary production
settings. Existing original-PostgreSQL deployment restrictions remain unchanged.
The current running Demo/other previews were not reconfigured or interrupted.

## D. Reused validation and fresh read-only checks

Trustworthy B6 evidence retained; no suites rerun:

- 54/54 generation, admission, recovery, readiness and lock/security tests:
  `reports/b2b3-24894941f91940c6a4b0f4947b4743c5`.
- 21/21 Prepare Day concurrency, lifecycle, preservation and crash-recovery tests:
  `reports/b2b3-46c1427fd78d4de3b36dbbf3628e38ab`.
- Both reports: zero failures/errors/skips and successful disposable DB cleanup;
  Django check and migration drift passed there with all 50 migrations.
- Prior 7/7 generation-client JS tests remain applicable; JS source unchanged.

B8 verified current loaded core/JSON fingerprints against B6 readiness evidence;
none of the relevant source/test files is newer than the successful results.
Current candidate Python AST syntax and tracked/untracked whitespace checks pass;
`git diff --check` passes. No full suite, new DB/test provisioning or browser run.

Fresh SELECT-only readiness remains `NO_GO / MISSING_OR_INCOMPATIBLE`, listener
V2 signature unproven, all_workers_verified=false, execution_authorized=false,
persistent_recovery_available=false. Persistent Gate/Prepare Day are unavailable.
Current production/Demo/protected-file preservation equals the signed B6 baseline
in `reports/h4-b6-3a57b8b541f940948356c415582e6acb`. Reports were read in place;
no new private evidence files or database snapshots were created by B8.

## E. Exact deferred resume point

**Do not resume at SQL installation or Prepare Day execution.** After a separate
owner decision to reprioritize deployment, resume with a disposable prototype of
the versioned runtime-profile transition and signed rollout/recovery workflow.

Prerequisites, in order:

1. Reverify committed preservation source, exact target/container/OID/marker,
   migration graph, generation/fixtures, signed evidence and current drift.
2. Approve administrator/direct-SQL trust boundary, deployment window, backup/
   disposable restore proof, and the exact source/SQL/grant/configuration intent.
3. Implement/test a separate V2 runtime identity across common/profile credentials,
   connection guards, middleware installation, health and capability/registry pins.
   Preserve generation UUID, signing key, users, sessions and pending envelopes.
4. Implement/test signed persistent installation/activation/recovery tooling,
   including PENDING-safe infrastructure-only worker certification. Do not
   weaken normal startup or remove disposable-only guards as a shortcut.
5. Prove durable retirement of old LOGIN/DML/column/sequence/capability authority,
   exact existing-session drain and controlled reconnects; inventory ALL writers
   without stopping unrelated previews. Unknown writers/prepared transactions or
   uncertain outcomes are STOP conditions. Direct privileged SQL is a trust limit.
6. Validate every deployment phase/interruption, metadata publication and worker
   activation in disposable PostgreSQL; obtain explicit persistent deployment
   authorization. No ungated rollback, automatic takeover or PENDING bypass.
7. Only then perform a separately approved fenced rollout and preservation
   reconciliation. Persistent Prepare Day/recovery entry points still need
   reviewed target validation and authorization; current ones remain disposable.
8. Before any later day preparation, obtain a signed current plan/date/UUID and
   confirmation. Existing C0005 IN_PROGRESS on 2026-10-15 blocks a later batch.
   Explicit authorized Visit resolution is separate; no completion, redating,
   reset or generation rotation is implied by deployment or source closeout.

B7 estimated 26–39 engineering hours, allowing 4–6 working days plus approvals,
for the remaining mandatory implementation/rehearsal/deployment work. It is
deferred, not completed or silently authorized by this audit. Management UI and
strategy-policy development require their own task scopes and safe preview paths.

## F. Source-only closeout recommendation and preservation

**GO for one source-only preservation commit of the exact 22-path allowlist,
after owner approval. NOT DEPLOYED / NO-GO for persistent execution or restart.**
Suggested description: preserve deferred Demo maintenance, recovery and Prepare
Day infrastructure; isolated validation passed; persistent rollout not authorized.
Do not advertise this as a deployed feature or an operational restart baseline.
If restart-ready persistent Demo compatibility is a release requirement, this
candidate is NO-GO for that release until separately resolved; do not remove
readiness protections to make it start.

No source/database/configuration changes were made by B8. Original SQLite SHA256
remains `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`,
modified relative to Git and UNSTAGED. Original stash remains
`2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index empty; unrelated DEMO-02 and
all earlier work preserved. No production/persistent Demo DDL, grants, writes,
restarts, authentication, credential changes, session termination, Prepare Day,
recovery release, reset or generation switch. No staging/commit/push performed.
