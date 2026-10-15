# Stage 3G1 — Explicit Visit completion backend

2026-10-15. Implemented for owner review; no frontend integration.
Baseline: fast-track / V3.0.19 d168a0da911849ecd8a65823ee981404a77ecdf1.

## Authority and existing behavior

The approved salesperson journey and Stage 0 lifecycle contract govern this
stage. The owner's Stage 3G1 Option 1 decision explicitly permits COMPLETE_VISIT
on the existing append-only SalesRequestMutationReceipt and an additive migration.

Use only IN_PROGRESS -> COMPLETED. No required outcome, completion reason,
purchase flag or new Visit status is introduced. No request, a retained DRAFT,
and a SUBMITTED request are all supported. Submission alone never completes a
Visit. Existing snapshots, request status/revision/lines, recommendation events,
legacy outcomes, follow-ups, inventory, prices and historical sales are untouched.

## Persistence

sales_requests/0003_complete_visit_receipt depends on 0002 and only replaces
srmr_valid_operation and extends the operation field's choices. No new table,
column, data migration or historical migration edit. All four prior operations,
Visit+UUID uniqueness, optional request/revision pairing and append-only guards
remain intact.

A no-request completion receipt has NULL sales_request/applied_revision. With an
existing request, it records that request and its unchanged historical revision.
The receipt contains the canonical successful response, including completion
time, command UUID, request identity/status/revision and acknowledgement identity.

For SUBMITTED only, create the existing separate SalesRequestAcknowledgement
in the same transaction, owned by the Visit salesperson. Metadata binds the
command, Visit and completion time. An already-present valid acknowledgement is
reused unchanged. DRAFT/no-request completion never creates an acknowledgement.
No request snapshot is modified to record acknowledgement or completion.

Reverse migration preserves old-operation receipts when no COMPLETE_VISIT rows
exist. Once completion evidence exists, the old CHECK rejects reversal: stop and
retain the migration; never delete/relabel historical receipts to force rollback.

## API contract

New endpoint: /api/visits/v1/visits/<visit_id>/completion/

- GET/HEAD ?customer_code=<code>: authorized, read-only canonical Visit state,
  current request identity/status/revision, can_complete and recorded_result.
  Reads never create a Draft, receipt, acknowledgement or other business record.
- POST: explicit completion, session authentication with CSRF. Body has exactly
  customer_code and command_uuid; reject unknown fields and malformed inputs.
  No catalog/ranking token, price fingerprint, outcome or reason is needed for
  Visit completion: current ownership and assignment remain authoritative.

Example input (illustrative only):

~~~json
{
  "customer_code": "C0003",
  "command_uuid": "0c106ffe-0e58-4113-9783-42e219487ee6"
}
~~~

Successful new command or identical replay: HTTP 200, with
Idempotent-Replayed: false or true. Response fields:

- version: 1 and success: true
- customer: id/code
- visit: id, COMPLETED status, customer_code, salesperson_code
- command_uuid and completed_at (receipt's original completion timestamp)
- request: null or id/status/revision/number
- acknowledgement: null or id/sales_request_id/actor_id/acknowledged_at

GET returns version, customer, current visit, request, can_complete and
recorded_result (the original successful POST body, or null). Its state projection
and receipt JSON are read in one SQL statement after authorization. A Visit
completed by the legacy endpoint legitimately has no new recorded result;
GET does not backfill evidence, infer a completion time from updated_at or
perform a second completion.

Errors have code and Persian detail:
400 INVALID_INPUT; 403 ACCESS_DENIED or standard session/CSRF denial;
404 NOT_FOUND; 409 COMMAND_CONFLICT or VISIT_NOT_ACTIVE.
Responses are private/no-store. PUT/PATCH/DELETE are not supported.

## Authorization, idempotency and transactions

Reuse visit_customer_access: active authenticated non-staff salesperson, active
profile, active assigned customer, matching customer/Visit and Visit owner.
Authorization is reread for replay as well as new commands; historical success
does not bypass revoked access.

Canonical intent hashes version, COMPLETE_VISIT operation, authenticated actor,
Visit and validated customer code with deterministic SHA256 JSON. UUID addresses
the receipt and is not itself an intent field. No arbitrary client intent hash
is trusted. The input has no optional business decision to silently ignore.

Within one atomic transaction:

1. Lock Visit through the existing authorization helper.
2. Check Visit+UUID receipt. Matching actor/operation/intent returns its frozen
   body/status without a new timestamp, write or acknowledgement.
3. Require IN_PROGRESS, then lock an existing Request (never get_or_create).
   Reject reuse of that request's submission UUID.
4. Conditional target-row UPDATE requires the same Visit/customer/owner and
   IN_PROGRESS. Zero updated rows is a lifecycle conflict.
5. Create/reuse the submitted-request acknowledgement if applicable.
6. Insert the append-only successful receipt and commit.

Same Visit lock order as basket, feedback and submission: Visit -> Request.
Concurrent identical completion commands yield one apply and one replay.
Different completion commands yield one apply and a lifecycle conflict.
Acknowledgement or receipt failure rolls back status and all new evidence.
No failed command leaves a successful receipt. No process-local locks, silent
POST retries or SQLite select_for_update correctness assumption are introduced.

A fresh process reconstructs replay entirely from committed receipt data;
no process memory, session cache or mutable request journal is required.
Read-only GET is the status-recovery boundary after an uncertain response.
Clients must explicitly recover/retry the same UUID, never automatically POST.

## Legacy compatibility and deferred work

/api/visits/v1/visits/<id>/complete/ and VisitCompleteAPIView are unchanged.
Legacy completion still returns its existing success response and rejects a
second completion with HTTP 400. Its historical-owner/current-context access
distinction is preserved. It does not acquire new durable replay semantics or
retroactively create request acknowledgement evidence.

The new endpoint's Visit lock serializes participating new workflow services.
Its conditional UPDATE also detects a legacy completion that wins first.
The unchanged legacy path is not claimed to have new command-level concurrency
or replay guarantees.

No frontend, completion dialog, Daily navigation change, message sending,
automatic task, PURCHASED feedback, stock reservation/deduction, request
submission/repricing or realized Sale/SaleItem write is included.

## Validation and preservation

Final focused PostgreSQL run: 192 tests, 191 passed, 1 failure, 0 errors/skips.
All 24 new completion and migration tests passed, including real separate-connection
concurrency, completion versus submission, process-restart replay, CSRF, selected
Draft preservation, submitted immutability, acknowledgement and receipt rollback,
append-only evidence, forward/reverse migration and zero-write GET/HEAD.
Existing receipt, submission, basket, feedback, revision-concurrency and canonical
legacy completion regressions passed. No full suite was run.

The sole failing test is unchanged baseline
apps.visits.tests_completion_review.VisitCompletionReviewTests.
test_missing_and_inactive_customer_do_not_leak_identity (line 226): a byte-for-byte
HTML comparison includes randomized masked CSRF values from shared navigation.
A separate 1/1 isolated diagnostic confirmed both pages differ ONLY in these token
values; test, handler and unavailable template are identical to HEAD. All other
HTML bytes and the expected 404 statuses match. This existing assertion is left
unchanged; the full focused selection is not claimed green. Its narrow test-only
normalization remains a review follow-up, not a change to authorization/CSRF/UI.

The first 24-test development run had one malformed-input error in the new
serializer's error shape (23 passed). Returning a structured non_field_errors
object corrected it; the final run's malformed-input regression passed.

Django system check: no issues. makemigrations --check --dry-run: no changes.
New migration was exercised only in disposable test databases, including full
fresh migration and historical round trips. All validation databases were removed.
Production canonical schema/table/data/sequence before/after reconciliation was
identical for every run; production remains on its existing migration baseline.
Production migration 0003 is NOT applied by this task.

Logs and the baseline CSRF diagnostic are protected and Git-ignored under
venv/stage3g1-artifacts/. No credentials or private database artifacts are included
in this checkpoint. No frontend or JS change; no browser preview was modified.

Exact project files changed:

~~~text
apps/sales_requests/models.py
apps/sales_requests/migrations/0003_complete_visit_receipt.py
apps/sales_requests/tests_completion_migration.py
apps/sales_requests/tests_mutation_receipts.py
apps/visits/completion.py
apps/visits/completion_views.py
apps/visits/tests_completion.py
apps/visits/urls.py
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3G1_VISIT_COMPLETION_BACKEND.md
~~~

The existing receipt operation-enumeration test now expects five supported
operations instead of four; existing guard/lineage/immutability expectations
are unchanged. Whitespace and source-scope checks passed.

Original SQLite baseline SHA256:
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15

Original stash: 2dac7bdc26f07f611f471564476ceaa52ec367cc.
Unrelated DEMO-02 planning is excluded. No staging, commit or push.
