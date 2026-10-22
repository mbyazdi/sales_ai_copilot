# Stage M-E1.1 — M-04 Visual Refinement & Mobile UX

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`, fast-track.
UI-only refinement; backend, API, evaluator, schema and frozen evidence unchanged.
Owner visual acceptance pending. No commit or deployment to persistent Demo.

## Exact task boundary

Changed relative to the approved, uncommitted M-E1 implementation:

- `templates/management/strategy_comparison.html`
- `static/management/css/strategy.css`
- `static/management/js/strategy_comparison.js`
- `apps/management/js_tests/strategy_comparison.test.cjs`
- `apps/management/tests_strategy_ui.py`
- `scripts/capture_management_comparison.cjs`
- This checkpoint.

No other pre-existing source/test/document changes belong to this task.

## Presentation and interaction

- Scoped body/product text 14px; secondary text 12–13px, improved contrast and
  1.85 line height. Header max 24px. Header/context/section gaps reduced.
- Desktop retains two balanced ranking columns and dark section sidebar.
- At <=600px, accessible Before/After tabs show one existing ranking list.
  Default: «بعد از تغییر». Click, native Enter/Space and RTL arrow/Home/End
  navigation; roving tab stop, selected state and labelled tabpanels.
- Above 600px both panels return, with tabs hidden. Focus moves to a visible
  panel/tab when resizing would otherwise hide its current location.
- Largest positive movement supplied by the server is highlighted, with ties
  resolved by the existing frozen After order. This selects explanation focus
  only; neither list is sorted or reranked by JavaScript.
- Rank movement and effective priority are prominent. Saved engine score stays
  separately labelled. All seven original factor values, ranks and Persian
  reasons remain available in native details: desktop initially expanded,
  mobile initially collapsed. Manual disclosure choice survives product
  selection and explicit read refresh within the same viewport mode.
- Lengthy «مبنای خواندن این مقایسه» is a collapsed native disclosure. The
  simulation/no-measured-sales warning remains visible above the comparison.
- Frozen commercial evidence remains a separate disclosure. Missing facts,
  historical versions, score semantics and all error/loading states are retained.

## Focused validation

- **13/13 PostgreSQL UI tests passed**, including frozen API order/contributions,
  label history, authorization, no-write GET/HEAD, POST rejection and new tab /
  disclosure template semantics. Unique disposable database and independent
  runtime roles; 51 migrations applied only there; database/roles removed.
- **21/21 JavaScript tests passed**: original 15 frozen-data/security/error tests
  plus six mobile keyboard, focus/resize, disclosure and movement-highlight tests.
- **6/6 DB-free preview boundary tests passed**.
- Django check and migration drift passed in disposable runner and isolated
  preview readiness. Python AST/JS syntax and scoped whitespace checks passed.
  `git diff --check` passed. No full suite or unchanged backend suite rerun.
- Persistent Demo all-table/sequence digest was unchanged across PostgreSQL tests.

## Preview and capture diagnostics

Page: `http://localhost:8901/management/strategy/comparisons/2/`.
Normal stable `manager` account and password retained; no password extraction,
reset, forced login, cookie injection or session fabrication.

Exact existing preview database:
`test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`.
Identity: `5d24c8a7-2361-4bcf-aa3b-6ea3fd0efe5a`.
Only its verified application was gracefully restarted (PID 39844), retaining
DB, signing keys, cookies, accounts and comparisons. Explicit reviewed source-pin
transition is protected in `me1-1-reviewed-source-transition.json`; startup
source checks were not disabled. Persistent Demo PID 37632 was untouched.

Node v24.19.0 and installed Edge are available. No active previous capture process
or old screenshots was found; old artifacts contained preservation evidence only.
The old helper concealed precise errors, used an obsolete stacked-mobile check
and had no early directory/availability diagnostic. It now prints environment,
health, exact output directory, stage-specific failures and each saved PNG path.
It never reads the protected account/password file. Normal owner login is required
in a separate visible Edge window, brought to the foreground; a three-minute
timeout is explicit. Prior screenshot files are preserved in the old directory.

Commands from the project directory:

```powershell
node scripts/capture_management_comparison.cjs --diagnose
node scripts/capture_management_comparison.cjs --manual-login
```

Output directory:
`D:\py project\sales_ai_copilot\venv\management-preview-live\me1-1-artifacts\`

Genuine captures already produced and visually inspected:

1. `01-M04-Desktop-1440.png`
2. `02-M04-Tablet-768.png`
3. `03-M04-Mobile-390.png`
4. `04-M04-Mobile-Before-390.png`
5. `05-M04-Mobile-Factors-390.png`

Browser checks before these captures verified actual API/list ordering, separate
70.0000 / 37.50 summary values, no horizontal overflow at all three widths,
two panels above 600px, After-only mobile default, native factor disclosure
defaults, collapsed limitations and keyboard switching to Before. Initial
keyboard product-selection proof failed after captures: the CDP helper did not
send native Enter text events. Adding those events and explicit settling fixed
the helper without changing application behavior. The final full browser run
**passed**: tab keyboard switch, product selection/focus retention, factor and
commercial disclosure keyboard activation, 404 state and normal POST logout.
Zero browser exceptions and zero business POSTs; only normal login/logout POSTs.
`browser-proof.json` records that completed run beside the images. Actual frozen
order was Before `[1,2,3,4]`, After `[3,1,2,4]`; summary values 70.0000 / 37.50.
Document widths were 1425 at 1440px, 753 at 768px and 390 at 390px, without
horizontal overflow. Images were opened and visually inspected at all widths.

## Preservation and remaining review

Only page-scoped UI, focused tests, capture tooling and this document changed.
No ranking arithmetic, current-data substitution, API mutation or commercial
logic change. Source preservation inventory captured before editing; private
preview data/sequence and credential preservation baseline retained outside Git.
Read-only final reconciliation matched all public tables except session rows and
auth_user.last_login (normal isolated authentication), every public sequence,
protected account/role credentials, UAT hash and account-signing key. Frozen
comparisons were unchanged. Only normal isolated login/session state changed.

SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 and prior approved work remain unstaged and preserved.
No original PostgreSQL connection, persistent Demo changes/restart, Gate V2,
Prepare Day, reset, generation switch, migrations, staging, commit or push.

Review mobile After/Before switching, separate score/priority, factor disclosure,
visible simulation warning and historical commercial details at the URL above.
Approved reference bitmap remains unavailable locally; no pixel-perfect fidelity
claim. Stop here for owner visual acceptance; no further management features.
