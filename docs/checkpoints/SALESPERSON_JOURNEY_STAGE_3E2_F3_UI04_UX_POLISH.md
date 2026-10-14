# Stage 3E2-F3 — UI-04 final UX polish

2026-10-14. Owner approved for V3.0.18 closeout on 2026-10-15. Implementation baseline:
`6af76c14cd5ffd9fe3528be1093317a8d7cacfd7`. Existing E1/E2/UI-04 work preserved.

## Presentation changes

- Authoritative selected DRAFT membership displays **در درخواست فروش** prominently.
  Remove-first guidance is visible outside the separate **سوابق بازخورد** disclosure.
- Selected products expose history only: rejection/LATER/change controls are
  hidden and remain disabled by the existing controller. Empty history is stated
  truthfully. Prior REJECTED/LATER events remain visible without implying edits,
  acceptance or purchase. Existing UUID/replay/CSRF/authorization behavior is unchanged.
- Product Detail heading is **قیمت و موجودی**. Display-only template aliases map
  `PCS` and standalone package-unit `PCS` to **عدد**. Stored values, names, codes,
  prices and quantities are untouched; unrecognized units remain as supplied.
- Existing Persian category labels remain as supplied. No approved English-to-
  Persian category map was found. An optional owner question was raised; absent
  approval, English names remain unchanged instead of introducing unapproved aliases.
- Hero, identity, commercial/evidence cards, global navigation and Guided layout
  are preserved. Changes are scoped to Product Detail presentation and tests.

## Validation and preview

- 56 focused Django tests passed in isolated PostgreSQL; database created/dropped.
  Django check clean; migration drift reports no changes. 30 focused feedback JS
  tests passed; JS syntax and whitespace checks passed. No full suite run.
- Genuine 390px/1440px selected and unselected captures: no horizontal overflow,
  no fatal JS errors. Selected actions are hidden; unselected actions remain
  functional. Keyboard disclosure, seven-reason dialog focus/open/cancel verified;
  screenshot interactions sent no mutation requests.
- Stable preview stays on `http://127.0.0.1:8790/`, normal isolated TEST login.
  Its four-line basket and all database records were reconciled unchanged.
- An independent copy of that TEST database was created for the unselected state:
  `test_ui04f3_preview_20261014194743_b61c8f8e`, port 8791. No migrations/seeds.
  Only there, TEF003 was removed through the existing CSRF-protected Basket API,
  preserving removal history and creating the normal receipt. No production or
  original-preview record changed. Same dedicated TEST login works on both previews.

Review URLs:

- Selected with prior history: `http://127.0.0.1:8790/products/TEF003/?customer_code=C0003&visit_id=19`.
- Unselected, same product/history: `http://127.0.0.1:8791/products/TEF003/?customer_code=C0003&visit_id=19`.
- UI-04 Philips hero: `http://127.0.0.1:8790/products/PHI004/?customer_code=C0003&visit_id=19`.

Protected, Git-ignored screenshots under `venv/ui04-f3-artifacts/`:
`selected-blender-390.png`, `selected-blender-1440.png`,
`selected-with-history-390.png`, `unselected-recommended-390.png`,
`unselected-recommended-1440.png`. Open the history disclosure to compare prior
feedback with current membership; inspect available decisions only on the unselected copy.

## Safety

Production PostgreSQL and original isolated-preview table/sequence/metadata
reconciliation passed unchanged. SQLite remains locally modified but byte-identical
and unstaged: `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`, unchanged.
Baseline hashes cover 460 existing source files; only six scoped presentation/test
files changed, plus two presentation-tag files and this checkpoint. Backend,
shared feedback controller, pricing, receipt/basket work and assets are unchanged.
Implementation-stage safety checks preceded this authorized closeout. Unapproved
category aliases remain deferred; closeout introduces no translations.
