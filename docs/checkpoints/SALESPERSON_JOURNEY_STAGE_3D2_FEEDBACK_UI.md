# Stage 3D2 — Guided recommendation feedback UI

2026-10-09; fast-track / V3.0.16 `c96907af` plus preserved Stage 3D1 and receipt
work. Ready for owner visual review; no visual approval is claimed.

## Interaction contract

Only saved recommended cards receive a compact native feedback disclosure beside
secondary Detail navigation. Ordinary cards have the feedback elements removed.
The collapsed disclosure adds no card height; reason/history content appears only
when expanded. Existing image/code/badge/reason/price/Quantity/Add zones, ordering,
real category chips and maximum-two-column layout are preserved. Attribution remains
accessible and no longer overlaps Detail; this adjustment is scoped to cards with
feedback controls. Header, Product Detail and other pages are unchanged.

`رد پیشنهاد` opens one RTL native dialog with all seven approved reason codes;
blank/invalid selection cannot submit. There is no free-text substitute for a reason.
`بعداً بررسی می‌کنم` opens explicit confirmation with no automatic task/completion
claim. Choosing the LATER reason also uses the defer presentation. The wire event
remains D1's REJECTED/reason LATER; the UI never labels deferral as rejection.

The existing authenticated GET/POST feedback endpoint is reused unchanged. Page
CSRF rendering sets a browser cookie without DB writes; POST uses the masked form
token in X-CSRFToken, same-origin credentials and the saved catalog context.
The history API supplies current Visit/request metadata and saved decisions. All
history pages are read in order to show the latest recorded decision per visible
recommendation; no empty-state outcomes are invented.

New decisions stay disabled until the read context succeeds and the Visit is
IN_PROGRESS; PLANNED/closed or submitted-request states show guidance. D1 remains
authoritative for role, ownership, assignment, context and selected-product checks.
Its read contract does not expose selected-line membership: PRODUCT_ALREADY_SELECTED
is enforced atomically at POST and disables that card with explicit removal guidance.
No selected-membership claim or Basket read/service is invented by the UI.

## Confirmation, replay and recovery

- UUID is generated only on explicit confirmation. Payload is frozen with actor-
  scoped customer/Visit sessionStorage, recommendation, reason/action, original
  signed context and observed request revision. No pricing arithmetic is added.
- Pending controls prevent double confirmation. Cancel/open/select creates no POST.
  Success requires an identity-checked server 201; replay is labelled prior-result
  confirmation. No optimistic success or purchase/acceptance state.
- Network/5xx/malformed-success ambiguity retains the exact command. Recovery
  survives reload and does not POST on restore. Only an explicit manual check
  resends the same UUID/payload. No automatic mutation retry or fresh intent while
  unresolved. Lost authorization during recovery does not erase an uncertain result.
- Known 409 conflicts remain failures with Persian guidance. Context/revision/
  lifecycle conflicts require refreshing/checking context; selected-product conflicts
  block that card. Cookie/auth failures cannot bypass D1 protections.
- Browser storage/CSRF preparation failures prevent a fresh POST.

## Focused validation

20 PostgreSQL Django tests passed (four new UI tests plus 16 existing Guided
presentation tests). GET/HEAD snapshot all managed models and remain SELECT-only;
the uniquely named test database was destroyed. Django check passed.

41 distinct JS tests passed: 25 existing catalog and 16 feedback cases. Coverage:
seven reasons, explicit confirmation, Later copy, pending/double click, CSRF,
UUID/payload replay, reload recovery, invalid/denied history, lifecycle/selection
conflicts, authorization loss, malformed 201 and no automatic POST retries.
Only affected tests were repeated after small controller changes. Syntax and
whitespace checks passed; no full regression suite ran.

Actual Chrome at 390/1440 verified RTL, no overflow/overlap, 80×84 image slots,
one/two product columns, zero ordinary feedback controls, keyboard dialog focus,
>=44px visible actions and unchanged collapsed card heights. Empty reason produced
no POST; explicit Later saved only in the isolated test preview and survived reload.
One fixture rejection plus that browser deferral are test history, not real outcomes.

## Owner review — isolated test database only

Preview: `http://127.0.0.1:8789/customers/C0003/recommendations/presentation/?visit_id=19`.
Database: `test_stage3d2_preview_20261009124100_c637fb29`.
It uses read-only copies of existing catalog/price/inventory/recommendation facts,
synthetic authentication and a controlled IN_PROGRESS Visit. Original Visit 19 is
not changed. Source auth accounts/password hashes are not copied. Existing migrations
apply only as isolated test infrastructure; no source/schema migration was created.

Open the protected local launcher in Windows PowerShell:

```powershell
& 'D:\py project\sales_ai_copilot\venv\stage3d2-artifacts\open-salesperson-preview.ps1'
```

1. Use the same browser and exact 127.0.0.1:8789 URL above.
2. Expand a recommended card's feedback; ordinary cards must have none.
3. Open Reject, inspect the seven reasons and cancel; no event should be created.
4. Confirm Later or a selected rejection reason; only the isolated preview changes.
5. Reload and inspect saved history. Do not use production URLs for mutation tests.

Preview POST is restricted to this Visit's feedback endpoint; SQL writes are
restricted to the two event/receipt INSERT targets in this test database. SQLite
and runtime database connections are prohibited. Other mutation paths remain
blocked. The isolated preview/database remain available for owner review and need
cleanup after review; existing previews/runtime profiles are unchanged.

Protected ignored screenshots: `venv/stage3d2-artifacts/guided-390.png`,
`guided-390-viewport.png`, `guided-1440.png`, `reject-dialog-390.png`.
Fixture identity, browser report and preservation evidence are in that directory.

No D1/backend/receipt/pricing/imagery file changed. No Add, Draft/Basket operation,
feedback acceptance, submission, completion or follow-up generation implemented.
All 40 production tables/metadata and 14 prices are unchanged. SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` preserved.
No staging, commit or push. Stop after Stage 3D2 for owner visual review.

## Stage 3D2-F1 — compact confirmed decisions

After a verified 201/replay, the dialog closes and the card disclosure collapses.
One summary displays the latest reason (for example `رد پیشنهاد · قیمت نامناسب`)
or exactly `بعداً بررسی می‌کنم`. The full reason wording and previously recorded
decisions remain in the native history disclosure, rendered with textContent.
Successful replay does not duplicate a history entry in the UI. A screen-reader
live region announces confirmation without adding another visible summary.

Saved decisions hide the redundant Reject/Later choices. A permitted explicit
`تغییر تصمیم` reveals them and states that a fresh event is recorded while old
history remains. It does not POST, generate a UUID or imply editing/deletion.
Only subsequent explicit confirmation creates the new command UUID. PLANNED,
unauthorized, selected-product, pending and submitted-request gating stays intact.

No success/collapse occurs for unknown network results. Stored pending payload,
UUID, original context and manual-only recovery remain unchanged across reload.
D1 remains untouched and authoritative; no new price/recommendation/basket logic.
Two-line summary line-height stays within the existing 44px action row, retaining
collapsed card geometry, image/price zones and existing Detail/attribution access.

Validation: 19 focused feedback JS tests and five Django UI tests passed; Django
check, JS syntax and whitespace checks passed. Tests include all seven reasons,
explicit change/new UUID, preserved history, PLANNED/unauthorized and pending/error
recovery. The isolated Django test database was removed; no full suite ran.

Actual browser checks used the existing isolated preview on port 8789. Explicit
change from Later to PRICE and a separate Later confirmation each appended one
event/receipt only in that test database. Prior rows were retained. A subsequent
read-only capture verified auto-collapse, concise summaries, accessible old/new
history, unchanged collapsed heights, RTL/no overflow and no fatal JS errors.
An initial 1.5px summary-height difference was fixed; successful mutations were
not repeated for the refreshed screenshots.

Owner review uses the same protected launcher and URL above. Updated screenshots:
`venv/stage3d2-f1-artifacts/collapsed-390.png`, `collapsed-390-viewport.png`,
`history-expanded-390.png`. The isolated preview remains available; production
data/metadata, original SQLite SHA, receipt/D1/pricing files and stash are unchanged.
No new migration, staging, commit or push. Stop after F1 for visual review.

## Stage 3D2-F2 — expanded history layout only

Only open-disclosure CSS changed. Detail/attribution remain in their original
action-row document positions. The latest summary has a separate full-width row;
chronological event rows have consistent spacing beneath it. `تغییر تصمیم` is a
distinct secondary action after history. No labels, event order, API, JavaScript,
template, dialog, pricing, image or business behavior changed.

Actual before/after browser measurements match all 14 collapsed card dimensions
and Detail positions exactly at 390/1440px. Expanded layout has no horizontal
overflow/overlap. Native disclosure keyboard activation and Tab to Change work;
focus remains visible and Change retains a >=44px target. Keyboard-induced browser
scrolling was accounted for in document-coordinate comparisons.

Three focused existing JS state/history tests passed. Django system check ran with
database-enforced read-only PostgreSQL settings and blocked SQLite connections.
No directly affected Django rendering tests: this is CSS-only, with no template or
controller change. No database setup, migration, fixture seed or full suite ran.
Whitespace checks passed.

Review URL remains the isolated port-8789 Guided URL above, using the same protected
launcher. Genuine screenshot:
`venv/stage3d2-f2-artifacts/history-expanded-390.png`.
Both production and existing isolated-preview databases are unchanged; original
SQLite hash, receipt/D1/F1 files and stash preserved. No staging, commit or push.
The preview remains available. Stop after F2 for final owner review.
