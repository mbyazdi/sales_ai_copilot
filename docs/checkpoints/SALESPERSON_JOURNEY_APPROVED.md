# Sales AI Copilot --- Salesperson Journey Checkpoint

**Status:** Approved for implementation planning\
**Date:** 2026-10-07\
**Scope:** Salesperson operational journey\
**Recommended repository path:**
`docs/checkpoints/SALESPERSON_JOURNEY_APPROVED.md`

## 1. Product Direction

Sales AI Copilot is an **operational sales assistant**, not merely a
recommendation dashboard.

The salesperson journey must help a field salesperson --- including a
relatively inexperienced user --- perform a customer visit with minimal
training and with clear guidance about what to do next.

Primary design principles:

-   Persian-only and RTL.
-   Mobile-first.
-   One obvious primary action at each stage.
-   AI complexity must remain behind the interface.
-   AI output must be translated into simple sales guidance.
-   Large touch targets and short texts.
-   Product images and important commercial numbers should be visually
    prominent.
-   Avoid unnecessary analytics during the salesperson's operational
    flow.

## 2. Approved End-to-End Journey

Canonical journey:

`Daily Visit Plan` → `Start Visit` → `Customer Operational View` →
`Guided Sale` → `Product Brief` when needed →
`Add products to Sales Request` → `Continue selling / recommendations` →
`Final Sales Request Review` → `Confirm & Submit Sales Request` →
`Sales Request Success` → `Prepared Customer Message` →
`Return to Daily Visit Plan`

The Copilot creates a **Sales Request / درخواست فروش**.

It must not represent this object as a finalized invoice or finalized
order.

In the production architecture, the Sales Request will eventually be
handed to the existing sales system through a Web Service/API. Approval,
warehouse, invoicing and downstream processes remain responsibilities of
the existing sales system.

## 3. Daily Visit Plan

The approved Daily Visit Plan is the salesperson's operational starting
point.

It should: - make today's visits immediately understandable; -
communicate visit status and priority; - expose the next action
clearly; - allow the salesperson to enter the selected customer's visit.

After completion of a customer visit, the salesperson returns to this
page and the corresponding visit status must reflect the completed
operation.

## 4. Customer Operational View

After `Start Visit`, the salesperson enters the approved operational
customer view.

The page should provide only the customer information needed to sell
effectively, while richer Customer360 information may remain available
as secondary information.

The primary selling action should be obvious.

## 5. Guided Sale --- Full Catalog + Smart Ranking

This is a major approved product decision.

Guided Sale must **not** be limited to three AI recommendations.

The full set of products that are eligible for sale to the current
customer remains accessible.

Products are ordered using intelligent and dynamic ranking.

**Guided Sale = Full eligible catalog + Smart Ranking**

High-priority products appear first.

Potential ranking inputs include: - customer purchase history; - likely
repurchase timing; - customer behavior; - customer segment/grade; -
inventory; - promotions; - salesperson/organizational targets; - company
priorities; - manager-defined sales priorities; - other recommendation
signals introduced later.

Company or manager priority is a ranking factor and must not blindly
override customer suitability.

Products without a special recommendation remain available after
prioritized products and may be labeled:

**بدون اولویت ویژه**

This label does not mean the product is unsuitable. It only means that
no current AI/business signal gives it special priority.

Only genuinely ineligible products should be excluded according to
sales/business rules.

## 6. Guided Sale Navigation

The salesperson must not be forced to manually analyze a very large
catalog.

The UI should provide: - intelligent ranking; - category filters; -
search; - easy access to all eligible products; - clear distinction
between prioritized and non-prioritized products.

The salesperson remains in control and can select any eligible product.

## 7. Prioritized Product Card

For prioritized/recommended products, the approved presentation should
expose: - product image; - product name/code; - priority indicator; -
simple explanation of why the product is recommended; - current
inventory when available; - base/current price; - customer discount; -
final customer price; - quantity; - add-to-sales-request action; -
product details when needed.

The explanation must be salesperson-friendly rather than model/algorithm
terminology.

## 8. Recommendation Feedback

Feedback applies **only to prioritized / intelligently recommended
products**.

Ordinary catalog products do not require this recommendation-feedback
interaction.

If a recommended product is purchased, adding it to the Sales Request
provides the positive commercial outcome.

If the recommendation is rejected, the salesperson must be able to
record a very quick reason.

Approved example rejection reasons: - مشتری علاقه‌مند نبود - قیمت مناسب
نبود - موجودی کافی نبود - فعلاً نیاز ندارد - قبلاً از برند/مدل دیگری
استفاده می‌کند - بعداً پیگیری شود - دلیل دیگر

An optional short note may be supported when appropriate.

The saved feedback should later support: - recommendation-quality
measurement; - AI/model improvement; - salesperson/manager analysis; -
promotion effectiveness; - target/policy effectiveness.

## 9. Recommendation Lineage

The system should retain enough lineage to determine why a product
appeared or was prioritized.

Where applicable, a resulting Sales Request line should eventually be
attributable to signals such as: - AI recommendation; - promotion; -
sales target; - company/manager priority; - normal salesperson
selection.

This is required for truthful future management analytics.

## 10. Pricing --- Demo/MVP Decision

Historical Sale/SaleItem prices must not be treated as authoritative
current prices.

The final architecture should eventually obtain current commercial
pricing from the appropriate pricing source/service.

For the current Demo/MVP, use the temporary simplified customer-grade
rule: - Grade A → 10% discount - Grade B → 5% discount - Other grades →
0%

The interface should distinguish: - base/current price; - customer
discount; - final customer price.

This temporary pricing rule must be replaceable by the future Pricing
Service/Web Service without requiring a redesign of the salesperson UX.

## 11. Sales Request Basket

Products accepted during the visit are added to the **Sales Request /
سبد درخواست فروش**.

The salesperson must be able to: - see selected products; - adjust
quantity; - remove products; - see final customer prices; - continue
adding products.

## 12. Final Sales Request Review

Before submission, show a compact final review containing: - selected
products; - editable quantities; - remove action; - final item prices; -
discounts where relevant; - grand total.

Primary action:

**تأیید و ثبت درخواست فروش**

This page should remain operational and compact, without distracting
analytics.

## 13. Sales Request Submission

After confirmation, the Demo records the Sales Request.

The success page should clearly show: - successful registration; - Sales
Request number; - item count; - final amount; - registration information
when appropriate.

## 14. Customer Message

After successful Sales Request registration, prepare a customer-facing
confirmation message containing, where applicable: - customer/store
name; - Sales Request number; - total amount; - short
confirmation/thank-you message.

For the Demo:

**No SMS, WhatsApp, Telegram or other messaging integration is
required.**

The interface must explicitly communicate:

**در نسخه فعلی این پیام ارسال نمی‌شود و فقط نمایش داده می‌شود.**

Future production implementation may connect the prepared message to an
approved messaging channel.

## 15. Visit Completion

After successful Sales Request handling and final acknowledgement, the
salesperson returns to:

**Daily Visit Plan**

The relevant visit status must be updated appropriately.

## 16. Manager Experience --- Next Major Design Stage

Manager functionality remains in scope.

The target manager product is a **Sales Command Center**, not merely a
reporting dashboard.

It should eventually support: - salesperson performance monitoring; - AI
recommendation performance; - AI impact on sales; - targets and target
achievement; - promotions and promotion impact; - company sales
priorities; - manager-defined priorities; - stock-focused campaigns; -
recommendation acceptance/rejection analysis; - policy impact analysis.

Desired closed loop:

`Manager Policy / Target / Promotion` → `Recommendation Ranking` →
`Salesperson Guided Sale` → `Sale / Rejection / Feedback` →
`Measurement` → `Manager Adjustment`

## 17. Approved Visual Direction

-   Persian RTL
-   mobile-first
-   professional but simple
-   visually close to final application
-   navy/teal existing design foundations
-   restrained cards and shadows
-   prominent product imagery
-   simple actionable language
-   minimal forms
-   one dominant action per operational state

Reuse the existing design system rather than introducing a new UI
framework.

## 18. Approved Screens

The following stages have been visually reviewed and approved: 1. Daily
Visit Plan 2. Customer Operational View after Start Visit 3. Guided Sale
--- Full Catalog + Smart Ranking 4. Guided Sale recommendation feedback
interaction 5. Sales Request / Final Review 6. Successful Sales Request
registration 7. Prepared Customer Message / Demo non-send state 8.
Return path to Daily Visit Plan

## 19. Deferred Items

Do not expand the current implementation scope unnecessarily.

Deferred: - full enterprise pricing engine; - real messaging
integration; - production sales-system Web Service integration; -
advanced ML ranking; - advanced manager command center; - full promotion
engine; - advanced target optimization; - sophisticated policy
optimization.

Interfaces should allow these capabilities to replace Demo
implementations later without redesigning the complete journey.

## 20. Implementation Guardrails

Implementation must preserve existing working business behavior unless a
separately approved product change requires modification.

Preserve: - existing lifecycle safeguards; - CSRF and POST
protections; - pending/recovery states; - customer/visit/recommendation
context; - manager surfaces not included in the current implementation
scope.

Validate responsive behavior at: - 390px - 768px - 1024px - 1440px

## 21. Acceptance Principle

> An inexperienced salesperson should understand within a few seconds
> where they are, what matters for this customer, and what they should
> do next --- without needing special training.

At the same time, the system must collect enough structured sales and
recommendation feedback to support future AI improvement and the Manager
Sales Command Center.

------------------------------------------------------------------------

## Checkpoint Decision

The salesperson product journey described above is **approved as the
canonical basis for the next implementation stage**.

The next step is to convert this checkpoint into a staged Codex
implementation plan and execute it without reopening already-approved
product decisions unless implementation reveals a genuine conflict.
