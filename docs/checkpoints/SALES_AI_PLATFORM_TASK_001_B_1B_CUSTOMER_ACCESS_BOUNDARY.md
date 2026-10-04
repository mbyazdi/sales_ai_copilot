# Task 001-B.1B — Current Customer Access Boundary

## Approved policy

Current customer access requires authentication and either Django staff status
(temporary management override) or an active Salesperson profile with an
`is_active=True` CustomerAssignment for that customer. Assignment dates do not
add eligibility conditions in this task. No organizational hierarchy is added.

`apps/customers/access.py::customer_access_queryset` applies this boundary before
direct customer-code/object lookups. Anonymous, missing-profile and inactive-profile
callers receive 403. Customers outside an active salesperson's assignment return
404 from the scoped lookup, matching nonexistent objects.

## Secured entry points

- Customer search HTML, under both `/customers/` and `/api/customers/`.
- Customer360 API, under both customer URL prefixes.
- Customer recommendations and customer recommendation performance.
- Customer sales history and outcome history.
- Visits customer recommendation-performance API.
- Product/customer commercial context.
- AI Sales Copilot current customer context, including visit-scoped requests.

The global sibling recommendation-performance API is staff-only so it cannot
expose unassigned customer data through an aggregate route. Authorized response
payloads and deterministic business calculations remain unchanged.

Historical Visit ownership is independent: existing visit operations continue
using their ownership rules. An owned historical Visit does not authorize
current Customer360 or AI customer context after assignment is inactive.
Task 001-B.1A AI visit checks still require an active salesperson and an owned,
customer-consistent Visit, including for staff callers supplying a visit ID.

## Customer-only AI defect

The AI view previously passed `commercial_context=None` without a visit even
when a primary recommendation was available. It now calls the existing
`build_product_commercial_context` for that recommendation's product and the
authorized customer. Inventory and eligible promotions use the existing builder;
no synthetic context, prompt changes or commercial-decision changes are added.

The regression uses real inventory records and checks the context passed to the
real sales-session builder and the generator boundary. External generation is
mocked. The existing no-primary-recommendation path is not redesigned here.

## Validation and limits

The endpoint matrix covers assignment access, missing/inactive profiles, staff,
anonymous callers, both HTML prefixes, duplicate assignments, direct primary-key
lookup, revoked assignments, historical ownership and AI denial before session
building/generation. Existing Recommendation/Visit and Task 001-B.1A tests remain.

This policy does not add prospecting, supervisor/territory scope, assignment-date
semantics, or organizational permissions. Internal deterministic services remain
usable by trusted callers; the access boundary is applied at HTTP entry points.

Executed validation with the existing virtual environment:

- `manage.py test apps.visits.tests_authorization`: 35 passed.
- `manage.py test apps.recommendations`: 4 passed.
- `manage.py test apps.visits`: 50 passed.
- `manage.py test`: 54 passed.
- `manage.py check`: no issues.
- Tracked and new-file diff whitespace checks: passed.
- `db.sqlite3` SHA-256 unchanged before/after validation.

No model, migration, dependency, frontend or demo-data changes; no commit/push.
