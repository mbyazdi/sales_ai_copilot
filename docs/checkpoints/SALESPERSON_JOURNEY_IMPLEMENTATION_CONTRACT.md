# Salesperson Journey — Stage 0 Implementation Contract

Date: 2026-10-07. Stage: baseline verification and contract documentation only.
Status: Stage 0 prepared for approval; Stage 1 has not started.

This document records approved product decisions and proposes the bounded data,
API and implementation contracts for later stages. It does not implement any
model, migration, application, endpoint, workflow or demo dataset.

## 1. Authoritative sources and precedence

1. `docs/checkpoints/SALESPERSON_JOURNEY_APPROVED.md` governs product behavior,
   workflow, business rules, terminology and MVP scope. It is unchanged.
2. The product owner's approved Stage 0 decisions clarify that specification:
   TOMAN pricing, inventory behavior, separate acceptance events, removal,
   explicit completion, retained drafts, request cardinality and stable priority.
3. All six PNGs in `D:\UI References\salesperson-journey` govern visual direction,
   information hierarchy and interaction presentation. Markdown and approved
   product decisions win over conflicting illustrated values or behaviors.
4. Older checkpoints describe earlier implementation slices. Their former
   exclusions of pricing, full catalog and basket do not override the new journey.
5. AGENTS.md engineering protections continue to apply: evolve incrementally,
   deterministic commercial logic, server authorization, immutable history and
   scoped demo reset. No unrelated manager redesign is authorized.

Authoritative Markdown SHA256:
`44BD3646B20C4169C58C8B2F9A98C647C7CF606A494F86812F277E13F3231E68`.

The visual files were all inspected in the preceding planning task; Stage 0
verified their identities/hashes again. They remain outside Git. The earlier
hyphenated directory and the supplied `salesperson-joutney` spelling were resolved
to the actual directory above; neither alternate path is authoritative.

## 2. Current repository baseline

- Repository: `D:\py project\sales_ai_copilot`.
- Branch: `fast-track`.
- HEAD: `769931e292e40dcb423f146577e343f4ea745d43`.
- `origin/fast-track`: same commit, verified after a successful fresh fetch.
- Accepted baseline: the existing working tree, including uncommitted 002-P
  work and the untracked approved specification, not just the HEAD commit.
- Index: no staged changes.
- Database: pre-existing tracked modification; never restored, reset or edited.
- Database SHA256 before Stage 0:
  `E49950656E5AD8EFF594AD62758BDE3CBE2FFE22AA8768EDE205C1D1265D0517`.
- Stash: exactly one entry,
  `stash@{0}: On fast-track: home-local-files-before-fast-track-work-2026-10-05`;
  object `2dac7bdc26f07f611f471564476ceaa52ec367cc`.

Initial `git status --short --untracked-files=all`:

```text
 M apps/customers/tests_productization.py
 M apps/visits/tests_workspace.py
 M db.sqlite3
 M static/core/css/customer_workspace.css
 M static/core/css/recommendation_outcome.css
 M static/visits/css/daily_workspace.css
 M templates/base.html
 M templates/core/customer_360.html
 M templates/core/customer_360/_ai_command_center.html
 M templates/core/customer_360/_ai_recommendations.html
 M templates/core/customer_360/_customer_hero.html
 M templates/core/customer_360/_outcome_modal.html
 M templates/core/customer_360/_sales_context.htm
 M templates/core/customer_360/_search.html
 M templates/core/product_detail.html
 M templates/customers/recommendation_presentation.html
 M templates/visits/_visit_card.html
 M templates/visits/completion_review.html
 M templates/visits/dashboard.html
?? apps/customers/tests_salesperson_journey.py
?? docs/checkpoints/SALESPERSON_JOURNEY_APPROVED.md
?? docs/checkpoints/SALES_AI_PLATFORM_TASK_002_P_SALESPERSON_JOURNEY_COHESION.md
?? static/css/salesperson_journey.css
?? templates/components/salesperson_context.html
?? templates/core/customer_360/_guided_entry.html
?? templates/visits/_daily_priorities.html
?? templates/visits/_visit_actions.html
```

Before creating this document, 293 tracked/non-ignored existing files were
recorded in a SHA256 manifest outside the repository at
`%TEMP%/salesperson-journey-stage0/before-files.json`. Status, migration inventory,
stash listing and database hash were also captured there. These temporary audit
artifacts are not product assets or new repository content.

Fresh automated baseline, executed before document creation:

| Command/check | Exact result |
| --- | --- |
| `venv\Scripts\python.exe -B manage.py check` | No issues; 0 silenced. |
| `venv\Scripts\python.exe -B manage.py test apps.customers.tests_salesperson_journey apps.customers.tests_productization apps.customers.tests_recommendation_presentation apps.visits apps.products.tests_commercial_brief --noinput` | 174 tests passed. |
| `venv\Scripts\python.exe -B manage.py test --noinput` | 218 tests passed. |
| `node --test apps/customers/js_tests/recommendation_presentation.test.cjs apps/visits/js_tests/recommendation_outcome.test.cjs apps/visits/js_tests/completion_review.test.cjs` | 3 test files passed; 20 explicit scenarios passed: 4 Guided, 7 outcome, 9 completion. |
| `node --check` for every existing `.js`/`.cjs` under static/apps | 13 files checked; 0 syntax failures. |
| `git diff --check` | Passed. |

Node version: `v24.19.0`. Python `-B` disabled bytecode generation. Django used
its isolated test database; no migration/seed was applied to `db.sqlite3`.
No baseline test failed, so no unrelated failure was repaired. These results
validate existing behavior, not the proposed functionality in later sections.
No new browser validation or Stage 1 test execution is claimed for Stage 0.

## 3. Existing reusable components

Reuse Customer/Customer360, Product/Brand/Category, Inventory, Promotions,
Salesperson/CustomerAssignment and the existing Visit records.

- `apps/customers/access.py`: current customer assignment boundary and staff
  inspection behavior; new operational services additionally deny staff roles.
- `apps/recommendations/engine.py` and models: existing deterministic v1 scoring,
  saved rank, explanations, score breakdowns and evidence. Regeneration currently
  deactivates old recommendations and creates new rows; historical identity matters.
- `apps/core/commercial_context.py`: batched current stock and promotion facts.
- `apps/visits/views.py`: canonical start/complete guards and existing APIs.
- `apps/visits/services.py`: snapshot capture, canonical legacy outcome resolution,
  follow-up synchronization, Daily context and management calculations.
- Existing Daily, Customer360, Product Brief, Guided and Review templates,
  shared presentation components, design-system tokens and focused JS patterns.
- Existing authorization, continuity, outcome, review, product and manager tests.

Current gaps are real functionality: Guided reads only active recommendations;
there is no Sales Request domain, current price source or canonical product media.
The present Product Brief Guided return also depends on an active recommendation.
None of these components is replaced in Stage 0.

## 4. Approved product decisions

| Decision | Binding MVP behavior |
| --- | --- |
| Money | TOMAN; controlled current demo prices; Decimal; no fractional displayed toman; tax 0/outside scope. |
| Grade discount | A 10%; B 5%; others or missing grade 0%. No automatic promotion stacking. |
| Stock | Positive sellable stock can permit add; zero/unknown may be visible but cannot be added; requested quantity cannot exceed current sellable stock. |
| Acceptance | Separate `ADDED_TO_REQUEST` concept; never legacy `PURCHASED` or realized sale. |
| Removal | Preserve earlier add history; removed line no longer represents current acceptance; no automatic rejection. |
| Completion | Explicit protected user mutation after success/message; submission and GET do not complete visits. |
| No-sale/drafts | No-sale completion remains supported; do not submit or block completion merely because a draft exists. |
| Cardinality | One submitted request and at most one active draft per visit; no multi-request-per-visit feature. |
| Priority | Saved recommendation context stays stable during the selling session; mutable commercial/security facts are revalidated. |
| Promotions | Truthful contextual display only; no inferred price rules. |
| Demo assets | Controlled price/image data supplied later; mockup values/assets are not business data; missing-image fallback remains. |

## 5. Sales Request domain boundary

Later stages introduce `apps/sales_requests`, within the existing Django modular
monolith. No app directory or settings registration is created by Stage 0.

| Domain | Owns |
| --- | --- |
| products | Catalog, eligibility, inventory-facing facts, controlled current demo price source and replaceable pricing abstraction. |
| recommendations | Saved ranking/evidence, session priority context, structured feedback and acceptance lineage. |
| sales_requests | Basket, lines, review, submission/idempotency/numbering, immutable submitted snapshots, prepared message and separate acknowledgement metadata. |
| visits | Existing visit lifecycle, ownership and point-in-time snapshot safeguards. |
| sales | Existing historical Sale/SaleItem and realized transaction information. |

Historical sales logic is not moved into sales_requests. A local Sales Request is
not an invoice, payment, finalized order, allocation or dispatch instruction.

## 6. Product eligibility contract

Keep catalog visibility, add permission and priority distinct. The catalog must
not be restricted to recommendation rows or v1 candidate-generation results.

The base catalog uses existing active Product master data and validated customer
context. Do not add unsupported restrictions based on customer grade, segment,
brand/category flags, inferred credit, territory or an LLM decision.

Each catalog item conceptually exposes product identity, priority/evidence,
inventory state, pricing availability, `can_add` and a truthful reason when
non-addable. All eligible ordinary products remain accessible through search,
categories/filters and pagination. Visible zero/unknown-stock products are clearly
non-addable; visibility never grants permission to mutate a basket.

Missing price is not a zero/free quote or a reason to fabricate catalog exclusion:
show the product truthfully, and block a priced add/submission until a valid quote
exists. This is quote availability, separate from recommendation priority.

## 7. Recommendation priority versus eligibility

The v1 engine can exclude a previously purchased product because repurchase is
not due, or omit it because of score/maximum-recommendation limits. Those are
prioritization decisions and do not automatically prohibit an ordinary selection.

At session start, use the saved ordered recommendation context. Recommended
products lead the catalog; other products are labeled `بدون اولویت ویژه` where
useful. That label never means unsuitable or prohibited.

Do not change v1 scoring/rank semantics or invent company/manager priorities.
Search and filtering change the visible subset, not the saved priority order.
Inventory/price changes do not automatically rerank the session.

A proposed zero-write session mechanism is an integrity-protected read context
bound to customer, visit, actor and the saved recommendation IDs/order/version.
Carry it through navigation and Product Brief return; persist selected lineage
only on explicit mutations. The implementation may use signed context tokens
without a GET-created session model. Such a token never grants authorization.
Unavailable/stale context must be surfaced explicitly, not silently substituted
with a new recommendation run. Future explicit refresh/re-ranking is deferred.

## 8. Feedback and acceptance semantics

| Concept | Meaning | Must not imply |
| --- | --- | --- |
| Recommendation acceptance | A legitimately prioritized product was explicitly added to a request. | Realized sale, revenue, invoice or payment. |
| Request submission | A confirmed local Sales Request was registered. | Final order approval, inventory reservation or external-system delivery. |
| Realized sale | Historical/authoritative sales-system transaction. | An event automatically created by this MVP. |

Use a distinct positive event such as `ADDED_TO_REQUEST`. Never map it to existing
`SalesOutcome.PURCHASED`, update legacy purchase-derived visit flags from it, or
write Sale/SaleItem. Existing legacy outcomes and their current resolver/sync
continue to retain their existing semantics.

Structured rejection is available only for a recommendation legitimately present
in the validated saved session context. A client-supplied `is_prioritized` flag
is not proof. Ordinary products have add/detail actions without recommendation
feedback requirements; never create fake recommendations for them.

Approved quick reasons: customer not interested; price unsuitable; insufficient
stock; no present need; using another brand/model; follow up later; other reason.
Use stable technical codes with Persian labels and an optional short note.
Opening/cancelling the dialog or viewing a product creates no event.
The rejection reason `بعداً پیگیری شود` does not silently schedule a FollowUpTask.
Existing explicit dated FOLLOW_UP behavior remains separate.

## 9. Basket state semantics

A basket is the mutable DRAFT request's selected lines, not browser-authoritative
prices and not a historical Sale. GET may return an empty basket with no request
record; the first successful explicit add can create the draft transactionally.

Only a DRAFT for an IN_PROGRESS, currently authorized owned visit is editable.
Add, set positive quantity, remove and continue selling are explicit operations.
Use absolute desired quantities and expected revision for quantity edits to avoid
accidental repeated increments. One selected line per product represents its
aggregate requested quantity. Product units/package text are not silently
converted into new pack-size or inferred quantity rules.

Basket item count means selected product lines, not total units or recommendation
events. Canonical amounts, prices, currency and revisions come from the server.
Do not create a draft by opening Daily, Guided, basket, review or Product Brief.

## 10. Removal semantics

For a recommended product, preserve its original add event and record a separate
removal fact such as `REMOVED_FROM_REQUEST`. Removed membership no longer counts
as current acceptance. Do not rewrite/delete the original event or infer REJECTED,
NOT_PRESENTED or other negative feedback from removal.

Proposed line representation: retain a removed draft line with `is_selected=false`
and removal metadata. A later re-add can create a fresh selected line with fresh
lineage; a conditional uniqueness constraint prevents two selected lines for the
same product/request. Submitted snapshots are never edited by removal.

Current acceptance is scoped to a selected recommended line; historical add and
removal counts are separate measures. Retained closed-visit drafts are not active
selling sessions and never count as submitted requests or realized revenue.

## 11. Pricing contract

The conceptual provider accepts validated customer/product/quantity/as-of context
and returns: base price; discount percentage; discount amount; final unit price;
currency `TOMAN`; pricing source/version. Quote/review responses also carry
calculation/rounding policy version and a revision/fingerprint for confirmation.

Current prices come only from explicit controlled demo data. Do not fall back to
SaleItem.unit_price, mockup text, an LLM, missing-price zero or inferred promotion
rules. A=10%, B=5%, other/missing grade=0%; tax contributes 0. Promotions are not
stacked. The same quote interface must support a later Pricing Service/API.

Use Decimal end-to-end, including decimal strings at API boundaries; no float
arithmetic or authoritative browser totals. Display monetary values as whole
toman. Line and request calculations apply the grade discount once:

- line base total = quantity × base unit price;
- line final total = quantity × final unit price under the recorded rounding policy;
- line discount total = line base total − line final total;
- request final total = sum of selected final line totals.

Do not subtract the displayed aggregate discount from already-discounted line
totals again. Submitted quotes/totals are snapshots and are never repriced by GET.

Technical proposal for later pricing implementation: controlled demo base prices
are whole toman; round final unit price to one toman using Decimal ROUND_HALF_UP,
derive discount amount as base minus that rounded final price, then multiply by
integer quantity. This keeps displayed line arithmetic consistent. The product
decisions specify no fractional display but not tie-breaking/rounding granularity;
this mechanical proposal must be approved with the pricing implementation before
Stage 4. It does not block additive Stage 1 schema work, which must retain enough
precision and policy-version information. No rounding logic is implemented here.

## 12. Inventory behavior

Use canonical sellable stock: `max(available_quantity - reserved_quantity, 0)`.
Do not use gross available_quantity alone or historical visit stock as current.

| Current stock | Catalog presentation | Basket permission |
| --- | --- | --- |
| Known, sellable > 0 | Truthful available quantity. | Positive aggregate product quantity ≤ current sellable stock. |
| Known, sellable = 0 | May remain visible as out of stock. | No add or submission for that line. |
| Missing/unknown | May remain visible with inventory-unknown copy. | No add or submission for that line. |

Revalidate stock at add, quantity change and submission. A stock change does not
silently remove an existing line or create negative feedback: show the conflict
and require explicit correction. A quantity beyond stock is rejected, not silently
capped. Removing a line remains possible even when its stock is now unavailable.
No stock deduction/reservation is introduced. A request validates observed
sellable stock but is not an allocation guarantee across different customers.

## 13. Request state machine

Only two persisted request states are proposed: `DRAFT`, `SUBMITTED`.
No ACKNOWLEDGED, APPROVED, INVOICED, SENT, PAID or other state is needed for MVP.

| Explicit operation | Request before → after | Required behavior |
| --- | --- | --- |
| GET/inspection | unchanged | Zero domain writes. |
| First successful add | absent → DRAFT | Protected mutation; validated visit, stock, quote and lineage. |
| Add/edit/remove | DRAFT → DRAFT | Authorized IN_PROGRESS visit; revision guard. |
| Confirm submission | DRAFT → SUBMITTED | Nonempty selected basket; atomic current validation; number/snapshots/message persisted. |
| Matching submit replay | SUBMITTED → SUBMITTED | Return the same existing registration; no rewrite/new event. |
| Explicit success acknowledgement/finish | SUBMITTED → SUBMITTED | Separate acknowledgement record and canonical visit completion mutation. |
| Explicit no-sale finish | DRAFT remains DRAFT, if present | Complete visit; retain draft read-only; never submit it. |

SUBMITTED never returns to DRAFT. Request submission does not change Visit.status.
Draft editability is derived from both request and visit state; completed/cancelled
visits cannot be reopened or made editable through this domain.

## 14. One-request-per-visit MVP constraint

Binding maximums: one submitted request per visit and at most one active draft.
Recommended minimal Stage 1 schema: one request header per Visit using a unique
visit relation. That header starts as DRAFT and becomes SUBMITTED. It satisfies
both maximums without allowing a second draft after submission or designing a
multi-request workflow. This is a conservative technical proposal within the
approved MVP rule, not an invitation to add draft generations.

Enforce uniqueness in the database, not only in UI or get-or-create code.
Keep submitted request numbers and submission idempotency keys unique. A visit
finished without sale retains its single draft if present; it stays non-submitted.

## 15. Submission and idempotency contract

Confirmation POST includes owned request/customer/visit context, expected draft
revision, accepted quote/version fingerprint and a stable idempotency key.
Amounts/discounts from the client are never trusted as authoritative inputs.

In one transaction: validate current authorization/visit state; acquire/compare
the expected draft revision; validate every selected line's current product,
stock and price; require renewed review if price/eligibility changed; persist
submitted line/header snapshots, unique request number and prepared message;
transition exactly once to SUBMITTED. A failure rolls back the entire operation.

The number is a Sales Request number, not an invoice number. Its format is a later
technical choice; it must not use unsafe `MAX(number)+1` allocation or copy the
mockup's sample identifier. The submitted identifier stays immutable.

Same key + same canonical submission intent returns the original registration
after authorization, without repricing or repeated effects. Reusing a key for
different content, or a conflicting new submission after SUBMITTED, returns a
conflict and the authorized canonical recovery path. Duplicate clicks/tabs must
not create a second request, number, acceptance event or prepared message.

The UI disables pending controls synchronously. It never automatically retries
POST after a dropped/malformed response: use GET status recovery. Any subsequent
explicit retry retains the original submission intent/key.

## 16. Submitted-request immutability

After SUBMITTED, request business fields and submitted line snapshots are frozen:
number, customer/visit/actor identity, product/name/code/unit snapshots, quantity,
base price/discount/final price/totals/currency, pricing/lineage versions, submitted
timestamp and prepared-message text. GET, master-data edits, current re-pricing,
recommendation regeneration and acknowledgement must not update them.

No submitted line edit/remove, request delete, cancel or resubmit-as-new operation
is part of MVP. Protect these invariants in domain services, write APIs and any
administrative access; do not rely on UI visibility. Avoid cascading deletion of
submitted business records.

Acknowledgement metadata belongs to a separate append-once record, proposed as
`SalesRequestAcknowledgement` in sales_requests. This resolves the need to capture
later acknowledgement without mutating a submitted request or adding a state.

## 17. Recommendation lineage requirements

Capture the validated saved context at explicit selection/feedback time:
recommendation identity/run or version, product/customer/visit identity, saved
rank/type/score/reason, relevant explanation/score-breakdown evidence, source
surface and whether selection was prioritized or ordinary. Preserve available
verified promotion/target/company signals; do not invent absent sources or claim
causality from a badge alone.

A line/event must remain understandable after recommendation deactivation or
master-data changes. Stable identity/evidence snapshots are mandatory; a mutable
foreign-key lookup alone is insufficient. Proposed references use protective
relationships where appropriate and preserve the original IDs in snapshots.
Recommendation deactivation must continue to work; historical linked records
must not be silently deleted. Stage 1 tests must characterize deletion behavior.

Positive acceptance attaches to the exact recommendation shown in the validated
stable session, not an arbitrary current replacement row or client-supplied rank.
Ordinary selections have truthful ordinary lineage and no fake feedback event.
Removal/re-add preserve their separate historical facts.

## 18. Visit lifecycle integration contract

Preserve canonical PLANNED → IN_PROGRESS start with immutable snapshot capture,
and IN_PROGRESS → COMPLETED completion. Preserve existing legacy endpoint guards,
response semantics and ownership compatibility, including tests for legacy
historical callers versus newer current-customer-context callers.

After request success and prepared-message display, expose an explicit action:
`پایان ویزیت و بازگشت به برنامه روزانه`.
Its protected mutation uses existing lifecycle safeguards and records the
separate acknowledgement. Successful request submission alone leaves the visit
IN_PROGRESS. Opening success/detail/message pages or returning via GET never
completes a visit.

Repeated acknowledgement may return its already-recorded result; it must not
reopen a visit or weaken the existing completion API's non-success-idempotent
contract. If another legitimate path already completed the visit, read the
canonical status and reconcile explicitly; do not perform an unsafe second POST.
Snapshots, outcomes and follow-ups are not rebuilt or cleared by completion.

On returning to Daily, reread persisted visit status. New integrations must be
narrow, characterized changes; no wholesale visits/services.py refactor.

## 19. Draft and no-sale behavior

An IN_PROGRESS visit remains finishable with no request or with a draft. A draft
does not automatically submit and does not block supported no-sale completion.
After completion, retain it as DRAFT with read-only editability derived from the
closed visit. No reactivation/reopening feature is introduced. Show its distinction
from a submitted request; never include it in submitted-request/revenue counts.

Normal product behavior does not destroy submitted requests. Demo reset behavior
must be separately scoped/documented later. Preserve SP001, the five canonical
demo customers, existing scoped reset and historical/master data. Any extension
must not wipe the database or delete submitted requests to make the demo repeat.
How repeatable reset handles a demo visit already linked to a submitted request
is a later demo-lifecycle design item: skip/protect it or deliberately create a
fresh scoped scenario under an approved checkpoint. It is not resolved by
silently clearing the one-request-per-visit constraint or deleting submissions.

## 20. Prepared-message behavior

Generate and persist a deterministic customer-facing message from the successful
submitted request: stored customer/store name, request number, final TOMAN amount
and concise registration/thank-you wording. Display that submitted snapshot,
not a later repriced basket or regenerated message using changed master data.

Display exactly: `در نسخه فعلی این پیام ارسال نمی‌شود و فقط نمایش داده می‌شود.`

Copy-text presentation may be offered later; it is not delivery. Do not claim
SMS/WhatsApp/Telegram was sent, introduce send timestamps/statuses or promise
an external-system approval/notification that the demo has not performed.
No outbound messaging call, SDK, credentials or integration is part of MVP.

## 21. Authorization, CSRF and mutations

New operational boundaries require authenticated active user, active salesperson,
non-staff operational role, current authorized active customer, owned matching
visit and matching request/line/context. A signed session token never replaces
these checks. Revalidate access at mutation/submission, including after revocation.

Use existing customer-access helpers and explicitly preserve unrelated manager
inspection and legacy historical-owner contracts. Do not grant new operational
request permissions through the helper's staff inspection override. Any future
manager request visibility requires its own approved scope.

All mutations are explicit protected POST/PATCH/DELETE operations with CSRF and
appropriate state/revision guards. Validate IDs, product/recommendation pairing,
quantities, notes, currency and source versions. Use generic non-leaking denials
for inaccessible customer/visit/request combinations. Never authorize by UI,
query-supplied salesperson ID, hidden field or amount.

## 22. GET zero-write requirements

Authenticated operational GET/HEAD must not create/update drafts, lines, feedback,
recommendations, snapshots, prices, acknowledgements or visits. They must not seed
data, reserve stock, invoke a commercial decision through an LLM or call a writer.
In particular, no get-or-create basket or persistent session creation on GET.

Read-only response construction and integrity-protected navigation context are
allowed; domain writes are not. Do not introduce session saves as a workaround
for silently persisted business state. GET refresh/status recovery is safe and
manual; it is not a hidden POST retry. Test captured SQL and unchanged record
counts for relevant GET paths. Avoid cache headers that expose customer data;
use private/no-store where the existing operational contract calls for it.

## 23. SQLite concurrency and revisions

Do not assume select_for_update supplies effective row locking on SQLite.
Use transaction.atomic, database uniqueness and guarded conditional state/revision
updates. A mutation must acquire the expected DRAFT revision before changing
lines/events; zero matched rows means conflict, not silent last-writer-wins.

Concurrent draft creation must respect the unique visit relation. Concurrent
edits/submission must not partially update lines, lose removals, create duplicate
events or submit an unreviewed revision. Recheck eligibility/pricing within the
submission operation. Treat database-busy/ambiguous failures as recovery states;
do not blindly retry POST or claim success.

Submission key plus canonical intent fingerprint and constraints provide replay
protection across processes. Duplicate acknowledgement is controlled by its
separate unique request relation. Test realistic competing writes on an isolated
SQLite database; future PostgreSQL locking may supplement, not replace, these
public revision/idempotency contracts.

## 24. API boundary proposal

These are proposed additive boundaries, not implemented routes. Freeze final
wire schemas in the relevant stage before frontend/backend implementation.

| Method/path proposal | Responsibility |
| --- | --- |
| GET `/api/products/v1/catalog/` | Scoped customer/visit catalog, stable priority context, search/category/filter/page, current inventory and pricing availability. |
| GET/POST `/api/recommendations/v1/visits/<visit_id>/feedback/` | Canonical feedback read / explicit prioritized rejection with lineage. |
| GET `/api/sales-requests/v1/visits/<visit_id>/basket/` | Read existing basket or empty result; no implicit draft. |
| POST `/api/sales-requests/v1/visits/<visit_id>/lines/` | Explicit add/create draft, current validation and recommended acceptance in one transaction. |
| PATCH/DELETE `/api/sales-requests/v1/requests/<request_id>/lines/<line_id>/` | Guarded absolute quantity update / semantic removal. |
| GET `/api/sales-requests/v1/requests/<request_id>/review/` | Canonical revision, quote fingerprint and selected line/totals review. |
| POST `/api/sales-requests/v1/requests/<request_id>/submit/` | Explicit idempotent registration. |
| GET `/api/sales-requests/v1/requests/<request_id>/` and `/submission-status/` | Authorized immutable detail / ambiguous-response recovery. |
| POST `/api/sales-requests/v1/requests/<request_id>/acknowledge/` | Explicit acknowledgement and protected visit completion. |

Catalog responses distinguish overall/filtered/priority/ordinary counts, current
stock states and non-addable reasons. Basket responses return request state,
revision, selected lines, canonical prices/totals and currency. Mutation responses
return canonical state/revision rather than client-inferred success. Candidate
errors include invalid input, access denial, generic not-found, stale revision,
changed quote and non-addable stock; exact response schemas are later-stage work.

Preserve existing `/customers/`, recommendation presentation, Product Brief,
visit review, outcome and start/complete routes. Add validated ordinary-product
and filter/session return context without arbitrary redirects; retain existing
customer_code/visit_id/recommendation_id continuity and manager return behavior.
No breaking URL rename or microservice boundary is proposed.

## 25. Data/model proposal for Stage 1

No models are created here. Recommended additive foundations:

| Domain/record | Proposed data and constraints |
| --- | --- |
| products: ProductDemoPrice | One controlled current demo quote source per Product; Decimal base price, TOMAN currency, source/version/update metadata; no historical SaleItem dependency. |
| products: optional image reference | Controlled product image URI/path or simple media reference, with truthful missing fallback; dataset population deferred. |
| sales_requests: SalesRequest | Unique protected Visit relation; matching Customer/Salesperson; DRAFT/SUBMITTED; nonnegative revision; optional draft note; unique nullable submission number/key; intent fingerprint; immutable submitted totals/currency/pricing/message/customer snapshots and submitted timestamp. |
| sales_requests: SalesRequestLine | Protected request/product relationship; positive integer quantity; selected/removal state; conditional unique selected product per request; product/unit identity, quote/eligibility and recommendation/source snapshots. |
| sales_requests: SalesRequestAcknowledgement | Unique protected submitted-request relation; actor and acknowledgement timestamp/metadata, appended once after explicit action; no mutation of the submitted request. |
| recommendations: RecommendationFeedbackEvent | Append-only ADDED_TO_REQUEST/REMOVED_FROM_REQUEST/REJECTED facts as applicable; visit/product/recommendation identity, request/line linkage where present, stable reason code/optional note, evidence/session/source snapshot and creation metadata. |

References must not cascade-delete submitted requests or their snapshots. Service
validation enforces cross-record owner/customer/visit/product matching that cannot
be expressed by a simple database CHECK. Uniqueness and positive/nonnegative
constraints belong in the database where supported. Preserve recommendation
deactivation and characterize any new protective-reference effect on old commands.

Stage 1 likely files: new sales_requests package, apps/models/access/admin/model
tests; bounded additions to products/models.py and recommendations/models.py;
INSTALLED_APPS registration; reviewed additive migrations. Current likely next
migration numbers are products 0003, recommendations 0012 and sales_requests
0001. Dependency order must be verified to avoid cycles; no schema change to
historical Sale/SaleItem or Visit snapshots is proposed.

Submitted immutability and new-record admin restrictions need domain/API tests
in later stages; a new table alone does not implement the workflow. Stage 1 must
not expose basket/submission APIs, seed prices/assets or implement pricing logic.

## 26. Explicit non-goals

Stage 0: only this document. No app, model, migration, settings/API/URL, service,
view, template, JS/CSS, database, seed/reset or workflow implementation. No commit,
push, stash manipulation, cleanup/reset of the accepted tree or Stage 1 execution.

MVP: no realized sale/invoice/payment, stock reservation, outbound message,
enterprise pricing/tax/promotion engine, production sales-system integration,
advanced ML, live automatic reranking, multi-request-per-visit, manager command
center redesign, microservices, incidental PostgreSQL migration, frontend-framework
replacement, advanced routing/offline synchronization or return-demand inference.

## 27. Regression protections

- Keep v1 scoring, saved evidence, legacy outcome resolution/purchase fallback,
  visit purchase-derived fields, target and manager metric semantics unchanged.
- New acceptance/submission amounts never become legacy realized-revenue measures.
- Retain old outcome APIs and explicit dated follow-up behavior; no implicit task
  creation/cancellation from basket add/remove or a quick rejection reason.
- Preserve ownership/current-access distinction, staff/dual-role boundaries,
  access revocation checks, CSRF, POST guards, pending/focus and recovery behavior.
- GET navigation and modal cancellation create no business events.
- Preserve historical snapshots and submitted snapshots through master-data,
  price and recommendation changes; no silent cross-visit result contamination.
- Preserve Product Brief customer/visit/focus return, adding ordinary-product
  context incrementally; keep manager/default surfaces independent.
- Test no-sale completion, retained closed drafts, one-request constraints,
  SQLite write conflicts, price changes, duplicate commands/submission and replay.
- Keep deterministic SP001/scoped demo behavior; never destroy submitted requests
  to reset a scenario. No canonical database mutation for screenshot inspection.
- Validate 390px first, then 768/1024/1440: RTL/bidi, long Persian labels, >=44px
  operational targets, keyboard/focus, loading/empty/error states, no document
  overflow and no content-covering pagination/action overlays.

The full current automated baseline in section 2 is the starting regression suite,
not permission to omit new characterization/domain/concurrency tests later.

## 28. Mapping of all six approved visual references

| File | Workflow states / interaction guidance | Limits |
| --- | --- | --- |
| Persian Sales Planning App Mockup.png | Daily visit list, next action/status; customer entry; prioritized product selling cues and quantity/add controls. | Illustrated revenue/targets, maps, time windows and three-product banner are not new data/rules or catalog limits. |
| Persian Sales App UI Mockups.png | Full catalog with search/category/filter, prioritized versus ordinary groups; Product Brief; request basket/review. | Product prices/images, similar-product examples and totals require real controlled data. |
| Persian AI Sales Recommendation Flow.png | Prioritized card, quick seven-reason rejection dialog, optional note, saved/editable feedback presentation and ordinary products below. | Feedback only for legitimate saved recommendations; follow-up reason does not create a task; illustrated counts/prices are examples. |
| Persian Sales Order Flow Mockup.png | Editable basket, continue selling, final review/confirmation, registration success, prepared message and Daily return. | Filename/sample SO number does not change Sales Request terminology; illustrated arithmetic is not canonical. |
| Persian Sales Order Completion Flow.png | Success acknowledgement, submitted detail, provenance distinction, prepared-message/copy state and non-send disclosure. | No promise of actual delivery or external approval; snapshot totals must agree across screens. |
| Persian Smart Sales CRM Workflow.png | Operational customer facts; grouped full catalog; request quantities/totals and final confirmation. | Do not invent credit validity, company policy, addresses/images or other unsupported facts. |

Reference SHA256 identities:

```text
D4E48FB26215C550E978520055647B71F814EAD2531454FFDB3BEC9E24F8DF27  Persian AI Sales Recommendation Flow.png
F744BDB6D79F60833E34816AB253357EC1E74B3ED9F5F6E2DFEE1CC7199F8061  Persian Sales App UI Mockups.png
E4A1CF3729F1BDB6066A88812B17170DF6EE3D2E5A03996843F000408C275A79  Persian Sales Order Completion Flow.png
0062DE97E449BB51C5BAA82C2CFC1DEA218DE6BCF7AE32456B32BB306D97A7C7  Persian Sales Order Flow Mockup.png
5A6A9E839E251B2D2E0DB7572814A291F13A5590E9AA014875DC5DDE7C813D5D  Persian Sales Planning App Mockup.png
FB538FC6AA5A2BAA10D5D7D825C5BD6ABFE3F62C49941EBF813A554C9B4C7410  Persian Smart Sales CRM Workflow.png
```

Follow navy/teal existing foundations, restrained cards, prominent approved
product imagery, short Persian copy and one dominant next action for the state.
Do not copy phone hardware, static badge counts or unsupported navigation as
working product features. Reference composition variants do not change workflow
or justify a new palette/font/framework.

## 29. Known conflicts and approved resolution

| Previous code/mockup/spec discrepancy | Approved resolution |
| --- | --- |
| Current Guided uses only active recommendation rows and one-item pagination. | Full active catalog with stable saved recommendation priority and ordinary-product access; preserve compatible selection/return context. |
| Old engine candidate/score limits exclude non-prioritized products. | Candidate exclusion is not sale ineligibility. Do not enlarge v1 limits as a catalog substitute. |
| Zero/missing stock historically remains inspectable; some mocks imply unrestricted add. | Keep truthful visible states where shown; block add/submission and excessive quantities using current sellable stock. |
| Basket addition resembles legacy PURCHASED in earlier feedback terminology. | ADDED_TO_REQUEST is separate acceptance; legacy purchase flags/analytics and actual Sale records are unchanged. |
| Some mocks mix product discounts for one customer or show repeated discounts/inconsistent totals. | Grade-only A10/B5/other0, applied once with server Decimal arithmetic. Never seed screenshot values. |
| Current Product has no current price/image source. | Controlled dataset/provider/media foundation later; no historical-price or fabricated-image fallback. |
| Current Product Brief Guided return requires a recommendation. | Later additive validated ordinary-product/filter/session return; old URLs and manager behavior retained. |
| Older finish flow has only Visit Review and no request acknowledgement. | Submission and completion stay distinct; explicit finish after success/message plus preserved no-sale path. |
| Submitted record must be immutable but acknowledgement occurs later. | Separate append-once acknowledgement record; no extra request state or submitted payload rewrite. |
| Current demo reset deletes scoped legacy artifacts and resets matching visits. | Do not extend it to delete submitted requests. Design a later scoped repeat strategy that preserves their one-visit linkage/history. |
| Images imply valid credit, company policies, map/time estimates or future notifications. | Only supported facts; no inferred eligibility or claimed integrations. |
| Images show TOMAN and Persian dates while old amounts have unspecified currency/Gregorian presentation. | New pricing is explicitly TOMAN. Do not reinterpret legacy amounts; date localization is presentation-only and ISO API/stored dates remain unchanged. |
| Earlier 002-P freezes/exclusions described a visual-only task. | New approved journey governs later functional stages; retain unrelated working behavior and manager protection. |

The ten Stage 0 product decisions resolve the material planning questions.
Remaining later-stage design items are not conflicting product mandates:
rounding tie/granularity proposal, exact controlled asset/price dataset, final
wire schemas/number format, signed-context encoding and submitted-demo repeat
strategy. Identify these explicitly in their implementation stage rather than
guessing values, weakening immutability or asking again about approved decisions.

## 30. Stage 1 entry criteria and exact recommended scope

Entry criteria:

- Authoritative specification and all six references identified; source precedence
  and approved Stage 0 decisions recorded, without modifying the specification.
- Accepted current tree/stash/database baseline captured and fresh automated
  checks pass; no unrelated failures require repair.
- Domain boundaries, two-state machine, one-header-per-visit proposal, separate
  acceptance/removal and acknowledgement semantics, GET protections and SQLite
  concurrency expectations documented.
- Only this document added; all earlier files, migration inventory, index, stash
  and database bytes preserved by post-write audit.
- Product owner approves beginning Stage 1. Stage 0 authorization does not supply
  that approval; do not proceed automatically.

These technical/documentation criteria are satisfied by the executed Stage 0 audit.
Starting Stage 1 still requires explicit approval. The later price/image dataset
and Stage 4 rounding implementation detail do not block foundation schema design.

Recommended Stage 1 scope only: create the bounded sales_requests app and
SalesRequest/SalesRequestLine/separate acknowledgement models; additive current
demo price/optional image-reference and recommendation feedback-event foundations;
database uniqueness/quantity/reference constraints; minimal registration and
submitted-record administrative protections; isolated model/migration tests and
reviewed additive migrations. Preserve all old models/behavior and capture
characterization coverage where new references affect them.

Do not include catalog/ranking implementation, pricing calculation, dataset seed,
basket services, APIs/views/URLs, UI changes, submission/message generation or
visit-lifecycle refactoring in Stage 1. No incidental database platform change.

Executed Stage 0 post-write safety result: the only new file/status entry is
`docs/checkpoints/SALESPERSON_JOURNEY_IMPLEMENTATION_CONTRACT.md`.
All 293 pre-existing repository content files are SHA256-identical, with zero
changed or missing files. The migration inventory and stash object/list match;
the index remains unstaged and no sales_requests app exists. The compact executed
audit is recorded outside the repo at
`%TEMP%/salesperson-journey-stage0/after-audit.json`. Database before/after is
`E49950656E5AD8EFF594AD62758BDE3CBE2FFE22AA8768EDE205C1D1265D0517`.
Nothing is staged, committed or pushed. Stop for approval; Stage 1 is not started.
