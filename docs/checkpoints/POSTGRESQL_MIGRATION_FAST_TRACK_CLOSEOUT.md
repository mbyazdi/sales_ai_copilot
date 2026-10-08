# PostgreSQL migration — Fast-Track closeout

Date: 2026-10-08. Owner authorized local cutover and this infrastructure-only
checkpoint commit/push. No Stage 3 functionality or unrelated product work is
authorized by this closeout.

## Accepted results and current runtime

- DB-01B3B: 2,396 imported business/auth rows reconciled, primary/foreign keys,
  sequences and financial totals preserved; 388 audited derived Decimal conversions.
- PostgreSQL 17.11 / sales_ai_db: 49 applied migrations and 40 tables.
- DB-01C1: 351/351 selected PostgreSQL compatibility tests passed, including real
  revision concurrency and JSONB display-order regressions. This suite was not
  repeated during closeout.
- DB-01C2A: sales_ai_runtime uses reviewed table/sequence privileges, without
  elevated flags, ownership or owner membership; append-only history restrictions.
- DB-01C4A/F1: normal password authentication, database-backed sessions, CSRF,
  role/customer/Visit authorization and standard application POST logout validated
  in isolated PostgreSQL databases. Logout/navigation: 19 distinct focused tests
  passed; one real 390px screenshot confirmed unchanged header height and 44px action.
- DB-01C4B: schema-compatible SQLite recovery artifact verified at 49 migrations;
  all six foundation tables empty, original data/keys preserved, quick_check=ok,
  foreign_key_check empty, Django check passed.
- DB-01C5A: normal local Django runtime started on http://127.0.0.1:8784/ as
  sales_ai_runtime, using database sessions and unchanged authorization/login logic.
  No preview identity injection or signed-cookie authentication is used.

**Owner's final manual smoke report:** salesperson and manager login/logout
succeeded; manager data displayed correctly. Daily had no Visits for the current
date. The full Guided Sale journey was consequently **not exercised** during this
final manual smoke test. That limitation is retained; earlier catalog/visual/test
evidence is not relabeled as a successful final end-to-end journey. These manual
tests were accepted as reported and were not repeated by the agent.

Read-only post-manual reconciliation: all business/framework table digests, financial
data, Visit/recommendation records, schema, sequences and grants match the approved
baseline. Only auth_user.last_login changed for user IDs 1 and 4; other user fields,
passwords and roles are unchanged. django_session was empty at closeout inspection.
No seed, business mutation, recommendation/Customer360 regeneration or cleanup occurred.

Stored totals: Sale/SaleItem/Customer360 each 425150.00; discounts 5790.00;
SalesOutcome amounts 20000.00. Actual legacy units and the approved SalesOutcome 1
customer-lineage mismatch are preserved, with no manual correction.

## Local configuration and safe startup

The local, Git-ignored startup profile is
venv/local-runtime/postgresql-profile.json. It selects PostgreSQL by default for
the dedicated launcher, reads the runtime password privately from
D:\docker\sales-ai-postgres\runtime-credentials\sales_ai_runtime.env, and changes
only the launched process environment. No credentials or global Windows environment
settings were committed/changed. Local profiles/backups/logins/screenshots stay out of Git.

```powershell
python -B .\venv\local-runtime\start_local.py check
python -B .\venv\local-runtime\start_local.py serve
```

Login normally at http://127.0.0.1:8784/accounts/login/ with existing account
credentials supplied privately. The launcher never migrates/seeds and fails on
unexpected identity/migration state instead of falling back. Do not use an old
preview's cookies, identity headers or private access links.

The shared source database selector remains explicitly environment-driven and
retains SQLite fallback. It does not auto-load .env/.env.example. Bare manage.py
without the approved process profile can still select the preserved original SQLite
and must not be used for ordinary development/demo writes. .env.example now names
the runtime role and PostgreSQL selection, with no password value.

To reproduce another local/home/office environment, privately provision the runtime
credential file and rebuild the secret-free launcher profile using DB_ENGINE,
POSTGRES_DB/USER/HOST/PORT/SSLMODE/CONNECT_TIMEOUT and an external credential-file
pointer. DB-01A documents process injection; local STARTUP.md records this machine's
exact commands. No automatic data synchronization or privileged runtime account is
implied. Office/remote TLS must use the approved trusted-CA configuration.

## Recovery and divergence

Original SQLite remains local-only, intentionally modified and unstaged:
SHA256 1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15.
It has 44 migrations and is preserved as a source, never migrated/reset/replaced.

Protected, read-only prepared artifact:
venv/db01c4b-artifacts/20261008T181843Z/rollback.sqlite3.
SHA256 911DE912915FC09588947FE9C3C992721F0DC2400E0864CB3D16E7538F299F86.
Its rollback-manifest.json and ROLLBACK_USAGE.md record the backup, five applied
migrations, per-table/financial digests and guarded future working-copy procedure.
No recovery working copy or rollback was activated. All 78 legacy source sessions
were preserved by the migration-only task; any session retirement is a separately
approved operation on a disposable working copy, not the original/prepared artifact.

After the first PostgreSQL authentication writes, auth timestamps can differ from
SQLite legitimately. PostgreSQL is the active local runtime store; the SQLite
artifact is a historical recovery baseline. Before rollback, pause writers with
approval and audit any newer business data. Never silently merge/reimport/reset
either store, discard post-cutover records or copy PostgreSQL sessions back. The
current selector does not implement SQLITE_DB_PATH; use the guarded recovery helper
only after recovery approval. Production schema/privileges are not changed here.

## Infrastructure commit boundary and validation

Include only DB-01A configuration/driver/tests, F1 revision guard with independent
core concurrency regressions, F2 Product Detail display-order/fixture corrections,
standard logout/navigation/tests, approved DB checkpoints and this closeout.

Keep Stage 3A1 contract, Pricing Core, mutation receipt model/admin/migration/tests
and receipt-dependent concurrency integration uncommitted. The infrastructure test
blob contains six core revision cases; the complete receipt-history variant remains
unchanged in the working tree for its later Stage 3 checkpoint. No local tests are
discarded and no business model semantics are rewritten.

Consequently this isolated source graph contains **48 migrations** (30 application
migration files plus 18 installed Django migrations); the live
49th migration, sales_requests.0002_salesrequestmutationreceipt, belongs to the
approved but deferred Stage 3B1 work. That extra live table is empty and unused by
the committed application paths. Do not fake/unapply/remove it to make counts match.
The running complete working tree and local launcher continue to use all 49.
Future Stage 3 publication must include its model/migration/tests together; a clean
infrastructure checkout must not silently regenerate a replacement migration.

The interrupted closeout was resumed under the owner's explicit instruction not
to rerun Django tests, PostgreSQL suites, manual login/logout or screenshots.
Previously approved automated/manual evidence is retained. Final commit checks
are cached whitespace/diff/credential exclusion and static dependency inspection
of the infrastructure test blob; no new staged-tree test execution is claimed.

Exclude db.sqlite3, credentials, local profiles, venv evidence, recovery databases,
browser state and screenshots. Original stash remains
2dac7bdc26f07f611f471564476ceaa52ec367cc. After commit/push, verify HEAD equals
origin/fast-track and that the remaining working changes are exactly Stage 3 plus
the intentionally preserved SQLite database. No Stage 3 implementation follows.
