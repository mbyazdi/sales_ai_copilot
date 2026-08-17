# Sales AI Copilot — Project Checkpoint

**Checkpoint Version:** v1.0  
**Date:** 2026-08-15  
**Project:** Sales AI Copilot – Django Demo  
**Status:** Active / Demo Development

---

## 1. Purpose of this checkpoint

This file is the recovery point for the Sales AI Copilot project.

If a future conversation loses context, resend this file so the project can continue from the agreed path without redesigning or mixing this project with unrelated work.

**Important rule:** Preserve the agreed project direction and order. Do not restart the architecture or introduce unrelated redesigns unless explicitly requested.

---

## 2. Project scope

The project is a **Django demo of an AI Sales Copilot** for a salesperson/marketer who visits customers in person.

The assistant should help the salesperson answer:

1. Who is this customer?
2. What has the customer bought?
3. What is the customer's commercial value and behavior?
4. What should I recommend now?
5. Why is this product recommended?
6. What should I say/do during the sales conversation?
7. What happened after the recommendation?
8. What follow-up should happen next?
9. Eventually: how can AI learn from these outcomes?

The demo is intentionally focused on **electrical appliances**.

The demo is not intended to reproduce the full production-scale enterprise architecture.

---

## 3. Technology stack

- Python 3.13.14
- Django 6.1
- Django REST Framework
- SQLite for demo
- Ollama
- HTML / CSS / JavaScript
- Bootstrap
- jQuery

Project path:

`D:\py project\sales_ai_copilot`

Main Django apps:

- `ai`
- `core`
- `customers`
- `inventory`
- `products`
- `promotions`
- `recommendations`
- `sales`
- `visits`

---

## 4. Business/demo scope

Current demo direction:

- Electrical-appliance business
- Customer subset for demo
- Product subset for demo
- Customer 360
- Product recommendations
- Salesperson/customer assignment
- Customer visits
- Sales outcomes
- Sales-session context
- Future AI assistant

The frontend should be **attractive and product-presentable**, with a modern SaaS / AI-first feeling.

However, UI work should not block the business/backend progression. The current UI has been intentionally left for later refinement.

---

## 5. Current Customer domain

### CustomerGrade

Commercial customer grade:

- `A` = Strategic
- `B` = High Value
- `C` = Medium Value
- `D` = Low Value

Important fields:

- code
- name
- description
- priority
- is_active
- created_at
- updated_at

---

### Customer

Master customer entity.

Customer types currently include:

- STORE
- DISTRIBUTOR
- WHOLESALER
- ELECTRICAL_STORE
- HOME_APPLIANCE_STORE
- OTHER

Important fields:

- customer_code
- name
- customer_type
- grade
- city
- address
- phone
- is_active
- created_at
- updated_at

---

## 6. Customer 360

`Customer360` is a **pre-calculated snapshot** used by the recommendation engine.

It contains:

### Purchase summary

- total_orders
- total_items
- total_sales_amount
- average_order_value

### Recency / Frequency

- last_purchase_date
- first_purchase_date
- purchase_frequency
- days_since_last_purchase

### RFM

- recency_score
- frequency_score
- monetary_score
- rfm_score

### Segmentation

- HIGH_VALUE
- GROWTH
- STABLE
- AT_RISK
- INACTIVE
- NEW

### Buying behavior

- top_category
- top_product_code

### Trends

- sales_30d
- sales_90d
- sales_30d_change_percent
- sales_90d_change_percent

### Snapshot metadata

- calculated_at

---

## 7. Current Customer 360 web page

The main customer page is:

`core/customer_360.html`

Current page includes:

- Customer search
- Customer 360 header
- Customer grade
- Customer type
- City
- Days since last purchase
- AI Sales Copilot section
- Primary recommendation
- Alternative recommendations
- AI score
- Reason for recommendation
- Sales-session interaction buttons

The UI was substantially rebuilt and is now visually much better.

There are still some visual imperfections in recommendation cards (#2/#3 and the primary recommendation badge/score areas), but the explicit decision was:

**Do not spend more time on these UI issues now. Move to the next project stage and return later if needed.**

---

## 8. Recommendation Engine status

Recommendation Engine/API is already implemented and tested.

Previously verified:

- Recommendation query optimization
- Recommendation API
- `Customer360` snapshot/API
- API returned HTTP 200 for customer `C0003`

Current recommendation model is represented by:

`CustomerRecommendation`

Recommendations are ordered by `rank`.

Each recommendation provides:

- rank
- product
- category
- score
- recommendation_type
- reason

Recommendation types currently used include:

- `REPEAT_PURCHASE`
- `CROSS_SELL`
- `CATEGORY`
- `SIMILAR_PRODUCT`

The UI currently displays the primary recommendation and alternatives.

---

## 9. Current Customer views.py

`apps/customers/views.py` currently contains two main flows:

### A. customer_search()

The web page flow:

1. Reads `customer_code`
2. Calls `get_customer_360(customer_code)`
3. Loads customer and Customer360
4. Loads active recommendations
5. Determines primary recommendation
6. Builds customer status
7. Builds sales opportunity
8. Builds primary product information
9. Builds salesperson talking point
10. Sends the result to `core/customer_360.html`

### B. Customer360APIView

REST endpoint that returns:

- customer
- customer_360
- sales_context
- recommendations
- recommendation_count

---

## 10. Current Customer 360 API

URL pattern:

`v1/customer-360/<str:customer_code>/`

Because the customers app is mounted under `/customers/`, the expected demo URL is:

`/customers/v1/customer-360/C0003/`

The API currently returns:

### customer

- code
- name
- type
- city
- address
- phone
- grade

### customer_360

- total_orders
- total_items
- total_sales_amount
- average_order_value
- first_purchase_date
- last_purchase_date
- days_since_last_purchase
- recency_score
- frequency_score
- monetary_score
- rfm_score
- segment
- top_category
- top_product_code
- purchase_frequency
- sales_30d
- sales_90d
- sales_30d_change_percent
- sales_90d_change_percent
- calculated_at

### sales_context

- salesperson
- assignment
- latest_visit
- sales_outcomes
- sales_outcome_count

### recommendations

- rank
- product_code
- product_name
- category
- score
- recommendation_type
- reason

---

## 11. Existing sales context

The project already has these entities:

`CustomerAssignment`
`Visit`
`SalesOutcome`

Current API joins them into the Customer 360 response.

### CustomerAssignment

Connects a customer to a salesperson.

### Visit

Represents a salesperson's visit to a customer.

Latest visit currently provides:

- id
- date
- status
- customer_request
- customer_feedback
- competitor_information
- notes
- order_created
- order_amount
- follow_up_required
- follow_up_date

### SalesOutcome

Captures the outcome associated with recommendations/products.

Current response includes:

- id
- outcome
- quantity
- sales_amount
- notes
- product_code
- product_name
- recommendation_type
- created_at

---

## 12. Important architectural decision

Do **not** immediately create a completely separate Sales Session model just because the phrase "Sales Session" was proposed.

The current project already has:

- Visit
- SalesOutcome
- Recommendation
- CustomerAssignment

The next step should first determine whether the existing entities can represent the desired sales-session workflow cleanly.

Avoid unnecessary model duplication.

---

## 13. Agreed next project stage

The project is now moving from:

**Customer 360 + Recommendation**

toward:

# Sales Intelligence / Sales Session workflow

The intended business flow is:

`Customer 360`
→ `Customer Behavior`
→ `Recommendation`
→ `Sales Opportunity`
→ `Talking Point`
→ `Sales Action`
→ `Outcome`
→ `Feedback`
→ `Next Recommendation`

The purpose is to make the product a real **AI Sales Copilot**, rather than only a Customer 360 dashboard.

---

## 14. Proposed next workflow

For a salesperson visiting customer `C0003`, the system should eventually support:

### Before the visit

Show:

- Customer profile
- Customer value/grade
- Purchase behavior
- Recent purchase
- Main opportunity
- Primary recommendation
- Alternative recommendations
- AI score
- Reason
- Suggested talking point

### During the visit

Salesperson can record:

- Customer response
- Interest
- Rejection
- Purchase
- Need for follow-up
- Notes

### After the visit

System records:

- outcome
- quantity
- sales amount
- follow-up date
- salesperson notes

### Later

The outcome becomes feedback for improving recommendations and AI behavior.

---

## 15. Current implementation priority

The recommended order is:

1. Verify/lock the Customer 360 API contract
2. Review the existing Visit + SalesOutcome model against the desired Sales Session workflow
3. Implement the Sales Intelligence workflow
4. Improve outcome/follow-up handling
5. Connect the workflow to the AI assistant
6. Add salesperson conversational interaction
7. Analyze recommendation outcomes
8. Introduce more advanced ML only when enough outcome data exists

---

## 16. Things explicitly deferred

### UI polishing

The current recommendation cards have some styling issues.

These are intentionally deferred.

Do not spend significant time redesigning the UI before the next backend/business milestone unless explicitly requested.

### Large-scale performance/load testing

This is a demo.

Do not prioritize enterprise-scale concurrency/load testing unless explicitly requested.

### Production architecture

Do not prematurely introduce:

- distributed architecture
- complex infrastructure
- unnecessary microservices
- enterprise-scale data platforms

The current objective is a convincing working demo.

---

## 17. Critical project constraints

1. Keep the project focused on **Sales AI Copilot**.
2. Do not mix this project with the separate Sales AI Copilot architecture/discussions from unrelated contexts unless explicitly requested.
3. Preserve the agreed implementation order.
4. Prefer incremental changes over unnecessary rewrites.
5. Do not redesign working models without a business/technical reason.
6. UI can be refined later.
7. Business workflow is now more important than pixel-level UI.
8. The demo is focused on electrical appliances.
9. SQLite is acceptable for the current demo.
10. Ollama is part of the planned AI layer.

---

## 18. Current checkpoint / resume point

### Completed

- Django project foundation
- Core apps
- Customer model
- CustomerGrade
- Customer360
- Product domain
- Recommendation domain
- Recommendation Engine
- Recommendation API
- Customer 360 API
- Customer search page
- Customer 360 frontend
- Salesperson/customer assignment integration
- Visit integration
- SalesOutcome integration
- Primary + alternative recommendation display
- Basic sales-session context generation

### Current position

**Customer 360 + Recommendation + basic sales context are working.**

### Immediate next task

**Review and implement the Sales Intelligence / Sales Session workflow using the existing Visit and SalesOutcome structures where possible.**

---

## 19. Recovery instruction

When this checkpoint is re-sent in a future conversation:

1. Read the entire checkpoint.
2. Treat the current position as the starting point.
3. Do not restart the project.
4. Do not redesign previously completed modules without reason.
5. Continue from the "Immediate next task".
6. Ask for the relevant current code only when necessary to implement the next step.
7. If a new major architectural/business decision is made, create a new checkpoint version.

---

## 20. Version history

### v1.0 — 2026-08-15

Initial recovery checkpoint created after Customer 360, Recommendation Engine/API, sales context, and frontend work.

**Resume point:** Sales Intelligence / Sales Session workflow.
