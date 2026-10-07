# Task 002-P — Salesperson Journey Visual Cohesion

Implementation prepared 2026-10-07. Awaiting visual/product approval. No staging,
commit, push or 002-K work. Presentation-only changes against `fast-track`;
HEAD and origin/fast-track both `769931e292e40dcb423f146577e343f4ea745d43`.
The user-approved implementation contract is authoritative. No saved 002-P
audit document was found in the repository. Relevant existing 002-B/I/J
foundations and contracts were inspected.

## Scope and visible result

- P0 A/B: scoped ID selectors override legacy operational Start/Complete styles,
  including the Complete button inserted by the existing lifecycle controller.
  Start uses the existing brand fill in PLANNED; Guided selling uses it in
  IN_PROGRESS. Finish, search and the salesperson assistant action are secondary.
  The same Guided link is secondary while PLANNED. All actions retain their
  existing destinations, IDs, handlers, disabled/pending semantics and lifecycle.
- P0 C: recommendation_outcome.css explicitly owns backdrop without blur,
  restrained token shadow, header margins, typography, product text, outcome
  label without a pill, field appearance/focus, 44px close button and submit/cancel
  hierarchy. Compared computed styles match across Customer360 and Guided at
  every approval viewport. Fields, IDs, CSRF and submission JS are untouched.
- P0 D: both Product Brief return anchors say «بازگشت». Their existing return_url
  is unchanged, including valid Guided recommendation/visit context.
- P1 A/C: a small supplied-identity partial is used only by standalone Guided and
  Review. Existing shell identity remains on Daily/Customer360/Product Brief;
  those pages do not duplicate the partial. Their opt-in sj-shell treatment
  removes the extra brand subtitle and breadcrumb, retains all navigation/help,
  and reduces repeated salesperson names in body captions. base.html adds only
  an empty body_class extension point. Managers do not load the new style layer.
- P1 B: IN_PROGRESS uses the existing info semantics, COMPLETED success, and
  PLANNED/CANCELLED neutral. Customer360 follows its existing data-status rereads;
  Review styles follow the existing visitReview data-status. Product Brief shows
  the supplied validated visit number/date/status. Values/mappings are unchanged.
- P1 D/E: confirmation dialogs share token padding, typography, backdrop,
  restrained shadow and mobile button rhythm while retaining their widths.
  Customer360 section links are at least 44px. Names, codes and dates receive
  presentation-only bidi isolation. Daily cards now show visit number/date.
  Completed Review hides its redundant header Daily link and pre-finish eyebrow,
  leaving the existing acknowledgement's clear primary Daily return.
- P2: Review's phone outer gutter becomes 12px, matching Guided and the shell.

Daily stays a planning surface; Customer360 retains richer optional intelligence;
Guided keeps single-product focus and pagination in document flow; Product Brief
retains current facts/saved evidence; Review remains limited to its existing
720px container; acknowledgement stays a closure surface. Wider layouts retain
their existing purpose and width constraints.

The new partial renders only supplied identity and optional navigation. It has
no data queries, authorization, status calculation, workflow or mutation logic.
Review already selects visit.salesperson; no backend pass-through was needed.

## Changed files

New:

- templates/components/salesperson_context.html
- static/css/salesperson_journey.css
- apps/customers/tests_salesperson_journey.py
- docs/checkpoints/SALES_AI_PLATFORM_TASK_002_P_SALESPERSON_JOURNEY_COHESION.md

Modified:

- static/core/css/customer_workspace.css
- static/core/css/recommendation_outcome.css
- templates/base.html
- templates/core/customer_360.html
- templates/core/customer_360/_ai_command_center.html
- templates/core/customer_360/_ai_recommendations.html
- templates/core/customer_360/_customer_hero.html
- templates/core/customer_360/_outcome_modal.html
- templates/core/customer_360/_sales_context.htm
- templates/core/customer_360/_search.html
- templates/core/product_detail.html
- templates/customers/recommendation_presentation.html
- templates/visits/_visit_card.html
- templates/visits/completion_review.html
- templates/visits/dashboard.html
- apps/customers/tests_productization.py (stylesheet revision assertion only)

## Deliberately unchanged

No view/controller/service, JS, URL/API, authorization, business calculation,
ranking, outcome semantics, follow-up synchronization, snapshot, model, schema,
migration or dependency change. Legacy customer_360.css remains intact. Direct
Customer360 completion stays direct and is not rerouted through Review. No POST
retry or new commercial meaning. No demo seed/reset or shared data mutation.

## Automated validation

- Django check: no issues.
- Focused salesperson presentation tests: 6 passed, with isolated fixtures.
- Relevant Customer360/presentation/visits/outcomes/Product Brief/review tests:
  171 passed, including the 6 new presentation tests.
- Full Django suite: 215 passed (baseline 209 plus 6 new tests).
- Applicable JS fixtures: all 20 scenarios passed (4 Guided, 7 outcome, 9 Review;
  Node test runner reports 3 test files passed).
- No JS files modified. Existing four production controllers also pass
  node --check; modified-JS syntax check is not applicable.
- git diff --check: passed.

The six new tests cover operational IDs/link continuity, identical modal field
contracts, shared identity, truthful return wording with unchanged destination,
manager opt-out and all four persisted status labels across hosts.

## Browser validation

Headless Chrome used actual Django views/templates/controllers with supplied
authenticated sales1/manager1 identities, SQLite mode=ro and an SQL write guard.
Both previews reject POST. This bypasses login/session middleware; authentication,
authorization and CSRF remain covered by existing isolated Django tests.

| Viewport | Result |
| --- | --- |
| 390px (primary) | Passed journey, full scroll, long Persian customer/identity, touch targets, modal parity, keyboard, return context and acknowledgement checks. |
| 768px | Passed; wider Guided layout and narrow Review preserved. |
| 1024px | Passed; no document overflow or pagination overlay. |
| 1440px | Passed; purposeful page widths and manager/default shell retained. |

At all four widths: Daily card navigation, PLANNED Start versus Guided hierarchy,
the injected Complete button's presentation, IN_PROGRESS Guided versus Finish,
44px Customer360 section links, Guided outcome targets, both modal hosts, Product
Brief return wording/context, End All confirmation, Review, Finish dialog
Tab/Escape/focus restoration, actual completed acknowledgement and Daily return.
Compared modal backdrop/card/header/title/product/outcome/close/label/field/button
styles match. Full-document scrolling and expanded Product Brief evidence have
no horizontal overflow. No JS runtime exceptions or mutation requests occurred.

Additional 390px checks: keyboard field focus has a 3px token ring, modal Tab
wrap/Escape restore focus, delayed read disables outcomes while loading, failed
read shows the existing error and manual GET recovery succeeds. A visible modal
validation message and long Persian note were inspected without submission.
Real Daily-empty, PLANNED-review-disabled and customer-only states were checked
at all four widths. Guided no-recommendation state is covered by Django tests.

Current shared data already has visit 14 COMPLETED and no visits on 2026-10-07.
The populated Daily/IN_PROGRESS journey and long Persian customer/identity used
an isolated temporary SQLite backup with only that copy adjusted. No shared demo
visit was started or completed for inspection. Actual completion and ambiguous
POST recovery remain exercised by isolated Django/JS lifecycle tests.

Screenshots, browser scripts/reports and isolated fixture database live outside
the repository: `%TEMP%/sales-ai-002p-preview/`. A temporary read-only fixture
preview on http://127.0.0.1:8770 is available for visual approval. It rejects POST;
opening/cancelling Finish is reviewable, submitting it is intentionally blocked.

## Manual inspection

As sales1 in the normal application (prefix with its actual host):

- /api/visits/ — current real Daily empty state.
- /customers/?customer_code=C0003&visit_id=27 — PLANNED, primary Start.
- /customers/?customer_code=C0003&visit_id=14 — existing COMPLETED context.
- /customers/C0003/recommendations/presentation/?visit_id=14&recommendation_id=424
  — actual completed/read-only Guided state; use its Product Brief detour.
- /products/PHI004/?customer_code=C0003&visit_id=14&return_to=presentation
  — concise return label and completed visit context.
- /customers/C0003/visits/14/review/?recommendation_id=424 — completed acknowledgement.
- /customers/C0003/visits/27/review/ — planned disabled Review.

For IN_PROGRESS and populated Daily approval on the isolated read-only fixture:

- http://127.0.0.1:8770/api/visits/
- http://127.0.0.1:8770/customers/?customer_code=C0003&visit_id=14
- http://127.0.0.1:8770/customers/C0003/recommendations/presentation/?visit_id=14&recommendation_id=424
- http://127.0.0.1:8770/customers/C0003/visits/14/review/?recommendation_id=424

Open/cancel outcomes and End All/Finish dialogs. Product Brief returns to the
same product, customer and visit. As manager1 in the normal application, inspect
/customers/?customer_code=C0003 and /products/PHI002/?customer_code=C0003;
salesperson chrome does not apply and operational controls remain absent.

## Repository and database safety

Initial status: only ` M db.sqlite3`. All task files are unstaged (16 modified,
4 new). The pre-existing ` M db.sqlite3` remains; it was never staged, reset,
restored or modified by this task. HEAD/origin remain at the requested baseline.

Database SHA256 before and after (byte-identical):

`E6F85581362A181BA102E132DC3EE5846140B69CBDAD8D324BC29A0EE8C439A7`

Stash remains exactly one entry:
`stash@{0}: On fast-track: home-local-files-before-fast-track-work-2026-10-05`,
object `2dac7bdc26f07f611f471564476ceaa52ec367cc`.

Stop point: visual/product approval. No commit, push or 002-K.

## Final visual polish — Daily and Customer360 entry only

The user approved Guided, Product Brief, Review, Finish confirmation and
Completed acknowledgement, and requested a final information-hierarchy pass
only on Daily and salesperson Customer360 entry. This section records that
additional work; earlier measurements/hashes above describe the first pass.

Daily cards now read customer → visit/priority/status → concise recommendation
cue → primary existing action → native readiness/details disclosure. The existing
commercial readiness, next-best-action copy, purchase/category information,
follow-ups, scores, reasons, targets and promotions remain in the disclosure.
Commercial-block warnings remain outside it. Customer360 is a quiet secondary
link. Phone KPI totals use a compact wrapping row; salesperson aggregate priority
totals/help move below the visit list. Per-card priority remains visible. A quiet
Follow-up link shares the visit-list heading row. Staff retains the prior layout,
information order and action treatment.

For a supplied valid IN_PROGRESS salesperson visit, Customer360 renders compact
customer identity, existing visit context, then the same Guided action before
intelligence. The original CTA is extracted into a presentation partial and
rendered once; its URL and visit continuity are unchanged. Existing customer
metadata and search remain in a collapsed native disclosure below the entry.
AI recommendation, sales assistant, KPIs, history and analytical sections remain
below. Non-active, missing/invalid-visit and manager entry behavior is preserved.
No backend or JS modification was required.

Exact additional files changed relative to the first 002-P pass:

- static/visits/css/daily_workspace.css
- static/core/css/customer_workspace.css
- templates/visits/dashboard.html
- templates/visits/_visit_card.html
- templates/visits/_visit_actions.html (new, existing action markup extracted)
- templates/visits/_daily_priorities.html (new, existing summary markup extracted)
- templates/core/customer_360.html
- templates/core/customer_360/_sales_context.htm
- templates/core/customer_360/_ai_recommendations.html
- templates/core/customer_360/_guided_entry.html (new, existing action extracted)
- apps/visits/tests_workspace.py
- apps/customers/tests_productization.py
- apps/customers/tests_salesperson_journey.py
- This checkpoint.

Approved-surface freeze: Guided/Product Brief/Review templates, shared identity,
base.html, salesperson_journey.css, outcome CSS and each approved surface's CSS
are byte-identical to the start of this final-polish turn. Before/after screenshot
hashes also match for Guided, Product Brief, Review, Finish, Completed and manager
Customer360 at all four viewports (24 matching screenshot pairs).

Final validation:

- Django check: no issues.
- Affected focused tests: 25 passed.
- Relevant 002-P regressions: 174 passed.
- Full Django suite: 218 passed (three new hierarchy/fallback regressions).
- Applicable JS fixtures: 20 scenarios passed across three test files.
- git diff --check: passed. No JS changed.
- 390/768/1024/1440px: passed RTL, scrolling/no horizontal overflow, action order,
  expanded disclosures, 44px operational links/summaries, retained intelligence,
  exact Guided destination and non-active/no-valid-visit fallback checks.
- At 390px/844px height with the long Persian fixture: first Daily primary action
  occupies y=724.75–768.75px; active Customer360 Guided action y=546.5–590.5px.
  Both are fully visible in the initial viewport. Customer360 renders one Guided
  CTA, and search stays collapsed below it.
- Browser validation: zero runtime exceptions and zero mutation requests.

The temporary final-polish preview uses the isolated fixture database, mode=ro,
SQL write guard and POST rejection. Template caching is disabled in this temporary
helper so edits cannot be masked by a stale preview. It still bypasses session/
login middleware; the real Django authorization/CSRF regressions passed. The
real shared database was not edited. Before-images, after-images, freeze hashes
and validation.json are outside the repo in `%TEMP%/sales-ai-002p-final/`.

Read-only final-polish inspection URLs:

- http://127.0.0.1:8772/api/visits/ — populated Daily, expand card readiness.
- http://127.0.0.1:8772/customers/?customer_code=C0003&visit_id=14 — active early entry;
  expand customer/search and scroll through retained intelligence.
- http://127.0.0.1:8772/customers/?customer_code=C0003&visit_id=27 — planned fallback.
- http://127.0.0.1:8772/customers/?customer_code=C0003 — customer-only fallback.
- http://127.0.0.1:8772/customers/C0003/recommendations/presentation/?visit_id=14&recommendation_id=424
  — frozen Guided surface after entry.

The database changed between the first implementation turn and this user review
turn. Its current bytes were recorded before final polish and preserved:

Before/after SHA256:
`E49950656E5AD8EFF594AD62758BDE3CBE2FFE22AA8768EDE205C1D1265D0517`.

Final worktree has 18 modified and 7 new task files, all unstaged, plus the
pre-existing modified db.sqlite3. HEAD/origin remain at the requested baseline.
The one original stash remains at `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No staging, commit, push, schema/data change or 002-K. Awaiting final visual
approval.

## Final blocker check — Customer360 active context

Only active Customer360 entry was adjusted in this pass. Daily and all other
approved templates/styles were frozen by SHA256 at turn start and remain
byte-identical (16 recorded frozen files, including Outcome). The shared
database's visit 14 is actually COMPLETED; its lifecycle state was not changed
or presented as active. Visual acceptance uses an isolated active fixture at
the same requested path, on a fresh preview port with template caching disabled.

The active entry now shows the existing first ranked recommendation's product
name as a concise cue, followed by the unchanged Guided action, then the
secondary existing Finish control. The one lifecycle action container and its
Complete ID/data/handler contracts remain intact. Search remains in the existing
collapsed customer disclosure below entry. All intelligence remains below.
PLANNED, customer-only, invalid-visit and manager branches are unchanged.

Additional changes in this blocker pass:

- templates/core/customer_360.html (stylesheet revision only)
- templates/core/customer_360/_sales_context.htm
- templates/core/customer_360/_guided_entry.html
- static/core/css/customer_workspace.css
- apps/customers/tests_productization.py (revision assertion)
- apps/customers/tests_salesperson_journey.py (entry order/unique control assertions)
- This checkpoint.

Final checks: Django check clean; 17 affected tests, 174 relevant tests and all
218 Django tests passed; 20 existing JS scenarios passed; git diff --check passed.
No production JS/backend/business changes. No mutation requests or runtime
exceptions during browser inspection.

390/768/1024/1440px browser checks passed: one Guided CTA at the existing URL,
customer/active visit recognizable, cue precedes action in reading order,
mobile cue/action stack, secondary Finish follows it, search collapsed below,
44px controls, retained intelligence and no horizontal overflow. Planned,
customer-only/search and invalid-visit fallbacks also passed. At 390px with an
844px viewport and the long Persian fixture, Guided occupies y=522.5–566.5px,
fully in the first viewport. Its destination is still
`/customers/C0003/recommendations/presentation/?visit_id=14`.

Approved-surface before/after images were checked at all four widths. Daily,
Product Brief, Review, Completed and manager Customer360 screenshots are exact
matches. Guided has only a single raster pixel difference in one 1024px capture;
Finish's 390px capture differs only in the browser's transient right-edge 4px
scrollbar. Their source/appearance is unchanged. Outcome template and stylesheet
are also frozen; its existing cross-host DOM and JS regressions passed.

Fresh read-only acceptance URL:
http://127.0.0.1:8774/customers/?customer_code=C0003&visit_id=14

State: isolated SP001 fixture; long Persian customer name, C0003, visit 14
IN_PROGRESS, primary product cue, one Guided CTA, secondary Finish, collapsed
search. The helper opens only its temporary database in mode=ro, guards SQL
writes and rejects POST. Login/session middleware is bypassed for preview;
the isolated Django authorization/CSRF regressions passed.

Screenshot: `%TEMP%/sales-ai-002p-blocker/validated-customer-390.png`.
Other screenshots, freeze hashes and validation.json are in the same temporary
directory outside the repo. Planned URL uses `visit_id=27`; customer-only omits
visit_id. All approved route screenshots were checked in this isolated fixture.

db.sqlite3 SHA256 before/after:
`E49950656E5AD8EFF594AD62758BDE3CBE2FFE22AA8768EDE205C1D1265D0517`.
Stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. All prior uncommitted
work is preserved. Nothing staged, committed or pushed; no 002-K. Stop for
final visual approval.
