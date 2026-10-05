# Task 002-D — Customer360 decision/action workspace

Baseline: fast-track, cbf9a1211f65c4a8f55a7447ede326f52462ad8b
(`feat: productize daily sales workspace`). Clean and synchronized with origin
before edits. Follows approved 002-A shell, 002-B design foundations, 002-C
Workspace, 001-B.1B customer boundary and 001-D demo continuity.

## Scope and files

Presentation only; no backend view/context/API/service changes. Existing
sales_session already supplies commercial score, priority, inventory, next
action and talk track for both customer-only and visit-based contexts.

- templates/core/customer_360.html: page hierarchy and disclosure.
- Existing customer_360 partials: _customer_hero.html, _sales_context.htm,
  _ai_command_center.html, _ai_recommendations.html, _search.html.
- New _recommendation_type.html: reused Persian presentation labels.
- static/core/css/customer_workspace.css: scoped layout/compatibility rules using
  ds tokens. Existing CSS retained for history, diagnostics and outcome modal.
- static/core/js/customer_360.js: only two displayed status messages translated;
  IDs, selectors, handlers, requests and state transitions remain unchanged.
- apps/customers/tests_productization.py: isolated rendering/security regressions.

## UX decisions

Compact identity includes code/location/grade/phone, segment and known purchase
timing. Current visit shows real date, salesperson, existing state and action.
Customer-only navigation clearly says that no visit is selected or created.
Primary decision is dominant and adjacent to Sales Copilot: actual product,
recommendation score/confidence/type, commercial score/priority, next action,
reason, existing inventory warning and eligible promotion information.

Recommendations retain backend rank/order. Each card identifies primary versus
alternative and keeps its own outcome data attributes. Alternative selection
does not recalculate/switch the primary commercial decision. Native details
contain reasons and outcome buttons; no speculative alternative commercial
signals are added. Outcome controls are initially disabled except IN_PROGRESS;
existing JS still updates their availability after successful visit actions.

Compact real customer KPIs follow the action zones. History, customer analysis,
recommendation diagnostics, visit results and follow-up remain reachable through
collapsed sections. No fake recommendation or missing-data metric is generated.
Missing AI context shows a message; generation remains explicit, with existing
authorization, provider fallback and error behavior intact.

## Authorization and continuity

The shared customer-access queryset is untouched. Active profile/assignment and
staff override remain server-side; own historical visits do not bypass current
customer access. Original validated visit_id stays in page JS, search hidden
field and action data attributes. Search JS still drops it for changed customers.
Invalid/other-customer visit IDs retain the existing warning and null context.
Opening Customer360 performs no business writes and does not invoke Ollama.

## Validation and manual review

Focused tests cover assigned/staff/anonymous/unassigned/missing-profile access,
both HTML prefixes, visit/no-visit and invalid-visit contexts, primary action,
ranked alternatives, all outcome states, no recommendations, missing snapshot,
optional absent AI context, shell assets, and no INSERT/UPDATE/DELETE on GET.
Fixtures are independent of tracked db.sqlite3; no network/Ollama required.

Executed with the existing virtual environment:
- `manage.py test apps.visits.tests_continuity apps.visits.tests_authorization`: 44 passed.
- `manage.py test apps.customers.tests_productization`: 9 passed.
- `manage.py check`: no issues.
- `manage.py test`: 87 passed.
- `git diff --check`: passed.
- Tracked database SHA-256 unchanged:
  `2D4A7B899EB6189A62DAF3956B27519FA2EECAA86649791E00E2877D04116703`.

Manual: sign in as sales1 → فضای کار روزانه → a HIGH priority visit if available
→ نمای ۳۶۰ درجه مشتری. Verify compact identity, obvious visit state, dominant
product/next action, adjacent assistant, secondary ranked alternatives, compact
KPIs, collapsed details, RTL ordering and preserved visit_id in the URL.
Expand «اطلاعات و تحلیل تکمیلی مشتری» or an alternative's «دلیل پیشنهاد و ثبت
نتیجه». Ask «پیشنهاد اصلی را چگونه مطرح کنم؟» without recording an outcome.
Check narrow viewport stacking, Tab focus and Enter expansion. Do not start,
complete or record outcomes solely for visual review.

## Limits

No connected browser was available for automated visual verification. Manual
approval remains required. Dates remain Gregorian. Reused secondary diagnostic,
history and modal components retain legacy styling/copy; their access and content
are preserved. Some stored business descriptions/category names may be English.
Only primary commercial context exists; alternatives do not invent stock/risk
assessments. No new roles, schema, font/icon library, dependency or demo seed/reset.
No next task, commit or push.
