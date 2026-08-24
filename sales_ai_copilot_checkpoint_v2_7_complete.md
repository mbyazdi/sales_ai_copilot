# Sales AI Copilot — Checkpoint V2.7 Complete

**Checkpoint:** V2.7 Complete
**Stage:** Customer Visit Workspace V2
**Status:** COMPLETE
**Continuation Point:** Final Git validation, commit and push V2.7

---

## 1. Project Context

Project:

Sales AI Copilot

Main stack:

- Python
- Django / DRF
- SQLite for Demo
- Ollama-backed Sales Copilot
- API-driven architecture
- Modern SaaS / AI-first Sales Workspace

Main project path:

C:\PY Project\sales_ai_copilot

V2 architecture remains API-driven.

The Customer 360 page is the operational Sales Rep workspace and currently combines:

- Customer 360
- Current Visit
- Commercial Decision
- Recommendations
- Sales Copilot
- Sales Outcomes
- Follow-up
- Purchase / Sales History
- Recommendation Explainability
- Recommendation Performance

---

# 2. Previous Stable Milestones

Previously completed:

- V2.3 — Sales Rep Daily Workspace
- V2.4 — Sales Target Foundation
- V2.5 — Commercial Context
- V2.6 — Pre-Visit Intelligence

Important existing canonical backend layers:

- Commercial Context
- Commercial Decision
- Pre-Visit Brief
- Pre-Visit Intelligence Window
- Sales AI Context

Commercial Decision remains the canonical decision layer.

Do not duplicate scoring or decision logic in UI or AI code.

---

# 3. V2.7 Goal

V2.7 converted Customer 360 from a mostly analytical customer page into a visit-aware operational Sales Workspace.

The workspace now understands and reacts to the lifecycle of a real sales visit:

PLANNED
    ->
IN_PROGRESS
    ->
COMPLETED

CANCELLED is also handled as a terminal state.

The backend remains authoritative for state transitions and sales outcome guardrails.

---

# 4. V2.7 Completed Capabilities

## 4.1 Visit Ownership / Security

Visit execution endpoints are restricted to the authenticated active salesperson who owns the visit.

Validated cases:

### Visit owner

sales1 / SP001

Allowed to:

- start own visit
- complete own visit
- record sales outcome during IN_PROGRESS

### Another salesperson

sales2

Cannot operate SP001 visits.

Validated responses included 404 for inaccessible visit resources.

### Manager / non-salesperson

Rejected because no active salesperson profile exists.

### Anonymous user

Rejected by authentication guardrails.

---

# 5. Visit Start Guardrails

Endpoint:

POST
/api/visits/v1/visits/<visit_id>/start/

Validated behavior:

PLANNED
    -> IN_PROGRESS

IN_PROGRESS
    -> IN_PROGRESS

The second start is intentionally idempotent.

Rejected:

COMPLETED
    -> start

CANCELLED
    -> start

Validated examples:

Visit 14
Customer C0003
Salesperson SP001

---

# 6. Visit Complete Guardrails

Endpoint:

POST
/api/visits/v1/visits/<visit_id>/complete/

Valid transition:

IN_PROGRESS
    -> COMPLETED

Rejected:

PLANNED
    -> COMPLETED

A visit must be started before it can be completed.

Ownership and authentication restrictions are also enforced.

---

# 7. Sales Outcome Guardrails

Sales Outcome creation is only allowed while:

Visit.status == IN_PROGRESS

Validated states:

PLANNED
    -> rejected

IN_PROGRESS
    -> accepted

COMPLETED
    -> rejected

CANCELLED
    -> rejected

This prevents historical / future visits from receiving invalid outcome mutations.

---

# 8. Customer 360 Visit-Aware Workspace

Customer 360 now accepts visit context using:

?customer_code=<CUSTOMER_CODE>&visit_id=<VISIT_ID>

Example:

/customers/?customer_code=C0003&visit_id=14

When a valid current visit exists, the page receives:

current_visit

and renders itself according to the visit lifecycle.

If no visit context exists, Customer 360 remains usable as a normal customer view.

---

# 9. Visit Workspace States

The main workspace receives one of these CSS state classes:

visit-state-planned

visit-state-in_progress

visit-state-completed

visit-state-cancelled

visit-state-none

These states are used only for presentation and operational UX.

Backend Visit.status remains authoritative.

---

# 10. PLANNED State

Purpose:

Pre-Visit Preparation Mode

Behavior:

- Customer context remains visible.
- Commercial Decision remains visible.
- Recommendations remain visible.
- Sales Copilot remains visible.
- Outcome buttons are disabled.
- Start Visit is the primary workflow action.
- Complete Visit is not shown.
- Page informs the salesperson that the visit has not started yet.

Validated:

HAS STATE CLASS: True
HAS START BUTTON: True
HAS COMPLETE BUTTON: False

---

# 11. IN_PROGRESS State

Purpose:

Live Visit Execution Mode

Behavior:

- Commercial Decision becomes the main decision surface.
- Sales Copilot acts as the meeting playbook.
- Recommendations become operational.
- Outcome actions are enabled.
- Complete Visit is available.
- Start Visit is no longer shown.

Validated:

HAS STATE CLASS: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: True

This is the primary operational mode of Customer Visit Workspace V2.

---

# 12. COMPLETED State

Purpose:

Visit Review Mode

Behavior:

- No new sales outcomes can be recorded.
- Start Visit is unavailable.
- Complete Visit is unavailable.
- Existing customer / recommendation / visit information remains readable.
- Visit summary and supporting information remain available for review.

Validated:

HAS STATE CLASS: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: False

---

# 13. CANCELLED State

Purpose:

Closed / Non-operational Visit State

Behavior:

- Start Visit unavailable.
- Complete Visit unavailable.
- New outcome operations unavailable.
- Page clearly communicates that the visit is cancelled.

Validated:

HAS STATE CLASS: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: False

---

# 14. Commercial Decision Prominence

V2.7 promotes the canonical Commercial Decision into the main Active Visit experience.

Customer 360 now visibly exposes:

- Commercial Priority
- Commercial Score
- Decision Reasons
- Why Now
- Next Best Action
- Talking Point
- Recommended Product

No independent UI scoring logic was introduced.

All values come from the canonical Commercial Decision backend.

---

# 15. Canonical Decision Consistency

Validated customers include:

## C0003

Primary:

PHI002

Commercial Priority:

HIGH

Commercial Score:

9

Product:

Philips Electric Toothbrush

Commercial signals include:

- target relevance
- eligible promotion
- available stock

---

## C0005

Primary:

PHI004

Commercial Priority:

HIGH

Commercial Score:

7

---

## C0013

Primary:

PHI002

Commercial Priority:

HIGH

Commercial Score:

8

---

## C0014

Primary:

PHS001

Commercial Priority:

NORMAL

Commercial Score:

3

Includes LOW_STOCK consideration.

---

## C0029

Primary:

PHI002

Commercial Priority:

HIGH

Commercial Score:

8

---

# 16. Commercial Score Render Validation

Scoped render validation was completed.

C0003 / Visit 14:

SCOPED COMMERCIAL SCORE: 9
EXPECTED: 9
MATCH: True

C0014 / Visit 17:

SCOPED COMMERCIAL SCORE: 3
EXPECTED: 3
MATCH: True

Therefore the rendered Commercial Score is confirmed to be the actual decision score, not an unrelated number elsewhere in HTML.

---

# 17. Commercial Decision Render Validation

For C0003 / Visit 14 and C0014 / Visit 17, validated:

- COMMERCIAL DECISION present
- COMMERCIAL SCORE present
- WHY NOW present
- NEXT BEST ACTION present
- RECOMMENDATION present
- expected product present
- expected priority class present
- expected score present
- active visit state class present

All passed.

---

# 18. Active Visit Visual Hierarchy — V2.7.8

A final presentation-only polish was added for IN_PROGRESS visits.

Goal:

Commercial Decision
    ->
Primary Decision Surface

Sales Copilot
    ->
Meeting Execution Guidance

Primary Recommendation
    ->
Operational Outcome Surface

Alternative Recommendations
    ->
Supporting Options

Customer Analytics
    ->
Secondary / Drill-down Context

No backend scoring, database model, API contract or recommendation logic was changed for this polish.

---

# 19. Primary Recommendation Active-State Behavior

In IN_PROGRESS mode only:

The primary recommendation becomes visually lighter and more operational.

The large duplicated recommendation reason is hidden because the decision reasoning is already presented in the Commercial Decision surface.

Outcome controls remain visible and active.

Alternative recommendations retain their existing presentation.

This reduces duplication between:

Commercial Decision

and

Primary Recommendation.

---

# 20. Customer Hero Active-State Behavior

Customer Hero becomes slightly more compact during IN_PROGRESS.

Reason:

During a live visit, operational decision support is more important than repeated customer context.

PLANNED and non-active states retain their normal customer context emphasis.

---

# 21. Static CSS Serving Issue Discovered During Validation

During V2.7.8 testing, an old runserver process initially served a stale CSS version.

Validated using:

python manage.py findstatic core/css/customer_360.css

Resolved path:

C:\PY Project\sales_ai_copilot\static\core\css\customer_360.css

HTTP validation initially showed:

HTTP V2.7.8: False

After restarting Django runserver:

HTTP V2.7.8: True

Important:

If future CSS changes appear not to apply despite correct code:

1. verify static file with findstatic
2. restart runserver
3. verify served HTTP content
4. use hard refresh

Do not immediately add additional CSS overrides.

---

# 22. Important UX Validation Note

V2.7.8 styling is intentionally scoped to:

.visit-state-in_progress

Therefore the light operational Primary Recommendation style only appears when Customer 360 is opened with a real Visit Context and that Visit is IN_PROGRESS.

Example:

/customers/?customer_code=C0003&visit_id=14

Opening Customer 360 without visit_id uses:

visit-state-none

and does not activate Active Visit styling.

This is correct behavior.

---

# 23. Final Visit-State Regression Test

Final test was executed against Visit 14.

Results:

## PLANNED

STATUS: 200
HAS STATE CLASS: True
HAS PRIMARY CARD: True
HAS COMMERCIAL DECISION: True
HAS COPILOT: True
HAS START BUTTON: True
HAS COMPLETE BUTTON: False
ACTIVE COMPACT CSS ELIGIBLE: False

## IN_PROGRESS

STATUS: 200
HAS STATE CLASS: True
HAS PRIMARY CARD: True
HAS COMMERCIAL DECISION: True
HAS COPILOT: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: True
ACTIVE COMPACT CSS ELIGIBLE: True

## COMPLETED

STATUS: 200
HAS STATE CLASS: True
HAS PRIMARY CARD: True
HAS COMMERCIAL DECISION: True
HAS COPILOT: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: False
ACTIVE COMPACT CSS ELIGIBLE: False

## CANCELLED

STATUS: 200
HAS STATE CLASS: True
HAS PRIMARY CARD: True
HAS COMMERCIAL DECISION: True
HAS COPILOT: True
HAS START BUTTON: False
HAS COMPLETE BUTTON: False
ACTIVE COMPACT CSS ELIGIBLE: False

Rollback:

STATUS RESTORED: True

---

# 24. Current Demo Visit State

At the end of V2.7 validation:

Visit 14 / C0003 is currently:

IN_PROGRESS

This is the original state at the beginning of the final regression test, so rollback correctly restored it.

This state resulted from the real browser validation of the Live Visit workflow.

Do not assume Visit 14 is PLANNED in future tests.

Always inspect its current database state before mutation tests.

---

# 25. Files Changed in V2.7

Current working tree contains changes in:

apps/visits/views.py

db.sqlite3

static/core/css/customer_360.css

templates/core/customer_360/_ai_command_center.html

templates/core/customer_360/_sales_context.htm

Checkpoint file will add:

sales_ai_copilot_checkpoint_v2_7_complete.md

---

# 26. Current Git Diff Before Checkpoint

git diff --stat currently reports:

apps/visits/views.py
    95 lines changed approximately

db.sqlite3
    binary demo DB update

static/core/css/customer_360.css
    718 lines added approximately

templates/core/customer_360/_ai_command_center.html
    96 lines changed approximately

templates/core/customer_360/_sales_context.htm
    92 lines added approximately

Total before adding checkpoint:

995 insertions
6 deletions

---

# 27. Important Design Rule Going Forward

Commercial Decision is the canonical sales decision.

Do not recreate commercial scoring in:

- templates
- JavaScript
- AI prompt layer
- Customer 360 view
- Recommendation UI

The correct architecture remains:

Commercial Context
        +
Recommendation
        +
Customer / Visit Context
        ↓
Commercial Decision
        ↓
Customer 360
Daily Workspace
Visit API
Sales Copilot
Pre-Visit Intelligence

---

# 28. Recommendation Engine Rule

Recommendation Engine V1 remains stable.

Do not modify it merely for performance or UI work.

Commercial Decision consumes Recommendation output but does not replace Recommendation Engine responsibilities.

---

# 29. V2.7 Completion Status

The following V2.7 areas are complete:

- Visit ownership and authentication
- Visit Start state transition
- Visit Complete state transition
- Sales Outcome state guardrails
- Visit-aware Customer 360
- Visit lifecycle rendering
- Planned preparation mode
- Live visit execution mode
- Completed review mode
- Cancelled state handling
- Commercial Decision prominence
- Commercial Score rendering
- Why Now rendering
- Next Best Action rendering
- Sales Copilot live-visit integration
- Active Visit visual hierarchy
- Primary Recommendation operational mode
- Final multi-state regression validation

Therefore:

V2.7 — Customer Visit Workspace V2

STATUS: COMPLETE

---

# 30. Immediate Next Action

Do NOT add new V2.7 features.

Next actions are only:

1. Create this checkpoint file.
2. Run:
   python manage.py check
3. Run:
   git diff --check
4. Review:
   git status --short
5. Review:
   git diff --stat
6. Stage only intended V2.7 files.
7. Review staged diff.
8. Commit V2.7.
9. Push main to origin.
10. Confirm:
    nothing to commit, working tree clean

Only after Git is clean should the next product stage begin.

---

# 31. Recommended V2.7 Commit Message

Complete Customer Visit Workspace V2

---

# 32. Continuation Rule

When development resumes after this checkpoint:

Do not repeat V2.7 implementation.

Start from the next roadmap stage after confirming:

- working tree clean
- main synchronized with origin/main
- V2.7 commit exists
- current demo database state is understood

---

# END CHECKPOINT

V2.7 — CUSTOMER VISIT WORKSPACE V2
COMPLETE
