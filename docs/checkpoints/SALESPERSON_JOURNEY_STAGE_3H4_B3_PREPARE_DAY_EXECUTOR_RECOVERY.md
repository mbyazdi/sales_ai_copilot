# Stage 3H4-B3 — Isolated Prepare Day executor and recovery

2026-10-16. `fast-track`, committed V3.0.22 baseline
`8bdb2ca6150a27d217eade7bfce8dff3768a4694`. Preserves uncommitted H4-B1/B2.
Implementation and write validation **only in disposable PostgreSQL**.
Persistent deployment/execution is NOT approved. No reset, generation switch,
current-day preparation, C0005 completion or production change occurred.

## Contract and scope

`scripts/demo/prepare_day.py` reuses the H4-A/B2-B1 policy, Gate V2, protected
generation/fixture verification and exact V1 capability/ACL inspection. A signed
plan binds source hashes, exact container/endpoint/database/OID/marker, generation,
owner/runtime, fixture manifest, Tehran planning day/target, SP001, assignments,
every Visit/request identity/state/revision and all public-row/sequence digests.
The plan is optimistic read-only evidence; it is NOT a substitute for locked
transactional revalidation. An unrelated state change conservatively invalidates it.

Only future missing Visits may be inserted, all PLANNED. An older IN_PROGRESS
Visit for the same customer/salesperson blocks the entire five-customer batch.
Older PLANNED/COMPLETED rows are retained. Registered open target-day Visits are
reused; closed/consumed, duplicate, foreign or unregistered target rows block.
Nothing is redated, reopened, completed, deleted or commercially recalculated.

There is no persistent apply/recovery CLI or installer. `make_plan` and
`execute_disposable` require the exact independently marked disposable database,
profile/OID/roles, dedicated Demo cluster and protected state. The existing
`plan.py --dry-run` remains diagnostic and cannot authorize execution. The runner
creates synthetic source-defined fixtures with independent TEST passwords; no
production rows/password hashes or persistent Demo scenarios are copied.

## Transaction and journal protocol

1. Operator retains the ORIGINAL signed plan/fingerprint and stable UUID and
   supplies the exact `PREPARE DEMO DAY <db> OID <oid> GENERATION <uuid> OP <uuid>
   PLAN <sha>` confirmation. Wrong source/identity/intent/signature fails closed.
2. Retain V2's session-level owner lease. In one transaction insert the signed
   control operation plus PREPARING day intent and commit PENDING. The operation
   and final gate audit use purpose `PREPARE_DAY_V1`, distinct from gate-only work.
3. Acquire exclusive V2 request admission on that same connection. All admitted
   request transactions, including session persistence, must drain. Recheck
   generation, ownership, live lease, signatures, fixture/capability/schema
   identity and complete commercial before-state. Lock SP → sorted customers →
   assignments → Visits deterministically; re-evaluate the exact policy/write set.
4. Reserve only the required Visit sequence IDs and atomically journal their
   signed ALLOCATED identity/high-water state. PENDING and owner lease remain.
   PostgreSQL sequences are nontransactional: this separate reservation makes
   a proven committed allocation reusable without another nextval.
5. Reacquire exclusive request admission with the retained owner lease (PENDING
   prevents new admissions between phases). Repeat full checks. Insert ONLY the
   reserved missing PLANNED Visits. Verify every old Visit, all other public
   tables and every sequence against the authorized before/allocation state.
6. Commit those Visit rows, signed COMMITTED canonical result, signed gate audit
   and conditional ACTIVE release in ONE database transaction. Recheck Tehran
   day and generation before commit. Failure rolls back rows/result/release.
   Owner disconnect releases the lifetime lease; uncertain PENDING is not cleared.
7. Publish the signed canonical result under protected
   `fixtures/prepared-days/<operation-uuid>.json`: exclusive temporary write,
   fsync and exclusive atomic hard-link publication. Existing bytes must match;
   never overwrite/adopt another file. PostgreSQL is authoritative; publication
   is a recoverable copy, not proof of commit or permission to unlock.

The owner-only control schema adds `prepared_days` and
`preparation_recoveries` in disposable provisioning only. Runtime cannot read or
write them. The day identity has a partial unique constraint on generation/date/
salesperson for committed insertion ownership; operation UUID is unique and
references original gate evidence. No Django migration, domain model or business
API changes. Initial fixture manifest and SalesRequest receipts are untouched.

## Recovery boundaries

- Identical committed operation + ORIGINAL signed intent verifies and replays
  its stored canonical result across processes, with no row/sequence mutation.
  Missing publication can be recreated from the verified DB journal. Conflicting
  intent or tampered existing publication is rejected. Replay cannot release a
  later unrelated pending operation.
- Uncommitted PREPARING/ALLOCATED continuation requires explicit
  `RECOVER DEMO DAY ...` confirmation. Acquire the owner lease (live owner
  refuses) AND drained exclusive request admission; validate original operation,
  plan, generation/source/identity and journal. Atomically record a signed claim
  and CAS backend ownership. Claims form one HMAC-verified predecessor chain
  rooted in original operation evidence; missing, orphaned or forked claims and
  unsigned backend ownership refuse. The committed result binds the chain head.
  Then revalidate all public evidence and resume only
  the proven phase/IDs. Never infer abandonment from PID/age or replace a plan.
- Crash before allocation can resume only if original state still matches.
  Crash after committed allocation, during insertion or before final commit can
  reuse the signed IDs after rollback/lease loss. Crash after commit/before or
  during publication replays the canonical committed result without reinsertion.
- Crash after nextval but BEFORE allocation evidence commits leaves unexplained
  sequence advancement. Recovery deliberately refuses and retains PENDING for
  independent review. No setval/reset, guessed reservation or destructive rollback.
- Changed assignments/data/source, a midnight rollover, missing/tampered DB
  evidence or uncertain owner/transaction outcome also remains fenced. This task
  does not provide an automatic abort/clear/rebaseline command for such cases.
- Gate-only `exclusive`/`recover_disposable` cannot release Prepare Day work;
  explicit purpose checks and journal reconciliation prevent that escape route.

## Validation and preservation

Focused command:

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/verify_generation_postgres.py --prepare-day
```

Each run verifies exact disposable identity before
migrations/writes, uses independent least-privilege runtime/owner/capability roles,
and removes only its own DB/roles after all connections close. Real Django
session/CSRF/generation checks are used for API races, never force_login.

Per-operation preservation verifies full public table digests, original Visit
rows, authorized Visit IDs and exact sequence state. Whole-run preservation
compares persistent Demo and original PostgreSQL read-only data/schema evidence,
generation, sessions, protected credential/fixture files, original SQLite,
unrelated DEMO-02, Git HEAD/index and original stash.

### Final executed evidence

| Selection | Pass / failure / error / skip | Disposable DB (removed) |
| --- | --- | --- |
| Prepare Day, real-session races, crash/publication/recovery, policy and ACL drift | 21 / 0 / 0 / 0 | `test_stage3h3b3_0640b12e196149c58eda2608d6a0b491`, OID 52643 |
| All 13 Gate B1 + all 13 B2 recovery + capability-registry + Feedback/Submit/Completion/pending-wire regressions | 30 / 0 / 0 / 0 | `test_stage3h3b3_0a39fa36588f42acbdf6025ac11ab791`, OID 54485 |
| Generation-client JS | 7 / 0 / 0 / 0 | No DB |

Both PostgreSQL selections: Django check clean; migration drift clean; 50/50
migrations only in disposable DBs; 158 mutating routes inventoried/covered by
pending denial tests. Independent owner/runtime/capability roles and DBs removed.
Python AST checks: 7/7; changed-file whitespace checks: 9/9; JS syntax and
`git diff --check`: clean. No full regression suite.

Protected `results.json`, `cleanup.json`, signed `before.json` and `after.json`:

- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-e52d44329a8c41d3aed6531539ea5149`
- `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-406aefc13a4a41648f68b60a9dd1fbca`

Development runs exposed only test-harness setup/expectation errors: assignment
drift fails before PENDING (ACTIVE is correct); fixture Visit INSERT requires
the disposable owner, never extra runtime grants; generation mismatch raises
its explicit exception type. Corrected and final selections above passed.
One mistyped regression-selection name was rejected before running tests; its
disposable setup was cleaned up, then exact method names were enumerated from
source. No application permissions were loosened for test fixtures.

Evidence includes real authenticated Start/Submit/Completion transactions paused
before outer commit: preparation cannot enter until they drain; their committed
changes invalidate the plan and leave PENDING, with zero prepared Visits.
Additional cases prove exact five-row insertion/no-op/replay, original history
and sessions unchanged, retained DRAFT and SUBMITTED/acknowledgement preservation,
no PURCHASED feedback, parent/child process recovery, live-owner refusal,
interrupted claims/publication, missing/tampered evidence and sequence-gap refusal.

Persistent read-only readiness: NO_GO as expected (no V2 objects, old listener
PID 37632 unproven); generation still `6ae05c63-b9a3-4e85-a469-4643d3f76a27`.
REFERENCE_LOCKS_V1 source SQL remains
`7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.
Original SQLite remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` unchanged; index empty.
No staging, commit, push, persistent write/DDL/restart or original SQLite write.
Final SELECT-only verification against the original signed regression baseline,
after the readiness/health inspection: `READ_ONLY_PRESERVATION_VERIFIED`.

Files changed by B3 (existing B1/B2 and unrelated files otherwise retained):

- `scripts/demo/prepare_day.py` (new)
- `scripts/demo/tests_prepare_day.py` (new)
- `scripts/demo/maintenance_gate.py`
- `scripts/demo/gate_recovery.py`
- `scripts/demo/tests_maintenance_gate.py`
- `scripts/demo/verify_generation_postgres.py`
- `scripts/demo/lock_capabilities.py` (explicit runtime role for read-only inspection)
- `scripts/demo/README.md`
- This checkpoint.

## Deployment remains blocked

Persistent Demo still has no V2 admission/journal objects and its existing
listener is not proven to run the new gate. No service was restarted or deployed.
Before separately authorized deployment: protected backup/recovery plan; complete
worker/connection inventory and proven quiescence; explicit V2/control-journal
DDL/ACL review; source/SQL/fixture/generation readiness; all-worker restart proof;
separate approval of actual target-day plan/UUID/confirmation and uncertain-outcome
operator procedure. Original PostgreSQL deployment restrictions remain unchanged.
No normal startup installs SQL objects, seeds, prepares dates or recovers PENDING.
