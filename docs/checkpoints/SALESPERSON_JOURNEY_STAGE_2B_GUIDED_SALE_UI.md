# Salesperson Journey — Stage 2 Closure and Approved Guided Sale

Date: 2026-10-07. Stage 2A is technically approved. Stage 2B Guided Sale visual
structure is product-owner approved. Stage 3 has not started.
Delivery checkpoint: V3.0.12 — add guided sale catalog experience.

## Authority and approval

Behavior remains governed by SALESPERSON_JOURNEY_APPROVED.md and
SALESPERSON_JOURNEY_IMPLEMENTATION_CONTRACT.md. The Stage 2A catalog checkpoint
records the backend implementation; this closure records its subsequent approval
and the final approved Stage 2B presentation. Neither approved specification nor
Stage 0/1 contract was changed.

The mobile Guided Sale portion of Persian Sales App UI Mockups.png is the
primary visual reference, with Persian AI Sales Recommendation Flow.png used
for recommendation-specific presentation and the secondary Detail treatment.
These images under D:\UI References\salesperson-journey are visual targets,
subject to truthful data and the approved stage boundaries. Illustrated product
facts/photos/prices are not seed data. All six journey references were inspected.

There is no approved desktop mockup. Mobile is authoritative; tablet/desktop
use the same mobile card zones within centered, bounded content, with a maximum
of two product columns. Three columns are prohibited.

## Approved catalog behavior

- Full active, catalog-visible products remain discoverable. Saved recommended
  products lead; ordinary products follow with بدون اولویت ویژه.
- Recommendation candidate exclusion is not sale exclusion. Saved ranks/order
  remain unchanged by browsing, search, filters or current commercial facts.
- Real category chips come from the API's actual category data. Priority filtering
  is separately labeled; search, categories and pagination retain existing semantics.
- Signed actor/customer/visit-bound context persists through filtering, pagination,
  browser history and Product Detail return. Stale/expired context is surfaced;
  no silent re-ranking, regeneration, token reset or automatic retry.
- Existing customer assignment/active-role and owned matching-visit authorization
  remains server authoritative. Staff/manager operational access is not added.
- Catalog/Guided/Detail reads create no recommendations, requests/lines, feedback,
  visits, snapshots, prices, stock changes or historical sales.

API: GET /api/products/v1/catalog/; HEAD/OPTIONS supported; no mutations.
Search/category/priority/page/context, counts, item availability, saved lineage
and bounded Detail destinations remain the Stage 2A wire contract. Relevant
service regression coverage fixes query count at eight for 6 and 86 products.

## Final approved presentation

The hierarchy is app header/customer/visit, search and real category chips,
recommendation-first section, ordinary section, and in-flow pagination. The
existing quiet Visit Review destination remains a navigation action only.

Cards use the reference's left image slot, primary product identity, distinct
readable product code and amber saved-priority treatment. Brand/category are
tertiary metadata, omitted visually when already repeated in the product name;
underlying values and Detail remain available. Ordinary cards share the visual
system without disabled styling or recommendation feedback.

One truthful cue is selected verbatim from the supplied saved recommendation;
the full supplied short explanation is available on expansion/Detail. No timing,
demand, affinity, percentage or new commercial signal is inferred.

Inventory is a small secondary commercial status, outside the quantity-control
slot. Current sellable stock remains canonical: max(available - reserved, 0).
Zero and unknown inventory remain visible and truthful, with unknown distinct
from zero. Later priced mutations must revalidate stock/quote/access.

The price region remains in the reference footer position. It shows price
availability without an invented amount: قیمت پایه plus در دسترس نیست or
ثبت شده است. Stage 2A returns demo-price existence, not a numeric customer quote.
There is no historical-price fallback, discount, final price or pricing provider.

The structural footer regions for quantity | price | primary Add are preserved.
Quantity/Add regions are empty, non-interactive and excluded from accessibility
navigation; no fake enabled or disabled operational controls are presented.
Product Detail is a separate secondary light-blue/outlined eye action, retaining
validated customer/visit/category/search/page/context and selected-product return.
Existing recommendation-based and manager Detail return contracts remain intact.

Real image references remain unavailable. The fixed image containers retain
intentional fallback visual weight; no mockup photos or fabricated product art
were used. Scoped navy/amber/surfaces follow the references while using available
fonts and matching hierarchy, weights and line heights. Global/manager styling,
Daily, Customer360, Product Detail and Review layouts were not redesigned.

The approved anatomy must be extended in place when later functions arrive:
insert real quantities, quotes and Add into their reserved regions rather than
redesigning the cards. Visual richness from real images, pricing and functioning
sales/feedback actions remains deliberately deferred.

## Deferred stage boundaries

No basket/Add/update/remove, quantity persistence, recommendation feedback or
rejection persistence, grade-discount/final-price calculation, submission,
request review/success, prepared-message generation, messaging or visit completion
integration is implemented by Stage 2. Legacy PURCHASED, realized Sale/SaleItem,
visit lifecycle, follow-up and manager behavior remain unchanged.

No schema/model/settings or migration was changed in Stage 2. The existing Stage 1
schema was applied only to isolated test/preview databases. The real developer
DB remains unmigrated; any normal-runtime schema application requires separate
approval and is not part of this checkpoint commit.

## Visual and automated evidence

Product-owner approval covers the final structure and the conservative responsive
adaptation. Prior isolated browser verification at 390/768/1440px confirmed true
RTL, no horizontal overflow, readable code/cues, >=44px operational targets,
truthful stock, empty reserved regions, secondary Detail, fourteen catalog cards,
the three saved priorities/order, same-context category/priority filtering,
pagination and Detail return/focus. No JS exceptions or mutation requests occurred.

Read-only preview used existing SP001/C0003 data plus isolated active Visit 37,
not a reopened shared Visit. Assets/reports are outside Git under
%TEMP%/salesperson-journey-stage2b, including final-guided-390.png,
final-guided-768.png, final-guided-1440.png and final-fidelity-browser-report.json.
No screenshot, temporary database, preview script/profile/log or local/generated
artifact belongs to this commit.

One final Stage 2 regression is required before committing: Django check, full
Django suite, the four relevant JS fixture files, all applicable JS syntax,
migration drift and diff whitespace. Record the exact executed results below;
stop without committing/pushing if any validation fails.

Final regression results (each suite executed once for closure):

- Django check: no issues, 0 silenced.
- Full Django suite: 320 tests passed; isolated test database destroyed normally.
- Guided JS: 23 tests passed. Three retained legacy JS fixture files passed their
  20 scenarios. Node's combined runner reports 26 passing entries, 0 failures.
- JS syntax: all 15 applicable JS/CJS files passed.
- Migration drift: No changes detected; no migration created/applied locally.
- git diff --check: passed.
- Real database hash and original stash unchanged after validation.

## Database investigation and delivery safety

Accepted source baseline: fast-track, HEAD/origin both
b9e43a69d7e57e141b6718ab0f0458f9e8a5ff8b before this closure. The only content
change during closure is this checkpoint update; implementation remains approved.

Real db.sqlite3 is tracked but its modified working copy is intentionally local-only.
It must NEVER be staged or committed. Accepted current SHA256:
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15.

The prior E499... hash changed with high confidence through normal Django
login/session writes at 2026-10-07 12:49:17 UTC. Comparison against the earlier
isolated copy found only user last_login and session signing/expiry changes;
the decoded session payload and existing business rows matched. Read-only SQLite
quick_check was ok and foreign_key_check reported no violations. No meaningful
business-data loss/corruption was found. Leave the real DB exactly as-is.
No reset, restore, copy, migrate, seed, vacuum or repair is part of delivery.

Original stash remains untouched:
2dac7bdc26f07f611f471564476ceaa52ec367cc
(home-local-files-before-fast-track-work-2026-10-05).

Stage 2 delivery includes only its approved source/test/checkpoint files. Commit
subject: V3.0.12: add guided sale catalog experience. Push only fast-track to origin.
Stage 3 remains unstarted and requires its own authorization.
