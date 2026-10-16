# Stage 3H4-B1 — Demo-only cross-process maintenance gate

2026-10-16. Baseline `fast-track`, V3.0.22,
`8bdb2ca6150a27d217eade7bfce8dff3768a4694`. Isolated validation only; owner review
pending. No persistent installation, restart, Prepare Day executor or journal.

## Architecture and lifecycle

The previous generation middleware checked a protected file once, without
retaining admission. It could reject new requests but could not drain admitted
requests. The new outermost Demo middleware starts a PostgreSQL atomic transaction
before all Django middleware, acquires shared transaction advisory admission on
the SAME connection as the business writes, then validates live DB endpoint,
database/OID/marker, runtime privileges, control identity, generation and state.
READ COMMITTED and one database with DB-backed sessions are required.

Admission remains held through authentication, CSRF, views, nested domain
transactions, template rendering and SessionMiddleware's response save. All
Django requests participate, including GETs that might persist session state.
Static files and the launcher's infrastructure health/stop surface perform no
business DB writes and remain outside Django admission. No route-name exception
can exempt a business API. Existing domain authorization/UUID/CAS/receipts and
submission replay remain unchanged. Production/default settings do not install
this middleware; SQLite behavior is unchanged.

`sales_ai_demo_control.admission` is a versioned singleton outside public/domain
tables. It binds generation UUID, DB OID, ACTIVE/PENDING state, operation UUID
and owning backend PID. Schema/table ownership stays with the independent Demo
owner; runtime receives USAGE/SELECT only. Both table and column mutation grants
are rejected. Runtime cannot announce maintenance, clear PENDING or perform DDL.

The maintenance owner commits PENDING on its verified connection before waiting
for exclusive admission. New shared attempts are nonblocking and must recheck
state after locking; they cannot reach business writes after PENDING commits.
Already-admitted transactions drain before the exclusive lock can be acquired.
The same live owner connection must then revalidate ownership, identity and
generation. Clean exit returns ACTIVE in the exclusive transaction; no new
admission can overlap its protected changes. There is no process-local lock,
filesystem-only fence, separate lock connection or executor-only advisory lock.

Maintenance announcement uses a conditional UPDATE, so competing owners cannot
both acquire the singleton. The committed pending state prevents an endless
stream of new business admissions while the owner waits. Timeouts stop the
attempt; they never grant exclusive access early or automatically retry.

## Failure boundaries

- Business exceptions, HTTP error responses and DB timeouts roll back the outer
  transaction, including session saves. Connection loss/worker termination keeps
  the database lock until PostgreSQL rolls back that SAME connection.
- Connection replacement during an admitted request fails closed. Advisory locks
  cannot be released by ordinary nested commits; they last through the outer
  transaction. Connection reuse starts a fresh admitted transaction per request.
- Streaming responses and newly registered on_commit callbacks fail closed before
  commit: their deferred work would fall outside this transaction. The current
  app has no such paths. Future use requires separate architecture review.
- A maintenance timeout, exception or owner crash leaves durable PENDING, even
  after the exclusive lock is released by rollback/disconnection. No automatic
  takeover, lease expiry, recovery, generation switch or state repair exists.
- Loss of the HTTP response after a successful DB commit remains an uncertain
  client outcome: retain the existing UUID/payload and use existing recovery.
  Never infer rollback from a network timeout or automatically repeat POST.

## Implementation and deployment boundary

New source: `scripts/demo/maintenance_gate.py` and
`scripts/demo/tests_maintenance_gate.py`. Demo-only installation hooks in
`generation.py`; SELECT-only startup validation in `demo.py`. The existing
`verify_generation_postgres.py` runner explicitly installs the gate only in its
UUID-named disposable database with exact OID/marker/endpoint/independent role
checks. `--maintenance-gate` includes the new tests. There is no Django migration.

**NOT DEPLOYED.** Persistent Demo still has no gate objects; its old listener is
untouched and must not be considered gate-protected. A new startup with this
source fails closed until separately approved installation and verified rollout
to every Demo worker. Ordinary startup never installs objects or changes grants.
Fresh-install documentation now explicitly records this additional prerequisite.
Original PostgreSQL remains blocked under the existing V3.0.22 deployment policy.
No persistent gate installer or crash-recovery operator tool is provided here.
Prepare Day executor/journal work may resume only after review of this foundation;
it must independently verify gate deployment, all-worker coverage and its own
intent, date, transaction, journal and reconciliation requirements.

## Focused evidence

The first 43-test run found one response-code regression: the new outer gate
masked the existing generation uncertainty code. Corrected the gate to preserve
`DEMO_MAINTENANCE_UNCERTAIN`; no existing test expectation was weakened.

- 45/45 focused PostgreSQL tests passed: 35 existing real-session generation,
  Feedback/Basket/Submit/Completion, security/reference-lock/concurrency tests plus
  10 new gate tests. Evidence: protected `reports/b2b3-e669eb8899de4b429c4a9b880f1c446c`.
- Final affected selection: 18/18 passed after additional setup guards, including
  12 gate tests and six lifecycle/CSRF/generation regressions. Evidence:
  `reports/b2b3-844c95f6c44441c7b6a1123e82045b1c`.
- One additional real Start Visit race test passed, exercising success and failed
  response subcases in separate runtime/maintenance processes. The Visit and both
  snapshots remain invisible/uncommitted while the response is paused; exclusive
  maintenance sees all committed effects together, or none after rollback.
  Evidence: `reports/b2b3-9d6fa27aeb894c2987e90d28438a9ff1`.
- Total distinct focused methods validated: 48 (not a claimed single 48-test run).
  Tests cover real login/DB sessions/CSRF, pending rejection across the enumerated
  unsafe API/admin/auth routes, separate-process admission and drain, multiple
  workers, request worker termination, owner termination, lock timeout, SQL
  timeout after an uncommitted insert, the lock-before-validation race, missing
  objects, wrong identity and prohibited table/column/DDL privileges.
- Each successful runner reports zero failures/errors/skips, clean Django check,
  no migration drift, exact 50 migrations, verified disposable DB/role cleanup
  and equal before/after persistent inventories. No full suite or JS changes.

Reports are under `D:\SalesAI-Demo\sales_ai_copilot\reports\`, never in Git.
No production or persistent Demo writes/DDL, C0005 completion, reset, Prepare Day,
generation/session/credential change or existing preview interruption occurred.
Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` preserved. No staging/commit/push.
