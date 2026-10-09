# DEMO-03 — product photograph preparation

Prepared 2026-10-09, fast-track baseline
`56ab473439a4714eeadef36dd1981185a5c62f19`. Product assets only; no integration.

## Result and approval boundary

Six representative **B** image pairs are prepared for owner review, not approved
for publication. Five products remain permission-pending **C**; three licensed
candidates remain **C** on quality hold. No exact **A** match is established.
All 14 existing product names, brands and categories were reconciled against
PostgreSQL using an enforced read-only connection; no Django runtime was started.

Manufacturer product-page availability did not establish permission. Instead,
individual Commons file licences were checked before downloading. Originals and
public licence-page/API evidence are retained locally in the Git-ignored
`venv/demo03-artifacts/`. No unlicensed candidate photograph was downloaded.
Wikimedia rate-limited some originals; its supported 960px thumbnail route was
used for the alternative toothbrush and quality-held vacuum/blender candidates.
Original-download SHA1 checks passed; downloaded-source SHA256 and output SHA256
are recorded. No photographs were generated or reconstructed.

| SKU | Prepared/review state | Pictured identity or remaining blocker |
| --- | --- | --- |
| PHD001 | C fallback, licensed candidate on quality hold | Philips Thermo Protect 2100W; bathroom/toilet scene unsuitable |
| PHS001 | C permission pending | Philips straightener; manufacturer reuse grant/model required |
| BRN001 | B ready for owner review | Braun S3 / Series 3; exact variant unknown; Malcolm Koo, CC BY-SA 4.0 |
| BRN002 | B ready for owner review | Braun exact 5 universal, visible device marking; Gmhofmann, public domain |
| PAN001 | C permission pending / type ambiguity | Panasonic brush curler versus tong unresolved |
| PHI002 | B ready for owner review | Philips Sonicare 1100 Series; exact HX variant unknown; electricteeth, reviewed CC BY 2.0 |
| BOS001 | C fallback, licensed candidate on quality hold | Bosch Serie 4 ProHygienic; overhead floor scene weak product emphasis |
| TEF001 | C permission pending | Tefal steam iron; no permitted product-focused candidate acquired |
| BOS002 | C permission pending | Bosch jug blender; immersion-blender photos not substituted |
| PHI003 | B ready for owner review, quality decision | Philips Cucina kettle; exact HD unknown; older/grainy scene, Rafa public-domain photo |
| TEF002 | B ready for owner review | Tefal drawer air fryer; exact model unknown; Djsgmnd, CC BY-SA 4.0 |
| ROW001 | B ready for owner review, age/style decision | Rowenta FK5401 filter coffee maker; Groupe SEB, CC BY-SA 3.0, permission ticket 2010060110010948 |
| PHI004 | C fallback, licensed candidate on quality hold | White Philips jug blender; disassembled appliance/outdoor scene unsuitable |
| TEF003 | C permission pending | Tefal blender; permission/model evidence required |

The first licensed toothbrush photo cuts off the head; it was rejected. Its
replacement shows the whole device. The contact sheet includes both and every
other acquired candidate, clearly separating materialized assets from holds.

## Files and quality checks

- Versioned authoritative manifest: `static/demo/products/manifest.v1.json`.
- Six directories: `static/demo/products/{BRN001,BRN002,PHI002,PHI003,TEF002,ROW001}/`;
  each contains exactly `hero.webp` and `thumb.webp`.
- Credits: `docs/demo/PRODUCT_ASSET_CREDITS.md`.
- Public permission evidence: `docs/demo/product-permission-evidence.v1.json`.
- Labelled review sheet: `docs/demo/DEMO_03_PRODUCT_CONTACT_SHEET.webp`.
- This checkpoint is the only additional checkpoint created by DEMO-03.

Exact Git-ignored research files under `venv/demo03-artifacts/`:
`PHD001.jpg`, `BRN001.jpg`, `BRN002.jpg`, `PHI002.jpg`, `PHI003.jpg`,
`TEF002.jpg`, `ROW001.jpg`, `BOS001-thumbsource.jpg`, `PHI002-thumbsource.jpg`,
`PHI004-thumbsource.jpg`, `permission-evidence.json`,
`toothbrush-alternative-evidence.json`, `thumbnail-evidence.json`,
`source-review.png`, `source-review-2.png`, `prepare_assets.py`.
These preserve permitted source material and reproducible mechanical preparation;
they are not application integration or a new dependency.

Heroes are 800×800; thumbnails 256×256. Aspect ratio is preserved by contain-fit,
centered padding on #F7F9FB, with no upscaling/distortion/product cropping.
WebP quality 82, method 6. EXIF/location metadata is removed. Existing photographed
backgrounds remain: these are not uniformly isolated studio packshots. This is a
remaining visual limitation requiring owner review, especially PHI003/ROW001;
neutral outer canvas must not be described as full background removal.
The approved 80×84 UI image slot is unchanged and can later contain these square
assets without distortion.

All 12 outputs reopened successfully as WebP with expected dimensions and matching
manifest SHA256: combined 185,214 bytes; heroes 13,230–41,596 bytes and thumbnails
2,958–6,108 bytes. The 1800×1960 review sheet was opened and inspected; 206,374 bytes.
`git diff --check` passed. No application/test suite was run for asset preparation.

## Owner decisions required before integration

1. Approve or replace each B representative model, appearance and photographic
   quality; no generic database record gains the pictured model's specifications.
2. Retain the mandatory label **تصویر نمونهٔ محصول؛ مدل دقیق تأیید نشده**.
3. Carry source/author/licence/change attribution into later publication and honour
   share-alike requirements for the relevant image derivatives. The review collage
   is CC BY-SA 4.0; each underlying photograph retains its recorded licence.
4. Confirm device/bundle ambiguities, including PHI002 device versus replacement
   head and ROW001 filter coffee maker versus other coffee equipment. No accessories
   or capabilities are asserted as included in a demo SKU.
5. Obtain a written supplier/manufacturer grant or a suitable open-licensed photo
   for the five permission-pending and three quality-held products. Exact A requires
   owner model/variant/GTIN linkage evidence as well as an appropriate photograph.

Fallback remains effective for every product until owner approval AND later UI
label/attribution integration. No UI, model, migration, price, inventory, visit,
recommendation, seed or session changes occurred. PostgreSQL was read-only;
SQLite remained byte-identical at
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` is preserved; nothing
staged, committed or pushed. Existing uncommitted Stage 3 files are preserved.
Final SHA256 comparison confirmed all 338 pre-existing tracked/nonignored files
unchanged; only the 17 intended asset/review/document files were added.

Stop boundary: no store images, DEMO-04, UI integration or Stage 3C2.
