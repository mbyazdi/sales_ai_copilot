# Stage 3H3-B2-B3 — Live generation safety verification

2026-10-15. fast-track / V3.0.21, `1a96e92b938a5f64d586249245734f8e5d083b1e`.
Generation fencing passed the tested negative paths. **Full B3 acceptance is
BLOCKED by existing Demo runtime locking privileges.** No reset, candidate,
promotion, Prepare Day, persistent migration, grant change or application fix.

## Isolation and repeatable verification

Added `scripts/demo/verify_generation_postgres.py` and
`scripts/demo/tests_generation_postgres.py`. The explicit runner verifies the
existing independent Demo container/endpoint before creating one UUID-named
disposable database on 127.0.0.1:5433, using only Demo operator credentials.
It applies the 50 migrations there, creates independent synthetic test accounts
and catalog fixtures, and reproduces B1 runtime grants in that database only.
No persistent user hashes or business records are copied. Secrets are not logged.

Connections are pinned before connecting to the exact test name, host, port and
allowed role. Actual database name, OID, owner-controlled marker, role and server
port are verified before application SQL. The generation registry/profile are
independent files inside the protected B3 report directory. Live Demo profile,
registry, keys, credentials and generation are never changed.

Requests use Django Client's full middleware chain with CSRF enforcement, real
database-backed sessions, ordinary password login and real PostgreSQL transactions
under `sales_ai_demo_runtime`. No force-login/authentication or memory sessions.
Each test transaction rolls back. Cleanup verifies exact OID/marker and absence
of active connections, drops only the test database, and verifies its removal.
No browser/TCP E2E test or persistent generation switch is claimed.

## Endpoint inventory and negative coverage

Runtime URL traversal recorded 158 routes: 15 non-admin routes and a conservative
143-route admin surface. Every explicit unsafe method is included, including
LoginView's inherited PUT handler. Admin coverage includes read-only handlers that
would reject POST even with valid generation proof; it is deliberately broader
than the set of admin writes permitted by model permissions/runtime grants.

| Surface | Unsafe methods / paths |
| --- | --- |
| Lifecycle | POST `/api/visits/v1/visits/{id}/start/`, `complete/`, `completion/` |
| Basket | POST `/api/sales-requests/v1/visits/{id}/lines/`; PATCH/DELETE `/api/sales-requests/v1/requests/{id}/lines/{line}/` |
| Feedback | POST `/api/recommendations/v1/visits/{id}/feedback/` |
| Submit | POST `/api/sales-requests/v1/visits/{id}/submit/` |
| Legacy outcomes/follow-up | POST `/api/visits/v1/outcomes/`, `/api/visits/v1/follow-ups/{id}/status/` |
| Staff tuning | POST `/api/recommendations/v1/tuning-suggestions/{id}/status/`, `apply/`, `rollback/` |
| AI command surface | POST `/api/ai/v1/sales-copilot/` (guard tested without calling the model) |
| Normal auth | POST/PUT `/accounts/login/`, POST `/accounts/logout/` |
| Django admin | Login/logout/password forms, model forms, changelists/actions and other resolved admin handlers |

Across 160 route/method combinations, five missing/empty/stale/unsigned/tampered
proof variants produced 800 HTTP 409 rejections. Real SQL capture found no
INSERT/UPDATE/DELETE/DDL, and all model row projections were identical afterward.
Valid CSRF did not override invalid generation. Two stale/unbound session
variants produced 316 HTTP 403 rejections with valid current document proof.
Normal `/accounts/login/` is intentionally the reauthentication exception;
credentials, CSRF and current proof are still required before binding the session.

Missing registry, uncertain maintenance, wrong generation, database, OID,
container and endpoint returned 503 before business operations. Only isolated
test registry/profile files were modified to simulate these states. An old pending
command proof failed even with a fresh valid login and previously successful UUID;
its original body was unchanged. Current-generation identical basket replay still
returned its frozen receipt. GET recovery did not write new evidence.

## Positive paths and limits

Passed: login/last_login/database session and generation binding; CSRF rejection;
normal and admin logout/session invalidation; stale-session reauthentication;
Start and legacy repeated-completion rejection; ordinary basket add/update/remove,
revision conflicts, changed-intent UUID conflict and exact replay; explicit
no-request completion/replay/recovery; retained-DRAFT completion preserving lines;
foreign salesperson and manager business authorization denial.

**Existing grant blockers, reproduced with B1-equivalent runtime privileges:**

- Feedback fails on `CustomerRecommendation.select_for_update().select_related(
  "product")` with PostgreSQL permission denied for
  `recommendations_customerrecommendation`.
- Submit fails on `Customer.objects.select_for_update()` in `_lock_commercial`
  with permission denied for `customers_customer`.
- Read-only inspection confirms the persistent Demo runtime has SELECT but no
  table/column UPDATE privileges on recommendations, customers, customer grades,
  products or inventory. PostgreSQL row-lock acquisition requires suitable UPDATE
  permission even when the business operation does not update those records.

Do not weaken locking or authorize broad writes to make the tests pass. A separate
approved task should review minimal Demo-only row-lock-compatible grants across
all joined/commercially locked tables, then retest feedback, submission and
submitted-request completion/acknowledgement. Their positive/replay paths remain
unverified under the current runtime role. No missing generation check was found
on the enumerated paths; these runtime permission failures prevent full approval.
Live candidate activation, in-flight transaction fencing and cross-process replay
remain outside this verification; promotion still requires quiescence and fencing.

## Exact validation and preservation

- Initial runner setup hit a test-harness lookup for a nonexistent session `id`;
  fixed the new runner to inspect column existence, matching B1. Test DB removed.
- First integration selection: 14 tests, 11 pass, 1 failure, 2 errors, 0 skips.
  The failure was a new test expecting anonymous Customer access to redirect;
  existing application correctly returns 403. Corrected only that test expectation.
  The two runtime grant errors above remain unresolved and are not hidden/skipped.
- Affected follow-up selection: 5/5 pass (corrected logout test plus four additional
  completion/auth probes). Across the 18 distinct test methods, 16 passed and
  two are blocked by grants. No full suite or repeat of successful selections.
- Affected JS: 87/87 pass; existing no-helper production/preview behavior and
  unchanged UUID/wire payload/proof retention remain covered.
- Django check clean; migration drift: no changes detected. Syntax and whitespace
  checks pass. No schema/migration source or application implementation changes.

Protected evidence includes `before.json`, `after.json`, `cleanup.json`,
`endpoints.json`, `results.json` and final preservation verification:

- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-a28c09121b1345b3b0e6adb4d8df7c6f\`
- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-b0af46e801bd4a30aba28b9ba96e518c\`

All disposable B3 databases were removed. Persistent Demo and production table
checksums, sequences and schema metadata match before/after; credentials, fixtures,
profiles, generation, original SQLite and unrelated planning hashes match. No
existing preview was stopped or reconfigured. SQLite remains unstaged, SHA256
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`; index remains empty.
No staging, commit or push. Stop for owner review; no reset/promotion approval.
