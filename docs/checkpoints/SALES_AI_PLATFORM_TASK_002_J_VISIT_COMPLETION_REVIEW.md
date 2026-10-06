# Task 002-J — Visit Completion Review & Explicit Finish Flow

Implementation checkpoint: 2026-10-06. Final visual/product approval granted;
commit and push to fast-track authorized. Baseline: `fast-track`, HEAD and origin/fast-track
`254d532331057bdb5b327c4ad01ed0879f28b349` (approved 002-I).

## Approved scope and user journey

Daily Workspace → customer visit → Guided Recommendations → confirmed End All
→ lightweight Visit Review → explicit Finish confirmation → acknowledgement
→ Daily Workspace. The approved guided layout, ranking, grouping, commercial
context and Product Brief behavior remain intact.

Review route: `/customers/<customer_code>/visits/<visit_id>/review/`.
The selected active recommendation ID is validated and optionally carried back
to the same guided product. Invalid/foreign focus IDs are discarded. Customer-only
presentation keeps its Customer360 End All fallback. An owned, accessible supplied
visit routes to review; only IN_PROGRESS is actionable. PLANNED/CANCELLED are
read-only; COMPLETED displays acknowledgement.

End All is GET navigation. It does not finish the visit, record outcomes, infer
presentation/viewing, create tasks or create commercial transactions. Review GET,
return navigation and opening/cancelling confirmation are also read-only.

## Canonical data and semantics

`build_post_visit_intelligence(visit)` supplies resolved recommendation totals,
all five outcome counts and existing visit-linked FollowUpTask counts/nearest
open due date. It reuses `resolve_recommendation_outcome`; raw events are not
counted as resolved recommendations. Cross-visit events are excluded. Ordering,
purchase fallback, recommendation snapshots and management denominator semantics
remain unchanged. No business formulas are implemented in JS.

The total is labelled «پیشنهادهای دارای نتیجه ثبت‌شده». Slides viewed are not
tracked or counted. No current-active-roster coverage KPI is introduced. Legacy
unattributed events, if present, receive a separate informational note.

PURCHASED remains a recorded interaction outcome, not order/invoice/payment or
authoritative revenue. No revenue KPI, currency, price or stock policy is added.

FOLLOW_UP outcomes and OPEN tasks are shown as distinct concepts. Existing task
counts and nearest OPEN due date are reused, including a truthful neutral state
when a follow-up outcome has no scheduled open task. Review never creates,
reconstructs, completes or cancels tasks. The existing Follow-up Workspace is
linked when relevant. Zero outcomes remain valid for completion; no outcome is
required and no automatic NOT_PRESENTED is written.

## Authorization and completion contract

Review requires an authenticated active non-staff salesperson, current customer
access through `customer_access_queryset`, active customer and owned matching
visit. Missing, foreign, revoked or mismatched context fails with generic denial.
Staff, including dual-role users, cannot enter this new operational flow.
Managers continue existing read-only customer/history inspection.

Only explicit confirmation posts to the unchanged canonical route
`/api/visits/v1/visits/<id>/complete/`, with CSRF and `customer_code`.
The smallest additive optional guard rechecks current customer access, visit
ownership/match and non-staff operational role. Legacy callers omitting
`customer_code` retain their existing historical ownership contract, including
characterized dual-role behavior. No breaking response or lifecycle change.

Canonical completion still requires IN_PROGRESS and changes only visit status
to COMPLETED plus the existing updated_at save. It remains non-success-idempotent:
a repeat returns 400. No new timestamp, duration, visit reopen, snapshot change,
outcome sync, task sync, order, sale or LLM invocation is introduced.

## Async recovery and UX

Finish is disabled until a matching canonical status GET succeeds through the
existing 002-I recommendation-outcomes read API. The native confirmation dialog
has cancellation focus, keyboard Escape/Tab support and clear consequence copy.
Only confirmation can POST; pending submissions disable duplicate clicks and
cancellation. There is no automatic POST retry.

Dropped, malformed or rejected completion responses trigger a canonical status
GET. COMPLETED becomes read-only acknowledgement. An unchanged IN_PROGRESS
requires another explicit confirmation. A failed reread keeps Finish disabled
and provides a manual GET recovery action. Errors are visible both in the review
and the dialog. BFcache restoration reloads the GET document so server-rendered
counts/tasks are refreshed. Counts represent the latest document GET; this is
not a live multi-tab analytics screen.

The Persian RTL page reuses ds-* foundations: customer/date/status, compact
five-outcome cards, concise follow-up context, Finish and Return actions. No
charts/tables/diagnostics. Phone actions stack; tablet/desktop actions share a
row. Safe-area padding, 48px primary controls, readable numbers, text status,
focus rings and semantic headings/dl/dialog support accessibility.

## Files

- `apps/customers/presentation_views.py`
- `apps/visits/views.py`
- `apps/visits/review_views.py`
- `apps/visits/tests_completion_review.py`
- `apps/visits/js_tests/completion_review.test.cjs`
- `sales_ai_copilot/urls.py`
- `templates/customers/recommendation_presentation.html`
- `templates/visits/completion_review.html`
- `static/visits/css/completion_review.css`
- `static/visits/js/completion_review.js`
- This checkpoint.

## Validation

- Django check: no issues.
- Focused `apps.visits.tests_completion_review`: 21 passed.
- Relevant visits + customer presentation + Product Brief suites: 156 passed
  (includes the 21 focused tests).
- Full Django suite: 209 passed (baseline 188 plus 21 new regressions).
- New isolated completion JS fixture: 9 scenarios passed.
- Existing outcome/presentation JS fixtures: 11 scenarios passed.
- Node syntax: new controller and JS fixture passed. No existing JS was changed.
- `git diff --check`: passed.

Finalization reran all required checks after approval: 21 focused tests, 156
relevant tests, 209 full-suite tests, 9 new and 11 existing JS scenarios passed.
Django check, both changed JS file syntax checks and diff checks passed. No UX,
CSS, backend or business behavior was changed during finalization.

Tests cover current scope/ownership, customer mismatch even with both assigned,
revocation, inactive/missing customer, staff/dual-role, no-write/no-LLM GET,
canonical counts and cross-visit isolation, zero-outcome completion, task/count
distinction and no reconstruction, End All/fallback/return, persisted statuses,
CSRF, snapshot/history/task preservation and legacy completion. Isolated JS
fixtures cover explicit confirmation, pending protection, CSRF payload, dropped/
malformed/repeated response recovery, rejection, failed reread/manual recovery,
denied/mismatched status and completed/BFcache behavior.

Read-only Chrome review used SQLite mode=ro plus an SQL write guard and temporary
authenticated preview outside the repository. Reviewed 390/768/1024/1440px:
End All confirmation → Review, correct context and return to recommendation 424,
RTL, scrolling, no horizontal overflow, 48px CTA, confirmation focus/Tab/Escape,
planned disabled state, customer-only fallback and manager denial. No JS runtime
exceptions or mutation requests occurred. Actual completion writes and ambiguous
responses were exercised with isolated Django/JS fixtures, not the demo database.
Preview bypasses login/session middleware; isolated CSRF tests cover real session
authentication. Screenshots/helpers stay outside the repository.

## Database and repository safety

Pre-existing local `db.sqlite3` modification remains intentional and unstaged.
Before and after implementation/validation SHA256 (byte-identical):

`0C9444025459DCC8F82816B3115AF7846D03E9EA77789EFCDEBA06AB19012AF2`

At the start of approved finalization, the pre-existing local database differed
from that earlier implementation hash. Finalization preserved its current bytes;
SHA256 before and after final validation:

`E6F85581362A181BA102E132DC3EE5846140B69CBDAD8D324BC29A0EE8C439A7`

The database is excluded from the approved staged/committed file set.

No schema/model/migration, seed/reset, configuration or dependency changes.
Existing stash preserved:
`2dac7bdc26f07f611f471564476ceaa52ec367cc`,
`home-local-files-before-fast-track-work-2026-10-05`.

## Live inspection and limitations

As `sales1`, open C0003 guided presentation with existing owned visit 14 and
recommendation 424:
`/customers/C0003/recommendations/presentation/?visit_id=14&recommendation_id=424`.
Confirm End All; review URL is
`/customers/C0003/visits/14/review/?recommendation_id=424`.
Visit 14 is IN_PROGRESS dated 2026-08-24, with zero resolved results and no open
follow-ups in the inspected demo. These empty values are intentional. Visit 27
is PLANNED dated 2026-10-06 and cannot be finished. No demo records were changed
to improve screenshots.

Inspect counts and current status, open/cancel Finish, return to the same guided
recommendation. Finish confirmation is the sole live mutation: completing visit
14 changes the demo and cannot be reopened through this task; do not confirm
merely for visual inspection. Successful completion shows acknowledgement and
Daily Workspace return. Manager inspection stays on existing customer/history
surfaces; the new operational review is denied.

Completion is not success-idempotent, there is no dedicated completion time or
duration, and no order/invoice relationship is implied. Login/session browser
testing and actual live completion were deliberately not performed. No 002-K work.
Final visual/product approval is granted. Finalization includes only the approved
002-J files; no reference images, screenshots, schema/migrations or 002-K work.
