# Stage M-E1 — M-04 Frozen Comparison Viewer

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Source-only implementation. Functional focused validation passed. Browser visual
acceptance/screenshots PENDING secure local manager login; no success fabricated.
No persistent deployment; Gate V2/Prepare Day remain NO-GO.

## Visual authority and scope

M-01-B/M-04 approved image files remain unidentifiable in the repository and
`D:\UI References`. This implements the owner's explicit reconstructed M-04
layout contract; no pixel-perfect image comparison is claimed. Existing shell
has a top header, not a dark global sidebar. A dark page-local section sidebar
implements that visual direction without redesigning shared navigation.

Route: `/management/strategy/comparisons/<id>/`, name `strategy-comparison`.
Anonymous requests use normal login/next redirect. An active authorized manager
passes the existing fresh strategy-view guard; unauthorized pages return a
Persian 403 without an API/data bootstrap. GET/HEAD only. No mutation view/service
or management editing/publication/rollback control was added.

The template extends `base.html`, keeping normal navigation, standard POST logout
and CSRF. Page-local CSS uses shared theme conventions with scoped styling:
compact title/breadcrumb, customer/salesperson/date/version context, frozen
simulation notice, two ranking panels, selectable explanation, commercial
disclosure and limitations. At desktop the panels share a row; the CSS mobile
breakpoint stacks them. Real 390/1440 layout/overflow proof is pending login.

## Frozen API mapping

The only data fetch is GET `/api/management/v1/strategy/comparisons/{id}/` with
same-origin credentials/no-store and no automatic retry. An explicit retry is
another GET. There are no business POSTs, background polling, live product reads,
policy activation, comparison creation or command replay from this page.

- `outputs.before.rows/after_ids`: captured ACTIVE policy result, not saved rank.
- `outputs.after.rows/after_ids`: proposed policy result on identical frozen facts.
- `outputs.movements`: before/after rank and movement; not recomputed in JS.
- Saved `source.base_score`, `saved_rank`, overlay `base_priority`, contribution
  points, `overlay_adjustment`, `effective_priority`: separate, clearly labeled.
- The first upward-moving row in server after-order is initially explained;
  any listed row is explicitly selectable without changing or sorting data.
- Persian explanations come from stored priority/target/promotion reasons;
  stable reason codes remain DOM metadata. No source JSON/digests are displayed.
- Stored quotes/commercial annotations provide the disclosed price/stock evidence.
  Missing remains missing; unknown stock and unavailable stock stay distinct.
  Commercial quantity-one evidence is not Visit/basket mutation authorization.
- Context uses captured date, revision, policy versions and stable identities.
  Actual uplift/revenue/causal impact is explicitly unmeasured, never zero-filled.

Added optional read projection `labels` to the existing comparison response.
`frozen_comparison_labels` reads ONLY the already verified stored capture:
customer `{id,code,name}`, salesperson `{id,code,name}`, and shortlist products
`[{id,code,name}]`. No ORM queries, current-name fallback, contact details, raw
capture or unrelated global policy reference products. Missing historical labels
remain null; client uses existing frozen code/ID. Persistence/digests unchanged.

UI consumes existing orders, exact decimal strings and server contributions;
formatting changes digits only. No client ranking/price/inventory calculation.
Rows validate identities/order consistency and refuse malformed evidence.
Selection retains button nodes/focus. API text is inserted with textContent,
never HTML parsing. Errors 401/403/404/409/503 have fixed Persian explanations;
unknown/network errors are redacted. Empty results and no-JS guidance are explicit.

## Functional evidence

Current isolated comparison 2 was inspected through the authorized frozen service:
before `ME01-P1, ME01-P2, ME01-P3, ME01-P4`; after
`ME01-P3, ME01-P1, ME01-P2, ME01-P4`.
P3: saved score `70.0000`, saved position 3, overlay baseline `10.00`, priority
`20.00`, target `2.50`, promotion `5.00`, adjustment `27.50`, effective `37.50`.
The renderer has no fixture-specific product/value constants.

Tests:
- **38 focused PostgreSQL tests passed**: 12 new UI/projection tests and 26
  existing strategy API/session/CSRF/publication/concurrency regressions.
  Unique OID/comment/endpoint-guarded disposable DB and independent runtime roles;
  51 migrations applied there; resources removed after validation.
- **15 JS tests passed**: frozen order, non-neutral before semantics, separate
  values, selection/focus-node retention, missing facts/labels, empty state,
  XSS-safe text sinks, malformed identities, 401/403/404/409/503, explicit GET
  retry, late-response suppression and URL rejection before fetch.
- **6 existing DB-free preview boundary tests passed**.
- Django check and migration drift passed; graph unchanged at 51. Scoped
  Python/JS syntax, Git whitespace and new-file whitespace checks performed.
- Initial PostgreSQL selection: all 11 then-new tests passed, one old API fixture
  failed on automatic customer INSERT reusing explicitly inserted PK 1. Corrected
  only `APIFixture` sequence bookkeeping with Django sequence_reset_sql for
  Customer, inside disposable test setup. No assertion weakening or app changes.
  Final 38-test selection passed, including that authorization regression.
- No full suite, no application pricing/eligibility/concurrency changes.

## Isolated preview and pending screenshot handoff

Working page URL (normal manager login):
`http://localhost:8901/management/strategy/comparisons/2/`

Exact DB retained: `test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`;
profile identity `5d24c8a7-2361-4bcf-aa3b-6ea3fd0efe5a`. Same account, password,
roles, key, cookies and frozen comparisons. Only the reviewed source pin advanced
after authenticated graceful shutdown; evidence in protected
`me1-reviewed-source-transition.json`. PID after restart: 50652.

Preview allowlist adds ONLY the exact positive-integer comparison-page route.
Startup fingerprint now includes viewer HTML/CSS/JS. No startup schema/grant/data
repair, migration or seeding. Normal session and top-level snapshot guarantees
remain unchanged. Persistent Demo launcher/settings are untouched.

Edge and Chrome executables are available, but the manager password is now
hash-only. Automated capture correctly refused before browser login; no password
reset, hash reversal, force-login or fabricated session. The owner was asked for
secure local sign-in. No screenshot file exists yet and no browser layout or
actual UI-render PASS is claimed.

Run locally from the project directory to finish genuine capture:

```powershell
node scripts/capture_management_comparison.cjs --manual-login
```

It verifies signed preview health, opens a SEPARATE Edge profile/window, prefills
username `manager`, and waits for normal owner login (up to three minutes).
Enter the password only in that browser window. It then checks stored/API order,
390/1440 layout/no overflow, keyboard selection, commercial disclosure, 404 state,
and normal logout. It records only request methods/paths and refuses business
POSTs; it never records password bodies/cookies. It closes only its own browser.

Expected output paths, **NOT YET CAPTURED**:
- `D:\py project\sales_ai_copilot\venv\management-preview-live\me1-artifacts\01-M04-Desktop-1440.png`
- `D:\py project\sales_ai_copilot\venv\management-preview-live\me1-artifacts\02-M04-Mobile-390.png`
- `browser-proof.json` alongside them only after successful checks.

Owner manual review:
1. Log in and open comparison 2; check frozen customer/date/version context.
2. Compare P3 moving 3 → 1 while score remains 70.0000 and effective priority 37.50.
3. Select other products using mouse/keyboard; inspect distinct factor explanations.
4. Open commercial evidence; verify simulation, quantity-one scope and no Add/Publish controls.
5. Inspect stacked mobile / side-by-side desktop, focus outlines and long labels.

## Exact file boundary

Modified existing:
- `apps/management/urls.py`
- `apps/management/strategy_api_reads.py`
- `apps/management/strategy_api_views.py`
- `apps/management/strategy_api_serializers.py`
- `apps/management/tests_strategy_api.py` (test-only sequence correction)
- `scripts/management_preview.py` (exact page allowlist/source fingerprint)

Added:
- `apps/management/strategy_ui_views.py`
- `apps/management/tests_strategy_ui.py`
- `apps/management/js_tests/strategy_comparison.test.cjs`
- `templates/management/strategy_comparison.html`
- `static/management/css/strategy.css`
- `static/management/js/strategy_comparison.js`
- `scripts/capture_management_comparison.cjs`
- This checkpoint.

## Preservation and remaining acceptance

Read-only before/after preservation matched for all preview public tables except
session rows and last_login (authorized auth scope), and every public sequence.
Comparison 2 original output digest is unchanged. Persistent Demo all-table/
sequence digest matched its before-state; original PostgreSQL was never connected.
No persistent writes/migrations/grants/restart, Gate V2, Prepare Day, reset or
generation switch. Original SQLite SHA256 remains:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` and unrelated DEMO-02 preserved.
Nothing staged/committed/pushed. Stable UAT credentials were not changed.

Functional implementation is ready for owner review. M-E1 visual acceptance
remains PENDING secure login/capture and comparison against approved images when
supplied. No M-01 editing, Impact, publication or further feature work started.
