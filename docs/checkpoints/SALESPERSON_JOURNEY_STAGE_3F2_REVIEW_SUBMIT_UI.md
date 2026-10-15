# Stage 3F2 — Review, confirm and submission result UI

2026-10-15; implemented, awaiting owner visual review. Baseline V3.0.18
`1f86206e970e18a15f6b9479cfb23c963b612eb5`, fast-track, with uncommitted approved
[Stage 3F1 backend](SALESPERSON_JOURNEY_STAGE_3F1_REVIEW_SUBMIT_BACKEND.md).
The approved journey, Stage 0/3 contracts and F1 owner decisions remain authoritative.

## Flow and routes

The Guided basket exposes «مرور و ثبت درخواست» only for a nonempty DRAFT after
authoritative state is loaded and no basket/feedback command is pending. Existing
cards, price areas, images, feedback controls, filters and Product Detail are unchanged.
The link carries signed selling context and search/category/priority/page values.

- GET/HEAD `/customers/<code>/visits/<id>/sales-request/review/`: authorized page
  shell; JS uses the existing GET review API. Missing context allows inspection
  but disables confirmation and directs the user to enter through Basket.
- GET/HEAD `/customers/<code>/visits/<id>/sales-request/result/`: authorized frozen
  submitted details. DRAFT redirects to review without mutation.
- POST page routes are not submission endpoints. Explicit confirmed Submit uses
  the existing `/api/sales-requests/v1/visits/<id>/submit/` only.

Pages require normal Django login, active salesperson/current assignment and the
matching owned Visit. Signed context is checked when supplied; it never grants
authorization. Local return destinations are constructed from validated context,
not arbitrary redirect URLs. Submitted results use frozen customer identity.

## Review and confirmation

Persian RTL, bounded 900px content and UI-04 navy/teal/mint card language. Review
shows product names, quantity, saved base/final unit prices, percentage/line discount,
final line amount, inventory, validation issues and authoritative request totals.
Amounts are formatted from server strings; JS never calculates commercial values.
When a current price differs, the new price is shown separately from saved terms.
Missing/unknown/zero stock and unavailable prices remain distinct.

An explicit native confirmation dialog shows item count and final amount and says
this registers a Sales Request, not a completed purchase. No automatic Submit.
PLANNED/closed/invalid drafts cannot confirm. Dialog controls are disabled while
sending; Escape cannot dismiss an in-flight confirmation. Focus moves to confirm.

PRICE_CHANGED requires an explicit existing basket re-quote, then fresh review.
Changed stock, stale revision and other conflicts display Persian guidance and
require renewed review; nothing silently replaces accepted prices or quantities.

## Durable client recovery and result

Before POST, persist a command envelope in tab-scoped sessionStorage keyed by
actor/customer/Visit. It contains a frozen wire payload, UUID, expected revision,
signed context and accepted review fingerprint, plus original display amount/count.
Storage failure prevents sending. Reload performs GET only; no automatic POST.

Ambiguous response/network failure preserves the exact payload. Explicit status
recovery GET obtains canonical DRAFT/SUBMITTED state. DRAFT does not prove failure
or discard pending intent. An explicit retry requires confirmation and resends
byte-identical payload/UUID. Lost authorization on uncertain retry retains it.
An authoritative submitted read opens the read-only result, without attributing
another writer's success to an unconfirmed command. Successful POST is validated
against request id, applied revision, count, total and SUBMITTED response fields.

The result shows request number/status, frozen lines/totals and prepared text.
The page view removes only the exact delivery-disclosure line from the *presentation
copy* of stored text; the persisted F1 snapshot and API remain unchanged. Copy uses
the server-rendered customer text, not a JS-generated message. The disclosure is
visible separately: «در نسخه فعلی این پیام ارسال نمی‌شود و فقط نمایش داده می‌شود.»
If clipboard access fails, the readonly text is selected for manual copy.

No acknowledgement, Visit completion, reservation/deduction, outbound messaging,
PURCHASED/Sale writes or new request lifecycle is introduced. Daily navigation is
GET only; the page explicitly states that submission has not ended the Visit.

## Exact Stage 3F2 project files

```text
apps/sales_requests/presentation_views.py
apps/sales_requests/tests_review_ui.py
apps/sales_requests/js_tests/review.test.cjs
apps/customers/js_tests/guided_basket.test.cjs
sales_ai_copilot/urls.py
templates/customers/recommendation_presentation.html
templates/sales_requests/context.html
templates/sales_requests/review.html
templates/sales_requests/result.html
templates/sales_requests/unavailable.html
static/core/css/sales_request_review.css
static/core/js/sales_request_review.js
static/core/js/guided_basket.js
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3F2_REVIEW_SUBMIT_UI.md
```

F1's service, API, tests and checkpoint are unchanged. No models/migrations,
pricing logic, Product Detail, authentication or manager surface changes.

## Validation and owner preview

- 45/45 isolated PostgreSQL Django tests passed: 8 review/result tests, 33 approved
  F1 backend tests and 4 existing Guided basket presentation tests. No failures,
  errors or skips. The uniquely named validation database was removed.
- Final JS coverage: 15/15 review/result tests and 26/26 Guided basket tests.
  Initial combined run was 38/38; navigation coverage made it 39/39; two additional
  review safety cases passed in the final 15-test review run. No full suite.
- Django check: no issues. Migration drift: no changes detected. Both modified
  JS syntax checks and tracked/new-file whitespace checks passed.
- Genuine Chrome browser: normal dedicated TEST login, Guided -> Review ->
  explicit confirmation; response deliberately interrupted *after* isolated
  submission. Pending command remained; explicit GET recovery displayed success.
  Exactly one Submit POST, no automatic retry, no fatal JS exceptions.
- 390px and 1440px Review/Success: no horizontal overflow, primary controls >=44px,
  Persian RTL and modal focus verified. Stored message disclosure remains outside
  copied customer text. Submitted reload is read-only.

Independent normal-login previews, original 8790 preview left unchanged:

| Port | Isolated PostgreSQL database | Current state |
| --- | --- | --- |
| 8793 | test_stage3f2_preview_20261014214431_c31ec2e5 | C0003 / Visit 19, DRAFT revision 12, ready for owner review. |
| 8794 | test_stage3f2_success_20261014214557_3e23a76d | Same copied fixture, SUBMITTED revision 13, SR-00000001. |

Start/login: `venv/stage3f2-preview/start-preview.ps1 -CopyPassword` (Draft) or
`venv/stage3f2-success-preview/start-preview.ps1 -CopyPassword` (result).
These protected Git-ignored launchers copy the dedicated TEST password without
printing it. Username: `isolated-preview-sp001`; login `/accounts/login/`.
Separate session/CSRF cookie names avoid disrupting other preview ports.

1. On 8793 open `/customers/C0003/recommendations/presentation/?visit_id=19`;
   select «مرور و ثبت درخواست» to carry the signed context.
2. Inspect quantities, discount, stock, totals and «بازگشت به سبد» navigation.
3. Open confirmation, verify amount/count and cancel unless intentionally testing
   submission in this isolated copy. The Draft copy will then become read-only.
4. On 8794 inspect `/customers/C0003/visits/19/sales-request/result/`, copied text,
   separate no-delivery disclosure and read-only reload. No Visit finish action.

Genuine screenshots (all under `D:\py project\sales_ai_copilot\venv\stage3f2-artifacts\`):
`01-review-390.png`, `02-review-1440.png`, `03-success-390.png`, `04-success-1440.png`.
Protected browser/reconciliation reports are in the same Git-ignored directory.

## Preservation

Production canonical table/sequence/schema reconciliation before/after passed.
Original TEST preview source is byte-value/digest equivalent before/after.
New previews were independent copies; no migrations or production fixtures/seeds.
Isolated submission changed no feedback or basket receipts: both retain six events
and thirteen receipts. Original Visit remains IN_PROGRESS; no completion occurred.
Original SQLite SHA256 unchanged:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash unchanged: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 planning and F1 work preserved; nothing staged, committed or pushed.

## Stage 3F2-F1 — Review and result polish

2026-10-15; awaiting final owner visual review. Submission semantics and routes
are unchanged. The owner explicitly authorized backend message formatting for
**new submissions only**: whole-TOMAN amounts now use Persian digits and U+066C
thousands separators, e.g. `۸۱٬۴۰۰٬۰۰۰ تومان`. Pricing calculations, API monetary
strings, numbering and existing submitted snapshots are unchanged. The generator
is called only on a new successful DRAFT -> SUBMITTED transition; GET and exact
replay continue to return stored text. The separate no-delivery disclosure stays
outside copied customer text. No outbound communication.

Each Review/Result line keeps product name, quantity, final unit price and final
line total immediately visible. Base price, percentage/line discount and truthful
inventory details remain in a native, initially closed per-line details/summary.
Summaries have product-specific accessible names, linked support content, visible
focus and >=44px touch targets. Actionable changed-price warnings remain visible.
The result card now says that Visit completion is separate from request submission;
no new Visit action or route is added. Scoped asset versions were advanced.

Additional files changed by this polish (relative to completed F2):

```text
apps/sales_requests/submission.py
apps/sales_requests/tests_submission.py
apps/sales_requests/tests_review_ui.py
apps/sales_requests/js_tests/review.test.cjs
static/core/js/sales_request_review.js
static/core/css/sales_request_review.css
templates/sales_requests/review.html
templates/sales_requests/result.html
docs/checkpoints/SALESPERSON_JOURNEY_STAGE_3F2_REVIEW_SUBMIT_UI.md
```

Validation: 43/43 focused isolated PostgreSQL Django tests (35 submission/replay
and 8 Review/Result), 16/16 focused JS tests, Django check, migration drift,
JS syntax and whitespace checks passed. Formatting covers zero, grouping and
maximum whole-TOMAN values; a legacy-text regression proves exact replay/read
never invokes the generator or rewrites stored evidence. No full suite.

Real-browser validation passed normal TEST login, native Enter open/close and
expanded accessibility-tree state, visible core values, read-only result reload,
no horizontal overflow and zero fatal JS exceptions. One explicit Submit occurred
only in a fresh isolated copy, producing the formatted stored text; Visit remained
IN_PROGRESS. The owner's original 8793 Draft had already been submitted, so it
was left intact. No existing submission was reset or reformatted.

Current review package:

- Draft: `http://127.0.0.1:8795/customers/C0003/recommendations/presentation/?visit_id=19`;
  select «مرور و ثبت درخواست» to carry signed context.
- New formatted result:
  `http://127.0.0.1:8796/customers/C0003/visits/19/sales-request/result/`.
- Normal dedicated TEST login on each port: `/accounts/login/`, username
  `isolated-preview-sp001`. Protected launchers:
  `venv/stage3f2-f1-preview/start-preview.ps1 -CopyPassword` and
  `venv/stage3f2-f1-success-preview/start-preview.ps1 -CopyPassword`.
- Screenshots under `D:\py project\sales_ai_copilot\venv\stage3f2-f1-artifacts\`:
  `01-review-390.png`, `02-result-390.png`, `03-result-1440.png`.

Production canonical reconciliation, the original isolated source and existing
submitted header/line evidence comparison all passed unchanged. Original SQLite
and stash retain the hashes above. The disposable focused test DB was removed;
independent preview copies remain available on 8795/8796. Private evidence is
Git-ignored. No project migration/schema change, production write, seeding,
staging, commit or push occurred.
