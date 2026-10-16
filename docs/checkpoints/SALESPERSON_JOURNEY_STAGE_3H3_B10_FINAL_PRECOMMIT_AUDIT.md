# Stage 3H3-B10 — Final source-only pre-commit audit

**GO for owner approval of a V3.0.22 source-only Demo infrastructure commit.
NO-GO for deploying this build to original PostgreSQL. No commit/push authorized
or performed by this audit.**

Started 2026-10-15; resumed 2026-10-16. Branch `fast-track`; HEAD and fetched
`origin/fast-track`: `1a96e92b938a5f64d586249245734f8e5d083b1e` (V3.0.21).
Index empty. Existing approved/unrelated work retained.

## Recovery and inventory reconciliation

Recovered the B10 before-state and candidate reconciliation, completed disposable
test results/cleanup, and two checksum-verified source-only initialization copies.
Current tested Python/JS/SQL/launcher source matches those copies and the B10
before-state. The only existing-file change is the documentation warning in
`scripts/demo/README.md`; this resumed audit completes its link and this checkpoint.
Successful suites were not rerun. Remaining work completed: dependency/secret
review, current read-only readiness, syntax/whitespace checks and final manifest.

The standalone original B8 manifest was not found. Its stated 43-file boundary is
reconstructed from the protected pre-B9-B inventory, excluding the three known
B9-A additions and the two protected/unrelated files. It is not presented as a
verbatim recovered B8 artifact. The entire current set was independently reviewed:

- B8 boundary: 43 files, including 24 Demo files, seven checkpoints and 12 shared
  source/test/SQL files.
- B9-A adds three: `initialization.py`, `initialize.py`,
  `verify_initialization_postgres.py`; modifies existing initialization scripts/docs.
- B9-B adds three: `preservation.py`, `tests_preservation.py`, B9-B checkpoint;
  modifies existing reconciliation/deployment/verification scripts/docs.
- B9-C adds one checkpoint; modifies README deployment documentation only.
- B10 adds this checkpoint and strengthens the existing README warning.
- **43 + 3 + 3 + 1 + 1 = 51 allowlisted files.** No dependency is omitted to make
  the commit appear Demo-only; shared Feedback/Submit changes and SQL are included.

## Exact staging allowlist — proposed only

Stage these exact paths only after owner approval, against the audited source.
Do not use directory-wide staging, `git add .` or `git add -A`.

```text
apps/core/reference_locks.py
apps/core/sql/reference_locks_v1.sql
apps/customers/js_tests/guided_basket.test.cjs
apps/customers/js_tests/guided_feedback.test.cjs
apps/recommendations/feedback.py
apps/sales_requests/js_tests/review.test.cjs
apps/sales_requests/submission.py
apps/visits/js_tests/visit_finish.test.cjs
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B1_DEMO_INFRASTRUCTURE.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2A_SYNTHETIC_BOOTSTRAP.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2B1_DRY_RUN_PLANS.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2B2_GENERATION_SAFETY.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2B3_LIVE_GENERATION_VERIFICATION.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2B6_ISOLATED_LOCK_CAPABILITIES.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B2B7_DEMO_LOCK_CAPABILITY_DEPLOYMENT.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B9B_PRIVATE_DEPENDENCY_REMOVAL.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B9C_POSTGRESQL_DEPLOYMENT_BOUNDARY.md
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3H3_B10_FINAL_PRECOMMIT_AUDIT.md
scripts/demo/README.md
scripts/demo/__init__.py
scripts/demo/bootstrap.py
scripts/demo/common.py
scripts/demo/demo.ps1
scripts/demo/demo.py
scripts/demo/deploy_lock_capabilities.py
scripts/demo/generation.py
scripts/demo/generation_client.js
scripts/demo/generation_client.test.cjs
scripts/demo/initialization.py
scripts/demo/initialize.py
scripts/demo/lock_capabilities.py
scripts/demo/lock_rollback_probe.py
scripts/demo/plan.py
scripts/demo/preservation.py
scripts/demo/provision.py
scripts/demo/tests_generation.py
scripts/demo/tests_generation_postgres.py
scripts/demo/tests_lock_capabilities.py
scripts/demo/tests_lock_deployment.py
scripts/demo/tests_plans.py
scripts/demo/tests_preservation.py
scripts/demo/validate.py
scripts/demo/validate_fixtures.py
scripts/demo/verify_deployed_locks.py
scripts/demo/verify_generation_postgres.py
scripts/demo/verify_initialization_postgres.py
scripts/demo/verify_reference_locks_sqlite.py
static/core/js/guided_basket.js
static/core/js/guided_feedback.js
static/core/js/sales_request_review.js
static/visits/js/visit_finish.js
```

Explicit exclusions: tracked local `db.sqlite3`; unrelated
`docs/checkpoints/DEMO_02_VISUAL_ASSET_SELECTION_APPROVAL.md`; all `.env`/credentials,
private keys/passwords, local profiles/registries, Compose instance state, database
copies/snapshots/dumps, reports/logs/screenshots/browser profiles, venv contents,
generated files and private previews. External `D:\SalesAI-Demo\sales_ai_copilot`
and `D:\docker\sales-ai-demo` instances are not commit payloads. No new Django
migration is in the allowlist. Migration 0003 already exists in committed source.

## Dependency, security and reproducibility review

All candidate imports resolve to repository helpers, committed baseline code,
standard library or declared Django/psycopg dependencies. Bootstrap's approved
price dataset/loader, DEMO-06 product definitions, manifest and image assets are
already in the baseline. No original database, DEMO-02 planning or ignored private
Python/report is a fixture source. No required import or runtime data dependency
is missing from the commit boundary.

Candidate extensions are source/test/SQL/docs only. Scan against actual configured
local secret values found no matches; no private keys/credential DSNs were found.
Controlled test placeholders and random-secret generation are intentional.
Instance credentials, auth hashes and operational manifests are not copied into
source. Fixed Windows paths are the approved Demo installation contract and
documentation examples, not embedded credentials; repository root is computed.
`venv/Lib/site-packages` is a normal dependency path, not historical artifact code.

This is a Windows/Docker local environment, not a portable public deployment.
Fresh installation requires installed requirements, the pinned image, approved
available ports/paths and operator permissions. Fresh Docker/volume provisioning
was not repeated in this audit. Database-level initialization was exercised from
source-only copies against fresh disposable DBs/independent roles on the verified
Demo cluster. Ordinary startup never seeds, migrates, prepares dates or installs
capabilities. Cross-environment regression runners additionally need their
configured production SELECT-only audit credential; that is not a fresh Demo
provisioning dependency.

Generation fencing is Demo-profile-only. Optional client hooks do not change
production UUID/payloads without the Demo transport. Shared PostgreSQL locking
changes, however, affect every PostgreSQL target and have the deployment boundary
below. There is no unlocked fallback or new broad reference UPDATE grant.

## Focused validation evidence

Recovered completed B10 results with unchanged source hashes:

- **35/35 PostgreSQL methods**, zero failures/errors/skips. Includes B3 real
  sessions/CSRF/generation rejection, B6 lock security/order/lifetime/concurrency,
  Feedback/Submit/replay/rollback and B7 readiness/drift. Independent disposable
  DB and owner/runtime/capability roles removed.
- **24/24 clean-source initialization steps**, two dates (2026-10-15/16), two
  disposable DBs with independent roles; fresh setup, authorized C0005 Start,
  repeat NO_OP/conflict, missing/tampered/foreign evidence and populated read-only
  preservation. Copies have no venv/private reports/Git metadata/source SQLite.
- Focused Python: evidence **4/4**, generation **14/14**, plans **16/16**.
- Affected JS: **87/87**, zero failures/skips. Not rerun on resume because source
  hashes and prior tool results remain available.
- PostgreSQL test-run Django check and migration drift passed; no model changes.
  Current resumed Demo Django/preflight check also passes read-only.
- Python AST/import review passed (28 candidate Python files); all 10 JS/CJS files
  and the PowerShell launcher parse successfully. Whitespace checks include every
  untracked candidate and this documentation. SQL syntax was exercised by actual
  disposable installs of the unchanged approved source. No full suite was run.

Protected audit root:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b10-e99b92c4f4e743e39b93c59358e5241a`.
Recovered test artifacts: `reports/b2b3-3b83c4ca797c4746a6b5734ecea7fef3`,
`reports/b9a-02c9db890d6f476c937cdc3932d85c8a`,
`reports/b9a-a6d1c2bb51c245b8b4f29a145a83a4f4`. These are protected evidence
locations, never executable or required historical source dependencies.

## Current Demo and original PostgreSQL

Demo: 50 migrations; exact `REFERENCE_LOCKS_V1` bodies/identities/owner/ACLs match
the protected registry. Canonical LF SQL SHA256:
`7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.
Dedicated NOLOGIN owner has only reviewed identity/link SELECT + UPDATE(id)
capabilities; runtime gets exact schema USAGE/function EXECUTE, no direct reference
UPDATE/PUBLIC EXECUTE/DDL/owner-role assumption. Demo listener remains on
`http://localhost:8900` (PID 37632), without restart or business probes.

**Demo-day limitation:** all five persistent Visits remain dated 2026-10-15;
C0005 remains IN_PROGRESS. On the observed Asia/Tehran day 2026-10-16 there are
zero current-day Visits. Infrastructure readiness is not a claim that today's
Daily Plan is ready for a new demonstration. Separate approved day preparation
is required; old active Visits must block conflicts. No redating, automatic
completion/reset or Prepare Day execution was performed.

Original PostgreSQL remains at 49 migrations, missing capability schema/functions
and pending `0003_complete_visit_receipt`. Its previously existing reference-table
UPDATE grants remain unchanged and differ from Demo's policy. Do not silently
reuse/relax Demo's strict role/registry validator for that original instance.

Accidental activation paths still exist: the private original `start_local.py
serve` launcher (active port 8784, PID 3492), generic `manage.py runserver`, and
WSGI/ASGI with original PostgreSQL environment can load the shared source without
capability readiness enforcement. Existing processes' loaded module versions are
not inferred from port presence. A restart/reloader/shared-checkout deployment is
not authorized. An eligible new Feedback/Submit can error and roll back; prior
login/GET/check success is not admission evidence. No such original POST was sent.

No tracked CI/deployment workflow, custom hooks path or active local Git hook was
found. This cannot prove absence of external automation. A future push must not
trigger original deployment/restart; independently confirm external automation
before coupling a push to operational release.

## Mandatory non-Demo deployment prerequisites — future approval only

Before any maintenance, approve exact target/roles, maintenance scope and proposed
grant policy. Then follow this order, with separate evidence/approval as required:

1. **Backup/rollback:** quiesce only verified affected runtimes; capture protected
   database backup and schema/role/version/data/sequence evidence; verify a usable
   restore/rollback plan against an explicitly approved isolated recovery target.
   Never clone original business data/password hashes into synthetic Demo. No
   backup/export/restore is performed by B10.
2. **Migration 0003:** apply only after separate original-target authorization;
   reconcile the full reviewed 50-migration graph. No auto-migrate/seed/repair.
3. **Capability installation:** explicitly install approved `REFERENCE_LOCKS_V1`
   with independent NOLOGIN ownership, exact SQL/security/grants and a protected
   original-target registry. Do not retarget Demo tooling by editing constants.
4. **Existing-grant policy review/reconciliation:** verify the result against the
   policy approved before writes. Original runtime already has broad reference
   UPDATE; explicitly approve retention implications or separately authorize/test
   reductions. No automatic grant broadening or reduction; no Demo-policy bypass.
5. **Executable readiness gate:** under an approved target policy, validate exact
   DB/container/endpoint/OID/roles, schema, SQL version/bodies/signatures/owner/ACLs
   and registry before admitting this build or its connections. Validate missing
   and drift failures, real least-privilege operations/concurrency, and recovery
   in disposable PostgreSQL. Generic Django check is insufficient.
6. **Explicit deployment authorization:** independently review completed evidence
   and authorize activation/restart of the exact build. Reconcile after activation.
   Code/schema/capability versions must remain paired during rollback; never drop
   dependencies under live code, use CASCADE, silently fall back to unlocked reads,
   restore business data or switch databases automatically.

These steps are not a multi-step atomic transaction, are not executed, and do not
come with commit approval. Original deployment remains **NOT APPROVED**.

## Recommendation and preservation

Recommend one dependency-complete, source-only commit after owner approval:
`V3.0.22: add isolated persistent demo infrastructure`. Inspect the exact 51-path
staged inventory and staged whitespace/secret boundaries in that future task.
This is not a claim of full-suite validation, original PostgreSQL compatibility,
current-day Demo preparation or authorized reset/generation switching.

No implementation changes were made by B10: only the README deployment warning
and this audit checkpoint. Before/after reconciliation preserves original/Demo
data, Demo full sequences, grants, fixtures, credentials, profiles, sessions,
generation and listeners. Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index empty;
no staging, commit or push. Unrelated DEMO-02 planning and all approved work retained.
