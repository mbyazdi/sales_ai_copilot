# M-E4B F1 — Control Center Visual Polish

Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`, fast-track.
Continues `MANAGEMENT_STAGE_M_E4B_STRATEGY_CONTROL_DRAFT_UI.md`.
Page-only refinement. Source remains uncommitted; owner visual approval required.

## Scope and exact changed files

- `templates/management/strategy_control.html`
- `static/management/css/strategy_control.css`
- `static/management/js/strategy_control.js`
- `apps/management/tests_strategy_control_ui.py`
- `apps/management/js_tests/strategy_control.test.cjs`
- This new versioned checkpoint.

No business services, models, migrations, APIs, shared styles, M-01 or M-04 source
changed. No publication/rollback actions. The JS changes are confined to native
navigation disclosure/responsive focus and presentation classes/selection labels.
Draft controller, CSRF, CAS, immutable-version checks and pending/recovery paths
are unchanged.

## Before / after

Inspected the owner's genuine 390/768/1440 Control screenshots from
`venv/management-preview-live/me4b-artifacts/`. These became available after the
earlier checkpoint's timed-out capture. Preserved verified copies in the new
task artifact folder, without changing existing screenshot files.

- Mobile: replaces the tall three-row management navigation with a compact native
  details/summary disclosure. Current page remains named while collapsed; expanded
  navigation retains all destinations and `aria-current`. Native keyboard operation,
  focus-visible styling and explicit responsive focus transfer are retained.
- Tablet: at widths up to 900px navigation uses the full-width compact bar, freeing
  content width previously consumed by the sidebar. Desktop retains its sidebar.
- Mobile priority rows: identity on its own row; score and subdued remove action
  share the next row in natural RTL order. Numeric/select/add/remove controls retain
  comfortable 44px targets. Destructive styling is quieter, with clear Persian copy.
- Desktop: smaller card/form gaps, aligned row areas, less status/card padding and
  a compact target section. No dense multi-column product form or new information.
- Explicit product/brand/category/promotion selection labels replace generic copy.
  Target help explains the unachieved portion; promotion help clarifies quantity-one
  evaluation. Scoring definitions and business semantics are unchanged.
- Control-only cache versions updated. No changes to global navigation or M-04.

## Focused executed checks

- **28 PostgreSQL tests passed**: seven Control Center UI/command tests, 17 existing
  frozen-comparison/creation UI tests, three independent-runtime/concurrency tests
  and real-session mutation-CSRF regression.
- **24 in-memory SQLite tests passed**, Control Center and M-04 UI only.
- **76 JS tests passed**: existing editor/recovery/comparison/overview tests plus
  compact-navigation focus, preserved destinations/layout and explicit-zero
  save/fresh-editor-reload checks.
- **23 DB-free isolation/preview tests passed**.
- Django check, migration drift, affected Python/JS syntax and whitespace checks
  passed. No full suite; no new migration.

Disposable PostgreSQL: `test_mc1_d67f63dba43c41898a1f0d2beec96eef`, 51 migrations.
Temporary database/test roles removed. Guarded connection trace contained only
that exact database and the explicitly authorized `postgres` provisioning catalog.
Neither protected business database was connected, including read-only probes.

Save/reload, explicit zero, revision/UUID conflicts and GET recovery are covered
by disposable tests. No draft was saved in the established live 8901 preview.

## Genuine screenshot evidence

Root:
`D:\py project\sales_ai_copilot\venv\management-preview-live\me4b-polish-artifacts\`

| Width | Before | After |
| --- | --- | --- |
| 1440 | `before/01-M02-Control-Desktop-1440.png` | `after/01-M02-Control-Desktop-1440.png` |
| 768 | `before/02-M02-Control-Tablet-768.png` | `after/02-M02-Control-Tablet-768.png` |
| 390 | `before/03-M02-Control-Mobile-390.png` | `after/03-M02-Control-Mobile-390.png` |

All six files exist and were visually inspected. Before files are byte-verified
copies of the owner-reviewed screenshots. After files were captured from real
authenticated Edge against 8901 with no API interception or fabricated data.
Authenticated overflow checks passed at 390/768/1440; mobile score/remove row
alignment and 44px heights passed. RTL and navigation identities passed.

All five M-04 regression screenshots from the same authenticated run have SHA256
identical to the original approved screenshot files. Originals were not overwritten.
Saved order, separate score/priority, tabs, disclosure and error handling remain
covered by the unchanged M-04 UI/JS tests.

First capture stopped after the three valid Control screenshots when an added
native-disclosure Enter-key automation check timed out. This is partial browser
evidence, not a claim that the entire script passed. A focused retry explicitly
brings the page to the foreground and tests native Space activation; final
keyboard/capture status must be recorded from its actual result below.

Focused retry result: Node/Edge and signed health passed; normal manager login
was not completed within the helper's waiting period. No new authenticated
keyboard evidence was obtained. **Native navigation keyboard acceptance remains
unverified on the authenticated page.** No automatic credential extraction or
session injection was used to get past that boundary. The first run's genuine
three-width screenshots and completed layout checks remain valid partial evidence;
neither complete script success nor owner visual acceptance is claimed.
The local-edit/error walkthrough later in that browser script was not reached;
its behavior is covered by Django/JS tests, not claimed as a completed browser check.

Operator retry (ignored local helper; keeps original artifacts untouched):
`node venv/me4b_polish_capture.cjs --manual-login --control`.
Sign in normally in its new Edge window. Final manual checks: expand/collapse
navigation with Space/Enter, tab through all destinations, resize while focused,
and inspect the rule input/add/remove actions. Save testing remains restricted
to disposable fixtures; the established 8901 policy has not been changed.

No live strategy/commercial POST was issued. Normal owner login/session activity
is allowed only in the isolated preview. No manager password was read or printed.

## Isolation and preservation

Preview: `http://localhost:8901/management/strategy/control/`.
Exact TEST database `test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a` retained.
Signed source pin advanced only through an explicit reviewed private transition:
`me4b-polish-reviewed-source-transition.json`. Read-only startup readiness passed.
8901 gracefully restarted through the existing authenticated helper, PID
27424 -> 1836. New source fingerprint:
`e7c7fdcb8e547836b3a5ac1c5ba22694d03f7a745799b355b8c3c52774be8a9e`.

Guarded read-only before/after reconciliation matched all preview public tables
except normal sessions/auth_user.last_login, plus sequences and protected runtime,
owner and UAT credential files. Policy/history/comparison #2 and commercial data
were preserved. Private evidence/helpers/screenshots remain ignored under venv.

Protected 8900 remains PID 37632; no restart or database connection. No original
PostgreSQL access, Gate V2 activation, Prepare Day, reset or generation change.
Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Prior unrelated work, including DEMO-02, is retained; index empty. No staging,
commit or push. Stop for owner visual review; no next management stage.
