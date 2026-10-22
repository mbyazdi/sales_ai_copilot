# Stage M-E0.1 — Isolated Management TEST Preview Boundary

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Owner authorization: disposable PostgreSQL and interactive TEST-profile proof only.
No management UI implementation or persistent deployment. Gate V2 remains NOT DEPLOYED / NO-GO.

## Explicit profile boundary

`scripts/management_preview.py` creates a separate `MANAGEMENT_TEST_PREVIEW_V1`
profile, following the approved M-D1 disposable API test configuration. It does
not call the persistent Demo launcher, `configure_django`, generation installer,
Gate V2 installer or recovery/Prepare Day tools. No Demo middleware is removed:
base Django middleware is retained, and an unexpected Demo profile is rejected.

Normal Django authentication, DB-backed sessions, logout, CSRF middleware and
the existing strategy-view/manage capabilities remain authoritative. There is
no force-login, signed-cookie session harness or permission impersonation.
An independent non-superuser staff TEST account exercises management services.

Gate V2 retains its existing request-wide atomic transaction. Strategy services
retain their top-level REPEATABLE READ / READ ONLY and command transaction
requirements. This TEST profile has `ATOMIC_REQUESTS=False`, no outer transaction,
and no maintenance/generation switching surface. Real HTTP overview, source
capture, preview and publication succeed without changing either architecture.
This does NOT establish Gate V2/strategy service compatibility or approve Demo rollout.

## Isolation and access

- Preview: `http://localhost:8901/accounts/login/`, bound only to `127.0.0.1`.
- Final disposable DB: `test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a` on `127.0.0.1:5433`.
- Independent roles: `me01_owner_5d24c8a723614bcfaa3b6ea3fd0efe5a` and
  `me01_runtime_5d24c8a723614bcfaa3b6ea3fd0efe5a`.
- DB identity: exact name, catalog OID, unique UUID/comment, role, client endpoint
  and internal server port checked on every new runtime connection.
- Runtime driver refuses other endpoints/databases/roles and DSNs, services,
  hostaddr/passfile routing before network access. SQLite connections are blocked.
- Inherited DB/libpq selectors are cleared only inside the preview process.
- Runtime never receives the operator or owner password. The operator credential
  is read only by explicit provisioning/cleanup, verifies the dedicated container,
  and connects to `postgres` for exact disposable resource administration.
- Protected state: `D:\py project\sales_ai_copilot\venv\management-preview-live\`.
  Independent random role/account passwords, Django signing key and control key.
  ACL inheritance removed; access granted only to current Windows user and SYSTEM.
  Entire state is Git-ignored. No secrets or password hashes are printed.
- Unique per-preview session AND CSRF cookie names; session cookie HttpOnly,
  SameSite Strict. Port numbers do not isolate cookies. Use a separate browser
  profile for convenient review; existing Demo cookies are not reused.
- HTTP allowlist: normal login/logout, `/api/management/v1/strategy/`, static
  assets and an attested private lifecycle endpoint. Admin, legacy dashboards,
  salesperson mutations, outbound integrations and other routes return 404.
- Runtime: source SELECT, strategy INSERT, policy-head column UPDATE only,
  required strategy sequence USAGE, session CRUD, auth_user UPDATE(last_login).
  No runtime DDL, reference/price UPDATE, or history UPDATE/DELETE. PUBLIC access
  revoked on the new DB/schema. No changes to existing database grants.

Driver/profile routing and restricted credentials protect this application.
The trusted operator/OS administrator can still use direct SQL; this is not an
OS sandbox against malicious code. No claim of database-wide denial of CONNECT
to every unrelated database is made; no existing PUBLIC ACL is altered.

## Synthetic scenario and real HTTP proof

Repository-owned `ME01_V1` fixtures, only on explicit fresh provisioning:
one manager, one linked nonstaff salesperson, one unrelated nonstaff TEST user;
one grade-A customer and active assignment; four fictional products/shortlist
rows, stock 12 available/2 reserved, fictional base price 100 TOMAN; one QUANTITY
target (100, actual 50) and one grade-qualified quantity-one promotion.
Evaluation date is captured explicitly from Asia/Tehran at provisioning, never
silently changed on startup. No production business rows or password hashes copied.

The verifier explicitly creates/previews/publishes neutral, then a product-3
priority 20, target weight 5, promotion emphasis 5 policy. Same frozen facts yield:

| Recommendation | Saved score | Base priority | Adjustment | Effective | Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 40 | 30 | 0 | 30 | 2 |
| 2 | 90 | 20 | 0 | 20 | 3 |
| 3 | 70 | 10 | 27.50 | 37.50 | 1 |
| 4 | 60 | 0 | 0 | 0 | 4 |

This is a simulation, not uplift, purchase probability or a real promotion price.
Stored recommendation scores/ranks/reasons, inventory, prices and all fixture
source rows remain unchanged. Frozen comparison ID 2 remains retrievable after
publication. The active policy is the published boost; no strategy is installed
in either persistent database. Existing signed-context source/format is untouched;
external contexts intentionally cannot cross this independent signing identity.

Validation:

- Six focused boundary tests passed: strict identities/routing, pre-network
  driver/SQLite denial, missing/tampered evidence, source drift, middleware and
  transaction configuration. Multiple negative cases are subtests.
- Final real HTTP PostgreSQL workflow: **54 checks passed**, including normal
  login/last_login/DB session, missing/invalid CSRF and hostile origin rejection,
  salesperson/unrelated-user denial, authoritative snapshot capture, explicit
  comparisons/publication, exact replay/conflicting UUID, command recovery,
  frozen historical retrieval, runtime privilege denial, GET/HEAD preservation,
  normal logout/session removal and unchanged fixture/source digests.
- Django check and migration drift passed; all 51 source migrations applied
  only to disposable databases. No new migration or application source change.
- Duplicate start on occupied 8901 and cleanup while serving fail closed.
- Authenticated shutdown drained workers and waited for the verified Windows
  process handle; restart succeeded. Fresh normal login retrieved the same
  comparison/output digest and ranking, then logged out. Recovery issued zero
  business POSTs. Evidence: protected `restart-proof.json`.
- Negative readiness test explicitly revoked one SELECT grant only in this
  disposable DB: checks refused, made zero permission repairs, and passed after
  the original grant was explicitly restored. Evidence:
  `readiness-negative-proof.json`. Command:
  `python -B scripts/verify_management_preview.py --readiness-negative`.
- First development proof DB/roles were removed with exact OID/comment checks;
  protected evidence retained under `venv/management-preview/`.
- Final preview retained for interactive owner review. No full suite or JS changes.

## Operator commands and recovery

From the project directory in PowerShell (never the persistent Demo launcher):

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview.py status
.\venv\Scripts\python.exe -B scripts/management_preview.py checks
.\venv\Scripts\python.exe -B scripts/management_preview.py start
.\venv\Scripts\python.exe -B scripts/management_preview.py stop
.\venv\Scripts\python.exe -B scripts/management_preview.py cleanup
```

The final preview is already running; do not run `start` again unnecessarily.
Open the protected `accounts.json` locally and use its `manager` entry. Never
paste credentials into terminal output or Git. After login, the existing JSON
overview opens; no management pages are implemented. Useful read routes:

- `http://localhost:8901/api/management/v1/strategy/overview/`
- `http://localhost:8901/api/management/v1/strategy/versions/`
- `http://localhost:8901/api/management/v1/strategy/comparisons/2/`

Read-only business recovery after restart (normal login/logout writes TEST sessions):

```powershell
.\venv\Scripts\python.exe -B scripts/verify_management_preview.py --recovery-only
```

The full HTTP verifier is intentionally fresh-preview-only. Do not run it again
against populated state: it refuses rather than silently reseeding/replacing
history. A new proof uses an explicitly different state directory:

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview.py provision --state venv/management-preview-new-proof
.\venv\Scripts\python.exe -B scripts/management_preview.py start --state venv/management-preview-new-proof
.\venv\Scripts\python.exe -B scripts/verify_management_preview.py --state venv/management-preview-new-proof
```

Stop the current verified 8901 process first. Provision rejects an existing state
directory, tests a real loopback bind, creates a UUID DB/independent roles, applies
migrations and seeds only there. Startup is read-only: no install/migrate/seed/date
adjustment. Startup checks signed profile, source fingerprint, DB identity,
migration graph, ownership/grants and middleware. Missing/incompatible evidence
or permissions fail closed, never falling back to another database.

Health responses carry a control-key HMAC over identity, source and process ID.
Shutdown authenticates that response, retains a Windows process handle before
sending the protected stop command, and waits for the exact process to exit.
Non-daemon request workers drain, including session persistence. No PID-only kill,
forced termination, unrelated service stop or automatic process adoption.

Source changes prohibit a new startup. Authenticated status/stop/cleanup retain
the signed original identity so source drift does not strand recovery. Cleanup
requires no listener, zero exact-DB sessions, matching OID/comment, then drops
only the two isolated roles and DB. Private evidence is retained, never recursively
deleted. Unexpected sessions/identity drift or partial provisioning refuse automatic
cleanup; operator must inspect original protected `creation.json` and catalog
evidence. Never rerun provisioning into uncertain state or modify its evidence.

After interrupted HTTP mutation: retain the exact UUID/payload, log in normally,
GET `commands/{uuid}/`, then inspect frozen comparison. Missing receipt does not
authorize an automatic retry or adoption. Existing services remain authoritative.

## Preservation and next boundary

No original PostgreSQL connection, persistent Demo writes/DDL/grants, service
restart, Gate activation, Prepare Day, reset or generation switch. Existing
management, settings, Demo/generation/gate code and signed-context logic unchanged.
Protected state/credentials and unrelated DEMO-02 work preserved. Index empty;
no staging, commit or push. Original stash:
`2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.

GO for this separate management API TEST preview. Management page implementation
still waits for approved M-01-B/M-04 desktop/mobile reference files. Future UI
routes must be explicitly added to the preview allowlist and its source identity
reviewed/rebuilt. Gate V2/strategy transaction compatibility and all persistent
deployment remain separate, unapproved work.

Final preservation verification: all **53 pre-existing modified/untracked files**
matched their captured SHA256 values byte-for-byte. Only the three new scripts
and this checkpoint were added. Persistent Demo all-user-table/sequence digest
matched before/after:
`c42009b3f3fb59bb4c91a1d4a27f817db34c9251727512a355ae2a1283f4e86d`.
Existing localhost:8900 process remains PID 37632; final preview PID is 51184.
Six unit tests, three Python syntax checks, Django check, migration drift,
`git diff --check` and scoped new-file whitespace checks passed. JavaScript was
not changed or retested. Live credentials/evidence remain outside Git.
