# V3.0.16 — demo pricing and commercial quote closeout

Owner approved Stage 3C1, 3C2, 3C3 and F1 functionally and visually.
Base: fast-track / V3.0.15 `9a3e170`. This checkpoint closes only pricing/quotes.

## Included feature

- Replaceable server-side Pricing Core over the existing ProductDemoPrice model.
  Whole TOMAN; grade A 10%, B 5%, other/missing 0%; Decimal ROUND_HALF_UP once
  at final unit price. No tax/promotion stacking or historical-price fallback.
- Authenticated, owned Visit/customer quote GET API; batched pricing/inventory,
  private/no-store responses and truthful missing/invalid/zero/unknown states.
- Guided/Detail shared read-only quotes in approved price slots. Fictional-demo
  disclosure, secondary inventory, PLANNED restrictions, signed catalog/return
  context and frozen Quantity/Add regions preserved. F1 strengthens final-price
  contrast without changing card dimensions.
- DEMO_06_V1 controlled 14-SKU dataset and separately authorized operator-only
  idempotent loader/guarded rollback. No automatic startup/GET price population.
- UTC/microsecond canonical PostgreSQL checksums, preserving every table/column
  and detecting real changes; no auth_user exclusion.
- Associated focused tests and approved Stage 3/demo-pricing checkpoints.

Dataset canonical SHA256:
`1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648`.
Earlier owner-authorized DEMO-06C-Retry committed exactly 14 fictional prices on
local sales_ai_db, IDs 15–28, TOMAN / DEMO_ONLY_FICTIONAL / DEMO_06_V1. Protected
receipts/reconciliation remain local under `venv/demo06c-artifacts/canonical-retry/`.
This closeout does not load, update, delete or revalidate by mutating prices.

## Independent commit boundary

Receipt model/admin/migration and receipt-history tests remain unstaged and
byte-identical. Pricing tests' receipt-specific import/snapshot-list additions
are excluded from the index only; the full working file retains them. The
committed pricing tests still check SELECT-only reads and unchanged Stage 1
workflow/history records. All other quote/read tests retain managed-model
snapshots without requiring the unfinished receipt model.

This commit introduces no migration: its tracked graph has 48 migrations.
The current local PostgreSQL database has 49 because the preserved local-only
Stage 3 receipt migration was applied during the approved PostgreSQL transition.
Pricing/quotes do not depend on that receipt table/model. Validate the exact
staged source tree with only its 48-migration graph in an isolated PostgreSQL
test database; do not alter the reconciled local database.

No Feedback/Basket mutation, Add/quantity persistence, submission, completion,
outbound messaging, Sale/SaleItem or revenue functionality is included.
Original SQLite, private artifacts/credentials and unrelated DEMO-02 planning
are excluded. Preserve stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` and SQLite
SHA256 `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.

## Closeout validation

The exact staged source, with no receipt model/migration, passed Django system
check and **60 focused pricing/quote tests** against its 48-migration graph.
Database `test_v3016_20261009111836_4750f5da` was created and destroyed normally;
read-only reconciliation confirmed all production table/metadata checks unchanged.
The focused rerun addressed the mixed-test dependency identified during commit
review; no full suite, visual review, price load or production migration repeated.
Approved JS/visual results remain recorded in the Stage 3C3/F1 checkpoint.

All 29 staged paths were reviewed; imports, route/component/static dependencies,
dataset checksum and Python syntax were checked. No SQLite, credentials, private
artifacts, receipt implementation or schema changes are included. Staged whitespace
validation passed after normalizing only the temporary partial-index blob to LF;
the full working test and receipt files stayed byte-identical.
