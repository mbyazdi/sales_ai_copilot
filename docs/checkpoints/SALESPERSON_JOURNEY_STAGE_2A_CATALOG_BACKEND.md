# Salesperson Journey — Stage 2A Catalog Backend

Date: 2026-10-07. Status: implemented and validated; awaiting approval.
Stage 2B has not started. No staging, commit or push.

## Authority and baseline

Behavior follows SALESPERSON_JOURNEY_APPROVED.md and
SALESPERSON_JOURNEY_IMPLEMENTATION_CONTRACT.md (particularly sections 6, 7,
9, 21, 22 and 24). Stage 1 remains as recorded in
SALESPERSON_JOURNEY_STAGE_1_PERSISTENCE_FOUNDATIONS.md. Those files are unchanged.
External images remain presentation references only; no image asset was copied.

Freshly fetched fast-track HEAD and origin/fast-track both:
`b9e43a69d7e57e141b6718ab0f0458f9e8a5ff8b`.
Initial working tree: only intentionally modified, unstaged db.sqlite3.
No reset, checkout, cleanup, stash operation, developer-database migration or seed.

## Eligibility and inventory

products/eligibility.py owns a narrow reusable stock policy:

- Catalog candidates are all active Product rows. Recommendation candidates are
  never consulted. Brand/category flags, grade, segment, inferred credit and LLM
  opinions introduce no sale restrictions.
- Inventory is an existing OneToOne Product relationship, not multiple locations.
  Reuse inventory/services.py and Inventory.sellable_quantity:
  `max(available_quantity - reserved_quantity, 0)`.
- AVAILABLE: positive sellable stock; inventory_can_add=true.
- UNAVAILABLE: a known zero sellable quantity; visible, not addable.
- UNKNOWN: missing Inventory row; visible, available_quantity=null, not addable.
  Missing stock is never fabricated as zero.
- available_quantity in this API means sellable stock, already net of reservations.
  Later quantity mutations must revalidate it; no stock is reserved here.

The stock policy's can_add is stock eligibility. The composed API additionally
requires current demo-price existence and an IN_PROGRESS visit for its can_add
hint, consistent with the contract's priced-add and editable-draft rules. Thus
positive stock alone does not fabricate a usable quote. Missing price never
removes a product from discovery; it gives PRICE_UNAVAILABLE.
PLANNED visits allow read-only preparation and cannot advertise an editable basket.

This hint is not a mutation permission or validated customer quote. Later services
must recheck authorization, visit/request state, stock, requested quantity and
pricing at the actual mutation boundary. A submitted request's editability is a
later basket-domain concern; this catalog does not read/create a request.

## Composition and saved ranking

recommendations/catalog_context.py owns saved priority context. At entry without
a catalog_context token, read all persisted active CustomerRecommendation rows
for the authorized customer, ordered by saved rank then PK for deterministic ties.
This matches existing Guided rank ordering; score is not recalculated or used to
override a saved rank. No Recommendation Engine configuration/limit is changed.

Products represented by those rows lead the full active Product catalog. Ordinary
products follow, ordered by product_code then PK, with recommendation=null and
the label `بدون اولویت ویژه`. A single Product queryset means no duplicate product
rows or competing recommended/ordinary copies. Priority counts are session-scoped.
No recommendations is a valid full ordinary-catalog result.

Search/category/priority filtering narrows the queryset without changing relative
saved priority. Zero/unknown stock and absent price do not affect ordering.
Product deactivation affects current visibility, without reprioritizing other rows.

## Zero-write session continuity

The service returns a Django timestamp-signed, compressed read context, bound to
user, salesperson, customer and Visit. It contains ordered recommendation IDs
and SHA256 fingerprints of saved identity/rank/type/reason/evidence/score/version
fields. Signing uses a dedicated v1 salt and an eight-hour maximum age, a bounded
demo read-context lifetime. It is integrity protected, not encrypted, and never
grants access. No persistent session, draft, cache record or Django session save
is created by the catalog.

Consumers MUST carry the returned token through paging, filters, repeated reads
and Product Brief navigation. Omitting it means a new read-context entry, not
continuation of an existing session. Stage 2B must not omit/reset it automatically.
Reusing it returns exactly the same ordered recommendation identities. Newly
inserted recommendations do not join an existing context; its remaining products
remain ordinary. Inventory/price changes are read afresh without affecting rank.

Changed/deactivated/deleted saved rows, a changed fingerprint, tampering, expiry
or binding mismatch gives CATALOG_CONTEXT_UNAVAILABLE (409). There is no silent
replacement, recommendation regeneration, automatic refresh or write-on-read.
Closed/missing/foreign visits or revoked access fail before context use.
Later explicit refresh/re-ranking UX is deferred.

Pagination is deterministic for an unchanged filtered Product set. This does not
freeze all master-data rows or invent a repeatable-read snapshot across requests;
concurrent catalog insertions/deactivations can alter offset page membership.
The guarantee is stable recommendation priority, not reserved stock or frozen
prices/master data.

## API contract

Read endpoint: **GET /api/products/v1/catalog/**, URL name product-catalog-v1.
HEAD and OPTIONS are supported; POST/PUT/PATCH/DELETE are not supported.
All responses use `Cache-Control: no-store, private`.

Example entry:
`/api/products/v1/catalog/?customer_code=C0003&visit_id=14&page=1&page_size=20`

| Query parameter | Contract |
| --- | --- |
| customer_code | Required authorized active customer code. |
| visit_id | Required positive ASCII integer, at most 18 digits; must match customer/owner. |
| catalog_context | Omit only for entry; carry the returned signed token for continuity. |
| q | Optional trimmed substring search, at most 200 characters. |
| category_id | Optional exact category PK; no inferred descendant/category restrictions. |
| priority | all (default), prioritized, ordinary. |
| page | Positive integer, default 1; beyond last page gives 404. |
| page_size | Positive integer, default 20, maximum 100. |

Search uses Product code/name and Brand/Category names with icontains. Unknown
category or no search matches gives a truthful empty result at page 1.
Category choices come from the full visible catalog, independently of filters.

Top-level response fields:

- version=1; customer {id, code, name}; visit {id, status}; catalog_context.
- counts {overall, filtered}, each {total, prioritized, ordinary}.
- categories [{id, code, name}]; filters {q, category_id, priority}.
- pagination {page, page_size, pages, has_next, has_previous}; items.

Each item:

- product_id, product_code, name, unit; brand {id, name}; category {id, code, name}.
- is_prioritized, priority_label; recommendation=null for ordinary products, or
  {id, rank, type, short_reason, explanation_snapshot}. short_reason selects at
  most two complete saved sentences using the existing Guided presentation rule;
  it does not generate an explanation or reinterpret evidence.
- catalog_visible=true; inventory_state; available_quantity; inventory_can_add;
  can_add; non_addable_reason (null, INVENTORY_UNKNOWN, OUT_OF_STOCK,
  PRICE_UNAVAILABLE or VISIT_NOT_ACTIVE).
- image {url:null, state:MISSING}: truthful fallback until controlled assets exist.
- pricing {has_demo_price:boolean, state:NOT_EVALUATED}: correlated EXISTS only.
  No price, grade discount, currency conversion, total, promotion stacking,
  historical-price lookup or pricing provider is implemented.
- brief_url: canonical Product Brief URL carrying validated return context.

Errors: 400 INVALID_INPUT with Persian field messages; 403 ACCESS_DENIED;
404 NOT_FOUND for unavailable context/page; 409 CATALOG_CONTEXT_UNAVAILABLE.
Unauthenticated requests retain the existing DRF IsAuthenticated behavior.
No arbitrary redirect parameter is accepted.

## Authorization and mutation protection

products/catalog_access.py reuses customer_access_queryset for current assignment
scope. It additionally enforces authenticated active user, active salesperson,
non-staff operational role, active customer and matching owned Visit. User/profile
are reread, so a cached service-caller instance cannot bypass role revocation.
Assignment does not substitute for Visit ownership. Staff and dual-role accounts
are denied on this new operational API; manager inspection remains unchanged.

PLANNED and IN_PROGRESS permit catalog reads; COMPLETED/CANCELLED are unavailable
selling contexts. No date-based assignment/Visit expiry or unsupported organizational
rule is invented. Tokens are checked only after current access is validated.
The endpoint uses existing DRF authentication and adds no mutation method or CSRF
exemption. Existing POST/CSRF/lifecycle behavior remains intact.

## Product Brief continuity

The additive backend mode is return_to=catalog with customer_code, owned visit_id,
catalog_context and q/category_id/priority/page/page_size. It works for ordinary
and prioritized products. The existing Product Brief view validates operational
access, token and options before constructing the return URL.

Destination is always the canonical recommendation-presentation route for the
authorized customer. It carries visit_id, selected product_id, the same token and
filters/page, with #catalog-product-<id>. There is no caller-controlled host/path
or acceptance of arbitrary return_url values. Missing/tampered/foreign/closed
context fails safely. No UI/template/Product Brief redesign was made.

Legacy return_to=presentation recommendation_id/visit_id/anchor construction and
default customer/manager return behavior are unchanged. Stage 2B must consume the
new product_id/filter/token contract in Guided; today's recommendation-only
Guided template/controller is deliberately not connected to the full catalog yet.
This stage establishes navigation context, not ordinary-product Guided rendering.

## Query behavior and zero-write evidence

Products use select_related for brand/category/inventory; demo price availability
uses correlated EXISTS; saved recommendations are fetched once. Aggregate counts
are reused for pagination. No per-item query or unbounded full Product materialization.

Representative service tests assert exactly **8 queries**, both for a 6-product
catalog and an 86-product catalog rendered with page_size=100, including current
access, ranking, counts and category discovery. Authentication middleware may add
its own fixed queries outside this service boundary. Empty contexts/results can
use fewer queries.

The zero-write regression captures SQL across service reads, API GET/HEAD and
an ordinary-product Product Brief GET. INSERT/UPDATE/DELETE/REPLACE count is zero.
Full row snapshots of customers/products/inventory/recommendations/visits/
sales_requests/historical sales models remain unchanged. SalesRequest, Sale and
SaleItem counts remain zero. Engine.generate, _save_recommendations and the Ollama
generator are patched to fail if called; none is called. No recommendations,
requests/lines/events, visits/snapshots, prices or stock are created/changed.

## Executed validation

- Django check: no issues, 0 silenced.
- Focused apps.products.tests_catalog: **37 passed**.
- Existing recommendation/Product Brief/customer presentation/visit regressions:
  **178 passed**.
- Full Django suite: **304 passed** (267 existing + 37 new), including Stage 1
  model/immutability/migration tests.
- makemigrations --check --dry-run: **No changes detected**.
- Existing JS regressions: **20 scenarios across 3 files passed**.
- node --check: **13 JS/CJS files passed**.
- git diff --check and new-file whitespace checks: passed.

The initial focused run had one new-test failure from a fixture's cached reverse
inventory object after QuerySet.update. The test now reloads Inventory via a fresh
Product, matching the service's current reads. No existing regression failed and
no legacy test was weakened. No browser redesign/viewport approval is claimed:
Stage 2B alone owns visual implementation and 390/768/1024/1440 validation.

## Exact file set and safety

New:

- apps/products/eligibility.py
- apps/products/catalog_access.py
- apps/products/catalog.py
- apps/products/api_views.py
- apps/products/api_urls.py
- apps/products/tests_catalog.py
- apps/recommendations/catalog_context.py
- this checkpoint

Modified:

- apps/products/views.py: additive validated catalog-return mode only.
- sales_ai_copilot/urls.py: additive api/products include only.

No model/settings/migration/legacy recommendation engine/service, salesperson UI,
template, JS/CSS, manager surface, Visit lifecycle, legacy PURCHASED or historical
Sale/SaleItem writer was changed. No basket, feedback POST, pricing calculation,
submission, prepared-message generator, messaging or Stage 2B implementation.

Database SHA256 before/after:
`E49950656E5AD8EFF594AD62758BDE3CBE2FFE22AA8768EDE205C1D1265D0517`.
db.sqlite3 remains its intentionally modified local file and was not migrated/seeded.
Stash remains stash@{0}: home-local-files-before-fast-track-work-2026-10-05,
object `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
The index is empty; no staging, commit or push.

## Concerns, deployment and Stage 2B entry

No unresolved inventory or product-rule ambiguity was found. Source precedence
resolves candidate exclusion versus catalog eligibility and missing-price behavior.

Runtime catalog price availability requires the already-approved Stage 1 schema
to be applied to the chosen deployment database. This stage did not apply it to
developer db.sqlite3. Tests use fully migrated isolated databases. Controlled
price/image population and a trusted final pricing provider remain later stages.

Stage 2B technical entry criteria are satisfied: tested full-catalog service/API,
explicit visibility/addability, stable carried ranking context, Product Brief
continuity and passing baseline regressions. Stage 2B still requires approval.
It must carry tokens, handle 409 explicitly, consume selected product_id, preserve
existing outcome/manager/return contracts, and validate mobile-first presentation
at 390, 768, 1024 and 1440px. Do not introduce automatic token reset/reranking or
pretend that NOT_EVALUATED pricing is a final quote.

Stop for approval. Do not stage, commit, push or start Stage 2B.
