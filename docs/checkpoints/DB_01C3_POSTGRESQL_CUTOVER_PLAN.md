# DB-01C3 — PostgreSQL cutover plan and safety checkpoint

Date: 2026-10-08. **Planning only; no cutover authorized or performed.**
Target: PostgreSQL is the default local development/demo backend; preserved SQLite
is a recovery source. No application, settings, migrations, privileges, runtime or
database changes are made by this checkpoint. Existing preview is left untouched.

Authority: owner-approved DB-01B3B transfer, DB-01C1 compatibility gate,
DB-01C2A runtime grants and DB-01C2B migration-purpose visual review. Older
DB-01A/DB-01C1 statements about remaining runtime-role work are superseded by
C2A/C2B. Salesperson Journey Stage 0/1/2/3 contracts remain authoritative for
business behavior; this plan does not activate additional Stage 3 functionality.

## A. Preconditions and go/no-go

Fresh read-only inspection confirmed:

- `fast-track`, HEAD `8fceda04dbafba6cb4cfb66a88653169a2a4dd98`; index empty.
- Original SQLite: 34 application/framework tables plus `sqlite_sequence`, 44
  migrations; no WAL/SHM/journal sidecars. SHA256:
  `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
- Protected frozen migration snapshot:
  `venv/db01b3b-artifacts/61301b5379417500c9e2-20261008T115440Z/source-frozen.sqlite3`;
  SHA256 `780d86b55db6f0bd6d8556f8b529dbcbd8d09a85a89a8e7dbdf291b9ad3084af`.
  Both source hashes match their approved values; they need not equal each other.
- PostgreSQL `sales_ai_db`, 17.11, UTF8: 49 applied migrations exactly match the
  current code graph, 40 tables, 2,396 imported rows in 29 tables. All 40 table
  digests/counts, schema definitions and sequences match the C2B baseline: no drift.
- Four users/roles/relationships preserved; 30 Customers and Customer360 rows,
  14 products, 457 Sales, 1,154 SaleItems, 453 recommendations (49 active), 36 Visits.
  Sale/SaleItem/Customer360 totals each `425150.00`; discounts `5790.00`; legacy
  SalesOutcome amounts `20000.00`. Actual stored units and the approved Outcome 1
  customer-lineage exception are preserved. Sessions and six new foundation
  tables remain empty; the audited 388 Decimal conversions are unchanged.
- Runtime grants match C2A. `auth_user` UPDATE and full session CRUD are present;
  normal login is therefore permitted at the table layer. No imported password
  currently needs a Django algorithm/work-factor upgrade; no login was performed.
- Existing 8783 preview answers unauthenticated Daily GET with the expected login
  redirect (302); no preview process/configuration was stopped or changed.

**Assessment: plan ready; activation is NO-GO until the following gates close.**

| Gate | Required evidence before activation |
| --- | --- |
| Explicit execution approval | Authorize configuration/default changes and the exact first-write validation scope. |
| Reproducible configuration | Approved default/profile behavior, focused configuration tests, runtime identity assertion and no silent SQLite fallback. |
| Normal runtime authentication | Existing-account login/logout/session/CSRF checks in an isolated PostgreSQL copy, using runtime grants and ordinary Django middleware. C2B's temporary sessions are not this proof. |
| Recovery readiness | Protected PostgreSQL backup and a validated, current-schema SQLite recovery copy; never migrate the original. |
| Final source/target reconciliation | Recheck approved hashes, migration fingerprints, PK/row digests, financial/per-sale totals, FKs, ranks, Visits, sequences and grants after pausing other writers. Stop on unexplained drift. |
| Source checkpoint | Approved uncommitted foundations/configuration/F1/F2 are committed in dependency order under separate commit authorization; record the executable commit and migration fingerprint. |

The prior 351/351 PostgreSQL gate is accepted evidence, not re-executed here.
Only changed configuration/authentication/recovery behavior needs new focused
validation unless another material change invalidates that evidence.

## B. Exact configuration and credential strategy

**Current behavior:** `sales_ai_copilot/database.py` selects SQLite when DB_ENGINE
is absent/blank/sqlite. It reads process variables only; neither `.env` nor Docker
credentials auto-load. Merely creating a PostgreSQL environment file cannot
establish a default. Current `.env.example` still selects SQLite and names the
owner account; it must not become the runtime template unchanged.

**Recommended future implementation, requiring execution approval:**

1. Make the selector's absent/blank default PostgreSQL, with missing/inaccessible
   credentials failing explicitly. Explicit `DB_ENGINE=sqlite` remains a recovery
   choice. Never fall back after a PostgreSQL connection/configuration failure.
2. Add a minimal settings bootstrap shared by manage.py/WSGI/ASGI. Read a local,
   ignored project `.env` containing only `SALES_AI_DB_ENV_FILE=<absolute path>`;
   the referenced ACL-protected external file supplies the database variables.
   Explicit process values take precedence for CI/office/isolated validation;
   actual runtime identity must still equal the approved database/role. Do not
   import preview settings, log loaded values or introduce a dotenv dependency.
3. Add explicit `SQLITE_DB_PATH` support for a writable recovery copy. When SQLite
   is selected, require this path and reject the preserved original/frozen paths;
   no implicit write connection to `BASE_DIR/db.sqlite3`. This is proposed support,
   not a currently available variable. Update focused configuration assertions
   for the intentionally approved default change, retaining isolation/security tests.
4. Update `.env.example` to explain the loader/pointer, PostgreSQL default,
   `sales_ai_runtime`, blank password placeholders and explicit recovery selection.
   No machine/user-level Windows environment changes, shell-profile edits or
   implicit Docker file loading. Use project-local launch/IDE configuration only.

| Runtime variable | Intended local value/behavior |
| --- | --- |
| DB_ENGINE | postgresql; no automatic backend fallback |
| POSTGRES_DB | sales_ai_db |
| POSTGRES_USER | sales_ai_runtime |
| POSTGRES_PASSWORD | Read only from the protected external runtime file; never a command argument/log/commit |
| POSTGRES_HOST / POSTGRES_PORT | 127.0.0.1 / 5432 here; environment-specific elsewhere |
| POSTGRES_SSLMODE / POSTGRES_CONNECT_TIMEOUT | prefer / 5 for loopback; verify-full and a trusted PGSSLROOTCERT for a remote server |
| SALES_AI_DB_ENV_FILE | Proposed portable absolute pointer; not currently interpreted |
| SQLITE_DB_PATH | Proposed explicit recovery-copy path; never the original |

Existing credential file:
`D:\docker\sales-ai-postgres\runtime-credentials\sales_ai_runtime.env`.
Its ACL permits only the current Windows user and SYSTEM. Keep an independent,
protected profile per home/office host; do not copy the Docker admin password into
runtime profiles or synchronize credentials through Git. Host/path differences
belong to local profiles, not hardcoded application paths. Matching configuration
does not authorize automatic data synchronization between home and office.

Keep the existing owner/admin for explicit maintenance only. Runtime retains
CONNECT, schema USAGE, 34 required sequence USAGE grants, reviewed table DML,
append-only SELECT/INSERT restrictions and no elevated flags/ownership/membership.
Do not broaden grants for startup, tests, migrations, prices, demo reset or cleanup.
Future new schema objects require an explicit grant review; there is no blanket
future-table write policy. Submitted-row immutability remains a model/service guard.

## C. Future cutover execution sequence

Commands below describe a later approved execution; **none run in C3**.

1. Record Git/index/stash, original/frozen hashes, code/migration fingerprints,
   target identity/role/grants and baseline reconciliation. Keep existing work;
   no reset/checkout/clean/stash operations. Capture an ACL-protected, consistent
   PostgreSQL backup using maintenance credentials and read-only pg_dump. Runtime
   cannot inspect sequence state sufficiently for a complete dump. Do not print
   PGPASSWORD or DSNs; record backup identity, checksum and a restoration check
   in a new isolated database. Record ownership/grant policy separately.
2. Under explicit preparatory authorization, validate normal Django runtime on a
   uniquely named PostgreSQL copy of this baseline. Restore with a maintenance
   identity, give it equivalent runtime permissions, and run the application as
   sales_ai_runtime. Never point write tests at sales_ai_db or the original SQLite.
   Prepare/validate the SQLite recovery copy described in E before activation.
3. Implement the bounded configuration changes in B, validate only those changes,
   and create the separately approved source checkpoint. No new product migration
   is expected. The target already has 49 migrations; an unexpected migration is
   a stop condition, not an invitation to run migrate automatically.
4. At the activation window, pause writable application/operator processes with
   owner approval and repeat final reconciliation. The read-only 8783 preview may
   remain available, but its baseline becomes historical after authorized writes.
   Do not regenerate recommendations/Customer360, run seed/reset, or transfer again.
5. Load the approved runtime profile for the normal development process. Exclude
   preview-only PGOPTIONS/read-only hooks, signed-cookie backend, cookie name/key
   and private access routes. Normal Django database sessions, ModelBackend,
   SessionMiddleware, AuthenticationMiddleware and CSRF remain enabled. Do not
   disconnect the standard update_last_login signal.
6. In the dedicated project environment, run `python manage.py check --database
   default` and a read-only identity query. Expect sales_ai_db / sales_ai_runtime,
   UTF8, `transaction_read_only=off`, no pending migration graph differences.
   Inspect migration status/plan without applying it. Fail closed on wrong identity.
7. Start normal `python manage.py runserver 127.0.0.1:8784 --noreload` for acceptance,
   separate from the untouched 8783 preview. Authenticate an existing account only
   after first-write approval, recording the exact auth/session changes. Confirm
   the business baseline remains unchanged. No Visit completion or request submission.
8. Record the first-write timestamp/boundary, final source and target identities,
   validation results and recovery references. Declare PostgreSQL the single active
   local development/demo database only after all gates pass. No automatic migrate,
   seed, demo reset or startup data repair belongs in the launcher.

## D. Required validation and manual review

- Configuration: missing profile/secret, precedence, invalid selector/host/port,
  default PostgreSQL, explicit safe SQLite copy, home/office overrides, secret
  non-disclosure and no production TEST mirror/name collision.
- Normal runtime on the isolated copy: valid existing salesperson/manager login,
  invalid login, database-session creation/reload/logout, last_login update, CSRF
  rejection and authorized normal mutation guards. Keep feedback/receipts/snapshots
  append-only; probe failures with rollback. No new Stage 3 endpoints/UI are enabled.
- At acceptance on sales_ai_db: allow only approved auth/session writes initially.
  Record count/timestamp diffs; ordinary login writes them even without business
  actions. A later hash upgrade, if required, is an explicit auth-only difference.
- Review Daily -> Customer360 -> Guided -> recommended/ordinary Detail -> return,
  search/category/priority/pagination and manager access at 390/1440. Generate fresh
  normal-server context: preview cookies and signed links use a temporary key and
  must not be imported. Keep approved card anatomy, saved ranks and genuine ownership.
- Dataset limitations remain truthful: no Visits dated 2026-10-08, C0003 Visit 32
  is PLANNED, and ProductDemoPrice is empty. Do not create an active Visit, image or
  price just for cutover acceptance. Controlled demo changes need their own task.
- Test runner: sales_ai_runtime cannot create/migrate test databases. Use a separate
  explicit maintenance/test process and unique isolated TEST name, with connections
  and write guards excluding sales_ai_db and db.sqlite3. Never add CREATEDB to runtime
  or silently fall back to SQLite. The earlier gated operator runner is an available
  pattern; an ordinary runtime-credential `manage.py test` is not ready by default.
- Demo reset is an explicit operator command: it deletes legacy outcomes/follow-ups
  and immutable Visit snapshots, which runtime grants deliberately prohibit. Preserve
  its existing scoped contract; never call it automatically or weaken runtime grants.
  Future request/receipt/submitted evidence requires a separate reset-scope review.

## E. Explicit rollback procedure

Triggers: wrong role/database, failed normal authentication/CSRF/authorization,
unexplained reconciliation differences, missing constraints/migrations, regression
in approved journey, or unsafe write behavior. Stop acceptance on the first failure.

**Original SQLite is not a drop-in rollback for current code.** It lacks these five
reviewed migrations (six tables), in dependency order:

1. products.0003_productdemoprice
2. recommendations.0012_recommendationfeedbackevent
3. sales_requests.0001_initial
4. recommendations.0013_recommendationfeedbackevent_line_and_more
5. sales_requests.0002_salesrequestmutationreceipt

Prepare a uniquely named protected recovery copy from the validated frozen source
using SQLite's backup API with a read-only source. Only after separate explicit
authorization, apply these reviewed additive migrations to that copy, verify its
49-migration schema and normalized logical business baseline, and validate current
guards/reads/auth using isolated tests. Exclude legacy sessions from this recovery
copy by clearing only its django_session table under that preparation approval;
never copy PostgreSQL sessions into it. Record both source and prepared-copy hashes.
Never copy over, migrate, restore, reset, delete or open the original for writes.

Rollback steps, requiring owner execution approval:

1. Stop only the newly activated writable server/operator jobs; record whether any
   auth or business writes occurred. Preserve PostgreSQL and capture current evidence.
2. If there are no business changes (including auth-only first-login differences),
   obtain explicit acceptance that the recovery copy contains the pre-cutover auth
   baseline and requires re-login. Do not copy sessions back. If business writes
   occurred, apply F first; do not switch blindly to stale SQLite.
3. In a separate recovery process set `DB_ENGINE=sqlite` and the proposed
   `SQLITE_DB_PATH=<validated writable recovery copy>`, overriding the PostgreSQL
   profile. Verify backend/path/schema before serving. Never leave the runtime
   POSTGRES_USER profile silently active against another target.
4. Run focused recovery checks/reads, then authenticate with ordinary database
   sessions in the copy after approval. Record new recovery writes and designate
   one active writer. Leave the original, frozen snapshot and PostgreSQL untouched.
5. If no validated copy exists, remain stopped/read-only while preparing recovery;
   do not improvise schema changes, git checkout over uncommitted work, reverse
   PostgreSQL migrations, DROP/TRUNCATE, or restore a backup over sales_ai_db.

## F. Source/target divergence policy

At the first PostgreSQL write, the original SQLite/frozen snapshot is a historical
baseline, no longer an automatically current database. PostgreSQL becomes the
authoritative operational store when activation is accepted. Auth/session writes
are expected but audited separately; business changes are never dismissed as metadata.

Prevent concurrent writable SQLite use through explicit path/default guards. Do
not reconcile by timestamp alone, merge PKs, reimport the 2,396-row baseline, rerun
the transfer controller or use a seed/reset to erase differences. No automatic
SQLite/PostgreSQL/home/office synchronization is approved.

If post-cutover business writes exist and rollback is requested, stop writers and
inventory those changes using PK/FK/revision/event/financial evidence. Prefer fixing
configuration/runtime access while retaining PostgreSQL. Alternatively prepare an
owner-approved reverse-transfer/recovery plan with a new audited Decimal mapping,
immutable lineage/history and sequence reconciliation. Restoring an older baseline
requires explicit acceptance of loss of identified changes. Preserve both stores;
never silently overwrite either to make counts match.

## G. Git and commit boundaries

Current modified tracked files: `.env.example`, customer Guided fixtures, Product
Detail code/tests, Sales Request admin/guards/models, requirements/settings and the
local db.sqlite3. Current untracked project files are approved Pricing Core,
receipt migration/tests, F1 concurrency tests, database selector/configuration tests
and their Stage 3/DB checkpoints. No pending historical migration rewrite was found;
the sole new migration file is the reviewed receipt 0002, already applied on PostgreSQL.

Recommended future commits, each requiring separate authorization:

| Order | Exact current files/scope |
| --- | --- |
| 1 — Stage 3 approved foundations | apps/products/pricing.py, tests_pricing.py; apps/sales_requests/models.py, admin.py, migrations/0002_salesrequestmutationreceipt.py, tests_mutation_receipts.py, tests_mutation_receipt_migrations.py; Stage 3 implementation contract. |
| 2 — PostgreSQL configuration/compatibility | .env.example, requirements.txt; sales_ai_copilot/database.py, settings.py; tests/test_database_config.py; apps/sales_requests/model_guards.py, tests_revision_concurrency.py; apps/products/views.py, tests_commercial_brief.py; apps/customers/tests_guided_catalog.py; DB-01A, F1, F2, gate and this C3 checkpoint. F1 receipt regression depends on commit 1. |
| 3 — Approved cutover implementation | Only future bounded profile/default/recovery/test-launch configuration, focused tests and executed cutover checkpoint; explicit changed-file allowlist before staging. |

Review actual diffs at staging time; groups are a plan, not a staging instruction.
Retain the F1 fix throughout preparation and publish only the final validated
combined head; do not activate an intermediate foundation commit without F1/F2.
Exclude db.sqlite3, all credentials/profiles, protected snapshots/backups, venv
evidence, private preview capabilities/browser profiles and screenshots. Check the
cached diff/secret exclusions and dependency completeness. Preserve stash
`2dac7bdc26f07f611f471564476ceaa52ec367cc`; do not apply/pop/drop it. No commit/push
is authorized by C3, and no Stage 3 basket/feedback/submission work is included.

## H. Remaining risks and owner decisions

Approve a bounded execution task covering: (1) the recommended true-default,
external-profile and explicit recovery-copy configuration; (2) isolated normal
runtime/auth validation and recovery-copy preparation, including only that copy's
five migrations; (3) separately checkpointing the approved uncommitted work;
(4) the permitted first auth/session writes and the rollback treatment of any later
business writes. Choose the protected recovery/backup location and canonical
home/office data authority; no automatic cross-machine data transfer is implied.

Normal authentication has not yet been exercised without the preview harness;
permission checks and the 351-test gate are not a substitute. Ordinary writes,
operator/test credentials and deliberate demo reset must stay distinct. Restore
readiness and preserving newly written data are the principal remaining cutover
risks. Existing data limitations, legacy exception, Stage 3 semantics and approved
Guided anatomy remain unchanged.

Evidence: protected `venv/db01b3a-artifacts/61301b5379417500c9e2`,
`venv/db01b3b-artifacts/61301b5379417500c9e2-20261008T115440Z`,
`venv/db01c1-gate-artifacts/20261008T152355Z`,
`venv/db01c2a-artifacts/20261008-runtime-role`, and
`venv/db01c2b-artifacts/20261008-runtime-preview`. No tests, full suite, migrations,
role/grant changes or data writes were run during C3; only read-only safety
inspection and git diff --check accompany this document.
