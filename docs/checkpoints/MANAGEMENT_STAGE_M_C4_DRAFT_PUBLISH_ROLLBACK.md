# Stage M-C4 — Internal Strategy Draft, Publish and Rollback

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Authority: approved M-A2 contract and M-C1/C2/C3 foundations.
Status: isolated validation passed; NOT DEPLOYED. No endpoints, UI or selling-context integration.

## Internal command contract

All commands require an active manager, stable command UUID, exact expected
policy revision and an explicit database alias (default supported). They return
the existing `StrategyCommandResult(event, replayed)` with durable canonical
result evidence. No command is called from an existing application route.

- `create_strategy_draft(actor, command_uuid, expected_revision, config)` accepts
  exact typed V1 JSON. Normalizes rule order, rejects unknown fields, invalid
  integers/bounds, duplicate identities and nonexistent references. Product,
  brand and category overlaps remain legal; the existing evaluator applies
  specificity and explicit-zero override. Creates one immutable version and
  SAVE_DRAFT event, advances revision and updates only the draft pointer.
- Existing M-C3 capture/`create_strategy_comparison` performs explicit Preview.
  Preview creates immutable evidence and does not advance revision.
- `publish_strategy(actor, command_uuid, expected_revision, draft_version_id,
  comparison_id, accepted_comparison_digest)` requires the current exact draft,
  its SAVE_DRAFT evidence and an accepted comparison's **output_digest** (which
  also binds its input digest). Comparison must have the same active baseline,
  revision, candidate and source version, valid hashes and a matching PREVIEW
  command. Current publisher and comparison author must still be managers.
  Re-captures assignment/customer/salesperson/recommendation/product/target/
  promotion/pricing/inventory facts and recomputes the output. Any difference
  rejects publication and leaves the head unchanged. Success changes active
  pointer, clears draft pointer, increments revision once and appends one event.
- `recover_strategy_command(actor, command_uuid)` is read-only, actor-bound and
  returns the stored operation/result, or None if no success is committed.
  Absence never triggers an automatic command retry.

Missing active policy means explicit neutral configuration. No neutral version
is silently seeded, and saving a non-neutral draft never activates it. Initial
head creation occurs only within an explicit successful mutation transaction.

## Rollback is a newly previewed version

Rollback preserves the same Draft → Preview → explicit activation contract:

1. `prepare_strategy_rollback(..., target_version_id)` copies a previously
   PUBLISH/ROLLBACK-activated configuration into a NEW immutable draft with
   parent pointing to the target. `target_version_id=None` explicitly requests
   neutral configuration and a null parent. Unpublished historical targets fail.
   This SAVE_DRAFT command does not activate anything.
2. Capture/Preview this new draft through the existing M-C3 service.
3. `rollback_strategy(...)` accepts the same envelope as publish. Verifies the
   rollback preparation, historical target/configuration/parent and new draft's
   comparison, then activates it with an append-only ROLLBACK event.

The final activation uses the already NEW version created by preparation; it
does not reuse the old target's ID, mutate history or attach an old comparison
to a different version. Publish and rollback commands cannot be relabelled.
Each explicit command is atomic; the three-step operator workflow is not one
transaction. Failed/abandoned preparation leaves an inspectable inactive draft.

## Transactions, freshness and replay

Reuses M-C1 head row locking, direct revision CAS and event uniqueness. The shared
`run_snapshot_command` now hosts the existing M-C3 repeatable-read/recovery
boundary for all commands. Top-level transactions are required. A PostgreSQL
serialization/deadlock/UUID collision rolls back first; only a fresh read of an
already committed identical receipt can resolve it. Handlers are never rerun
automatically. Different intent/actor/operation conflicts. Replay precedes
current-revision/source validation but always rechecks current manager access.
Reconnect replay returns original event/result even after assignments, stock
or head state change; it does not perform a fresh publication.

Freshness is explicitly M-C3's single repeatable-read image, with the accepted
comparison's supplied Asia/Tehran evaluation date, not a new wall-clock default.
Already committed differences visible to that image fail. Changes committed
after the image was established do not retroactively alter it. No source-row
lock/reservation or current-at-commit stock guarantee is claimed. Policy CAS
still rejects concurrent policy changes. Later live integration must capture
fresh context facts and retain current Basket/Submit commercial validation.

Stored evidence now requires present, well-formed hashes before full_clean;
creation-time digest derivation cannot silently reconstruct missing historical
digests. Preview receipt, input document and deterministic output are checked
together. Privileged raw SQL remains an administrative trust boundary.

## Disposable validation

Reproducible focused selection:

```powershell
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_services
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_services --sqlite
```

Executed 114-test regression selection, then four additional evidence-integrity
tests separately, without repeating unchanged successful regressions:

| Backend | Passed | Failed/errors | Skipped |
| --- | ---: | ---: | ---: |
| PostgreSQL | 118 | 0 | 0 |
| In-memory SQLite | 105 | 0 | 13 PostgreSQL-only |

Selection includes 31 new M-C4 tests, M-C1 command/integrity/serialization/
concurrency, M-C2 pure and database parity, all M-C3 tests and unchanged engine
baseline regressions. PostgreSQL independent backend PIDs and forced overlapping
snapshots prove one winner for competing publication UUIDs, and exactly one
committed event with identical replay for concurrent matching commands.
Tests cover fresh role/assignment checks, reference changes, missing/rehashed
contradictory evidence, stale draft/revision/baseline, reconnect recovery,
rollback/new-neutral history and injected failure after CAS with full rollback.
All non-strategy model rows, including sessions, requests and historical evidence,
have identical digests across successful publication/rollback.

Runner creates verified UUID DB/OID/marker and independent owner, preview role
and publication runtime role on the isolated cluster. The publication role gets
only SELECT on required sources, INSERT on strategy records, UPDATE(revision,
active_version_id,draft_version_id) on head, and three sequence USAGE grants.
Preview-only role remains unchanged. Real publication-role commands succeed;
direct source/price/inventory writes, history UPDATE/DELETE and DDL fail. Missing
active-pointer permission fails closed without a partial event/head update.
These are disposable grants, not a production privilege deployment.

Applied unchanged 51-migration graph only to disposable DBs. Django checks and
migration drift pass. No M-C4 migration, JS changes or full suite. Python syntax
and scoped whitespace checks pass. Both disposable PostgreSQL databases and all
test roles were removed; persistent Demo all-user-table/sequence digest matched
before/after each run.

## Exact M-C4 files and preservation

Changed existing uncommitted source:
- `apps/management/strategy_persistence.py`
- `apps/management/strategy_comparisons.py`
- `apps/management/verify_strategy_foundation.py`

Added:
- `apps/management/strategy_services.py`
- `apps/management/tests_strategy_services.py`
- `apps/management/verify_strategy_services.py`
- `docs/checkpoints/MANAGEMENT_STAGE_M_C4_DRAFT_PUBLISH_ROLLBACK.md`

No model, migration, evaluator, pricing, Visit, Basket, Submit, recommendation
engine, UI, settings or launcher changes. Existing C1/C2/C3 documentation and
unrelated DEMO-02 document preserved. Original PostgreSQL never connected to;
persistent Demo accessed only through read-only preservation queries. No service
restart, Gate V2 activation, Prepare Day, reset, generation switch or credentials
change. Index remains empty; no staging, commit or push.

Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.

No M-C4 blocker remains. Separate approval is required for management APIs/CSRF
integration, UI, fresh signed selling-context policy binding, persistence/grant
deployment and activation. Existing signed contexts, pending commands, request
revisions, submitted snapshots and salesperson ordering remain unchanged.
