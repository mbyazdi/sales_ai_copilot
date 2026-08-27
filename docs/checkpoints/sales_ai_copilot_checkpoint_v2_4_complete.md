# Sales AI Copilot — Development Checkpoint

**Checkpoint:** V2.4 Complete  
**Continuation Point:** V2.5 — Commercial Decision Layer  
**Date:** 2026-08-24

---

## 1. Project Identity

- Project: `sales_ai_copilot`
- Repository: `https://github.com/mbyazdi/sales_ai_copilot.git`
- Branch: `main`
- Stack: Windows, PowerShell, VS Code, Python virtualenv, Django 6.1, Django REST Framework, SQLite Demo DB, Ollama
- Architecture: API-driven
- Known project paths:
  - `D:\py project\sales_ai_copilot`
  - `C:\PY Project\sales_ai_copilot`

---

## 2. Product North Star

The product is a role-aware **Sales AI Copilot** for field sales.

It is not intended to be just a chatbot.

Primary goals:

1. Increase sales volume.
2. Increase basket size through cross-sell/up-sell.
3. Help sales reps achieve product/category/business-line targets.
4. Preserve customer fit and customer satisfaction.

Commercial flow:

```text
Customer Context
+ Purchase Behavior
+ Customer Grade
+ Recommendation
+ Sales Target
+ Promotion
+ Inventory
+ Historical Outcome / Follow-up
        ↓
Commercial Decision Layer
        ↓
Prioritized Opportunity
        ↓
Next Best Action
        ↓
Talking Point
        ↓
Sales Rep Execution
        ↓
Outcome / Follow-up
        ↓
Feedback
```

Architectural separation:

```text
Recommendation Engine → What fits this customer?
Commercial Decision Layer → What should this rep focus on now?
Next Best Action → What should the rep do?
AI Copilot → How can I help the rep execute it?
```

Backend facts remain authoritative. The LLM must not invent recommendations, target gaps, promotions, inventory, outcomes, or commercial facts.

---

## 3. Completed Stages

```text
V2.1 Role & Experience Foundation       COMPLETE
V2.2 Sales Rep Daily Workspace V2       COMPLETE
V2.3 Sales Target Foundation            COMPLETE
V2.4 Commercial Context                 COMPLETE
V2.5 Commercial Decision Layer          NEXT
V2.6 Pre-Visit Intelligence / Nightly-ready
V2.7 Customer Visit Workspace V2
V2.8 Context-Aware Copilot V2
V2.9 Manager Workspace V2
V2.10 Demo Integration & Polish
```

---

## 4. V2.2 Baseline

Primary Sales Rep page:

```text
/api/visits/
```

Current SP001 Demo visits for 2026-08-24:

```text
C0003
C0005
C0013
C0014
C0029
```

Priority order:

```text
C0003 | HIGH   | 7
C0029 | HIGH   | 6
C0013 | MEDIUM | 5
C0005 | MEDIUM | 4
C0014 | MEDIUM | 3
```

Browser validation:

```text
V2.2 UI: OK
```

---

## 5. V2.3 Target Foundation Summary

Target scopes:

```text
PRODUCT
CATEGORY
PRODUCT_GROUP
```

`PRODUCT_GROUP` acts as Business Line for Demo.

Target units:

```text
QUANTITY
MSU
```

Important:

```text
MSU conversion is not available in current data.
Do not invent MSU conversion logic.
```

`SalesTarget.actual_value` is currently treated as imported/snapshot data because Sale rows do not directly attribute sales to a salesperson.

Current SP001 targets:

```text
CATEGORY | BLENDER
Target 300 | Actual 165 | Remaining 135 | Achievement 55%

PRODUCT | PHI002
Target 500 | Actual 410 | Remaining 90 | Achievement 82%

PRODUCT_GROUP | PERSONAL_ELECTRICAL
Target 1000 | Actual 720 | Remaining 280 | Achievement 72%

PRODUCT_GROUP | HOME_APPLIANCE
Target 800 | Actual 440 | Remaining 360 | Achievement 55%
```

Target relevance is context only and does not yet alter Visit Priority.

---

# 6. V2.4 — Commercial Context — COMPLETE

Completed steps:

```text
V2.4.1 Normalized Commercial Context Foundation
V2.4.2 Safe Demo Commercial Data
V2.4.3 Commercial Context in Pre-Visit Brief
V2.4.3C Batch Query Optimization
V2.4.4 Commercial Context UI
V2.4.5 Commercial Context API
V2.4.6 Final Regression / Smoke Test
```

---

## 7. Promotion Domain

Existing model files:

```text
apps/promotions/models.py
apps/promotions/services.py
apps/promotions/views.py
```

Promotion types:

```text
PERCENTAGE
FIXED_AMOUNT
BUY_X_GET_Y
```

Promotion supports:

```text
start_date
end_date
discount_percent
discount_amount
minimum_quantity
maximum_quantity
description
is_active
products
customer_grades
```

Join model:

```text
PromotionProduct
```

Important finding:

Recommendation Engine's current `_promotion_score()` checks promotion existence via `promotion__is_active=True`, but the new Commercial Context layer additionally evaluates date validity and customer-grade eligibility.

Recommendation Engine v1 remains stable for now. Do not casually rewrite its scoring in V2.5.

---

## 8. Inventory Domain

Model fields:

```text
product
available_quantity
reserved_quantity
minimum_stock
last_updated
```

Derived property:

```text
sellable_quantity = max(available_quantity - reserved_quantity, 0)
```

V2.4 explicitly distinguishes:

```text
No Inventory Record
```

from:

```text
Stock = 0
```

Missing inventory returns:

```text
has_record = False
quantity/status fields = None
```

---

## 9. Inventory Service

File:

```text
apps/inventory/services.py
```

Main service:

```text
get_product_inventory_context
```

Normalized output:

```text
has_record
available_quantity
reserved_quantity
sellable_quantity
minimum_stock
is_in_stock
is_low_stock
last_updated
```

Low stock logic:

```text
sellable_quantity > 0
and sellable_quantity <= minimum_stock
```

---

## 10. Promotion Service

File:

```text
apps/promotions/services.py
```

Main service:

```text
get_eligible_product_promotions
```

Eligibility rules:

```text
promotion.is_active = True
start_date <= as_of_date
end_date >= as_of_date
product linked to promotion
customer grade eligible
```

If a promotion has no grade restriction, it is open to all grades.

If a promotion has grade restrictions and no customer is supplied, it is not treated as eligible.

---

## 11. Cross-Domain Commercial Context

New file:

```text
apps/core/commercial_context.py
```

Important functions:

```text
build_product_commercial_context
build_product_commercial_contexts
```

Batch callers should use:

```text
build_product_commercial_contexts
```

Normalized contract includes:

```text
product_code
product_name

inventory:
    has_record
    available_quantity
    reserved_quantity
    sellable_quantity
    minimum_stock
    is_in_stock
    is_low_stock
    last_updated

promotions:
    id
    code
    name
    promotion_type
    start_date
    end_date
    discount_percent
    discount_amount
    minimum_quantity
    maximum_quantity
    description
    customer_eligible

has_eligible_promotion
```

This layer provides authoritative context only. It does not make the final commercial decision.

---

## 12. Safe Demo Commercial Data

New management command:

```text
apps/core/management/commands/seed_commercial_context_demo.py
```

Purpose:

```text
idempotent
non-destructive
Demo-only commercial context setup
```

Current Demo inventory:

```text
PHI002
available 180
reserved 30
sellable 150
minimum stock 40
low stock False

PHI004
available 90
reserved 20
sellable 70
minimum stock 25
low stock False

PHS001
available 24
reserved 8
sellable 16
minimum stock 20
low stock True

TEF003
available 140
reserved 20
sellable 120
minimum stock 30
low stock False
```

---

## 13. Demo Promotions

### PHI002

```text
Code: DEMO-PHI002-10
Name: Electric Toothbrush Growth Offer
Type: PERCENTAGE
Discount: 10%
Minimum Quantity: 2
Eligible Grades: B, C
Active Period: 2026-08-01 → 2026-09-30
```

### PHI004

```text
Code: DEMO-PHI004-07
Name: Blender Volume Offer
Type: PERCENTAGE
Discount: 7%
Minimum Quantity: 2
Eligible Grades: A, B, C
Active Period: 2026-08-01 → 2026-09-30
```

### TEF003

```text
Code: DEMO-TEF003-BXGY
Name: Tefal Blender Buy X Get Y
Type: BUY_X_GET_Y
Minimum Quantity: 12
Public / no grade restriction
Active Period: 2026-08-01 → 2026-09-30
Description: Buy 12 units and receive 1 bonus unit.
```

PHS001 intentionally has no promotion.

---

## 14. Commercial Context Demo Validation

For C0003 Grade C:

```text
PHI002 | STOCK 150 | LOW False | PROMO DEMO-PHI002-10
PHI004 | STOCK 70  | LOW False | PROMO DEMO-PHI004-07
PHS001 | STOCK 16  | LOW True  | no promo
TEF003 | STOCK 120 | LOW False | PROMO DEMO-TEF003-BXGY
```

For C0005 Grade B, the same eligible promo behavior was confirmed.

---

## 15. Commercial Context in Pre-Visit Brief

`build_pre_visit_briefs()` now attaches:

```text
commercial_context
```

for each primary recommendation.

Validated results:

```text
C0003 | PHI002
STOCK 150
LOW False
PROMO DEMO-PHI002-10

C0005 | PHI004
STOCK 70
LOW False
PROMO DEMO-PHI004-07

C0013 | PHI002
STOCK 150
LOW False
PROMO DEMO-PHI002-10

C0014 | PHS001
STOCK 16
LOW True
PROMOS []

C0029 | PHI002
STOCK 150
LOW False
PROMO DEMO-PHI002-10
```

V2.4 does not alter Recommendation Score or Visit Priority.

---

## 16. Query Optimization

Initial implementation caused:

```text
5 visits
5 briefs
17 queries
```

Cause:

```text
per-visit Inventory query
per-visit Promotion query
per-visit Promotion Grade prefetch
```

This was replaced with batch loading.

Final result:

```text
5 visits
5 briefs
6 queries
```

Final query structure:

```text
1) Visits + Customer context
2) Recommendations
3) Inventory batch
4) PromotionProduct + Promotion batch
5) Promotion customer grades prefetch
6) Follow-ups
```

Do not regress this in V2.5.

---

## 17. Commercial Context UI

File:

```text
templates/visits/dashboard.html
```

Pre-Visit Brief displays:

```text
وضعیت تجاری این پیشنهاد
```

UI includes:

```text
sellable inventory
in-stock / low-stock / out-of-stock state
promotion name
promotion type
discount percent / amount
minimum quantity
```

Automated validation:

```text
STATUS: 200
HAS COMMERCIAL TITLE: True
HAS STOCK 150: True
HAS STOCK 70: True
HAS LOW STOCK: True
HAS PHI002 PROMO: True
HAS PHI004 PROMO: True
```

Browser layout was visually inspected and accepted.

---

## 18. Commercial Context API

New read-only endpoint:

```text
GET /api/v1/customers/<customer_code>/products/<product_code>/commercial-context/
```

View:

```text
ProductCommercialContextAPIView
```

Location:

```text
apps/core/views.py
```

Route:

```text
apps/core/urls.py
```

Permission:

```text
IsAuthenticated
```

Validated:

```text
C0003 | PHI002
STATUS 200
Grade C
Stock 150
Low False
Promo DEMO-PHI002-10

C0005 | PHI004
STATUS 200
Grade B
Stock 70
Low False
Promo DEMO-PHI004-07

C0014 | PHS001
STATUS 200
Grade A
Stock 16
Low True
Promotions []
```

---

## 19. Final V2.4 Validation

Smoke test:

```text
DASHBOARD STATUS: 200
HAS COMMERCIAL CONTEXT: True
HAS LOW STOCK: True
HAS PROMOTION: True

COMMERCIAL API STATUS: 200
API STOCK: 150
API PROMO COUNT: 1
```

System validation:

```text
python manage.py check
→ System check identified no issues (0 silenced).

git diff --check
→ passed
```

Therefore:

```text
V2.4 STATUS = COMPLETE
```

---

## 20. Current Git State Before V2.4 Commit

Modified files:

```text
apps/core/urls.py
apps/core/views.py
apps/inventory/services.py
apps/promotions/services.py
apps/visits/services.py
db.sqlite3
templates/visits/dashboard.html
```

Untracked files:

```text
apps/core/commercial_context.py
apps/core/management/commands/seed_commercial_context_demo.py
sales_ai_copilot_checkpoint_v2_4_complete.md
```

Tracked diff summary before staging:

```text
apps/core/urls.py               |  16 ++-
apps/core/views.py              |  79 ++++++++++++++-
apps/inventory/services.py      |  70 +++++++++++++
apps/promotions/services.py     | 115 +++++++++++++++++++++
apps/visits/services.py         |  52 +++++++++-
db.sqlite3                      | Bin 1036288 -> 1040384 bytes
templates/visits/dashboard.html | 219 ++++++++++++++++++++++++++++++++++++++++
```

Note: `git diff --stat` does not include untracked files until staged.

---

## 21. NEXT ACTION — Close V2.4 Safely in Git

Before staging, inspect:

```powershell
Get-ChildItem "apps\core\management" -Recurse -File |
Select-Object FullName
```

Remove any `__pycache__` / `.pyc` files if present.

Then stage only intended V2.4 files:

```powershell
git add `
  apps/core/urls.py `
  apps/core/views.py `
  apps/core/commercial_context.py `
  apps/core/management/commands/seed_commercial_context_demo.py `
  apps/inventory/services.py `
  apps/promotions/services.py `
  apps/visits/services.py `
  templates/visits/dashboard.html `
  db.sqlite3 `
  sales_ai_copilot_checkpoint_v2_4_complete.md
```

Review:

```powershell
git status
git diff --cached --stat
git diff --cached --check
```

Suggested commit:

```text
Complete Commercial Context V2
```

Then:

```powershell
git commit -m "Complete Commercial Context V2"
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

# 22. V2.5 — Commercial Decision Layer — NEXT

Purpose:

Combine authoritative signals into a deterministic commercial decision.

Inputs:

```text
Customer Fit / Recommendation
Target Gap / Target Relevance
Promotion
Inventory
Customer Grade
Historical Outcome
```

Conceptual outputs:

```text
Commercial Opportunity Priority
Primary Sales Focus
Why Now
Next Best Action facts
Talking Point source facts
```

Do not replace Recommendation Engine.

Do not let the LLM invent the decision.

The Commercial Decision Layer should be backend-authoritative first.

---

## 23. V2.5 First Inspection Before Coding

Before creating a new decision service, inspect existing opportunity / NBA / talking-point logic to avoid duplication:

```powershell
Get-ChildItem `
  "apps","templates","static" `
  -Recurse `
  -Include *.py,*.html,*.js `
  -File |
Select-String `
  -Pattern "sales_opportunity|next_best_action|talking_point|primary_product|customer_status|opportunity" |
ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line.Trim())"
}
```

Then inspect relevant implementations in:

```text
apps/customers/views.py
apps/customers/insights.py
apps/ai/views.py
apps/ai/prompt_builder.py
```

Do not create duplicate commercial-decision concepts until these are reviewed.

---

## 24. Critical Warnings

1. V2.1–V2.4 are complete.
2. V2.5 Commercial Decision Layer is next.
3. Recommendation Engine v1 stays stable.
4. Target relevance currently does NOT alter Visit Priority.
5. Commercial Context currently does NOT alter Recommendation Score.
6. Do not invent MSU conversion.
7. `SalesTarget.actual_value` is still imported/snapshot.
8. Do not infer salesperson attribution from historical Sale rows without reliable linkage.
9. Product Group acts as Business Line for Demo.
10. Promotion eligibility in Commercial Context checks active flag + date + product + grade.
11. Current Recommendation Engine promotion scoring is simpler and should not be casually rewritten.
12. Batch Commercial Context must remain N+1 safe.
13. Current pre-visit brief query count is 6 for 5 visits after V2.4.
14. Do not run the destructive global sample generator casually.
15. Reuse Promotion and Inventory domains.
16. Reuse existing opportunity / NBA / talking-point concepts where possible.
17. Manager / Sales Rep / Customer Visit experiences remain separate.
18. Backend facts remain authoritative.
19. Continue `python manage.py check` and `git diff --check`.
20. Keep `db.sqlite3` versioned.

---

## 25. One-Line Handoff

```text
V2.4 Commercial Context is complete and regression-tested; close it safely in Git, then begin V2.5 by inspecting all existing sales_opportunity / next_best_action / talking_point logic before designing the deterministic Commercial Decision Layer that combines Recommendation Fit + Target Gap + Promotion + Inventory + Historical Outcome.
```
