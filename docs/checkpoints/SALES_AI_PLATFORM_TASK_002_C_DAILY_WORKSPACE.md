# Task 002-C — Daily Workspace productization

Baseline: fast-track, 76159f0. Builds on approved 002-A top shell and 002-B
design tokens. No view/service/API/model or authorization changes.

## Presentation

- Compact Persian header with actual salesperson identity and today's date.
  Dates remain Gregorian and are explicitly labeled; no calendar dependency.
- Five real operational summary counts in one dense strip; real high/medium/
  normal counts from the existing priority_summary, with text and semantic color.
- Owned today's visits retain their backend priority order. Visit cards become
  the primary work area; targets remain available in an expandable secondary
  section after the visits, with existing actual/remaining/achievement values.
- Cards show customer identity, priority, visit state, primary recommendation,
  next action, existing inventory/promotion signals and open follow-up context.
  No recommendation/unknown inventory states do not fabricate business facts.
- Priority reasons, recommendation evidence, sales talk, promotion terms and
  target relevance are available through native details elements. Existing
  priority reason strings are translated in the template without changing scores.
- State-specific primary link labels: preparation/start for PLANNED, continue/
  outcome for IN_PROGRESS, summary for COMPLETED, customer information for
  CANCELLED. These are navigation links to the existing Customer360 URL, not
  direct mutations or new transitions. Every visit entry preserves visit_id.
  Starting/completing still occurs through the existing Customer360 controls.

## Files and verification

Template: templates/visits/dashboard.html; card partial: visits/_visit_card.html.
Layout CSS: static/visits/css/daily_workspace.css. All appearance uses ds-*
classes/tokens; the large page-owned inline stylesheet is removed. No page JS
was previously present and none is introduced. Shared assets and feature pages
outside Daily Workspace are unchanged.

apps/visits/tests_workspace.py uses isolated data and real context builders to
verify dates/ownership, genuine priority counts/order, all visit-state labels,
context-preserving navigation, empty/no-recommendation/profile errors and targets.
No network, Ollama or demo-data mutation is needed.

## Manual approval checklist

Sign in as sales1 and open /api/visits/. Refresh after any external seed/reset.
1. Header: compact salesperson identity and real date; five summary counts.
2. Priorities: high/medium/normal counts, distinct color plus text; expand help.
3. High-priority card, if one exists today: customer prominent, red priority
   accent, distinct state badge, product/next action and compact commercial facts.
4. Primary action: label follows state; it opens Customer360 with that visit.
   The link itself must not start or complete a visit.
5. Customer entry: secondary «نمای ۳۶۰ درجه مشتری» preserves code and visit_id.
6. Responsive: below 700px context stacks and KPIs use three columns; below
   420px KPIs use two columns and visit actions fill the card width. Check Tab
   focus and Enter expansion/navigation, long customer/product names and RTL.

Demo records remain external to this change. Missing today's visits or high
priority data produce truthful empty/normal states; no automatic seed/reset.
Visual approval is pending manual review. No subsequent task is started.
