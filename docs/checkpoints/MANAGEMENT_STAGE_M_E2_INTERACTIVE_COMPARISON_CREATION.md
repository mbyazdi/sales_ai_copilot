# Stage M-E2 — Interactive Frozen Comparison Creation

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`, fast-track.
M-C1 through M-E1.1 retained. Source-only; owner review pending, no commit/push.

## UI boundary and exact files

Modified relative to approved M-E1.1:

- `apps/management/urls.py`
- `apps/management/strategy_ui_views.py`
- `apps/management/tests_strategy_ui.py`
- `templates/management/strategy_comparison.html`
- `static/management/css/strategy.css`
- `static/management/js/strategy_comparison.js` (skip viewer bootstrap on no-ID page)
- `scripts/management_preview.py` (exact entry-route allowlist and source pins)
- `scripts/capture_management_comparison.cjs` (read-only creation capture mode)

Added:

- `templates/management/_strategy_comparison_create.html`
- `static/management/js/strategy_comparison_create.js`
- `apps/management/js_tests/strategy_comparison_create.test.cjs`
- This checkpoint.

No strategy API/service, evaluator, pricing, model or migration changed.

The no-ID entry route is `/management/strategy/comparisons/`. It reuses the
authorized M-04 shell and opens the creation disclosure. Historical detail URLs
are unchanged; each detail includes the compact, initially collapsed creation
panel. The accepted Before/After viewer and its mobile tabs remain intact.
Creation controls use the separate strategy-manage hook on the freshly loaded
actor. View-only users retain historical viewing and a read-only explanation.
Actual mutation authorization remains enforced independently by the API.

## Selection, preparation and explicit creation

1. GET `overview/` supplies the current draft ID and revision. No draft means
   disabled creation and honest guidance. No implicit draft or policy creation.
2. GET `options/?kind=salespersons` supplies active sellers. Customer options
   request `kind=customers`, the chosen seller and evaluation date. The API
   applies actual date-scoped assignments. Both lists use bounded pages of 100
   and explicit load-more buttons; late customer responses are discarded.
3. Initial date is server-derived Asia/Tehran today; the manager explicitly
   selects a seller/customer. The only proposed version is the current draft.
4. «آماده‌سازی مقایسه» refreshes overview, rejects a changed revision/draft,
   and obtains exact `preview_context` through read-only options. Its customer,
   seller, draft, date, revision and source fingerprint must match the selection.
5. «ایجاد مقایسه» generates a UUID v4 and sends exactly that authoritative
   context plus `command_uuid` to existing POST `comparisons/`, with session and
   masked Django CSRF token. Changing selections invalidates preparation.
6. Only a confirmed PREVIEW result with matching fingerprint/revision and a
   valid comparison ID navigates to `/management/strategy/comparisons/<id>/`.

No ranking, price, discount, stock or source-fact calculations in the browser.
All option labels and status/error text use safe text nodes. Server error codes
map to fixed Persian guidance, without displaying SQL/raw evidence.

## Uncertain-command recovery

Before POST, the exact serialized body is persisted and read back in localStorage
under a versioned actor-scoped key. Missing/unavailable/tampered storage fails
closed before dispatch. Reload never automatically resends a POST and blocks
new creation until the saved command is resolved. Duplicate clicks are guarded.

«بررسی نتیجهٔ فرمان» uses only GET `commands/<uuid>/`. Committed matching
PREVIEW results open the frozen detail. A 404 is explicitly NOT proof of
cancellation: the operation may still be running. Only then is an explicit
«تلاش مجدد با همان فرمان» offered; it sends identical UUID/body, never fresh
terms. No background POST retry, polling or silent replacement of pending intent.

Definitive initial 400/401/403/404/409 responses clear uncommitted local preparation
and require renewed evidence. Network/timeout/unreadable-response uncertainty
retains the command. Once uncertainty exists, errors on a later explicit retry
do not discard its envelope. Ambiguous/conflicting evidence remains blocked for
operator reconciliation; there is no new cancellation/abandonment API here.

## Focused evidence

- **43/43 disposable PostgreSQL UI/API tests passed**. Includes 17 UI tests,
  real session/CSRF, assignment scoping, preparation/create/replay/recovery,
  unchanged commercial rows, frozen result/history, stale evidence and existing
  concurrent publication regressions. Independent least-privilege runtime test
  role; unique DB `test_mc1_38c0c185011d47ac8efe8ece1bdebdc4`, 51 migrations,
  all disposable roles/database removed after validation.
- **40 SQLite tests passed, 3 PostgreSQL-only tests skipped**, in-memory database
  only. Original SQLite was never opened by the test runner.
- **36 JS tests passed**: 21 accepted viewer regressions plus 15 creation tests
  covering authoritative selection, no draft/assignment, stale preparation,
  CSRF header, explicit POST/navigation, pending reload, GET recovery, 404/exact
  retry, mismatched results, storage tampering, duplicate clicks and safe sinks.
- **6 DB-free preview boundary tests passed**. Django check/migration drift,
  affected Python/JS syntax and whitespace checks passed. No full suite.

Important audit exception: the reused PostgreSQL runner performs read-only
`persistent_digest` probes against `sales_ai_demo_db` before/after disposable
tests. This was contrary to M-E2's stricter no-persistent-access instruction,
although no persistent writes occurred and its all-table/sequence hashes matched.
The exception was disclosed during work. No further persistent DB connections
were used; future no-access tasks must avoid that runner's preservation probe.
Original PostgreSQL was never connected.

## Live preview and genuine screenshots

Entry: `http://localhost:8901/management/strategy/comparisons/`
History: `http://localhost:8901/management/strategy/comparisons/2/`
Use normal stable manager login; credentials unchanged, no forced session or
password extraction. Live policy has an active version and NO draft; no policy
or comparison was created there. Success was validated only with disposable
fixtures, not represented as a successful live browser creation.

Only verified 8901 application restarted; same DB, roles, keys, cookies, accounts
and comparison evidence. PID 35848. Source-pin transition evidence is protected
in `me2-reviewed-source-transition.json`; startup validation remains fail-closed.
8900 application PID 37632 was not stopped or restarted.

Capture command:
`node scripts/capture_management_comparison.cjs --manual-login --creation`

All images are under
`D:\py project\sales_ai_copilot\venv\management-preview-live\me2-artifacts\`:

1. `01-M04-Desktop-1440.png`
2. `02-M04-Tablet-768.png`
3. `03-M04-Mobile-390.png`
4. `04-M04-Mobile-Before-390.png`
5. `05-M04-Mobile-Factors-390.png`
6. `06-ME2-No-Draft-Desktop-1440.png`
7. `07-ME2-No-Draft-Tablet-768.png`
8. `08-ME2-No-Draft-Mobile-390.png`

Real browser passed all three widths/no horizontal overflow, comparison 2 API
ordering, separate saved score/effective priority, tabs, keyboard selection,
disclosures, no-draft disabled controls, new entry route, 404 and normal logout.
Zero browser exceptions; only login/logout POSTs, no strategy/commercial POSTs.
`browser-proof.json` records the completed run. UI screenshots contain real
current no-draft state; no mock API interception or fabricated success.

## Preservation and limits

Read-only before/after management-preview digest covers all public tables except
normal session rows/auth_user.last_login, plus all sequences. Protected manager
UAT hash, account-signing key and DB credentials are compared separately.
Current policy, comparison 2, commercial rows and pre-existing source are retained.

SQLite expected SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No staging/commit/push; unrelated DEMO-02 and approved work preserved. No
persistent migrations/grants/writes/restart, Gate V2, Prepare Day, reset or
generation switch. No policy editor, publish/rollback controls or Impact UI.

Live successful-creation UAT remains unavailable until a draft fixture is
separately approved for the current preview or another isolated browser fixture
is authorized. No automatic draft was created to make screenshots look complete.
Stop here for owner review.
