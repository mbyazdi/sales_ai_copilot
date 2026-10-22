# Stage M-D1 — Management Strategy API V1

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Status: source-only, isolated validation passed; NOT DEPLOYED.
Authority: approved M-A2 and approved uncommitted M-C1 through M-C4.

## Routes and permissions

Prefix `/api/management/v1/strategy/`; existing dashboard API remains unchanged.

| Method/path | Capability | Contract |
| --- | --- | --- |
| GET `overview/` | strategy-view | Head revision, active/draft IDs, validated active configuration (neutral if absent), version/comparison counts, explicit integration/impact limitations |
| GET `options/` | strategy-view | Typed rule bounds and paged reference choices; optional authoritative preview context/fingerprint |
| GET `versions/` | strategy-view | Immutable versions, config/hash/algorithm, parent/author IDs, timestamp, ever-published flag |
| POST `draft/` | strategy-manage | M-C4 immutable draft command |
| POST `comparisons/` | strategy-manage | M-C3 accepted-source comparison command |
| GET `comparisons/{id}/` | strategy-view | Frozen before/after output, explanations/contributions, positions, quotes and evidence digests |
| POST `publish/` | strategy-manage | M-C4 accepted-comparison publication |
| POST `rollback/` | strategy-manage | Explicit PREPARE or ACTIVATE stage of M-C4 rollback |
| GET `commands/{uuid}/` | strategy-view plus service manager/actor check | Read-only committed-command recovery |

GET routes also allow HEAD; OPTIONS is authenticated. Mutation routes accept
POST/OPTIONS only. No edit/delete endpoints. All responses use JSON and
`Cache-Control: no-store, private`. JSON is the only mutation body format.

Current view/manage hooks both require authenticated active staff, as approved
for the single global management role. No salesperson impersonation. Policy ID
is fixed to 1, never client-selected. New capture/comparison/publication validates
the genuine active salesperson/customer assignment for the supplied date. Current
global managers can inspect immutable historical comparisons after assignments
change; command recovery remains original-actor-only. Future organizational role
separation must retain the service authorization boundaries, including the
manager requirement on command recovery.

Uses ordinary Django database-backed sessions and standard SessionAuthentication
CSRF enforcement. The endpoint-local authentication subclass changes only the
401 challenge and safe CSRF error presentation; it calls the standard validator.
No basic/token authentication, middleware bypass, login or logout changes.

## Request and response contracts

All POST bodies reject unknown fields, numeric/bool UUIDs, coerced string/bool
integers and out-of-range IDs/revisions. UUIDs are JSON strings. Digests are 64
lowercase hexadecimal characters. Dates are supplied as `YYYY-MM-DD`, evaluated
using the approved Asia/Tehran capture semantics. IDs below are illustrative
disposable-fixture identifiers, not persistent Demo instructions.

Every mutation supplies `command_uuid` and integer `expected_revision`.

- Draft adds `config`: exact M-C1 V1 JSON (`schema_version`, `priority_rules`,
  `target_weight`, `promotion_rules`). Existing service validates references,
  duplicates, bounds and semantic configuration hash.
- Comparison adds `customer_id`, `salesperson_id`, `proposed_version_id`,
  `evaluation_date`, `accepted_source_fingerprint`.
- Publish adds `draft_version_id`, `comparison_id`,
  `accepted_comparison_digest` (the accepted comparison's output digest).
- Rollback PREPARE adds `action: "PREPARE"`, `target_version_id` (previously
  published version ID, or explicit null for neutral). Creates a NEW inactive
  rollback draft. Preview that draft normally.
- Rollback ACTIVATE adds `action: "ACTIVATE"` and the same three acceptance
  fields as Publish. Calls `rollback_strategy`; no automatic preparation,
  comparison, activation or repeated POST.

Example draft:

```json
{
  "command_uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "expected_revision": 0,
  "config": {
    "schema_version": 1,
    "priority_rules": [{"scope_type": "PRODUCT", "scope_id": 3, "points": 20}],
    "target_weight": 0,
    "promotion_rules": []
  }
}
```

Command response shape: `{"event_id": integer, "operation": code, "result":
original_canonical_service_result}`. New Draft/Preview/rollback PREPARE returns
201; exact replay returns 200 with identical body. Publish/rollback ACTIVATE
returns 200 for success/replay. `Idempotent-Replayed: true|false` distinguishes
replay without rewriting the original result. UUID + different intent conflicts.
There is no automatic mutation retry.

Preview fingerprint acquisition is read-only:

```text
GET options/?customer_id=1&salesperson_id=7&proposed_version_id=1&expected_revision=1&evaluation_date=2026-10-16
```

`preview_context` contains those five validated fields plus
`accepted_source_fingerprint`. POST that context with a new command UUID to
`comparisons/`. Fetch `comparisons/{result.comparison_id}/` for frozen output
and `output_digest`; explicitly accept it in Publish. Changed facts between
capture/preview/publish reject the new command under existing M-C3/M-C4 snapshot
semantics. Fingerprints are opaque hashes, not client-supplied business facts.

`options/` without context returns bounds/limitations. Optional `kind` selects
products, brands, categories, promotions, salespersons or customers. Customer
choices require `salesperson_id` and `evaluation_date` and include only active
customers with a genuine assignment covering that date. Reference choices and
versions use `after_id` (default 0) and `limit` (default 50, maximum 100), ordered
by PK, with `results` and nullable `next_after_id`. Duplicate/unknown query keys
are rejected by options/versions validation. No unbounded reference export.

Comparison response includes customer/salesperson/date, baseline/candidate IDs,
revision, input/output/source digests, server-generated `outputs` and `quotes`.
`outputs` retains Persian reason data, component contributions, before/after
ordering, original source scores/ranks/IDs and commercial annotations. Explicit
`availability_scope=COMMERCIAL_QUANTITY_ONE_NOT_VISIT_MUTATION_AUTHORIZATION`
prevents treating manager simulation as Add permission. Raw capture documents,
database endpoint/name and unrestricted source records are omitted.

GET `commands/{uuid}/` returns `{"operation": code, "result": stored_result}`;
missing command returns 404. It never creates state or retries a command.
No GET initializes a policy, activates a version or refreshes stored history.

## Stable errors

Errors have `{code, detail}` with Persian detail; serializer errors additionally
contain field error codes, not submitted values or internal model/SQL diagnostics.

| Status | Codes/meaning |
| --- | --- |
| 400 | INVALID_INPUT: malformed JSON, UUID, typed body/query, references or bounds |
| 401 | AUTHENTICATION_REQUIRED: valid active Django session absent |
| 403 | ACCESS_DENIED or CSRF_FAILED |
| 404 | NOT_FOUND: missing comparison/committed command |
| 409 | Existing service conflict codes, including STALE_POLICY_REVISION, COMMAND_INTENT_CONFLICT, STALE_STRATEGY_INPUTS, STRATEGY_DRAFT_CHANGED, STALE_OR_MISMATCHED_COMPARISON; INVALID_STRATEGY_EVIDENCE for contradictory/missing digests |
| 405/415 | METHOD_NOT_ALLOWED / INVALID_INPUT for unsupported method/media |
| 503 | STRATEGY_NOT_READY: unavailable schema, grants or database dependency; no fallback or repair |

## Validation and preservation

Runner: `python -B -m apps.management.verify_strategy_api` (guarded disposable
PostgreSQL); `--sqlite` selects in-memory SQLite. No original SQLite is opened.

- PostgreSQL: **144 passed, 0 failures/errors/skips**, including 26 API tests
  and 118 approved focused C1–C4/evaluator/engine regressions. Independent
  backend PIDs and real normal Django sessions prove one winner/one conflict
  for HTTP publication and rollback races. C4 also retains forced-overlap
  identical-command replay and head-CAS concurrency tests.
- SQLite: **128 passed, 16 PostgreSQL-only skips** across the focused selection.
  The first run exposed two new transport errors from a DRF non-field error
  shape. Corrected only the new strict serializer, then reran the affected API
  selection: 23 passed, 3 PG-only skips. Unchanged C1–C4 regression evidence
  from that run was retained rather than rerunning it unnecessarily.
- Tests use normal login POST, DB sessions and CSRF cookies/tokens, not
  force_authenticate/force_login. Verify missing/invalid CSRF, inactive/nonstaff
  denial, assignment scoping, immutable evidence, reconnect replay, conflicting
  UUID, changed source facts, rollback stages, first-use GET/HEAD zero writes,
  bounded options/history, stable redacted errors and logout invalidation.
- A separate disposable publication runtime receives only the prior C4 grants
  plus session SELECT/INSERT/UPDATE/DELETE and auth_user UPDATE(last_login).
  Normal runtime-role HTTP login/preview/publish/logout succeeds. Existing C3/C4
  negative privilege tests remain passing. No persistent grants were changed.
- Django check, unchanged 51-migration graph, migration drift, route assertions,
  eight scoped Python syntax checks and tracked/scoped whitespace checks pass.
  No new migration, JS change or full suite. Migration round-trip was not
  repeated; the existing graph was applied only to disposable PostgreSQL/SQLite.
- All non-strategy row digests, including requests/Visit snapshots/feedback and
  commercial sources, match across the API draft/preview/publish journey after
  normal authentication setup. Persisting previews writes only comparison/event
  evidence; exact replay adds no duplicate records.
- Disposable PG database/test roles removed. Persistent Demo all-user-table and
  sequence digest unchanged. Original PostgreSQL never connected to. No service
  restart, deployment, Gate V2, Prepare Day, reset or generation switch.

## Exact M-D1 files

Modified: `apps/management/api_urls.py`,
`apps/management/verify_strategy_foundation.py` (optional disposable API grants).

Added: `apps/management/strategy_api_serializers.py`,
`apps/management/strategy_api_reads.py`, `apps/management/strategy_api_views.py`,
`apps/management/strategy_api_urls.py`, `apps/management/tests_strategy_api.py`,
`apps/management/verify_strategy_api.py`, this checkpoint.

Approved M-C1–M-C4 models/migration/evaluator/services/tests/checkpoints and
unrelated DEMO-02 file preserved. Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` preserved. Index empty;
no staging, commit or push.

## Deferred contract and deployment boundary

`impact/` is deliberately not exposed. Overview counts are evidence counts;
comparison is a simulation, and revenue uplift remains null. Real policy impact
requires independently approved selling-context/version lineage and outcome
definitions that distinguish submitted requests from realized sales. Do not infer
uplift or attribution from current legacy sales/request totals.

No policy is integrated with Guided Sale, Customer360 or existing signed contexts.
Publication currently changes only strategy persistence. Later integration must
bind fresh context version/snapshot and preserve old signed/pending/request state.

Persistent rollout requires separate owner authorization, backup/rollback plan,
reviewed full migration graph including management/0001, least-privilege strategy
and normal-session grants, role/security/readiness validation and approved source
deployment. Top-level service transactions are required; do not wrap these
commands with ATOMIC_REQUESTS or silently downgrade snapshot isolation. Existing
non-Demo reference-lock/deployment restrictions remain unchanged. Ordinary startup
never installs/repairs schema or grants. The deferred Demo launcher and Gate V2
must not be activated as an incidental part of management deployment.

No M-D1 blocker remains. STOP for owner review; no deployment is authorized here.
