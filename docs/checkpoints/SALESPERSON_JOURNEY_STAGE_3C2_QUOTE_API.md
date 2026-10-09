# Stage 3C2 — read-only commercial quote API

2026-10-09; fast-track baseline `9a3e17053d9bb17341572fea95267e2eb19ac288`.
Authority: Stage 3 implementation contract and approved Stage 3C1 Pricing Core.
No pricing-policy ambiguity found. Pricing Core and its existing tests are preserved
byte-for-byte; this task adds only the quote read boundary and its focused tests.

## Frozen endpoint and inputs

`GET /api/sales-requests/v1/visits/<visit_id>/quote/`

Matches the Stage 3 contract's proposed Visit quote path. The sales_requests view
is a thin read adapter; `apps/products/quotes.py` owns product/pricing/inventory
composition and delegates every calculation/fingerprint to `DemoPriceProvider`.
No basket service, current-Draft lookup or mutation is introduced.

Required query parameters:

- `customer_code`: must match the owned Visit and current active assignment.
- `items`: URL-encoded JSON array of `{"product_id": 1, "quantity": 3}` objects.
  1–50 unique active catalog product IDs, absolute positive integer quantities.
  No duplicate product aggregation, float/bool/string coercion, client prices or
  extra per-item fields. Quantity range 1–2,147,483,647 matches the existing
  PositiveIntegerField line representation; product IDs reuse the catalog's
  bounded identifier range. JSON input is limited to 10,000 characters.

GET/HEAD/OPTIONS only; authenticated unsupported mutations are 405. Existing
authentication/SessionAuthentication CSRF behavior remains unchanged. Responses
including errors use `Cache-Control: no-store, private`.

Example query (encode `items` when sending):
`?customer_code=CAT-A&items=[{"product_id":1,"quantity":3}]`

## Response: controlled TEST fixture example, not production prices

The following comes from approved core arithmetic for test base 105 TOMAN, grade A,
quantity 3, stock 10 minus reserved 2. No corresponding production price was seeded.

```json
{
  "version": 1,
  "currency": "TOMAN",
  "customer": {"id": 1, "code": "CAT-A"},
  "visit": {"id": 1, "status": "IN_PROGRESS"},
  "items": [{
    "product_id": 1,
    "product_code": "CAT-0",
    "name": "محصول آزمایشی",
    "unit": "PCS",
    "quantity": 3,
    "pricing": {
      "state": "AVAILABLE",
      "reason_code": null,
      "quote": {
        "customer_id": 1,
        "product_id": 1,
        "grade_code": "A",
        "quantity": 3,
        "base_unit_price": "105",
        "discount_percentage": "10",
        "unit_discount": "10",
        "final_unit_price": "95",
        "line_base": "315",
        "line_discount": "30",
        "line_total": "285",
        "currency": "TOMAN",
        "price_source": "test-fixture",
        "price_source_version": "1",
        "calculation_policy_version": "DEMO_GRADE_UNIT_HALF_UP_V1",
        "quote_fingerprint": "427a7f77ab8c428f86e9e75122265c67e207c8feafdcc632b331e14fd5423d58"
      }
    },
    "inventory": {
      "state": "AVAILABLE",
      "sellable_quantity": 8,
      "can_add": true,
      "reason_code": null
    },
    "can_add": true,
    "non_addable_reason": null
  }]
}
```

Amounts are Pricing Core's whole-TOMAN decimal strings. A=10%, B=5%, other/missing
grade=0%; Decimal ROUND_HALF_UP once at final unit, unit discount by subtraction,
line amounts by multiplication. No tax/promotion stacking or historical SaleItem
fallback. Price source/version/policy and per-product fingerprints are passed
through unmodified, not recalculated by the adapter.

Each fingerprint binds the core's customer/grade/product/quantity/current-price/
source/version/policy results. It is not an authorization token, stock reservation,
request revision or recommendation context. Aggregate basket totals/fingerprint and
saved Draft quote projection remain future basket work, not invented here.

## Truthful states and authorization

Pricing AVAILABLE returns a quote, including explicitly configured zero. Missing
price is HTTP 200 with `pricing={"state":"UNAVAILABLE","reason_code":"MISSING_PRICE",
"quote":null}`; never a fake zero. Fractional/malformed configured data returns
CONFIGURATION_ERROR and a null quote, without repair. Core input/amount-range errors
are safe HTTP 400 errors. Current production has no ProductDemoPrice rows, so no
final price is claimed operational by the UI or this checkpoint.

Inventory reuses `product_eligibility` and `max(available-reserved,0)`:
AVAILABLE / positive integer; UNAVAILABLE / zero; UNKNOWN / null. Requested quantity
greater than positive stock keeps the requested quantity and price quote, with
`can_add=false`, INSUFFICIENT_STOCK; no silent cap. Inventory reasons take precedence,
then price availability/configuration, then VISIT_NOT_ACTIVE. Independent pricing
and inventory state/reason fields remain available even when the top reason differs.

Top `can_add` describes candidate price/stock/quantity/current Visit prerequisites,
not a persisted selection or guarantee of a future basket mutation. Request
immutability, revision and current basket membership remain future mutation safeguards.

Reuse `catalog_access` unchanged: current user/profile/assignment reread, authorized
active customer, exactly matching salesperson-owned Visit. Staff/dual-role/missing
or inactive profiles are denied; foreign/missing/mismatched/closed contexts are
generic 404 and never read commercial products/prices first. PLANNED permits read-only
preparation but is not addable; IN_PROGRESS is potentially addable. Recommendations
do not determine sale eligibility; no saved-priority token is required for pricing.
No recommendation creation, regeneration, ranking or outcome behavior is changed.

## Bounded reads and verification

Deterministic product-ID ordering; 50-item maximum. One joined product/inventory
query, two batched provider queries and three authorization queries: **6 service
queries for one or fifty products**, including missing inventory/price rows.
Session/basic-authentication queries may add their existing fixed authentication
cost outside this boundary. No per-product query or persistent quote cache.

Focused PostgreSQL execution selected **90 tests**: 21 new quote tests plus existing
Pricing Core and catalog regressions. Initial executed run: 89 passed, one new-test
mock error (wrong RecommendationEngine method name). Corrected only that mock to
the actual existing `generate` method and reran only that test: passed. Final
unique-test evidence **90/90 passing**, no unresolved failures; passing suites were
not repeated. Setup guards initially stopped before DB creation on configuration/
no-database-alias issues; only ignored validation tooling was corrected.

Real isolated PostgreSQL databases:
`test_stage3c2_20261009071714_0c31e744` and
`test_stage3c2_20261009071936_bc3b0db7`, both created and removed normally.
Hard connection/SQL guards prohibited SQLite and production write connections.
Existing migrations applied only as ordinary isolated test setup; no migration
file or existing-database migration created/applied.

Django check passed; `git diff --check` passed. No full suite, JS/UI changes or
browser checks. GET/HEAD tests snapshot every managed model and assert SELECT-only
captured SQL; no Draft, line, receipt, feedback, recommendation, price, inventory,
Visit, acknowledgement or Sale/SaleItem change. Recommendation generation is guarded.

Actual runtime-role smoke: genuine SP001 / C0003 / PLANNED Visit 32, 14 products,
6 SELECT queries, all prices truthfully UNAVAILABLE/null; production table states
identical before/after. No login/session creation, seeding or fixture data on production.

## Scope and stop boundary

Exact Stage 3C2 files: `apps/products/quotes.py`, `apps/products/tests_quotes.py`,
`apps/sales_requests/api_views.py`, `apps/sales_requests/api_urls.py`,
`sales_ai_copilot/urls.py`, this checkpoint. Existing receipt/admin/models/migrations,
Pricing Core/tests, UI/assets/settings and all unrelated uncommitted work preserved.
Ignored validation logs/reports/examples under `venv/stage3c2-artifacts/`.

No schema migration, price seed, UI integration, basket read/mutation, feedback,
submission, realized sale, visit completion or messaging behavior. Existing long-running
development processes may need a normal reload to pick up the new route; this task
did not restart/change the preview or default development runtime.

Original SQLite SHA256 unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash unchanged: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No staging, commit or push. Stop after Stage 3C2.
