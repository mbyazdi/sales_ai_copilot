# Sales AI Copilot — Development Checkpoint

**Checkpoint:** V2.5 Complete  
**Continuation Point:** V2.6 — Pre-Visit Intelligence / Nightly-ready  
**Date:** 2026-08-24

---

## 1. Project State

- Project: `sales_ai_copilot`
- Branch: `main`
- Architecture: Django/DRF, API-driven, SQLite Demo DB, Ollama
- V2.1 Role & Experience Foundation: COMPLETE
- V2.2 Sales Rep Daily Workspace V2: COMPLETE
- V2.3 Sales Target Foundation: COMPLETE
- V2.4 Commercial Context: COMPLETE
- V2.5 Commercial Decision Layer: COMPLETE
- Next: V2.6 Pre-Visit Intelligence / Nightly-ready

---

## 2. V2.5 Objective

Create one deterministic, backend-authoritative commercial decision layer that combines:

```text
Recommendation Fit
+ Target Relevance / Target Gap
+ Promotion Eligibility
+ Inventory Availability
+ Customer Context
+ Historical Outcome context where applicable
        ↓
Commercial Decision
        ↓
Commercial Priority
Commercial Score
Decision Reasons
Why Now
Next Best Action
Talking Point
```

The Recommendation Engine remains the source of truth for product fit.

The LLM does not make or override the decision. It only explains and assists execution using approved backend facts.

---

## 3. Canonical Commercial Decision Service

New file:

```text
apps/core/commercial_decision.py
```

Primary function:

```text
build_base_sales_session
```

This is now the canonical source for:

```text
customer_status
sales_opportunity
primary_product
primary_product_code
primary_reason
recommendation_type
next_best_action
talking_point
target_context
inventory_context
promotion_context
commercial_signals
commercial_score
commercial_priority
decision_reasons
why_now
commercial_blocked
```

---

## 4. Commercial Priority Scoring

Current deterministic scoring logic:

```text
Recommendation Fit
score >= 80   +3
score >= 50   +2
score > 0     +1

Confidence
>= 80         +2
>= 60         +1

Target
relevant + at-risk   +2
relevant             +1

Eligible Promotion   +2

In Stock             +1
```

Availability guardrails:

```text
LOW_STOCK
→ caution
→ HIGH capped to MEDIUM if applicable

OUT_OF_STOCK
→ BLOCKED
```

Current priority thresholds:

```text
HIGH    score >= 7
MEDIUM  score >= 4
NORMAL  otherwise
```

---

## 5. Current Demo Decisions

Validated:

```text
C0003 | PHI002 | HIGH   | 9
C0005 | PHI004 | HIGH   | 7
C0013 | PHI002 | HIGH   | 8
C0014 | PHS001 | NORMAL | 3
C0029 | PHI002 | HIGH   | 8
```

Examples:

```text
C0003
Reasons:
STRONG_RECOMMENDATION
HIGH_CONFIDENCE
TARGET_RELEVANT
ELIGIBLE_PROMOTION
IN_STOCK

C0005
Reasons:
ACTIVE_RECOMMENDATION
MODERATE_CONFIDENCE
AT_RISK_TARGET
ELIGIBLE_PROMOTION
IN_STOCK

C0014
Reasons:
ACTIVE_RECOMMENDATION
TARGET_RELEVANT
IN_STOCK
LOW_STOCK
```

---

## 6. Daily Workspace Integration

`build_pre_visit_briefs()` now includes:

```text
commercial_decision
```

with:

```text
commercial_score
commercial_priority
decision_reasons
why_now
commercial_blocked
next_best_action
talking_point
```

Visit Priority and Commercial Priority remain separate concepts.

Example:

```text
C0005
Visit Priority: MEDIUM 4
Commercial Priority: HIGH 7
```

This distinction is intentional.

---

## 7. Commercial Decision UI

File:

```text
templates/visits/dashboard.html
```

Browser-validated block:

```text
COMMERCIAL DECISION
اولویت تجاری این فرصت
Why Now
```

Current rendered decision badges:

```text
HIGH   = 4
NORMAL = 1
```

Browser check: OK.

---

## 8. Canonical Commercial Decision API

Endpoint:

```text
GET /api/visits/v1/visits/<visit_id>/commercial-decision/
```

View:

```text
VisitCommercialDecisionAPIView
```

Top-level contract:

```text
visit
salesperson
customer
primary_recommendation
visit_priority
target_relevance
commercial_context
commercial_decision
```

Commercial decision contract:

```text
commercial_score
commercial_priority
decision_reasons
why_now
commercial_blocked
next_best_action
talking_point
```

Permissions validated:

```text
sales1 / owner   → 200
sales2 / non-owner → 403
manager1         → 403
anonymous        → 403
```

Manager/team decision APIs belong to a later Manager Workspace stage.

---

## 9. Customer 360 Integration

`apps/customers/views.py` now consumes the canonical decision path.

For visit-scoped Customer 360:

```text
sales_session
=
context["commercial_decision"]
=
sales_ai_context["sales_session"]
```

Validated for all five Demo visits.

A duplicate `build_sales_ai_context()` call in `customers/views.py` was also removed.

---

## 10. AI View Integration

`apps/ai/views.py` now uses the canonical commercial decision path.

When `visit_id` is supplied, AI context receives:

```text
Target Relevance
Commercial Context
Commercial Priority
Commercial Score
Why Now
Next Best Action
Talking Point
```

Validated against:

```text
C0003 → HIGH 9
C0005 → HIGH 7
C0013 → HIGH 8
C0014 → NORMAL 3
C0029 → HIGH 8
```

---

## 11. AI Prompt Guardrails

`apps/ai/prompt_builder.py` now includes authoritative commercial fields:

```text
Commercial Priority
Commercial Score
Commercial Blocked
Decision Reasons
Why Now
Target Context
Inventory Context
Promotion Context
```

Guardrails explicitly tell the LLM:

```text
Do not recalculate Commercial Priority.
Do not override Commercial Score.
Do not invent promotion benefits.
Do not infer inventory beyond explicit fields.
If Commercial Blocked is true, do not encourage closing before resolving the blocker.
```

Prompt validation:

```text
HAS COMMERCIAL PRIORITY : True
HAS COMMERCIAL SCORE    : True
HAS WHY NOW             : True
HAS PHI002 TARGET       : True
HAS STOCK 150           : True
HAS PROMO               : True
HAS BLOCK GUARDRAIL     : True
```

---

## 12. End-to-End Consistency

Validated across:

```text
Daily Workspace
Customer 360
Commercial Decision API
AI Context
AI Prompt
AI Endpoint
```

For every tested visit:

```text
PRIORITY CONSISTENT: True
SCORE CONSISTENT: True
PROMPT HAS PRIORITY: True
PROMPT HAS SCORE: True
```

This is the key V2.5 milestone:

```text
One canonical backend commercial decision is reused across the product.
```

---

## 13. Query Sanity

After all V2.5 changes:

```text
VISITS: 5
BRIEFS: 5
TOTAL QUERIES: 6
```

This matches the optimized V2.4 baseline.

No N+1 regression was introduced.

---

## 14. Final Validation

Confirmed:

```text
python manage.py check
→ System check identified no issues (0 silenced).

git diff --check
→ passed
```

Therefore:

```text
V2.5 STATUS = COMPLETE
```

---

## 15. Current Git State Before V2.5 Commit

Modified:

```text
apps/ai/prompt_builder.py
apps/ai/views.py
apps/customers/views.py
apps/visits/services.py
apps/visits/urls.py
apps/visits/views.py
db.sqlite3
templates/visits/dashboard.html
```

Untracked:

```text
apps/core/commercial_decision.py
sales_ai_copilot_checkpoint_v2_5_complete.md
```

Tracked diff summary before staging:

```text
apps/ai/prompt_builder.py       | 186 ++++++++++++++++++++++++++
apps/ai/views.py                | 234 +++++++++-----------------------
apps/customers/views.py         | 289 +++++++++++-----------------------------
apps/visits/services.py         |  60 +++++++++
apps/visits/urls.py             |   6 +
apps/visits/views.py            | 194 +++++++++++++++++++++++++++
db.sqlite3                      | Bin 1040384 -> 1044480 bytes
templates/visits/dashboard.html | 170 +++++++++++++++++++++++
```

---

## 16. NEXT ACTION — Close V2.5 Safely in Git

Inspect for caches:

```powershell
Get-ChildItem "apps\core" -Recurse -File |
Where-Object {
    $_.FullName -match "__pycache__|\.pyc$"
} |
Select-Object FullName
```

Remove any cache directories if present.

Then stage only intended V2.5 files:

```powershell
git add `
  apps/core/commercial_decision.py `
  apps/ai/prompt_builder.py `
  apps/ai/views.py `
  apps/customers/views.py `
  apps/visits/services.py `
  apps/visits/urls.py `
  apps/visits/views.py `
  templates/visits/dashboard.html `
  db.sqlite3 `
  sales_ai_copilot_checkpoint_v2_5_complete.md
```

Review:

```powershell
git status
git diff --cached --stat
git diff --cached --check
```

Suggested commit:

```text
Complete Commercial Decision Layer V2
```

Then:

```powershell
git commit -m "Complete Commercial Decision Layer V2"
git push origin main
```

Final verification:

```powershell
git status
git log -5 --oneline
```

Expected:

```text
nothing to commit, working tree clean
```

---

# 17. V2.6 — NEXT

Next stage:

```text
V2.6 — Pre-Visit Intelligence / Nightly-ready
```

Primary goal:

Prepare visit-level intelligence so the system can precompute or preassemble the decision package before the sales rep opens the workspace.

Likely concerns to inspect first:

```text
existing visit scheduling
today / upcoming visit logic
pre-visit brief generation
follow-up timing
whether commercial decision can be materialized or cached
whether a nightly/precompute path is useful for Demo
```

Do not create a nightly job before inspecting the current visit/service architecture.

---

## 18. Critical Warnings

1. V2.1–V2.5 are complete.
2. Recommendation Engine v1 remains stable.
3. Commercial Decision is canonical and deterministic.
4. LLM does not make or override commercial decisions.
5. Visit Priority and Commercial Priority are separate.
6. Target relevance does not overwrite recommendation fit.
7. Promotion/Inventory are authoritative commercial context.
8. Do not invent MSU conversion.
9. `SalesTarget.actual_value` remains imported/snapshot.
10. Current pre-visit brief query count is 6 for 5 visits.
11. Do not regress batch loading.
12. Keep Manager / Sales Rep / Customer Visit experiences separate.
13. Keep `db.sqlite3` versioned for Demo.
14. Continue `python manage.py check` and `git diff --check`.

---

## 19. One-Line Handoff

```text
V2.5 Commercial Decision Layer is complete, end-to-end consistent across Workspace, Customer 360, API and AI, and still runs at 6 queries for 5 visits; close it safely in Git, then start V2.6 by inspecting how to make pre-visit intelligence nightly-ready without duplicating the canonical decision logic.
```
