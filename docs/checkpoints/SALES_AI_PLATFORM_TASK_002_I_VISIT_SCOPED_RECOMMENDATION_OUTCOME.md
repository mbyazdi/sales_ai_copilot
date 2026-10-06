# Task 002-I — Visit-scoped recommendation outcome and continuity

Status: final live visual/product approval granted, including the mobile presentation.
Final validation passed; commit/push authorized for the approved 002-I files. Task 002-J is not started.

## Purpose and approved scope

Preserve the authorized customer, owned visit and inspected recommendation through
Customer360 → Product Commercial Brief → return → explicit outcome recording.
Another visit's events must never become this visit's current result.
This is a bounded correctness/continuity slice, not Guided Sale or order creation.

Baseline: D:\py project\sales_ai_copilot, branch fast-track, HEAD and
origin/fast-track 99e80047753c8193ac3ad439b83125e3a65abee8. Initial source tree clean;
only the intentional local db.sqlite3 modification was present. Existing stash
`home-local-files-before-fast-track-work-2026-10-05` was preserved, with refs/stash
`2dac7bdc26f07f611f471564476ceaa52ec367cc`. No fetch/pull needed.
Read AGENTS.md and approved architecture/002-D/E/F/G/H/outcome-sync evidence.

## Canonical read contract

Additive GET/HEAD:
`/api/visits/v1/visits/<visit_id>/recommendation-outcomes/?customer_code=<code>`

Customer code is required. An authenticated active salesperson must have current
access through `customer_access_queryset`, and the visit must match both customer
and owner. Staff/manager, including dual-role staff, cannot use this operational
read path. Missing, inaccessible, foreign and mismatched contexts return one generic
404; role/profile denial returns 403. Successful responses are no-store/private.

Response:
- `visit`: id, real date/status, authorized customer code/name.
- `can_record`: backend visit status is IN_PROGRESS after authorization.
- `recommendation_outcomes`: unchanged canonical rows from
  `build_post_visit_intelligence(visit)`, which uses `resolve_recommendation_outcome`.
  Rows retain recommendation/product identity, final_outcome, canonical quantity/
  sales_amount, event count and last-event identity/time. Empty array means no
  resolved recommendation result in this visit; absence of a card's ID means no
  result for that recommendation in this visit.

Latest event ordering, equal-timestamp ID tie break and retained valued-purchase
fallback stay in the existing resolver. JavaScript only formats backend values.
The customer-wide raw history API and its response remain unchanged and separate.
History never feeds the selected visit's current status.

## Continuity and UX

- Each rendered recommendation has a stable `recommendation-<id>` anchor and
  focusable article. The Product Brief derives return focus from its already
  authorized customer/product active recommendation, not a supplied arbitrary ID
  or external URL. No active recommendation means return to the generic section.
- Returning focuses/scrolls the actual rendered card and opens its native details.
  It never opens a mutation form or selects/submits an outcome automatically.
  Manager return focus opens only read-only information.
- Customer360 now accepts operational visit context only for the requesting active
  salesperson's own visit and accessible customer. Invalid/foreign visit context
  is discarded with the existing neutral warning, no actionable visit binding.
  Staff inspection continues to ignore visit parameters.
- Current card results have loading, no-result, resolved, unavailable/error states.
  Failed reads clear current results and disable actions; historical events never
  act as fallback. GET refresh is explicit and safe; no POST is automatically retried.
- Five existing outcome choices remain explicit user actions. The compact Persian
  RTL form identifies customer/product/real visit/current result. Quantity and
  recorded amount fields are shown for PURCHASED; FOLLOW_UP retains the existing
  required date. No price/amount/currency is inferred; all defaults/POST fields
  preserve existing quantity/amount behavior.
- Pending submissions are guarded synchronously and disable form input/submit.
  A confirmed save cannot be submitted twice in the same open form; reopening is
  a deliberate new interaction. Success requires a successful writer response.
  Current status is refreshed from canonical GET, never copied from the raw POST
  event. Ambiguous network failures are not success and do not retry the POST.
- Keyboard focus is trapped in the dialog; Escape/cancel return focus to the
  originating action. Read-only inspections do not submit demo mutations.
- Outcome/post-visit copy explicitly treats PURCHASED as a recorded result, not a
  submitted order/invoice, stock reservation or payment.

## Minimal writer compatibility and authorization

The existing `/api/visits/v1/outcomes/` writer, result/history semantics, follow-up
sync, visit sync and CSRF middleware remain. The new UI supplies `customer_code`.
When this optional field is present, the existing writer re-checks canonical current
customer access and matches the owned visit to that customer at write time; staff
operational context is denied. This small compatibility guard is necessary to
prevent revoked assignments becoming actionable between read and save.

Callers omitting customer_code retain the existing owned historical-visit contract,
including legacy dual-role ownership behavior. Existing start/complete/follow-up
APIs are unchanged; no blanket retrospective permission change or impersonation.
The new field does not grant any broader authorization. Numeric validation and
server idempotency are not redesigned. Canonical reads do not call any writer,
configuration builder with write behavior, recommendation engine or LLM.

## Files

- apps/visits/outcome_views.py: small canonical, authorized read-only contract.
- apps/visits/urls.py: additive route only.
- apps/visits/views.py: optional current-customer writer context guard.
- apps/customers/views.py: owned/valid operational visit selection.
- apps/products/views.py: safe recommendation-specific return anchor.
- templates/core/customer_360.html: scoped CSS and new JS module/revision.
- templates/core/customer_360/_ai_recommendations.html: focus anchors, visit/current
  result states, explicit existing actions and result/order boundary copy.
- templates/core/customer_360/_outcome_modal.html: accessible compact form/context,
  CSRF token and truthful status regions.
- templates/core/customer_360/_visit_summary.html: purchase-result wording only.
- static/core/js/recommendation_outcome.js: focused read/form/focus controller.
- static/core/css/recommendation_outcome.css: scoped ds-based RTL/mobile/form rules.
- static/core/js/customer_360.js: retire the obsolete customer-history-derived
  current-status resolver and modal controller; existing history/visit/Copilot/nav
  behavior stays. Add read-refresh/history-refresh notifications only. This is
  one scoped interaction extraction, not a rewrite of the remaining legacy file.
- apps/visits/tests_recommendation_outcomes.py: isolated backend/continuity regressions.
- apps/visits/js_tests/recommendation_outcome.test.cjs: dependency-free isolated
  DOM/fetch fixtures exercising the production JS async controller.
- apps/products/tests_commercial_brief.py: update the one approved return-anchor assertion.
- This checkpoint.

## Validation — 2026-10-06

- `python -B manage.py check`: no issues (0 silenced).
- `python -B manage.py test apps.visits.tests_recommendation_outcomes --noinput`:
  **18 passed**.
- `node apps/visits/js_tests/recommendation_outcome.test.cjs`: **5 scenarios passed**:
  duplicate-pending/CSRF/context/failed-save, canonical refresh and saved guard,
  network failure/no retry, revoked preflight/no POST, manager read-only focus.
- Relevant existing suites: `apps.customers apps.products
  apps.visits.tests_authorization apps.visits.tests_continuity apps.visits.tests
  apps.management`: **131 passed**.
- Full suite: **176 passed** (158 baseline + 18 new Django regressions).
- node --check on customer_360.js, recommendation_outcome.js and the JS test:
  passed. git diff --check: passed (existing LF/CRLF notices only).

Backend regressions cover cross-visit isolation, resolver parity, valued-purchase
fallback, timestamp ties, all five outcomes, follow-up date/synchronization,
owned/foreign/revoked/non-progress contexts, staff/dual-role behavior, preserved
legacy writer authorization, CSRF enforcement, failed writes, safe return targets,
source ordering, no-write/no-LLM GETs, immutable snapshots/recommendations, unchanged
Sale/SaleItem counts and canonical NOT_PRESENTED/management metric parity.

Read-only Chrome review uses actual Django views/demo data through authenticated
RequestFactory/APIRequestFactory preview requests and SQLite mode=ro plus SQL-write
guard. It does not substitute for the user's final live login/visual review.
sales1 and manager1 at 1440/768/390px passed: no page overflow or runtime exceptions,
no mutation requests, correct PHI004/recommendation 424 return/focus/disclosure,
valid visit 14 continuity, current no-result state, keyboard form open/trap/Escape/
focus restoration and read-only manager inspection with no outcome controls.
An intercepted canonical GET failure safely disabled actions without historical
fallback. Pending/write behavior uses isolated fixtures, not live/demo POSTs.

## Database safety and limits

db.sqlite3 SHA256 before and after implementation/tests/browser review:
`B46DB8F247829B1FA4E256EFC930FCD0C70B2EDFACAEC0970F2536342B6F060C`.
The pre-existing local modification is preserved byte-identically, unstaged and
uncommitted. Tests use isolated test data; no seed/reset/demo changes or migrations
against the tracked database. Browser artifacts/scripts remain outside the repository.

No models/schema/migrations/dependencies or recommendation scoring/order changes.
No inventory/promotion/Sale/SaleItem, saved evidence/snapshot, tuning or management
analytics changes. Full Guided Sale/session/cursor/lenses, catalog/manual sale,
Product Advisor, basket/cart/order/invoice/checkout, pricing/currency/quantity
engines, offer persistence, stock reservation, financial policy, navigation/login
redesign and frontend migration are explicitly out of scope.

Numeric-validation and server-idempotency limits of the legacy writer remain;
the UI prevents overlapping pending writes but does not claim exactly-once delivery.
Network ambiguity requires inspecting canonical results before a deliberate new
submission. Purchase fallback, raw event history and visit-level follow-up attribution
are existing semantics. FollowUpTask has no per-product FK; none is invented.
Dates remain Gregorian. October 6 Daily Workspace is empty because the latest demo
visits are dated October 5. Existing promotions expired September 30; no data is
changed to manufacture a populated state.

## Manual review

sales1 → `/customers/?customer_code=C0003&visit_id=14` (owned IN_PROGRESS visit,
real date 2026-08-24) → PHI004/recommendation 424 → «بررسی محصول و شرایط فعلی» →
return. Confirm `#recommendation-424`, visit_id=14, visible focus and open card
details; no form or mutation opens automatically. Read current visit status, open
«نیاز به پیگیری», inspect identity/date/current result, then cancel/Escape without
submitting. Review 1440/768/390px and keyboard focus. Visit 22 remains PLANNED and
therefore cannot record an outcome until an ordinary explicit authorized start.

manager1 → Customers → C0003 → PHI004 brief → return: same read-only card focus,
no carried operational visit and no outcome buttons/modal/operational GETs.
Functional saves are verified using isolated fixtures; do not submit demo writes
solely for visual review. Stop for visual/product approval; no commit/push or 002-J.

## Approved final UX rework — guided single-product presentation

This section supersedes earlier presentation decisions and the earlier exclusion
of a guided visual flow. It preserves the valid 002-I backend read/write/security
work. Full Guided Sale engines/sessions/lenses, transaction creation and schema
changes remain outside scope. The user explicitly approved the mobile/tablet-first
single-product UX and supplied `D:\UI References\guided-selling-approved.png`.
That image was inspected before editing. Incorrect sample product/code/category
combinations, invented photographs and desktop four-action footer layout were not copied.

### Presentation and navigation

New HTML route:
`/customers/<customer_code>/recommendations/presentation/?visit_id=<id>&recommendation_id=<id>`.
Visit and recommendation parameters are optional; when supplied they are strictly
validated against current customer access and salesperson ownership/customer data.
Staff/dual-role staff cannot enter the operational presentation; existing richer
management Customer360/Product Brief inspection remains unchanged and read-only.
The route is registered once at the root, avoiding the legacy duplicated HTML/API
customer URL names. Anonymous/inactive/unassigned/foreign contexts remain denied.

Only one recommendation/product is rendered per response, in the same rank order
as Customer360. A compact dedicated in-visit header uses the shared ds foundations;
the global dashboard/navigation shell is unchanged. Customer360 offers a primary
«شروع نمایش پیشنهادها» action and moves its richer salesperson list behind a
disclosure. Daily IN_PROGRESS primary links open the presentation; PLANNED visits
still enter Customer360 for an explicit existing start. Manager/dual-role staff
daily links remain inspection links. No page/view automatically starts a visit.

Default hierarchy: salesperson/customer/real visit → exact position/remaining count
and progress → large product visual → actual name/code/brand/category/type → first
two complete saved reason sentences → current canonical inventory/useful eligible
offers → optional explanation/Product Brief → compact five outcome actions →
Previous/Next → visually separate End Group/End All.

No raw scores, signal contribution lists or engine diagnostics appear in the guided
default. Full saved reason is optional; Product Brief is optional deeper inspection.
Its new `return_to=presentation` enum selects a server-constructed authorized return
URL with the same recommendation/visit. Arbitrary URLs/foreign recommendation IDs
are never trusted. Existing Customer360 return anchors continue to work, including
opening ancestor disclosures after the richer list became secondary. Guided return
focus does not automatically expand explanation or open a mutation form.

Previous/Next and group-target URLs are backend-generated navigation values, not
JavaScript ranking/business formulas. First/last/single/empty states are explicit.
Refresh and Back/Forward preserve selection through the URL; restored browser pages
re-read canonical outcomes. Groups are consecutive runs of the same stored existing
recommendation_type in rank order. End Group moves to the next different type without
globally excluding later occurrences or reordering. End All requires a native dialog
confirmation; ending the last group also requests confirmation before leaving.
These controls only navigate/leave the screen: no group/session completion record,
NOT_PRESENTED event, visit completion or outcome is implied or written.

### Image strategy and reference deviations

Product has no canonical image/media field or source. The hero therefore uses a
large neutral labelled image placeholder, not fabricated product photography,
external URLs, thumbnails or a new media/storage model. The view reserves an
optional `image_url` presentation adapter, currently None; future canonical media
can occupy the same contain-fit slot. Failed media returns to the labelled fallback.
There is no new model/migration/dependency or product-media data change.

Real stored names/codes/categories replace the mockup's inconsistent sample text.
Stock units remain recorded values (e.g. PCS), not invented «عدد»/currency semantics.
RTL navigation places Previous on the right and dominant Next on the left with
appropriate arrows; the mockup's mixed directional artifacts are not copied.
The mobile navigation is reachable at the viewport bottom with safe-area/content
padding; tablet/desktop use a compact normal row. End actions are separate from
pagination. Touch outcomes are at least 44px in both dimensions (measured approximately
61×58px at 390px). Image/product arrangement stacks on phone and becomes a spacious
text-right/image-left composition on tablet. Keyboard focus, native confirmation,
dialog cancel/focus restoration and textual result labels do not rely on color.

### Preserved outcome contracts and safety

The existing visit-scoped canonical read, resolver, tie ordering, purchase-value
fallback, optional customer_code writer guard, CSRF and synchronization are reused.
The same outcome controller handles the one rendered product. Unavailable products
remain navigable but cannot enable outcome controls; missing and zero inventory
remain distinct. No price/amount/promotion/credit/reason/image is invented.
Viewing, navigating, returning, ending a group/all or opening/cancelling a form
produces zero business/configuration writes and no AI/LLM calls. Mutation requires
the existing explicit form save. Pending/repeated-saved submissions are guarded,
failed POST remains recoverable and POST is never automatically retried.

### Additional files for this rework

- apps/customers/presentation_views.py: scoped one-product reader/navigation context.
- sales_ai_copilot/urls.py: unique HTML presentation route.
- templates/customers/recommendation_presentation.html: focused mobile/tablet page.
- static/core/css/recommendation_presentation.css: responsive ds-based presentation.
- static/core/js/recommendation_presentation.js: navigation confirmation/media fallback only.
- apps/customers/tests_recommendation_presentation.py: 12 isolated Django regressions.
- apps/customers/js_tests/recommendation_presentation.test.cjs: isolated navigation/fallback scenarios.
- templates/visits/_visit_card.html: primary in-progress selling entry.
- Existing 002-I Product Brief view, recommendation list, outcome JS/tests and this
  checkpoint: return context, secondary rich list and shared guided-controller support.

### Rework validation and database

- Django check: no issues (0 silenced).
- Guided presentation + preserved 002-I outcome suites: **30 passed** (12 + 18).
- Relevant Customer360/Product/visit/authorization/continuity suites: **133 passed**.
- Full suite: **188 passed** (176 earlier 002-I + 12 new presentation regressions).
- Isolated production-JS fixture scenarios: **7 outcome + 4 navigation/media passed**.
- JS syntax checks for customer_360.js, recommendation_outcome.js,
  recommendation_presentation.js and both fixture-test files: passed.
- git diff --check: passed; existing Windows LF/CRLF notices only.

Read-only authenticated Chrome preview reviewed at 390/768/1024/1440px, with actual
authorized demo data and SQLite mode=ro/SQL-write guard: one rendered product,
correct RTL, no page overflow, no runtime exceptions or mutation requests. Verified
first/next/previous/last/group transitions, refresh, Back/Forward, Product Brief
return to recommendation 424, keyboard End All confirmation/cancel, last-group
confirmation, read error/disabled actions/recovery, form open/cancel, and unchanged
manager inspection/operational denial. No live/demo outcome was submitted for
visual testing. Browser artifacts remain outside the repository. Final live visual
approval is still required; preview does not replace the application's login review.

At entry to this rework the intentional local database hash differed from the prior
002-I review. That pre-existing state was preserved exactly, not restored. Before/
after SHA256 for this rework:
`F0BA0AC6D7ED7AB126D490D3823534F7361CBEDE0B018E3D852F2B99C6083FE3`.
The database remains unstaged/uncommitted; the existing stash remains untouched.
No seeds/resets/migrations, models, backend calculations, engine ordering, tuning
or management analytics changes. Current demo data now contains later visits than
the earlier audit; the read-only review still uses real owned visit 14 (2026-08-24,
IN_PROGRESS), without altering any visit date/status or fabricating current offers.

### Final manual inspection

sales1 → Customer360 C0003 with owned visit 14 → «شروع نمایش پیشنهادها».
Direct: `/customers/C0003/recommendations/presentation/?visit_id=14`.
Press Next to PHI004/recommendation 424. Open «بررسی محصول», return, confirm the same
product/visit. Open/cancel an outcome form without saving; inspect position/type,
current stock, compact actions, Previous/Next, End Group and End All confirmation.
To enter directly at PHI004, add `&recommendation_id=424`. Also inspect any actual
today IN_PROGRESS visit through Daily Workspace without changing demo data.
manager1 → Customers → C0003 retains richer read-only inspection, with no guided
operational action. Do not commit/push or start 002-J; stop for visual/product approval.

## Focused mobile overlap/density polish

This presentation-only pass supersedes the fixed mobile footer described above.
Pagination now occupies its own normal document row directly after the product
interaction. It is not an overlay: product title, explanation, outcome controls
and completion actions cannot pass behind it. Mobile safe-area padding remains.
Previous/progress/Next controls and the separate completion hierarchy are unchanged.
No URL, script, backend, authorization, grouping/outcome or completion behavior changed.

Only recommendation_presentation.css and this checkpoint changed in this pass.
Phone-only overrides compact header/customer/progress gaps, reduce the placeholder
to approximately 133px and real-image slot to 180px, and bring identity/message
closer without reducing text sizes. Tablet/desktop computed composition remains
unchanged. Outcome targets remain approximately 63×58px at 390px.

Read-only Chrome review at 390×844, 768×1024, 1024×768 and 1440×900 verified initial
view and full scrolling: below image, title, outcome controls, pagination and
completion actions. Bounding-box sweeps found zero navigation/content intersections,
no horizontal overflow, runtime exceptions or mutation requests. At 390px, title
begins at approximately 383px and message at 454px; title font remains 19.2px.
Pagination is fully reachable and End All confirmation/cancel remains intact.

Validation: Django check clean; 30 focused, 133 relevant and 188 full-suite tests
passed; 11 isolated JS scenarios and unchanged-controller syntax checks passed;
git diff --check passed (existing LF/CRLF notices only).
The database had another intentional local state at entry; it was preserved,
not restored. Before/after SHA256 for this polish:
`BD529E6DED2CC62560AB77884321D1318A6D7F1671F84AA6B64EAC3892C5BC96`.
No stage/commit/push or 002-J. Final visual approval remains pending.

## Final approval and commit handoff

The user granted final visual/product approval for the visit-scoped outcome flow,
guided single-product presentation and final mobile overlap/density polish. This
supersedes all earlier pending-approval notes. Finalization introduces no additional
UX, CSS, backend, business-rule or architectural changes.

Final validation rerun: Django check clean; **30 focused tests passed**;
**133 relevant existing tests passed**; **188 full-suite tests passed**;
**11 isolated JS scenarios passed**. All three production JS files and both JS test
files passed node --check; working/staged diff whitespace checks are required before
commit. The approved commit contains only the 24 scoped source/test/static/template/
checkpoint files. No schema/model/migration, generated artifacts or 002-J work.

The intentional local database had a newer hash at finalization entry than during
prior reviews. It was preserved without reset/restore/seed/migration. SHA256 before
and after final validation is identical:
`0C9444025459DCC8F82816B3115AF7846D03E9EA77789EFCDEBA06AB19012AF2`.
db.sqlite3 is explicitly excluded from staging/commit. The existing stash remains
untouched. The local design reference `D:\UI References\guided-selling-approved.png`
is not copied or committed. Stop all development after commit/push verification.
