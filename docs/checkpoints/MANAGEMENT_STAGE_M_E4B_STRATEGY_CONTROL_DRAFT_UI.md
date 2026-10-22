# Stage M-E4B — Strategy Control Center Draft Editor

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`, fast-track.
Source-only. Owner review required; no commit, push or persistent deployment.

## Route, authority and visual boundary

`/management/strategy/control/` reuses base.html and the approved management
sidebar/tokens. The overview exposes its link only with strategy-manage access.
The page requires strategy-view; a view-only shell has no save/recovery actions.
Server API authorization remains authoritative, including current role checks.

No identifiable M-02-A desktop/mobile bitmap was available locally. This implements
the owner's approved functional layout using M-01/M-04 visual components. Exact
visual fidelity and final desktop/mobile acceptance await the reference handoff
and owner review. No replacement mockup or pixel-perfect claim is made.

## Exact source boundary

Modified relative to the task's captured working-tree baseline:

- `apps/management/urls.py`
- `apps/management/strategy_ui_views.py`
- `templates/management/strategy_overview.html`
- `static/management/js/strategy_comparison_create.js`
- `apps/management/js_tests/strategy_comparison_create.test.cjs`
- `scripts/management_preview.py`
- `scripts/capture_management_comparison.cjs`

Added:

- `templates/management/strategy_control.html`
- `static/management/css/strategy_control.css`
- `static/management/js/strategy_control.js`
- `apps/management/tests_strategy_control_ui.py`
- `apps/management/js_tests/strategy_control.test.cjs`
- This checkpoint.

No API, service, evaluator, pricing, model, migration or existing shared stylesheet
changed. The narrow M-E2 addition verifies the requested draft identity at entry
and preparation; legacy comparison entry without this hint is unchanged.

## Form and read contract

- GET overview/options and bounded exact-ID version retrieval. Re-read overview
  after initialization to reject a concurrently changed revision/head.
- Existing draft loads its immutable configuration. Without a draft, use an
  UNSAVED local copy of active configuration, including the API's neutral state.
- Product/brand/category integer priority 0–20; per-promotion integer emphasis
  0–5; global target influence 0–5. Strict shape, safe integers and duplicate
  validation support the form; existing server validation is authoritative.
- Explicit zero is preserved. Product > brand > category specificity remains
  non-stacking. The 30-point cap describes each evaluated recommendation, not
  the sum of all editor rows. No ranking or commercial computation in JS.
- Reference requests use pages of at most 100 with explicit additional-page
  controls, monotonic cursor validation and no assumption of complete first page.
  Unresolved configured references retain stable IDs; no inferred deletion,
  deactivation or silently removed rule. Server reference validation still applies.
- Active promotion choices do not imply customer/date eligibility. Actual target
  facts are not available in this form; qualifying contribution is established by
  the existing authoritative comparison workflow, not estimated in the editor.
- Native disclosures, labels, focus-visible styles, focus retention while typing
  and focus restoration after rule insertion/removal. View-only users can inspect
  loaded configuration; mutations remain unavailable.

## Explicit save and recovery

POST only `draft/`, with stable UUID, captured expected revision and exact typed
configuration. Same-origin normal session/CSRF, no-store and redirect rejection.
Before dispatch, verify durable local pending-envelope storage in a separate
actor + host + environment-specific session-cookie-name namespace. UUID/payload
remain immutable across uncertainty and reload. No automatic POST retry.

Success requires SAVE_DRAFT / CONFIGURATION evidence, expected revision step,
and exact immutable version/configuration/config-hash agreement through GET
versions. A failure of those verification reads after an accepted POST preserves
pending state; it cannot be mistaken for a definitive mutation rejection.

Explicit GET command recovery only. Missing evidence is uncertain, not proof of
cancellation. Explicit retry after missing evidence uses the same UUID/body.
Wrong operation, result, configuration, storage or ownership fails closed.
Conflicting UUID retains pending evidence. Initial definitive stale-revision
rejection preserves edits and requires explicit refreshed review before saving.
No silent merge, replacement UUID or pending-command abandonment.

Saving creates a NEW immutable version, changes draft pointer/revision and appends
existing command evidence. Active version and historical versions are preserved.
Replacing an existing draft requires an explicit UI confirmation. Local reset
requires confirmation and does not delete or change any server record.

Comparison navigation checks the current revision/draft and passes only an
expected-draft identity hint to `/management/strategy/comparisons/`. M-E2 reloads
authoritative state, rejects a different hinted draft, and prepares its own source
fingerprint. No automatic comparison creation, publication or rollback.

## Focused executed validation

- **57/57 PostgreSQL tests passed**, including six new Control Center tests,
  existing M-E1/M-E2/M-E3 UI, API, real-session/CSRF, independent least-privilege
  runtime, reconnect replay and concurrent publication/rollback regressions.
- **54 SQLite tests passed; 3 PostgreSQL-only tests skipped**, memory DB only.
- **73/73 JS tests passed**, including 21 new editor tests and one draft-handoff
  regression plus the approved viewer/creation/overview suites.
- **23/23 DB-free preview/isolation tests passed**.
- Django check and migration drift passed; affected Python and JS syntax and
  Git whitespace checks passed. No full suite or schema changes.

Guarded test command:

```powershell
.\venv\Scripts\python.exe -B -c "from apps.management.verify_strategy_foundation import main; main(test_labels=['apps.management.tests_strategy_control_ui','apps.management.tests_strategy_overview_ui','apps.management.tests_strategy_ui','apps.management.tests_strategy_api'],runtime_tests=True,publication_tests=True,api_tests=True)" --provision-disposable
```

Use `--sqlite` instead for isolated memory tests. Disposable PostgreSQL identity:
`test_mc1_da03c2103681484c9c8f1b9fdd2c446c`, 51 migrations. All temporary database
and test roles removed. Guard trace contained ONLY that database and the explicitly
authorized `postgres` provisioning catalog, never either protected business DB.

## Existing isolated preview and preservation

URL: `http://localhost:8901/management/strategy/control/`.
Same TEST database `test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`; no rebuild or seed.
Only the authenticated 8901 app was gracefully stopped and restarted through
reviewed tooling (PID 38812 -> 27424). Protected source transition evidence:
`venv/management-preview-live/me4b-reviewed-source-transition.json`.
New source pin: `fa3343475b710614ea7d1711873bf16336eceb8f0edaf6d8b83b0e26e2f2c0cc`.
New route/assets are explicitly allowlisted/fingerprinted; readiness was not bypassed.
Startup checks are read-only. Normal anonymous HTTP access redirects to Django login.

M-E2.1 guarded read-only reconciliation matched all preview public tables except
normal session rows/auth_user.last_login, plus all sequences and protected runtime,
owner, account/UAT credential files. Policy/history/comparison #2 and commercial
evidence are preserved. Before/after hashes are private ignored artifacts only.

Persistent Demo 8900 retains PID 37632. No connection to original PostgreSQL or
persistent Demo, no restart of 8900, no Gate V2, Prepare Day/reset/generation change.
Original SQLite hash remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. Index empty; prior
unrelated source and DEMO-02 preserved. No staging, commit or push.

## Browser capture and remaining review

Capture command: `node scripts/capture_management_comparison.cjs --manual-login --control`.
Requires normal owner-entered manager login; no password extraction, forced
session or existing browser-cookie reuse. Capture remains subject to successful
authenticated execution; screenshot existence and browser PASS must be reported
only from real output. No live draft creation is authorized or performed.

Executed attempt: Node v24.19.0 and Edge available, output directory created,
signed isolated preview health verified, normal login window opened. Timed out
waiting for owner login/frozen comparison. **No successful screenshots or genuine
390/768/1440 browser layout PASS from this attempt.** The newly spawned capture
browser was closed by the helper; preview remains running. Intended filenames,
not claimed artifacts, under `venv/management-preview-live/me4b-artifacts/`:

- `01-M02-Control-Desktop-1440.png`
- `02-M02-Control-Tablet-768.png`
- `03-M02-Control-Mobile-390.png`

The capture helper's Control mode checks no-draft state against actual overview,
responsive overflow, local edit state and keyboard focus; only normal login/logout
POSTs are permitted. These browser checks remain pending authenticated execution.

Successful draft saving is proven in disposable database tests. Current 8901
remains active-policy/no-draft; no policy/comparison fixture was changed to make
the UI appear populated. Publication/rollback UI, richer target/reference read
projections, exact M-02-A fidelity and deployment remain future approved scope.
