# Stage 3H4-B5 — Demo writer isolation and deployment safety design

2026-10-16. READ-ONLY investigation/design. No application implementation,
test-database writes, grants, credentials, service control or deployment.
Branch `fast-track`; committed V3.0.22 remains
`8bdb2ca6150a27d217eade7bfce8dff3768a4694`. Existing uncommitted H4 work retained.
Input: H4-B4 preflight. Recommendation: **NO-GO until the controls below are
approved, implemented and proven in disposable PostgreSQL.**

## 1. Verified target and session evidence

Persistent target remains `sales-ai-demo-postgres`, `127.0.0.1:5433`,
`sales_ai_demo_db` OID 16384; application `http://localhost:8900`.
Generation remains ACTIVE `6ae05c63-b9a3-4e85-a469-4643d3f76a27`.
V2 schema is absent. Existing listener PID 37632/parent 16592 reports this exact
database/runtime and REFERENCE_LOCKS_V1, but no V2 worker signature.

Session observation, **2026-10-16 05:24:55.403658 UTC**:

| Backend PID | Authenticated role | application_name | Client | State / transaction age | Attribution |
| --- | --- | --- | --- | --- | --- |
| 75484 | sales_ai_demo_bootstrap | sales-ai-h4-b5-readonly | 172.20.0.1:45202 | active / 0.007370 seconds | This controlled audit connection, transaction_read_only=on |

No other client session to this DB was present in that snapshot; zero prepared
transactions. The audit connection was closed afterward. Transaction start was
05:24:55.396297 UTC; backend start 05:24:55.390293 UTC. Session age is observation,
not an abandonment criterion. No query bodies, passwords or password hashes
were logged. Short-lived Django connections mean an empty snapshot is NOT proof
against dormant or future clients. `application_name` is client-supplied and is
not an authorization/build identity. Docker forwarding prevents reliable Windows
PID attribution from the PostgreSQL address/port alone.

Protected session, role/column/function and process evidence:
`D:\SalesAI-Demo\sales_ai_copilot\reports\h4-b5-d086e1061c4444c3aa19f8538b8ef1fd`.

## 2. Process inventory and evidence-limited mapping

Thirty matching Windows processes were observed: 28 long-lived project processes
plus two transient read-only audit processes. Twenty-one project listeners:
Demo on 8900 and twenty historical preview listeners. Python redirectors and
parents without listeners are included; none were stopped.

| Port(s) | PID(s) at observation | Database evidence | Classification |
| --- | --- | --- | --- |
| 8900 | 37632, redirector 16592 | Live infrastructure health plus exact protected profile identify sales_ai_demo_db:5433/runtime | Verified Demo application, **V2-ungated** |
| 8783 / 8786 / 8787 | 36564 / 13816 / 30396 | Files declare sales_ai_db; no live Demo session identified | Declared original-DB previews, not proven Demo writers |
| 8784 | 3492 | Local runtime launcher, target indirect | Unresolved from static extraction; preserve |
| 8785 | 11456 | File declares 127.0.0.1:5432/sales_ai_user; target DB indirect | Original-cluster validation listener; live target unverified |
| 8789 | 5796 | File declares test_stage3d2_preview_* on 5432 | Declared isolated preview; live target unverified |
| 8790 | 35964 | Profile declares test_stage3e2_preview_* on 5432 | Declared isolated preview; live target unverified |
| 8791 / 8792 | 37556 / 25584 | Profiles declare test_ui04f3_preview_* / test_ordinary_f1_preview_* on 5432 | Declared isolated previews; live target unverified |
| 8793 / 8794 | 32472 / 45344 | Profiles declare test_stage3f2_preview_* / test_stage3f2_success_* on 5432 | Declared isolated previews; live target unverified |
| 8795 / 8796 | 38140 / 37808 | Profiles declare test_stage3f2_f1_preview_* / test_stage3f2_f1_success_* on 5432 | Declared isolated previews; live target unverified |
| 8797 / 8798 / 8799 | 39020 / 25020 / 45704 | Profiles declare test_stage3g2_preview_* / test_stage3h1_demo_* / test_stage3h2_demo_* on 5432 | Declared isolated previews; live target unverified |
| 8770 / 8772 / 8774 / 8782 | 22176 / 38256 / 28184 / 36688 | Older temporary launchers; no direct literal target extracted | Unknown live targets; do not classify as Demo writers |

Some private scripts have both inherited credentials.json metadata and newer
profile.json target declarations. The sanitized report retains both; neither is
silently treated as the actual loaded target. Private code was parsed as text/AST,
NEVER imported/executed. Static declarations and files on disk do not attest to
loaded process settings. Process 8770 changed between B4/B5 observations; capture
fresh creation time/ancestry before any future control operation.

Ubuntu-24.04 was verified already running before read-only `ps`/`ss`. No
Python/Django/WSGI process was observed there. Cron and interactive bash/sh
sessions were present; loopback 5432/5433 listeners are reachable. Cron payloads
and future interactive commands are not attested. Docker has the two PostgreSQL
containers, not an observed Django app container; `docker top` for Demo shows
PostgreSQL/background processes. Docker-desktop/host administrator access remains
a privileged control surface. DBeaver PID 28392 is present, without a Demo client
session in the sample. Other projects' Python/LSP processes are not Demo writers
merely because they are Python processes. B4's service/task inventory remains a
snapshot, not a guarantee against future scheduled or manually launched work.

## 3. Effective writer roles and access paths

Privileges include table AND column grants, memberships/SET ROLE paths and
SECURITY DEFINER functions; 40 public tables include framework/auth tables.

| Role | LOGIN | Effective write access | Reachability / isolation meaning |
| --- | --- | --- | --- |
| sales_ai_demo_runtime | yes | 12 public tables counting column grants: Visit/request/line/session updates, allowed append-only inserts; auth_user UPDATE(last_login,password) | Application or arbitrary SQL with this credential; no general reference UPDATE, no append-only UPDATE/DELETE |
| sales_ai_demo_owner | yes | All 40 public tables, ownership/DDL | Maintenance/direct SQL; not constrained by cooperative middleware |
| sales_ai_demo_bootstrap | yes | All tables as superuser, role/database administration | Trusted cluster administrator; can bypass/reverse database fences |
| sales_ai_demo_lock_owner | NOLOGIN | UPDATE(id) on Customer, Grade, Product, Inventory, Recommendation; selected column reads | No memberships allow runtime assumption. Only two reviewed SECURITY DEFINER lock functions expose its privileges; functions lock, not business DML |
| pg_write_all_data | NOLOGIN | Implicit write rights across 40 public tables | No members observed; latent privileged role, not a separate connected writer |

Only the three custom LOGIN roles are reconnect-capable. No custom role
memberships were observed; only the standard pg_monitor/read-statistics graph.
The two lock functions grant EXECUTE solely to lock owner/current runtime, not
PUBLIC. The NOLOGIN roles must not be misreported as active anonymous accounts.
Bootstrap can SET ROLE/alter grants regardless; no in-database design can exclude
the cluster superuser acting outside an approved administrator trust boundary.

Writer classes now:

- **Gate V2-aware Demo application:** none verified running in persistent Demo.
  Approved source/tests exist, not deployment. V2 control objects are absent.
- **Known V2-ungated Demo application:** listener 8900, generation-aware older
  runtime, using sales_ai_demo_runtime. It must be retired under a future fence.
- **Administrative/direct SQL:** owner/bootstrap/runtime credentials, DBeaver,
  Docker/WSL access, management commands and explicit maintenance/validation tools.
  A connection need not be active now to belong to this risk class.
- **Unknown/unattributed:** no unknown Demo connection observed at sampling;
  other preview live targets and potential interactive/cron launches remain
  unproven. Preserve them; do not solve uncertainty by killing all Python/DB clients.

## 4. Isolation alternatives

| Option | Enforces | Does not establish alone |
| --- | --- | --- |
| A. Controlled shutdown + verified drain | Known old worker retirement; complete backends/transactions can be checked | Dormant relaunch, direct SQL or credential reuse. Port close/PID count is not a drain certificate |
| B. DB connection/write fencing | Durable denial for specified old principals; survives operator crash | REVOKE CONNECT/NOLOGIN does not end existing sessions or prove in-flight statements cannot still commit. Owners/superusers bypass ordinary ACL retirement |
| C. Independent versioned runtime credential | New compatible workers need not reuse old authority | An old credential can reconnect if later restored. New credential holders can still issue ungated SQL with direct DML grants |
| D. A+B+C with controlled admin/credential boundary | Smallest defensible containment of legacy writers while preserving unrelated services | Requires explicit trust/control of new credential and privileged administrators; not code attestation enforced by PostgreSQL |

**Recommend D**, scoped solely to the dedicated Demo cluster/roles/application.
Do not change original PostgreSQL, stop unrelated previews, rotate generation,
invalidate browser sessions or automatically resolve Visits.

Proposed new principal: `sales_ai_demo_runtime_v2` (NOT created). After approval:

1. Keep its independently generated credential in a versioned protected path,
   accessible only to a controlled compatible launcher/service execution identity.
   Do not overwrite a shared old credential file or expose owner/bootstrap creds
   to application processes. Do not inherit old/runtime administrative memberships.
2. Durably retire old runtime LOGIN, table/column DML, sequence use and lock-function
   EXECUTE authority; do not merely disable it temporarily and re-enable afterward.
   Enumerate PUBLIC/inherited grants too. Revocation is not proof of drain: already
   executing statements/transactions must finish or roll back before installation.
3. Stop only the verified Demo worker tree under that reconnect fence. Prove zero
   old-role backends (including idle ones), zero prepared transactions and no
   uncertain transaction effects. Capture/reconcile legitimate in-flight changes
   separately; never replace an old baseline to conceal them.
4. Unknown sessions: identify authenticated role, endpoint, backend start and
   transaction evidence. Stop deployment if unresolved. Any later termination
   needs explicit authorization for exact Demo backends and outcome reconciliation;
   no blanket pg_terminate_backend, connection-age cutoff or unrelated service stop.
5. Enforce a maintenance-only administrator window: freeze owner/bootstrap/SQL
   commands and Docker/WSL administrative access except the approved operation.
   Container-local HBA trust means protecting only passwords is insufficient.
6. Grant the new runtime only the existing reviewed journey privileges. Replace,
   rather than accumulate, old runtime EXECUTE/schema ACLs in REFERENCE_LOCKS_V1;
   refresh the exact protected capability registry through a reviewed operation.
   No reference UPDATE, ownership, SUPERUSER, CREATEDB or CREATEROLE for runtime.
7. Permanently keep old-role fencing after success/recovery. Preserved credentials
   can be archived for evidence, not restored as a shortcut to an ungated build.

**Trust limit:** roles/application_name cannot attest that arbitrary SQL is
gate-aware. Anyone able to use the NEW runtime credential outside the controlled
launcher can still bypass the application gate, as can owner/bootstrap. If that
trusted-operator/credential boundary is unacceptable, D is insufficient. A broader
DB-enforced gated-DML design (restricted business mutation functions, or carefully
designed statement-level enforcement including sequences) needs separate approval
and equivalent concurrency tests. Do not invent that architecture in this task.
Simple triggers alone must not be claimed to cover standalone nextval, owner/
superuser bypass or an entire multi-transaction HTTP request lifecycle.

## 5. Required configuration compatibility

The proposed versioned role is NOT a drop-in environment-variable change:
`common.py` pins RUNTIME, profile/credential role names, connection guards and
the conditional generation/middleware installation. `demo.health`, capability
ACL validation and generation registry pins also reference the approved runtime.
A future narrow configuration change must preserve all these checks for the new
role, not bypass `role == RUNTIME` and accidentally omit generation/gate middleware.
The new role must remain bound to the same database/OID/container/endpoint and
approved profile. No production or old-preview profile change is needed.

Keep generation UUID, user IDs/password hashes, Django signing key, cookie name,
session rows and pending command UUID/payload/proof unchanged. Role/profile/ACL
publication is a journalled deployment metadata change, NOT generation rotation.
If control operations already exist, their signed role/source bindings cannot be
rewritten. Any PENDING operation or unreviewed historical binding blocks a role
transition until its original outcome is proven under separately approved recovery.

## 6. Smallest fail-closed readiness correction — proposal only

Current `demo.preflight → maintenance_gate.verify_ready` and
`gate_readiness.assess → inspect` inspect admission, not all journal objects.
`prepare_day.context` verifies its private tables only when using the disposable
executor. B4 proved normal readiness can pass with journal tables absent.

Propose one shared SELECT-only versioned bundle inspector, reused by normal
startup, read-only readiness and owner/executor preflight:

- Verify all five exact ordinary tables: admission, operations, results,
  prepared_days, preparation_recoveries, with the reviewed schema owner.
- Validate expected columns/types/nullability/defaults, PK/FK/CHECK and partial
  unique index through pg_catalog, normalized by qualified identity (not OIDs or
  incidental formatting). Bind this to the reviewed versioned schema contract.
- Verify schema/PUBLIC/table/column ACLs: runtime SELECT on admission only,
  no runtime privileges on four private tables, no schema CREATE/grant options.
  Runtime can inspect pg_catalog without granting SELECT on journal contents.
- Check exact DB/generation singleton and phase; normal serving still requires
  ACTIVE. Missing/partial/wrong-owner/incompatible/unsafe/PENDING state fails
  closed before request handling. Never CREATE, repair, grant or clear PENDING.
- Reuse the same inspector; do not call disposable-only execution context from
  persistent startup, remove its guards, or introduce an unlocked fallback.
- Extend loaded worker evidence to the complete deployment/bundle contract,
  including Prepare Day/source where required. One healthy worker still cannot
  certify all workers; keep all_workers_verified false without independent proof.

No domain model/schema migration or business-service change is needed to fix this
readiness defect. Tests proposed: remove each required table/index/constraint,
alter a column/owner, grant a private column, mismatch DB/gen/version/source, and
verify fail-closed startup plus zero writes; valid complete bundle passes. Apply
all destructive setup only to disposable DBs. **Nothing implemented or tested anew.**

## 7. Dependency order and proof gates

1. Owner approves administrator trust boundary, permanent old-role retirement,
   new credential/profile policy and exact maintenance window. If arbitrary new-
   runtime/direct privileged SQL must be technically fenced too, STOP for the
   broader DB-enforcement design before any rollout.
2. Implement/test bundle readiness and narrowly scoped role/profile compatibility
   in disposable PostgreSQL. Prove all existing CSRF/session/generation/UUID,
   authorization, pricing, receipt and concurrency invariants remain intact.
3. Approve a persistent deployment/recovery wrapper with durable signed phases,
   stable operation identity and verified independent DB ownership/fencing. No
   retargeting of current disposable installers/recovery/executor guards.
4. Capture fresh backup and signed before-state. Fence old reconnect/write
   authority; retire only known Demo workers. Prove ALL old sessions/transactions
   ended under the retained fence; resolve unknowns and any in-flight outcomes.
5. Install exact reviewed Gate V2 + journal SQL atomically in the verified Demo,
   with no business changes. Verify full catalog/ACL fingerprint and publish
   installation evidence. Keep generation/fixtures/sessions and sequences intact.
6. Reconcile startup versus PENDING explicitly. Preferred design if workers must
   be certified before admission: a separately approved maintenance-only launch
   mode may inspect installed schema and expose infrastructure health, but ALL
   Django requests must remain blocked by PENDING. Normal startup still requires
   ACTIVE. This is not permission to clear PENDING or bypass request admission.
   An alternative offline-verify → authorize → start sequence needs an equally
   explicit trusted-launch/no-uncontrolled-credential proof. Select/test one,
   rather than silently inventing a readiness exception.
7. Prove only compatible controlled workers hold new runtime access. In one
   authorized DB transition reconcile the signed deployment result, request drain
   and operation ownership before releasing PENDING/enabling intended mutation
   authority. Profile/registry publication and process startup are separate phases,
   not an atomic filesystem+database+service operation. An interruption keeps the
   durable principal/admission fence; no automatic takeover or role re-enabling.
8. Verify fresh request/session behavior under narrow separate auth-write
   authorization, then reconcile allowed effects and open only approved traffic.
   Keep old identities retired. Prepare Day remains a separate approval; C0005
   remains IN_PROGRESS and may not be completed by deployment.

Proof requirements before GO: correct DB/marker/OID/container/endpoint; exact
source/SQL/ACL/bundle version; no writable retired role or unknown reachable
principal; zero old backends/prepared transactions under a durable fence;
controlled privileged access; every worker's loaded build/profile verified;
crash-safe signed deployment outcome and recovery; unchanged generation,
business/sequence/fixture/session evidence except explicitly authorized effects.
PID, application_name, age, empty session samples and port closure alone never
satisfy these requirements.

## 8. Required validation and recovery boundaries

Future disposable tests must include existing connections during NOLOGIN/CONNECT/
DML revocation, waiting/in-flight statements, reconnect after retirement,
unrelated services/5432 unaffected, old-role attempts after deployment, unknown
session refusal, admin-window assumptions, new-credential access boundaries,
PENDING startup/request denial, bundle tampering, interrupted activation and
publication, owner crash, competing operators, exact replay and unchanged
business/sequence state. Reuse B1/B2/B3/B4 evidence; do not mistake eight successful
B4 experiments for proof that the bypass/retirement/readiness findings are fixed.

On ambiguity retain the permanent old-role fence, PENDING and all original
evidence. Use read-only outcome inspection before any approved continuation.
No restore, sequence reset, automatic data merge, role reactivation, generation
rotation, fixture reset or return to ungated source. Superuser intervention is
an explicit trusted recovery action, never a claimed database-enforced safeguard.

## 9. Changes and preservation

Design checkpoint only in repository. New ignored helper/evidence pointer under
`venv/stage3h4-b5-artifacts/` and protected reports contain sanitized observations,
not runtime dependencies or credentials. Application/SQL/configuration unchanged.
No tests, migrations, grants, authentication POSTs, business writes, service stops/
restarts, Prepare Day, reset or recovery ran. Original SQLite and stash, unrelated
DEMO-02 and all prior H4 work remain protected. Final signed preservation comparison
returned `READ_ONLY_PRESERVATION_VERIFIED`; application fingerprints, helper syntax,
checkpoint whitespace and `git diff --check` passed. Index remains empty.
SQLite SHA256 is unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No staging/commit/push.

**Owner decision required:** approve the trust/isolation model and the next
disposable-only implementation scope. Persistent deployment remains NO-GO.
