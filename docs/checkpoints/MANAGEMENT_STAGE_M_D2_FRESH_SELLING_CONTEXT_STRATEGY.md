# Stage M-D2 — Fresh Selling Context Strategy Integration

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Authority: approved M-A2 and M-C1 through M-D1; latest M-D2 resume instruction.
Status: source-only implementation validated in disposable databases; NOT DEPLOYED.

## Recovery findings

Branch/HEAD/fetched origin matched the expected baseline; index was empty.
No partial M-D2 source/tests/checkpoint existed. The previous interruption had
only inspected context issuance. Existing approved strategy work was reused.
Original SQLite hash and stash matched before editing. No reset, clean, stash
application or unrelated rewrite.

## Lifecycle and integration inventory

- `saved_priority` remains the single signed-context issuer/reuse boundary.
  No token means fresh issuance; a supplied token is validated and reused.
  An invalid, stale, foreign or malformed token never becomes a fresh context.
- `GET /api/products/v1/catalog/` issues/reuses context for Guided Sale.
  Filters, pagination, detail links, browser history and reload retain its token.
- `/customers/{code}/recommendations/presentation/` supplies the Guided Sale
  shell. Its back link now retains any supplied context; the catalog API owns
  actual card ordering. Legacy selected-recommendation navigation remains.
- Customer360 HTML `/customers/?customer_code=...&visit_id=...` and optional
  Visit-scoped `/api/customers/v1/customer-360/{code}/` use the same resolver.
  Customer360 requests without a Visit and manager inspection retain engine
  ordering; no operational Visit/customer is fabricated.
- A fresh policy-backed Customer360 HTML read redirects once to its signed URL.
  Existing tokens are never replaced. Neutral HTML retains legacy 200/render
  behavior: browser JS retains the neutral token in URL/Guided Sale/product links.
  Neutral context retention, like Guided Sale's existing transport, requires JS.
- Product Detail validates supplied context for its default/presentation return
  paths. Existing catalog return validation is reused. Standalone Product Detail
  feedback bootstrap is another fresh catalog consumer: it now retains its new
  token in the browser URL and customer return links. It rejects replacement of
  an already supplied token.
- Basket Add and feedback validate the original signed priority. Existing
  receipt replay runs before current context evaluation, as before.
- Basket edits/removals, Review/Result and Submit retain the existing V1
  `_captured_context` boundary: no policy lookup and no new expiry restriction.
  Completion remains independent of policy. Completion/daily-plan navigation
  does not issue recommendations; return via existing signed history remains
  available. No Submit/Completion status/acknowledgement/UUID change.

## Shared resolver and freshness

`apps/management/selling_strategy.py::resolve_fresh_strategy` uses the approved
pure evaluator. M-C3's fact extraction is shared through `_context_facts` and
`_capture_facts`; the management wrapper still requires management permission.
The salesperson wrapper revalidates normal catalog ownership/assignment, never
impersonates a manager and never activates a draft.

Absent head/active policy uses legacy saved ordering. Active capture requires a
top-level PostgreSQL REPEATABLE READ / READ ONLY transaction. A caller-owned
transaction may use the neutral legacy path; active evaluation fails closed
rather than inheriting weaker isolation. Date derivation explicitly uses
`ZoneInfo("Asia/Tehran")`, independently of host/default timezone.

The resolver validates active configuration/algorithm/hash and immutable
PUBLISH/ROLLBACK evidence. A head pointer to an unpublished draft, missing grant,
corrupt configuration or absent publication proof cannot silently fall back to
neutral/unlocked evaluation. Existing signed contexts need none of those current
policy reads.

Only the active configuration is evaluated; an unpublished draft is ignored.
Capture and ORM recommendation rows share one MVCC image. Publication racing
with issuance yields one complete old/new policy image, never mixed evidence.
Source changes committed after that image do not retroactively alter it.
This is not stock reservation or a current-at-commit commercial guarantee.

No engine call, candidate expansion, saved-row rewrite, policy initialization,
comparison insertion or business write occurs during strategy evaluation.
The shared source adapter retains the M-C3 5,000-row fail-closed bound.

## Signed and selection lineage contract

The existing salt, version=1 binding (actor/salesperson/customer/Visit), signature
checks, recommendation fingerprints and eight-hour read lifetime are retained.
An optional signed `strategy` V1 extension binds:
- Active version, head revision, algorithm and configuration hash.
- Explicit date/timezone, aggregate and per-source fingerprints.
- Ordered recommendation fingerprint and effective recommendation ID order.
- Base score/rank/priority, effective position/priority and individual
  priority/target/promotion contributions with Persian reason data.
- Canonical evidence digest.

No source database endpoint/credentials or raw capture document is put in the
extension. Token size remains bounded by the existing 100,000-character limit.
Reuse validates the extension and signed row identities, but does not read the
active policy, reevaluate targets/promotions, resign or refresh the context.
Existing engine-row changes/expiry still fail under the pre-existing contract.

Only newly added recommended lines/new feedback events gain `lineage_snapshot.strategy`.
Original rank/score/reasons remain separate. Ordinary products are not ranked
and create no recommendation feedback. Existing selected lines, receipts, events,
prepared messages and submitted/Visit snapshots are never rewritten by
publication. Old UUID/intent/revision and uncertain pending payloads replay
against their original evidence.

Guided Sale and Customer360 expose separate base score/effective priority and
Persian factor explanations. Effective priority is explicitly not confidence or
purchase probability. Current catalog visibility, inventory/addability, quote
fingerprints, grade discounts, whole-TOMAN pricing and stock limits remain
independent and authoritative.

Overview now truthfully reports selling-context integration in this source.
New publication results say `FRESH_SELLING_CONTEXTS_ONLY`; previously stored
receipt results, including older descriptive scope text, replay unchanged.

## Real ranking evidence (disposable fixture)

| Recommendation | Base score | Saved rank | Base priority | Overlay | Effective priority | New position |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 101 | 40.0000 | 1 | 30.00 | 0.00 | 30.00 | 2 |
| 102 | 90.0000 | 2 | 20.00 | 0.00 | 20.00 | 3 |
| 103 | 70.0000 | 3 | 10.00 | 27.50 | 37.50 | 1 |
| 104 | 60.0000 | 4 | 0.00 | 0.00 | 0.00 | 4 |

Published product priority 20 + target contribution 2.50 + promotion emphasis 5
moves 103 first. These are actual asserted synthetic test results, not persistent
Demo facts or predicted uplift. Saved ordering remains 101/102/103/104 in the DB.
Neutral/new neutral contexts preserve it; old non-neutral tokens keep their
103/101/102/104 order after subsequent neutral publication.

## Focused validation

Confirmed executions (overlapping selections, not additive unique-test counts):

| Selection | PostgreSQL | In-memory SQLite |
| --- | --- | --- |
| Initial integration/commercial regression selection | 234 passed | 223 passed, 11 PG-only skips |
| Broader pricing/management selection | final PG result not relied on | 281 passed, 12 PG-only skips (293 discovered) |
| Final affected selling context/Product Hero/catalog/Customer360/API selection | 77 passed | 75 passed, 2 PG-only skips |
| Explicit Tehran date versus UTC host/default | 1 passed | 1 passed |

Final affected JS selection: **92 passed**, zero failures/skips. Includes Guided
Sale, Basket, Feedback, Customer360 Finish and Product Detail feedback/recovery.
Earlier query regression was fixed by removing redundant neutral access reads:
fresh catalog adds one policy SELECT (9 queries in its existing fixture); signed
reuse retains the exact 8-query budget even with 86 catalog products.
Runtime follow-up initially exposed a missing Visit SELECT in the disposable
management-only test role; its journey setup now grants that one read privilege.
A new neutral-retention test initially omitted customer/Visit query parameters in
Django's client request; corrected the fixture request, not application behavior.

Tests verify neutral parity, real publication, old/new context stability, same
Customer360/catalog order/evidence, Product Detail round-trip, independent real
runtime credentials, missing-grant failure without blocking old token reuse,
unpublished draft rejection, publication-during-capture concurrency, lineage,
feedback/Basket replay and unchanged quote fingerprints. Existing Basket,
Feedback, Submit and Completion/acknowledgement regressions remain passing.
Unknown stock, zero stock and missing price remain separately non-addable.
All non-strategy business-row digests match across read evaluation.

The focused runner applies the unchanged 51-migration graph only to verified,
UUID/OID/comment/endpoint-guarded disposable databases. Journey tests install
the unchanged approved REFERENCE_LOCKS_V1 SQL there using the existing exact
installer, independent NOLOGIN capability owner and independent runtime role.
No runtime reference UPDATE grants. No persistent capability/grant deployment.
Confirmed runs removed all disposable resources; a final read-only cluster check
found zero strategy test DBs and zero associated test roles.

Django checks, migration drift, affected route assertions, Python/JS syntax and
tracked/scoped whitespace checks passed. No new migration or full suite.
Reproducible focused runner: `python -B -m apps.management.verify_selling_strategy`;
`--sqlite` uses in-memory SQLite. Delta selections retained earlier successful
unchanged evidence instead of repeatedly rerunning all scenarios.

## Exact M-D2 file inventory

- `apps/customers/js_tests/customer_360_finish.test.cjs`
- `apps/customers/js_tests/guided_catalog.test.cjs`
- `apps/customers/presentation_views.py`
- `apps/customers/views.py`
- `apps/products/catalog.py`
- `apps/products/js_tests/product_feedback.test.cjs`
- `apps/products/tests_catalog.py`
- `apps/products/views.py`
- `apps/recommendations/catalog_context.py`
- `apps/recommendations/feedback.py`
- `apps/sales_requests/basket.py`
- `static/core/js/customer_360.js`
- `static/core/js/guided_catalog.js`
- `static/products/js/product_feedback.js`
- `templates/core/customer_360/_ai_recommendations.html`
- `templates/core/customer_360/_guided_entry.html`
- `apps/customers/selling_context.py`
- `apps/management/selling_strategy.py`
- `apps/management/strategy_api_reads.py`
- `apps/management/strategy_services.py`
- `apps/management/strategy_snapshots.py`
- `apps/management/tests_selling_strategy.py`
- `apps/management/tests_strategy_services.py`
- `apps/management/verify_selling_strategy.py`
- `apps/management/verify_strategy_foundation.py`
- `docs/checkpoints/MANAGEMENT_STAGE_M_D2_FRESH_SELLING_CONTEXT_STRATEGY.md`

M-C3 extraction preserves its public service authorization/transaction contract.
M-C4 changes only future result scope text plus its assertion; M-D1 changes only
the integration-readiness projection. The runner changes are optional,
disposable-only setup. Original models/migration, evaluator, management APIs,
pricing arithmetic, assets, settings and launchers remain unchanged.

## Preservation and deployment boundary

Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Original PostgreSQL never connected to. Persistent Demo all-user-table and
sequence digests matched before/after the confirmed disposable runs; generation,
fixtures, sessions and credentials were not changed. No service restart,
deployment, Gate V2 activation, Prepare Day, reset or generation switch.
Unrelated DEMO-02 planning and prior checkpoint files preserved. Index empty;
no staging/commit/push.

No M-D2 implementation blocker remains. Persistent deployment is separately
NOT APPROVED. It requires reviewed schema/migration deployment, source-compatible
reference-lock prerequisites for existing Feedback/Submit, runtime SELECT on
strategy policy/version/publication evidence and source facts, ordinary journey
grants, backup/rollback/readiness authorization, and coordinated compatible
client asset deployment. Do not run the deferred Demo launcher incidentally.

Management UI, candidate expansion and Impact analytics remain out of scope.
A frozen rank/selection lineage is not causal revenue attribution or realized
sales; further analytics/context-expiration/refresh UI require separate approval.
STOP for owner review.
