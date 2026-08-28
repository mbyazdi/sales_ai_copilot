# SALES AI COPILOT — V3.0.10.9
## Demo Reset & Repeatability

**Status:** Completed / Validated
**Milestone:** V3.0.10.9

## Objective
Provide a safe, deterministic and repeatable reset for the Daily Workspace demo without globally wiping the demo database.

## Scope
The reset is intentionally limited to the active salesperson `SP001`, `timezone.localdate()`, and these demo customers:

- `C0003`
- `C0005`
- `C0013`
- `C0014`
- `C0029`

## Implementation
New management command:

`apps/visits/management/commands/reset_daily_workspace_demo.py`

Run with:

```bash
python manage.py reset_daily_workspace_demo
```

The command runs inside `transaction.atomic`.

It preserves the matching Visit rows and resets their mutable workflow state to:

- `status = PLANNED`
- `customer_request = ""`
- `customer_feedback = ""`
- `competitor_information = ""`
- `notes = "V2 Daily Workspace Demo visit."`
- `order_created = False`
- `order_amount = 0`
- `follow_up_required = False`
- `follow_up_date = None`

It deletes only scenario artifacts linked to the scoped demo visits:

- `SalesOutcome`
- `FollowUpTask`
- `VisitCustomerSnapshot`
- `VisitCommercialSnapshot`

The two snapshot types must be removed because they are immutable point-in-time snapshots captured when a visit starts. Deleting `SalesOutcome` is an explicit demo-reset exception; normal product behavior remains append-only.

## Data Preserved
The reset does not intentionally modify Customer, Product, Recommendation, purchase/sales history, CustomerAssignment, Salesperson master data, or Recommendation Engine v1 logic.

## Seed Baseline Validation
On `2026-08-28`, `seed_daily_workspace_demo` produced five `SP001` visits:

- Visit 22 — `C0003` — `PLANNED`
- Visit 23 — `C0005` — `PLANNED`
- Visit 24 — `C0013` — `PLANNED`
- Visit 25 — `C0014` — `PLANNED`
- Visit 26 — `C0029` — `PLANNED`

Initial scenario artifact counts were all zero.

Result:

`SEEDED BASELINE VALID: True`

## Real Pre-Reset Workflow Validation
Visit 22 / `C0003` was started through the real Customer360 UI.

After Start:

- status: `IN_PROGRESS`
- SalesOutcome: `0`
- FollowUpTask: `0`
- VisitCustomerSnapshot: `1`
- VisitCommercialSnapshot: `1`

Result:

`START STATE VALID: True`

A `FOLLOW_UP` outcome was then recorded through the UI.

Pre-reset state:

- Visit 22: `IN_PROGRESS`
- `order_created = False`
- `order_amount = 0`
- `follow_up_required = True`
- `follow_up_date = 2026-08-29`
- SalesOutcome: `1` (`FOLLOW_UP`)
- FollowUpTask: `1` (`OPEN`)
- VisitCustomerSnapshot: `1`
- VisitCommercialSnapshot: `1`

Result:

`PRE-RESET DEMO STATE VALID: True`

## First Reset Validation
After:

```bash
python manage.py reset_daily_workspace_demo
```

all five scoped visits returned to `PLANNED`, with order/follow-up fields at baseline, and all scoped artifact counts returned to zero:

- SalesOutcome: `0`
- FollowUpTask: `0`
- VisitCustomerSnapshot: `0`
- VisitCommercialSnapshot: `0`

Result:

`RESET BASELINE VALID: True`

## Idempotency Validation
The reset command was immediately run a second time.

Output:

```text
Visits reset: 5
Sales outcomes deleted: 0
Follow-up tasks deleted: 0
Customer snapshots deleted: 0
Commercial snapshots deleted: 0
```

`Visits reset: 5` is expected because `QuerySet.update()` reports matched rows.

Post-second-reset validation:

```text
VISITS: 5
OUTCOMES: 0
FOLLOW-UPS: 0
CUSTOMER SNAPSHOTS: 0
COMMERCIAL SNAPSHOTS: 0

IDEMPOTENT RESET VALID: True
```

## Customer360 Refresh Observation
During validation, Customer360 had initially been open before the demo visits were seeded. The already-loaded page therefore did not contain the newly seeded visit context.

The JavaScript chain was verified as:

```text
startVisit()
→ changeVisitStatus("start")
→ /api/visits/v1/visits/<visitId>/start/
→ VisitStartAPIView
```

`visitId` comes from `window.salesAiCopilot.visitId`.

After a hard refresh, Visit 22 started correctly and both snapshots were created. This was a stale-page/context issue, not a Visit Start API or URL-routing defect.

Operational rule: after seeding/resetting demo data, refresh any Customer360 page that was already open before starting the demo.

## Source / Repository Validation
Validation completed successfully:

```text
python manage.py check
System check identified no issues (0 silenced).

git diff --check
PASS
```

Validation-only mutations to tracked `db.sqlite3` were removed with:

```bash
git restore db.sqlite3
```

The milestone therefore does not intentionally commit test-only database mutations.

## Recommended Demo Preparation
For a fresh local state:

```bash
python manage.py seed_daily_workspace_demo
python manage.py reset_daily_workspace_demo
```

Then refresh any already-open Customer360 page.

The seed command ensures the five demo visits exist; the reset command guarantees their deterministic workflow baseline.

## Architectural Decision
V3.0.10.9 uses a **Scoped Demo Reset**, not a global database rebuild.

This preserves business/demo context, purchase history and Recommendation Engine v1 behavior while making the Sales Rep scenario repeatable and auditable.

## Milestone Result
Validated lifecycle:

```text
Seed
→ PLANNED baseline
→ Start Visit
→ snapshots created
→ FOLLOW_UP outcome
→ open FollowUpTask
→ Reset
→ PLANNED baseline restored
→ scenario artifacts removed
→ Reset again
→ same baseline preserved
```

Validation results:

```text
SEEDED BASELINE VALID: True
START STATE VALID: True
PRE-RESET DEMO STATE VALID: True
RESET BASELINE VALID: True
IDEMPOTENT RESET VALID: True
```

**V3.0.10.9 — Demo Reset & Repeatability: VALIDATED.**

## Next Action
After commit/push, create the 5–10 minute Demo Runbook:

`Role Home → Sales Rep Daily Workspace → C0003 → Customer360 → AI Pre-Visit Intelligence → Commercial Decision / Recommendations → Start Visit → Record Outcome → Complete Visit → Manager Dashboard → Executive Intelligence / Decision Support`

The runbook should focus on presenter actions, expected UI state, talking points, and preparation/recovery steps rather than new feature development.
