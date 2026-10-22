# Stage M-C3 — Authoritative Strategy Snapshots and Comparisons

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Authority: approved M-A2 contract and approved uncommitted M-C1/M-C2.
Status: isolated validation passed. No HTTP routes, publication, UI or selling
context integration; no deployment to persistent databases.

## Service contract

- `capture_strategy_snapshot(actor, customer_id, salesperson_id,
  proposed_version_id, expected_revision, evaluation_date)`: read-only, returns
  immutable `CapturedStrategyInputs` plus canonical source fingerprint.
- `evaluate_comparison(captured)`: pure active/proposed evaluation over the same
  frozen facts. A missing active version is explicitly neutral, not a new record.
- `create_strategy_comparison(..., command_uuid, accepted_source_fingerprint)`:
  explicit authorized PREVIEW command. Returns the M-C1 command result/event.
- `get_strategy_comparison(actor, comparison_id)`: authorized frozen evidence.
- `recover_strategy_comparison(actor, command_uuid)`: read-only committed-command
  lookup; returns original result plus comparison, or None when absent. No retry.

These are internal services, not API endpoints. Future HTTP integration must
provide standard session/CSRF protections and must not accept client-built facts.
All services use an explicit database alias; the test runner separately enforces
the disposable database's endpoint, role, OID and marker on each connection.

Fresh management role checks use a dedicated viewer hook and the existing
manager write hook. They do not call salesperson catalog authorization or
impersonate the selected employee. Current scope is one global active staff
management role. New captures require an active customer/salesperson and a real
active assignment covering the supplied date. Candidate must be the current
draft version; expected head revision and version configuration hashes must match.

## Authoritative sources

Capture retains active saved recommendation rows ordered by `(rank, pk)`, never
calls the engine, and keeps original IDs/scores/ranks/reasons/type/confidence and
explanations. Native JSON columns are canonical opaque JSON strings, preserving
legitimate engine floats without treating them as new scoring components.

The read set includes customer/grade, employee, assignment evidence, products,
brand/category identities, same-employee matching-scope targets, linked or
explicitly emphasized promotions and their product/grade links, inventory and
ProductDemoPrice rows. Global policy references outside the shortlist are fetched
for validation only; they cannot add candidates. Inactive/expired facts remain
available for qualification evidence. Each source collection is capped at 5,000
rows; excess fails rather than truncating. Queries are batched, not per-product.
Focused capture asserts at most 25 SQL statements including transaction setup.

The date is required as a Python date and explicitly labeled Asia/Tehran; no
implicit wall-clock default or Visit redating. It controls period qualification
over currently captured rows, not a reconstruction of past recommendation data.
Missing inventory is null/UNKNOWN; known sellable stock uses the existing
`max(available-reserved, 0)` rule. Missing price is unavailable, explicit zero is
available, fractional configuration is an error. Quotes call existing Pricing
Core's pure calculation against captured prices and grade, never legacy sales or
promotion discount values. Stored target actuals remain imported/snapshot facts;
no current achievement is inferred from requests.

Availability is explicitly scoped to **commercial quantity one**, not Visit or
mutation authorization. No Visit is fabricated; a positive annotation is not
permission to Add. Later salesperson integration must still enforce ownership,
Visit lifecycle, current quotes, stock and Basket rules. Inactive products remain
disabled audit evidence, not an expanded live recommendation catalog.

## Snapshot and persistence semantics

Read capture uses a top-level PostgreSQL REPEATABLE READ / READ ONLY transaction.
The command uses a top-level REPEATABLE READ transaction, then M-C1's policy-head
row lock and durable command boundary. Nested/externally managed transactions
are rejected rather than silently inheriting inconsistent isolation. SQLite
supports transactional/sequential checks; strong concurrency claims are PG-only.

Only the strategy head is explicitly row-locked. Reference sources are selected
from one MVCC image; no reference UPDATE grants or new locking capabilities are
needed. Input fingerprint validation refers to that image. A source commit after
the image was established does not retroactively invalidate a consistent frozen
simulation. A later new command captures new facts and rejects the old accepted
fingerprint. This is not an inventory reservation or a claim of current-at-commit
commercial availability. Concurrent policy revision changes fail closed; no
automatic mutation retry occurs.

The immutable input document binds source version `STRATEGY_CAPTURE_V1`, logical
database identity (no credentials), timezone/date, policy revision and version
IDs/configurations, source rows/fingerprints, one shared evaluator fact set,
pricing policy and quotes. No volatile capture timestamp enters the semantic
fingerprint. The M-C1 comparison additionally binds customer/salesperson/author,
version FKs and its own input/output digests. Created timestamp is normal metadata.

Before is the active policy's evaluated order; after is the proposed policy's
evaluated order. Both retain the same saved baseline and sources. Outputs include
Persian explanations, contribution evidence, before/after ranks and movements,
`simulation_only=true` and unavailable revenue uplift (null). No causal KPI is
fabricated.

A successful new command inserts exactly one StrategyComparison and one PREVIEW
StrategyPolicyEvent. It does not change head revision/pointers or create versions.
The receipt stores comparison ID, original policy revision, source fingerprint
and input/output digests. Failure rolls back both records.

Identical UUID/intent returns original committed evidence even after source,
assignment or head changes; replay is audit retrieval, not a new comparison.
Current manager permission is always checked. Changed intent/actor conflicts.
For a concurrent identical preview, both RR images can predate the first receipt
because preview does not update the head. On the specific UUID uniqueness
collision (or a rolled-back concurrency conflict), rollback is followed by a
fresh read-only receipt lookup. Matching committed success replays; a conflicting
intent fails. No handler/POST is automatically repeated. Absent receipt never
means permission to adopt a partial result.

Historical get/recovery validate stored hashes without re-reading live source
facts, repairing history or requiring the old assignment to remain active.
Current global managers can inspect history; UUID recovery remains actor-bound.
Hash checks detect contradictory evidence; privileged raw SQL remains the
administrative trust boundary already documented in M-C1.

## Disposable validation and least privilege

```powershell
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_comparisons
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_comparisons --sqlite
```

The existing identity-guarded runner optionally creates a separate LOGIN runtime
role only in the disposable environment. Its standard M-C1/M-C2 defaults remain
unchanged. The independent runtime gets:

| Object | Runtime permissions |
| --- | --- |
| Required business reference tables and auth user | SELECT |
| Strategy versions | SELECT |
| Strategy head | SELECT, UPDATE(revision) for row-lock admission |
| Comparison and event | SELECT, INSERT |
| Their two identity sequences | USAGE |
| Public schema | USAGE only |

No ownership, SUPERUSER, CREATEDB, CREATEROLE, BYPASSRLS, source UPDATE,
append-only UPDATE/DELETE or active/draft-pointer UPDATE grants. Grants affect
only the disposable DB. No persistent grant or capability changes.

Final focused results: **PostgreSQL 85 passed, 0 failures/errors/skips**;
**SQLite 77 passed, 8 PostgreSQL-only skips, 0 failures/errors**. Selection is
21 new snapshot/comparison tests, 29 focused C1 tests, 31 pure evaluator tests and
4 unchanged engine regressions. Existing migration round-trip was not repeated;
the unchanged 51-migration graph was applied only to disposable databases.

Tests cover same-fact evaluation, neutral/non-neutral active parity, source
immutability, price/stock distinctions, assignment changes, authorization,
frozen hash integrity, replay after physical reconnect, stale revisions/inputs,
rollback, and read-only recovery. Independent PostgreSQL connections/backend PIDs prove one MVCC
image during concurrent source updates, two previews blocked on the head before
either commits, canonical collision replay, and concurrent policy-change rejection.
Actual separate-runtime login succeeds for capture/create/read/replay/recovery;
direct reference/price edits, history mutations, publication-pointer UPDATE and
DDL fail. Django check and migration drift passed; no full suite or JS changes.

## Preservation and next boundary

Persistent Demo all-user-table and sequence digests matched before/after.
Disposable DB and both test roles were removed. Original PostgreSQL was never
connected to. No persistent schema/data writes, service restart, Gate V2,
Prepare Day, reset, promotion, generation switch or credential rotation.
No M-C3 migration; M-C1/M-C2 models, evaluator, persistence, serialization,
migration, tests and checkpoints remain unchanged. Only the access module and
disposable runner were extended alongside new C3 services/tests/docs.

Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 planning is preserved; index remains empty. No commit/push.

No C3 blocker remains. Next tasks require separate approval: management APIs,
policy publication/freshness rules, UI and fresh selling-context integration.
Persistent Demo still lacks rich target/promotion fixtures; no such data was
inserted there. Existing production/Demo deployment restrictions remain in force.
