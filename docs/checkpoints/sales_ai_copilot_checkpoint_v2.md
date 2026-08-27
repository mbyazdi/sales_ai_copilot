# Sales AI Copilot — Development Checkpoint V2

**Checkpoint purpose:** This file is designed to be pasted into a brand-new ChatGPT conversation so development can continue without losing architecture, business context, workflow decisions, implementation status, or coding preferences.

**Project:** `sales_ai_copilot`  
**Repository:** `https://github.com/mbyazdi/sales_ai_copilot.git`  
**Main branch:** `main`  
**Environment:** Windows / PowerShell / VS Code / Python virtualenv / Django / SQLite  
**Current Git state at last confirmed checkpoint:** clean and synced with `origin/main` after Stage 9.8 commit.

---

## 1. BUSINESS CONTEXT / PRODUCT NORTH STAR

This project is a Demo for a large trading/distribution company with approximately **700 field sales reps / visitors** and **several thousand customers** across the country.

The company sells through **field visits**. Sales reps follow planned daily customer visits, visit stores, take orders, and send them to the company for approval and fulfillment.

The Demo scope intentionally focuses on a smaller **Electrical business line**, including examples such as:

- Personal electrical products: shavers, hair dryers, etc.
- Home electrical products: blenders, fans, TVs, etc.

The system’s main goal is NOT to build a chatbot. The goal is to build a **Sales AI Copilot / Sales Decision Support System** that helps field sales reps make better commercial decisions before and during a customer visit.

Primary business outcomes:

1. Increase total sales.
2. Increase basket size / number of products sold.
3. Help sales reps move toward assigned monthly targets.
4. Maintain customer acceptance / satisfaction rather than simply pushing company targets.

The key question the final system should answer is:

> “For this customer, during this visit, what should this sales rep focus on, why, and how should they execute it?”

---

## 2. IMPORTANT PRODUCT SEPARATION

The product must be role-based and journey-based. Manager information, daily sales-rep information, and in-meeting customer information must NOT be mixed into one experience.

### 2.1 Manager Experience

Manager should see things like:

- Team overview
- Visit performance
- Sales / conversion
- Target achievement
- Recommendation performance
- Recommendation tuning / diagnostics / explainability
- Follow-up health
- Promotion effectiveness
- Commercial opportunity performance
- Trends / exceptions

### 2.2 Sales Rep Daily Workspace

Sales rep should see:

- Today’s visit plan
- Today’s customers
- Visit statuses
- Follow-ups
- Brief / priority per customer
- Target gap relevance
- High-priority opportunities
- Entry point into each customer visit workspace

### 2.3 Customer Visit / Sales Meeting Workspace

When the rep opens a customer:

- Customer brief / Customer 360
- Recommendations
- Sales opportunity
- Promotion relevance
- Target relevance
- Inventory relevance
- Talking point
- Next Best Action
- Outcome capture
- Follow-up capture
- Context-aware Copilot

---

## 3. CORE PRODUCT ARCHITECTURE

Keep these concepts separated:

### Recommendation Engine
Answers:

> “What fits this customer?”

Current Recommendation Engine v1 is rule-based and should be considered **frozen for now** except for bug fixes or necessary integration. Do NOT replace it with ML during the current Demo phase.

### Commercial Decision Layer
Should answer:

> “What should this sales rep focus on now?”

Inputs may include:

- Recommendation / customer-product fit
- Customer grade
- Customer behavior
- Sales rep target gap
- Promotion
- Inventory
- Previous outcomes
- Company commercial priority

### Next Best Action
Answers:

> “What should the sales rep do?”

### AI Copilot
Answers:

> “How can I help the rep understand and execute the approved decision?”

The LLM must NOT invent or override business facts. Backend-approved data and decisions remain authoritative.

---

## 4. BATCH / NIGHTLY ARCHITECTURE DIRECTION

The real system does not need to compute everything in real time.

A preferred future architecture is:

```text
Night before / batch
→ tomorrow's planned visits
→ calculate customer context
→ recommendation
→ promotion / target / inventory context
→ commercial decision
→ persist pre-visit intelligence

Next day
→ sales rep opens app
→ instant precomputed brief
```

This is important for future scalability across hundreds of sales reps and thousands of customers.

For the Demo, computation can still be on-demand where simpler, but design should not block batch/precompute later.

---

## 5. CUSTOMER BUSINESS DATA CONTEXT

Customers are categorized / graded in the real business based on factors such as:

- Payment discipline / good standing
- Purchase volume
- Market reputation / creditworthiness
- Store size
- Owner vs tenant
- Possibly other commercial factors

Customers may also belong to different price levels and possibly different promotion eligibility groups.

### Demo decision

Do NOT build a full customer credit-scoring engine now.

Use existing `CustomerGrade` as master data supplied by the business.

---

## 6. SALES REP TARGET BUSINESS RULES

In the real business, sales reps may have monthly targets by:

- Product
- Category
- Business line

Target units are often quantity / MSU based.

Sales rep performance may be rewarded based on achievement.

For Demo V2, target domain should likely support:

```text
Salesperson
Period / Month
Scope type: Product / Category / Line
Target unit: MSU / Quantity
Target value
Actual
Remaining
Achievement %
```

Do NOT implement compensation / payroll bonus calculations in Demo V2.

---

## 7. PROMOTION BUSINESS RULES

Real examples:

- Buy 12 units → get 1 free
- Buy above a monetary threshold → receive discount / purchase bonus

Promotions may target:

- Product
- Category
- Customer grade
- Date range

Current model supports some but not all of this.

---

## 8. VISIT PLANNING BUSINESS RULES

Visit schedules are typically planned monthly by supervisors/managers.

Sales reps have a daily list of customers they must visit.

Routing / route optimization is explicitly OUT OF SCOPE for the Demo.

Use existing `Visit` lifecycle rather than creating a new VisitPlan model unless later evidence requires it.

Existing status choices:

```text
PLANNED
IN_PROGRESS
COMPLETED
CANCELLED
```

This is sufficient for Demo visit planning lifecycle.

---

## 9. PROJECT DIRECTION / ORIGINAL BUSINESS WORKFLOW

Main business flow:

```text
Customer 360
→ Behavior
→ Recommendation
→ Opportunity
→ Talking Point
→ Sales Action
→ Outcome
→ Feedback
→ Next Recommendation
```

Current understanding is that much of this already exists, but some middle layers are too simple / inline / mixed into views.

---

## 10. DEVELOPMENT APPROACH / USER PREFERENCES

When giving code changes, ALWAYS use this format:

```text
FILE
OPEN — exact VS Code Ctrl+P path
FIND — exact code/text
ADD / REPLACE / DELETE
RUN — validation commands
```

Do NOT tell the user to manually browse the VS Code file tree.

### Django shell preference

For multi-line Django shell tests ALWAYS use:

```powershell
python manage.py shell
```

Then provide the full test using:

```python
exec("""
...
""")
```

Do NOT provide multi-line interactive shell code that requires manual indentation.

### Validation habit

After code changes normally run:

```powershell
python manage.py check
git diff --check
```

For schema changes additionally:

```powershell
python manage.py makemigrations <app>
python manage.py migrate
```

### Git workflow between environments

The user works from two environments: home and office.

When entering an environment:

```powershell
git fetch
git status
```

Only if working tree is clean:

```powershell
git pull --ff-only
```

When leaving:

```powershell
git status
# review changes
git add ...
git commit ...
git push
git status
```

Final state should be clean and synced with `origin/main`.

The user intentionally wants `db.sqlite3` committed because it is part of the Demo dataset.

---

## 11. PROJECT TECHNICAL BASELINE

Project path:

```text
D:\py project\sales_ai_copilot
```

Core apps:

```text
ai
core
customers
inventory
management
products
promotions
recommendations
sales
visits
```

Primary stack:

- Python 3.13.x
- Django 6.x
- SQLite for Demo
- Django/DRF
- Ollama for local LLM integration

Architecture direction remains API-driven so a future React/Vue frontend or independent frontend remains possible.

UI target:

- Modern SaaS Dashboard
- AI-first but not chat-first
- Product-oriented
- Professional / customer-facing Demo quality

Preferred Persian fonts if available:

- Yekan
- IRANSans Sharp / Iran Sharp

---

## 12. EXISTING DATA MODELS — CONFIRMED

### customers

#### CustomerGrade

Fields:

```text
code
name
description
priority
is_active
created_at
updated_at
```

#### Customer

```text
customer_code
name
customer_type
grade -> CustomerGrade
city
address
phone
is_active
created_at
updated_at
```

#### Customer360

```text
customer -> Customer
total_orders
total_items
total_sales_amount
average_order_value
last_purchase_date
first_purchase_date
purchase_frequency
days_since_last_purchase
recency_score
frequency_score
monetary_score
rfm_score
segment
top_category
top_product_code
sales_30d
sales_90d
sales_30d_change_percent
sales_90d_change_percent
calculated_at
```

### visits

#### Salesperson

```text
employee_code
user -> User
first_name
last_name
phone
is_active
created_at
updated_at
```

#### CustomerAssignment

```text
salesperson
customer
start_date
end_date
is_active
created_at
```

#### Visit

```text
salesperson
customer
visit_date
status
customer_request
customer_feedback
competitor_information
notes
order_created
order_amount
follow_up_required
follow_up_date
created_at
updated_at
```

Status choices:

```text
PLANNED
IN_PROGRESS
COMPLETED
CANCELLED
```

#### SalesOutcome

```text
visit
recommendation -> CustomerRecommendation
outcome
quantity
sales_amount
notes
created_at
```

#### FollowUpTask

```text
customer
visit
salesperson
due_date
status
notes
completed_at
created_at
updated_at
```

### promotions

#### Promotion

```text
name
code
promotion_type
start_date
end_date
discount_percent
discount_amount
minimum_quantity
maximum_quantity
description
is_active
products M2M through PromotionProduct
customer_grades M2M CustomerGrade
created_at
updated_at
```

Promotion types:

```text
PERCENTAGE
FIXED_AMOUNT
BUY_X_GET_Y
```

Known current limitations:

- `BUY_X_GET_Y` has no explicit Y/free quantity field.
- There is no explicit minimum purchase amount field for value-threshold promotions.
- No dedicated Promotion API/UI yet.

#### PromotionProduct

```text
promotion
product
priority
```

### inventory

#### Inventory

```text
product -> Product
available_quantity
reserved_quantity
minimum_stock
last_updated
```

No dedicated Inventory API/UI yet.

### sales

#### Sale

```text
customer
invoice_number
sale_date
total_amount
description
created_at
updated_at
```

#### SaleItem

```text
sale
product
quantity
unit_price
discount_amount
total_amount
created_at
```

There is no full separate Order / Approval / Fulfillment domain yet. For Demo this may remain simplified.

---

## 13. CUSTOMER 360 / INSIGHTS STATUS

`Customer360` metrics are built from sales using `apps/customers/services.py`.

Existing metrics include:

- Orders
- Total items
- Total sales
- Average order value
- First / last purchase date
- Purchase frequency
- RFM
- Segment
- Top category
- Top product
- Sales 30d / 90d

`apps/customers/insights.py` contains:

```python
build_customer_insight(...)
```

Customer 360 is considered **DONE / STRONG** for current Demo baseline.

---

## 14. RECOMMENDATION ENGINE STATUS

Recommendation Engine v1 is mature enough for Demo and should not be reworked for performance now.

Current engine is rule-based.

Relevant signals include:

- group affinity
- repurchase
- association
- upsell
- customer grade
- promotion
- similar product
- historical outcome feedback

Historical outcome feedback is already included in scoring.

Recommendation Engine currently uses Promotion only as a relatively simple active-promotion signal / score boost.

Inventory is NOT currently part of Recommendation Engine scoring.

### Important architectural decision

Do NOT force Salesperson Target or full Commercial Priority into Recommendation Engine.

Recommendation Engine remains responsible for customer-product fit.

Commercial Decision Layer will sit above it.

---

## 15. STAGE 8 — COMPLETED

Stage 8 delivered Recommendation Performance / Tuning lifecycle including:

- Recommendation Performance
- Tuning suggestions
- Approve / Reject
- Apply
- Rollback
- Audit fields
- Stale suggestion protection
- Allowed tuning range protection
- Maximum delta protection
- Full generate → approve → apply → rollback lifecycle
- Manager tuning UI
- Filtering
- CSS
- Cleanup of test records

Rollback tested successfully.

Stale apply protection tested.

Unsafe values blocked.

Final similar_product_score after cleanup was `17.00`.

---

## 16. STAGE 9 — EXPLAINABILITY — COMPLETED

Stage 9 evolved Recommendation Engine from black-box scoring toward explainable decisions.

### CustomerRecommendation model additions

File:

```text
apps/recommendations/models.py
```

Added:

```python
confidence_score = models.DecimalField(
    max_digits=6,
    decimal_places=2,
    default=0,
)

evidence_quality = models.CharField(
    max_length=20,
    default="LOW",
)

explanation_snapshot = models.JSONField(
    default=dict,
    blank=True,
)
```

Migration:

```text
0011_customerrecommendation_confidence_score_and_more.py
```

Applied successfully.

### score_breakdown

Current score breakdown includes:

```text
group_score
purchase_score
association_score
upsell_score
grade_score
promotion_score
similar_score
rule_score
feedback_score
final_score
```

### explanation_snapshot

Signals include:

```text
group_affinity
repurchase
association
upsell
customer_grade
promotion
similar_product
historical_feedback
```

Snapshot includes:

```text
signals
rule_score
feedback_score
final_score
active_signal_count
confidence_score
evidence_quality
```

### Confidence

Confidence is intentionally separate from recommendation score.

Current evidence quality logic:

```text
>= 4 active signals → HIGH
>= 2 active signals → MEDIUM
otherwise → LOW
```

Example:

```text
C0001 / PHI004
Final Score: 50
Confidence: 80
Evidence: MEDIUM
Active Signals: 3
```

---

## 17. STAGE 9 — CUSTOMER 360 EXPLAINABILITY UI — COMPLETED

Actual partial:

```text
templates/core/customer_360/_ai_explainability.html
```

Do NOT modify old backup:

```text
templates/core/customer_360_back.html
```

UI displays:

- Confidence
- Evidence Quality
- Rule Score
- Historical Feedback
- Final Score
- Active signal breakdown
- Dynamic reasons from `explanation_snapshot.signals`

Historical feedback supports positive and negative explanations.

CSS:

```text
static/core/css/customer_360.css
```

---

## 18. STAGE 9.6–9.8 — MANAGER EXPLAINABILITY / DIAGNOSTICS — COMPLETED

Manager Recommendation Performance page:

```text
templates/management/recommendation_performance.html
```

Explainability partial:

```text
templates/management/_recommendation_explainability.html
```

JS:

```text
static/management/js/recommendation_explainability.js
```

CSS:

```text
static/management/css/recommendation_performance.css
```

### Diagnostics API

```text
/api/recommendations/v1/diagnostics/
```

Manager-only using `IsAdminUser`.

Returns active recommendations with:

```text
id
customer_code
rank
product_code
product_name
recommendation_type
score
confidence_score
evidence_quality
active_signal_count
rule_score
feedback_score
score_breakdown
explanation_snapshot
```

### Diagnostics Summary API

```text
/api/recommendations/v1/diagnostics/summary/
```

After controlled regeneration of all active recommendations, current Demo snapshot was:

```text
total_recommendations: 49
average_confidence: 61.84
HIGH: 11
MEDIUM: 34
LOW: 4
low_confidence: 18
negative_feedback: 0
single_signal: 4
```

All active recommendations were regenerated through official `RecommendationEngine.generate()` to backfill Explainability.

Post-regeneration:

```text
TOTAL ACTIVE: 49
ZERO CONFIDENCE: 0
NON-ZERO CONFIDENCE: 49
EMPTY SNAPSHOT: 0
NON-EMPTY SNAPSHOT: 49
```

### Manager Summary UI

8 KPI cards:

- Active Recommendations
- Average Confidence
- High Evidence
- Medium Evidence
- Low Evidence
- Low Confidence
- Negative Feedback
- Single Signal

### Detail Drill-down API

```text
/api/recommendations/v1/diagnostics/<recommendation_id>/
```

Returns:

```text
id
customer_code
rank
product {code, name}
recommendation_type
score
confidence_score
evidence_quality
reason
active_signal_count
rule_score
feedback_score
score_breakdown
explanation_snapshot
```

Permissions tested:

```text
manager1 → 200
missing recommendation → 404
anonymous → 403
```

### Drawer UI

Diagnostics rows are clickable / keyboard accessible.

A Side Drawer opens with:

- Product / customer
- Final score
- Confidence
- Evidence
- Active signals
- Score breakdown
- Signals
- Reason
- Metadata

Close works with:

- X button
- Backdrop
- Escape

Stage 9.8 final Git state was clean and pushed.

---

## 19. SALES REP DAILY WORKSPACE — EXISTING FOUNDATION

Current view:

```python
salesperson_dashboard(request)
```

Current problem:

```python
Salesperson.objects.filter(employee_code="SP001", is_active=True)
```

Salesperson is hard-coded to `SP001`.

This MUST eventually change to logged-in user mapping:

```text
request.user
→ salesperson_profile
→ My Visits
```

Existing Dashboard already shows:

- Today’s visits
- Planned count
- In-progress count
- Completed count
- Cancelled count
- Customer code
- Customer name
- Customer grade
- City
- Segment
- Link to Customer 360

Template:

```text
templates/visits/dashboard.html
```

Current conclusion:

```text
Sales Rep Daily Workspace = PARTIAL, strong foundation
```

Do NOT rebuild from zero.

---

## 20. FOLLOW-UP WORKFLOW — COMPLETED / STRONG

Follow-up Dashboard is already user-aware:

```python
salesperson = getattr(
    request.user,
    "salesperson_profile",
    None,
)
```

Open tasks are scoped to that salesperson.

Tasks are grouped into:

```text
Overdue
Today
Upcoming
```

This existing pattern should be reused for role-aware Sales Rep behavior.

---

## 21. MANAGER EXPERIENCE — CURRENT STATUS

Manager app currently contains only one real management page:

```text
management/recommendations/performance/
```

View protected by:

```python
@staff_member_required(login_url="/accounts/login/")
```

Recommendation management APIs use `IsAdminUser`.

Current manager functionality is strong specifically for:

- Recommendation performance
- Recommendation tuning
- Explainability diagnostics
- Quality summary
- Recommendation drill-down

But Manager overall workspace is still narrow.

`templates/base.html` currently has hard-coded identity text such as:

```text
Sales Manager
Sales Representative
```

Navigation links are mostly `href="#"`.

Therefore:

```text
Manager authorization = EXISTS
Role-aware manager UX = PARTIAL / GAP
```

---

## 22. ROLE SEPARATION — MAJOR GAP

Foundation exists:

```text
Manager → staff_member_required / IsAdminUser
Sales Rep → User ↔ Salesperson
```

But UI/navigation are not role-aware.

V2 should ensure:

```text
Manager login → Manager workspace
Sales Rep login → Sales Rep Daily Workspace
Sales Rep sees only their own visits/tasks/data
```

This is expected to be the first implementation stage in Roadmap V2.

---

## 23. PROMOTION CURRENT IMPLEMENTATION

Files:

```text
apps/promotions/models.py
apps/promotions/services.py
apps/promotions/views.py
```

Current `views.py` is effectively empty.

No dedicated `promotions/urls.py`.

No Promotion API/UI currently exposed to the sales rep.

Recommendation Engine imports `PromotionProduct` and uses active promotion existence to add a promotion score.

Important current behavior:

```text
active PromotionProduct exists
→ promotion_score boost
→ explanation may say active promotion exists
```

It does NOT currently expose full promotion mechanics to the rep.

---

## 24. INVENTORY CURRENT IMPLEMENTATION

Files:

```text
apps/inventory/models.py
apps/inventory/services.py
apps/inventory/views.py
```

Current `views.py` is effectively empty.

No dedicated `inventory/urls.py`.

No Inventory API/UI currently exposed.

Inventory is not currently consumed by Recommendation Engine.

For Demo, current global product-level inventory is acceptable; no warehouse/region complexity is needed.

---

## 25. SALES TARGET — CONFIRMED MAJOR GAP

Extensive search found no meaningful implementation for:

```text
target
quota
MSU
achievement
```

Therefore current status:

```text
Sales Target
Data: MISSING
Logic: MISSING
API: MISSING
UI: MISSING
```

This is one of the largest new business capabilities needed in V2.

---

## 26. SALES OPPORTUNITY / TALKING POINT / NEXT BEST ACTION — EXISTING BUT SIMPLE

Current `apps/customers/views.py` builds:

```text
customer_status
sales_opportunity
primary_product
recommendation_type
talking_point
next_best_action
```

The logic is inline and mostly based on:

- days_since_last_purchase
- recommendation_type
- primary recommendation

Examples:

```text
REPEAT_PURCHASE
CROSS_SELL
CATEGORY
SIMILAR_PRODUCT
UP_SELL
```

These concepts are therefore NOT missing, but they are currently **simple / rule-based / presentation-level**.

Do NOT create duplicate Opportunity/Talking Point/NBA models or endpoints unless a later design truly requires persistence.

Current conclusion:

```text
Opportunity = PARTIAL
Talking Point = PARTIAL
Next Best Action = PARTIAL
```

---

## 27. AI COPILOT CURRENT IMPLEMENTATION

Main endpoint:

```text
/api/ai/v1/sales-copilot/
```

View:

```text
apps/ai/views.py
SalesCopilotAPIView
```

Service:

```text
apps/ai/services.py
generate_sales_copilot_response(...)
```

Prompt builder:

```text
apps/ai/prompt_builder.py
build_sales_copilot_prompt(...)
```

Context builder:

```text
apps/customers/services.py
build_sales_ai_context(...)
```

Current AI context contains:

```text
customer
customer_360
current_visit
sales_session
recommendations
```

Current customer_360 context includes data such as:

```text
segment
total_orders
total_sales_amount
average_order_value
last_purchase_date
days_since_last_purchase
top_category
top_product_code
rfm_score
```

However current prompt builder consumes only part of those fields.

### Important AI guardrail already implemented

Prompt builder explicitly says:

- Recommendations are decided by Rule-Based Recommendation Engine.
- LLM must not replace, reorder, or invent recommendations.
- LLM must not invent pricing, inventory, promotion, product claims, customer behavior, etc.
- Backend facts are authoritative.

This principle MUST be preserved.

### Current limitation

The current AI service is mostly a **controlled wording assistant**.

It largely asks the LLM to rewrite:

```text
APPROVED TALKING POINT
APPROVED NEXT ACTION
```

in natural Persian.

The eventual V2 Copilot should become **grounded context-aware Q&A**, e.g. answer:

- Why this recommendation?
- What happened in the last visit?
- What should I focus on today?
- What promotion applies?
- How far am I from target?
- Is there an open follow-up?
- What should I say if customer rejects the first proposal?

For out-of-scope questions, return a logical scope-aware answer rather than repeating recommendations.

Do NOT prioritize changing the LLM model until context and guardrails are improved.

---

## 28. IMPORTANT DUPLICATION FOUND

Sales Session logic is currently duplicated in at least:

```text
apps/customers/views.py
apps/ai/views.py
```

Both build variants of:

```text
customer_status
sales_opportunity
talking_point
next_best_action
```

This duplication should eventually be consolidated to a single source of truth, probably through a service function such as conceptually:

```python
build_sales_session(...)
```

Likely location:

```text
apps/customers/services.py
```

But do NOT start this refactor blindly before considering V2 priorities. Business-value stages come first.

---

## 29. V2 GAP ANALYSIS — FINAL STATUS

### Manager Journey

```text
Authorization: EXISTS
Recommendation Console: STRONG
General Manager Dashboard: PARTIAL
Target/Team/Visit/Sales overview: GAP
Role-aware navigation: GAP
```

### Sales Rep Journey

```text
Salesperson identity: EXISTS
Today's Visits: EXISTS
Visit lifecycle: EXISTS
Follow-up: EXISTS
Role-aware login → own workspace: PARTIAL/GAP
Pre-visit brief: GAP
Target context: GAP
Commercial priority: GAP
```

### Customer Visit Journey

```text
Customer 360: STRONG
Recommendations: STRONG
Explainability: STRONG
Opportunity/Talking Point/NBA: EXISTS but SIMPLE
Promotion detail: GAP
Inventory relevance: GAP
Target relevance: GAP
Context-aware Q&A: GAP
Outcome/Follow-up: STRONG
```

### Commercial Decision Layer

Current status:

```text
MISSING as an explicit layer
```

This is the main architectural gap.

---

## 30. ROADMAP V2 — FROZEN INITIAL PLAN

### V2.0 — Gap Analysis & Architecture

**STATUS: COMPLETED / CLOSED**

This checkpoint is the output of that stage.

### V2.1 — Role & Experience Foundation

Estimated: **4–6 hours**

Goals:

- Remove hard-coded `SP001` behavior.
- Bind Sales Rep workspace to logged-in `request.user.salesperson_profile`.
- Create role-aware navigation / identity.
- Manager login → manager experience.
- Sales Rep login → own daily workspace.
- Prevent sales reps from seeing other reps’ data.

This should be the FIRST implementation stage after this checkpoint.

### V2.2 — Sales Rep Daily Workspace V2

Estimated: **5–8 hours**

Reuse existing Dashboard; do NOT rebuild.

Add / improve:

- Customer priority
- Pre-visit summary placeholder / brief
- Follow-up relevance
- Target relevance placeholder
- Better entry into visit workspace

### V2.3 — Sales Target Foundation

Estimated: **8–12 hours**

New domain likely needed.

Support Demo requirements:

```text
Salesperson
Period
Product / Category / Line scope
MSU / Quantity unit
Target
Actual
Remaining
Achievement %
```

No commission payroll logic.

### V2.4 — Commercial Context

Estimated: **6–10 hours**

Make Promotion and Inventory usable.

Minimum desired Promotion V2 features:

- Percentage
- Fixed amount
- Buy X Get Y
- Product eligibility
- Customer Grade eligibility
- Date validity

Potential model additions only if needed:

- free quantity / Y for BUY_X_GET_Y
- minimum purchase amount for value-threshold promotions

Expose appropriate Promotion/Inventory context to Sales Rep / Decision Layer.

### V2.5 — Commercial Decision Layer

Estimated: **10–15 hours**

Main new business layer.

Inputs:

```text
Recommendation / Customer Fit
Target Gap
Promotion
Inventory
Customer Grade
Historical Outcome
```

Outputs conceptually:

```text
Opportunity Priority
Primary Sales Focus
Why Now
Next Best Action
Talking Point source facts
```

Do NOT replace Recommendation Engine.

### V2.6 — Pre-Visit Intelligence / Nightly-ready

Estimated: **5–8 hours**

Build customer-specific visit brief suitable for precomputation.

Design for:

```text
Tomorrow's Visit
→ build intelligence
→ persist / snapshot
→ instant next-day UI
```

Can initially run on-demand if simpler.

### V2.7 — Customer Visit Workspace V2

Estimated: **7–11 hours**

Enhance existing Customer 360 rather than creating duplicate page.

Show rep-relevant items:

- Customer Brief
- Primary Opportunity
- Recommendations
- Promotion
- Target relevance
- Inventory
- Why this action
- Talking Point
- Next Best Action
- Outcome / Follow-up

Keep manager diagnostics out unless rep needs them.

### V2.8 — Context-Aware Copilot V2

Estimated: **8–13 hours**

Upgrade from wording assistant to grounded business Q&A.

Preserve:

- Backend facts authoritative
- LLM does not invent recommendations or commercial facts
- Scope-aware response behavior

### V2.9 — Manager Workspace V2

Estimated: **8–13 hours**

Reuse existing Recommendation Performance / Tuning / Diagnostics.

Add broader management view such as:

- Team overview
- Visits
- Sales / conversion
- Target achievement
- Follow-up
- Recommendation performance
- Commercial opportunity performance

### V2.10 — Demo Integration & Polish

Estimated: **6–10 hours**

End-to-end Hero Demo:

```text
Manager
→ Target / Promotion setup
→ visit intelligence

Sales Rep login
→ Today's Customers
→ Customer Visit Workspace
→ Commercial Opportunity
→ Recommendation + Target + Promotion
→ Copilot question
→ Outcome
→ Follow-up

Manager
→ Performance / feedback
```

---

## 31. CURRENT ESTIMATED V2 TIME

For V2.1–V2.10:

```text
Minimum: ~67 hours
Maximum: ~106 hours
Practical strong-demo range: ~70–85 focused development hours
```

At approximately 5–6 focused development hours/day:

```text
~12–17 focused working days
```

This estimate excludes:

- Production deployment
- Enterprise integrations
- Full automated test suite expansion
- Route optimization
- ERP order approval workflow
- Full warehouse-level inventory
- ML replacement of Recommendation Engine
- Commission / payroll engine

---

## 32. CRITICAL DEMO PATH

Highest-priority execution order:

```text
V2.1 Roles
→ V2.2 Rep Workspace
→ V2.3 Targets
→ V2.4 Commercial Context
→ V2.5 Decision Layer
→ V2.6 Pre-Visit Brief
→ V2.7 Visit Workspace
→ V2.8 Copilot
→ V2.10 Demo Polish
```

V2.9 Manager Workspace is also important, but much of Recommendation Management already exists and can be incrementally expanded.

---

## 33. EXPLICIT OUT-OF-SCOPE FOR DEMO V2

Do NOT allow scope creep into:

- Route Optimization / GPS
- Full ERP order approval workflow
- Warehouse / regional inventory complexity
- Commission / bonus payroll engine
- Customer credit-scoring engine
- ML/XGBoost replacement of Recommendation Engine
- Complex promotion optimization
- Production hardening beyond what Demo needs

Architecture should allow these later, but they are not current priorities.

---

## 34. NEXT ACTION — EXACT CONTINUATION POINT

**Do NOT repeat Gap Analysis.**

V2.0 is complete.

Start with:

```text
V2.1 — Role & Experience Foundation
```

First substep should be a very small design/inspection step before code changes:

1. Confirm current login URL and authentication flow.
2. Confirm `Salesperson.user` related name / how `request.user.salesperson_profile` is defined.
3. Confirm intended landing URLs for:
   - Manager
   - Sales Rep
4. Then make the smallest safe change to remove hard-coded `SP001` from `salesperson_dashboard`.
5. Reuse the existing follow-up pattern using logged-in user.
6. Do NOT build new role models unless absolutely necessary.

After every change:

```powershell
python manage.py check
git diff --check
```

For multi-line Django tests, use `exec("""...""")`.

---

## 35. IMPORTANT WARNINGS FOR FUTURE CONVERSATIONS

- Do not modify `templates/core/customer_360_back.html` unless explicitly needed.
- Actual Customer 360 explainability partial is:
  `templates/core/customer_360/_ai_explainability.html`
- Actual Manager Recommendation page is:
  `templates/management/recommendation_performance.html`
- Manager diagnostics are already implemented; do not rebuild them.
- Recommendation Engine v1 should remain stable for now.
- Do not jump into ML yet.
- Do not create duplicate Opportunity / Talking Point / NBA layers without checking existing logic.
- Do not treat AI Chat as the product core.
- Keep Manager, Sales Rep Daily Workspace, and Customer Visit Workspace separate.
- Preserve backend-authoritative facts and LLM guardrails.
- Prefer incremental, low-risk changes and test every small step.
- Demo DB (`db.sqlite3`) should continue to be versioned in Git.

---

## 36. ONE-SENTENCE PROJECT NORTH STAR

> Build a role-based Sales AI Copilot that prepares the right commercial decision for each planned customer visit, helps the sales rep execute it using grounded context, captures the outcome, and feeds the result back into future recommendations — while giving managers a separate view of team and recommendation performance.

