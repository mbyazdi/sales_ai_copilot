# Stage M-E3 — M-01-B Strategy Overview

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`, fast-track.
Read-only management UI. Source-only; owner visual acceptance pending.
Existing approved M-C1–M-E2.1 work and M-04 surfaces preserved.

## Exact source boundary

Modified:
- `apps/management/urls.py`
- `apps/management/strategy_ui_views.py`
- `scripts/management_preview.py`
- `scripts/capture_management_comparison.cjs`

Added:
- `templates/management/strategy_overview.html`
- `static/management/css/strategy_overview.css`
- `static/management/js/strategy_overview.js`
- `apps/management/tests_strategy_overview_ui.py`
- `apps/management/js_tests/strategy_overview.test.cjs`
- This checkpoint.

No API/service/evaluator/model/migration/pricing changes. Shared M-04 CSS/JS,
comparison templates, creation/recovery logic and global navigation unchanged.

## Page and design mapping

Route: `/management/strategy/`, named `strategy-overview`.
Reuses base.html, shared typography/tokens, dark page-local management sidebar,
normal sessions/CSRF logout and M-04 visual language. New styles are scoped to
`.strategy-overview`; no global redesign. Compact responsive sections:

1. Current active version, draft status, comparison count and revision cards.
2. Four-stage schematic: saved shortlist → manager priorities → effective order
   → fresh selling context. Saved engine evidence and old contexts are retained.
3. Current active product/brand/category priorities, including explicit zero.
   Native disclosure explains non-stacking specificity.
4. Quantity-target influence and promotion-emphasis points, clearly not actual
   customer contributions, percentages or price/discount changes.
5. Configuration-data availability and fresh-context integration status;
   customer inventory/pricing explicitly not evaluated in this overview.
6. Causal sales uplift, attributable profit and conversion remain unavailable;
   no numeric placeholder, fabricated chart or revenue claim.
7. Version history with creation time in Persian/Asia-Tehran formatting, current
   active/draft status and whether publication was ever recorded.
8. Direct links to `/management/strategy/comparisons/` and explicit GET refresh.

Approved M-01-B bitmap was not identifiable in repository/local reference files.
This follows the owner's approved layout direction and M-04 components; no
pixel-perfect bitmap fidelity is claimed.

## API-to-UI contract and limitations

- GET `overview/`: active configuration and version, draft ID, revision, version
  and comparison counts, integration flag, limitations. Missing mandatory values
  fail closed, rather than being replaced by zero. Null active means the API's
  neutral configuration; null draft means no draft, with no initialization.
- GET `options/`: actual scopes, bounds and combined cap. Point values/bounds
  are never hardcoded in the renderer. No client-side ranking/price calculation.
- Bounded GET `options/?kind=...&after_id=0&limit=100`: names for active-reference
  product/brand/category/promotion rules only. Missing/inactive/unreturned names
  fall back to the configured stable ID with an explicit notice; no inferred
  eligibility or current availability. Historical versions do not use current
  labels as a substitute for frozen historical evidence.
- GET `versions/?after_id=...&limit=6`: existing ascending-ID pages, explicitly
  labelled oldest-to-newest, with user-triggered pagination. The API exposes
  `created_at` and `published`, NOT publication timestamps or the full rollback
  event sequence. Creation times are never relabelled as publication times.
- Version hashes, raw configs/audit evidence, author IDs and internal algorithm
  identifiers are not rendered. API text enters textContent only.
- This is a current multi-endpoint overview, not one frozen comparison snapshot.
  A fresh explicit refresh can observe changed policy state. M-04 remains the
  authoritative frozen before/after viewer. Publication/editing/rollback,
  targets, Impact analytics and promotion mutation are outside this task.

GET-only fetches use same-origin sessions, no-store and redirect rejection.
No mutation payload, local pending command, implicit policy initialization,
background polling or POST retry. Loading/neutral/empty/reference-unavailable,
permission and 401/403/404/409/503 error states are Persian. Authorization errors
hide content; failed history pagination preserves existing rows and allows only
explicit GET retry. Late responses cannot overwrite a newer refresh.

## Focused validation

- **10/10 disposable PostgreSQL tests passed**: 8 new overview UI/API tests plus
  existing M-04 zero-write GET/HEAD and independent least-privilege runtime
  session/API regression. Authorized/unauthorized shell, current capability,
  POST rejection, no first-use initialization, all reference GETs, actual config/
  counts/publication flags, frozen comparison preservation and commercial data.
- Unique database `test_mc1_bfabcccb9a6f4d699fce0e230e2454b3`, 51 migrations;
  temporary DB and roles removed. M-E2.1 driver guard connection trace contains
  only that disposable DB and the explicitly authorized `postgres` provisioning
  catalog. No persistent Demo/production connection or preservation probe.
- **51/51 JS tests passed**: 15 new overview tests and 36 accepted M-04/creation
  regressions. Covers actual server values, zero versus missing, explicit-zero
  rules, history semantics, XSS-safe projection, unavailable labels, errors,
  bounded read requests, pagination failure and stale-response suppression.
- **23/23 DB-free isolation tests passed**. Django check, migration drift,
  affected Python/JS syntax and Git whitespace checks passed. No full suite.

## Isolated preview

Page: `http://localhost:8901/management/strategy/`
Comparisons: `http://localhost:8901/management/strategy/comparisons/`
Historical comparison: `http://localhost:8901/management/strategy/comparisons/2/`

Same normal manager account, DB, roles, signing keys, cookies and history.
Exact DB: `test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`.
Only identity-verified 8901 app gracefully restarted; new PID 38812.
Protected `me3-reviewed-source-transition.json` records the explicit source-pin
advance; new overview source files are included in startup fingerprinting.
Exact page added to the existing preview route allowlist. No startup seeding,
migration, repair or silent source-check bypass.

Capture command:
`node scripts/capture_management_comparison.cjs --manual-login --overview`

Artifact directory:
`D:\py project\sales_ai_copilot\venv\management-preview-live\me3-artifacts\`

Primary expected screenshots (report success only after real capture):
- `06-M01-Overview-Desktop-1440.png`
- `07-M01-Overview-Tablet-768.png`
- `08-M01-Overview-Mobile-390.png`

First genuine capture attempt reached the normal login window but timed out
waiting for owner sign-in after three minutes. No screenshot or browser-layout
PASS is claimed from that attempt. Node/Edge and signed preview health passed;
the precise blocker is authenticated local browser access, not a fabricated
layout result. Owner was asked whether to open another capture window. The
same command can be run locally; enter the password only in its browser window.

The helper also rechecks M-04, keyboard/disclosures and 404 handling, compares
actual overview counters/config/history to actual APIs, and forbids business
POSTs. Only normal owner browser login/logout may write isolated auth state.
No password extraction, forced session or synthetic browser data.

## Preservation and review

Before-state captured only through M-E2.1 `connect_preview`, with exact offline
and live TEST-profile identity checks. Reconciliation covers every public table
except normal session rows/auth_user.last_login, plus all sequences; protected
UAT/account/DB credential hashes are checked separately. No persistent database
digest/probe is used. Persistent Demo 8900 PID 37632 never stopped or restarted.
Final guarded reconciliation matched all those management-preview tables,
sequences and protected credential hashes; active policy, history, comparison 2
and commercial data are unchanged.

SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02, private files and all other approved changes preserved.
No staging, commit, push, persistent migrations/DDL/writes/connections,
Gate V2, Prepare Day, reset or generation switch.

Stop here for owner visual review. Exact publication audit timestamps/events,
measured Impact, policy editing and deployment remain outside this UI task.
