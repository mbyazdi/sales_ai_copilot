# Stage 3C3 — read-only commercial quote presentation

2026-10-09. Baseline: fast-track / V3.0.15 `9a3e170`, with existing approved
uncommitted Pricing Core, Quote API and receipt foundations preserved.
Implementation is ready for owner visual review; this is not visual approval.

## Behavior and boundary

Guided Sale and Product Detail share `components/commercial_quote.html` and
`products/js/commercial_quotes.js`. They request the existing authorized
`GET /api/sales-requests/v1/visits/<visit_id>/quote/` for quantity **1**.
Base unit price, grade discount percentage/unit discount and final unit TOMAN
price are server results. JavaScript only formats whole amount strings using
BigInt/Intl; it performs no monetary arithmetic, rounding or grade calculation.

Guided fetches quotes for the current visible catalog page, at most 50 products
per API batch. A 100-product page needs two requests, not per-card requests.
Product Detail uses the same renderer for one product. Response context/product
identity is checked before display. The API remains the authorization authority.
Requests are GET-only, same-origin, private/no-store; there is no automatic retry.
Aborted/obsolete catalog responses cannot replace current quotes.

The existing Guided recommendation ordering, search/category/priority filters,
pagination, signed context and Detail return links are unchanged. No views,
services, API contracts, permissions, models or migrations changed in this task.

## Presentation and truthfulness

- Quotes occupy the existing Guided price slot; image areas, card zones, grid,
  reserved Quantity/Add slots and secondary Detail navigation stay intact.
  Price content adds necessary height; no card/grid geometry CSS is rewritten.
- Product Detail shows quotes inside its current commercial/inventory card,
  for an owned PLANNED/IN_PROGRESS Visit. Manager/customer-only/closed-Visit
  detail inspection does not initialize operational quote requests.
- Visible label: **قیمت فرضی دمو**. Accessible description/title explicitly says
  **قیمت فرضی دمو؛ قیمت بازار نیست**. These are DEMO_06_V1 fictional prices.
- Missing/configuration-error prices show unavailable messages, not zero.
  An explicitly configured zero stays a real zero. Failures retain browsable
  products and show a Persian recovery message without revealing technical errors.
- Quote inventory/addability is separate from price availability. Unknown, zero,
  insufficient stock and not-started Visits retain their server-provided states.
  Known positive inventory alone does not enable any action.
- Quantity/Add, feedback, basket and submission remain non-operational. No
  discounts/promotions are recomputed or stacked in the browser.

## Focused validation

- 76 focused Django tests passed: new quote presentation tests, existing Quote API,
  Guided presentation and Product Detail regressions. A final text-fit adjustment
  was followed by only its two affected template assertions, both passed.
- Both uniquely named PostgreSQL test databases were destroyed; production
  checksums remained identical. No original SQLite connection was used by tests.
- 36 distinct JS cases passed (25 Guided + 11 shared quote). One new assertion
  initially compared fixture method identities; it was corrected to compare
  deterministic rendered properties and passed its targeted rerun. After the
  stock-color update, the two affected stock cases passed again.
- Django system checks and both modified JS syntax checks passed.
- Real Chrome screenshots captured at 390px; quotes matched across Guided/Detail,
  signed return/search worked, and there was no horizontal overflow or fatal JS
  exception. At 768/1440px Guided retained two columns and empty action slots.
  Product image slots stayed 80×84. Existing asset labels/fallbacks are retained.
- `git diff --check` and new-file whitespace checks passed. No full suite ran.

## Read-only owner review

Preview: `http://127.0.0.1:8787`. Private access page:
`venv/stage3c3-artifacts/open-preview.html` (local, protected, Git-ignored).
This preview uses temporary signed-cookie sessions for existing users, plus the
runtime role with database-enforced read-only transactions and a SELECT-only
SQL guard. HTTP mutations and SQLite connections are blocked; normal runtime
settings and other previews are unchanged.

1. Open the local access page and choose salesperson SP001.
2. Open `/customers/C0003/recommendations/presentation/?visit_id=19`.
   Verify prices/discount, demo label, availability and empty Quantity/Add slots.
   This actual customer is grade C; Visit 19 is PLANNED, so discount is 0% and
   the not-started-Visit restriction is truthful. Do not start/complete it.
3. Search or choose a category; open a card's Detail and compare its quote.
4. Use Back; the signed catalog context/filter/selected product must survive.
5. Optional grade checks: C0005/Visit 15 (B, 5%) and C0014/Visit 17 (A, 10%).

Clean Detail inspection URL:
`/products/PHI002/?customer_code=C0003&visit_id=19&return_to=presentation`.
For signed filter continuity, enter Detail through its actual Guided link.

Screenshots: `venv/stage3c3-artifacts/guided-390.png` and
`venv/stage3c3-artifacts/product-detail-390.png`; the browser report records
actual signed navigation URLs. Artifacts are local/protected/ignored.

Original SQLite remains intentionally modified/unstaged, SHA256
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash `2dac7bdc26f07f611f471564476ceaa52ec367cc` is preserved.
No production rows, prices, inventory, history, Visit or recommendation records
were changed. No staging, commit or push; stop for visual approval.

## Stage 3C3-F1 — readability and preview access

Final available unit amounts now use navy/teal contrast with an existing-token
light highlight; the TOMAN unit receives the same stronger color. Base price and
discount remain secondary. Only `commercial_quote.css` presentation changes;
font sizes, card dimensions, images, ordering, filters and action regions stay
unchanged. Product Detail uses the same restrained emphasis in its commercial
area. Unavailable/loading/error prices do not receive this highlight.

Anonymous Guided requests reproduced HTTP 403. Fresh access through the existing
protected SP001 capability returned 200 for Guided and Quote API; manager access
correctly returned 403. Visit 19 belongs to active SP001, with an active C0003
assignment, and is PLANNED. No application permission fix or bypass is needed.
The owner's browser cookie was unavailable for inspection: missing/expired
session, a different hostname, or manager preview identity can explain its 403,
but the exact browser cause cannot be asserted.

Run the secret-free local launcher in Windows PowerShell:

```powershell
& 'D:\py project\sales_ai_copilot\venv\stage3c3-f1-artifacts\open-salesperson-preview.ps1'
```

It reads the existing protected capability without printing it and opens SP001
in the default browser. Then use the `http://127.0.0.1:8787` URLs above in that
same browser; do not substitute `localhost` or choose manager access. Hard-refresh
if older CSS is cached. Opening the protected local HTML launcher in a browser
and selecting its salesperson link is also supported.

Seven focused PostgreSQL quote/presentation tests and Django check passed; the
unique test database was removed. Real browser checks at 390/1440px verified
no overflow on both pages, and identical widths/heights for all 14 Guided cards
against the pre-F1 baseline. Image slots stay 80×84 and action slots empty.
Quotes, signed return/search, demo disclosure and PLANNED restrictions are intact;
no fatal JS exceptions. No JS source changed, so JS suites were not rerun.
`git diff --check` passed.

Updated screenshots/evidence are protected and ignored under
`venv/stage3c3-f1-artifacts/`: `guided-390.png`, `guided-390-viewport.png`,
`product-detail-390.png`, `access-investigation.json`,
`geometry-before-and-candidate.json` and `browser-review.json`.
All 40 production table checksums/metadata, original SQLite SHA and original
stash remain unchanged. No application authorization/logic/schema changes,
production writes, staging, commit or push. Stop for owner visual review.
