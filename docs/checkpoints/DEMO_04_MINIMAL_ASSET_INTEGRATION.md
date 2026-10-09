# DEMO-04 — minimal visual asset integration and review

2026-10-09; fast-track HEAD `56ab473439a4714eeadef36dd1981185a5c62f19`.
Resumed the interrupted task without repeating the 97-test run or acquiring new
assets. No business functionality, schema, migration, runtime default or approved
page layout was redesigned.

## Implementation and asset classification

`static/demo/manifest.v2.json` is the additive, code-keyed local-demo registry.
The historical DEMO-03 manifest and all prepared image binaries remain unchanged.
`apps/core/demo_assets.py` verifies enabled status, local path containment and
SHA256; it performs no database queries/writes. Missing/unapproved/altered images
retain the pre-existing missing-image response. Metadata/file checks are cached
per process; restart the preview when changing the static registry/assets.

Three permitted representative real photographs are enabled for the local demo:
BRN001, BRN002 and PHI002. None is an exact verified photograph of the database SKU.
The sample caption, photographer, licence, source, alteration notice and original
electricteeth article link travel with the image; source/credit details are
expandable in Guided Sale and visible in Product Detail.

| Product | Status | Current display | Immediate demo use / remaining decision |
| --- | --- | --- | --- |
| PHD001 | GAP | Existing fallback | Bathroom candidate held; replacement brief |
| PHS001 | GAP | Existing fallback | No permitted local photo; brief |
| BRN001 | B | Real Braun S3 representative photo | Ready for labelled local demo; variant not verified |
| BRN002 | B | Real Braun exact 5 universal representative photo | Ready for labelled local demo; pictured marking does not establish database SKU identity |
| PAN001 | GAP | Existing fallback | Owner must select tong versus brush-curler type before generation |
| PHI002 | B | Real Philips Sonicare 1100 Series representative photo | Ready for labelled local demo; exact HX/bundle unverified |
| BOS001 | GAP | Existing fallback | Overhead floor-scene photo held; brief |
| TEF001 | GAP | Existing fallback | Permission/model unresolved; brief |
| BOS002 | GAP | Existing fallback | No jug-blender photo acquired; no immersion-blender substitution |
| PHI003 | GAP | Existing fallback | Grainy old kettle photo held; brief |
| TEF002 | GAP | Existing fallback | Retail/display photo held; brief |
| ROW001 | GAP | Existing fallback | Old coffee-maker appearance/quality held; owner type decision and brief |
| PHI004 | GAP | Existing fallback | Disassembled/outdoor blender photo held; brief |
| TEF003 | GAP | Existing fallback | Permission/model unresolved; brief |

A = exact verified identity; B = real representative; C = deliberate fallback-only
choice without planned acquisition; GAP = fallback today with a replacement brief.
There are no A/C-only selections here; all blocked products have explicit briefs.
Fallback is safe to show during the demo, but is not a completed photograph set.

| Store/customer | Existing type / city | Status and current display | Ready as photograph? |
| --- | --- | --- | --- |
| C0003 | Electrical retailer / Eindhoven | GAP; existing store icon | No; fictional-premises brief |
| C0005 | Electrical retailer / Eindhoven | GAP; existing store icon | No; distinct fictional-premises brief |
| C0013 | Electrical retailer / The Hague | GAP; existing store icon | No; brief |
| C0011 | Electrical retailer / Utrecht | GAP; existing store icon | No; brief |
| C0029 | Home-appliance retailer / Rotterdam | GAP; existing store icon | No; licensed candidate unavailable for local acquisition |
| C0008 | Home-appliance retailer / The Hague | GAP; existing store icon | No; brief |
| C0009 | Home-appliance retailer / Rotterdam | GAP; existing store icon | No; brief |
| C0014 | Wholesaler / Eindhoven | GAP; existing store icon | No; licensed candidate unavailable for local acquisition |
| C0010 | Wholesaler / Amsterdam | GAP; existing store icon | No; brief |
| C0006 | Distributor / Rotterdam | GAP; existing store icon | No; licensed candidate unavailable for local acquisition |

The Pexels licence and three DEMO-02 candidate pages were rechecked, but direct
source/image downloads failed with connection-refused errors. No URL or photograph
was fabricated and no stock image was duplicated across ten fictional premises.
Future store images require the visible caption «تصویر نمونهٔ فروشگاه» and actual
provenance review. No store image is currently enabled.

## Rendering and scope

- Catalog API adds only image presentation metadata. Existing authorization,
  ranking, counts, stock, price availability, signed context and URLs are untouched.
- Guided Sale fills its existing 80×84 image region. Source disclosure is secondary;
  existing card zones, recommendation cues, secondary Detail, reserved Quantity/Add,
  search/category filters, pagination and one/two-column layout remain.
- Product Detail replaces its existing identity glyph inside the same slot: 48×48
  mobile, 56×56 desktop. Caption/credit appears beside the product identity. The
  existing glyph reappears if the image fails.
- The existing 92×92 Guided customer/store slot can resolve a future approved
  registry image; today it remains the same icon. Customer360 was not modified and
  has no new store image. No Customer360 screenshot is needed for an asset change.
- No basket, quantity, Add, feedback, pricing, submission, visit or message behavior.

## Validation: completed result, not a clean test gate

The previous focused run completed in its guarded in-memory test database:
**97 total, 94 passed, 3 failed, 0 errors, 0 skipped**. It was recovered from the
completed tool output and was not rerun on resume. The nine new registry/journey
tests and the Guided/catalog regressions passed. The failures were:

1. `ProductCommercialBriefTests.test_invalid_foreign_or_mismatched_visit_context_has_same_response`
2. `ProductCommercialBriefTests.test_missing_and_inactive_products_are_unavailable`
3. `ProductCommercialBriefTests.test_unauthorized_and_missing_customers_have_identical_nonleaking_response`

Each compares raw unavailable-page response bytes; observed differences occur in
the independently masked CSRF value of the existing logout form. Product views,
unavailable template and shared base template are unchanged from HEAD. This is an
existing assertion/CSRF interaction, not an asset-rendering failure; no assertion
was weakened or unrelated authentication/template behavior patched. The test gate
remains 94/97 and these failures require separate review.

- Django check: passed, 0 issues; incidental SQLite capability checks in memory.
- Guided + image fallback JS: 26 passed, 0 failed/skipped.
- Modified/new production JS syntax: both scripts passed `node --check`.
- `git diff --check`: passed (only Git LF/CRLF notices).
- No full suite, database migration or seed was run.

The first preview startup failed safely because port-text replacement also altered
the temporary expected-hash literal. Corrected only that ignored harness literal;
the actual SQLite never changed. Browser capture initially expected the desktop
Product Detail slot size at mobile; corrected only the capture assertion to its
pre-existing responsive 48px size. Neither issue required application/UI changes.

## Genuine browser review and manual steps

Separate read-only preview: `http://127.0.0.1:8786/`, production PostgreSQL via
`sales_ai_runtime`, `default_transaction_read_only=on`, only SELECT SQL, GET/HEAD
HTTP paths and temporary signed-cookie sessions. No production login/session writes.
Real user/customer/visit authorization remains active. Existing runtimes unchanged.
Open the local private role-entry page first:
`venv/demo04-artifacts/preview/open-preview.html`.

Exact stable page URLs:

- Guided: `http://127.0.0.1:8786/customers/C0003/recommendations/presentation/?visit_id=32`
- Product: `http://127.0.0.1:8786/products/BRN001/?customer_code=C0003&visit_id=32`
- Customer: `http://127.0.0.1:8786/customers/?customer_code=C0003&visit_id=32`
- Other scenario entry pages: `/customers/?customer_code=C0005&visit_id=33`,
  `/customers/?customer_code=C0013&visit_id=34`,
  `/customers/?customer_code=C0014&visit_id=35`,
  `/customers/?customer_code=C0029&visit_id=36` on the same host/port.

These are genuine existing **PLANNED** visits, read-only preparation. No Visit was
started/reopened or created. The five scenario themes remain intended storytelling
directions, not assertions that today's saved ranks match those themes. In current
C0003 data the saved priorities are PHI002, PHI004, TEF003; do not regenerate them
to force a repeat-purchase story.

Four full-page screenshots, absolute directory
`D:\py project\sales_ai_copilot\venv\demo04-artifacts\preview\`:
`guided-390.png`, `guided-1440.png`, `product-390.png`, `product-1440.png`.
Actual signed-context Product Detail URL and screenshot state are recorded in
`browser-review.json`; prefer reaching Detail from Guided for same-context return.

1. Enter the local salesperson preview, then Guided; confirm 14 products, three
   saved priorities first, three B photos and fallback elsewhere.
2. Open a photo's sample-label disclosure; check creator/licence/source. Ordinary
   product images do not become AI priorities merely because imagery exists.
3. Search BRN001, open secondary Detail, inspect image/sample credit, return. Search
   and signed context should survive. Do not use any mutation/finish control.
4. Inspect 390 and 1440 widths: no overflow, same card zones, empty reserved action
   regions, one/two product columns. Missing price and unknown stock stay truthful.

Guided, Product and Customer HTTP all 200; 57 static responses 200/304, no fatal JS
exceptions, browser application requests GET/HEAD only. Error-event probes restored
both actual image fallbacks and hid their captions. Search/Detail return passed.
All four captures succeeded; preview remains running. No self-declared visual approval.

## Exact DEMO-04 project files and preservation

Changed existing files (five):
`apps/products/catalog.py`, `static/core/js/guided_catalog.js`,
`apps/customers/js_tests/guided_catalog.test.cjs`,
`templates/customers/recommendation_presentation.html`,
`templates/core/product_detail.html`.

New files (eleven):
`apps/core/demo_assets.py`, `apps/core/templatetags/__init__.py`,
`apps/core/templatetags/demo_assets.py`, `apps/core/tests_demo_assets.py`,
`apps/core/js_tests/demo_assets.test.cjs`,
`templates/components/demo_image_credit.html`,
`static/demo/assets.css`, `static/demo/assets.js`, `static/demo/manifest.v2.json`,
`docs/demo/DEMO_04_GENERATION_BRIEFS.md`, this checkpoint.

Ignored preview/validation reports live under `venv/demo04-artifacts/`, including
`production-before.json`, `production-after.json`, `preservation-report.json`,
`focused-validation-recovered.json`, `run_focused.py`, and preview scripts, logs,
temporary capability/session material, browser profile and screenshots. No secrets
or private artifacts belong in Git.

All 40 production table states match the before baseline, including auth/session
rows; original SQLite SHA256 unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash unchanged: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
SHA256 baseline comparison confirms Stage 3 work, existing demo documents/assets
and all other pre-existing files unchanged except the five listed scoped files.
Index empty; nothing committed/pushed. No migrations or database schema changes.

Stop: local-demo asset review only. No DEMO-05 or Stage 3C2.

## DEMO-04-F1 — focused closure (2026-10-09)

The three unavailable-page comparison failures are resolved in tests only.
`assert_same_unavailable_page` requires both 404 responses, the unavailable template
and exactly one correctly shaped logout CSRF input; it substitutes only that input's
64-character masked token value before comparing the entire remaining HTML.
Authorization, business-identity non-disclosure, form structure and CSRF presence
remain checked. Authentication/logout/CSRF application code is unchanged.

Product Detail keeps the visible exact label «تصویر نمونه محصول؛ مدل دقیق تأیید نشده».
Creator, source, licence, original-review link where applicable and alteration notice
remain in a native, initially closed disclosure titled «اطلاعات تصویر». It has a
44px target and visible keyboard focus; actual keyboard opening/closing passed for
BRN001, BRN002 and PHI002. Credit links/required attribution remain available.

Guided's initial DEMO-04 standalone credit row added 50px and pushed stock/price/
Detail below their approved positions. Removed that extra card-grid row. A compact
«تصویر نمونه» disclosure now occupies unused space beside the centered secondary
Detail action; the full model-unverified warning and credit remain inside, and the
image alt text still contains the full warning. Opening it deliberately reflows
the secondary-action region rather than overlaying neighbouring content.
At 390 and 1440px, closed-disclosure measurements exactly matched the same card
without image credits: card height, product body, stock/price/Detail coordinates,
title/code typography. 80×84 image slots, one/two columns and empty Quantity/Add
regions remain. Summary targets >=44px, no overlap or horizontal overflow.
Approved Guided/Product Detail stylesheets and shared manager/base styles untouched.

Validation: Django check passed; **68 focused Django tests passed**, 0 failures/
errors/skips, including all three formerly failing tests, Product Detail, image
registry/journey, Guided and normal logout/CSRF tests. Used a guarded in-memory test
database, destroyed normally; no real database connection or migration. The full
suite and original 97-test selection were not rerun. **26 JS tests passed**,
0 failures. `git diff --check` passed. No JavaScript changes in F1.

Read-only preview remains on 8786; refreshed only its task-owned server to clear
cached templates. Product Detail URL:
`http://127.0.0.1:8786/products/BRN001/?customer_code=C0003&visit_id=32`.
Enter via `venv/demo04-artifacts/preview/open-preview.html` first. New genuine 390px
capture: `D:\py project\sales_ai_copilot\venv\demo04-f1-artifacts\product-detail-390-f1.png`.
Check the permanent warning, open «اطلاعات تصویر» with keyboard/touch, inspect
creator/source/licence, then close. No visual-approval claim.

Exact F1 files: `apps/products/tests_commercial_brief.py`,
`apps/core/tests_demo_assets.py`, `templates/components/demo_image_credit.html`,
`templates/customers/recommendation_presentation.html`, `static/demo/assets.css`,
this checkpoint. Ignored inspection/test/browser reports under
`venv/demo04-f1-artifacts/`; no new assets or manifest changes.

All 40 PostgreSQL table states matched the F1 baseline. SQLite hash remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` unchanged.
Stage 3/pricing/receipt files and every unrelated pre-existing file are byte-identical.
No real database writes, migration, seed, staging, commit or push. Stop after F1.
