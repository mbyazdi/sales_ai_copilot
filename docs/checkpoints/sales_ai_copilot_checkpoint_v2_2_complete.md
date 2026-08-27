# Sales AI Copilot --- Development Checkpoint

**Checkpoint:** V2.2 Complete\
**Continuation Point:** V2.3 --- Sales Target Foundation\
**Date:** 2026-08-24

------------------------------------------------------------------------

## 1. Project Identity

-   Project: `sales_ai_copilot`
-   Repository: `https://github.com/mbyazdi/sales_ai_copilot.git`
-   Branch: `main`
-   Stack: Windows, PowerShell, VS Code, Python virtualenv, Django 6.1,
    DRF, SQLite Demo DB, Ollama
-   Architecture: API-driven
-   Known paths: `D:\py project\sales_ai_copilot` and
    `C:\PY Project\sales_ai_copilot`

Last confirmed synchronized baseline before V2.2 work:

``` text
2c3e168 Update demo database credentials
89d3ddd Add Sales AI Copilot V2 checkpoint
fdfae1d Add role-aware manager and sales rep experience
80276fc Add recommendation explainability drill-down
aaf58b9 Add explainability quality monitoring
```

V2.2 changes happened after this baseline. Inspect current Git state
before committing.

------------------------------------------------------------------------

## 2. Product North Star

This is not a chatbot demo. It is a role-aware Sales AI Copilot that
prepares the commercial decision for planned customer visits, helps the
rep execute it, captures outcome/follow-up, and feeds that information
back.

Business goals:

1.  Increase sales volume.
2.  Increase basket size / cross-sell / up-sell.
3.  Help reps achieve product/category/line targets.
4.  Preserve customer fit and satisfaction.

``` text
Customer Context + Purchase Behavior + Grade + Recommendation
+ Promotion + Sales Rep Target + Inventory + Previous Outcome
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
Feedback → Next Recommendation
```

Architectural distinction:

``` text
Recommendation Engine → What fits this customer?
Commercial Decision Layer → What should this rep focus on now?
Next Best Action → What should the rep do?
AI Copilot → How can I help the rep execute it?
```

The LLM is not the authoritative source of business facts.

------------------------------------------------------------------------

## 3. Experience Separation

Keep these distinct:

### Manager Experience

Team overview, sales/conversion, target achievement, visit performance,
follow-up health, recommendation performance, diagnostics, tuning,
promotion effectiveness.

### Sales Rep Daily Workspace

Today's visit plan, own customers, visit statuses, customer priority,
pre-visit brief, follow-ups, target-gap relevance, entry into customer
workspace.

### Customer Visit Workspace

Customer brief, recommendations, opportunity, promotion, target
relevance, inventory, Talking Point, Next Best Action, outcome,
follow-up, grounded Copilot.

------------------------------------------------------------------------

## 4. Hard Architecture Constraints

-   Recommendation Engine v1 is stable; do not replace it with
    ML/XGBoost.
-   Existing recommendation types include `REPEAT_PURCHASE`,
    `CROSS_SELL`, `CATEGORY`, `SIMILAR_PRODUCT`, `UP_SELL`.
-   Existing Customer 360 already has `sales_opportunity`,
    `primary_product`, `talking_point`, `next_best_action`; do not
    create duplicate layers without checking existing logic.
-   Backend facts are authoritative.
-   LLM must not invent recommendations, promotions, stock, target gaps,
    outcomes, or commercial facts.
-   Prefer incremental, low-risk changes.

------------------------------------------------------------------------

## 5. Required Development Workflow

For code changes use:

``` text
FILE
OPEN — Ctrl+P + exact path
FIND — exact text/code
ADD / REPLACE / DELETE
RUN
```

For multiline Django shell tests prefer `exec("""...""")`.

After changes:

``` powershell
python manage.py check
git diff --check
```

`db.sqlite3` is intentionally versioned for the Demo.

Multi-environment Git entry workflow:

``` powershell
git fetch origin
git status
git pull --ff-only origin main   # only when working tree is clean
git status
git log -5 --oneline
```

------------------------------------------------------------------------

## 6. V2.1 --- COMPLETE

Demo identities:

``` text
sales1   → SP001 Ali Ahmadi
sales2   → SP002 Sara Karimi
sales3   → SP003 Reza Moradi
manager1 → staff user, no salesperson profile
```

Role-home redirects:

``` text
sales1/sales2/sales3 → /api/visits/
manager1 → /management/recommendations/performance/
```

`salesperson_dashboard` uses logged-in
`request.user.salesperson_profile`; hard-coded SP001 behavior was
removed. `templates/base.html` is role-aware.

Browser validation:

``` text
Sales Rep UI: OK
Manager UI: OK
```

Existing Manager Recommendation Performance / Explainability /
Diagnostics / Tuning are already implemented. Reuse them; do not
rebuild.

------------------------------------------------------------------------

## 7. V2.2 --- Sales Rep Daily Workspace V2 --- COMPLETE

Primary page:

``` text
/api/visits/
```

Primary implementation:

``` text
apps/visits/views.py → salesperson_dashboard
templates/visits/dashboard.html
```

V2.2 reused the existing dashboard rather than rebuilding it.

Final browser validation:

``` text
V2.2 UI: OK
```

### Demo visits for sales1 / SP001 on 2026-08-24

``` text
14 | C0003 | Electrical Customer 03 | PLANNED
15 | C0005 | Electrical Customer 05 | PLANNED
16 | C0013 | Electrical Customer 13 | PLANNED
17 | C0014 | Electrical Customer 14 | PLANNED
18 | C0029 | Electrical Customer 29 | PLANNED
```

Before these Demo visits, historical data contained 13 visits from
2026-08-14 through 2026-08-22.

------------------------------------------------------------------------

## 8. V2.2 Pre-Visit Brief

Confirmed:

``` text
VISITS: 5
BRIEFS: 5
TOTAL QUERIES: 3
```

Brief data includes customer code/name, grade, segment, days since last
purchase, top category, primary recommendation, recommendation type,
score, confidence, evidence quality, reason, and open follow-up context.

Representative primary recommendations:

``` text
C0003 → PHI002 Philips Electric Toothbrush | REPEAT_PURCHASE | score 82 | confidence 100 | HIGH
C0005 → PHI004 Philips Blender | CATEGORY | score 42 | confidence 72 | MEDIUM
C0013 → PHI002 Philips Electric Toothbrush | REPEAT_PURCHASE | score 77 | confidence 90 | HIGH
C0014 → PHS001 Philips Hair Straightener | CROSS_SELL | score 26.84 | confidence 46.84 | MEDIUM
C0029 → PHI002 Philips Electric Toothbrush | REPEAT_PURCHASE | score 67 | confidence 90 | HIGH
```

For these five selected visits, open follow-ups were zero.

The 3-query result is acceptable for the Demo; do not prematurely
optimize it.

------------------------------------------------------------------------

## 9. V2.2 Priority Layer

Confirmed priority scoring:

``` text
C0003 | HIGH   | 7
C0029 | HIGH   | 6
C0013 | MEDIUM | 5
C0005 | MEDIUM | 4
C0014 | MEDIUM | 3
```

Priority reasons use explainable signals such as recommendation score,
confidence and customer segment/value.

Final visit ordering is descending priority score.

Priority summary:

``` python
{"high": 2, "medium": 3, "normal": 0}
```

The missing-salesperson error context also provides a zeroed
`priority_summary`.

Automated validation:

``` text
STATUS: 200
PRIORITY SUMMARY: {'high': 2, 'medium': 3, 'normal': 0}
HAS PRIORITY OVERVIEW: True
```

The template contains `TODAY'S PRIORITIES`, priority badges, Pre-Visit
Brief, score and confidence.

Earlier automated checks confirmed the Sales Rep page contains Daily
Workspace / Today's Visits / Follow-ups and does not expose Manager
Dashboard.

------------------------------------------------------------------------

## 10. Promotion / Inventory Readiness Finding

At V2.2 inspection:

``` text
TOTAL PROMOTIONS: 0
TOTAL INVENTORY RECORDS: 0
```

Key Demo products including `PHI002`, `PHI004`, `TEF003`, `BOS001`,
`TEF001`, `PHS001` had no active inventory records/promotions in the
inspected DB.

However, `scripts/sample_data_generator.py` already contains:

``` text
create_inventory(products)
create_promotions(products, grades)
```

and `main()` calls both.

Do not run the full sample generator casually because it
deletes/recreates broad Demo data. Prefer narrow Demo-data changes when
needed.

Promotion models already support `PERCENTAGE`, `FIXED_AMOUNT`,
`BUY_X_GET_Y`, product eligibility, customer grades, dates, discount
fields, quantities and active state.

Recommendation Engine already consumes active `PromotionProduct`
existence as a scoring signal.

Inventory models/services also exist, but no dedicated Inventory UI/API
was exposed at the last inspection. Product-level inventory is enough
for Demo V2; no warehouse complexity.

------------------------------------------------------------------------

## 11. Current Validation Status

End of V2.2:

``` text
python manage.py check
→ no issues

git diff --check
→ passed

V2.2 UI: OK
```

Therefore:

``` text
V2.2 STATUS = COMPLETE
```

------------------------------------------------------------------------

## 12. V2 Roadmap

``` text
V2.1 Role & Experience Foundation       COMPLETE
V2.2 Sales Rep Daily Workspace V2       COMPLETE
V2.3 Sales Target Foundation            NEXT
V2.4 Commercial Context
V2.5 Commercial Decision Layer
V2.6 Pre-Visit Intelligence / Nightly-ready
V2.7 Customer Visit Workspace V2
V2.8 Context-Aware Copilot V2
V2.9 Manager Workspace V2
V2.10 Demo Integration & Polish
```

V2.3 minimum concepts:

``` text
Salesperson
Period
Product / Category / Line scope
MSU / Quantity unit
Target
Actual
Remaining
Achievement %
```

No commission/payroll logic.

Later V2.5 Decision Layer inputs should include Recommendation/Customer
Fit, Target Gap, Promotion, Inventory, Customer Grade and Historical
Outcome.

------------------------------------------------------------------------

## 13. Explicit Out of Scope

Do not scope-creep into:

-   Route Optimization / GPS
-   Full ERP order approval
-   Warehouse/regional inventory complexity
-   Commission/bonus payroll
-   Customer credit scoring
-   ML/XGBoost replacement of Recommendation Engine
-   Complex promotion optimization
-   Production hardening beyond Demo needs

------------------------------------------------------------------------

## 14. NEXT ACTION --- EXACT CONTINUATION POINT

Do not repeat V2.1 or V2.2.

### A. Close V2.2 safely in Git

Run first:

``` powershell
git status
git diff --stat
git diff --check
python manage.py check
```

Review all V2.2 changes, including `db.sqlite3` and the five planned
Demo visits.

Then commit/push the intended V2.2 changes. Suggested commit message:

``` text
Complete Sales Rep Daily Workspace V2
```

Verify clean synchronization with `origin/main`.

### B. Start V2.3 --- Sales Target Foundation

Before creating any model, inspect the repository for existing
target/quota/MSU/achievement concepts:

``` powershell
Get-ChildItem . `
  -Recurse `
  -Include *.py,*.html,*.js `
  -File |
Where-Object {
    $_.FullName -notmatch "\\venv\\"
} |
Select-String `
  -Pattern "SalesTarget|sales_target|target|quota|MSU|achievement|remaining" |
ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line.Trim())"
}
```

Then inspect:

``` powershell
Get-Content "apps\products\models.py"
```

and:

``` powershell
Select-String `
  -Path "apps\visits\models.py" `
  -Pattern "^class Salesperson" `
  -Context 0,100
```

Do not create V2.3 models until these inspection results are reviewed.

The first Sales Target design must answer:

``` text
For this salesperson,
during this target period,
for this product/category/line scope:

What is the target?
What is actual sales?
What remains?
What percentage is achieved?
```

It should later be reusable by Daily Workspace, Commercial Decision
Layer, Customer Visit Workspace and Manager Workspace.

------------------------------------------------------------------------

## 15. Critical Handoff Warnings

1.  V2.1 is complete.
2.  V2.2 is complete and browser-validated.
3.  V2.3 Sales Target Foundation is next.
4.  Do not repeat the V2 Gap Analysis.
5.  Recommendation Engine v1 stays stable.
6.  Do not duplicate Opportunity/Talking Point/NBA.
7.  AI Chat is not the product core.
8.  Preserve role-separated experiences.
9.  Preserve backend-authoritative facts and LLM guardrails.
10. Keep changes incremental and test each step.
11. Keep `db.sqlite3` versioned.
12. Do not run the full sample generator casually.
13. Promotion/Inventory generator logic exists even though inspected DB
    counts were zero.
14. Existing Manager Recommendation management must be reused.
15. V2.2 brief performance is 3 queries for 5 visits.
16. Final V2.2 order for sales1 is C0003, C0029, C0013, C0005, C0014.

------------------------------------------------------------------------

## 16. One-Line Handoff

``` text
V2.2 Sales Rep Daily Workspace is complete and browser-validated; safely commit/push V2.2, then begin V2.3 by inspecting existing target/quota/MSU/achievement code before designing any Sales Target models.
```
