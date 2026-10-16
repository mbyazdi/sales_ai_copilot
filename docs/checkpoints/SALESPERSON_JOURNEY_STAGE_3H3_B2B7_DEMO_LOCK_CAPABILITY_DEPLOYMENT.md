# Stage 3H3-B2-B7 — Controlled Demo lock capability deployment

2026-10-15. Baseline V3.0.21 / `1a96e92b`. Owner authorized B6 capabilities
only in `sales-ai-demo-postgres`, `127.0.0.1:5433`, `sales_ai_demo_db`.

## Identity, preflight and deployment

Verified container/image/volume, database OID 16384 and owner-controlled marker,
generation `6ae05c63-b9a3-4e85-a469-4643d3f76a27`, independent credentials,
owner/runtime roles, all 50 migrations and SYNTHETIC_DEMO_V1 fixture definition
SHA256 `c93994113eb2ac22275d91a21aff624d648376f2ed57cf714c4cc27e772730ef`.
No active transaction, existing capability schema or capability owner was found.
Only the verified Demo listener was stopped; installation required no remaining
Demo connections. Other containers/previews were not stopped or changed.

Deployed unchanged B6 `REFERENCE_LOCKS_V1`; canonical LF SQL SHA256:
`7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.

- Private schema `sales_ai_locks`, OID 24896.
- `lock_feedback_references(bigint,bigint)`, OID 24897.
- `lock_submission_references(bigint,bigint[])`, OID 24898.
- Owner `sales_ai_demo_lock_owner`, OID 24895: NOLOGIN, NOINHERIT, no superuser,
  CREATEDB, CREATEROLE, replication, BYPASSRLS, role memberships or public ownership.
- Owner gets public schema USAGE and SELECT only on required identity/link columns:
  Customer(id,grade_id), Grade(id), Product(id), Inventory(id,product_id),
  Recommendation(id,customer_id,product_id); UPDATE(id) only on these five tables.
- Runtime gets private schema USAGE and the two exact EXECUTE grants, without grant
  option. No PUBLIC EXECUTE or runtime direct reference UPDATE. Existing public
  relation/column ACLs, including grantors/options, were preserved.
- Functions retain SECURITY DEFINER, fixed `pg_catalog, pg_temp` search_path,
  row_security=on, input bounds, lock-only bodies and no privileged business output.

Lock order/lifetime is unchanged: Feedback Recommendation → Product; Submit
Customer → Grade → Products by PK → Inventory by product ID, retained until the
outer transaction commits/rolls back. Operational Visit/Request/Line locks,
authoritative rereads, revision, UUID, replay and authorization remain unchanged.

## Startup and recovery

Explicit installer: `scripts/demo/deploy_lock_capabilities.py`. First installation
requires `install --approve-reference-locks-v1`; `preflight`, `recheck` and repeat
installation perform read-only inspection. No ordinary startup installs/repairs.
Protected registry: `D:\SalesAI-Demo\sales_ai_copilot\lock-capabilities.json`
and `.sha256`. Startup and each new Demo runtime Django connection compare exact
registry identity, source/version, object OIDs, bodies, owners, signatures and ACLs.
Missing/drifting objects fail closed. Production/other preview settings unchanged.

Recovery evidence was recorded **before DDL**. Role/grant/function installation was
one transaction; commit, protected registry publication and application restart
were separate durable journal stages, not a claimed atomic promotion. Partial or
uncertain state requires inspection, never automatic repair/destructive retry.
Rollback plan retains all data: exact-function drops without CASCADE, empty private
schema removal, only new owner's scoped grant revocation and dependency-checked
role removal, registry archival. Separate approval is required. The guarded
launcher stays blocked without capabilities; no automatic unlocked fallback.

Protected deployment evidence and recovery plan:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b7-dfded36e40314edc9e6d657d87d0ccae\`.
Final journal: `COMPLETE_RESTARTED_VERIFIED`.

## Validation

- Full focused B3/B6 plus B7 deployment selection: **34 passed**, 0 failures/errors/
  skips, 90.081s. Newly added launcher missing-registry test: **1 passed**.
  Preliminary two B7 tests also passed before deployment.
- Each disposable database/role was verified and removed. Real sessions, CSRF,
  stale sessions/documents/pending commands, authorization, UUID conflicts/replay,
  rollback, lock retention, reference-change races, Submit vs basket/completion
  and concurrent submissions passed under actual least-privilege runtime grants.
- Real persistent runtime service probes: LATER Feedback, recommended Add, Submit,
  Completion, acknowledgement and exact replays succeeded inside forced rollback.
  Explicit transaction-local PK allocation prevented nontransactional sequence
  advancement; this mechanism was first tested in disposable PostgreSQL.
- Direct reference/price UPDATE, append-only UPDATE/DELETE, DDL, role assumption
  and unauthorized function execution were denied (42501). Hostile search_path
  did not alter function resolution or caller identity. A competing owner
  connection confirmed reference locks were retained (55P03 NOWAIT).
- Runtime check and migration drift clean; SQL fingerprint unchanged. Repeat
  install returned `READ_ONLY_VERIFIED_NO_OP`, preserving object identities/ACLs.
- Controlled application restart succeeded at `http://localhost:8900`.
  Login and generation script GETs returned 200; unauthenticated Daily Plan
  redirected to normal login. No login/session write was performed on persistent
  Demo during B7. Health reports the deployed capability version/SHA.
- Relevant business UI JS: 80 passed; generation client: 7 passed (**87 total**).
  Python syntax and whitespace checks passed. No full regression suite.

Runtime rollback/negative-security evidence:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b7-runtime-ee4d4164f6ab418e9bfc5789c12f8651\`.
Disposable full selection:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-c6a24570a3114c5c9cc66cb955b361b0\`.
Additional missing-registry test:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-822d1234d5974060b70bdf682bbacf3b\`.

## Preservation and limits

All 40 public table counts/digests and full operator-visible sequence values plus
is_called flags were identical before/after deployment, rollback probes and
restart. Fixtures, sessions, credentials, profile and active generation unchanged.
Production read-only reconciliation was identical. No migrations, business commits,
reset, preparation, candidate activation or generation switch occurred.
SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc`; index empty.
Existing Stage 3H3 work/unrelated planning preserved; nothing committed/pushed.

No B7 blocker remains. Production still lacks capabilities and requires separate
approval/deployment. Capability objects are outside Django migration history;
future Demo rebuilds/generations need separately verified explicit installation
and registry publication before startup. Reset/Prepare Day/promotion remain
unimplemented/unexecuted. B5 operator lock ordering limitations remain unchanged.
