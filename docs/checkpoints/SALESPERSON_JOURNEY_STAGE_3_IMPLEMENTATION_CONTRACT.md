# Salesperson Journey — Stage 3 Implementation Contract

Date: 2026-10-08. Status: Stage 3A1 contract freeze; owner decisions approved.
This checkpoint implements documentation only. Later tasks require separate
authorization; no Stage 3 model, migration, service, API or UI exists from 3A1.

## 1. Authority and baseline

- Product behavior: [approved journey](SALESPERSON_JOURNEY_APPROVED.md) and
  [Stage 0 contract](SALESPERSON_JOURNEY_IMPLEMENTATION_CONTRACT.md).
- Reusable persistence: [Stage 1](SALESPERSON_JOURNEY_STAGE_1_PERSISTENCE_FOUNDATIONS.md).
- Approved catalog and presentation: [Stage 2A](SALESPERSON_JOURNEY_STAGE_2A_CATALOG_BACKEND.md)
  and [Stage 2B](SALESPERSON_JOURNEY_STAGE_2B_GUIDED_SALE_UI.md).
- This checkpoint records the owner's subsequent Stage 3 decisions and closes
  the Stage 0 rounding question. Basket/pricing now belong to 3B/3C; older stage
  numbering does not override this scope. Other approved business rules remain.
- Visual target: `D:\UI References\salesperson-journey`; mobile is authoritative.
  Markdown governs behavior and truthful data when references conflict.
- Baseline: `fast-track`, HEAD `8fceda04dbafba6cb4cfb66a88653169a2a4dd98`.
  Initial working tree: only intentionally modified, unstaged `db.sqlite3`.
- Accepted local DB SHA256:
  `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
  Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
  Neither may be altered by this documentation task.

## 2. Scope and domain boundaries

Stage 3 makes Guided Sale operational through recommendation feedback, DRAFT
basket mutations and current pricing. Terminology remains **Sales Request /
درخواست فروش**, never finalized invoice/order.

| Domain | Responsibility |
| --- | --- |
| products | Catalog/eligibility, canonical inventory-facing facts, ProductDemoPrice and a replaceable pricing provider. |
| recommendations | Saved priority/evidence, legitimate recommendation context, append-only feedback and acceptance lineage. |
| sales_requests | Draft header/lines, basket coordination, revisions, totals and durable command receipts. |
| visits | Existing ownership and lifecycle safeguards. |
| historical sales | Existing Sale/SaleItem and realized revenue; unchanged. |

Reuse existing SalesRequest, SalesRequestLine, ProductDemoPrice and
RecommendationFeedbackEvent fields and protections. SalesRequestAcknowledgement
remains unchanged and unused in Stage 3. No new request states or redundant
customer/owner foreign keys are required. Only the later minimal receipt
foundation requires an additive schema change; it is not created in 3A1.

## 3. Draft and inventory invariants

- One SalesRequest lifecycle per Visit, enforced by the existing unique Visit
  relationship. Stage 3 creates/updates DRAFT only, for an authorized IN_PROGRESS
  Visit. The first successful explicit Add may create it; reads never do.
- Add/set quantity uses an absolute desired positive integer, never implicit
  increment. Reject booleans, fractions and inferred pack/unit conversions.
- One selected line per product; remove retains the line with selection/removal
  metadata. Re-add creates a fresh line, preserving previous history.
- Basket item count is selected product lines; total units is a separate value.
- Sellable stock is `max(available_quantity - reserved_quantity, 0)`. Known
  positive stock is potentially addable; zero/unknown stock remains visible but
  cannot be added. Revalidate current stock at Add and quantity changes.
- Requested aggregate product quantity must not exceed observed sellable stock.
  Reject conflicts; never silently cap quantity, remove lines or generate feedback.
- Removal remains possible when stock or price becomes unavailable. Surface
  invalid remaining lines/totals truthfully; never substitute zero prices.
- No stock deduction/reservation or allocation guarantee is introduced.
- A retained draft never automatically submits/completes a Visit and must not
  block supported no-sale completion. Closed-visit drafts are read-only.

## 4. Recommendation event contract

Recommendation acceptance, request submission and realized sale are distinct.
`ADDED_TO_REQUEST != PURCHASED`; no legacy outcome, purchase flag or revenue
semantics change.

| Successful explicit action | Persistence effect |
| --- | --- |
| Add a legitimately prioritized product | Fresh selected recommended line plus ADDED_TO_REQUEST, atomically. |
| Change selected quantity | Quantity/quote update; no additional acceptance event. |
| Remove a recommended line | Retain line as unselected; append REMOVED_FROM_REQUEST. |
| Re-add after removal | Fresh selected line and fresh ADDED_TO_REQUEST; old lines/events remain. |
| Add/change/remove ordinary product | Basket effect only; no recommendation feedback. |
| Explicit rejection | Append REJECTED with approved reason and optional short note. |
| Failed command or successful replay | No additional domain effect/event. |

Reject explicit rejection whenever that product is currently selected, including
an ordinary-source selected line: return `PRODUCT_ALREADY_SELECTED`. The user
must remove explicitly first. Removal itself is never rejection. Later Add is
allowed and retains any earlier rejection history.

Approved codes: `NOT_INTERESTED`, `PRICE`, `STOCK`, `NO_CURRENT_NEED`,
`OTHER_BRAND`, `LATER`, `OTHER`, with existing Persian labels. FOLLOW_UP_LATER
is REJECTED with reason LATER; it creates no FollowUpTask, scheduled contact or
Visit completion. Existing dated legacy follow-up behavior remains separate.

Validate new selection/rejection against the saved signed context, not a client
priority flag or a newly generated recommendation. Preserve recommendation ID,
rank/type, saved reason/evidence and context fingerprint with identity lineage.
Existing line identity/lineage is not rewritten on quantity change. Existing-line
edit/removal uses captured lineage and must not be stranded by token expiry or
recommendation deactivation. Product Detail operational controls use the carried
selling context rather than assuming its live recommendation lookup is canonical.

Current acceptance is scoped to selected recommended lines. Fold add/remove
history per exact line identity and cross-check selected membership. Historical
add counts are not current acceptance; rejection is a separate explicit fact.
GET must not repair any mismatch or rewrite history.

## 5. Pricing and rounding — approved

Current base prices come only from controlled ProductDemoPrice data. No historic
SaleItem, screenshot, AI or promotion-derived price fallback. Missing price is
unavailable, never zero; an explicitly configured zero remains distinct.
Fractional demo base prices are configuration errors, not silently rounded data.

Use Decimal end-to-end, TOMAN currency and whole displayed monetary amounts.
Grade code A gives 10%, B gives 5%, other/missing gives 0%. Tax contributes zero
in this MVP; promotions are contextual only and never stacked.

```text
base_unit = explicit whole-TOMAN demo base price
final_unit = (base_unit * (1 - discount_percentage / 100))
             .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
unit_discount = base_unit - final_unit
line_base = base_unit * quantity
line_discount = unit_discount * quantity
line_total = final_unit * quantity
request_base / discount / total = sums of the corresponding selected line amounts
```

For base 105, grade A, quantity 3: final unit 95, unit discount 10, line base 315,
discount 30, total 285. Do not independently round/reapply discounts at request
level or subtract discounts again from already-discounted totals.

The replaceable provider belongs in products. It accepts validated customer,
product, quantity/as-of context and returns base unit price, discount percentage,
unit discount, final unit price, line total, currency, source/version and a
versioned calculation/rounding policy. Wire amounts are decimal strings; the
server owns arithmetic. A future Pricing Service/API can replace the demo adapter.

Quote fingerprints bind relevant customer grade, products/quantities, price
source/version and policy/results. Priced mutations require an accepted quote
fingerprint and revalidate the resulting basket; changed quotes conflict rather
than silently changing accepted prices. Removal is not blocked by an unavailable
quote. Reads may expose current validity alongside saved draft quotes, without
persisting repricing. Submitted snapshot protections remain untouched.

## 6. Concurrency and successful-command replay

Durable append-only mutation receipts are approved. The later minimal foundation
belongs in sales_requests and records protected Visit/actor, stable client UUID,
operation, canonical intent fingerprint, optional request, applied revision,
canonical successful result and timestamp. Enforce uniqueness on Visit plus
command UUID; validate actor on replay. Do not reuse submission_key or hide a
command journal in pricing/lineage snapshots. Feedback may succeed before a Draft
exists, so receipt request linkage is optional.

- Commands carry stable UUID, expected request revision (or explicit no-request
  expectation for first Add), absolute quantity where relevant, validated context
  for new selection/rejection, and accepted quote fingerprint for priced mutations.
- Canonical intent includes operation, targets and relevant command inputs; it
  excludes transport noise. Replays resend the original command unchanged.
- A recorded successful UUID with identical intent replays its exact prior
  canonical result without new writes/repricing. Different intent conflicts.
  A newer basket may exist: return the original applied revision and fetch current
  state separately; never present an old replay as the latest basket.
- Authorization is rechecked before replay/status disclosure. Replay is retrieval
  of prior success, not permission to mutate a closed/submitted request.
- Commit effects, revision, events, totals and successful receipt in the same
  atomic transaction. Failed commands leave no successful receipt or partial effects.
- Acquire the expected DRAFT revision with a conditional update before line/event
  changes; require IN_PROGRESS in mutation guards. Zero matched rows conflicts.
  Preserve the acquired revision when saving totals from model instances.
- First-Draft races respect Visit uniqueness. SQLite correctness uses transactions,
  uniqueness and conditional guards, not assumed select_for_update row locks.
- Database-busy/ambiguous network failures are recovery states. Do not automatically
  retry mutation POSTs, infer success or append another event. Use authorized
  command-status/current-state reads. Later tests use isolated file-backed SQLite.

## 7. API/service direction

Thin versioned APIs delegate to domain services; no business arithmetic or
recommendation eligibility logic is duplicated in JavaScript.

| Boundary | Responsibility |
| --- | --- |
| GET/POST `/api/recommendations/v1/visits/<visit_id>/feedback/` | Feedback projection / explicit rejection. |
| GET `/api/sales-requests/v1/visits/<visit_id>/basket/` | Existing/empty basket, revision, selected lines, counts and quote validity. |
| POST `/api/sales-requests/v1/visits/<visit_id>/lines/` | Absolute-quantity Add and transactional first Draft. |
| PATCH/DELETE `/api/sales-requests/v1/requests/<request_id>/lines/<line_id>/` | Absolute quantity / retained semantic removal. |
| GET `/api/sales-requests/v1/visits/<visit_id>/quote/` | Read-only current/candidate basket quote and fingerprint. |
| Authorized command-status GET | Prior successful-command lookup; exact path/schema frozen with receipt API task. |

Catalog pricing additions must be additive and batched, preserving Stage 2 ranking,
search, filters, pagination and signed return context. Responses return canonical
state/revision/amounts, not client-inferred success. Stable errors include
PRODUCT_ALREADY_SELECTED, REVISION_CONFLICT, PRICE_CHANGED, INSUFFICIENT_STOCK,
CATALOG_CONTEXT_UNAVAILABLE and truthful unavailable-price/configuration states.
User-facing labels/errors remain Persian. Endpoint serializers and exact result
schemas must be frozen/tested before their dependent UI task.

Every mutation enforces current role/profile, assignment, matching customer/Visit,
owned request/line and CSRF/HTTP protections. Saved tokens never grant access.
Operational GET/HEAD creates no Draft, line, receipt, feedback, recommendation,
price, acknowledgement or Visit changes.

## 8. Small-task implementation order

Each later task is separately reviewable with focused tests. Backend, API and full
UI are not one combined task. No later task is authorized by completing 3A1.

| Order | Task | Boundary / validation |
| --- | --- | --- |
| 1 | 3A1 contract freeze | This document only; diff whitespace and safety verification. |
| 2 | 3B1 mutation receipt foundation | Minimal additive model/admin/migration; constraints, append-only and isolated migration tests. |
| 3 | 3C1 pricing core | Demo adapter/pure calculations; grade, ties, missing/fractional data and reconciliation tests. |
| 4 | 3C2 quote reads | Read-only quote/canonical pricing binding; authorization, fingerprints, zero writes and bounded queries. |
| 5 | 3A2 feedback service | Saved-context validation/event projection; seven reasons, selected-product conflict and history tests. |
| 6 | 3A3 feedback API | Thin protected API; CSRF, replay/conflicts, access and stale-context tests. |
| 7 | 3A4 feedback presentation | Prioritized-only Guided/Detail controls; focused JS/presentation tests, preserved anatomy. |
| 8 | 3B2 basket reads | Empty/existing/read-only projections; counts, lineage, authorization and zero-write tests. |
| 9 | 3B3 basket mutation service | Pricing/event dependencies; atomic add/edit/remove/re-add, revisions, rollback and SQLite race tests. |
| 10 | 3B4 basket APIs/recovery | Thin endpoints and successful-command lookup; CSRF, cross-context and ambiguous-response tests. |
| 11 | 3C3 price presentation | Existing price slots; truthful server amounts, unavailable states and focused rendering tests. |
| 12 | 3B5 operational controls | Activate reserved quantity/Add plus basket summary/removal; shared Guided/Detail behavior and JS tests. |
| 13 | 3X checkpoint/approval | Integrated invariants and owner inspection at 390/768/1024/1440; no automatic visual approval. |

## 9. Deferred scope and regression protections

No submission/review/success workflow, request numbering, acknowledgement,
prepared-message generation, actual outbound messaging, realized Sale/SaleItem,
Visit completion change, stock reservation, automatic follow-up, promotion engine,
advanced ranking or manager redesign is part of Stage 3.

Activate the approved quantity | price | Add regions without redesigning card
anatomy. Detail stays secondary navigation; inventory stays a truthful secondary
commercial status. Preserve Persian RTL, >=44px operational targets, mobile-first
composition and bounded maximum-two-column desktop adaptation. No fabricated
images/prices or fake enabled controls. Product Detail retains its approved
direction, validated return URLs and legacy compatibility.

Preserve Recommendation Engine v1, recommendation-first full catalog, ordinary
products, saved ordering, permissions, CSRF, existing outcomes, follow-up semantics,
Visit snapshots, no-sale completion and submitted/append-only protections. Never
silently rerank, regenerate, repair history or mutate on read. Existing models
are changed only for a demonstrated blocker reviewed before implementation.

The developer database and original stash remain local/untouched; validation for
future tasks uses isolated databases. Controlled pricing data and runtime migration
need their own authorization, never implicit population from a GET or preview.
