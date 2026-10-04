# Sales AI Platform --- Product + Architecture Checkpoint v1.1

**Status:** Baseline approved for engineering\
**Product language:** Persian (RTL-first)\
**Architecture direction:** Django/DRF + modern independent frontend/PWA

## 1. Vision

Build an end-to-end intelligent sales platform for a large field-sales
distribution company. The product must improve sales effectiveness,
profitability, customer fit, organizational execution, and operating
efficiency---not merely provide a chatbot or a recommendation widget.

## 2. Confirmed product principles

-   Final user-facing product is Persian-only and RTL-first; it will not
    be developed as bilingual.
-   Technical internals such as code, APIs, classes and database naming
    may remain English.
-   The UI must be professional from the first implementation: simple at
    first glance, rich on demand, responsive, role-aware and demo-ready.
-   Mobile, tablet and desktop are distinct responsive experiences built
    from one design system.
-   Help/Info is part of the product contract so business rationale is
    preserved in demos and production.
-   The product should cover the full sales journey while controlling
    implementation scope through L1/L2/L3.

## 3. Core selling experience

Two modes are mandatory:

### Standard Sale

Fast catalog/search/filter/quantity workflow for experienced
representatives.

### Guided Smart Sale

Products are presented one by one. The representative can continue until
satisfied or candidates are exhausted, change ranking lens, filter
categories, inspect reasons and product knowledge, adjust quantity, add,
skip or reject.

Potential lenses: Recommended, Customer Fit, My Target, Company Focus,
Promotions, New Products.

## 4. Product knowledge and Product Advisor

Product 360 supports media, specifications, selling points, use cases,
manufacturer information, approved external-review insights, objections,
offers and comparison.

External knowledge follows: External Source → Fetch → Extract →
Source/Date → AI Summary → Review/Approval → Approved Knowledge → Sales
Experience.

Conversational Product Advisor follows: Natural-language need →
structured need → eligible product matching → business ranking →
explanation.

Customer fit and eligibility precede organizational priorities.

## 5. Customer intelligence

Customer Grade, dynamic financial/commercial health and Customer
Strategy are separate.

Commercial states may include NORMAL, WATCH, RESTRICTED and BLOCKED.
Hard blocks come from explicit company policy/authorized systems, not
free-form AI judgment.

Customer Strategy may include GROW, DEVELOP, MAINTAIN, PROTECT, RECOVER,
REACTIVATE and RESTRICT.

## 6. Opportunity and recommendation

Opportunity represents a persistent commercial opportunity;
Recommendation is a contextual decision snapshot.

Opportunity signals may include REORDER, CROSS_SELL, WHITE_SPACE,
UPSELL, NEW_PRODUCT, TARGET_RECOVERY, INITIATIVE, INVENTORY_PUSH,
PROMOTION, CUSTOMER_REACTIVATION and CUSTOMER_NEED.

Recommendation preserves customer/product, visit/session, rank, score,
lens, reasons, suggested quantity, offer context, decision version and
timestamp.

Generated, rep-viewed, customer-presented, accepted/rejected and ordered
are distinct events.

## 7. Return-aware and promotion-aware intelligence

Gross sales must never automatically be treated as true customer demand.

Required concepts include Gross Invoiced Qty, Returned Qty, Net Retained
Qty, Effective Demand, Return Risk and Promotion Overbuy Risk.

Return reason matters. Product defect/delivery error must be
distinguished from overstock, low sell-through and promotion overbuy.

Ranking and quantity estimation remain separate.

Suggested quantity conceptually follows: Historical Demand → Return
Adjustment → Promotion Distortion → Expected Demand → Promotion
Optimization → Inventory Constraint → Credit Constraint → Pack/MOQ Rules
→ Commercially Safe Quantity.

## 8. Commercial policy

Recommendation answers what is commercially interesting. Commercial
Policy answers what is currently allowed.

Policy covers credit restrictions, cash-only rules, promotion
eligibility, discount limits, approval requirements and authorized
overrides, with INFO/WARNING/HARD_BLOCK severity.

## 9. Targets

A high-level line/product target is currently broken down manually and
experientially to representative level. This workflow must be supported.

Target domain includes Definition, Hierarchy, Allocation, Allocation
History, Actual, Gap, Forecast, Feasibility, Allocation Suggestion and
Operational Focus.

Allocation methods: MANUAL, HISTORICAL, AI_SUGGESTED, HYBRID.

AI suggestions may consider return-adjusted history, customer potential,
whitespace, active customers, fit, territory potential, seasonality,
promotion, financial eligibility and inventory. Managers retain final
control.

## 10. Sales initiatives and missions

Sales Initiative defines organizational commercial direction: objective,
period, priority, product scope, audience, geography, sales line,
targets, offer, playbook and eligibility.

Sales Mission defines the primary purpose of a visit and may include
SELL, CROSS_SELL, NEW_PRODUCT_INTRODUCTION, TARGET_RECOVERY,
INITIATIVE_EXECUTION, REACTIVATE_CUSTOMER, PROTECT_RELATIONSHIP and
PRODUCT_EDUCATION.

## 11. Commercial lineage

Target lineage: Opportunity → Recommendation → Presentation → Basket
Item → Order Item → Invoice Item → Delivery Item → Return Item →
Payment/Settlement.

The platform does not replace ERP/Finance/WMS; it canonicalizes enough
information for execution and learning.

## 12. Canonical domains

1.  Organization & Field Sales
2.  Customer
3.  Product & Commercial
4.  Sales Intelligence
5.  Commercial Outcome
6.  Strategy & Execution

## 13. Application architecture

Preferred architecture: **Django Modular Monolith + API-first +
Event-ready**.

Candidate domain apps: identity, organization, customers, products,
knowledge, field_sales, commercial, orders, targets, initiatives,
opportunities, recommendations, intelligence, actions, ai, integrations,
experience.

Avoid uncontrolled cross-app ORM coupling; use explicit
services/contracts/context builders.

Core services: - Opportunity Engine - Recommendation Engine - Quantity
Engine - Customer Strategy Engine - Commercial Policy Engine

## 14. AI architecture

Preferred pattern: Business Data → Deterministic Engines → Structured
Context → LLM → Explanation/Conversation.

AI is used for understanding, synthesis, explanation and conversation,
not hidden business authority. Provider access should be abstracted and
local/on-premise-ready. Core sales flow must have deterministic fallback
when the LLM is unavailable.

## 15. Proposed technical baseline

Subject to audit of the existing implementation: - Backend: Django +
Django REST Framework - Frontend: Next.js + TypeScript - Database:
PostgreSQL - Cache/short-lived state: Redis - Async: queue-ready; Celery
is a candidate - App style: responsive PWA - Optional future geospatial:
PostGIS - Architecture: modular monolith, API-first, event-ready

## 16. Key screens

Sales Rep: Home/Daily Brief, Route, Customer 360, Pre-Visit, Visit,
Standard Sale, Guided Sale, Product 360, Product Advisor, Basket, Order
Review, Visit Summary, Action Center.

Supervisor: Team Today, Route Execution, Performance, Risks,
Approvals/Coaching.

Manager: Executive Overview, Sales Analytics, Targets, Target
Allocation, Initiatives, Initiative Analytics, Customer Intelligence, AI
Management Brief.

Admin: Product Knowledge, Configuration, Users/Roles.

## 17. Demo scope

### L1 --- Operational Demo

Authentication/role, Home, Daily Brief, Route, Customer 360, Pre-Visit,
Visit start/end, Standard Sale, Guided Smart Sale, Product 360, Product
Advisor, Opportunity/Recommendation, Suggested Quantity, Why This,
Basket/Order, Promotion/Inventory, Target/Gap, Basic Initiative, AI
Sales Copilot, Visit Summary.

### L2 --- Functional Product Shell

Manager/Supervisor dashboards, Target Allocation, Initiative
Builder/Analytics, Action Center, Customer Strategy, Commercial Health,
Returns, Complaints, Delivery/Payment summaries, Product Knowledge
Admin, AI Management Brief.

### L3 --- Roadmap

Full offline sync, advanced ML, automated target allocation, route
optimization, advanced promotion optimization, enterprise SSO, complex
approvals, full finance/WMS integration, large-scale external review
pipeline.

## 18. Demo story

Sales Rep Login → Daily AI Brief → Route → Pre-Visit → Customer 360 →
Guided Smart Sale → Why This → Product Presentation → Customer Question
→ Product Advisor → Basket → Order → Visit Summary → Target/Initiative
Progress.

Then switch to Manager → Sales Performance → Target Progress →
Initiative Funnel → AI Management Insight.

## 19. Canonical demo archetypes

The dataset deliberately includes: 1. Healthy Grade-A growth customer 2.
High-value Grade-A customer with recent financial risk 3. Promotion
overbuyer with significant returns 4. New-product-fit customer 5.
Customer with explicit need for Product Advisor 6. Dormant/reactivation
customer

All screens use one canonical dataset; credit, returns, targets,
recommendations and orders must remain internally consistent.

## 20. Screen Definition of Done

A hero screen is done only when business logic is connected, canonical
data is used, visual design is professional, responsive behavior is
complete, RTL is correct, loading/empty/error states exist, permissions
are enforced, Help/Info exists where appropriate, no obvious dead
actions remain and the demo scenario is tested.

## 21. Engineering entry rule

Do not rewrite the current Django application blindly.

First audit the existing project and classify every relevant component:
**KEEP / REFACTOR / REPLACE / ADD**.

Audit project structure, models/migrations, APIs, auth, recommendation
engine, domains, AI integration, frontend/static assets, tests,
dependencies, settings and demo/data-loading mechanisms.

## 22. Next step

Create and follow Implementation Master Plan v1.0, then audit the
existing Django project before freezing Technical Architecture v1.
