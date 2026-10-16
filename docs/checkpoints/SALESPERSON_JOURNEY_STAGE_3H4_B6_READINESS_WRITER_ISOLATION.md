# Stage 3H4-B6 — Control-bundle readiness and isolated writer retirement

2026-10-16. Branch `fast-track`, committed V3.0.22 remains
`8bdb2ca6150a27d217eade7bfce8dff3768a4694`; fetched origin matches. No staging,
commit, push or persistent deployment. B1–B5 and unrelated planning retained.

**GO for controlled rollout design; NO-GO for persistent deployment.** The
persistent Demo is still running the previous listener and has no Gate V2 schema.
Original PostgreSQL deployment remains NOT APPROVED.

## Recovery and exact B6 source boundary

Recovered one partial, untracked `control_bundle.py` draft. It had no completed
contract JSON, startup integration, B6 tests or successful B6 validation report.
The existing B1/B2/B3 implementation and B4/B5 findings were reused, not rewritten.

Files added/changed by B6 only (earlier changes in shared files retained):

- `scripts/demo/control_bundle.py` — shared SELECT-only inspector.
- `scripts/demo/control_bundle_v1.json` — reviewed PostgreSQL 17 catalog contract.
- `scripts/demo/maintenance_gate.py` — startup delegates to complete inspector.
- `scripts/demo/gate_readiness.py` — same inspector and loaded worker evidence.
- `scripts/demo/prepare_day.py` — same owner-side preflight; loaded-source hash.
- `scripts/demo/verify_generation_postgres.py` — explicit B6 selection; disposable
  environments always receive the complete five-table bundle.
- `scripts/demo/tests_control_bundle.py` — six focused real-PostgreSQL tests.
- `scripts/demo/README.md` — contract, trust boundary and future rollout conditions.
- This checkpoint.

No business service, application view, model, migration, JS, production setting or
persistent profile/credential was changed. Prior `demo.py`, `generation.py`,
`lock_capabilities.py`, B1/B2/B3 tests/checkpoints and DEMO-02 remain preserved.

## Shared readiness contract

Version `H4_CONTROL_SCHEMA_V2_PREPARE_DAY_V1`: admission, operations, results,
prepared_days and preparation_recoveries. The repository-owned JSON describes
the reviewed existing disposable DDL, not a catalog snapshot accepted from the
target being checked. No historical private report or ignored helper is needed.
SHA256: `ee02a1439c026c7f4ef03808f20020ca167cc6b5b34a6a6026eedfb1eacc9b76`.

The inspector resolves current qualified identities without cross-database OID
assumptions; compares columns/types/nullability/defaults, relation kinds/RLS flags,
13 PK/FK/UNIQUE/CHECK definitions and seven indexes including the partial unique
day identity; rejects unexpected relations, user triggers, rules, inheritance and
functions. It checks schema/table ownership, exact schema/table ACL grantees and
grant options, column grants, effective runtime rights, elevated runtime flags
and memberships. Private journal contents remain unreadable by runtime.

Database name/OID, endpoint, authenticated role, marker, isolation and singleton
generation/version use existing identity validation. Startup/Prepare Day/operator
callers retain protected generation/fixture/capability validation. Loaded gate,
recovery, Prepare Day, inspector and JSON fingerprints cannot bless changed files
underneath a worker. Health reports loaded evidence, not an all-worker guarantee.
This is a source/version contract, not protection against a trusted source editor
or database owner intentionally replacing the entire contract.

Normal startup requires ACTIVE. Operator inspection may describe PENDING but
does not authorize serving, recovery or clearing it. Missing/incompatible objects,
unsafe ACLs or source mismatches fail closed. All inspector statements are SELECT;
tests execute it in a real read-only transaction. No startup DDL/repair/seed exists.
The application admission/locking and signed recovery protocols are unchanged.
PostgreSQL-major/catalog rendering changes require contract review, not automatic
acceptance of a new target baseline.

## Disposable role and existing-connection proof

The runner's newly created `sa_b3_runtime_<uuid>` is the independent V2 runtime;
`sa_b3_owner_<uuid>` is maintenance owner. The test creates separate
`sa_h4b6_legacy_<uuid>` and `sa_h4b6_other_<uuid>` principals and a canary database.
No existing Demo credential or role is renamed, rotated, disabled or terminated.

| Surface | Test legacy before retirement | V2 runtime | Retired legacy |
| --- | --- | --- | --- |
| Public reads | SELECT | SELECT | No new authority restored |
| Visit/request/line | Existing reviewed operational rights | Same reviewed rights | Table/column DML revoked |
| Sessions / auth | Session I/U/D; auth UPDATE(last_login,password) | Same; normal Django sessions tested | DML and column grants revoked |
| Append-only tables | INSERT only | INSERT only | INSERT revoked |
| Reference data/prices | No direct UPDATE | No direct UPDATE | No direct DML |
| Lock capabilities | Schema USAGE/function EXECUTE | Existing restricted capabilities | EXECUTE revoked |
| Sequences | Required USAGE | Required USAGE | Revoked |
| Control schema | None | USAGE; SELECT admission only | None |
| DDL/elevated rights | None | None; no memberships | None; LOGIN retired |

The legacy child opens a real independent backend and inserts an uncommitted
session row. NOLOGIN plus CONNECT, table/column DML, sequence and capability
revocation prevents reconnect but leaves that exact existing backend alive.
After matching database OID/name, role, backend PID AND backend start, the test
terminates ONLY that new TEST backend. The child confirms its connection died;
zero legacy backends/prepared transactions remain, its uncommitted insert is
absent and the full public business/sequence digest is unchanged.

TEST-only LOGIN/CONNECT restoration then proves the old credential still cannot
DELETE because DML remains revoked. LOGIN is retired again before cleanup. The
V2 role passes complete readiness and normal session/journey regressions; direct
price changes, append-only UPDATE/DELETE, private journals, admission UPDATE and
DDL remain denied. An independently authenticated canary database/role retains
its exact row and write capability. All test databases and new roles are removed.

## Focused validation

- **54/54 passed**, zero failures/errors/skips: 18 real-session generation/auth/
  journey tests, 13 B1 cross-process admission tests, 13 B2 recovery tests, six B6
  tests and four reference-lock/security/concurrency tests. Includes Feedback,
  Submit/acknowledgement, stale pending payloads, worker crashes, drain timeouts,
  competing recovery and Submit versus basket/completion. 71.229 seconds.
  Evidence: `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-24894941f91940c6a4b0f4947b4743c5`.
  `writer-isolation.json` records non-secret role/backend/canary evidence.
- **21/21 passed**, zero failures/errors/skips: B3 Prepare Day policy, exact
  write set, generation/session preservation, exclusive drain, Start/Submit/
  Completion races, old commercial evidence, competing executors, allocation/
  publication crashes, interrupted recovery, missing/tampered journals, stale
  assignments and Tehran midnight. 77.436 seconds.
  Evidence: `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b3-46c1427fd78d4de3b36dbbf3628e38ab`.
- Django check and migration drift passed in both disposable environments;
  each applied all 50 migrations only there. Cleanup and signed persistent
  before/after reconciliation passed. No full application suite.
- Generation client **7/7 JS tests**, JS syntax, all Demo Python AST syntax and
  whitespace checks passed. JS source unchanged.
- Initial negative probes used two incorrect model column names; corrected to
  `base_price` and `reason_code` in TEST code only. Earlier diagnostic runs had
  errors; final 54-test evidence above contains the corrected probes. No security
  or application behavior was changed to accommodate them.

## Future persistent deployment — design only

1. Separately approve the trusted administrator/credential boundary, exact
   maintenance window, backup and signed journalled rollout/recovery procedure.
2. Verify fresh container/endpoint/DB/OID/marker, generation, fixture/source/SQL
   identities, roles, all writers and authoritative before-state. Record each
   non-atomic phase before attempting it.
3. Durably retire old LOGIN/reconnect/DML/sequence/capability authority. Stop only
   verified Demo workers under that fence; prove all old backends and transactions
   ended and reconcile any legitimate in-flight outcomes. PID/port closure or a
   transient empty session sample alone is insufficient.
4. Explicitly install the exact reviewed control bundle only under proven
   quiescence. Verify its full catalog and ACL contract. Ordinary startup cannot
   install anything. Interrupted/ambiguous installation retains the fence.
5. Introduce independently protected V2 credentials with least privilege through
   a reviewed launcher/profile/generation/capability-registry transition. Current
   `common.py` role pins are NOT a drop-in username switch; preserve middleware.
   Do not rotate generation, user identity, signing key, sessions or pending UUIDs.
6. Independently certify every compatible worker and signed deployment outcome
   before permitting mutation traffic. Normal startup refuses PENDING. A future
   maintenance-only health/activation protocol or offline validation/release order
   requires explicit design/approval; B6 does not introduce a PENDING bypass.
7. On uncertainty retain old-role retirement and durable PENDING/evidence. Never
   re-enable ungated source as rollback or use automatic takeover. Prepare Day,
   C0005 completion, reset and generation switching remain separate approvals.

STOP for unknown writers, trusted SQL access outside the agreed window, surviving
old backends/prepared transactions, mismatched source/identity/ACLs, missing or
tampered evidence, unresolved PENDING, ambiguous commit/drain or incomplete
all-worker proof. No persistent installer is implemented or exposed here.

**Operational trust limit:** owner/bootstrap/Docker administrators and anyone who
can use the new runtime credential for direct SQL can bypass cooperative request
admission. The gate does not claim to prevent them. If controlling these actors
and credentials is unacceptable, stop for a separately approved DB-enforced DML
architecture. Separate roles cannot attest to the code a credential holder runs.

## Persistent preservation and recommendation

Read-only readiness reports **NO_GO / MISSING_OR_INCOMPATIBLE**, old listener
signature unproven. Existing persistent application on `localhost:8900` remains
running, untouched. This is the expected deployment restriction, not a failed
disposable implementation. REFERENCE_LOCKS_V1 source SHA remains
`7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.

Signed read-only final before/after evidence:
`D:\SalesAI-Demo\sales_ai_copilot\reports\h4-b6-3a57b8b541f940948356c415582e6acb`.
Production and persistent Demo rows, sequences, sessions, fixtures, generation
and protected credentials reconciled unchanged; migration and capability checks
remain valid. No persistent schema/grant command was issued. No existing preview
was stopped or altered. No persistent DDL/grants/writes/restart, real credential
rotation/termination, Prepare Day/reset or generation switch occurred.

Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
modified relative to Git but untouched and UNSTAGED. Original stash remains
`2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index empty; HEAD unchanged;
unrelated DEMO-02/private previews preserved. Ignored B6 diagnostic helpers under
`venv/stage3h4-b6-artifacts/` and protected reports are local evidence only, not
runtime/provisioning dependencies or commit candidates.

**GO to begin controlled rollout design; NO-GO to execute rollout.** Owner review
and separate deployment/recovery authorization are still required.
