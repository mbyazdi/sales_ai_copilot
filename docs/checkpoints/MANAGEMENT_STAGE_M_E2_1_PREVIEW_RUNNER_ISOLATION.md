# Stage M-E2.1 — Preview Runner Isolation Safety Patch

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Source-only safety patch. No management UI or business behavior changes.

## Root cause

M-E2 invoked `apps.management.verify_strategy_foundation.main(...)` for its
focused PostgreSQL tests. That shared runner called `persistent_digest(password)`
before tests and in final cleanup. The helper used direct `psycopg.connect`
against `sales_ai_demo_db` at 127.0.0.1:5433 as the maintenance role, then hashed
tables/sequences. These read-only probes were unauthorized under M-E2.

The original Django `DatabaseWrapper.get_new_connection` guard protected ORM
test connections, but did not intercept those direct driver connections. The
before-probe also ran before that ORM guard was installed. Read-only access was
incorrectly treated as acceptable preservation evidence. Both calls and the
helper itself are now removed; there is no option to re-enable the probe.

## Exact files

Modified:
- `apps/management/verify_strategy_foundation.py`
- `scripts/verify_management_preview.py`

Added:
- `scripts/management_test_isolation.py`
- `scripts/tests_management_test_isolation.py`
- This checkpoint.

No evaluator, service, API, UI, migration, pricing or application/startup file
changed. Existing M-C1 through M-E2 work is retained byte-for-byte outside this
explicit verification boundary.

## Fail-closed connection contract

- PostgreSQL test execution requires explicit `--provision-disposable`.
  Without it the runner fails before connecting or reading provisioning state.
- A fresh process is required. Already configured Django settings/connections
  are rejected, rather than adopted or silently redirected.
- The runner clears inherited database selectors/libpq routing before setup.
  Subsequent routing-environment changes are rejected at each driver boundary.
- Each allowed business/test target is enrolled with the run's exact UUID,
  OID, marker, fixed endpoint and generated owner/runtime-role identities.
  A `test_` prefix alone grants nothing. Unenrolled/protected names, wrong roles,
  DSNs, service/hostaddr/passfile overrides or wrong endpoints fail before the
  connector is called. Direct `psycopg.connect` and Django driver calls share
  this guard.
- Offline identity/routing validation occurs BEFORE networking/cursor creation.
  Actual server identity cannot be known before a connection exists: the first
  allowed query attests current database, role, OID, marker and server endpoint.
  A mismatch closes immediately before any test/business SQL is returned access.
- SQLite is limited to `:memory:` and Django's exact shared-memory test URI.
  PostgreSQL mode rejects SQLite entirely. Original and unexpected disk files
  cannot be opened through the installed SQLite guard.
- Catalog provisioning is a separate explicit channel: `postgres` on the
  isolated 5433 cluster, maintenance role only, for UUID DB/role CREATE/DROP.
  It is never an ordinary Django/test target and cannot be redirected to either
  protected business database. It remains an operational maintenance trust
  boundary; this is not a Python sandbox against arbitrary privileged code.
- Direct connections in `verify_management_preview.py` now use
  `connect_preview`: validate the exact TEST-profile database/role/8901 marker
  and routing BEFORE connecting, then attest live identity before verification
  SQL. The caller already authenticates signed local profile/health evidence.
  No persistent profile or runtime code was changed.

## Focused validation evidence

- **23 DB-free tests passed**: 17 new isolation tests and 6 existing preview
  boundary tests. Protected-target negatives assert connector and cursor mocks
  remain unused. Cases include protected/unrecognized names, wrong endpoints,
  DSNs, environment routing, inherited Django settings, disk SQLite, direct
  driver bypass, explicit catalog authority, UUID/OID enrollment and preview
  configuration/attestation. No real protected connection in these tests.
- **3 disposable PostgreSQL smoke tests passed**: prepared comparison creation /
  replay / recovery with unchanged commercial data; zero-write viewer/API GETs;
  real session/CSRF API operations using the independent temporary runtime role.
  Identity printed before tests:
  `test_mc1_1ff041d7e7384d47964b2dcb13c28dcf`, 51 migrations.
  The connection allowlist trace contained exactly that database and `postgres`
  (explicit catalog provisioning). Temporary DB and roles were removed. No
  persistent Demo/production connection or checksum probe.
- **2 in-memory SQLite UI/API smoke tests passed** under the patched fresh-process
  runner, including the no-ID entry route and explicit comparison creation.
- Django check/migration drift passed in disposable PostgreSQL and isolated
  memory settings. Affected Python syntax/whitespace and Git diff checks passed.
- Accepted M-E2 36/36 JS evidence and full 43-test PostgreSQL/40-test SQLite
  evidence retained: no UI, JS or business implementation changed, so those
  expensive suites were not repeated. No full regression suite.

## Operator commands

DB-free boundary tests:

```powershell
.\venv\Scripts\python.exe -B -m unittest scripts.tests_management_test_isolation scripts.tests_management_preview
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_foundation --checks
```

To run a selected management UI regression in PostgreSQL, explicitly authorize
only the disposable factory (this flag supersedes older checkpoint commands):

```powershell
.\venv\Scripts\python.exe -B -c "from apps.management.verify_strategy_foundation import main; main(test_labels=['apps.management.tests_strategy_ui'],runtime_tests=True,publication_tests=True,api_tests=True)" --provision-disposable
```

Use `--sqlite` instead for in-memory SQLite. Normal preview startup, daily
operations and current 8901 state are unrelated to this provisioning command.
Do not run old fresh-fixture HTTP verification against an established preview:
its pre-existing fresh-only check still rejects that usage. This patch does not
authorize policy changes, account reset, readiness-negative grant changes or
rebuilding the current preview.

## Preservation and decision

No original PostgreSQL or persistent Demo connections were opened in M-E2.1.
No protected database preservation probes were used. Preservation evidence is
the strict connection allowlist, local source/file hashes and unchanged process
identities, rather than a claim based on querying those databases.

Both applications remained running: persistent Demo 8900 PID 37632 and management
preview 8901 PID 35848. No restart, login/session mutation, policy change,
comparison #2 change, credential operation, profile/source-pin update or preview
database connection was needed. Current signed preview source remains compatible
because verification-only files are outside its application fingerprint.

Original SQLite SHA256 remains:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 and all other approved source preserved. Index remains empty;
no staging, commit or push. No persistent migrations, DDL/grants, Gate V2,
Prepare Day, reset or generation switch.

**GO for owner review/source closeout of M-E2 with this safety patch included.**
This does not approve deployment. Live successful-creation visual UAT still
requires separately approved draft fixtures; the current no-draft state remains
unchanged. Stop after owner review.
