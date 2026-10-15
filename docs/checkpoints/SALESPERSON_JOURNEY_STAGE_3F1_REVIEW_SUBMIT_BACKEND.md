# Stage 3F1 — Sales Request review and submit backend

2026-10-15. Implemented; awaiting owner review. Baseline: fast-track,
V3.0.18 `1f86206e970e18a15f6b9479cfb23c963b612eb5`.
Authority: [approved journey](SALESPERSON_JOURNEY_APPROVED.md),
[Stage 0 contract](SALESPERSON_JOURNEY_IMPLEMENTATION_CONTRACT.md),
[Stage 3 contract](SALESPERSON_JOURNEY_STAGE_3_IMPLEMENTATION_CONTRACT.md),
[basket backend](SALESPERSON_JOURNEY_STAGE_3E1_DRAFT_BASKET_BACKEND.md),
and the owner's Stage 3F1 submission decisions.

## Boundary and owner decisions

Use existing DRAFT/SUBMITTED states and immutable snapshots. No model, schema or
migration change. Submission idempotency uses the existing unique
`SalesRequest.submission_key` and `submission_intent_hash`, independently of
basket/feedback MutationReceipts. No SUBMIT_REQUEST receipt operation is added.

Generate the required nonempty Persian prepared-message snapshot atomically at
submission. This is registration of a Sales Request, not a realized purchase.
No message is sent, no delivery record is created, and replay never regenerates
text. No frontend, acknowledgement, Visit completion, stock reservation/deduction,
external fulfillment, tax/promotion change, Sale/SaleItem or PURCHASED effect.

## API contract

SessionAuthentication, IsAuthenticated and existing active salesperson/customer
assignment plus matching owned Visit checks apply. Staff operational access is
denied. Responses use `Cache-Control: no-store, private`.

| Method / URL under `/api/sales-requests/v1/` | Behavior |
| --- | --- |
| GET/HEAD `visits/<visit_id>/review/?customer_code=<code>` | Authoritative saved Draft lines/totals alongside current prices, inventory, validation issues and review fingerprint. Missing request: 404; never create/repair a Draft. A submitted request returns frozen details without repricing. |
| POST `visits/<visit_id>/submit/` | Explicit existing-Draft confirmation. Session CSRF is required. GET/HEAD: 405 with no mutation. |

Submit body (illustrative identities; use actual server review/context):

```json
{
  "customer_code": "C0003",
  "command_uuid": "12345678-1234-4234-8234-123456789012",
  "expected_request_revision": 4,
  "catalog_context": "<signed existing selling context>",
  "accepted_review_fingerprint": "<64-character server review SHA256>"
}
```

Unknown fields, client amounts, malformed UUID/hash, non-integer/null revision
are rejected (400 INVALID_INPUT). Existing-line context binding validates the
signature/actor/customer/Visit without requiring an unexpired/live recommendation
run. Context never replaces current authorization. New Submit requires an
IN_PROGRESS Visit and the exact current DRAFT revision.

Review includes request id/status/revision, customer/Visit, selected line ids,
quantity, product and lineage snapshots, saved quote/inventory, current quote
and inventory per product, saved/current totals, item count, total units,
validation issues, `can_submit` and `review_fingerprint`. All money remains
server-calculated whole-TOMAN decimal strings. The fingerprint binds reviewed
selection, revision, saved/current pricing and truthful sellable stock;
the server recomputes it rather than trusting client-supplied terms.

Success: 201, `Idempotent-Replayed: false|true`. Body includes request
id/number/status/revision/submitted_at, frozen customer/salesperson/Visit identity,
selected line pricing/product/lineage/inventory snapshots, totals, currency,
item count/total units, pricing snapshot, prepared message and disclosure.
The response Visit status is explicitly the stored submission-time status,
not a claim that the Visit can never subsequently complete.

## Changed terms and validation

Review/failed confirmation never changes Draft prices, totals, revision or lines.
Validate saved scalar price fields against their quote JSON, header totals and
line quote fingerprints. Malformed/contradictory saved terms yield DRAFT_INVALID.
Current prices come exclusively from Pricing Core; no historical-price fallback.

Missing/fractional prices, inactive products, unknown/zero/insufficient sellable
stock, empty selection and overflow prevent submission. Stock remains
`max(available - reserved, 0)`. Ordinary and recommended products share these
commercial checks; ordinary products create no recommendation feedback.

A changed price/grade/source version yields PRICE_CHANGED with the current review
and saved/current amounts. Even a fresh review fingerprint cannot silently
replace stored accepted prices. Use an explicit existing basket priced mutation
(including the same absolute quantity with a fresh basket quote fingerprint),
then read review again and confirm. This keeps the approval boundary explicit.

Changed stock that remains sufficient yields REVIEW_CHANGED for an old review
fingerprint. A fresh review and explicit confirmation can accept that stock state;
submission captures it. Insufficient/unknown/zero stock must be resolved or the
selection explicitly changed first. No silent capping, removal or negative event.

Errors: 403 ACCESS_DENIED/CSRF, 404 NOT_FOUND, and 409 COMMAND_CONFLICT,
REQUEST_NOT_DRAFT, VISIT_NOT_ACTIVE, REVISION_CONFLICT, REVIEW_CHANGED,
EMPTY_BASKET, DRAFT_INVALID, PRICE_CHANGED and existing commercial reason codes.
Validation conflicts include an actionable `review` object with product/line issues.
Imported/pre-service submitted snapshots missing submission metadata return
SUBMISSION_SNAPSHOT_UNAVAILABLE; GET never invents or repairs frozen evidence.

## Transactions, snapshots and replay

Lock order: Visit -> existing Request -> selected Lines -> Customer/Grade ->
Products/Inventory in stable id order. Revalidate current commercial terms;
acquire the expected DRAFT revision using the existing target-row conditional
UPDATE; capture inventory/identity/submission metadata; perform a full guarded
save to SUBMITTED. No partial `update_fields` submission save. Any failure rolls
back revision, line writes, number/key/message and status together.

Runtime demo-price permission remains SELECT-only. Pricing Core performs fresh
batched price reads at the validation boundary, without price-row locks or new
grants. Submitted pricing is a versioned point-in-time quote; this does not lock
future price configuration or guarantee warehouse allocation. Product, grade and
existing inventory rows are locked through commit on PostgreSQL. Missing rows
are never created. No process-local concurrency lock or automatic write retry.

Request number is `SR-<request primary key padded to at least eight digits>`;
existing database uniqueness enforces identity without unsafe MAX(number)+1.
Selected price/product/lineage snapshots are retained, not recalculated or
reranked. Removed historical lines remain retained and become immutable with
their parent. All selected snapshot totals and message are frozen on submission.

Canonical submission intent binds version/operation, actor, Visit, Request,
customer/context, expected revision and accepted review fingerprint. A committed
matching key/hash replays 201 and the original frozen response, after current
authorization, even after Visit closure or master price/name changes. A reused
key with different intent conflicts; a different key cannot submit an already
submitted request. Keys are globally unique across Requests; reuse of an existing
basket/feedback receipt UUID within the Visit also conflicts. Failed confirmations
persist no key or successful receipt.

**Distinct recovery boundary:** basket/feedback commands continue using
`visits/<id>/commands/<uuid>/` and append-only MutationReceipts. Submission uses
the immutable Request header, not that command-status endpoint. After an ambiguous
network result, GET the authorized review endpoint for canonical DRAFT/SUBMITTED
state. Never automatically resend POST or change an uncertain command's payload.
An explicit retry keeps the original UUID and exact payload. Confirmed changed-term
conflicts permit explicit new review/intent; no successful command is rewritten.

Prepared-message example for an isolated fixture (not a production price claim):

> مشتری الف، درخواست فروش شما با شماره SR-00000001 به مبلغ 285 تومان ثبت شد.
> از همراهی شما سپاسگزاریم.
> در نسخه فعلی این پیام ارسال نمی‌شود و فقط نمایش داده می‌شود.

## Validation and preservation

- Initial isolated PostgreSQL focused run: 177/177 passed, including basket,
  revision concurrency, receipt and submitted-model guards plus submission/catalog.
- After snapshot edge cases: 69/69 passed (32 submission tests plus 37 imported
  catalog tests). Test discovery was then narrowed to avoid rediscovering that class.
- Final submission suite: **33/33 passed**, zero failures/errors/skips, including
  six real PostgreSQL transaction/concurrency/recovery tests. Exact replay also
  passed in a fresh Python subprocess using the committed isolated test data.
- Runtime-role test passed with SELECT-only demo prices. Its grants affected only
  the isolated database; no production role/grant changes.
- Review: 11 SELECT queries for both one and two selected lines; no writes/N+1.
- Django check: no issues. Migration drift check: no changes detected. No full
  suite or frontend tests/screenshots; frontend files are unchanged.
- All three uniquely named PostgreSQL test databases were removed. Guarded runners
  prohibited Django SQLite/production connections; production reconciliation used
  separate read-only connections and passed before/after each run.
- No production table, financial data, sequence or schema changes. Original SQLite
  SHA256 remains `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
  original stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
- Existing local SQLite modification and unrelated DEMO-02 planning are preserved.
  Nothing staged/committed/pushed. Owner review is required before the next task.

Private test evidence is Git-ignored in `venv/stage3f1-artifacts/`. No credentials
or private database artifacts are part of the project diff.
