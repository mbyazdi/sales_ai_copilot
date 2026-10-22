# Stage M-E4B F2 — Interactive Browser Acceptance

Date: 2026-10-20. Baseline V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Branch fast-track. M-E4B/F1 visual direction is owner-approved. This task completes
interaction acceptance without changing the existing preview's policy or records.

## Exact source additions

- `apps/management/tests_strategy_control_browser.py`
- `scripts/verify_strategy_control_browser.cjs`
- This checkpoint.

No existing application, UI, service, API, model, migration, shared stylesheet or
M-04 file changed. No application defect was found. Prior approved uncommitted
work is retained. No staging, commit or push.

## Separate disposable browser boundary

The opt-in Django TransactionTestCase uses the M-E2.1 guarded runner to provision
an exact UUID/OID/marker-enrolled PostgreSQL database and independent owner/runtime
roles. Only owner-side fixture setup creates synthetic source records. The HTTP
server and normal manager session run under the least-privilege publication runtime.
Runtime has no reference-table modification or schema-creation privileges.

A fresh loopback WSGI server binds an available ephemeral port, excluding 8900/8901.
There is no change to persistent Demo settings, TEST preview settings, middleware,
readiness or authentication. Strategy commands retain their top-level transaction
boundary. A signed fixture-only HTTP attestation verifies the actual database and
runtime role in the server thread before browser login. The Node helper also limits
requests to the supplied fixture origin and rejects protected listener ports.

Synthetic manager/nonstaff credentials are generated within the test and passed
through the subprocess stdin pipe. Never CLI arguments, environment, files, logs or
reports. Neither UAT password nor browser cookie is extracted. A fresh headless Edge
profile performs ordinary Django login, server-issued CSRF and DB-backed sessions.

The fixture has 105 extra products, brands, categories and promotions each, plus
one existing inactive reference. They are not added to any existing database or
recommendation shortlist. These rows exercise actual bounded reference pagination.

## Genuine browser interaction matrix

All 15 scenario groups passed against real Django HTTP and PostgreSQL:

| Scenario | Result / evidence |
| --- | --- |
| Normal manager login and CSRF | PASS; absent CSRF rejected with 403/CSRF_FAILED |
| Navigation Enter, Space, Tab | PASS; native disclosure opens/closes and focuses first destination |
| Reference selection and pagination | PASS; product, brand, category and promotion pages exceed 100 choices |
| Numeric/target/promotion editing | PASS; actual keyboard input, retained field focus, Persian dirty state |
| Invalid numbers | PASS; out-of-range, fractional, negative and empty inputs show Persian errors without POST |
| Duplicate rules | PASS; existing choices excluded; DOM-tampered duplicate rejected before POST |
| Deletion and reset | PASS; explicit zero differs from deletion; remove restores focus; confirmed reset restores captured config |
| Save, reload, exact replay | PASS; real inactive draft persisted, zero survives fresh GET/editor reload, identical command returns replay |
| 390/768/1440 | PASS; RTL, no horizontal overflow/clipped form controls, correct responsive navigation and resize focus |
| Stale revision | PASS; second real command advances revision; old editor gets 409, retains edits and requires explicit refresh |
| Commit followed by lost response | PASS; CDP drops actual server response, not its contents; reload sends no POST; GET recovers original committed version |
| Request lost before commit | PASS; real recovery GET returns 404; no automatic retry; explicit retry sends identical UUID/body |
| Unresolved and nonexistent references | PASS; inactive existing ID remains visible and saved; nonexistent ID receives actual server validation failure with edits retained |
| Same UUID / different intent | PASS; actual 409 leaves pending evidence; mismatched recovery cannot claim success or unlock editing |
| Logout and nonstaff | PASS; normal logout/login; active nonstaff gets actual page/API 403 and no editor bootstrap |

Network faults are deliberately injected at the CDP request/response boundary in
the disposable fixture only. No successful API responses, comparison data, ranks
or validation errors are fabricated. Duplicate/nonexistent-choice tampering is an
explicit negative test, distinguished from normal selection. Real server receipts
and immutable-version GET validation remain authoritative.

The earlier F1 keyboard gap did not reproduce with complete native key dispatch
(including key text) and explicit headless page-focus emulation. No application
keyboard fix was required. During harness development, a malformed selector and
an asynchronous wait for a recovery control were corrected; neither was an app
defect. Final evidence is from a clean complete passing run.

## Final executed validation

- **29/29 PostgreSQL tests passed**, including the real-browser test, existing
  Control Center and M-04 UI tests, real-session CSRF, independent-runtime commands
  and concurrent publication/rollback regressions.
- **15/15 browser scenario groups passed**, zero browser exceptions.
- **76/76 management JS tests passed**.
- **23/23 DB-free isolation/preview tests passed**.
- Django check, migration drift, affected Python/Node syntax and whitespace checks
  passed. No full suite. No application/schema changes.
- Earlier F1 SQLite results remain applicable because application source is
  byte-identical; no SQLite database was opened for F2.

Reproduction (explicitly disposable only):

```powershell
$env:STRATEGY_BROWSER_ACCEPTANCE='1'
.\venv\Scripts\python.exe -B -c "from apps.management.verify_strategy_foundation import main; main(test_labels=['apps.management.tests_strategy_control_browser','apps.management.tests_strategy_control_ui','apps.management.tests_strategy_ui','apps.management.tests_strategy_api.StrategyAPIPostgresTests','apps.management.tests_strategy_api.StrategyAPITests.test_all_mutations_enforce_missing_invalid_and_valid_csrf'],runtime_tests=True,publication_tests=True,api_tests=True)" --provision-disposable
```

The browser test is skipped without its explicit environment opt-in. Do not invoke
the Node helper against an existing preview or supply real credentials manually.

Final fixture database: `test_mc1_6a1e692fa53c43f98c57809ef39a9808`, 51 migrations.
Temporary browser server: `http://localhost:13079`; stopped after validation.
Database and independent roles removed by the runner. Connection allowlist trace:
only that disposable database and the explicitly authorized `postgres` provisioning
catalog. No original PostgreSQL or persistent Demo connection/probe.

After browser execution, the test verifies all non-strategy source/commercial rows
have identical digests, except normal session/last-login effects. It checks inactive
draft versions and SAVE_DRAFT events correspond, immutable history remains and the
active pointer is still null. No recommendation, stock, pricing, Visit, request or
commercial history write is permitted by the browser role or observed in the digest.

## Redacted evidence and genuine screenshots

Final artifact directory:
`D:\py project\sales_ai_copilot\venv\me4b-f2-artifacts\93d9b8eb5dbf493f89ee6f463754bb4c\`

- `browser-proof.json`: complete PASS matrix, fixture identity, screenshot names,
  allowed mutation paths, zero browser exceptions. No password, cookie, raw command
  payload, private profile or signing key.
- `01-Control-390.png`
- `01-Control-768.png`
- `01-Control-1440.png`

These are actual browser renders of the separate synthetic fixture after confirmed
draft save/reload. They are not evidence that a draft was saved on the existing
8901 preview. Existing M-02/M-04 screenshots were never overwritten.

## Existing preview / Git preservation

Existing preview unchanged: `http://localhost:8901/management/strategy/control/`.
Signed TEST identity `5d24c8a7-2361-4bcf-aa3b-6ea3fd0efe5a`, database
`test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`, PID 1836 and source fingerprint
`e7c7fdcb8e547836b3a5ac1c5ba22694d03f7a745799b355b8c3c52774be8a9e` retained.
No 8901 restart, login, draft save, policy/comparison mutation or session operation.
Fresh guarded read-only before/after reconciliation matches its policy/history,
comparison #2, source/commercial tables, sequences and protected credential files.
Normal session/last-login fields are excluded by that existing read-only helper;
this task sends no authenticated or mutating HTTP requests to 8901 at all.

Protected 8900 still PID 37632; no connection, restart or modification. No Gate V2,
Prepare Day, reset or generation switch. Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index empty.
All pre-existing source, unrelated DEMO-02 and protected artifacts preserved.

## Decision

**GO for M-E4B closeout / owner acceptance.** No remaining application defects or
interactive browser blockers found. This does not authorize committing, deploying,
changing current preview policy or proceeding to another management stage.
