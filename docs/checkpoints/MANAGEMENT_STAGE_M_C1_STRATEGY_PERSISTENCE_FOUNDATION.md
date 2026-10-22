# Stage M-C1 — Versioned Strategy Persistence Foundation

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Status: implemented and validated in disposable databases; NOT DEPLOYED.
Authority: owner-approved M-A2 contract in the conversation. No M-A1/M-A2
repository checkpoint exists; this records the persistence slice, not a new
scoring decision.

## Boundary

Foundation in the existing management app only. No new routes, policy evaluator,
publication API, UI, recommendation rebuild, pricing change or selling-context
activation. Existing views/settings/scripts and all salesperson services remain
unchanged. One global policy; current managers are authenticated active staff.
Separate view/manage hooks leave room for future role separation.

## Records and integrity

- `StrategyPolicy`: database-enforced singleton PK 1, nonnegative revision,
  nullable protected active/draft version pointers. No row is seeded by migration
  or GET. Ordinary save/update/delete of an existing head is blocked.
- `StrategyPolicyVersion`: protected policy, author and optional parent; immutable
  typed configuration, algorithm ID, SHA256 and timestamp. Parent cannot be self.
  Equal configurations may have different version IDs (needed for rollback).
- `StrategyComparison`: protected policy, candidate/baseline versions, customer,
  salesperson and author; date, source version, frozen input/output JSON and
  digests. Null baseline means neutral policy. A real active assignment covering
  the comparison date is required at creation. Input digest binds identities,
  versions, date and source; output digest also binds the input digest.
- `StrategyPolicyEvent`: protected actor/policy/version/optional comparison,
  command UUID, operation, expected/applied revision, canonical intent/hash,
  canonical successful result and timestamp. Unique policy+command UUID; unique
  non-preview write revision; operation/revision-step checks; comparison required
  for preview/publish/rollback. Comparison candidate must match event version.

All evidence rejects instance updates/deletes, QuerySet update/delete, bulk
creation/update, base-manager bypass and supplied-PK overwrite through normal
ORM boundaries. Historical role/assignment changes and subsequent head revisions
do not invalidate recorded evidence. Creation validates current manager rights,
scope references and consistent policy ownership. References use PROTECT.
Privileged raw SQL remains an administrative trust boundary: no new triggers,
runtime grants or database capability objects are introduced.

## Canonical configuration and evidence

Algorithm: `SAVED_RANK_OVERLAY_V1`. Configuration schema:

```json
{
  "schema_version": 1,
  "priority_rules": [{"scope_type": "PRODUCT", "scope_id": 1, "points": 20}],
  "target_weight": 0,
  "promotion_rules": []
}
```

Priority scopes are PRODUCT/BRAND/CATEGORY, integer points 0–20. Promotion rules
use `promotion_id` and integer points 0–5; target weight is integer 0–5. Reject
unknown fields, bool-as-int, duplicate scopes and missing reference records.
Rule lists are sorted by typed identity before configuration hashing. The hash
includes the algorithm version. Explicit zero is retained. Specificity,
non-stacking, total cap 30 and actual ranking are evaluator work, not implemented
in this persistence task.

Canonical JSON uses UTF-8, sorted object keys and exact normalized Decimal
strings; meaningful list order is preserved. Aware timestamps become UTC with
six fractional digits; naive times, floats and non-finite decimals are rejected.
Existing supplied digests must match, never silently replace contradictory hashes.
Future command handlers normalize typed config before constructing semantic
intent; the generic serializer does not reorder arbitrary evidence arrays.

## Transaction primitive

`run_strategy_command` is internal, with a trusted handler returning
`StrategyEffect`; it is not a complete preview/publication service. Future
handlers must implement accepted-preview, frozen-input freshness and other
operation-specific rules before it can be exposed by any route.

1. Validate UUID, operation, intent and expected revision; re-read manager rights.
2. Inside one atomic transaction, initialize only the constant empty singleton
   if absent (DB conflict arbitration), then lock its row on PostgreSQL.
3. Resolve prior successful UUID before stale-revision checking. Same actor and
   intent replay the stored event/result without handler execution. Changed
   actor/operation/revision/intent conflicts.
4. Invoke handler, validate persisted version/comparison identity, CAS the actual
   head row by PK and expected revision, and append successful event atomically.
   SAVE_DRAFT updates the draft pointer; other write operations have an active
   pointer primitive. PREVIEW records evidence without changing revision/pointers.
5. Any exception rolls back handler records, pointer/revision changes and event,
   including first-command singleton creation. No automatic retry.

Historical applied revisions are immutable; replay never substitutes the latest
head state. PostgreSQL provides the tested concurrent-writer contract; SQLite
supports model/migration and sequential command compatibility only.

## Migration and validation

`apps/management/migrations/0001_initial.py`: additive CreateModel/AddField/
AddConstraint only. No data migration or edits to existing migrations. Full graph
is now 51 migrations; applied only to disposable PostgreSQL/in-memory SQLite.

Focused commands:

```powershell
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_foundation
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_foundation --sqlite
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_foundation --checks
```

The PostgreSQL runner verifies the dedicated container, creates a UUID-named test
DB and independent non-superuser owner, and checks endpoint/role/OID/database
marker on each Django connection. Cleanup rechecks OID/marker before DROP of
only that test DB/role. Credentials stay in process memory. Persistent Demo
connections are read-only preservation checks, never Django test connections.

Results: PostgreSQL **30 passed, 0 failed/errors/skips**; SQLite **27 passed,
3 PostgreSQL-only skips, 0 failed/errors**. Includes migration round-trip with
legacy row preservation, CAS SQL shape, two independent PostgreSQL connections,
one-winner revision race, identical-command replay race and concurrent first use.
Initial constraint-test savepoint handling was corrected before the final pass.
Django check and migration drift passed. No JS changed; no full suite run.

## Preservation and next boundary

Persistent Demo all-user-table and sequence digests matched before/after; test
resources were removed. Original PostgreSQL was never connected to. No service
restart, Gate activation, generation change, Prepare Day or credential rotation.
Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` is preserved.

Future deployment needs explicit migration authorization and review of runtime
grants and pinned Demo migration/profile fingerprints. Do not run a new launcher
against the persistent Demo as part of this task. Existing loaded services are
unchanged; no new strategy table is queried by existing business routes.
Next slices: pure evaluator, authoritative snapshot capture, preview/publication
services/APIs, fresh-context lineage, and management UI, each separately approved.
