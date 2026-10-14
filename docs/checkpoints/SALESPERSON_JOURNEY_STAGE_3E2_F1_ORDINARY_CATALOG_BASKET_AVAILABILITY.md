# Stage 3E2-F1 — Ordinary catalog basket availability

2026-10-14. Owner approved for V3.0.18 closeout on 2026-10-15. Implementation baseline HEAD/origin:
`6af76c14cd5ffd9fe3528be1093317a8d7cacfd7`; accepted E1/E2/UI-04/F3 work preserved.

## Investigation

Recommendation priority never controls sale permission. Active catalog products
use canonical inventory `max(available - reserved, 0)`, current Pricing Core,
Visit/assignment authorization and DRAFT basket state. Reads never create state.
Catalog price existence is only a placeholder; Quote/Basket validation is authoritative.

For C0003, actual read-only production classification:

| Products | Cause / current facts |
| --- | --- |
| PHS001 (ordinary) | Price configured: 3,200,000 TOMAN; stock 24 less 8 reserved = 16 sellable. Eligible in an authorized IN_PROGRESS Visit; existing backend already supports Add/update/remove. |
| BOS001, BOS002, BRN001, BRN002, PAN001, PHD001, PHI003, ROW001, TEF001, TEF002 | All have configured prices but no inventory record: UNKNOWN, visible, not addable. No stock was fabricated. |
| PHI002, PHI004, TEF003 (prioritized) | Positive known inventory and configured prices; same commercial controls apply. |

Production C0003 Visit 19 is PLANNED, so it cannot mutate a basket; closed Visits
also remain protected. Isolated previews use their existing controlled IN_PROGRESS
Visit 19. All 14 prices currently exist; ProductDemoPrice has no inactive flag.
Missing/configuration-error prices and insufficient stock are distinct tested states.

## Small frontend correction

There was no ordinary-product exclusion defect. The UI did allow an excessive
typed quantity to leave Add enabled until the resulting-basket quote rejected it,
and that rejection appeared only in the global notice.

- Gate Add/update against positive-integer desired quantity and the server-supplied
  stock limit; permit reducing an overstock selected line rather than disabling its input.
- Explain unavailable stock/price, Visit/read restrictions, pending commands and
  rejected quantities in the existing card availability area, linked by aria-describedby.
- Disable Add when known invalid other basket content would prevent the resulting
  quote. Explicit removal remains available even with invalid stock/prices.
- Fresh server basket quote/fingerprint, revision, CSRF, UUID, confirmation and
  retry/replay rules remain unchanged. Browser checks do not replace mutation revalidation.
- No API/service/model/price/stock/ranking change. No template/CSS/card redesign.
  Product Detail and shared feedback code are byte-identical to the task baseline.

## Validation and review

- 58 focused PostgreSQL Django tests passed, including ordinary add/update/remove,
  stock/missing-price failures with zero effects, authorization, CSRF, replay,
  rollback, pricing and Guided bindings. Isolated test DB created and dropped.
- 81 focused JS tests passed, including five new availability regressions.
- Django check clean; migration drift unchanged; JS syntax and diff checks pass.
  No full suite. Basket read query regression remains nine queries for 1/2/50 items.
- Browser exercised real ordinary PHS001 removal of the copied selection, Add 2,
  reload, update 3, removal and reload, only in an independent TEST preview copy:
  `test_ordinary_f1_preview_20261014201547_30ff4130`, port 8792.
  Four receipts advanced revision 12 → 16. Ordinary feedback events remain zero;
  total feedback history remains six events. Only request/line/receipt tables changed.
- Quantity 17 was blocked against sellable stock 16; unknown-stock cards remained
  disabled. Missing/configuration-error prices and zero/insufficient stock are
  covered with isolated fixtures, not production price/inventory alterations.
- A private browser-helper Unicode comparison caused timeouts after successful
  commands. Server state was inspected before resuming; commands were not replayed
  blindly. Final browser checks passed with no fatal JS error or horizontal overflow.

Preview: `http://127.0.0.1:8792/customers/C0003/recommendations/presentation/?visit_id=19`.
Uses the existing dedicated TEST credential via normal Django sessions; credentials
were not reset. The stable 8790 preview and 8791 F3 preview remain unchanged.
PHS001 is unselected and eligible after the test for manual inspection.

Protected, Git-ignored screenshots in `venv/ordinary-basket-f1-artifacts/`:
`ordinary-availability-390.png`, `ordinary-availability-1440.png`,
`ordinary-populated-390.png`, `ordinary-populated-1440.png`.

## Preservation

Read-only reconciliation confirms production PostgreSQL and original-preview
tables/sequences/metadata unchanged. Inventory/pricing in the new fixture copy
are unchanged too. Existing source hashes changed only for guided_basket.js and
its two test files, plus this new checkpoint. SQLite remains unstaged and unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No production writes, migrations, inventory seed, price changes, stage, commit or push.
