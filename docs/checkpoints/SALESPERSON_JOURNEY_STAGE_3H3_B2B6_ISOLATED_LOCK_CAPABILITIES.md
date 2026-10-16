# Stage 3H3-B2-B6 — Isolated PostgreSQL lock capabilities

2026-10-15. V3.0.21 / `1a96e92b938a5f64d586249245734f8e5d083b1e`.
Owner-approved A+C implemented and validated in disposable PostgreSQL only.
No persistent deployment, grant change, migration, reset, generation activation
or preparation. Existing Stage 3H3 work and unrelated planning are preserved.

## Implementation and exact boundaries

- `apps/core/reference_locks.py`: parameterized Django adapter, positive bigint
  identities, bounded 50-product list, outer atomic transaction required.
  PostgreSQL always calls the capabilities; missing functions/errors propagate
  and roll back. SQLite retains its existing no-row-lock/CAS behavior.
- `apps/core/sql/reference_locks_v1.sql`: two fixed, void-returning functions,
  `lock_feedback_references(customer_id, recommendation_id)` and
  `lock_submission_references(customer_id, product_ids)`, in `sales_ai_locks`.
  Only identity/link reads and row locks; no business DML, dynamic SQL, prices,
  commit, outbound action or business-data output.
- Feedback replaces only protected-reference lock acquisition, then rereads the
  recommendation/Product and performs the existing active/context/selection checks.
- Submit replaces only `_lock_commercial` reference acquisition, then rereads
  Customer and runs existing Pricing Core, inventory/review/fingerprint checks.
- Operational Visit/Request/Line locks, guarded saves, CAS, authorization, CSRF,
  generation validation, event/receipt/submission UUID semantics and exact replay
  remain unchanged. Replay still precedes reference locking; missing capabilities
  do not prevent retrieval of an already committed successful submission.

Lock strength stays FOR UPDATE, in explicit order:

1. Feedback: Visit -> optional Request -> Recommendation -> Product.
2. Submit: Visit -> Request -> selected Lines -> Customer -> current Grade ->
   Products by ascending PK -> Inventory by ascending product ID.

The SQL independently sorts/deduplicates bounded inputs. Missing inventory remains
unknown, not fabricated. Locks survive the function return until the caller's
outer commit/rollback. No stock reservation/deduction or price-row lock is added.
Current base prices remain versioned point-in-time reads; changed terms are never
silently accepted. Existing grade/product/inventory protection lasts through commit.

## Security and reproducible installation

`scripts/demo/lock_capabilities.py` installs only into a verified, UUID-named B3
disposable DB on the independent Demo endpoint. It checks DB OID, marker, operator,
client endpoint and a new unprivileged NOLOGIN role; refuses persistent targets or
an existing schema. Installation is one transaction, without a PUBLIC EXECUTE
window. The static SQL has REFERENCE_LOCKS_V1 comments; protected receipts include
its SHA256, exact functions, DB/OID and owner.

Each run uses a different `sa_lock_b6_<uuid>` role: NOLOGIN, NOSUPERUSER,
NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS, no role memberships.
It owns only the capability schema/functions, not reference tables. Its SELECT
columns are exactly:

| Reference table | SELECT columns | UPDATE column |
| --- | --- | --- |
| customers_customer | id, grade_id | id |
| customers_customergrade | id | id |
| products_product | id | id |
| inventory_inventory | id, product_id | id |
| recommendations_customerrecommendation | id, customer_id, product_id | id |

These UPDATE privileges belong solely to the non-assumable capability owner,
never runtime. Runtime retains its original table grants plus schema USAGE and
EXECUTE on the two signatures. PUBLIC EXECUTE is revoked. Functions fix
`search_path=pg_catalog,pg_temp`, fully qualify references, set row_security=on,
are VOLATILE/PARALLEL UNSAFE, and reject null/nonpositive identities, null elements,
multidimensional arrays and lists over 50. They do not replace application auth.

No persistent provisioning hook or deployment executor was enabled. Original
50 Django migrations remain unchanged. SQL is a separately versioned infrastructure
artifact, not a claim that the Django graph installs capabilities. A future
deployment needs explicit role/schema/grant approval, capability fingerprint and
ACL validation, and a maintenance/startup readiness plan. Current persistent
Demo/production are not ready to serve the new PostgreSQL mutation code until
that installation; missing functions fail closed. Existing processes were untouched.

## Focused evidence

`scripts/demo/verify_generation_postgres.py --lock-capabilities` reuses B3 isolation,
normal Django password login/DB sessions/CSRF, independent synthetic fixtures and
real least-privilege runtime credentials. Every connection is pinned to the exact
test name/endpoint/OID/marker. Additional B6 tests live in
`scripts/demo/tests_lock_capabilities.py`. All added writes are disposable-only.

- 32 distinct PostgreSQL test methods passed across focused selections, no skips.
  Includes all 18 B3 methods (800 invalid-proof and 316 stale-session method/route
  rejections), previously blocked Feedback/Submit and submitted completion/ack.
- First run: 27 actual methods passed, then one harness discovery error attempted
  to call the `test_profile` data attribute. Corrected only discovery to require a
  callable. Added/changed follow-up selection: 7/7; timeout/conflict selection:
  2/2; after narrowing owner SELECT columns: 4/4 Feedback/Submit/ACL/order checks.
  Successful unchanged selections were not rerun; no full suite.
- Independent PostgreSQL sessions observed real blockers via `pg_blocking_pids`:
  12 lock-lifetime cases across commit/rollback, plus staged checks proving
  Recommendation before Product, Customer before Grade, sorted Products before
  Inventory and sorted inventory locks. No sleep-only concurrency assertions.
- Recommendation/Product deactivation and Customer/Grade/Inventory changes made
  waiting HTTP mutations reread authoritative values and reject stale context or
  terms. No failed submission key/revision/snapshot was committed.
- Submit versus quantity edit and completion, concurrent identical Submit replay,
  conflicting valid intents, stale revisions, missing functions and actual lock
  timeout rollback passed. An explicit later retry can apply once; no auto-retry.
- Whole-TOMAN rounding, changed/fractional/missing price, zero/unknown/insufficient
  stock, immutable replay after capability removal, ordinary-product no-feedback
  behavior and separate acknowledgement semantics remain covered.
- Runtime direct reference UPDATE/DELETE, price modification, all seven append-only
  table UPDATE/DELETE, DDL/temp tables and SET ROLE are denied. Unauthorised function
  execution and PUBLIC EXECUTE are denied; exact owner SELECT/UPDATE columns checked
  with pg_catalog privilege predicates. Hostile search_path/shadow tables did not
  affect functions. Invalid SQL/adapter inputs left business state unchanged.
- Existing SQLite Feedback/Submission API regressions: 54 run, 53 passed, one
  expected PostgreSQL-only skip. Dedicated runner rejects every SQLite connection
  except its exact in-memory test names. Original SQLite was never opened by Django.
- Affected JS: 87/87 passed. Django checks clean; migration drift reports no changes.
  Python/JS syntax and whitespace checks pass. No JavaScript implementation changes.

Protected receipts, before/after reconciliations and cleanup evidence:

- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-b42ba5e16e494fbea78042302d4b6e0c\`
- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-f80ddc0bfdcb4ee89b8cbb0fe570ce26\`
- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-0a550c81f2cc4c51a0dff3d60fff910d\`
- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-07cf70cfe7b54af5960e74d889855638\`

## Preservation and next approval

All four disposable databases and their capability owners were removed after exact
identity verification. Persistent Demo/production tables, sequences/schema metadata,
credentials, fixtures, profile, generation and existing previews remain unchanged.
No persistent role grants, function installation, migrations, reset, redating,
candidate or generation switch occurred. Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index remains empty.
No staging, commit or push.

Remaining approval: isolated implementation review, then a separate controlled
deployment plan. No production privilege reduction/deployment is implicit. Existing
operator-loader ordering and legacy lifecycle limitations identified in B5 are
unchanged; do not claim universal deadlock freedom or warehouse allocation.
