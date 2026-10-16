# Stage 3H4-B2 — Maintenance recovery and deployment readiness

2026-10-16. `fast-track`, committed V3.0.22 baseline
`8bdb2ca6150a27d217eade7bfce8dff3768a4694`. Preserves uncommitted B1.
Implementation/validation ONLY in disposable PostgreSQL. Owner review pending.
**No persistent installation/recovery/restart or Prepare Day is authorized.**

## Reviewed gap and scope

B1 safely drained admitted requests with a shared/exclusive transaction lock,
but its PENDING row contained only operation UUID/backend PID and had no durable
outcome evidence. An owner could be alive and idle before exclusivity or after a
drain timeout; absence of the request lock did not prove abandonment. PID/age or
filesystem flags alone cannot authorize recovery.

Current source requires **DEMO_MAINTENANCE_V2**, not V1. V2 retains B1's outer
request transaction/session protection and adds an independent session-level
owner lifetime lock, HMAC-signed operation evidence, and signed RELEASED/RECOVERED
results. V1/missing objects fail closed; no adoption, migration or evidence
backfill is provided. These extra control tables are outside public/domain tables
and Django's unchanged 50-migration graph.

Only disposable provisioning creates `sales_ai_demo_control.admission`,
`operations`, and `results`. Existing Demo owner owns them; runtime has schema
USAGE and SELECT on admission only. Runtime cannot write control/evidence/audit
rows. Signing uses the protected control key with a separate HMAC purpose salt;
only fresh disposable tests generate an independent key. Persistent keys are
never rotated/copied into Git or disclosed.

## State machine and transaction proof

1. **ACTIVE:** no pending operation. Owner verifies exact DB/endpoint/OID/marker,
   role, source/generation, then acquires the owner-lifetime PostgreSQL session
   lock `(89005433,3402)` before announcement. It remains held across commits,
   drain waits and timeouts until clean release or actual disconnection.
2. **PENDING:** signed operation evidence and its digest are inserted/recorded
   atomically with the conditional PENDING transition. Evidence binds operation,
   owner/runtime, database/OID/container/generation, source hashes, backend PID,
   gate-only purpose and full public-row/sequence digest. No duplicate operation
   evidence is overwritten. An uncertain announcement closes its connection;
   any committed PENDING remains durable and requires inspection.
3. **EXCLUSIVE (live lock state):** owner retains the lifetime lease and acquires
   B1's request lock `(89005433,3401)` exclusively on the same business connection.
   All admitted requests must commit/roll back first. Revalidate ownership, live
   lease, evidence, generation and source before entering the protected section.
4. **RELEASED:** clean gate-only work verifies unchanged public data/sequences,
   inserts a signed result and clears PENDING in that same transaction. Release
   the session owner lease only after commit. Lasting business writes in this
   gate-only section cause rollback; Prepare Day requires a later explicit
   write-set/outcome contract, not reuse of this narrow purpose.
5. **ABANDONED/UNCERTAIN PENDING:** owner failure never clears the committed row.
   A recovery command must independently acquire BOTH exclusive owner admission
   and exclusive request admission, without terminating/waiting out a live owner.
   This proves no conforming owner/request transaction can still commit under the
   gate. PID is corroborating identity only; it is not the abandonment proof.
6. **RECOVERED:** under both transaction locks and a control-row lock, validate
   signed evidence and current generation, require the exact approved operation
   digest, and reconcile the full public-row/sequence baseline. Insert the signed
   recovery result and CAS PENDING to ACTIVE in one PostgreSQL transaction.
   A crash before commit rolls back both. A crash after commit is resolved by
   reading the durable signed result; never infer outcome from a lost response.

The owner lock serializes competing owners/recoveries; the request lock drains
protected work. Both remain retained until commit/rollback. A live idle owner,
owner waiting for drain, or owner after timeout still holds its lifetime lock:
recovery refuses. Worker loss rolls back its protected connection before its lock
is released. Pending survives a fresh Django process, application restart and DB
restart; sessions/generation/key identities are not rotated.

### Conservative recovery boundary

Evidence is captured at announcement. If previously admitted work subsequently
commits, that legitimate change may make the baseline differ. Recovery then
**refuses**, preserves PENDING and requires independent outcome review. Never
recapture/sign a replacement baseline or reset sequences to force success.
Changed data, sequence high-water state, source, missing key/evidence, tampered
signature, unknown identity or contradictory results are not auto-recoverable.
V2 does not claim to reconcile these uncertainties.

## Operator workflow (contract, NOT persistent execution authorization)

1. Verify the exact dedicated container, endpoint `127.0.0.1:5433`, database/OID,
   owner-controlled marker, generation ACTIVE, V2 ownership/grants/source and
   complete all-worker gate deployment. Original PostgreSQL is never a target.
2. Inspect the pending operation and its ORIGINAL signed evidence. Verify the
   protected key and original source. Keep evidence and business/sequence state;
   never terminate a backend, forge evidence or release by elapsed time/PID.
3. Record a stable recovery UUID and confirm the exact phrase:
   `RECOVER DEMO GATE <database> OID <oid> GENERATION <generation> OP <operation> EVIDENCE <sha256>`.
   The owner role, operation, source and evidence digest must all match.
4. Attempt the narrow recovery once. Live owner/request, ambiguity or mismatched
   baseline means STOP. No automatic wait/retry/takeover, data change, reset,
   generation switch or business correction follows.
5. On uncertain response, inspect the signed result read-only. Identical recovery
   UUID/intent returns the original result; a different command conflicts. Replay
   may not unlock a subsequent pending operation. Results/evidence are separate
   from SalesRequest receipts and submission idempotency.
6. After proven recovery, verify ACTIVE, signed audit, unchanged public table and
   sequence digests, generation and sessions before any business traffic resumes.

`gate_recovery.recover_disposable` enforces an exact disposable identity/OID/
marker/role/endpoint boundary. **No persistent recovery CLI or installer exists.**
The audit/control records here are maintenance evidence, not a Prepare Day journal.

## Controlled deployment prerequisites (future separate approval)

1. Approve a dedicated-Demo-only installation/recovery package and exact reviewed
   source/grant matrix; capture protected backup/rollback and public/control state.
2. Inventory EVERY Demo app worker/process/listener and DB connection. Quiesce
   all old workers and prove they have exited and their DB transactions ended.
   B1's daemon-thread listener stop alone is not proof of drain. Unknown processes
   or runtime connections block deployment; do not force-kill unrelated services.
3. Install V2 control/evidence objects explicitly through the independent Demo
   maintenance role, with narrowly reviewed grants and the existing protected key.
   No ordinary startup installation, business-row write, fixture change or Django
   migration. Existing V1/PENDING/unknown objects stop for review, never upgrade
   by clearing state. Reconcile ownership, objects, grants, data and sequences.
4. Start every approved worker with the reviewed build/profile. Startup verifies
   only; missing/incompatible/PENDING gate blocks serving. Worker health captures
   version and loaded source hashes, not newly edited file bytes. Compare exact
   process inventory, endpoint/marker/generation and signatures for EVERY worker.
   One good health response cannot certify all workers or dormant old processes.
5. Independently validate full worker coverage, no old reconnect-capable workers,
   runtime permissions, CSRF/session/generation behavior and transaction fencing
   before authorizing traffic. Runtime write-fencing or credential changes, if
   needed for rollout, require separate explicit owner approval; none occurs here.
6. Preserve current generation, credentials, fixtures, sessions and historical
   Visits. This approval would not authorize Prepare Day, C0005 completion, reset,
   candidate promotion or original PostgreSQL deployment.

Read-only inspection:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/gate_readiness.py
```

NO_GO exits 2. The inspector never authorizes execution or attests to all workers.
Existing Demo read-only inspection confirms: 50 migrations, valid fixture/capability
prerequisites, same ACTIVE generation and listener PID 37632; gate missing and
listener V2 evidence unproven. **Deployment remains NO-GO, intentionally.**

### Rollback / interruption

Before installation, retain exact approved build/profile/grants/evidence and a
verified backup. If installation or rollout is uncertain, keep Demo mutations
blocked and inspect exact committed objects/state; no automatic retry, DROP,
CASCADE, data restore or schema repair. Never remove gate objects while dependent
workers run or launch an old ungated build merely to bypass PENDING. Stop and
verify all affected workers/transactions first. A return to pre-gate source needs
separate approval and a matched runtime/grant/readiness contract. Preserve the
control/evidence objects and all business history while investigating. Recovery
cannot settle a changed baseline; independent reconciliation is required.

## Focused validation and preservation

Initial focused PostgreSQL run: 58 methods, 56 passed, two test-fixture failures.
Both used 41-character session keys against Django's 40-character column, before
their race assertions. Corrected only those fixture keys and improved child EOF
diagnostics. Existing 48 B1/domain/security methods passed in that run.

Final affected run: **20/20 passed, zero failures/errors/skips**: all 13 B2 tests
plus seven directly affected B1 process/race tests. Covers normal release, live
owner refusal before/after exclusivity, owner death, active requests, drain timeout,
same-command replay/conflict, competing/interrupted recovery, fresh app processes
remaining blocked, tampered/missing/stale evidence/key/source/identity, changed
baseline refusal, runtime audit-write denial, loaded-worker evidence and rollback
of disallowed gate-only business writes. Full business/sequence digests match
around successful recovery. No automatic recovery or business corrections.

Evidence: protected `reports/b2b3-7ec7c9d2dea1492bb61de7b198425806`; initial run
`reports/b2b3-fa64dba143a94312a51cfd682eda1e23`, under
`D:\SalesAI-Demo\sales_ai_copilot\`. Both disposable databases, their independent
owner/runtime roles and capability owners were removed after exact-identity checks.
Django check and migration drift passed in both isolated runs; no full suite or JS
changes. Python syntax/whitespace checks are part of final closeout.

No persistent Demo/production DDL, writes, restart, generation switch, sessions,
credentials or original SQLite change. Before/after persistent inventories agree.
SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` and unrelated files
preserved; no staging, commit or push. B1 work is retained and extended, not reset.
