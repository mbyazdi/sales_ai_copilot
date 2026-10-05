# Task 002-G — Recommendation Performance and Explainability workspace

## Approved baseline and scope

- Branch: fast-track. HEAD/origin at start: 27972b7ae23ddf83c04920d6bc3db63284d6837c.
- Fetch succeeded; initial working tree was clean. Read AGENTS.md, the product
  architecture/master plan, 002-B through 002-F checkpoints, authorization and
  demo-continuity checkpoints, and canonical analytics documentation.
- The user explicitly approved 002-G in the implementation conversation, including
  canonical management semantics. Earlier discovery found no repository-defined
  002-G scope; this checkpoint records the now-approved implementation.
- Persian RTL productization of /management/recommendations/performance/.
  Performance and evidence are primary; tuning remains a secondary admin area.
- No model, migration, dependency, engine/scoring/ranking, historical snapshot,
  customer scope, organizational hierarchy, global shell or demo-data changes.

## Metric-source decision

The existing /api/visits/v1/recommendations/performance/ uses
get_recommendation_performance(). It resolves Visit + Recommendation outcomes,
but increments presented for all resolved results, including NOT_PRESENTED.
Tuning suggestion generation also consumes this legacy service and stores its
performance snapshot. Changing it would affect public responses and tuning.

The management HTML view now calls the existing
build_recommendation_type_analytics(customer=None), V2.9.2, which consumes
build_outcome_analytics_contract(), V2.9.1. This is the same canonical source
used by the approved Manager Workspace. The view passes summary/items through;
no formulas or new thresholds are implemented in templates or JavaScript.

- Evaluated: resolved Visit + Recommendation pairs, using the latest result.
- Presented: PURCHASED + INTERESTED + FOLLOW_UP + REJECTED.
- NOT_PRESENTED stays in evaluated and its own count, outside rate denominators.
- Conversion: canonical purchased/presented. Engagement: canonical
  (purchased + interested + follow_up)/presented.
- No presented results: show unavailable rate (—), not a claim of zero performance.
- Real presented results with zero purchase: show the backend-provided zero rate.
- Sales amount: canonical recorded outcome revenue, with no assumed currency unit.
- Quality: existing NO_PRESENTED_DATA, INSUFFICIENT_DATA, LIMITED_DATA and
  SUFFICIENT_DATA states, based on the existing canonical presented counts.
- Type order is copied from the existing V2.9.2 descriptive analytics order.
  Recommendation ranking/scoring and legacy performance/learning classifications
  remain unchanged. Type comparisons explicitly warn about sample size.

The legacy performance endpoint, customer APIs, tuning generator, tuning snapshots
and all mutations remain compatible. Tuning help explicitly distinguishes its
stored historical methodology from the canonical live management indicators.
There is no silent recalculation of tuning snapshots or API contract change.

## Product behavior and files

- apps/management/views.py: canonical context plus read-only selected active
  RecommendationConfig. Selection matches the engine/tuning service:
  is_active, descending updated_at then id. No default record is created.
- templates/management/recommendation_performance.html: compact header, six
  real KPIs, methodology disclosure and responsive type comparison. Individual
  outcome counts and recorded revenue remain reachable under each row's details.
- templates/management/_recommendation_explainability.html: independent async
  summary/list states, help distinguishing confidence from sales-data quality.
- static/management/js/recommendation_explainability.js: existing staff-only
  diagnostics summary/list/detail GETs. First six cards are visible; further cards
  retain source order behind a disclosure. Expanding a recommendation fetches its
  saved reason, signals and score breakdown. No LLM or recommendation generation.
  Missing evidence is explicit. Detail retry and list/summary refresh recover from
  errors. Separate request revisions prevent stale refresh responses replacing
  newer results. Stored strings are escaped or inserted as text.
- templates/management/_recommendation_tuning.html: collapsed
  «تنظیمات و کنترل موتور پیشنهاد», selected active configuration values,
  historical-methodology help, existing filters/status/apply/rollback controls.
  Includes a CSRF token so direct page entry supplies the existing mutation header.
- static/management/js/recommendation_tuning.js: preserves existing mutation URLs,
  request bodies, CSRF header and same-origin credentials. Reads load on expansion;
  responses have loading/ready/empty/error states and refresh recovery. Missing
  values display —. Parameter labels and validation messages are Persian; technical
  identifiers and recorded reasons are available under disclosure. Mobile cells
  retain visible labels. Server validation and status transitions are unchanged.
- static/management/js/recommendation_performance.js: formats server-rendered
  numbers only; no legacy performance fetch or client business calculations.
- static/management/css/recommendation_performance.css: scoped ds-token layout,
  desktop tables/mobile labeled cards, evidence cards and progressive disclosure.
- apps/management/tests_recommendation_workspace.py: twelve isolated regressions.
- This checkpoint.

The active configuration display is a snapshot at HTML request time; refresh the
page after an authorized apply/rollback to see new values. Nine selected parameters
are shown, rather than presenting every internal engine constant as an editor.

## Authorization and safety

The existing staff_member_required decorator precedes canonical/config queries.
Global performance, diagnostic and tuning APIs keep their existing staff guards.
No customer lookup or operational mutation permissions are broadened. Shared
customer assignment scope, company-wide staff inspection, ignored manager visit
parameters and salesperson-owned visit/follow-up operations remain intact.

Page/async reads perform no business or configuration writes. Tuning only changes
through explicit existing POST actions. Approval-before-apply, range/delta/stale
validation and rollback remain server-controlled. No demo tuning action was run.

## Validation

Using the existing environment and isolated Django test database:

- python -B manage.py test apps.management.tests_recommendation_workspace
  apps.management.tests_workspace apps.visits.tests_authorization --noinput:
  **53 passed**, including twelve new workspace tests.
- python -B manage.py test --noinput: **125 passed** (113 baseline + 12 new).
- python -B manage.py check: **no issues (0 silenced)**.
- node --check on recommendation_performance.js, recommendation_explainability.js
  and recommendation_tuning.js: **passed**.
- git diff --check: **passed**; existing Windows LF/CRLF warnings only.

Regressions cover denial before context building, canonical denominator and
Manager Workspace parity, latest-result resolution, type breakdown/order,
empty/no-presented/sparse/real-zero states, retained evidence without LLM or engine
generation, staff-only real tuning IDs, CSRF denial and authenticated valid
requests, pending/approved/apply/rollback validation, stale/range/delta rejection,
actual active config selection and no default creation, unchanged tuning snapshots,
and no INSERT/UPDATE/DELETE for HTML/diagnostic/tuning-list GETs.

Headless Chrome reviewed a temporary HTTP snapshot rendered with manager1 via
RequestFactory and real existing diagnostics responses. Its Django connection
used SQLite mode=ro; captured business writes were zero. No login/session mutation
or production tuning POST was used. Browser assets are the actual changed files.
Preview files/profile/screenshots stay in the system temporary directory, outside
the repository; they are validation artifacts, not demo or product assets.

- Desktop 1440px, tablet 768px and mobile 390px: no whole-page horizontal overflow.
- Reviewed desktop/mobile performance, evidence and expanded tuning screenshots.
- Six initial evidence cards; remaining cards and tuning initially collapsed.
- Real evidence detail 423 expanded successfully with saved reason/signals.
- Real tuning list/filter bindings and labeled mobile cells rendered successfully.
- Browser response interception exercised evidence summary/list error, empty,
  recovery; detail error/retry/missing-evidence/real-data recovery; tuning
  loading/error/empty/recovery. No database fixtures were inserted for these states.
- No JavaScript runtime exceptions; zero non-GET/HEAD requests.

Database SHA256 before implementation and after tests/read-only browser review:

`2D4A7B899EB6189A62DAF3956B27519FA2EECAA86649791E00E2877D04116703`

The hashes match. Tracked db.sqlite3 is unchanged. No migration, seed/reset,
database restore, commit, push or Task 002-H.

## Current read-only demo findings

At inspection: seven evaluated and seven presented pairs, one purchase, amount
10,000, conversion 14.29%, engagement 100%, LIMITED_DATA; NOT_PRESENTED count zero.
Repeat purchase: four evaluated/presented, one purchase, conversion 25%.
Category: three evaluated/presented, zero purchases, conversion 0%.
There are 49 active recommendations and three stored tuning suggestions.

Suitable non-mutating detail: recommendation **423**, customer **C0003**, product
**PHI002 / Philips Electric Toothbrush**. It has a real saved reason, confidence
100, HIGH evidence, five active signals and a saved score breakdown. These are
recorded engine outputs, not guaranteed purchase probability or new AI narration.

## Manual visual approval

1. Sign in as manager1, open «عملکرد پیشنهادها» at
   /management/recommendations/performance/, and hard refresh.
2. Confirm the real summary above and matching Manager Workspace metrics. Expand
   «روش محاسبه و میزان اتکای داده» to inspect denominator/quality/revenue scope.
3. Compare خرید مجدد and پیشنهاد دسته; expand «جزئیات نتایج» for interest,
   follow-up, rejection, not-presented and revenue. This demo has no NOT_PRESENTED
   record; denominator exclusion was verified with isolated regression data.
4. Review active-recommendation quality separately from historical sales quality.
   Expand «سایر پیشنهادهای فعال» if necessary, find C0003 / PHI002 and open
   «دلیل پیشنهاد و شواهد». Inspect reason, confidence, signals and score composition.
   This only issues GET requests; no outcome or configuration changes.
5. Expand «تنظیمات و کنترل موتور پیشنهاد». Inspect selected active configuration,
   stored suggestion statuses, parameter reasons and filters. Do not click تأیید,
   رد, اعمال or بازگردانی solely for visual testing; these are real write actions.
6. Check 1440px, 768px and about 390px, type rows becoming labeled cards, keyboard
   Tab/Enter, focus rings and all disclosures. Wide desktop tuning tables scroll
   locally; mobile rows keep labels without page-wide overflow.
7. To inspect loading/errors without changing data, use browser request blocking
   or throttling for /api/recommendations/v1/diagnostics/ and tuning-suggestions/;
   refresh the relevant section, then unblock and retry. Empty/missing-evidence
   states were tested with interception and isolated fixtures, without demo edits.

## Limits

The product remains Django-rendered. There is no new chatbot, predictive model,
date/period filter, schema, independent frontend or organizational hierarchy.
Currency remains unspecified. Source product names and saved text can contain
English; new interface labels are Persian. Diagnostic/tuning APIs retain their
existing unpaginated payloads, and canonical analytics retain their existing query
cost. Browser verification used a read-only snapshot; authenticated live-server
inspection remains the user's final visual approval step. Stop before 002-H.

## Final UX polish — 2026-10-05

The subsequent approved pass changes presentation only. This section supersedes
the earlier layout and manual-review descriptions; initial validation and database
hash above remain the historical record of the initial implementation.

### Files changed in this pass

- templates/management/recommendation_performance.html
- templates/management/_recommendation_outcomes.html (new)
- templates/management/_recommendation_explainability.html
- templates/management/_recommendation_tuning.html
- static/management/css/recommendation_performance.css
- static/management/js/recommendation_explainability.js
- apps/management/tests_recommendation_workspace.py
- This checkpoint.

No backend, API, model, migration, calculation, recommendation order, tuning
behavior or authorization change was made during polish. The canonical metric
source and NOT_PRESENTED exclusion documented above remain intact.

### Presentation decisions

- Evaluated -> presented -> purchased is an ordered, labeled HTML flow using
  canonical server counts. Current data: 7 -> 7 -> 1. Three separate rate/revenue
  KPIs remain. Flow runs right-to-left on larger screens and stacks vertically
  at mobile width; arrows are decorative, labels/counts convey the meaning.
- Each recommendation type has a compact segmented outcome bar. CSS flex-grow
  receives existing integer counts directly, without new percentages. All five
  outcome categories have visible labels/counts including zeros. Patterns supplement
  color. Exact rates/revenue and the original detailed table remain behind
  "همه اعداد و جزئیات مقایسه"; analytics ordering is preserved.
- Existing HIGH/MEDIUM/LOW counts provide a factual Persian narrative and compact
  distribution. Current counts: strong 11, medium 34, limited 4. The narrative
  names the class with the largest recorded count; ties are explicit. Missing
  classifications omit the distribution. No aggregate quality grade or new scoring
  rule is introduced. Diagnostic flags remain behind a smaller disclosure.
- Cards default to product/context, type, recorded confidence/quality, the existing
  active signal with the largest recorded contribution, and recorded active count.
  This selects existing evidence, without calculating a new strength. Unknown or
  missing evidence remains explicit. "مشاهده دلیل و شواهد" lazily retrieves the
  unchanged detail API. Recorded reason, signals, rank, score and score composition
  remain available after expansion. The first six/source order remain unchanged.
- Recommendation 423 / C0003 / PHI002 shows Philips Electric Toothbrush, repeat
  purchase, 100% confidence, strong evidence, purchase-cycle evidence and five
  active signals while collapsed. Expansion reveals the saved Persian reason,
  final score 82, rank 1, all eight signal entries (five active) and saved score
  composition under its existing nested disclosure. Purchase-cycle contribution
  is the existing 45; no reason, confidence or score is generated.
- Tuning is titled "تنظیمات پیشرفته موتور پیشنهاد", at the bottom and collapsed
  by default, with controlled-configuration/admin-purpose copy. Its existing
  filters, values, statuses, CSRF and actions are retained unchanged.

### Validation after polish

- .\venv\Scripts\python.exe -B manage.py check: no issues (0 silenced).
- .\venv\Scripts\python.exe -B manage.py test apps.management --noinput:
  **55 passed**.
- .\venv\Scripts\python.exe -B manage.py test --noinput: **127 passed**.
- node --check for all three Recommendation Performance JavaScript files: passed.
- git diff --check: passed; existing Windows line-ending warnings only.
- git status --short and git diff --stat inspected. Initial uncommitted 002-G
  implementation remains; no commit/push or 002-H.
- Two focused presentation regressions verify canonical flow/bar values, default
  collapsed comparison/tuning, empty visuals and NOT_PRESENTED-only visuals.
  Existing management parity, read-only, security and tuning tests remain valid.
- Read-only SQLite mode=ro preview with manager1 and actual API responses; zero
  captured business writes. Chrome reviewed 1440px, 768px and 390px. No whole-page
  horizontal overflow, including expanded evidence/type details/tuning on mobile.
  Flow is horizontal at 1440/768 and vertical at 390. Screenshots inspected.
- Native summary keyboard Enter expansion verified. Labels/counts provide text
  equivalents; decorative bars/arrows are hidden from accessibility APIs; existing
  focus rings, busy/live/status/error semantics and mobile labels remain intact.
- Response interception checked summary/list/detail/tuning loading, empty, error
  and recovery without inserting demo data. Evidence summary tie, missing-class
  and unavailable-confidence states were also checked. No runtime exceptions or
  non-GET/HEAD requests; no tuning action was performed for visual testing.

Database was already modified relative to HEAD on entry to this polish pass.
It was preserved rather than restored. Before and after polish SHA256 match:

`EF6513572D171A768D4A58C1E3CC3C1655CE48DB7443D82BD6A510BB786F46ED`

The existing db.sqlite3 modified status is unchanged. No database business writes,
migrations, seeds, resets or restores were performed by this polish task.

### Updated manual visual approval

Sign in as manager1 -> "عملکرد پیشنهادها" ->
/management/recommendations/performance/ and hard refresh. Inspect 7 -> 7 -> 1,
the remaining KPIs and denominator help. Compare exact outcome legends; expand
"همه اعداد و جزئیات مقایسه" for rates and saved outcome/revenue detail. Inspect
the evidence narrative/distribution, then C0003 / PHI002's collapsed card and
"مشاهده دلیل و شواهد". Expand "ترکیب امتیاز ثبت‌شده" if desired. These reads do
not mutate recommendations or outcomes. At the bottom, inspect the initially
collapsed advanced tuning area and expand its configuration/filters; do not use
approval/apply/rollback for visual testing. Repeat at 1440, 768 and about 390px.
Use browser throttling/request blocking to inspect async loading/error/recovery;
empty cases were verified with interception and isolated regression data.

Remaining limits: current demo has no NOT_PRESENTED outcomes; isolated tests cover
exclusion. Stored product names/reasons can contain English; currency is unspecified.
Browser verification used a read-only rendered/API snapshot. The user subsequently
granted visual approval for the current workspace. No new dependencies or LLM calls.

## Finalization and visual approval — 2026-10-05

The user explicitly granted visual approval for the existing 002-G implementation
and authorized this checkpoint, validation, commit and push to fast-track. No
additional UX, features, business logic or polish changes were made in finalization.

The approved final hierarchy is: compact performance header; canonical flow plus
conversion/engagement/revenue KPIs and methodology help; type outcome comparison
with expandable exact details; explainability and evidence-quality summary;
concise recommendation cards with lazy reason/evidence expansion; engine explanation
help; and collapsed advanced tuning at the bottom. The metric-source decision,
authorization constraints and known data limitations above remain in force.

Final source review covers eleven scoped view/test/template/static/checkpoint
files. No model, schema, migration, dependency, global shell, public API contract,
recommendation scoring/ranking, analytics calculation, tuning validation/mutation
contract or historical snapshot changes were introduced. Management HTML reuses
the canonical analytics builder; legacy performance API/tuning snapshots remain
compatible. Staff guards, CSRF and customer authorization boundaries remain intact.

Final validation rerun on the approved build:

- .\venv\Scripts\python.exe -B manage.py check: no issues (0 silenced).
- .\venv\Scripts\python.exe -B manage.py test apps.management --noinput:
  **55 passed**.
- .\venv\Scripts\python.exe -B manage.py test --noinput: **127 passed**.
- node --check for recommendation_performance.js, recommendation_explainability.js
  and recommendation_tuning.js: passed.
- git diff --check: passed; existing Windows LF/CRLF warnings only.
- Fetch confirmed fast-track HEAD and origin/fast-track at the approved baseline
  27972b7ae23ddf83c04920d6bc3db63284d6837c before committing.

db.sqlite3 was already locally modified on entry. Its SHA256 before and after
final validation is identical:

`EF6513572D171A768D4A58C1E3CC3C1655CE48DB7443D82BD6A510BB786F46ED`

The database is explicitly excluded from staging/commit and its local modification
is preserved. No demo data alteration, migration, seed/reset, tuning visual-test
mutation or database restore was performed. Test mutations use isolated test data.
Temporary browser artifacts remain outside the repository. Only approved 002-G
files are eligible for the authorized commit. Development stops after push
verification; Task 002-H is not started.

## Approved visual patch — 2026-10-05

Final live visual approval granted for the solid muted outcome bars and solid
evidence-quality distribution. Both use 12px bars, rounded corners and quiet exact
count summaries. Patterns, hatching and gradients are removed; scoped outcome and
evidence palettes retain distinct semantics. Zero-count segments have zero width.
Type/conversion headers and expandable exact details remain available.

Patch scope: recommendation_performance.css and _recommendation_outcomes.html,
plus this approval note. No business/calculation/classification/API behavior,
authorization, recommendation ordering/scoring, tuning or database changes.
Final validation: Django check clean; 55 management tests passed; all three
Recommendation Performance JS syntax checks and git diff --check passed.
Database SHA256 before/after remains
`EF6513572D171A768D4A58C1E3CC3C1655CE48DB7443D82BD6A510BB786F46ED`.
Its pre-existing local modification is preserved and excluded from the commit.
