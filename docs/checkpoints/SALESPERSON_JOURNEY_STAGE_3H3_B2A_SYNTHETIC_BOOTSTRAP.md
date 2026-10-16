# Stage 3H3-B2-A — Persistent synthetic Demo bootstrap

2026-10-15. Owner review pending. fast-track / V3.0.21
`1a96e92b938a5f64d586249245734f8e5d083b1e`. Builds on uncommitted B1.
No application business/UI/schema change; no destructive reset.

## Identity, provenance and frozen artifacts

Dedicated container `sales-ai-demo-postgres`, database `sales_ai_demo_db` at
`127.0.0.1:5433`; app http://localhost:8900. Existing B1 container/image/volume,
database OID, owner/runtime roles and owner-controlled identity marker verified
before writes. All 50 migrations present; required runtime grants verified.
No migrations or grant changes in B2-A.

Version **SYNTHETIC_DEMO_V1**, explicitly prepared for **2026-10-15, Asia/Tehran**.
Fixture-payload SHA256:
`c93994113eb2ac22275d91a21aff624d648376f2ed57cf714c4cc27e772730ef`.
Protected creation-manifest file SHA256:
`7b20ef10b059c9a8630da310db2b29fac1e7b1ffae07539eb08482b5f14435b6`.
Approved DEMO_06_V1 price-dataset SHA256:
`1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648`.

All products/names/categories and price facts derive from committed approved
Demo documents/data, not a production export. Other data is freshly synthetic.
No copied users, credentials, password hashes, sales, Customer360 history or
recommendation output. Existing `static/demo/manifest.v2.json`, verified image
files, labels/credits/licenses/fallbacks are reused unchanged. Exact-model or
real-premises claims are not introduced.

## Inserted fixture inventory

- 3 independent TEST users: `demo-sp001-test`, `demo-manager-test` (staff, not
  superuser), `demo-unassigned-test` (no salesperson profile/assignment).
- SP001 salesperson, 3 grades A/B/C, 5 customers and 5 current assignments.
- 6 brands, 12 categories, 14 approved products and 14 whole-TOMAN prices through
  the existing validated loader. Source DEMO_ONLY_FICTIONAL / DEMO_06_V1.
- 5 NEW/zero-history Customer360 rows. No fake historical transactions/metrics.
- 13 inventory rows: ordinary/recommended stock normally 25 available minus 3
  reserved = 22 sellable; PHI004 3 minus 2 = 1; ROW001 zero; TEF003 has no inventory
  row, so UNKNOWN remains distinct from zero.
- 15 explicitly synthetic saved recommendations, 3 per customer. C0003 uses the
  REPEAT_PURCHASE fixture type, C0005 CROSS_SELL, others CATEGORY. Reasons identify
  synthetic practice rather than claiming real purchase evidence. Scores/ranks
  are fixed fixture values; no engine generation or scoring-rule changes.
- 5 Visits and the 2 normal Start snapshots for C0005. No committed SalesRequest,
  line, feedback event, receipt, acknowledgement, sale or follow-up created.

| Customer | Visit ID | Persistent initial state | Scenario / grade |
| --- | ---: | --- | --- |
| C0003 | 1 | PLANNED | Complete selling journey / A |
| C0005 | 2 | IN_PROGRESS | Cross-sell; started via normal authorized API / B |
| C0013 | 3 | PLANNED | No-sale completion / C |
| C0014 | 4 | PLANNED | Retained-DRAFT and low-stock / B |
| C0029 | 5 | PLANNED | TEF003 prioritized but inventory unknown / C |

All primary products have valid Demo prices. For C0003, PHD001 is prioritized;
PHS001 is an eligible ordinary product. PHI002 remains one complete toothbrush
per PCS and keeps the documented consumable flag. No product model identity,
legacy historical financial unit or existing production fact is changed.

## Bootstrap and normal access

`scripts/demo/bootstrap.py --date 2026-10-15 --confirm-database sales_ai_demo_db`
is a separate explicit operator action. It verifies identity/schema/grants,
requires initially empty business tables, uses a transaction/advisory lock and
INSERT only. C0005 starts afterward through real login, CSRF and the existing
Start endpoint. Normal login/logout updates only synthetic auth/session state.
No preview bypass or forced authentication is used for HTTP/browser validation.

Independent generated account passwords remain only in protected
`D:\SalesAI-Demo\sales_ai_copilot\credentials\test-accounts.json`.
Creation data/version/checksums/image references are under `fixtures\` in that
state directory. Nothing secret is printed or stored in the repository.

Same-version/date replay checks the manifest checksum, all recorded immutable
fixture fields and account password validity and returns NO_OP. Conflicting
identities stop; nothing is overwritten. PostgreSQL numeric trailing-zero scale
initially caused a false record mismatch; read-only evidence showed identical
values. Canonical comparison strips insignificant zeros without rounding, and
detects actual numeric changes. The original manifest remains unchanged.
Evolved Visit status/results and normal last_login are not reset by bootstrap.
Partial preparation stops for inspection. No reset, cleanup or auto-recovery.

Normal startup still only verifies and serves. Demo health reports fixture
readiness from the identity-bound completed manifest; it does not seed or adjust
dates. Guarded Django stop/start preserved fixtures. See `scripts/demo/README.md`.

## Focused validation and browser evidence

- **10/10** runtime-role acceptance checks passed; an additional **1/1** focused
  Decimal comparison regression passed. Zero failures/errors/skips.
- Normal TEST login/logout, last_login, DB-backed session creation/invalidation,
  staff-manager access, salesperson restriction and unassigned-user denial passed.
- C0003 recommended + ordinary Add, C0013 no-request completion and C0014
  retained-DRAFT completion passed inside rolled-back transactions. Retained
  Draft identity/revision/lines stayed unchanged by completion. These probes
  leave no committed business evidence; sequence gaps are expected, not reset.
- Unknown, zero and insufficient inventory remain distinct and non-addable.
  A/B/C pricing uses the existing provider; saved catalog and basket GETs create
  no requests/history. No price/discount calculation duplicated in fixtures/UI.
- Repeat bootstrap: every table digest and sequence value identical before/after.
- Genuine Chrome normal login/logout at 390/1440: 5 today's Visits; C0005 full
  14-product catalog, saved PHD001/BRN001/BOS002 priority order, ordinary PHS001
  enabled, zero/unknown disabled, all 14 product images loaded; signed Product
  Detail return passed. Zero business mutation HTTP requests, fatal JS errors
  or horizontal overflow. C0003 Start available; PLANNED Finish remains hidden.
- Django check clean. No full regression suite. No application JS changed.

Protected evidence: `D:\SalesAI-Demo\sales_ai_copilot\reports\b2a\`:
`focused-validation.json`, `idempotency.json`, `browser-validation.json` and
numbered screenshots `01-daily-plan-390.png`, `02-daily-plan-1440.png`,
`03-guided-C0005-390.png`, `04-guided-C0005-1440.png`,
`05-unknown-stock-C0029-390.png`.

## Preservation and next boundary

Production is read-only reconciliation only; no production migrations/writes,
data/credential cloning or preview-database changes. Original SQLite SHA256
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`,
stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` and unrelated DEMO-02 planning
remain preserved. No staging, commit or push.

B2-B requires separate owner approval: any reset/refresh mechanism, future-day
Visit preparation and immutable-evidence handling must have exact Demo identity,
explicit confirmation, a bounded write set and conflict/retention policy. B2-A
does not reset completed scenarios or advance their dates on startup/replay.
