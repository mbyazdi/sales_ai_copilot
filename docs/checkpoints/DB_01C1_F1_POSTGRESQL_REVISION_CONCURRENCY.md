# DB-01C1-F1 — PostgreSQL revision concurrency correction

Date: 2026-10-08. Scope: conditional request revision UPDATE and permanent
PostgreSQL regressions only. No model fields, migrations, APIs or UI changed.

## Root cause and correction

RequestQuerySet.update previously added a Visit join to its caller's query.
Django compiled UPDATE with an outer id IN (joined SELECT), leaving revision and
status predicates inside the statement-snapshot selection. At READ COMMITTED,
two waiting writers could both update the selected ID after the row changed.

The corrected UPDATE has direct target-row DRAFT and revision predicates. The
revision is compared with a correlated scalar selection retaining the original
caller filters/expected revision, including ownership joins. Visit eligibility
uses an open-Visit ID subquery, without adding an outer join. This also protects
joined caller scopes; simply removing the internal Visit join would not suffice.

```sql
UPDATE sales_requests_salesrequest AS target
SET revision = target.revision + 1
WHERE target.status = 'DRAFT'
  AND target.revision = (
      SELECT selected.revision
      FROM sales_requests_salesrequest AS selected
      -- Original caller conditions/ownership joins retained here.
      WHERE selected.id = target.id AND selected.revision = :expected
      LIMIT 1
  )
  AND target.visit_id IN (SELECT id FROM visits_visit WHERE status IN ('PLANNED', 'IN_PROGRESS'));
```

PostgreSQL rechecks the outer predicates against a concurrently updated target
row: the loser matches zero rows. Zero remains the existing conflict signal; no
new API/exception contract, automatic retry, Python lock or SQLite locking
dependency is introduced. Existing submitted/closed checks, allowed update fields,
and all other GuardedModel/AppendOnlyModel/queryset guards remain unchanged.

## Permanent tests and executed validation

apps/sales_requests/tests_revision_concurrency.py uses TransactionTestCase and
separate PostgreSQL connections at READ COMMITTED. Test coordination holds a row
lock until pg_stat_activity confirms both actual UPDATEs are waiting; it is not
implementation concurrency control. The PostgreSQL-only cases are skipped on
other backends.

- Before correction: deterministic regression failed with [1, 1], reproducing
  the original defect. Its isolated database was dropped.
- After correction: 74 focused tests passed (46 existing model, 23 existing receipt,
  5 new PostgreSQL regressions). Both plain and joined-scope races yield [0, 1]
  and final revision 1; stale updates yield 0; successive revisions reach 2.
- An additional submitted-state race passed separately: a waiting revision UPDATE
  cannot modify a row submitted before its lock is released. Complete submitted
  fields remain unchanged. No successful suite was rerun for this added case.
- Total successful focused coverage: 75 distinct tests, zero failures/errors/skips.
- Existing normal-ORM submitted, line snapshot, append-only feedback/receipt and
  partial-save protections passed; historical receipts remain valid after revisions.
- All three unique PostgreSQL test databases were created/dropped. Production
  connections were read-only; no production test data or full suite was used.
- Read-only production reconciliation retained all 2396 imported rows, original
  financial totals, framework metadata, empty sessions and empty foundation tables.

Protected ignored logs and SQL evidence:
venv/db01c1-f1-artifacts/20261008T143412Z/.

## Limits and delivery safety

Mutation services must still provide the expected revision, fresh authorization
and required IN_PROGRESS validation. This foundation retains PLANNED/IN_PROGRESS
metadata editability. Concurrent changes to related Visit state remain a separate
transaction-coordination responsibility; the request-row CAS does not claim to
lock unrelated Visit rows.

Other DB-01C1 findings (Product Detail JSONB component order, invalid test fixture
lengths and runtime privilege reduction) remain outside F1. No cutover.

Original SQLite SHA256 remains
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15.
Original stash remains 2dac7bdc26f07f611f471564476ceaa52ec367cc.
All pre-existing Stage 3/DB-01A work is preserved. Nothing staged/committed/pushed.

Reference: [PostgreSQL READ COMMITTED](https://www.postgresql.org/docs/17/transaction-iso.html#XACT-READ-COMMITTED).
