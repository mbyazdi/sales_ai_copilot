# DEMO-06 — controlled fictional TOMAN pricing proposal

2026-10-09. Owner-review proposal only; **NOT APPROVED FOR LOADING**.
Baseline: V3.0.15 `9a3e17053d9bb17341572fea95267e2eb19ac288` plus existing
uncommitted Stage 3C2/receipt/pricing work, all preserved.

## Explicit DEMO-ONLY scope

**Every base and final amount below is DEMO-ONLY / FICTIONAL, not a verified market,
supplier, manufacturer or historical selling price.** No market research or legacy
Sale/SaleItem amounts informed the proposal. Illustrative product photos/logos do
not establish specifications or exact model identity. No currency conversion or
reinterpretation of historical financial units is proposed.

Amounts are per one recorded **PCS**, package **1 PCS**, before the approved
customer-grade discount. This is a fictional base sales-price dataset, not a cost,
margin, invoice or realized-revenue dataset. Tax remains 0/outside MVP; promotions
do not stack. Netherlands customer geography remains unchanged; TOMAN is the
already-approved denomination for these new demo prices only.

Read-only PostgreSQL inventory confirmed exactly the 14 requested active products.
Descriptions repeat their product names; no manufacturer model/GTIN/capacity/kit
fields exist. Only PHD001's stored 2100W wording and BRN001's Series 3 family provide
additional named identity cues; neither identifies a unique verified model.
**ProductDemoPrice currently has 0 rows and remains empty.**

## Fourteen-product approval table — ALL AMOUNTS DEMO-ONLY TOMAN

| Code | Existing name; brand / category | Base (DEMO) | A final, 10% (DEMO) | B final, 5% (DEMO) | Other/missing final, 0% (DEMO) |
| --- | --- | ---: | ---: | ---: | ---: |
| PHD001 | Philips Hair Dryer 2100W; Philips / Hair Dryer | 2,400,000 | 2,160,000 | 2,280,000 | 2,400,000 |
| PHS001 | Philips Hair Straightener; Philips / Hair Straightener | 3,200,000 | 2,880,000 | 3,040,000 | 3,200,000 |
| BRN001 | Braun Electric Shaver Series 3; Braun / Electric Shaver | 4,800,000 | 4,320,000 | 4,560,000 | 4,800,000 |
| BRN002 | Braun Beard Trimmer; Braun / Trimmer | 2,800,000 | 2,520,000 | 2,660,000 | 2,800,000 |
| PAN001 | Panasonic Hair Curler; Panasonic / Hair Curler | 2,600,000 | 2,340,000 | 2,470,000 | 2,600,000 |
| PHI002 | Philips Electric Toothbrush; Philips / Electric Toothbrush | 2,200,000 | 1,980,000 | 2,090,000 | 2,200,000 |
| BOS001 | Bosch Vacuum Cleaner; Bosch / Vacuum Cleaner | 11,500,000 | 10,350,000 | 10,925,000 | 11,500,000 |
| TEF001 | Tefal Steam Iron; Tefal / Steam Iron | 4,200,000 | 3,780,000 | 3,990,000 | 4,200,000 |
| BOS002 | Bosch Blender; Bosch / Blender | 5,800,000 | 5,220,000 | 5,510,000 | 5,800,000 |
| PHI003 | Philips Electric Kettle; Philips / Electric Kettle | 2,900,000 | 2,610,000 | 2,755,000 | 2,900,000 |
| TEF002 | Tefal Air Fryer; Tefal / Air Fryer | 9,800,000 | 8,820,000 | 9,310,000 | 9,800,000 |
| ROW001 | Rowenta Coffee Maker; Rowenta / Coffee Maker | 5,400,000 | 4,860,000 | 5,130,000 | 5,400,000 |
| PHI004 | Philips Blender; Philips / Blender | 4,900,000 | 4,410,000 | 4,655,000 | 4,900,000 |
| TEF003 | Tefal Blender; Tefal / Blender | 5,300,000 | 4,770,000 | 5,035,000 | 5,300,000 |

Relative placement is a demo-design choice: vacuum/air fryer occupy the highest
band, blenders/coffee maker/shaver the middle band, and smaller appliances/personal
care the lower band. The Bosch/Tefal/Philips blender ordering is intentionally
fictional positioning, not a factual comparison of quality, features or market value.

## Grade calculations and provenance

All 42 grade final-unit values were calculated through the existing pure
`calculate_demo_quote` function, Decimal / whole TOMAN / ROUND_HALF_UP, not copied
from screenshots or calculated with floats. Unit discount is base minus rounded
final; line amounts multiply those units; totals never receive a second discount.

- Proposed `currency`: `TOMAN`.
- Proposed `source`: `DEMO_ONLY_FICTIONAL`.
- Proposed `source_version`: `DEMO_06_V1`, frozen only after owner approval.
- Current calculation policy: `DEMO_GRADE_UNIT_HALF_UP_V1`.
- No effective-date/retail-price/promotion/tax fields or extra price model needed.

PHD001 demo examples: A unit discount 240,000 / final 2,160,000; B discount
120,000 / final 2,280,000; other/missing discount 0 / final 2,400,000. At A quantity
3: line base 7,200,000, line discount 720,000, line total 6,480,000 TOMAN.

Non-SKU rounding demonstration only (NOT a proposed product price): base 105,
grade A yields 94.5 before rounding, final unit **95**, unit discount **10**,
quantity 3 total **285**. Never round the discount independently to 11 or discount
the line total again. Proposed table amounts happen to divide cleanly; the same
ROUND_HALF_UP rule still applies.

## Ambiguities and owner decisions

1. Approve/revise the 14 fictional base amounts and relative demo positioning.
   Do not interpret approval as verified supplier/market pricing.
2. Confirm that one PCS means one complete sellable appliance/device, not a carton,
   replacement part or accessory bundle. All records say 1 PCS, but exact kits are
   unspecified. **PHI002 is named an electric toothbrush while is_consumable=true**;
   this proposal assumes a complete device, not a replacement head. Do not silently
   fix that flag, unit or recommendation behavior as part of price loading.
3. PAN001's conventional tong versus brush-style curler remains unspecified.
   ROW001's filter coffee-maker assumption versus espresso/other type needs owner
   acknowledgement. Exact model/variant/capacity/power/bundle remains unknown for
   most records; the demo assumption can be approved without inventing specifications.
4. Confirm a separate authorized loading task and its precise target database.
   This proposal itself does **not** authorize population. Later price UI should
   identify demo prices as «قیمت نمایشی؛ قیمت بازار تأیید نشده»; no UI change now.

## Proposed repeatable loading — NOT IMPLEMENTED OR EXECUTED

1. Freeze an owner-approved code-keyed manifest containing these 14 whole-number
   decimal strings, TOMAN, source/version, per-PCS assumption and payload SHA256.
   Any later amount revision gets a new source version; never silently redefine V1.
2. A future scoped loader starts in dry-run mode. Verify explicit PostgreSQL target,
   expected migration readiness, active code set, units/pack sizes and existing
   ProductDemoPrice state. Abort on missing/inactive/unexpected codes or conflicting
   prices. Do not infer IDs from list order or derive any historical/AI/promotion price.
3. Use an authorized operator configuration without changing the runtime/default
   database. Capture a protected before-image of only targeted price rows, including
   absence, IDs, values/source/version and timestamps; also record product-code/ID
   mapping and approved payload digest. No credentials/password hashes in reports.
4. Apply the 14 targeted rows in one transaction using the existing OneToOne product
   relationship. Create missing rows; **skip byte-equivalent commercial values**
   so reruns do not touch updated_at or fingerprints. Same source/version with a
   different amount, or another source/version, is a conflict: stop unless an
   explicit replacement approval identifies the exact before-image.
5. Before commit reconcile row count/key set, whole TOMAN, all grade examples,
   source/version and no unrelated changes. Afterwards verify read-only quote
   behavior, including stock still unknown/zero where applicable, stable ranking
   and unchanged historical business data. No recommendation/Customer360 generation,
   inventory update/reservation, promotion, Visit, SalesRequest or realized-sale write.

Identical rerun is a no-op, not a bulk update. Only base data is stored; customer
discount/final amounts remain server-calculated by the replaceable provider.
Price/source-version changes intentionally affect quote fingerprints; mutation
boundaries must revalidate later, not rewrite existing snapshots.

## Proposed rollback — separate authorization, no automatic cleanup

Failed apply/reconciliation rolls back the transaction. For post-commit rollback,
match every targeted row against the recorded after-image first; stop if any was
edited subsequently. Restore recorded prior values for updated rows, and delete
only newly created rows whose IDs/product/source/version/values match this load.
Do not delete unrelated price records, reset sequences, reset databases or modify
Product master data. The current empty baseline would mean removing just the 14
owned rows, restoring unavailable-price behavior. Never rewrite/delete submitted
request snapshots, historical Sale/SaleItem, feedback, recommendations or visits.

## Read-only safety evidence

Only repository change: this proposal Markdown. Calculation/inventory evidence is
ignored under `venv/demo06-artifacts/`; no loader/code/API/test/UI implementation.
No tests/migrations/seeds, default database switch, staging, commit or push.
All 40 PostgreSQL table states matched before/after calculation; ProductDemoPrice
remains empty. Existing pricing/receipt/Stage 3C2 files and stash are preserved.
Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Stop after proposal; no price population authorized/performed.
