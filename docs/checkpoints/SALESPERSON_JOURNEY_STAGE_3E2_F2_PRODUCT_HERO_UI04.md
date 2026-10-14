# Stage 3E2-F2 — Product Hero UI-04

Date: 2026-10-14. Owner approved for V3.0.18 closeout on 2026-10-15.
Baseline: `fast-track`, `6af76c14cd5ffd9fe3528be1093317a8d7cacfd7`, with
the accepted, uncommitted Stage 3E1/E2 work preserved.

## Reference and implementation

Owner-selected UI-04, inspected directly at
`D:\UI References\ChatGPT Image Oct 14, 2026, 09_59_05 PM.png`.
The Stage 3 contract governs behavior; this task explicitly supersedes visible
demo disclaimers only on salesperson Product Detail.

| UI-04 zone | Implementation |
| --- | --- |
| Large image and brand | Landscape hero, existing registry image with contain sizing, brand chip and intentional error/missing-image fallback. No new assets. |
| Identity/context | Product title, distinct code, brand/category and compact customer/Visit/status strip with bidi isolation. |
| Mint commercial card | Prominent final unit TOMAN price, secondary base/grade discount, truthful availability and recorded/reserved/minimum-stock tiles. Values come from the existing Quote API and commercial context. |
| Blue explanation card | Actual saved reason, recommendation type/confidence and existing business/technical disclosures. Zero-valued evidence remains available. |
| Feedback card | Prominent keyboard-accessible disclosure, explicit REJECTED/seven reasons and LATER confirmation, shared history/retry controller and authoritative selection guidance. |
| Supporting facts/return | Existing descriptions, units, promotions and safe context return remain accessible. |

Layout is a single bounded column (maximum 900px) with responsive spacing.
Global navigation and manager Product Detail remain unchanged. Missing price
and unknown/zero inventory are never represented as usable commercial values.
Redundant stock wording is hidden only when the authoritative availability
message already occupies that location.

## Functional boundaries

- Product Detail bootstraps feedback from the existing authorized catalog,
  signed context, feedback-history and basket GET APIs; reads never create state.
- The shared Guided feedback controller is reused without changing its
  command UUID, CSRF, confirmation, append-only history or uncertain-retry rules.
- Basket membership is read before fresh decisions become available. Selected
  products block rejection/LATER. A selection/revision conflict triggers a
  basket GET refresh, never an automatic POST retry. Explicit recovery of a
  previously uncertain command remains available even if the current catalog
  has changed; its original UUID, revision, context and payload are retained.
- Ordinary products have no feedback buttons. PLANNED/closed Visits and failed
  authorization/context/history/selection reads cannot enable fresh feedback.
- Confirmed recommended-line membership displays ADDED_TO_REQUEST selection;
  ordinary membership uses neutral selection wording. No ACCEPTED event or
  purchase claim is introduced. Removal stays an explicit Guided basket action;
  existing historical add/removal events are neither changed nor invented here.
- Product Detail does not introduce Add, quantity, submission or completion.
  Existing Guided Add/update/remove and feedback flows are preserved.
- No backend, model, migration, price arithmetic, inventory rule or permissions
  change. No production feedback or basket commands were submitted.
- Visible demo-price/image labels are removed on salesperson Product Detail.
  Registry provenance/model-match metadata remains untouched. Required licensed
  photo author/source/license/change credits remain in accessible image details.
  Guided disclosures and manager presentation retain their existing behavior.

## Validation

- Focused PostgreSQL selection: 109 tests. Initially 108 passed and one hidden
  image-fallback markup assertion failed; its selector was updated for the new
  hero and the single test passed on rerun. No remaining failure/error/skip.
- Selection covers Product Hero, existing Product Brief/evidence/authorization,
  quote presentation, asset integration/registry, Guided feedback/basket UI and
  existing selected-product/CSRF feedback API regressions.
- Separate uniquely named PostgreSQL test databases were created and removed;
  production connections were read-only and SQLite connections prohibited.
- JS: 83 tests passed initially; after Product conflict-refresh and pending
  recovery coverage were added, all 29 directly affected feedback/Product tests
  passed. Total distinct tested cases: 85 (76 existing, nine new).
- Django check: no issues. Migration drift: no changes detected. Both changed
  JS files pass `node --check`; `git diff --check` passes. No full suite run.
- Genuine Chrome captures at 390px and 1440px: no horizontal overflow, fatal
  JS error or business mutation request. Native feedback disclosure opens with
  Enter, retains visible focus and has a 48px touch target. Image-error fallback
  and signed return/product focus into the existing Guided basket were verified.
- Preview currently has all three recommended products selected. Their disabled
  feedback states were inspected without changing the owner's basket. Unselected
  feedback, all seven reasons, LATER history, rejection conflict, missing price,
  zero/unknown stock and PLANNED/closed restrictions are covered by isolated tests.

## Manual review

Use the existing isolated normal-login preview, left running on port 8790:

- Login: `http://127.0.0.1:8790/accounts/login/`.
- Guided: `http://127.0.0.1:8790/customers/C0003/recommendations/presentation/?visit_id=19`.
- Blender: `http://127.0.0.1:8790/products/PHI004/?customer_code=C0003&visit_id=19`.
- Ordinary: `http://127.0.0.1:8790/products/PHS001/?customer_code=C0003&visit_id=19`.
- Unknown stock: `http://127.0.0.1:8790/products/BOS001/?customer_code=C0003&visit_id=19`.

For signed filter/page continuity, enter Detail from a Guided card. Use the
existing `venv/local-demo-preview/start-demo-preview.ps1` launcher and dedicated
TEST login; `-CopyPassword` copies its protected password without printing it.
No production password/session is used or changed.

Screenshots and protected browser/check reports are Git-ignored in
`venv/ui04-artifacts/`:
`product-hero-blender-390.png`, `product-hero-blender-1440.png`,
`product-feedback-recommended-390.png`, `product-feedback-recommended-1440.png`,
`product-ordinary-390.png`, `product-ordinary-1440.png`,
`product-selected-390.png`, `product-unavailable-390.png`.

Review hero/identity/price hierarchy, open feedback on a selected recommendation
and confirm remove-first guidance, inspect ordinary/unknown-stock products, then
return through the signed link and check Guided filters/basket.

## Deliberate differences and preservation

Existing approved neutral product imagery replaces the mockup kitchen scene;
actual product text, saved evidence, price and grade discount remain authoritative.
No favorite, carousel or decorative accepted action is added. Supporting facts
and required licensed credits remain available. Final membership presentation is
documented in the approved F3 checkpoint.

Production PostgreSQL table/sequence/metadata reconciliation is unchanged before
and after focused validation and preview reads. The original SQLite remains
modified locally but byte-identical and unstaged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Baseline hashing covered 452 existing source files; only the five intentional
existing presentation/test files changed. Other E1/E2 work is byte-identical;
the shared feedback file retains E2 changes with only Product mount/refresh
bindings added. Nothing staged, committed or pushed.
