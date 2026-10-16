# Stage 3H3-B2-B1 — Demo-day and reset dry-run plans

2026-10-15. fast-track / V3.0.21 `1a96e92b938a5f64d586249245734f8e5d083b1e`.
Preserves uncommitted B1/B2-A. Planning commands implemented; execution is not.

## Operations and read-only boundary

```powershell
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py prepare-day --dry-run
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py prepare-day --dry-run --date 2026-10-16
& '.\venv\Scripts\python.exe' -B scripts/demo/plan.py reset --dry-run --date 2026-10-16
```

CLI requires --dry-run and rejects --execute/--confirm. No startup hook, HTTP
mutation, login, bootstrap, DDL/DML, migration, Docker lifecycle or grant operation.
No owner/bootstrap credentials are loaded. Protected Demo runtime identity,
container/image/volume binding, endpoint 127.0.0.1:5433, DB OID/marker and completed
SYNTHETIC_DEMO_V1 manifest/checksum are verified before inventory. Source and DB
migration graph must match the exact 50-migration profile.

Inventory uses one REPEATABLE READ / READ ONLY transaction and UTC-canonical
row digests plus sequence observations. Plans carry state/plan fingerprints,
fixture generation, dates and schema evidence. No password/hash/session token
values are output. Files are only explicitly saved audit reports, outside Git.
Normal `demo.py`/`demo.ps1` startup is byte-identical to B2-A.

## Prepare-day policy

Default target is the current aware clock converted to Asia/Tehran; --date is
an explicit ISO calendar date. Past dates block preparation. Plans contain each
of C0003/C0005/C0013/C0014/C0029 for SP001. Existing active assignment semantics
are reused (is_active only; no new date-based sales eligibility).

- Registered PLANNED/IN_PROGRESS same-day rows: KEEP_EXISTING.
- Registered COMPLETED/CANCELLED: PRESERVE_CLOSED, plan BLOCKED/DAY_ALREADY_USED.
- Duplicates, unregistered matching rows, missing/changed registered identities,
  inactive/unassigned customer: BLOCKED. Never adopt, redate, reopen or overwrite.
- Missing target-day row: WOULD_INSERT PLANNED Visit only. An older IN_PROGRESS
  Visit originally produced REVIEW_REQUIRED. B2-B2 owner decision supersedes it:
  conflicting preparation is BLOCKED with zero proposed inserts. It remains
  unchanged and is never automatically completed.
- New C0005 would require a separate authorized Start action and normal snapshot
  capture; a preparation insert never fabricates IN_PROGRESS.

Today's real plan is NO_OP: preserve Visits 1–5 and their current statuses.
The original 2026-10-16 plan proposed five PLANNED inserts and performed none.
B2-B2 now blocks that plan because C0005 Visit 2 is still active. Same observed
state/date produces the same plan fingerprint.

Future executor must serialize competing maintenance, quiesce conflicting Visit
creation, recheck identities/state and atomically insert. No customer/salesperson/
date uniqueness exists in schema. A future protected prepared-day ledger must
bind generation/date/Visit IDs with checksum; planner can inspect that format but
does not create it. Completed scenarios need a different date or an independently
approved candidate reset, not hidden changes to historical evidence.

## Candidate reset and recovery design

Reset inventories all 40 public tables, their counts, current generation and
migrations. Each table has expected candidate count/treatment and **zero deleted
rows in the old generation**. Fresh framework metadata comes from reviewed
migrations. Fresh synthetic users/catalog/inventory/prices/recommendations and five
Visits come from the frozen fixture definition; C0005 starts through normal API.
Candidate requests, lines, feedback, receipts, acknowledgements, sales, follow-ups
and sessions start empty. No production or old-generation data/hash cloning.

Candidate name derives from old identity/state/date, not a random rename/retry.
It is a proposal only; no candidate DB, user, secret, browser or schema is created.
Current launcher hardcodes sales_ai_demo_db: future activation requires an exact
owner-controlled generation registry/allowlist, with name/OID/marker/roles/container/
endpoint checks. Generic database-name prefixes are insufficient. Current owner
has no CREATEDB: future provisioning requires explicit dedicated Demo operator
authorization, never production credentials.

Future confirmation must bind current and candidate identities, state and plan
hashes, migration/fixture checksums, date, old-write fencing and retention policy.
An explicit generated confirmation phrase is shown but no command can accept it.
Validate the candidate independently, stop only the verified Demo app, reconcile
old pending commands, fence old runtime writes, and select the approved profile
through an ordered durable journal. Multi-step promotion is not atomic. Preserve
all old records, credentials, manifests and profiles.
Cleanup requires independent later approval; no DROP/TRUNCATE/reset implementation.

Before new business writes, recovery may reactivate the preserved generation
after explicit identity/profile/browser and grant-unfencing approval. After new
writes, stop and reconcile both generations; no silent merge or discarded new
evidence. Candidate failure never triggers destructive automatic retry/cleanup.

## Browser-generation risk

Current storage namespaces: guided-basket:v1, guided-feedback:v1,
sales-request-submit:v1, visit-completion:v1, scoped by actor/customer/Visit IDs,
not Demo generation. IDs can recur in a fresh candidate. Counts of DB sessions,
receipts or pending-looking requests cannot prove absence of browser sessionStorage
or in-flight commands. Do not inspect/report cookie values or session data.

Fresh browser profile/storage, independent signing key/session namespace and
generation-specific origin are prerequisites. Old-generation Host/Origin mutations
must be rejected at the Demo boundary. Stable localhost:8900 may become a GET-only
entry redirect to an exact generation hostname; DNS/Host/CSRF/browser behavior needs
owner approval and isolated validation first. Same-origin cookie/key rotation alone
cannot fence stale tabs after a fresh login; completion has no signed catalog
context. Old pending payloads remain quarantined and recoverable only against old
receipts/state. No silent retry or cross-generation replay; no clearing/rotation now.

## Validation and preservation

16/16 focused planner tests passed, zero failures/errors. Includes Tehran midnight,
year/leap boundaries, naive clock rejection, repeat planning, existing/closed/
duplicate/missing/unregistered Visits, assignment failure, wrong DB/endpoint/
container/OID/marker, and rejected execution flags. Real plans verified server
read-only mode. SQL trace for the three example plans observed only SELECT, SET
and SHOW. Django check and exact migration graph passed on a separately forced
read-only Demo connection. No fixture/authentication tests or full suite run.

Reports under `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b1\` include
`prepare-today.json`, `prepare-next-day.json`, `reset.json`, `sql-trace.json`,
baseline inventory and final preservation evidence. No actual preparation/reset.
Original SQLite, production, Demo data/sequences, original stash, protected files
and existing previews are preserved; no services restarted, staging/commit/push.

Owner decisions before execution: older active-Visit handling, exact future
transaction/ledger maintenance protocol, candidate provisioning/activation and
generation/browser fencing, retention/cleanup policy and post-write divergence
recovery. No future execution is authorized by this checkpoint.
