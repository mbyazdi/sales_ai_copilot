# Stage 3H2 — Customer360 Finish navigation refresh

Baseline: fast-track / V3.0.20
`abe235f607056cf8e04e1c49dcfecf915939af5f`. Technically and visually approved
by the owner for V3.0.21 closeout. Reused the interrupted implementation.

## Root cause and bounded correction

The server rendered the Finish navigation only for IN_PROGRESS Visits. Starting
a PLANNED Visit updated the badge and legacy completion control in JavaScript,
but no Finish navigation element existed until a new page request.

For an authorized salesperson's PLANNED Visit, render the existing navigation
position as a hidden anchor without href. Store only the server-reversed,
customer/Visit-specific destination in data-finish-url. IN_PROGRESS pages retain
the ordinary functional link. Manager, missing/foreign, COMPLETED and CANCELLED
contexts do not receive this placeholder.

After a successful lifecycle response, synchronize the link using the confirmed
Visit ID and status: only the current Visit's IN_PROGRESS response reveals the
unchanged destination. A confirmed legacy completion hides it and removes href.
Failed/pending requests never activate it. No link is invented when the server
has not provided one. Update the scoped script cache version.

No API, authorization, signing, Visit mutation, legacy completion behavior,
confirmation, layout, CSS, price, basket or submission change. The Finish page
and its protected API remain authoritative. No automatic completion or new retry.

## Focused validation

- PostgreSQL: 38/38 passed, zero failures/errors/skips, covering journey rendering,
  authorized/non-active navigation, Finish UI and legacy completion regressions.
  Disposable test database was removed; canonical production state was unchanged.
- The interrupted run's only failure was a new test expecting anonymous HTTP 302.
  Existing Customer360 access correctly returns 403; the new test now asserts
  that denial and absence of the Finish link. No security behavior was changed.
- JavaScript: 25/25 passed in the interrupted run; the JS source/tests were
  preserved during recovery. Includes seven new tests for pending/confirmed Start,
  denied/network responses, mismatched Visit, inactive states and legacy completion,
  plus affected outcome and Finish regressions.
- Django check: no issues. Migration drift: no changes. JS syntax and whitespace
  checks passed. No full regression suite.

Real Chrome at 390px and 1440px: PLANNED link hidden, no href and zero rendered
height; one Start POST per Visit; matching response reveals the correct 44px link
without a document reload (document nonce retained, no extra Customer360 GET).
Followed the link, cancelled confirmation with no completion POST, then explicitly
completed the mobile fixture. Completed/cancelled/mismatched contexts have no
Finish link; anonymous Customer360 returns 403. No fatal page JS errors or overflow.

## Isolated review and evidence

Preview: http://127.0.0.1:8799/accounts/login/
Username: isolated-preview-sp001. Protected TEST-password workflow:
`.\venv\stage3h2-preview\start-preview.ps1 -CopyPassword`.

Database: `test_stage3h2_demo_20261015085103_5b51183e`, 50 migrations,
normal Django sessions and least-privilege runtime role. Fresh synthetic fixtures;
no production records/password hashes copied. Existing previews and credentials
were not reset or overwritten. Migration 0003 was applied only in isolation.

Active owner-review URL:
http://127.0.0.1:8799/customers/?customer_code=C0013&visit_id=2

Protected browser evidence and screenshots:
`D:\py project\sales_ai_copilot\venv\stage3h2-artifacts\`

- 01-planned-no-finish-390.png
- 02-started-finish-visible-390.png (initial scroll capture)
- 03-started-finish-visible-1440.png
- 04-completed-no-finish-390.png
- 05-active-finish-navigation-390.png (settled mobile link viewport)
- browser-evidence.json: response/navigation counts, document nonces and restrictions.

## Preservation and remaining scope

Production data/schema/sequences remain unchanged, on 49 migrations; production
deployment of 0003 and current-date demo planning remain separately authorized
prerequisites from Stage 3H1. Neither is implemented here.

Original SQLite SHA256 remains
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 planning and all existing preview credentials are preserved.
No schema/model/migration change.

## V3.0.21 closeout validation

Fresh focused run: PostgreSQL 38/38 and JavaScript 25/25 passed, with zero
failures/errors/skips. Django check, migration drift, JS syntax and whitespace
checks passed. Disposable database test_v3021_20261015090519_e483f654 was created
and removed; canonical production reconciliation remained unchanged. No full
suite or browser rerun. Commit boundary is exactly the approved template, script,
Python journey tests, JS navigation tests and this checkpoint. SQLite, credentials,
private artifacts and unrelated DEMO-02 planning remain excluded.
