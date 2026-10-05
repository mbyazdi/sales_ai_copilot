# Task 002-E — Follow-up Workspace

## Baseline and scope

- Branch: fast-track; HEAD: c8ee6867e276c021d28718dd1ca30b7491219cdb.
- Fetch completed; HEAD/origin divergence: 0 / 0.
- Initial working tree: only the expected local db.sqlite3 modification.
- Database starting/ending SHA256: BB59FFE2292BAB200FF64BEFD9AE3C8DD5BE80C940AB934742D6BCFF244E4276.
- Scoped Persian RTL productization; no backend, workflow, API or authorization changes.

## Existing business behavior

`sync_visit_outcome_state` creates or updates an open FollowUpTask when a current resolved visit outcome is FOLLOW_UP and a follow-up date is supplied. The task carries the visit's customer and salesperson, date and notes. If no current FOLLOW_UP remains, open visit tasks are cancelled. Existing status actions support DONE and CANCELLED and synchronize visit follow-up flags/dates.

The HTML workspace requires login and an active Salesperson profile. It lists only that salesperson's OPEN tasks. Overdue is due_date before timezone.localdate(); today is equal; upcoming is after. Within each group the existing ordering is due_date, then id. Real counts come directly from the existing view querysets.

Tasks have mandatory customer/visit links, but no direct recommendation/product/outcome FK. Attribution to a particular product cannot be safely inferred from the visit. Missing notes or missing recommendation/outcome records are valid rendering cases.

## UX decisions and files

- `templates/core/follow_up_dashboard.html`: compact Persian page header, real four-count summary, ordered groups, helpful global empty state and Daily Workspace return route.
- `templates/core/partials/follow_up_group.html`: reusable group heading/count and individual empty states.
- `templates/core/partials/follow_up_card.html`: customer/code, due date, OPEN state, real notes or neutral next-step guidance, primary Customer360 link, existing completion/cancellation controls and expandable visit metadata.
- `static/visits/css/follow_up_workspace.css`: scoped layout using existing ds tokens; restrained semantic borders, wrapping actions, two-column mobile summary. No independent palette or font system.
- `apps/visits/tests_follow_up_workspace.py`: eight isolated fixture-based regression tests.
- This checkpoint.

The approved top-navigation shell, design foundations and existing follow_up_dashboard.js remain intact. Feature legacy Customer360 CSS is no longer needed by this page. Group order is overdue, today, upcoming; no scoring is introduced. No frontend business calculations or invented product/context data.

## Authorization and continuity

Ownership and active-profile requirements remain unchanged. Staff without an active salesperson profile cannot select or impersonate a salesperson. Other owners' customer names/codes do not appear. Each Customer360 link retains the task's customer_code and visit_id. Customer360 continues to enforce its shared current-customer policy; an owned historical task does not grant current customer access after assignment ends. Tasks remain historical ownership resources, as before.

Existing JS selectors/data attributes and status API routes are preserved. Rendering does not introduce writes. Customer codes use URL encoding; notes use Django escaping.

## Validation

- `git fetch origin`: succeeded; branch/HEAD/status/divergence verified.
- `.\venv\Scripts\python.exe manage.py test apps.visits.tests_follow_up_workspace apps.visits.tests_authorization apps.visits.tests_continuity`: 52 passed.
- `.\venv\Scripts\python.exe manage.py test`: 95 passed (87 baseline + 8 new).
- `.\venv\Scripts\python.exe manage.py check`: no issues.
- `git diff --check`: passed; Git may emit its existing Windows LF/CRLF conversion warning.
- `Get-FileHash db.sqlite3 -Algorithm SHA256`: matches starting hash.

New tests cover owned OPEN scope/counts, date boundaries and rendered ordering, global/per-group empty states, visit navigation and current customer denial after assignment ends, minimal source data/shared shell/action bindings, escaped real notes, and staff/missing/inactive/anonymous restrictions. Existing authorization and continuity tests remain unchanged.

## Demo/manual review and limits

Read-only demo inspection on 2026-10-05 found sales1 has three DONE tasks (IDs 1–3, C0001, visit 3) and zero OPEN tasks. No demo data was created or changed. The current demo therefore supports empty-state visual review, not populated-card review.

No browser is connected; desktop/narrow visual inspection was not performed by the agent.

Manual review:

1. Sign in as sales1; use the shell's پیگیری‌ها navigation.
2. Inspect compact پیگیری‌های من header, salesperson/date and four zero counts.
3. Inspect پیگیری بازی ندارید explanation: a dated نیاز به پیگیری visit outcome creates/updates work; use مشاهده ویزیت‌های من to return to Daily Workspace.
4. Check active top navigation, RTL order, Tab focus and a roughly 390px viewport: counts form two columns, header/actions wrap without a navigation rail.
5. When real open tasks exist through ordinary business use, verify overdue/today/upcoming order and customer/code/date/notes. Expand زمینه ویزیت و جزئیات; open مشتری و زمینه ویزیت and verify the URL retains customer_code and visit_id. No data mutation is needed for these inspections. انجام شد / لغو پیگیری are real write actions; do not click solely for visual review.

Dates retain the existing Gregorian date semantics (displayed Y/m/d); Jalali conversion is outside scope. No new product attribution, status workflow, completed history or manager selection is added. Existing browser alert/reload behavior for status errors/success remains. Visual approval remains pending. No models, migrations, dependencies, database contents, commits or pushes changed; stop before 002-F.
