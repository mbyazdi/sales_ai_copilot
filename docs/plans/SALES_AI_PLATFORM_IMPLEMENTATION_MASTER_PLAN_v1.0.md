# Sales AI Platform --- Implementation Master Plan v1.0

**Depends on:** Product + Architecture Checkpoint v1.1

## 1. Delivery principles

-   Audit before rewriting.
-   L1 end-to-end journey takes priority over L2/L3.
-   Use one canonical dataset and domain model.
-   Keep business policy deterministic and explainable.
-   Use AI for understanding, synthesis, explanation and conversation.
-   Build professional Persian RTL UI from the first implementation.
-   Avoid premature microservices and advanced ML.

## 2. Workstreams

### WS0 --- Existing Project Audit

Inventory project structure, apps, models, migrations, APIs,
authentication, recommendation engine, AI integration, frontend, tests,
dependencies, settings and demo data.

**Output:** KEEP / REFACTOR / REPLACE / ADD matrix with rationale and
dependencies.

### WS1 --- Platform Foundation

Settings/environment cleanup, API conventions, role/scope authorization,
audit fields, logging/error handling, demo-mode configuration and base
test strategy.

### WS2 --- Design System & Frontend Shell

Persian RTL foundations, typography, spacing, semantic colors,
responsive breakpoints, navigation, Help/Info, loading/empty/error
patterns and reusable domain components.

No hero screen may invent its own visual language.

### WS3 --- Canonical Demo Dataset

Suggested scale: 3 sales lines, 3--5 regions, 5--10 supervisors, 20--30
reps, 100--200 customers, 80--150 products, several thousand invoice
lines, targeted visits/returns/payments, 5--10 promotions, targets and
2--4 initiatives.

The same facts must drive Customer 360, Guided Sale, Basket, Targets and
Manager screens.

### WS4 --- Core Master Domains

Organization, sales line, territory, employee assignment,
customer/profile/grade, product/brand/category/SKU, product attributes,
price, inventory, promotion and credit/commercial summary.

### WS5 --- Field Execution

Route, daily plan, route stops, visit, visit status, notes, verification
abstraction, pre-visit context and visit completion.

### WS6 --- Commercial History & Outcomes

Canonicalize orders, invoices/lines, delivery summary, returns/reasons,
credit/payment summary and complaints as needed. Preserve
order/invoice/return lineage.

### WS7 --- Targets & Initiatives

Implement target definition/hierarchy/manual
allocation/actual/gap/progress plus initiative definition/product
scope/audience/priority/playbook/basic eligibility.

### WS8 --- Intelligence Foundation

Implement explainable rule/analytics v1: - Customer Strategy Engine -
Commercial Policy Engine - Opportunity Engine - Recommendation Engine -
Quantity Engine

All return structured reasons.

### WS9 --- Sales Rep L1 Experience

Build in order: 1. Home / Daily Brief 2. Route 3. Customer 360 4.
Pre-Visit 5. Visit Start 6. Standard Sale 7. Guided Smart Sale 8.
Product 360 9. Product Advisor 10. Basket 11. Order Review/Submit 12.
Visit Summary 13. Basic Action/Follow-up

### WS10 --- Product Knowledge

Approved product knowledge, media, specifications, selling points,
objections, manufacturer-source metadata, approved review insights and
Customer Presentation Mode.

### WS11 --- AI Services

Provider abstraction, Persian responses, structured outputs and fallback
behavior.

L1: Daily Brief narrative, Product Advisor need extraction, Sales
Copilot, explanation enhancement, visit-note extraction/summary.

### WS12 --- Manager & Supervisor L2

Manager Overview, Target Progress, Initiative Funnel, risks, AI
Management Brief; Supervisor Team Today, Route Execution, Target Risk,
issues and approval/coaching shell.

### WS13 --- Target Allocation L2

Hierarchy visualization, manual allocation, allocated/unallocated
validation, historical reference, explainable AI/rule suggestion,
manager override, publish state and audit history.

### WS14 --- Initiative Builder & Analytics L2

Builder: Objective → Products → Audience → Offer → Playbook → Target →
Review/Publish.

Analytics: Eligible → Visited → Presented → Accepted → Ordered →
Delivered → Retained, plus Gross/Returns/Net where available.

## 3. Experience API candidates

Subject to audit: - `/api/v1/me/daily-brief` - `/api/v1/me/route` -
`/api/v1/customers/{id}/360` - `/api/v1/visits/{id}/pre-visit` -
`/api/v1/visits/{id}/guided-sale/session` -
`/api/v1/guided-sale/{session_id}/next` - `/api/v1/products/{id}/360` -
`/api/v1/product-advisor` - `/api/v1/baskets/{id}` - `/api/v1/orders` -
`/api/v1/visits/{id}/summary` - `/api/v1/manager/overview` - target and
initiative APIs

## 4. Milestones

**M0 Audit Complete** --- current system understood and migration
strategy approved.\
**M1 Foundation Ready** --- roles, masters, design-system shell,
demo-data framework.\
**M2 Customer & Visit Ready** --- Home, Route, Customer 360, Pre-Visit.\
**M3 Smart Selling Ready** --- Standard + Guided Sale +
recommendation/quantity engines.\
**M4 Product Intelligence Ready** --- Product 360 + knowledge + Product
Advisor.\
**M5 Transaction Loop Ready** --- Basket/order/visit summary +
recommendation lineage.\
**M6 Strategy Loop Ready** --- Targets and initiative context reflected
in rep flow.\
**M7 Management Story Ready** --- Manager overview, analytics and AI
brief.\
**M8 Demo Hardening** --- reset, fallbacks, responsive/RTL polish,
performance and rehearsal.

## 5. L1 acceptance criteria

1.  Correct role-scoped login.
2.  Daily Brief reflects canonical data.
3.  Route/customer context is coherent.
4.  Pre-Visit shows mission, opportunity and warnings.
5.  Customer 360 reflects sales, financial and return history.
6.  Standard Sale supports fast selection.
7.  Guided Sale returns ranked recommendations.
8.  Lens/category controls affect experience.
9.  Recommendation reasons are structured.
10. Promotion-overbuy customer gets return-aware quantity.
11. Financial-risk customer gets correct warning/restriction.
12. Product 360 professionally presents a new product.
13. Product Advisor converts Persian need to product candidates.
14. Basket preserves source/recommendation lineage.
15. Commercial constraints are checked before submit.
16. Visit Summary captures outcome/follow-up.
17. Target progress reacts to demo transactions.
18. Manager view shows meaningful field consequences.
19. LLM failure does not break core selling.
20. Hero screens pass visual/RTL/responsive quality gates.

## 6. UX quality gate

Every hero screen must have Persian copy, correct RTL, professional
hierarchy, device-appropriate layouts, clear primary action, realistic
density, contextual warnings, Help/Info, loading/empty/error states,
accessible touch targets and consistent shared components.

## 7. Engineering quality gate

Critical rules require automated tests; hero APIs require tests;
permissions are server-side; recommendation/quantity, promotion/return
and financial restriction edge cases are tested; sensitive changes are
auditable; critical rules never live only in frontend or LLM prompts.

## 8. Scope control

-   L1 before L2/L3.
-   New ideas go to backlog unless they block the core journey.
-   L2 UI remains production-quality even when logic is simplified.
-   No microservice extraction without measured need.
-   No advanced ML before baseline analytics and outcome data.
-   No full offline sync in the first demo.
-   No ERP/WMS/finance replacement.
-   No uncontrolled internet content in customer-facing knowledge.

## 9. Immediate next action: Django project audit

Preferred input is a project archive or repository snapshot containing
the project/app tree, settings, dependency file, models,
serializers/views/URLs, recommendation services, AI integration, current
frontend/templates/static files, relevant migrations, fixtures/demo data
and tests.

The audit produces the KEEP / REFACTOR / REPLACE / ADD matrix and the
first implementation backlog.
