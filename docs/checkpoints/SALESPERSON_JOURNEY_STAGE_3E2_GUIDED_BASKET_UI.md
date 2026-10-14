# Stage 3E2 — Guided Sale basket UI

2026-10-09; owner approved for V3.0.18 closeout on 2026-10-15. Baseline V3.0.17 with approved,
uncommitted [Stage 3E1 backend](SALESPERSON_JOURNEY_STAGE_3E1_DRAFT_BASKET_BACKEND.md).
The [Stage 3 contract](SALESPERSON_JOURNEY_STAGE_3_IMPLEMENTATION_CONTRACT.md)
governs pricing, inventory, lineage and replay. No backend/schema changes in 3E2.

## Presentation and API wiring

- Activate existing quantity | price | Add footer regions; preserve original grid,
  images (80×84), badges, ranking, filters, secondary Detail and two-column maximum.
- Add a compact, initially collapsed “درخواست فروش” disclosure with server line
  count, total quantity and saved final TOMAN total; expanded contents offer
  explicit quantity update/removal, including products outside the current filter.
- Initial load/filter/reload reads the authorized basket, never creates a Draft.
  Current selection is server-owned, not a browser cart. Old/stale read responses
  cannot replace a newer catalog/basket observation. Failed reads disable actions
  and mark current state unavailable rather than presenting old totals as current.
- Catalog unit quote results govern initial Add eligibility. Selected-line edits
  use the basket's current commercial facts; removal remains possible when prices
  or stock become unavailable. IN_PROGRESS/editable comes from the server.
- Add/PATCH first reads `visits/<id>/basket/quote/` for the resulting selection.
  An accessible native confirmation shows product, absolute quantity and the
  server's resulting total. Only explicit confirmation sends the accepted complete
  basket fingerprint, expected revision, original signed context and stable UUID.
- POST `visits/<id>/lines/`; PATCH/DELETE `requests/<request>/lines/<line>/`.
  CSRF and same-origin credentials are mandatory. All business validation stays
  in Stage 3E1; browser logic only formats monetary strings and collects quantities.
- Confirmed success/replay retrieves the current basket rather than displaying
  an old receipt result as current. Visible unit quotes are reread through the
  existing CommercialQuotes renderer; no browser discount/total calculations.
- Unknown/zero/insufficient stock and missing/configuration-error prices remain
  distinct and truthful. A server-denied proposed quantity disables that action
  until the quantity changes or authoritative state is reread. No silent capping.
  Explicit configured zero price remains a real quote, not a missing-price fallback.
- No Submit, acknowledgement, Visit completion, follow-up, message or Product Detail
  operational controls. Existing pricing/image disclaimers remain visible.

## Recovery and feedback

Successful response shape/context/applied revision/selection are checked before
showing success. No optimistic basket, automatic mutation resend or new UUID on
uncertain transport failure. One frozen command (including method/targets/payload)
is stored in actor/customer/Visit-scoped sessionStorage before send. Reload only
reads server state and restores recovery controls. Storage/CSRF failure prevents
new writes. Explicit retry sends exactly the original command; receipt-status GET
can confirm prior success. A missing receipt is not proof of definite failure.
Lost authorization during uncertain recovery does not discard that command.

Definite fresh-command conflicts refresh state and require another explicit
decision/quote confirmation. Uncertain commands block fresh basket decisions.
Feedback and basket controls coordinate pending state; current selected membership
and revision from basket reads disable rejection/LATER until explicit removal.
Existing REJECTED/LATER history/dialog/labels remain unchanged; conflicts trigger
an authoritative basket reread, not a fabricated local selection state.

Recommended selected lines show “افزوده‌شده به درخواست” from server selection
source. Confirmed recommended removal reports removal with historical add preserved.
Ordinary products have neither feedback controls nor acceptance labels. Backend
creates acceptance/removal events; UI never posts those events separately. The
existing feedback read exposes rejection/defer history, not a full acceptance/
removal timeline; no historical removal state is invented after reload.

## Focused validation

- PostgreSQL: 61/61 passed in
  `test_stage3e2_20261009193624_d3a2660c`, removed afterward. Includes Guided basket/
  feedback/catalog presentation and all 36 Stage 3E1 basket tests with real races.
- JavaScript: 76 distinct focused tests passed across runs (basket 20, feedback 20,
  catalog 25, commercial quotes 11). A new mock initially omitted basketPanel;
  corrected the fixture and reran affected tests. No application failure remains.
- Syntax checks passed for guided_basket.js, guided_catalog.js, guided_feedback.js
  and commercial_quotes.js. Django check passed; migration drift unchanged (49).
- git diff --check and new-file whitespace/syntax inspection passed. No full suite.
- Real browser, isolated PostgreSQL: Add recommended/ordinary, PATCH quantity,
  DELETE/remove/re-add, reload persistence and selected-feedback restrictions passed.
  Review state: revision 7, two selected products, five units, saved total 14,000,000
  TOMAN (copied approved fictional demo prices). Seven basket receipts plus one
  initial isolated feedback receipt; four retained lines (two selected), two add
  events, one removal and one initial rejection, only in the isolated database.
- 390/1440: RTL, no horizontal overflow, 1/2 columns, 80×84 product slots and ≥44px
  quantity/Add targets. Removing controls temporarily while retaining the reserved
  slots produced identical card heights. Recommended selected-state caption is the
  only added card row; no grid/header/price/image redesign.
- Native modal keyboard: initial Confirm focus, Tab to Cancel, Escape closes. No
  fatal browser JS errors. Browser focus emulation was needed for hidden Chrome.

## Isolated manual review

Preview remains on `http://127.0.0.1:8790` using
`test_stage3e2_preview_20261009193639_263bc31c`. Only this disposable database
receives UI mutations. It contains controlled SP001/C0003/Visit 19 IN_PROGRESS
fixtures, copied catalog/pricing/ranking facts, and genuine Django authentication/
authorization checks. No production password hashes are copied. Protected local
capability access supplies an isolated signed-cookie Django session; no application
permissions are bypassed. HTTP/SQL guards permit only Draft line/header and
feedback/receipt mutations; completion/submission/other writes are blocked.

Open access first in local PowerShell:

```powershell
& 'D:\py project\sales_ai_copilot\venv\stage3e2-artifacts\open-salesperson-preview.ps1'
```

Then open:
`http://127.0.0.1:8790/customers/C0003/recommendations/presentation/?visit_id=19`
Without the private access session, authorization correctly denies this page.

1. Inspect the populated summary, expand its lines, and reload: selection persists.
2. Change quantity and inspect the server quote; cancel once, then explicitly confirm.
3. Add an ordinary product: no recommendation feedback is created/displayed.
4. Remove a recommended line: history is retained and rejection/LATER becomes
   available; re-add creates a fresh selection.
5. Search/category/pagination and Detail return keep the saved selling context.

Screenshots/artifacts (all local, protected and ignored):

- `venv/stage3e2-artifacts/guided-basket-390.png` — full 390px catalog/basket.
- `venv/stage3e2-artifacts/guided-basket-390-viewport.png` — populated mobile top.
- `venv/stage3e2-artifacts/guided-basket-1440.png` — bounded desktop, two columns.
- `browser-review.json`, `keyboard-geometry.json` — actual browser verification.

Required captures succeeded. An optional later full-page recapture worker stalled
and was stopped; the verified screenshots remain usable and the preview stayed
running. Later changes only tightened recovery/quote bindings, not visual anatomy.
This checkpoint does not declare visual approval.

## Preservation / deferred work

Stage 3E1 files and unrelated DEMO-02 planning remain byte-identical. Production
PostgreSQL tables/financial/migration/sequence reconciliation remains unchanged.
Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`, unchanged.
No production writes, migrations, seeds, default switch, staging, commit or push.
Only the isolated owner-review database/server remain available intentionally.
Submission/Review/Success and Product Detail basket controls are deferred.
