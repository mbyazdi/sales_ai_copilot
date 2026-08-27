# Sales AI Copilot — Development Checkpoint

**Checkpoint:** V2.3 Complete  
**Continuation Point:** V2.4 — Commercial Context (Promotion + Inventory)  
**Date:** 2026-08-24

---

## 1. Project State

- Project: `sales_ai_copilot`
- Branch: `main`
- Architecture: Django/DRF, API-driven, SQLite Demo DB, Ollama
- Last confirmed commit before V2.3: `c693531 Complete Sales Rep Daily Workspace V2`
- V2.1: COMPLETE
- V2.2: COMPLETE
- V2.3: COMPLETE
- Next: V2.4 Commercial Context

## 2. Product Architecture

Keep these layers separate:

```text
Recommendation Engine → What fits this customer?
Commercial Decision Layer → What should this rep focus on now?
Next Best Action → What should the rep do?
AI Copilot → How can I help the rep execute it?
```

Backend facts remain authoritative. The LLM must not invent recommendations, promotions, stock, target gaps, outcomes, or commercial facts.

## 3. V2.2 Baseline

Sales Rep Daily Workspace is complete and browser validated.

Current SP001 daily demo visits for 2026-08-24:

```text
C0003
C0005
C0013
C0014
C0029
```

Final V2.2 priority order:

```text
C0003 | HIGH   | 7
C0029 | HIGH   | 6
C0013 | MEDIUM | 5
C0005 | MEDIUM | 4
C0014 | MEDIUM | 3
```

Pre-visit briefs were validated at 3 queries for 5 visits.

## 4. V2.3 — Sales Target Foundation

V2.3 was completed through these steps:

```text
V2.3.1 Target Domain Inspection
V2.3.2 SalesTarget Model Foundation
V2.3.3 Model Validation
V2.3.4 Database Constraint Validation
V2.3.5 Target Progress Service Layer
V2.3.6 Demo Target Data
V2.3.7 Target Context in Daily Workspace
V2.3.8 Target Relevance
V2.3.9 Sales Target Progress API
V2.3.10 Final Regression Check
```

## 5. Target Domain Decisions

No prior real Target / Quota / MSU domain existed.

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

Important: MSU conversion is NOT available in current product/sales data. Products are effectively `PCS / 1 PCS`. Do not invent MSU conversion logic.

Current `Sale` data also has no direct salesperson attribution. Therefore `SalesTarget.actual_value` is currently treated as an imported/snapshot value rather than being calculated automatically from historical sales.

## 6. New Targets App

New app:

```text
apps/targets/
```

Registered as:

```python
apps.targets.apps.TargetsConfig
```

Primary model: `SalesTarget`

Key fields:

```text
salesperson
period_start
period_end
scope_type
product
category
product_group
target_unit
target_value
actual_value
is_active
created_at
updated_at
```

Derived properties:

```text
remaining_value
achievement_percent
scope_code
```

## 7. Target Constraints

Migration:

```text
apps/targets/migrations/0001_initial.py
```

Applied successfully:

```text
targets
 [X] 0001_initial
```

Key constraints:

```text
sales_target_value_gt_zero
sales_target_actual_gte_zero
sales_target_valid_scope
unique_active_product_target
unique_active_category_target
unique_active_product_group_target
```

Validated DB behavior:

```text
Duplicate active target → blocked
Inactive duplicate → allowed
Mixed scope → rejected
Invalid period → rejected
Target <= 0 → rejected
Overachievement > 100% → allowed
Remaining never below 0
```

## 8. Target Progress Service

File:

```text
apps/targets/services.py
```

Primary functions:

```text
serialize_sales_target
get_salesperson_target_progress
build_target_summary
```

This service is intended to be reused by Daily Workspace, Commercial Decision Layer, Customer Visit Workspace, Manager Workspace, and API.

## 9. Demo Target Data for SP001

Period:

```text
2026-08-01 → 2026-08-31
```

Current demo targets:

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

Summary:

```text
Total Targets: 4
Average Achievement: 66%
Completed: 0
At Risk: 2
```

## 10. Daily Workspace Target Integration

Daily Workspace now receives:

```text
target_progress
target_summary
```

Target Overview renders successfully.

Automated validation:

```text
STATUS: 200
TARGET COUNT: 4
AVERAGE: 66%
HAS TARGET OVERVIEW: True
```

Browser validation:

```text
V2.3 Target UI: OK
```

## 11. Target Relevance

Primary recommendation is matched to active targets by:

```text
PRODUCT → same product
CATEGORY → recommendation product category
PRODUCT_GROUP → recommendation product group
```

Confirmed relevance:

```text
C0003 → PHI002 + PERSONAL_ELECTRICAL
C0005 → BLENDER + HOME_APPLIANCE
C0013 → PHI002 + PERSONAL_ELECTRICAL
C0014 → PERSONAL_ELECTRICAL
C0029 → PHI002 + PERSONAL_ELECTRICAL
```

Target relevance is context only. It does NOT yet change Visit Priority. Commercial prioritization belongs to V2.5.

## 12. Target API

Endpoint:

```text
GET /api/targets/v1/my-progress/
```

Sales Rep validation:

```text
sales1 / SP001
STATUS: 200
CONTENT TYPE: application/json
TARGET COUNT: 4
AVERAGE ACHIEVEMENT: 66.0
```

Manager validation:

```text
manager1
STATUS: 403
BODY: Active salesperson profile was not found.
```

This is intentional. Manager/team target APIs belong to the later Manager Workspace stage.

## 13. Final Regression

Confirmed:

```text
python manage.py check
→ System check identified no issues (0 silenced).

git diff --check
→ passed

python manage.py showmigrations targets
→ [X] 0001_initial

DASHBOARD STATUS: 200
HAS TARGET OVERVIEW: True
HAS TARGET RELEVANCE: True

API STATUS: 200
API TARGET COUNT: 4
API AVERAGE: 66.0
```

Therefore:

```text
V2.3 STATUS = COMPLETE
```

## 14. Current Git State Before V2.3 Commit

Modified:

```text
apps/visits/services.py
apps/visits/views.py
db.sqlite3
sales_ai_copilot/settings.py
sales_ai_copilot/urls.py
templates/visits/dashboard.html
```

Untracked:

```text
apps/targets/
```

Before commit, inspect `apps/targets/` and remove any `__pycache__` / `.pyc` files.

## 15. NEXT ACTION

First close V2.3 safely in Git.

Run:

```powershell
git status --short
Get-ChildItem "apps\targets" -Recurse -File | Select-Object FullName
```

Remove any `__pycache__` folders if present. Then review/stage only intended V2.3 files.

Suggested commit:

```text
Complete Sales Target Foundation V2
```

After push, verify:

```powershell
git status
git log -5 --oneline
```

Then begin:

```text
V2.4 — Commercial Context (Promotion + Inventory)
```

## 16. V2.4 First Inspection

Do not create new Promotion/Inventory models before inspecting the existing domains.

Start with:

```powershell
Get-Content "apps\promotions\services.py"
Get-Content "apps\inventory\services.py"
Get-Content "apps\inventory\models.py"
Get-Content "apps\recommendations\engine.py" | Select-Object -Skip 1170 -First 70
```

Then inspect current DB counts for Promotion and Inventory.

Known prior state at V2.2 inspection:

```text
Promotions: 0
Inventory: 0
```

The global sample-data generator already contains Promotion and Inventory creation logic, but it is destructive. Do not run it casually.

## 17. V2 Roadmap

```text
V2.1 Role & Experience Foundation       COMPLETE
V2.2 Sales Rep Daily Workspace V2       COMPLETE
V2.3 Sales Target Foundation            COMPLETE
V2.4 Commercial Context                 NEXT
V2.5 Commercial Decision Layer
V2.6 Pre-Visit Intelligence / Nightly-ready
V2.7 Customer Visit Workspace V2
V2.8 Context-Aware Copilot V2
V2.9 Manager Workspace V2
V2.10 Demo Integration & Polish
```

## 18. Critical Warnings

1. Do not repeat V2.1–V2.3.
2. Recommendation Engine v1 remains stable.
3. Do not invent MSU conversion.
4. Do not auto-attribute Sale history to Salesperson without reliable attribution.
5. Target relevance does not yet alter Visit Priority.
6. Promotion and Inventory domains already exist and should be reused.
7. Do not run the destructive global sample generator casually.
8. Keep Manager, Sales Rep Daily Workspace, and Customer Visit Workspace separate.
9. Keep backend facts authoritative.
10. Continue `python manage.py check` and `git diff --check` after changes.
11. Keep `db.sqlite3` versioned for Demo.

## 19. One-Line Handoff

```text
V2.3 Sales Target Foundation is complete and regression-tested; close it safely in Git, then start V2.4 by inspecting existing Promotion and Inventory services/models and current DB readiness before building the normalized Commercial Context layer.
```