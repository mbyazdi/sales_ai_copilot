# DEMO-06B — isolated controlled price-load validation

2026-10-09; baseline V3.0.15 `9a3e17053d9bb17341572fea95267e2eb19ac288`
plus preserved uncommitted Stage 3 pricing/receipt/quote work.
Owner approved DEMO_06_V1 amounts for this isolated validation. **Production loading
is NOT authorized by this checkpoint and has not been performed.**

## Frozen dataset and checksum

`apps/products/data/demo_prices_DEMO_06_V1.json` contains exactly the approved
14 SKU-keyed whole-TOMAN base values. Source `DEMO_ONLY_FICTIONAL`, version
`DEMO_06_V1`, PCS / 1 PCS, complete sellable unit. All values remain fictional
demo configuration, not verified market prices or historical-unit conversions.

Canonical SHA256:
`1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648`

Checksum definition: SHA256 of UTF-8/ASCII
`json.dumps(parsed_json, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
This freezes all semantic dataset fields and is independent of Git/Windows newline
normalization. Duplicate JSON keys are rejected; any changed price/source/version/
unit/scope field fails checksum validation. All 14 values were compared directly
with the owner-approved proposal before testing.

PHI002 means one complete electric toothbrush per PCS; its existing consumable flag
is deliberately preserved. PAN001 and ROW001 keep their existing generic catalog
identities. No model/capacity/kit/type fact is inferred from imagery.

## Bounded operator-only loader

`apps/products/demo_price_loader.py` exposes no HTTP/UI entry point or automatic
startup hook. Caller must already hold explicit write/rollback authorization.

- `read_frozen_dataset()` verifies the fixed checksum.
- `plan_demo_prices(expected_database=...)` is SELECT-only; checks actual PostgreSQL
  database identity, all 14 active codes, PCS/1 PCS and existing targeted prices.
- `apply_demo_prices(expected_database=...)` locks targeted Product/current-price
  rows in deterministic order, validates the full plan, then atomically creates
  missing configuration rows. Equal base/currency/source/version rows are skipped
  without saving/touching timestamps. Any conflict aborts; no replacement supported.
- Result records database/checksum, created-row IDs/product IDs/values/source/version/
  timestamps and skipped codes. Save this as a protected operator audit report when
  an actual future load is authorized; no new receipt model or request event is used.
- `rollback_demo_prices(report, expected_database=...)` accepts a trusted protected
  report; only unchanged rows actually created by that load can be removed. It
  validates the database/checksum, approved commercial values, product identity and
  exact after-image before any deletion. Later edits/replacement rows conflict.
  Skipped existing rows and unrelated records are never owned by rollback.

PostgreSQL-only operations explicitly reject an unspecified/wrong target/backend.
No SQLite select_for_update assumption, process lock, sequence reset, migration,
historical price lookup, recommendation generation or inventory mutation.

## Actual isolated validation and cleanup

Database: `test_demo06b_20261009083220_c38f2b65`, independently created through
authorized operator credentials. All **49 current migrations** applied only there.
Necessary fixtures: 14 named products/brands/categories, controlled test actor,
customer/grades/Visit/assignment for quote authorization. No source users/password
hashes, business history, recommendation records or stock rows copied/seeded.
Stock stays truthfully UNKNOWN in quote validation; price availability is separate.

**11 focused PostgreSQL tests passed**, 0 failures/errors/skips:

| Check | Observed result |
| --- | --- |
| Read-only preflight | 14 planned creates, 0 writes |
| First load | 14 created, 0 skipped; exact approved values/source/version |
| Identical rerun | 0 created, 14 skipped; no INSERT/UPDATE/DELETE, timestamps and fingerprints identical |
| Grade/quote verification | All 14 quote API prices AVAILABLE for A, B, C/other and missing grade; 56 unit quotes match existing Pricing Core |
| Wrong amounts/source/version | Conflict; no partial price creation or repair |
| Injected failure on fourth save | Entire load rolled back; zero new price rows persisted |
| Rollback | Deletes only owned rows; unrelated price and all non-price managed records preserved |
| Matching pre-existing row | Skipped; rollback removes other 13 and preserves the existing row |
| Later price edit | Rollback conflicts before any delete |
| Repeated rollback | Safe no-op for already absent owned rows |
| Unit mismatch / wrong database | Rejected without changing master data or prices |
| Dataset portability/tampering | CRLF copy accepted semantically; changed price rejected |

Django check passed; `git diff --check` passed. The initial file-style test label
was rejected before database creation; corrected to a dotted class label, then
the focused suite ran once. No full regression suite or UI/browser work.

The isolated database was destroyed normally; an independent read-only PostgreSQL
catalog query confirmed no `test_demo06b_%` database remains. Production table
digests matched before/after; `sales_ai_db.products_productdemoprice` remains **0 rows**.

## Exact proposed production write set — NOT EXECUTED

On the currently empty production price baseline, the only proposed application
writes are **14 INSERTs into products_productdemoprice**, referencing existing
products below. Each gets TOMAN / DEMO_ONLY_FICTIONAL / DEMO_06_V1 plus generated
price-row ID and created_at/updated_at. No Product/FK/flag/name/unit/stock/history/
recommendation/customer/Visit/request/auth/schema updates. Normal price-sequence
allocation only; no resetting or changes to unrelated sequences.

| Code | Current existing product_id | Base TOMAN to insert |
| --- | ---: | ---: |
| PHD001 | 1 | 2,400,000 |
| PHS001 | 2 | 3,200,000 |
| BRN001 | 3 | 4,800,000 |
| BRN002 | 4 | 2,800,000 |
| PAN001 | 5 | 2,600,000 |
| PHI002 | 6 | 2,200,000 |
| BOS001 | 7 | 11,500,000 |
| TEF001 | 8 | 4,200,000 |
| BOS002 | 9 | 5,800,000 |
| PHI003 | 10 | 2,900,000 |
| TEF002 | 11 | 9,800,000 |
| ROW001 | 12 | 5,400,000 |
| PHI004 | 13 | 4,900,000 |
| TEF003 | 14 | 5,300,000 |

Future loader must resolve by code and revalidate this mapping; never assume IDs
from table/list order. Identical successful rerun would perform **zero row writes**.
Unexpected existing conflicting prices stop the process; no auto-upsert overwrites.

## Exact future production procedure and approval boundary

1. Obtain a separate explicit owner instruction authorizing the 14 current-price
   INSERTs on `sales_ai_db` for this checksum. Approval of isolated tests is insufficient.
2. Use a dedicated operator process with existing secure environment credentials,
   DB_ENGINE=postgresql and intended database identity. Do not change normal runtime
   profiles, roles/grants, global environment, original SQLite or schema.
3. Read-only preflight through
   `plan_demo_prices(expected_database="sales_ai_db")`; verify the fixed checksum,
   migration readiness, 14-code/product mapping/units, intended create/skip counts
   and baseline. Record the targeted price before-image and business-table digest
   baseline in a protected Git-ignored artifact directory. Stop on unexpected drift.
4. Only after that authorization/preflight, call
   `apply_demo_prices(expected_database="sales_ai_db")` once. It performs the tested
   one-transaction create-or-skip operation. Save its exact created-row audit report
   securely. Failure rolls back; do not silently retry or replace conflicting data.
5. Reconcile all 14 price fields/source/version and A/B/other core results, plus
   unchanged non-price business data. Run read-only authorized quote checks. Stock
   restrictions remain actual; no UI, Add, basket or recommendation regeneration.
6. Post-commit rollback needs its own explicit authorization. Invoke
   `rollback_demo_prices(saved_report, expected_database="sales_ai_db")` only after
   matching the after-image. Stop if any owned configuration was edited/replaced;
   never destroy submitted snapshots or unrelated current-price rows. Sequence
   gaps after transactional failure/deletion are acceptable and must not be repaired.

No production CLI/HTTP apply command has been run or installed as a startup action.
No production price availability claim: the actual runtime still has no configured
prices. This stage validates the mechanism and proposes the next authorized write.

## Files and preservation

Exact repository additions: `apps/products/data/demo_prices_DEMO_06_V1.json`,
`apps/products/demo_price_loader.py`, `apps/products/tests_demo_price_loader.py`,
this checkpoint. Existing models, migrations, Pricing Core, Stage 3C2, receipt
work, UI/assets/settings and all other pre-existing files remain unchanged.
Private validation runner/logs/reports are ignored under `venv/demo06b-artifacts/`.

Original SQLite SHA256 unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash unchanged: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Index empty; no staging/commit/push or production price load. Stop after DEMO-06B.
