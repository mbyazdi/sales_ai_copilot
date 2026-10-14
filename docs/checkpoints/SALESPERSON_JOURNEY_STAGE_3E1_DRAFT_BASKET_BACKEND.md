# Stage 3E1 — Draft Sales Request and basket backend

2026-10-09; owner approved for V3.0.18 closeout on 2026-10-15. Baseline V3.0.17
`6af76c14cd5ffd9fe3528be1093317a8d7cacfd7`, fast-track. Governing contract:
[Stage 3](SALESPERSON_JOURNEY_STAGE_3_IMPLEMENTATION_CONTRACT.md).

## Boundary and persistence

Reuse existing SalesRequest, SalesRequestLine, MutationReceipt and feedback event
models unchanged; no schema/migration. Only the first successful explicit Add
creates a DRAFT. One lifecycle per Visit; no submitted state, numbering,
acknowledgement, completion, follow-up, legacy PURCHASED or Sale/SaleItem writes.
Reads never create, repair or reprice stored records. UI is unchanged.

Selected lines represent current contents. Removal retains the line, quantity,
quotes and lineage with `is_selected=False` and `removed_at`; re-add creates a
fresh line. Recommended add/removal append ADDED_TO_REQUEST/REMOVED_FROM_REQUEST
linked to the exact line. Quantity changes do not append acceptance; ordinary
products never create feedback. Existing rejection history is retained; the
existing feedback service continues to reject decisions on selected products.

## Frozen API contract

All endpoints below have `/api/sales-requests/v1/` prefix. SessionAuthentication
only; authenticated, current salesperson/profile/assignment and matching Visit
customer required. Cache-Control is `no-store, private`.

| Method / suffix | Purpose |
| --- | --- |
| GET/HEAD `visits/<visit_id>/basket/` | Existing/empty selection, revision, saved quotes/totals and current validity. |
| GET/HEAD `visits/<visit_id>/basket/quote/` | Resulting basket quote after a proposed product/absolute quantity. |
| POST `visits/<visit_id>/lines/` | Explicit Add, including transactional first Draft. |
| PATCH `requests/<request_id>/lines/<line_id>/` | Absolute selected-line quantity. |
| DELETE `requests/<request_id>/lines/<line_id>/` | Retained semantic removal; JSON command body. |
| GET/HEAD `visits/<visit_id>/commands/<command_uuid>/` | Authorized historical receipt lookup; 404 means no successful receipt is recorded. |

GET requires `customer_code`; candidate basket quote also requires `product_id`
and positive `quantity`. Existing Stage 3C2 `visits/<visit_id>/quote/?items=...`
remains unchanged: its per-product fingerprints are not a resulting-basket
acceptance fingerprint. Obtain the basket fingerprint from the new quote read.

Every mutation requires `customer_code`, `catalog_context`, stable `command_uuid`
and explicit `expected_request_revision` (JSON null means no request expected).
Add requires `product_id`, `quantity`, `accepted_quote_fingerprint`; PATCH requires
quantity/fingerprint. DELETE needs neither price acceptance nor quantity.
Unknown fields, client monetary values, booleans/fractional/string quantities,
malformed UUIDs and out-of-range values are rejected. Positive quantities are
bounded by the existing line representation; selected baskets are bounded to
50 products, consistent with current quote batches.

Fresh mutations require IN_PROGRESS and DRAFT. New Add validates the current
saved signed recommendation context and automatically determines recommended
versus ordinary source, rather than trusting a priority flag. Existing-line edits
and removal validate the signed actor/customer/Visit binding without expiry or
live-recommendation validation, as the contract requires; captured lineage is
not rewritten or stranded by deactivation. Tokens never grant authorization.
PLANNED and closed Visits allow authorized inspection/preparation only;
`editable=false` is distinct from commercially valid pricing.

Success: Add 201; PATCH/DELETE 200. Header `Idempotent-Replayed: true|false`.
The canonical body contains customer/Visit, request id/status/revision, currency,
editable, selected lines, item_count, total_units, saved_totals, current_quote and
quote_changed. Money is whole-TOMAN decimal strings. Current validity can differ
from saved quotes; GET does not persist these differences. Receipt results are
historical: replay can return an older revision; fetch current basket separately.

Example Add command (fixture identities; fingerprint/UUID must come from the caller):

```json
{
  "customer_code": "C0003", "product_id": 1, "quantity": 3,
  "command_uuid": "12345678-1234-4234-8234-123456789012",
  "expected_request_revision": null,
  "catalog_context": "<signed selling context>",
  "accepted_quote_fingerprint": "<64-character resulting-basket SHA256>"
}
```

Illustrative successful response excerpt for explicit base 105 / grade A / 3 PCS
(not a production price claim; real responses include line snapshots/current quote):

```json
{
  "version": 1,
  "request": {"id": 1, "status": "DRAFT", "revision": 1},
  "currency": "TOMAN", "editable": true,
  "item_count": 1, "total_units": 3,
  "saved_totals": {"base": "315", "discount": "30", "final": "285"},
  "quote_changed": false
}
```

Errors: 400 INVALID_INPUT; 403 ACCESS_DENIED/CSRF; 404 NOT_FOUND; 409
VISIT_NOT_ACTIVE, REQUEST_NOT_DRAFT, REVISION_CONFLICT, COMMAND_CONFLICT,
PRODUCT_ALREADY_SELECTED, LINE_NOT_SELECTED, CATALOG_CONTEXT_UNAVAILABLE,
PRICE_CHANGED, PRICE_UNAVAILABLE, PRICE_CONFIGURATION_ERROR, INACTIVE_PRODUCT,
INVENTORY_UNKNOWN, OUT_OF_STOCK, INSUFFICIENT_STOCK, BASKET_LIMIT or
REQUEST_AMOUNT_OUT_OF_RANGE. Persian details accompany API business errors.

## Pricing, transactions and recovery

Pricing Core remains authoritative: whole explicit TOMAN base, A=10%, B=5%,
other=0%, ROUND_HALF_UP once at unit level. Totals sum unit-derived selected line
amounts, never reapply discounts. Stage 1 `discount_amount` holds unit discount;
pricing_snapshot separately holds line discount and policy/source versions.
Product identity/unit, immutable selection lineage, observed eligibility and
accepted quotes are captured. Draft pricing/eligibility may refresh; lineage does
not. All resulting selected quotes are revalidated on Add/PATCH; any changed
commercial fingerprint conflicts before writes. This avoids silently repricing
another selected product. No tax, promotions or historical-price fallback.

Fingerprint binds customer, Visit, quantities, full Pricing Core quotes (grade,
price/source/version/calculation policy), not timestamps or volatile inventory.
Inventory separately revalidates `max(available-reserved,0)`; aggregate selected
quantity per product must fit observed stock. No reservation/deduction/allocation
guarantee. Zero and unknown stock/missing price remain separate; explicit price
zero is valid configuration. Removal stays possible with unavailable/overflowing
current quotes; it retains saved remaining quotes/totals and reports current
invalidity instead of substituting zero. Incomplete saved quotes yield null totals.

Atomic lock order is Visit then existing Request, matching Feedback API. Acquire
the expected DRAFT revision by the existing target-row conditional UPDATE with
IN_PROGRESS predicate before any line/event changes; preserve the acquired
revision on header save. First Add creates revision 0 and acquires revision 1.
All lines, totals, events, revision and successful receipt commit together.
Failure rolls back everything; no successful receipt is recorded. Visit+UUID
uniqueness backs exact canonical replay; changed intent/operation/targets conflicts.
Replay rechecks access but does not reprice or mutate, even after lifecycle or
context changes. No process locks, automatic POST retry or SQLite lock assumption.

Reads are observations, not locks/reservations or permission to mutate. A header
revision/status recheck detects mixed line/header reads and returns REVISION_CONFLICT
without automatic retry or writes. Concurrent
changes are handled by expected revision and complete quote acceptance at the
mutation boundary. After uncertain transport failure, inspect the authorized
receipt/current basket; any explicit retry resends the original UUID/payload.
No client should infer failure merely from a missing receipt while a command may
still be running.

## Validation and preservation

- Focused PostgreSQL run: 90/90 passed (34 basket plus 56 existing feedback,
  receipt and revision guard tests). Actual separate-connection races prove one
  first-Draft winner, exact duplicate replay, conflicting UUID denial and one
  winner for two quantity writers expecting the same revision.
- Final affected basket run: 34 passed, one new 50-line fixture setup error
  (omitted explicit currency). Corrected fixture; targeted rerun 1/1 passed.
  All 35 basket tests passed across the final run and affected rerun.
- Final zero-write read-consistency refinement: 5/5 affected tests passed,
  including an interleaved header/line revision change. The current basket suite
  contains 36 tests; all passed across the focused runs and targeted reruns.
- Initial new serializer malformed-input error was corrected with a structured
  non_field_errors response and covered by subsequent passing tests.
- Basket inspection: exactly 9 queries for 1, 2 and 50 selected products; no
  per-product read queries. Mutation writes/model validation scale with selected
  lines, bounded to 50; current pricing/stock lookups remain batched.
- Django system checks passed; migration drift: no changes (49 unchanged
  migrations). git diff --check passed. No JS changes/tests or full suite needed.
- Every isolated test database was removed; enforced runner blocks SQLite and
  non-test Django writes. Canonical production before/after reconciliation passed.
- Original SQLite SHA256 remains
  `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
  original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` unchanged.

Deferred: operational UI, Review/Submit/Success, acknowledgement, prepared message,
actual messaging, stock allocation, SQLite concurrency validation and full suite.
No staging, commit or push in Stage 3E1.
