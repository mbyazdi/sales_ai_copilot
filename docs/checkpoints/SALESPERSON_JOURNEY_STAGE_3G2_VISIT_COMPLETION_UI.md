# Stage 3G2 — Visit completion UI

2026-10-15. Implemented for owner visual review.
Baseline: fast-track, V3.0.19 d168a0da911849ecd8a65823ee981404a77ecdf1,
plus preserved uncommitted Stage 3G1/F1. Authority: approved journey, Stage 0
lifecycle contract, Stage 3G1 completion API and the owner's Stage 3G2 task.

## Routes and entry points

New GET/HEAD page:
 /customers/<customer_code>/visits/<visit_id>/finish/

The page reuses current Visit/customer ownership and assignment authorization;
anonymous users use normal Django login. Staff, foreign or revoked contexts are
denied. Page GET/HEAD and initial-state/API reads do not mutate domain records.
The page uses private/no-store responses and never accepts arbitrary return URLs.

- Customer360: quiet پایان ویزیت link in the current IN_PROGRESS salesperson
  navigation. No link in manager, customer-only, planned or completed contexts.
- Submitted request Result: explicit پایان ویزیت link while the actual Visit is
  IN_PROGRESS. Submitted snapshots and their stored submission-time Visit status
  remain unchanged. Completed Result pages offer no completion action.
- Existing legacy Customer360 controls, Visit Review and /complete/ are unchanged.
  The new page exclusively uses /api/visits/v1/visits/<id>/completion/.

## State and interaction

One bounded mobile-first Persian RTL screen reuses Review/Result and UI-04
tokens, typography, contextual identity, surfaces and buttons. No global styling,
product card redesign or new outcome/reason form.

- No request: clearly permits finishing without creating a SalesRequest.
- DRAFT: visible warning on the page and confirmation: the draft is not submitted
  or deleted and becomes read-only after completion.
- SUBMITTED: explains that the submitted request remains unchanged; Stage 3G1
  handles the separate acknowledgement atomically.
- COMPLETED: read-only ویزیت تکمیل شد state and direct Daily Plan link.
- PLANNED/CANCELLED: no enabled completion control.

Native accessible dialog requires explicit confirmation. Initial focus is on
cancel; Escape/cancellation creates no command or mutation. Pending confirmation
disables duplicates and Escape. Server-confirmed success updates the visible
Visit badge and focuses the completion heading. Daily navigation performs a
normal request to /api/visits/ and rereads persisted status.

## Pending command and recovery

Only the two Stage 3G1 command fields are submitted: customer_code and stable
command_uuid. Session authentication and rendered CSRF token are required.
The actor/customer/Visit-scoped sessionStorage envelope preserves the exact
serialized payload before sending; storage failure prevents POST.

No automatic mutation retry. Reload/BFcache only triggers authoritative GET.
An identical recorded completion UUID confirms the prior result and clears the
local pending envelope. Legacy or other-command completion is displayed read-only,
without falsely claiming this pending command succeeded or resending it.

Explicit retry requires another confirmation and uses the byte-identical payload.
An uncertain retry remains stored. Definitive retry errors preserve that original
envelope and disable further sending until a fresh successful state read.
Malformed storage, foreign endpoints, unauthorized/mismatched reads and malformed
success responses fail closed. No client-created receipt, acknowledgement,
submission, follow-up, stock change or prepared message.

## Focused validation

- 7 new Django UI tests passed: all three request states, canonical completed
  view, GET/HEAD zero-write, explicit route methods, authorization, Customer360
  entry and Submitted Result entry.
- Focused PostgreSQL selection: 72 tests, 71 passed, 1 existing failure,
  0 errors/skips. All 24 Stage 3G1 completion/migration tests and the other
  directly affected Review/Result and legacy completion tests passed.
- Existing failure: apps.customers.tests_salesperson_journey.
  SalespersonJourneyPresentationTests.test_brief_return_copy_is_truthful_and_target_is_unchanged,
  line 114, still expects two Product Detail back links; approved UI-04 renders
  one. Product Detail source and the test are unchanged from HEAD. Left untouched;
  this selection is not claimed fully green. No Product Detail redesign or
  unrelated assertion correction was made.
- 17 new completion JS tests passed. Existing 16 Review/Result JS tests and the
  legacy completion suite (9 explicit scenarios; one Node file-level test) passed.
- Django check: no issues. Migration drift: no changes. JS syntax, source syntax
  and tracked/new-file whitespace checks passed. No full suite.

Real Chrome: normal dedicated TEST login, both journey entry links, dialog focus
and Escape, Draft warning/cancel preservation, submitted-request guidance, and
one explicit no-request completion. Its committed response was intentionally
interrupted; pending identity survived reload, GET found the durable receipt,
and no automatic POST occurred. Exactly one completion POST. Daily displayed
persisted completion. No fatal JS error, static asset failure or horizontal
overflow. Visible operational targets measured at least 44px at 390/1440.

## Isolated review package

Preview: http://127.0.0.1:8797/accounts/login/
Database: test_stage3g2_preview_20261015051256_33b15e95 (disposable).
Migration 0003 was applied to this copy only: 50 applied migrations.
Existing source preview, its credentials, fixture state and all other previews
were preserved. The new preview uses normal database-backed Django sessions.

From the repository:
 .\venv\stage3g2-preview\start-preview.ps1 -CopyPassword

Username: isolated-preview-sp001. The protected launcher copies the TEST password
to the clipboard without printing it. No authorization bypass/capability harness.

Read/review URLs on port 8797:

- No request, ready: /customers/C0003/visits/2/finish/
- Retained DRAFT, ready: /customers/C0003/visits/19/finish/
- SUBMITTED entry: /customers/C0003/visits/3/sales-request/result/
- SUBMITTED finish, ready: /customers/C0003/visits/3/finish/
- Captured completed state: /customers/C0003/visits/1/finish/
- Customer entry: /customers/?customer_code=C0003&visit_id=2

Open an active state, choose پایان ویزیت, inspect/cancel the dialog or explicitly
confirm only in this isolated copy. Then inspect read-only reload and Daily.
Confirmed completion is permanent for that fixture; no reset is performed.

Numbered genuine screenshots under
 D:\py project\sales_ai_copilot\venv\stage3g2-artifacts\

01-no-request-confirmation-390.png
02-retained-draft-warning-390.png
03-completed-390.png
04-completed-1440.png

Logs/browser evidence and checksummed preservation reports are protected and
Git-ignored under the same artifact directory. Visual approval remains the owner's.

## Changed project files and preservation

apps/visits/completion_page.py
apps/visits/tests_completion_ui.py
apps/visits/js_tests/visit_finish.test.cjs
sales_ai_copilot/urls.py
templates/core/customer_360.html
templates/sales_requests/result.html
templates/visits/finish.html
static/visits/css/visit_finish.css
static/visits/js/visit_finish.js
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3G2_VISIT_COMPLETION_UI.md

Stage 3G1/F1 application, tests and migration 0003 remain byte-identical.
No additional migration or schema change. Production remains at 49 migrations:
applying 0003 there is a separate authorization/deployment step.
Production canonical schema/table/data/sequence reconciliation and source-preview
reconciliation passed unchanged. Preview writes were confined to the new copy.

Original SQLite SHA256 unchanged:
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15

Original stash unchanged: 2dac7bdc26f07f611f471564476ceaa52ec367cc.
Unrelated DEMO-02 planning preserved. Nothing staged, committed or pushed.
