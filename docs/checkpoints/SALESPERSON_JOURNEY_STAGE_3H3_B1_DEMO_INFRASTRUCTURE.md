# Stage 3H3-B1 — Persistent isolated Demo infrastructure

2026-10-15. Owner review pending. Baseline: fast-track / V3.0.21
`1a96e92b938a5f64d586249245734f8e5d083b1e`. No scenario fixtures or reset.

## Recovery and provisioned identity

Owner approved replacing 8800, reserved in Windows IPv4 and IPv6 TCP ranges
8800–8899, with **8900**. Real exclusive socket binds succeeded on IPv4 and
IPv6 loopback at 8900, and IPv4 at 5433. No reservations/firewall settings changed.
All five interrupted Demo drafts were reviewed and reused.

- Application: http://localhost:8900/accounts/login/ (IPv4 loopback listener).
- Dedicated container: `sales-ai-demo-postgres`, PostgreSQL **17.11** at
  `127.0.0.1:5433`; persistent volume `sales_ai_demo_pgdata`.
- Container ID: `69e311c315218d237f06f2d5b04395d63c30c24c0285ff18d6dbeeb7d66ab41c`.
- Pinned image: `postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`.
- Database: `sales_ai_demo_db`; owner-controlled database comment and container/
  volume labels bind identity `6ae05c63-b9a3-4e85-a469-4643d3f76a27`.
- Secret-free Compose: `D:\docker\sales-ai-demo\compose.yaml`.
- Protected state: `D:\SalesAI-Demo\sales_ai_copilot\`; independently generated
  owner/runtime/bootstrap passwords, Django signing key and shutdown token remain
  outside Git, readable only by the current Windows user and SYSTEM.

## Schema and runtime boundary

All **50/50** reviewed migrations applied only to this new database, including
`sales_requests.0003_complete_visit_receipt`. 40 public tables, 35 content types,
140 permissions. No users, groups, sessions, products, customers, Visits, prices,
requests, feedback or receipts were created. Only migrations-generated framework
metadata is populated. Six new foundation tables are empty.

Migration-source SHA256 (path/content canonical fingerprint):
`f702fb67f632ac62b25555913ae95c88c23db64fee454c2dbe33c3931ed4992f`.

Separate `sales_ai_demo_owner` owns schema/tables/sequences; separate
`sales_ai_demo_runtime` has no elevated role flags, membership, ownership,
schema CREATE or database TEMP/CREATE. Runtime reads all public tables; can
insert/update Draft header/lines, update Visits, maintain sessions and update
only user last_login/password. History tables (feedback, receipts,
acknowledgements, snapshots, outcomes/admin log) are SELECT/INSERT only.
Sequence USAGE is limited to insertable tables, without sequence UPDATE.
Catalog/inventory/price/history maintenance is not granted. Runtime cannot
connect to the cluster's `postgres` database or change the identity marker.
Bootstrap credentials are never used by the application.

## Stable access and safety

See `scripts/demo/README.md` for exact check/start/status/stop/restart commands.
The launcher uses normal Django login and DB sessions, dedicated session cookie,
independent signing key, CSRF middleware and standard csrftoken compatibility.
No preview auth bypass. Startup validates profile, credentials, Docker binding,
image/container/volume identity, database role/OID/marker and exact migration
graph. No auto migration, seed, reset, fixture creation or date changes.

Shutdown sends a protected control request only to the verified Demo listener;
no generic PID termination. A Windows venv Python redirector initially made
readiness PID comparison too strict; the Demo-only draft now accepts the actual
serving PID or its direct launcher parent. Successful guarded startup was then
verified. Dedicated PostgreSQL restart preserved volume/marker/schema/grants;
Django stop/start succeeded without touching other services.

## Focused evidence

- **11/11 infrastructure tests passed**, zero failures/errors. Covers wrong
  database/database port/application port, actual wrong OID/marker, missing
  credentials, occupied listener preservation and foreign health rejection.
- Allowed runtime DML verified with explicit-column zero-row statements and
  rollback-only savepoints; no data/defaults/sequence values generated. Denied
  append-only UPDATE/DELETE, catalog/inventory modification, user-role field
  modification, persistent/TEMP/schema DDL and SET ROLE owner. Ownership and
  non-elevated flags verified by catalog queries.
- Django check: no issues. Migration drift: no changes detected.
- Genuine Chrome, 390px: normal login HTTP 200, stylesheet HTTP 200, username,
  password and CSRF form present; RTL, no overflow, no fatal JS error. No login
  POST. Browser probe excludes only optional favicon responses from required
  asset checks; application/static checks remain explicit.
- Protected reports: `D:\SalesAI-Demo\sales_ai_copilot\reports\` contains
  `provision-journal.json`, `infrastructure-validation.json`,
  `browser-validation.json`, `final-preservation.json`, and
  `01-normal-login-390.png`.
- No full application suite run. Successful TEST-account login and complete
  journey cannot be exercised before B2 accounts/scenarios exist.

Production canonical table/financial/schema/sequence evidence is unchanged;
production remains at 49 migrations. Its container ID/start time/mounts and all
preserved preview credential hashes are unchanged. Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` and unrelated DEMO-02
planning are preserved. No staging, commit or push.

## B2 prerequisites

Owner approval of B1, then explicit synthetic fixture/account manifest and
controlled reset design. Preserve SP001 and the approved five scenario codes
without importing production business rows, password hashes or credentials.
Fixtures need today's Demo dates, genuine eligible recommended/ordinary products,
whole-TOMAN prices and no-sale/retained-Draft/submission paths. Reset must be
explicitly confirmed and identity-guarded. No B2 action is included here.
