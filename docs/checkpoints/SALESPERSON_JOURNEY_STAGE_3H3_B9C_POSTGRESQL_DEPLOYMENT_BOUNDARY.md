# Stage 3H3-B9-C — PostgreSQL compatibility and deployment boundary

2026-10-15. Baseline V3.0.21 / `1a96e92b938a5f64d586249245734f8e5d083b1e`.
Approved uncommitted B1–B9-B work retained. Analysis/readiness documentation only:
no application/configuration, locking, SQL, privilege or migration changes.

## Exact dependency and execution paths

`apps/core/reference_locks.py` unconditionally calls the two versioned capability
functions for PostgreSQL, inside the caller's atomic transaction. It validates
identities and bounded product lists; there is no unlocked or privileged fallback.
The only application callers are:

| Entry/path | Dependency and invariant |
| --- | --- |
| POST `/api/recommendations/v1/visits/<id>/feedback/`, `record_feedback` | New REJECTED/LATER commands: authorized Visit lock → existing Request lock → `lock_feedback_references(customer_id,recommendation_id)` → authoritative reread/validation → append-only event + receipt. Capability locks Recommendation → Product until transaction end. |
| POST `/api/sales-requests/v1/visits/<id>/submit/`, `submit_request` → `_lock_commercial` | New DRAFT submission: authorized Visit → Request → selected Lines → `lock_submission_references(customer_id,product_ids)` → authoritative Customer reread and commercial review → fingerprint/revision/CAS/immutable snapshots. Capability locks Customer → Grade → Products by PK → Inventory by product ID until transaction end. Even an empty DRAFT can reach the capability before its validation rejection. |
| Identical successful Feedback/Submit replay | Authorization and operational locks remain; stored success returns before reference-lock acquisition. No new commercial effects. Service-level replay surviving missing functions does not establish environment readiness; Demo's connection fence still rejects capability drift. |
| Catalog, quote, review/result, Product Detail and feedback-history GET | No direct capability call. Rendering/price availability/login success does not prove POST readiness. |
| Basket, Visit Start, legacy/new completion and acknowledgement | No direct capability call. Existing operational locks, receipt/revision guards and schema requirements remain mandatory. No new dependency is inferred for these services. |
| B7 explicit runtime probes and B6 tests | Direct function calls are deliberate verification only. Never run persistent mutation probes as an original-database readiness test. |

Missing schema/function/EXECUTE fails with PostgreSQL DatabaseError, not an unlocked
read. Fresh Feedback/Submit transactions roll back; current API exception handlers
do not map infrastructure errors to a special Persian 503/409 response. An
otherwise eligible request can therefore produce HTTP 500. This failure behavior
is inferred from handlers and verified with missing-function disposable tests;
no business POST was sent to the original database.

The lock adapter does not lock demo-price rows. Existing authoritative provider
reads, quote/review fingerprints and point-in-time pricing semantics are preserved.
Do not claim warehouse allocation, future-price freezing or universal deadlock
freedom from these capabilities.

## Verified environment matrix

| Target | Schema/capability state | Admission boundary |
| --- | --- | --- |
| Persistent Demo `sales_ai_demo_db`, 127.0.0.1:5433 | 50/50 migrations; verified `REFERENCE_LOCKS_V1`, pinned registry/OIDs/bodies/owner/ACLs. Runtime has no direct reference UPDATE. | READY under the existing dedicated launcher. Preflight and each new runtime Django connection validate capabilities. No startup SQL installation. |
| Original `sales_ai_db`, 127.0.0.1:5432, `sales_ai_runtime` | PostgreSQL 17.11; 49/50 migrations, pending `sales_requests.0003_complete_visit_receipt`; capability schema absent, zero capability functions. | **NO-GO for new shared mutation source.** Ordinary `manage.py check` passes, but neither it, CoreConfig, settings, WSGI nor the current local launcher validates capabilities. No original startup enforcement was added. |
| Disposable PostgreSQL, normal Django migrations only | Tables/migration state alone do not create capabilities, regardless of owner privileges. | NOT READY for Feedback/Submit tests until explicit, identity-guarded capability setup. Missing functions must fail, including for superuser callers. |
| Disposable PostgreSQL, approved B3/B6 harness | 50 migrations; independent owner/runtime/capability roles, explicitly installed functions and normal session/CSRF/generation transport. | READY for the selected tests only; exact DB/OID/marker checked and disposable objects removed afterward. |
| Isolated SQLite development/test | Adapter retains original atomic/CAS behavior; PostgreSQL row-lock statements/functions do not apply. | Supported by focused in-memory tests; no claim of PostgreSQL-equivalent concurrency. Original SQLite is preserved, not opened/migrated or advertised as schema-ready. |

Additional compatibility fact: the original runtime already has UPDATE privileges
on all columns of Customer, Grade, Product, Inventory and Recommendation. Demo's
no-reference-UPDATE policy does not describe that older instance. The existing
original role remains LOGIN/NOINHERIT with no superuser, CREATEDB, CREATEROLE,
replication or BYPASSRLS. All existing grants remain unchanged. The initial
diagnostic's assumption of Demo-equivalent reference privileges was disproved by
read-only inspection; it was not evidence of a new grant change.

The 49/50 schema gap predates this review and is separate from capability absence.
Do not apply migration 0003 here or describe capability installation alone as
making the complete current salesperson journey ready.

## Options

| Option | Security/concurrency | Operations, rollback and compatibility |
| --- | --- | --- |
| **A. Explicit pre-deployment capability contract — recommended** | Keep the approved shared locking architecture, lock order/strength/lifetime, authoritative rereads and least-privilege capability owner. No fallback or broad new runtime reference UPDATE. | Every PostgreSQL target must be explicitly provisioned/validated before serving this build. Requires owner-approved original migration, role/ACL policy, target identity/registry and readiness integration. SQL and registry publication are separate journalled steps. Roll back application and dependencies coherently after quiescence. |
| B. Strict original-only legacy-locking boundary | Could retain the committed pre-B6 direct row-locking path on explicitly identified original instances; existing original UPDATE grants can support those statements. Must preserve both Recommendation and Product locks, lock ordering and all commercial invariants. No missing-function exception fallback. | Requires business-service selection/compatibility branches and an explicit trusted environment contract, separate architecture approval and tests for BOTH paths. Forked concurrency/security policies and accidental target selection increase maintenance risk. Not implemented or approved by this task. |
| C. Hold rollout; separate verified application builds | Limit this source to the validated Demo/disposable environments. Keep original instances on an independently verified compatible build/schema; do not equate their previous grant policy with Demo security. | Temporary operational containment, not a capability fix. Shared mutable checkout/reloader processes are unsuitable isolation. Repinning/stopping original processes or introducing a separate build needs explicit action/approval; none performed here. Does not solve the original migration gap. |

No unambiguous executable original-runtime correction is authorized: installing
capabilities/migrations or changing the selected locking path crosses the task's
approval boundary. Only documentation and the explicit NO-GO contract were added.

## Proposed Option A admission and recovery contract — not executed

1. Independently approve exact original endpoint/database/OID/owner/runtime,
   application build and maintenance window. Verify preservation evidence and
   quiesce only verified dependent processes. Never retarget Demo installers by
   editing constants or copy Demo credentials, OIDs, marker or registry.
2. Approve migration 0003 separately; require the full reviewed migration graph.
   No automatic migration, seed, price change or business-data correction.
3. Approve a dedicated NOLOGIN capability owner and minimal SELECT/link-column +
   UPDATE(id) privileges, schema ownership, exact runtime USAGE/EXECUTE and PUBLIC
   denial. Do not grant runtime new broad reference privileges. Explicitly decide
   whether existing original reference UPDATE is retained as a documented legacy
   policy or separately reduced after testing affected manager/reference workflows.
4. Approve reproducible original-target installation and a protected readiness
   registry. Enforce version/signature/body/source hash, safe fixed search_path,
   bounded arguments, owner flags/memberships, ACLs, table/column privileges and
   schema/DB identity. Mere function existence or version comment is insufficient.
   The Demo inspector's stricter ACL/identity contract cannot be silently relaxed
   or treated as an original-target deployment tool.
5. Validate the exact target policy in disposable PostgreSQL first: normal
   Feedback/Submit, contention/order/lifetime, deactivation/stock/grade races,
   UUID/revision/replay/rollback, missing/drifting capabilities and denied DML/DDL.
   Add an executable original startup/admission gate only under that approved
   policy; ensure readiness and every used connection/pool path are accounted for.
6. Reconcile all rows/financial digests/sequences/grants before and after any later
   authorized maintenance. Store recovery evidence before DDL; verify registry
   publication and restart separately. Never describe the whole rollout as atomic.
7. On uncertainty, block admission and inspect original evidence. Roll back only
   to a verified application/schema/capability combination. Preserve snapshots,
   receipts, fixtures, generations and history. Never drop capabilities while
   dependent code runs; no CASCADE, automatic grant repair, data restore, unlocked
   fallback or silent database switch. Dependency-checked SQL removal would need
   its own approval. No removal/rollback operation is supplied here.

## Focused validation and preservation

- PostgreSQL: **8/8 passed**, zero failures/errors/skips, disposable only. Methods
  08/09 (Feedback/Submit/completion/replay), 20/21 (exact security/denied writes),
  30 (real competing locks through commit/rollback), 34 (missing-function rollback),
  40/42 (readiness/registry/drift rejection). The source and existing tests were
  not modified. The disposable database and independent roles were removed.
- SQLite: **54 run, 53 passed, 1 expected PostgreSQL-only skip**, guarded in-memory
  databases only. No original SQLite connection.
- Demo Django/preflight check passed, including full 50-migration schema and exact
  capability/source/owner/ACL registry verification. Original Django system check
  passed with identity-guarded read-only connections, demonstrating that this
  generic check is **not** capability readiness. Original migration graph is
  consistent but pending 0003; no migration was applied.
- Disposable migration drift check reports no changes. Python syntax and Git
  whitespace checks pass. No JS changed; no full regression suite was run.
- Canonical LF capability SQL SHA256 remains
  `7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.

Protected evidence: `D:\SalesAI-Demo\sales_ai_copilot\reports\b9c-bf7f1a8d16944ef19ad80e66f262a8c0`.
Disposable PostgreSQL results/cleanup:
`reports/b2b3-c362e65fa3c4417e88ae2f96c4ef36a9` under that protected state root.
These reports are evidence only, not source/runtime dependencies.

Original/Demo data, sequence evidence, profiles, credentials, sessions, generation,
capability objects/privileges and listener remain preserved. Original SQLite SHA:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`. No staging/commit/push;
all previous approved/unrelated work retained.

**Owner decision required:** approve Option A's original-target rollout plan,
separate migration/capability installation, runtime-reference-grant policy and
executable readiness enforcement; or explicitly select Option B/C. The deployment
boundary is documented, but B8 blocker #3's original-instance readiness remains
open. No production compatibility or full closeout approval is claimed.
