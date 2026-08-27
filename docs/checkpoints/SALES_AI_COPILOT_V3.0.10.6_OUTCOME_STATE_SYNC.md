# Sales AI Copilot — V3.0.10.6 Outcome State Sync Checkpoint

## Checkpoint Version

V3.0.10.6

## Status

COMPLETE

---

# 1. Milestone Summary

V3.0.10.6 hardens the Sales Rep visit execution flow and
makes recommendation outcome state deterministic and reversible.

The milestone preserves raw SalesOutcome rows as immutable event
history while treating the latest event for each Visit +
Recommendation pair as the current resolved outcome.

Derived Visit commercial state is synchronized from the resolved
current outcomes.

---

# 2. Outcome Resolution Semantics

Previous behavior:

- Raw SalesOutcome events were preserved.
- Final outcome was selected by OUTCOME_PRIORITY.
- A historical higher-priority event could override the latest
  salesperson selection.

Example:

INTERESTED -> FOLLOW_UP

Previously resolved as:

INTERESTED

because INTERESTED had higher priority.

New behavior:

- Raw SalesOutcome events remain preserved.
- Current outcome is the latest SalesOutcome event ordered by:

  - created_at descending
  - id descending

Example:

INTERESTED -> FOLLOW_UP

Now resolves as:

FOLLOW_UP

This aligns Backend resolution with the salesperson's latest
explicit selection in the UI.

---

# 3. Central Visit Outcome State Synchronization

A centralized service was added:

sync_visit_outcome_state()

Location:

apps/visits/services.py

Responsibilities:

- Resolve current outcome for every Recommendation in the Visit.
- Rebuild purchase-related Visit state.
- Rebuild follow-up-related Visit state.
- Preserve raw SalesOutcome event history.
- Avoid reopening DONE or CANCELLED follow-up tasks.

---

# 4. Purchase State

Purchase state is now derived from current resolved outcomes.

If at least one current recommendation outcome is PURCHASED:

- visit.order_created = True
- visit.order_amount = sum of current resolved purchase amounts

If no current recommendation outcome is PURCHASED:

- visit.order_created = False
- visit.order_amount = 0

This makes purchase state reversible.

Validated transition:

REJECTED
-> PURCHASED
-> REJECTED

Final state:

order_created = False
order_amount = 0

---

# 5. Follow-Up State

Follow-up state is now derived from current resolved outcomes.

If at least one current recommendation outcome is FOLLOW_UP:

- visit.follow_up_required = True
- visit.follow_up_date is synchronized with the open FollowUpTask

If no current recommendation outcome is FOLLOW_UP:

- visit.follow_up_required = False
- visit.follow_up_date = None
- OPEN FollowUpTask records for the Visit are moved to CANCELLED

Cancelled task semantics remain compatible with the existing
FollowUpTaskStatusAPIView:

- status = CANCELLED
- completed_at = None
- updated_at is refreshed

Validated transition:

INTERESTED
-> FOLLOW_UP
-> REJECTED

Final state:

follow_up_required = False
follow_up_date = None
previous OPEN task = CANCELLED

---

# 6. SalesOutcome Event History

SalesOutcome continues to behave as an event-history model.

Multiple rows for the same Visit + Recommendation are intentional.

Example validated history:

INTERESTED
FOLLOW_UP
REJECTED
PURCHASED
REJECTED

Raw events are not deleted or overwritten.

The latest event is the current resolved recommendation outcome.

No UniqueConstraint was added to Visit + Recommendation.

---

# 7. SalesOutcomeCreateAPIView

The previous direct mutation logic for:

- order_created
- order_amount
- follow_up_required
- follow_up_date
- FollowUpTask creation/update

was removed from SalesOutcomeCreateAPIView.

The View now:

1. validates the request
2. creates a raw SalesOutcome event
3. calls sync_visit_outcome_state()
4. returns the synchronized Visit state

Backend-derived state remains authoritative.

---

# 8. Visit Start State Transition

VisitStartAPIView was hardened.

Allowed transition:

PLANNED -> IN_PROGRESS

Rejected start attempts:

- IN_PROGRESS
- COMPLETED
- CANCELLED

Invalid states return HTTP 400 and remain unchanged.

Snapshots are captured only when the Visit is genuinely PLANNED.

Strict non-database-mutating tests passed for all four states.

---

# 9. Customer 360 Runtime State Sync

Customer 360 now updates the visit-state banner immediately after
successful visit transitions without requiring a page reload.

Validated runtime transitions include:

PLANNED -> IN_PROGRESS

The following UI elements update correctly:

- Visit status badge
- Sales workspace visit-state CSS class
- Visit state banner
- Outcome button availability
- Start / Complete visit action
- Visit workflow message

No JavaScript errors were observed during validation.

---

# 10. Complete Visit CTA

The dynamically rendered Complete Visit button now has explicit
IN_PROGRESS styling.

Validated:

- visible
- correctly styled
- active while Visit is IN_PROGRESS

---

# 11. Primary Recommendation Outcome Status Visibility

Primary recommendation status contrast was corrected.

Validated:

- status label is visible
- current status value is visible
- "هنوز ثبت نشده" is clearly readable
- layout remains intact

Duplicate CSS rules were consolidated into one canonical block.

---

# 12. Primary Demo Validation

Primary demo Visit:

Visit ID:

23

Customer:

C0005 — Electrical Customer 05

Salesperson:

SP001 — Ali Ahmadi

Visit state during validation:

IN_PROGRESS

Recommendation:

ID 375

Product:

PHI004 — Philips Blender

Validated event sequence:

INTERESTED
FOLLOW_UP
REJECTED
PURCHASED
REJECTED

Final resolved outcome:

REJECTED

Final Visit-derived state:

order_created = False
order_amount = 0
follow_up_required = False
follow_up_date = None

No OPEN FollowUpTask remains for the Visit.

---

# 13. Strict Validation Results

Validated successfully:

- latest-event outcome resolution
- raw event-history preservation
- FOLLOW_UP creation
- FOLLOW_UP -> REJECTED reversibility
- REJECTED -> PURCHASED synchronization
- PURCHASED -> REJECTED reversibility
- FollowUpTask cancellation
- purchase state reset
- follow-up state reset
- Visit remains IN_PROGRESS during outcome changes
- no duplicate open follow-up task created
- strict PLANNED-only visit start
- runtime banner synchronization
- Complete Visit button styling
- primary outcome status visibility

All strict checks passed.

---

# 14. Static Validation

Executed successfully:

python manage.py check

Result:

System check identified no issues (0 silenced).

Executed successfully:

git diff --check

Result:

No output.

---

# 15. Database Validation Note

db.sqlite3 was intentionally mutated during real end-to-end
validation of the Sales Rep workflow.

Validation events created for:

Visit:

23

Recommendation:

375

included:

- INTERESTED
- FOLLOW_UP
- REJECTED
- PURCHASED
- REJECTED

These mutations were used only to validate:

- latest-event outcome resolution
- reversible purchase state
- reversible follow-up state
- FollowUpTask cancellation
- UI -> API -> Database consistency

Before the source-code checkpoint was committed, db.sqlite3 was
restored to the tracked Git state.

Therefore:

- validation data is not part of the V3.0.10.6 source commit
- source changes remain reproducible independently of test mutations
- the repository database remains clean

---

# 16. Final Repository State

V3.0.10.6 source changes are limited to:

- apps/visits/services.py
- apps/visits/views.py
- static/core/css/customer_360.css
- static/core/js/customer_360.js
- this checkpoint document

db.sqlite3 is intentionally excluded from the milestone changes.

---

# 17. Next Action

NEXT ACTION:

1. Run final static validation.
2. Review final git diff statistics and repository status.
3. Stage only the five V3.0.10.6 source/checkpoint files.
4. Commit V3.0.10.6.
5. Verify the working tree is clean.
6. Continue the end-to-end Demo flow with:
   - fresh Demo visit preparation
   - Visit completion
   - completed-state UI validation
   - post-visit intelligence validation
   - Management Dashboard impact validation