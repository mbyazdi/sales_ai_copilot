# Stage 3D1 — durable recommendation feedback API

2026-10-09; fast-track baseline V3.0.16 `c96907af` plus the preserved approved
uncommitted receipt foundation. Backend only; no UI or basket work.

## API contract

`/api/recommendations/v1/visits/<visit_id>/feedback/`

- GET/HEAD: authorized history, ordered by created_at then PK, 50 events per page.
  Required `customer_code`; optional `recommendation_id` and positive `page`.
  Returns version/customer/Visit, count/page/pages, rejected/deferred events and
  existing request ID/revision/status or null. It creates neither context nor Draft.
- POST: explicit decision. Standard Django session authentication with mandatory
  CSRF; Basic authentication is not an alternative bypass for this endpoint.
- OPTIONS: normal authenticated API metadata. PUT/PATCH/DELETE are unsupported.
- All responses use `Cache-Control: no-store, private`.

POST fields:

| Field | Contract |
| --- | --- |
| customer_code | Required active assigned customer matching Visit. |
| recommendation_id | Required positive JSON integer; legitimate saved recommendation. |
| command_uuid | Required stable client UUID, reused unchanged for an uncertain retry. |
| action | Exactly REJECTED or LATER. |
| reason_code | Required for REJECTED: exactly NOT_INTERESTED, PRICE, STOCK, NO_CURRENT_NEED, OTHER_BRAND, LATER or OTHER. For action LATER, omit or supply LATER only. |
| note | Optional trimmed text, up to 200 characters; no requirement invented for OTHER. |
| catalog_context | Required saved signed Guided catalog context; never a client priority flag. |
| expected_request_revision | Optional/null when no request exists. If a request exists, supply its current integer revision. This API never advances it. |

Unknown fields, malformed bodies, noninteger identifiers/revisions, invalid
reasons and overlong notes are rejected. No quantity, client actor, priority,
pricing or basket inputs are supported.

Fresh success is HTTP 201 with `Idempotent-Replayed: false`, for example:

```json
{
  "version": 1,
  "customer": {"id": 1, "code": "TEST-CUSTOMER"},
  "visit": {"id": 1},
  "feedback": {
    "id": 1, "recommendation_id": 1, "product_id": 1,
    "event_type": "REJECTED", "action": "LATER", "reason_code": "LATER",
    "note": "", "created_at": "2026-10-09T00:00:00+00:00"
  }
}
```

This is an illustrative test response, not a production mutation/result.
Identical successful retry returns the exact stored body/status, with header
`Idempotent-Replayed: true`. A different intent for the same Visit/UUID returns
409 COMMAND_CONFLICT. Other stable errors include INVALID_INPUT (400), ACCESS_DENIED
(403), NOT_FOUND (404), VISIT_NOT_ACTIVE, REQUEST_NOT_DRAFT, REVISION_CONFLICT,
PRODUCT_ALREADY_SELECTED and CATALOG_CONTEXT_UNAVAILABLE (409).

## Authorization, lifecycle and lineage

The existing profile/assignment/ownership logic is reused through a small extraction
of `visit_customer_access` from the catalog access helper. Catalog/quote allowed
states and query behavior are unchanged. Feedback reads/replays can inspect an owned
closed Visit; fresh commands require IN_PROGRESS. Staff/dual-role/inactive or missing
profiles, inactive/revoked customers/assignments and foreign Visit/customer combinations
remain denied. Signed context never grants authorization.

Fresh decisions validate the current active recommendation/product and the saved
signed actor/customer/Visit/ranking context, preserving recommendation ID, product,
customer/Visit/actor, saved rank/type/score/confidence/reason/evidence and context
fingerprint. No recommendation generation, scoring or update occurs. Ordinary
products have no fake recommendation/feedback. Selected products are blocked even
when their selected line's source is ORDINARY; explicit removal is required first.

LATER persists **REJECTED + reason LATER**, never a new event type, automatic
FollowUpTask or Visit completion. Existing dated follow-up and PURCHASED semantics
are untouched. Request/line state is read only, with no creation/revision mutation.

## Durability and concurrency

One atomic transaction appends the RecommendationFeedbackEvent and existing
SalesRequestMutationReceipt, operation REJECT_RECOMMENDATION. The receipt may have
no request; an existing Draft linkage captures its unchanged applied revision.
Canonical intent binds action/reason/note/target/revision and signed-context hash.
No raw context token or credentials are persisted in lineage/receipt output.

Lock order is Visit, existing Request, target Recommendation; same-Visit PostgreSQL
writers serialize. Existing Visit+UUID database uniqueness is the durable backstop.
Failure rolls back event and receipt; integrity-race recovery only reads an already
successful receipt, never retries the mutation. No process-local locks or assumed
SQLite row locks. No automatic POST retries after ambiguous network failures.

Authorization is rechecked before replay; a successful historical command survives
context expiry, recommendation deactivation and completion without authorizing a
new closed-Visit mutation. Existing append-only model/ORM guards are unchanged.
Raw SQL or deliberately bypassed ORM guards remain outside these protections;
the API exposes no update/delete path. Runtime grants already permit required row
locks and SELECT/INSERT on event/receipt tables, without UPDATE on append-only tables.

## Validation and preservation

48 distinct focused PostgreSQL tests passed: 27 feedback/CSRF/history/concurrency
cases and 21 existing quote/shared-authorization regressions. Initial 46-test run
had 45 passes and one new unknown-field error-shape bug; corrected to a dictionary
validation error, then only that regression plus a malformed-body case passed.
A separate new conflicting-UUID concurrency test passed. Successful suites were
not repeated; no full regression suite or browser work ran.

Concurrent identical commands yielded one event/receipt and exact replay. Concurrent
different intents with the same UUID yielded one success and one COMMAND_CONFLICT.
Tests cover all seven reasons, state/access/context denial, selected-product conflict,
rollback, expired-context replay/access revocation, historical revision, GET/HEAD
zero writes, missing/invalid/valid CSRF, and guarded ORM immutability for both records.

All three uniquely named isolated test databases were removed. Django check and
whitespace checks passed. Production data/metadata remain unchanged (49 migrations,
14 demo prices), original SQLite and stash preserved. Receipt models/admin/migration/
history tests stayed byte-identical. No new migration, UI, pricing, assignment,
inventory, legacy outcome, Draft, Basket, submission, completion or message changes.

The API depends on the already-approved receipt foundation still present locally
and uncommitted; a later commit boundary must include that dependency explicitly.
No receipt file was changed or staged here. Stop after Stage 3D1 for owner review.
