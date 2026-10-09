# DEMO-05 — approved generated visual asset integration

2026-10-09; fast-track baseline `228ee06b94b250a157921d7fa34c2167266e6871`.
Local visual-review integration only; no staging, commit or push.

## Archive verification and provenance

Source: `D:\UI References\DEMO_05_approved_visual_assets.zip`.
SHA256: `CFFF8219BC5D10B59ABE84122496F3D106967DE439A196E7009CC6E52BA2A5C1`.
44 archive members: 42 WebP images, original handoff JSON and README.
CRC, duplicate/path/symlink/encryption safety, all 42 SHA256 values, actual WebP
format/dimensions and exact code/variant sets passed before import. All codes were
confirmed to exist through an enforced read-only PostgreSQL connection.

The original unmodified handoff is retained at
`docs/demo/DEMO_05_ASSET_HANDOFF.json`. It says style-approved with crops pending
in-app review and `approved_for_ui=false`. The owner's current DEMO-05 instruction
explicitly authorizes local activation for this review; the handoff flags are not
silently rewritten or promoted to public-launch approval. Provider/generation IDs
and provider licensing terms were not supplied and are not invented. Registry
permission is owner-authorized local demo use, not a CC licence or public reuse grant.

All 21 supplied subjects are AI-generated representative **B** illustrations,
not manufacturer photographs, verified SKU models or actual customer premises.
Names, brands, quantities, prices, stock, geography and recommendations remain
database facts; image contents/logos/numeric displays do not establish facts.

## Asset registry and files

Extended `static/demo/manifest.v2.json` to manifest version `demo-assets-2.1.0`,
retaining its existing schema and static-only lookup. No image model/schema change.

Generated product codes: PHD001, PHS001, PAN001, BOS001, TEF001, BOS002, PHI003,
TEF002, ROW001, PHI004, TEF003. Each has exact imported bytes at
`static/demo/products/<code>/generated-v1/hero.webp` (800×800) and `thumb.webp`
(256×256). Versioned paths preserve every historical licensed photograph and the
old manifest's checksums. **BRN001, BRN002 and PHI002 entries and image bytes remain
unchanged**; their real representative photos/attribution are still active.

Store codes: C0003, C0005, C0013, C0011, C0029, C0008, C0009, C0014, C0010, C0006.
Each has exact imported bytes at `static/demo/stores/<code>/front.webp` (600×980)
and `thumb.webp` (184×300). The portrait originals use cover-fit in the existing
92×92 customer-image pattern; no distortion or new image generation/retouching.

Runtime distinguishes `GENERATED_REPRESENTATIVE` from existing real-photo
`REPRESENTATIVE`; generated entries never return `VERIFIED`. Source/CC licence URLs
are absent for generated pixels; old photograph licences are not copied onto them.
Unknown, disabled, missing or checksum-invalid assets retain existing fallback.

## Minimal presentation changes

- Guided product image slots remain 80×84 with contain-fit. Generated provenance is
  included in alt text and the existing image disclosure; commercial/card zones,
  saved priority, fonts, spacing, filters, pagination and reserved Quantity/Add are
  unchanged. All 14 products now have usable local imagery.
- Product Detail reuses its identity slot and approved «اطلاعات تصویر» disclosure.
  Generated items keep «تصویر نمونه محصول؛ مدل دقیق تأیید نشده» plus the visible
  statement that this is AI-generated imagery, not a real product photograph.
- Guided's existing 92×92 customer/store region now shows the selected store.
- Customer360 reuses the same 92×92 image pattern beside the existing customer
  identity, in both normal and active-visit headers. Search/operational action order,
  analytical sections and their DOM/JS contracts are untouched. Only image/display
  markup and scoped demo styles are added; no customer view/controller change.
- Visible store caption: **تصویر نمونهٔ فروشگاه**. Visible explanation:
  **تصویرسازی با هوش مصنوعی؛ محل واقعی مشتری در هلند نیست.**
  The supplied signs are Persian; Netherlands cities/phone/customer data stay
  unchanged. Do not infer real addresses, assortment, scale or business type from
  these illustrative storefronts, especially wholesale/distribution customers.
- Image-error handling restores both existing store/product fallbacks and hides
  their caption. No operational control or mutation behavior is added.

## Focused validation and remaining pre-existing failure

Django check passed with in-memory-only incidental SQLite checks. Initial focused
run: 72 tests, 67 passed and 5 failed. Four failures caught Persian registry strings
damaged by PowerShell stdin encoding. Restored those new strings from a UTF-8 script;
the four affected tests then passed. Final unique-test evidence: **71/72 passed**.
The other passing suites were not repeated. Tests used guarded in-memory databases,
destroyed normally; no original SQLite or PostgreSQL write-test connection.

The one remaining failure is pre-existing:
`ManagerCustomerWorkspaceTests.test_unavailable_html_and_api_do_not_disclose_existence`.
It compares unavailable HTML bytes containing independently randomized logout CSRF
tokens, the same assertion issue diagnosed in DEMO-04-F1. This test's fixture uses
non-demo customer codes; no new imagery appears in those responses. Manager test,
auth code and base/unavailable templates were not modified. No comparison/CSRF
protection was weakened to hide it; it requires a separately scoped assertion fix.

Relevant JS: **27 passed**, 0 failures; modified Guided JS syntax passed.
`git diff --check` passed. No full suite, new migration or seed.

Browser: actual 390px Guided and Customer360 captures succeeded; all images loaded,
RTL and no horizontal overflow, captions/AI/geography disclaimers visible, original
three photos preserved, fourteen product cards, one column, 92×92 store slots,
unchanged closed-card geometry and reserved controls. At 1440px Guided remains two
columns with no overflow. Store error fallbacks and generated Product Detail
search/signed-context return passed; zero fatal JS exceptions. No visual-approval claim.

## Review URLs and screenshots

Task-owned read-only preview remains on `http://127.0.0.1:8786/` using the existing
runtime role, forced read-only SELECT SQL and temporary signed-cookie sessions.
POST is blocked before the app; no production auth/session/business mutation.
First open `venv/demo04-artifacts/preview/open-preview.html` and choose salesperson.

- Guided: `http://127.0.0.1:8786/customers/C0003/recommendations/presentation/?visit_id=32`
- Customer360: `http://127.0.0.1:8786/customers/?customer_code=C0003&visit_id=32`
- Generated Product Detail: `http://127.0.0.1:8786/products/PHD001/?customer_code=C0003&visit_id=32`

Screenshots:
`D:\py project\sales_ai_copilot\venv\demo05-artifacts\guided-390.png`
and `D:\py project\sales_ai_copilot\venv\demo05-artifacts\customer360-390.png`.
These are genuine existing PLANNED visit context; no visit was created/reopened.
Inspect product proportion/crops, short image disclosure, store cover crop and
sample/geography wording; navigate Detail from Guided to verify exact filter return.

## Exact scope and safety

Ten existing files changed: `apps/core/demo_assets.py`,
`apps/core/tests_demo_assets.py`, `apps/customers/js_tests/guided_catalog.test.cjs`,
`static/core/js/guided_catalog.js`, `static/demo/assets.css`,
`static/demo/manifest.v2.json`, `templates/components/demo_image_credit.html`,
`templates/customers/recommendation_presentation.html`,
`templates/core/customer_360.html`, `templates/core/customer_360/_customer_hero.html`.

New: the 42 image paths listed above; `docs/demo/DEMO_05_ASSET_HANDOFF.json`,
`templates/components/demo_store_image.html`,
`templates/components/demo_store_caption.html`, and this checkpoint. Total 56 scoped
files. Inspection/validation scripts, source review sheet, logs/reports/screenshots
are Git-ignored under `venv/demo05-artifacts/`; private preview access stays ignored.

All 40 PostgreSQL table states matched the task baseline after review. Original
SQLite hash unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash unchanged: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Stage 3, historical photos and all unrelated pre-existing files preserved.
Index remains empty; no staging/commit/push, database changes, migrations or seeds.
Stop for visual approval; no next task started.

## DEMO-05-F1 — final minimal polish (2026-10-09)

Owner approved DEMO-05's Guided/Customer360 390px views before this patch.
Store caption retains the visible «تصویر نمونهٔ فروشگاه». The full, unchanged
AI/Netherlands explanation is now inside a native, initially closed disclosure
titled «اطلاعات تصویر». It supports keyboard opening/closing and visible focus.
Closed caption space is retained with scoped em-based minimum heights; the 92×92
images and surrounding context/product-card geometry remain unchanged. No image,
manifest/provenance, geography, ranking, pricing or business logic change.

The single manager-test failure is resolved in its assertion only. The test still
requires the same 404 statuses, non-disclosure checks, API response equality and
every other HTML byte; normalization replaces only the logout field's unpredictable
64-character CSRF value, also requiring exactly one correctly shaped field.
No authentication, logout or CSRF application logic was changed.

Validation: Django check passed; **72/72 focused Django tests passed**, including
the previously failing manager test and DEMO-05 registry/journey/Guided/Product
Detail cases, using guarded in-memory databases. **27/27 JS tests passed**;
`git diff --check` passed. No full suite or real-database migration/seed.

Actual browser checks at 390 and 1440px passed: native disclosures open/close with
Space, visible label retained, long clarification hidden when closed and readable
when open, visible 3px focus, no horizontal overflow or JS exceptions. Image size,
closed caption height and whole context/image/product-card positions/dimensions
match the former paragraph presentation (within subpixel rounding). Guided remains
one/two columns. The earlier transient capture authentication race was corrected
only in the ignored capture script using the preview's freshly issued signed cookie;
application authorization and read-only SQL/POST safeguards remain intact.

New genuine 390px captures:
`D:\py project\sales_ai_copilot\venv\demo05-f1-artifacts\guided-390-f1.png`
and `D:\py project\sales_ai_copilot\venv\demo05-f1-artifacts\customer360-390-f1.png`.
Review URLs remain:
`http://127.0.0.1:8786/customers/C0003/recommendations/presentation/?visit_id=32`
and `http://127.0.0.1:8786/customers/?customer_code=C0003&visit_id=32`.
Use `venv/demo04-artifacts/preview/open-preview.html` first. Open «اطلاعات تصویر»
beside the store caption to inspect the unchanged explanation, then close it.
Read-only preview remains running; no visual-approval claim for this final change.

Exact F1 files: `templates/components/demo_store_caption.html`,
`static/demo/assets.css`, `apps/customers/tests_manager_workspace.py`,
`apps/core/tests_demo_assets.py`, this checkpoint. Private tests/inspection/browser
reports are ignored under `venv/demo05-f1-artifacts/`.

All 40 PostgreSQL table states match the F1 baseline. SQLite remains unstaged and
byte-identical at `1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stage 3, all image bytes, registry provenance and unrelated pre-existing work are
unchanged. Stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` preserved;
index empty, no migration/seed/staging/commit/push. Stop after F1.
