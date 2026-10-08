# DB-01C1 — final PostgreSQL compatibility gate

Date: 2026-10-08. Status: PASSED; runtime cutover is not performed/authorized.
F1/F2 fixes are approved. Branch fast-track, committed HEAD
8fceda04dbafba6cb4cfb66a88653169a2a4dd98; existing uncommitted work retained.

## Exact selection and single execution

The original 19 module labels and all three original PostgreSQL native probes
were retained, plus apps.sales_requests.tests_revision_concurrency. F2 adds four
regressions within the existing Product Detail module. Thus original 341 + six
permanent F1 + four F2 tests = 351. The selected suite was executed exactly once.

- apps.customers.tests_productization
- apps.customers.tests_salesperson_journey
- apps.customers.tests_guided_catalog
- apps.customers.tests_recommendation_presentation
- apps.products.tests_catalog
- apps.products.tests_commercial_brief
- apps.products.tests_pricing
- apps.recommendations.tests
- apps.visits.tests
- apps.visits.tests_authorization
- apps.visits.tests_workspace
- apps.visits.tests_recommendation_outcomes
- apps.visits.tests_follow_up_workspace
- apps.visits.tests_continuity
- apps.visits.tests_completion_review
- apps.sales_requests.tests_models
- apps.sales_requests.tests_mutation_receipts
- apps.sales_requests.tests_migrations
- apps.sales_requests.tests_mutation_receipt_migrations
- apps.sales_requests.tests_revision_concurrency
- Original native probes: atomic rollback, simultaneous revision compare-and-set,
  select_for_update transaction requirement.

Result: 351 passed, 0 failures, 0 errors, 0 skipped, 63.463 seconds.
All original three failures/two errors are explicitly recorded as passing.
No newly discovered failures. Six permanent concurrency tests and four ordering/
JSONB regressions passed. No source fix or test-suite retry occurred during gate.

Isolated database: test_db01c1_gate_20261008T152355_54481f; created/dropped once. Production connections were
forced read-only, SQLite test connections prohibited, and maintenance DDL restricted
 to that exact test database. No migrations were run against existing databases.

## Checks and production reconciliation

- PostgreSQL Django check: no issues; migration drift: no changes detected.
- 49 applied migrations, 40 tables, 35 content types, 140 permissions retained.
- All 2396 imported rows matched their transfer row/PK digests before and after.
- 30 Customers/Customer360 rows, 14 products, 457 historical Sales, 1154 SaleItems,
  453 recommendations (49 active), 36 Visits and their relationships preserved.
- Catalog smoke: C0003 / planned Visit 32, 14 products, three priorities; search,
  signed-context resume and tamper denial passed without writes/regeneration.
- All active saved recommendation customer/ID/product/rank sequences matched the
  frozen SQLite snapshot. Category ordering and association lift/confidence/ID
  ordering matched for this dataset; no general collation equivalence is claimed.
- Sale headers, SaleItem totals and Customer360 sales each 425150.00; discounts
  5790.00; legacy outcome amounts 20000.00. Actual stored units remain unchanged.
- Empty sessions and six foundation tables retained; approved legacy SalesOutcome
  1 customer mismatch preserved. No seed, recalculation or data transfer.
- git diff --check is checked during final delivery.

## Evidence and remaining cutover requirements

Protected ignored evidence: D:/py project/sales_ai_copilot/venv/db01c1-gate-artifacts/20261008T152355Z.
Includes full test IDs/results, sanitized log, production smoke/reconciliation,
runner and artifact checksums. Gate status is evidence of compatibility, not a
production privilege/security or runtime-switch approval.

Current database role remains overprivileged. Implement the reviewed separate
owner/migration/runtime identities and runtime grant allowlist before cutover.
Any active database configuration switch and runtime/browser validation needs its
own authorized cutover task; SQLite remains the default meanwhile.

Source SQLite SHA256 before/after:
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15.
Original stash: 2dac7bdc26f07f611f471564476ceaa52ec367cc, unchanged.
No application/schema changes, staging, commit or push during this gate.
