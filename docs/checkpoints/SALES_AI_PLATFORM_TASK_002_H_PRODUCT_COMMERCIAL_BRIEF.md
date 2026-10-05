# Task 002-H — Customer-context product commercial brief

Status: final live visual and product approval granted; final validation passed.
Commit/push authorized for the approved nine-file task. Task 002-I is not started.

## Approved scope and baseline

The user approved a bounded read-only Commercial Decision → Sales Action bridge,
not full Product360, Product Advisor, catalog/search, Guided Sale or basket/order.
Persian RTL presentation reuses the approved shell and ds foundations.

Baseline verified in D:\py project\sales_ai_copilot on fast-track:
HEAD = origin/fast-track = 89a6ed0a5c4cf69d07eae0ef061634d5b43e5ade.
Only db.sqlite3 was already modified. Existing home-local-files stash remains
untouched. No fetch/pull was needed. AGENTS.md and the architecture/master-plan
and relevant Customer360/002-G checkpoint evidence were reviewed before edits.

## Route, hierarchy and continuity

HTML route: `/products/<product_code>/?customer_code=<customer_code>`.
Customer code is required; there is no standalone global product experience.
Optional `visit_id` is validated before any commercial-context reads.

1. Product identity: stored name/code, brand/category, description, unit/package.
2. Current commercial context: canonical stock status and quantities, inventory
   update timestamp, current eligible promotions and explicit empty states.
3. Why this product: saved active recommendation type/reason/confidence/quality.
   Native collapsed disclosures contain stored signal contributions, rank/score,
   update time and score components. Opening them performs no requests.
4. Return: canonical `/customers/` with customer code and only validated own visit
   ID, anchored to recommendations. No operational controls are duplicated.

Customer360 active recommendation cards gain «بررسی محصول و شرایط فعلی» links.
They retain engine ordering and all existing outcomes/actions. Inactive products
have no brief link. Only valid own salesperson visit context is carried; manager
links have none. No global navigation or shell redesign.

The legacy customer URL name is included under both HTML/API prefixes. Return
navigation explicitly uses `/customers/` to avoid reversing to `/api/customers/`.

## Sources and security decisions

- Canonical `customer_access_queryset` executes before product/visit lookup.
  Active assigned salespeople retain their current customer scope. Staff retain
  the existing active-customer inspection override, without impersonation.
- Missing/inaccessible customer/product and invalid/nonexistent/foreign visit
  combinations return the same generic Persian 404 page without business identity.
  Anonymous/missing/inactive salesperson profiles receive a generic 403.
- A supplied visit must match both customer and the requesting salesperson.
  Staff, including dual-role accounts, cannot carry operational visit context:
  supplied nonempty visit IDs return generic 404. Staff customer-only inspection
  remains available; manager entry links omit visit IDs.
- GET/HEAD only; POST is unsupported. Existing CSRF middleware and mutation/API
  contracts are unchanged. No sales, visit, outcome, recommendation or tuning writes.
- Product metadata comes from Product/Brand/Category. Inventory and promotions
  use `build_product_commercial_context`, sharing the service behind the existing
  customer/product commercial-context API. Date/grade eligibility and sellable
  stock formulas are neither duplicated nor changed.
- Current context uses the actual local date even when an old visit is supplied.
  VisitCustomerSnapshot/VisitCommercialSnapshot remain untouched and are never
  substituted for current stock/offers. Saved recommendation evidence is labelled
  separately; it is not recalculated against current commercial facts.
- CustomerRecommendation provides stored reason/confidence/quality/signals/scores;
  local presentation labels translate existing identifiers only. No LLM invocation,
  new ranking/scoring, financial approval inference or fabricated explanation.
- Missing inventory is unavailable, not zero. Recorded units are shown as stored.
  No product price exists in this master model; none is invented. Recorded fixed
  promotion discount amounts carry no invented currency and say its unit is
  unspecified. Promotion eligibility is explicitly separate from credit approval.

## Files

- apps/products/views.py: scoped read-only HTML view and presentation labels.
- apps/products/urls.py; sales_ai_copilot/urls.py: bounded HTML route registration.
- templates/core/product_detail.html: brief using shared shell/design foundations.
- templates/products/unavailable.html: generic nonleaking unavailable response.
- templates/core/customer_360/_ai_recommendations.html: recommendation entry links.
- static/products/css/product_brief.css: scoped responsive RTL layout.
- apps/products/tests_commercial_brief.py: isolated regression fixtures/tests.
- This checkpoint.

No models/migrations, dependencies, API/service/calculation changes, new hierarchy,
pricing/quantity policy, reservation, AI tools, login or frontend migration.
No product JavaScript is needed; native disclosures and server rendering avoid
asynchronous loading races. Empty/unavailable states are server rendered.

## Validation — 2026-10-05

Executed with the existing virtual environment:

- `python -B manage.py check`: no issues (0 silenced).
- `python -B manage.py test apps.products.tests_commercial_brief --noinput`:
  **25 passed**.
- `python -B manage.py test --noinput`: **152 passed** (127 baseline + 25 new).
- `node --check static/core/js/customer_360.js`: passed; file unchanged.
- `git diff --check`: passed; Windows LF/CRLF notices only.

Regressions cover authorized/unauthorized access and nonleaking responses, lookup
order, profile/assignment restrictions, staff/dual-role inspection, own/foreign/
invalid visits, safe return navigation, active product/source/API parity, current
promotion date/grade/product/active filtering, missing/zero/low stock, saved and
absent/missing evidence, rank-preserving links, escaped stored copy, unsupported
POST, zero SQL writes and zero Ollama calls. Historical snapshots remain unchanged
even when their stock differs from current stock and their offers have expired.

Read-only headless Chrome review used actual Django views and current demo data,
authenticated RequestFactory/APIRequestFactory preview requests and a SQLite
`mode=ro` connection, with an additional SQL write guard. It does not replace a
full live login review; session/access behavior is covered by Django client tests.
Both sales1 and manager1 were reviewed at 1440, 768 and 390 pixels:

- No whole-page horizontal overflow, including expanded evidence.
- No runtime exceptions or mutation network requests.
- Native disclosures collapsed initially and opened with keyboard Enter.
- PHI002 shows 150 sellable PCS from the canonical source, plus 180 recorded,
  30 reserved and minimum stock 40; no currently eligible promotion is fabricated.
- Daily Workspace → C0003 → PHI002 carries owned visit 22 and returns with it.
  Manager Customer inspection returns without a visit context or operational controls.
- Missing customer-code URL shows the generic unavailable state without product identity.

Temporary preview scripts/browser images are outside the repository. Nothing was
seeded/reset/migrated and no tuning or outcome action was performed for review.

## Database safety

db.sqlite3 was already locally modified. SHA256 before and after validation:

`EF6513572D171A768D4A58C1E3CC3C1655CE48DB7443D82BD6A510BB786F46ED`

The existing modification is preserved exactly, unstaged and uncommitted.
Tests use Django's isolated test database; the tracked database is not altered.

## Manual review and limits

Sign in as sales1 → فضای کار روزانه → C0003 → پیشنهادها و نتیجه تعامل →
PHI002 / recommendation 423 → «بررسی محصول و شرایط فعلی».
Inspect current stock/offers, stored reason/confidence, expand evidence, then
«بازگشت به پیشنهادهای مشتری» and confirm valid visit continuity.
Direct customer-only path: `/products/PHI002/?customer_code=C0003`.
For the current owned demo visit: append `&visit_id=22` as sales1 only.

Sign in as manager1 → مشتریان → C0003 → same product link. Confirm read-only badge,
absence of operational controls and return without visit_id. Review at desktop,
768px and 390px. Do not start/complete visits or save outcomes solely for review.

Existing demo descriptions may repeat the English product name, as PHI002 does;
there are no rich approved product benefits/specifications/media to fabricate.
Demo promotions ended on 2026-09-30; the empty eligible-offer state on 2026-10-05
is intentional. Dates remain Gregorian and stored units/names remain source data.
No global catalog or product search is introduced. Live visual/product approval
remains pending; stop without commit/push or Task 002-I.

## Final presentation polish — 2026-10-05

The user granted structural approval and requested only presentation refinements
to product identity and saved recommendation evidence. Final visual approval is
still pending. This pass changes views.py presentation context, product_detail.html,
product_brief.css, focused presentation tests and this checkpoint only.

The first evidence disclosure now emphasizes the saved Persian reason, existing
type/quality/confidence/rank/final score and compact active non-zero signal cards.
Signal filtering selects existing structured values in source order, including
negative active contributions; it creates no scores, strengths, labels or reasons.
Absent active non-zero evidence has an explicit truthful empty state.

Nested «جزئیات فنی امتیازدهی» is collapsed by default. It retains the complete
signal list including zeros, source update/count metadata and the existing score
composition disclosure. Modern CSS :has selectors hide the collapsed preview when
business evidence opens, hide summary cards while the complete technical list is
shown, and hide overlapping signal rows/business score when composition opens.
This avoids simultaneously repeating the same evidence values, without JavaScript
or removal of stored detail. All disclosures remain native and keyboard accessible.

Descriptions matching the displayed product name after whitespace/case normalization
are suppressed only in presentation. Distinct descriptions and existing absent-data
copy remain; Product.description and all source records are untouched.

Validation rerun:
- Django check: no issues (0 silenced).
- Focused 002-H suite: **31 passed** (25 original + 6 presentation regressions).
- Full suite: **158 passed**.
- Unchanged customer_360.js syntax check: passed; no application JS changes.
- git diff --check: passed; Windows LF/CRLF notices only.
- Read-only authenticated Chrome preview, sales1 and manager1 at 1440 and 390px:
  no overflow, runtime exceptions or mutation requests. Keyboard opening of both
  evidence layers passed, technical disclosure starts collapsed, duplicate rows
  are not simultaneously visible, and all saved signal values match the existing
  customer-scoped recommendation API. PHI002 business summary contains five active
  non-zero signals; technical detail retains all eight signals and ten score
  components. Its redundant product description is suppressed. Stock/offers and
  validated return navigation remain unchanged. Full live login review remains
  the user's approval step; preview uses SQLite mode=ro and rejects SQL writes.

The database already had a different local hash at entry to this polish than at
initial implementation. That pre-existing state was preserved, not restored.
SHA256 before/after this presentation pass is identical:
`B46DB8F247829B1FA4E256EFC930FCD0C70B2EDFACAEC0970F2536342B6F060C`.

No business calculations, API contracts, access rules, ordering, recommendation
engine, current inventory/promotions, visits, models/migrations or data changed.
No stage/commit/push and no Task 002-I. Review the existing PHI002/C0003 path,
expand «مشاهده شواهد و جزئیات پیشنهاد», then «جزئیات فنی امتیازدهی» and optionally
«ترکیب امتیاز ثبت‌شده». Stop for final visual approval.

## Final approval and handoff

The user granted final live visual and product approval for 002-H, including the
business-oriented saved-evidence summary, complete technical scoring details
behind collapsed disclosures, and presentation-only suppression of descriptions
that repeat the product name. This approval supersedes the earlier pending notes.
No additional product or visual changes were made during finalization.

Final validation rerun: Django check clean; **31 focused tests passed**;
**158 full-suite tests passed**; customer_360.js syntax check and git diff --check
passed. No schema, business calculations, API contracts or authorization changes
were introduced during polish/finalization.

db.sqlite3 SHA256 before and after final validation is identical:
`B46DB8F247829B1FA4E256EFC930FCD0C70B2EDFACAEC0970F2536342B6F060C`.
Its pre-existing local modification is preserved and explicitly excluded from
staging/commit. The existing stash is untouched. Only the nine approved task files
are eligible for commit/push. Stop all development after successful push verification;
do not start Task 002-I.
