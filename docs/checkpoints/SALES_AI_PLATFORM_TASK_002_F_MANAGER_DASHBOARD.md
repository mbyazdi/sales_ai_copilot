# Task 002-F — Sales management decision workspace

## Baseline and safety

- Branch: fast-track; HEAD: 712e31e291cde7c458602d28ae46a3026cce9c10.
- `git fetch origin` succeeded; HEAD/origin divergence was 0 / 0.
- Initial status contained only the expected manual-demo modification to db.sqlite3.
- Starting and final database SHA256: `01E333AB8FF8785B69D856C026ED5F780283D0888CCA890D7B51BB14079329DE`.
- Read AGENTS.md and approved 002-B/C/D/E checkpoints; reused the 002-A top-navigation shell and 002-B ds tokens/components.
- No database restore/staging/seed/reset/migration; no model, schema, dependency, recommendation-scoring, authorization or API changes. No commit or push.

## Audit: metric source and meaning

The original HTML page was an empty client-rendered shell. Its staff-only `/api/management/v1/dashboard/` response combines management contracts from `apps/visits/services.py` and an optional executive narrative from `apps/ai/services.py`. Core figures originate in `build_outcome_analytics_contract` and `resolve_recommendation_outcome`.

Each Visit + Recommendation pair contributes one resolved result. The latest event determines its outcome. For a final PURCHASED result, the resolver uses the latest purchase event carrying quantity or monetary value, if one exists. Raw event counts, recommendation inventory, and total company orders are not these metrics.

| Block/metric | Source and definition | Reality/actionability/placement |
|---|---|---|
| Evaluated recommendations | Resolved Visit + Recommendation pairs with recommendation context | Real count; primary, with presented count as context |
| Presented | PURCHASED + INTERESTED + FOLLOW_UP + REJECTED; excludes NOT_PRESENTED | Real denominator; methodology and table context |
| Conversion | PURCHASED / presented × 100; zero if no presented data | Derived deterministic KPI; primary; never independently classified good/bad |
| Engagement | (PURCHASED + INTERESTED + FOLLOW_UP) / presented × 100 | Derived deterministic KPI; primary; not interest rate alone |
| Successful purchases | Number of resolved PURCHASED pairs | Real result count, not order count; primary |
| Sales amount | Sum of resolved purchase sales_amount | Recorded recommendation revenue only; primary; currency unit is unspecified in the contract, so no rial/toman assumption |
| Data quality | Presented 0: NO_PRESENTED_DATA; 1–2: INSUFFICIENT_DATA; 3–9: LIMITED_DATA; 10+: SUFFICIENT_DATA | Existing backend thresholds; compact Persian badge and interpretation guidance |
| Attention | `build_management_decision_support_context.attention_items` | Existing deterministic FOLLOW_UP and limited/insufficient-data conditions; primary. FOLLOW_UP is an outcome count, not an OPEN/overdue FollowUpTask count |
| Executive brief | Existing backend decision-support performance highlights derived from executive context/rankings | Deterministic factual observations; concise secondary brief, with uncertainty. No LLM attribution |
| Highlights | Existing best conversion/engagement product, best revenue brand, best conversion salesperson | Descriptive backend rankings; merged into brief to avoid repeating the old highlights block. Single-salesperson winner claim suppressed |
| Trends | `build_management_kpi_trend_contract.trends` | Existing conversion/revenue series; secondary, explicit dates and exact-value tables |
| Recommendation analysis | `dashboard.performance.recommendation_type.items` | Existing type/outcome aggregation; expandable diagnostics and link to Recommendation Performance |
| Product/category/brand | `dashboard.performance` items | Preserved as expandable diagnostic tables |
| Sales team | `dashboard.performance.salesperson.items`, also the source used by the existing sales-team contract | Actual evaluated/presented counts, purchases, conversion, engagement, revenue, quality; preserves source order; no invented quota or ranking |

The prior KPI cards, long narrative, highlights, tabbed analysis and team summary repeated several facts. The new hierarchy is pulse → needs attention → concise brief → trend → team → recommendation/deeper analysis. Detailed methodology is collapsed.

## Time and ranking semantics

All summary metrics cover all recorded history; there is no current-period filter or previous-period comparison. Periods use Visit.visit_date, not outcome creation time. Weeks run Monday–Sunday; months are Gregorian calendar months. Only periods present in the data are emitted. Missing periods are not synthesized as zero.

Backend rankings are supported but descriptive: eligible rows have presented > 0; ranking selectors use metric-specific tie breakers. Salesperson rows retain backend conversion-descending/presented-descending order, followed by employee code. No frontend sorting, new thresholds, growth, target attainment or weak-performer alerts were introduced.

Charts use independent bars and real dates without interpolation. Zero or one presented-data period gets a clear sparse-data state. All exact daily/weekly/monthly values remain accessible in tables, including periods without presented outcomes. Long chart series scroll locally. Number formatting is presentation only.

## Implementation and files

- `apps/management/views.py`: small context addition calling existing dashboard, trend and decision-support builders. The staff decorator runs before these calls. Values are passed through without new calculations. Server rendering makes the workspace and exact tables available without JavaScript or optional Ollama latency.
- `templates/management/dashboard.html`: compact Persian hierarchy, five KPIs, supported attention items, concise deterministic observations, period selector, team and expandable diagnostics.
- `templates/management/_number.html`: safe numeric formatting with Persian numeral enhancement.
- `templates/management/_quality.html`: Persian semantic state labels.
- `templates/management/_performance_table.html`: shared table for team and diagnostic dimensions; recommendation-type rows include interest/follow-up/rejected/not-presented counts.
- `templates/management/_period_table.html`: accessible exact-value tables.
- `static/management/css/dashboard.css`: scoped ds-token layout, responsive KPI/attention/trend grids, focus and local table/chart scrolling. Replaces the old page-specific decorative styles; shared styles remain unchanged.
- `static/management/js/dashboard.js`: presentation-only Persian formatting and SVG bars from safely embedded existing series. Replaces asynchronous page construction; no business calculations or API writes.
- `apps/management/tests_workspace.py`: six isolated rendering/security/data regressions.
- This checkpoint.

The management API and its executive narrative generation remain available with their existing contracts. The page uses the authoritative structured facts for its short brief; it no longer requests the optional narrative merely to render management content. Recommendation Performance itself is untouched.

## Authorization and drill-down

HTML remains guarded by active Django staff membership; API remains IsAdminUser. Staff retains the existing general Customer360 override, but this aggregate dashboard has no customer rows and introduces no customer-specific links. Salesperson-only visit/follow-up actions and impersonation controls are absent.

Supported deeper route: `/management/recommendations/performance/` (staff-only HTML; its overall performance API also checks staff). No manager salesperson-detail route exists; no fake drill-down is presented. In-page attention navigation points to existing performance diagnostics or methodology.

## Tests and validation

Executed using the existing virtual environment, without network/Ollama or demo fixtures:

- `.\venv\Scripts\python.exe manage.py test apps.management apps.visits.tests_authorization apps.core.tests apps.recommendations`: **53 passed**.
- `.\venv\Scripts\python.exe manage.py test`: **101 passed** (95 baseline + 6 new).
- `.\venv\Scripts\python.exe manage.py check`: **no issues**.
- `node --check static/management/js/dashboard.js`: **passed** using existing Node; no packages installed.
- `git diff --check`: **passed** (existing Windows LF/CRLF conversion warnings may appear).
- Database SHA256 matches its starting value.

New coverage: staff/anonymous/salesperson boundaries; actual KPI values; LIMITED_DATA, sparse and empty states; supported attention and its follow-up meaning; actual trend dates/series; team/single-member state; recommendation-type labels/outcome columns; deeper route visibility; no customer/action leakage; shared shell/assets; canonical latest-result behavior; no business writes or AI invocation on page GET. Earlier fixture-only failures were corrected before the passing runs. No unrelated regression was found.

## Read-only demo findings and manual review

manager1 is active staff. At inspection, management contracts reported: 7 evaluated and 7 presented outcomes, 1 purchase, sales amount 10,000, conversion 14.29%, engagement 100%, 3 FOLLOW_UP outcomes and LIMITED_DATA. Two recommendation types: REPEAT_PURCHASE and CATEGORY. Only SP001 / Ali Ahmadi has analytics rows. Dates: 2026-08-14, 2026-08-15, 2026-08-19; two weekly periods; one monthly period. These values reflect manual demo activity, not fixtures manufactured for this task.

No browser is connected (browser list empty), so rendered desktop/mobile screenshots and live JS interactions were not verified by the agent. Manual visual approval is required:

1. Sign in as manager1 → نمای مدیریت (`/management/`). Hard refresh to load the new versioned page assets.
2. First viewport: compact title/all-history context, five KPIs, Persian numbers/grouping, visible data-quality badge and prominent نیازمند توجه.
3. Attention: expect three follow-up outcomes and a limited-data warning. Verify the follow-up text does not claim three open/overdue tasks. Open the methodology link and expand its explanation.
4. Brief: concise backend-derived product/brand observations; no AI-generated claim and no single-member team winner claim.
5. Trends: daily and weekly show independent bars with dates/values. Change to ماهانه: expect the one-period message instead of a fabricated trend. Expand مقادیر دقیق دوره‌ها to compare source values.
6. Team: one SP001 row, explicitly explaining that comparison between salespeople is unavailable.
7. Expand recommendation types and product/category/brand details; verify truthful outcome columns and quality states. Open جزئیات عملکرد پیشنهادها to reach the existing diagnostic page.
8. At roughly 390px width, KPIs become two columns; attention/charts stack and wider tables/charts scroll locally. Check RTL reading order and visible Tab focus on links, selector, disclosures and scroll regions.

## Known limits

Currency unit is not defined by the current contract. Dates remain Gregorian; KPI scope is all history. There is no prior-period comparison, manager task queue, salesperson-detail drill-down or organizational hierarchy. Backend contract composition repeats analytics queries; this task does not optimize that existing service architecture. The page is rendered by Django; unanticipated database/service failures follow existing server error handling. Charts require JavaScript, while all metrics and exact tables remain accessible without it. Single-member/sparse demo data limits meaningful comparisons. No further task starts before manual approval.

## Restart recovery and Manager Customers correction — 2026-10-05

The preceding sections record the original 002-F implementation and validation.
After an unexpected restart, recovery confirmed fast-track HEAD and the local
origin/fast-track reference at 712e31e. A subsequent authorized fetch confirmed
the same baseline. All surviving uncommitted work was preserved. Two untracked
files were wholly NUL-filled: templates/customers/manager_workspace.html (4,291
bytes) and apps/customers/tests_manager_workspace.py (7,039 bytes). Both were
rebuilt from the surviving views, models, shared access policy and design system.
Other interrupted source/assets/checkpoint files were intact. The recovered
002-F dashboard was not redesigned.

### Approved interim scope and product wording

Task 001-B.1B documents a temporary authenticated Django staff customer-read
override. The approved Fast Track continuation preserves that override for all
active company customers. The shared customer_access_queryset applies it before
list, search, HTML Customer360 and Customer360 API lookups. The surviving helper's
active-record filter remains. Non-staff access still requires an active salesperson
profile and active CustomerAssignment, with unchanged assignment-date semantics.

There is no Manager -> Salesperson/Team domain relationship. Salesperson.user and
CustomerAssignment express user/profile and salesperson/customer relationships;
management analytics aggregates do not define a managed team. Therefore this
workspace and its navigation say «مشتریان», not «مشتریان تیم». Its Persian help
explicitly explains that management reads cover all active company customers and
are not limited to a particular team. No model, schema or migration was added.
Future team-limited access requires an explicit, authorized team hierarchy and
matching server-side scope; it cannot be inferred from SP001 or demo analytics.

### Recovered behavior and files

- templates/customers/manager_workspace.html: shared Persian RTL shell, code/name
  search, real result count, 20-item pagination retaining the query, customer
  identity/code/city, active salesperson assignments, grade/translated segment,
  existing last-purchase date, actual open-follow-up count/nearest due date,
  missing-data/no-result/empty states and links to the existing Customer360.
- static/management/css/customers.css: compact ds-token cards/facts, responsive
  four/two/one-column details and keyboard focus on contextual help. No dashboard
  stylesheet or JavaScript changes during this continuation.
- apps/customers/views.py: retained interrupted list/search and inspection
  implementation; Customer360 now passes the authorized queryset into its existing
  loader instead of performing a subsequent unscoped customer-master lookup.
- apps/customers/services.py: optional keyword-only queryset in the existing
  lookup helpers; existing trusted internal callers retain their default behavior.
  Recommendation/commercial/snapshot calculations are unchanged.
- templates/base.html: truthful «مشتریان» navigation (matches committed wording).
  The surviving design_system_help.html uses name/code search for staff and the
  existing code field for salespeople.
- templates/core/customer_360.html and _ai_command_center.html /
  _ai_recommendations.html / _customer_hero.html / _follow_up_card.html: management
  inspection wording, Persian segment labels, customer-list return link, no
  salesperson-plan link or follow-up-preparation CTA, no visit controls, outcome
  buttons or outcome modal. Existing customer-only explanatory Copilot remains.
- apps/customers/tests_manager_workspace.py: twelve isolated regression tests.
  Existing apps/management/tests_workspace.py and 002-F regressions are preserved.
- This checkpoint records recovery, policy, verification and manual review.

Manager inspection ignores visit_id, including crafted URLs, and does not select
an operational visit. A staff account without an active salesperson profile
cannot start/complete visits, record outcomes or change follow-up status. Existing
dual-role users still inspect customers as staff and retain their own salesperson
operations through existing endpoints; they cannot impersonate another owner.
No blanket staff ban was added to those endpoints. No second Customer360 exists.

Missing/inactive/out-of-scope direct HTML requests use the same generic Persian
404 page without customer identity. API lookups use the same scoped 404 boundary.
Search and pagination counts derive from the authorized active-customer queryset.
Assigned-customer views and salesperson operational controls remain unchanged.

### Original reported 404 and database evidence

The reported manager1/C0003 404 could not be reproduced against the committed
baseline and recovered database: manager1 was active staff, C0003 was active with
an active SP001 assignment, and the committed lookup evaluated in memory returned
200. Its original failure was at the scoped exact-code/active-record lookup; the
precise earlier request/runtime/database cause is not established. Absence of a
manager salesperson profile is not a cause under the existing staff override.

The database hash observed at recovery differs from the original 002-F validation
hash recorded above; this audit cannot establish when or why it changed. SQLite
read-only quick_check returned ok. No database restore, staging, seed/reset,
migration or canonical-demo change was performed. Before and after this
continuation, db.sqlite3 SHA256 was identical:

`F8DC98A044AC00260FB6D1F3643E8E46B9CB5C377CAC166D970C779E6707BA9B`

### Executed continuation validation

- Initial focused run before the scoped-loader extension: 61 passed.
- `.\venv\Scripts\python.exe -B manage.py test apps.customers apps.management apps.visits.tests_authorization --noinput`: **62 passed** after all code changes.
- `.\venv\Scripts\python.exe -B manage.py test --noinput`: **113 passed** (101 recovered baseline + 12 customer regressions).
- `.\venv\Scripts\python.exe -B manage.py check`: **no issues**.
- `node --check static/management/js/dashboard.js`: **passed**.
- `git diff --check`: **passed**, with Windows LF/CRLF conversion warnings only.
- Test records and operational mutations were confined to Django's separate test
  database. No demo fixtures, Ollama calls or network-dependent tests were needed.
- GET query capture asserts no INSERT/UPDATE/DELETE for manager list/search,
  direct inspection and Customer360 API. Tests also cover pure-staff mutation
  rejection and preserved dual-role ownership rules.

New tests cover company-wide active scope (including unassigned customers),
real context/missing data, code/name search on both route prefixes, pagination,
empty/no-result states, login/profile boundaries, direct HTML/API Customer360,
ignored visit IDs, hidden operational controls, generic existence non-disclosure,
salesperson assignment/revocation and compatible scoped/default loader behavior.
No source NUL bytes remain in the recovered files. Browser screenshots, responsive
appearance and live JavaScript interactions still require manual visual approval;
template rendering/regression tests do not substitute for that review.

### Exact manual review

1. Sign in as manager1 at `/accounts/login/`. Open `/management/` and hard refresh.
   Confirm the recovered 002-F dashboard hierarchy, tables and period selector
   remain as previously reviewed; no dashboard redesign was introduced.
2. Open «مشتریان» at `/customers/`. Confirm the management heading, code/name search
   and «مبنای نمایش اطلاعات» explanation of all active company customers. There
   should be no «مشتریان تیم» label. With the current 30 active records, the first
   page contains 20 cards and the next contains 10.
3. Search `C0003`; confirm its card appears. Copy its displayed customer name and
   search that name; C0003 should still be among the matching results. Search
   `NO_SUCH_CUSTOMER_002F`; confirm the no-result message, then clear the search.
4. Review assignment, grade/segment, purchase date and open-follow-up information.
   Records missing a snapshot/assignment/date/task should show factual missing-data
   text, not invented values. Check next/previous page navigation.
5. Search C0003 and choose «بررسی مشتری». Confirm existing Customer360 shows
   «بررسی مدیریتی مشتری», read-oriented recommendations/history/follow-up and
   «بازگشت به مشتریان». The salesperson-plan link, start/complete controls, outcome
   controls/modal and follow-up-preparation CTA must be absent.
6. Open `/customers/?customer_code=C0003&visit_id=1`; inspection must still have no
   operational visit controls. Open
   `/customers/?customer_code=NO_SUCH_CUSTOMER_002F`; expect the generic Persian 404.
7. At about 390px, confirm cards/search stack, facts fit the viewport and pagination
   remains usable. At tablet/desktop widths, confirm readable RTL layout. Tab
   through search, customer links, contextual help and pagination; check focus.
8. Sign out and sign in as sales1. Open `/customers/?customer_code=C0003`; confirm
   authorized Customer360 and «برنامه ویزیت امروز» remain available. Open an owned
   visit from «فضای کار روزانه» and confirm the existing lifecycle controls and
   outcome availability match its current status; do not mutate demo records just
   for visual review.
9. As sales1, open `/customers/?customer_code=C0001` (unassigned in the recovered
   database) and `/customers/?customer_code=NO_SUCH_CUSTOMER_002F`. Both must return
   the same generic 404 presentation without customer identity. The corresponding
   `/api/customers/v1/customer-360/<code>/` requests must both return 404.

Known remaining limits: management scope is temporary company-wide staff scope;
no real team hierarchy exists; dates are Gregorian; list context is existing
snapshot/task data rather than new analytics; unexpected server/service failures
use existing error handling. No commit/push or Task 002-G. Stop for visual approval.

## Final Manager Customers UI polish — 2026-10-05

This presentation-only pass replaces the tall `/customers/` cards with a compact
RTL management table above 1100px. Each customer occupies one row containing
name/code/city, existing active salesperson assignments, separate «رتبه» and
«گروه مشتری» columns, existing purchase date, open-follow-up count/nearest due
date, and the existing «بررسی مشتری» action. Rows adapt into compact cards below
that breakpoint, with two cards per row on tablets from 700px and one on phones.
Mobile facts retain visible labels, wrapping content and a full-width action
using the existing 44px minimum control height. Existing ds tokens, search,
clear-search, no-result states, pagination and scope explanation are preserved.

The existing Customer360 hero adds «گروه مشتری:» in manager inspection only;
its separate «رتبه» label and all supplied values remain unchanged. Salesperson
presentation and authorization are preserved. No backend, dashboard, performance,
API, model, schema, migration or business-behavior changes were made in this pass.

Changed files in this pass:
- `templates/customers/manager_workspace.html`
- `static/management/css/customers.css`
- `templates/core/customer_360/_customer_hero.html` (manager-only label)
- `apps/customers/tests_manager_workspace.py` (presentation assertions only)
- This checkpoint.

Validation:
- `.\venv\Scripts\python.exe -B manage.py test apps.customers apps.management apps.visits.tests_authorization --noinput`: **62 passed**.
- `.\venv\Scripts\python.exe -B manage.py test --noinput`: **113 passed**.
- `.\venv\Scripts\python.exe -B manage.py check`: **no issues (0 silenced)**.
- `node --check static/management/js/dashboard.js`: **exit 0**.
- `git diff --check`: **exit 0**, with existing Windows LF/CRLF warnings only.
- Read-only SQLite + RequestFactory checks for manager1: C0003 code search,
  name search and direct inspection with a supplied visit ID all returned **200**;
  inspection retained no operational visit/outcome controls; captured business
  writes: **0**. Existing C0003 grade **C** and segment **HIGH_VALUE** were retained.
- `db.sqlite3` SHA256 before and after this pass, unchanged:
  `10CA409A53BA0BC5EBDD8996E91110CF931A9D8113C11F767E8206AE6D61AE3F`.

The branch was already synchronized with origin/fast-track. The working tree
contained the earlier 002-F implementation and a modified demo database on entry;
those changes were preserved. No database restore/reset/migration, commit or
push; no Task 002-G work.

Final visual review: hard refresh `/customers/` on desktop and confirm 20 compact
rows with separate grade/segment columns. Review at 390px, 768px and desktop
widths for wrapping, readable spacing, visible focus and tappable actions. Search
C0003 by code/name, clear the search, review a no-result query and pagination,
then inspect C0003 with its existing values. Automated browser review was not
available because no browser was connected; responsive appearance and lack of
horizontal overflow still require final manual visual approval. Stop here.

## Office exit / authorized fast-track handoff — 2026-10-05

The user authorized checkpointing the completed/reviewed Manager Dashboard and
Manager Customers/search/authorization work together, using commit message
`feat: productize manager sales workspace`, then pushing only `fast-track`.
The preceding no-commit/manual-review notes describe earlier work sessions.

Before staging, `fast-track` remained at `712e31e` and matched origin after fetch.
All 23 intended source/test/template/static/checkpoint files were inspected;
the dashboard asset reductions are the approved server-rendered UI replacement.
No empty files, invalid UTF-8, NUL/replacement characters, trailing whitespace,
credential-pattern matches, generated junk, temporary files or unrelated changes
were found in the intended files. The Manager Customers work adds no JavaScript.

Final handoff validation:
- `.\venv\Scripts\python.exe -B manage.py check`: **no issues (0 silenced)**.
- `.\venv\Scripts\python.exe -B manage.py test`: **113 passed**. `-B` suppresses
  bytecode generation; tests use Django's separate test database.
- `node --check static/management/js/dashboard.js`: **exit 0**.
- `git diff --check`: **exit 0**, with existing Windows LF/CRLF warnings only.
- Final security review confirmed existing staff-only dashboard access,
  company-wide active-customer management scope, scoped name/code search,
  read-only manager inspection, preserved salesperson assignment/ownership
  boundaries and generic out-of-scope/missing-customer responses. Passing tests
  verify no unauthorized customer identity/count exposure or GET business writes.
- Read-only SQLite/RequestFactory verification: manager1 C0003 code search,
  name search and direct inspection (including a supplied visit ID) returned
  **200** each, with **0 business writes** and no operational visit/outcome
  controls. Its supplied grade **C** and segment **HIGH_VALUE** remain unchanged.

`db.sqlite3` was already modified on entry and is excluded from staging/commit.
Its SHA256 before and after handoff validation is identical:
`E6EA4D6B87BB1125B44392D6E052912E76160491F895780D2759E0ACF8E1CA7B`.
This differs from the earlier UI session's recorded hash; the intervening change
is outside this handoff. No database restore/reset, demo command or migration
was run. Task 002-G was not started. Stop all project work after push verification.
