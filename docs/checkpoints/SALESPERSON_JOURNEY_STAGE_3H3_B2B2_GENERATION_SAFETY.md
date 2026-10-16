# Stage 3H3-B2-B2 — Demo generation safety foundation

2026-10-15. Owner review pending. fast-track / V3.0.21
`1a96e92b938a5f64d586249245734f8e5d083b1e`, with B1/B2-A/B2-B1 preserved.
No reset, candidate creation/activation, Prepare Day execution or cleanup.

## Durable current identity and scope

Created only protected `D:\SalesAI-Demo\sales_ai_copilot\generation-state.json`.
Existing generation remains `6ae05c63-b9a3-4e85-a469-4643d3f76a27` on
sales_ai_demo_db / 127.0.0.1:5433 / sales-ai-demo-postgres. Registry pins DB OID,
container ID, roles, volume, endpoints and migration fingerprint to the verified
profile/owner-controlled DB marker. No profile/credential/key/fixture change.
Registry ACTIVE plus no maintenance is required; partial/missing/mismatched state
fails closed, never automatically repairs. Current initial generation has no
predecessor; any future activation must retain at least this healthy generation.

Dedicated runtime `configure_django` installs middleware/signal only for the
verified Demo. Base settings, production and other previews are unchanged. Only
the verified Demo Django app was stopped/started on the same generation to load
security code. No Docker restart or generation switch. Login and transport script
GETs return 200; no live login or business POST was performed during this task.

## Session, document and pending-command fencing

Standard Django login/DB sessions/CSRF/authorization remain authoritative. On
successful normal login, session records `sales_ai_demo_generation`. Middleware
checks protected current state before views; stale authenticated sessions return
403, missing/invalid/stale document or command proofs return 409, uncertain
maintenance/profile state returns 503. Old sessions are not flushed/repaired.

Demo HTML gains an invisible signed-document transport bootstrap, with no template,
CSS or layout redesign. POST forms carry a hidden proof, removed before the view;
CSRF remains intact. Non-command lifecycle fetches carry the fixed page proof.
Four optional shared-JS hooks carry Demo metadata only if the Demo helper exists:
basket, feedback, submission and completion. Production/preview helper is absent.

New command proof is saved in its outer pending envelope, outside payload/wire.
Reload/retry sends that same proof with the same command UUID and bytes. A fresh
session/cookie cannot authorize an older generation's signed proof. Unmarked old
pending data is not restamped; missing proof is rejected. Static browser adapter
does not auto-fill proof for UUID POSTs. No POST auto-retry, new feedback state,
new payload field, receipt operation or submission idempotency change.

These are signed generation/transport checks, not new business authorization or
malicious-user/XSS prevention: ordinary domain permissions, revisions, pricing,
inventory and intent hashes still apply. Within one generation, an earlier valid
document proof remains valid so exact pending-command replay remains possible.
Browser profile/cookie isolation is supplementary, never the generation authority.

Normal Demo bootstrap HTTP/test helpers read the server-issued document proof;
they do not fabricate it or skip CSRF. No bootstrap/fixture validation writes were
executed here. On restart, legacy pages should reload and log in explicitly.
Existing unsigned uncertain commands need read-only recovery, not proof upgrades.

## Maintenance journal and recovery design

Pure validators and reset dry-run describe:
PLANNED -> CANDIDATE_VALIDATED -> RECOVERY_RECORDED -> OLD_APP_QUIESCED ->
OLD_WRITES_FENCED -> PROFILE_SELECTED -> NEW_APP_VALIDATED -> COMPLETE.
Journal sequence, exact old/candidate UUIDs, prior-entry hash/checksum and required
evidence must agree. Recovery recording and completion require the old healthy
generation in the retained list. Tests use synthetic evidence flags only; a future
executor must independently verify actual signed/sealed validation reports,
identity, role fences and process observations. No executor/appender/switch CLI
is supplied and even a complete synthetic journal grants no mutation permission.

Promotion is multi-step and **not atomic**. Record verified old profiles/identities,
grants/recovery references and retention before switching. Quiesce only identified
Demo app processes, drain requests, fence old DB writes, select the exact approved
profile and independently validate new auth/generation/read paths. During any
interruption or ambiguous phase, runtime is blocked; no automatic resume, rollback,
promotion or cleanup. Candidate guards still need explicit implementation/approval
because the current launcher hardcodes sales_ai_demo_db.

An in-flight old-generation transaction cannot be made safe by a filesystem read
alone: actual promotion requires quiescence and old-role write fencing before new
activation. After candidate writes, preserve both generations and reconcile;
never silently merge/discard evidence. Preserve at least one previous healthy
generation until independently approved cleanup.

## Older Visit policy

Older IN_PROGRESS Visits now block conflicting future-day preparation. Current
2026-10-16 plan is BLOCKED by C0005 Visit 2, with proposed insert count zero.
Four other rows are only unblocked candidates, not an executable partial write
set. No automatic completion/redating. Same-day registered open Visits remain
reusable, closed Visits remain closed, and existing duplicate/identity safeguards
remain. B2-B1 wording is updated to this owner decision.

## Focused evidence and preservation

- Python: 14/14 memory-only generation/CSRF/login/journal tests, plus 16/16
  read-only planner tests passed. An initial multipart test spy incorrectly read
  raw body after POST parsing; corrected only the spy, then 14/14 passed.
- Login test calls real Django login/signals on an in-memory user/session;
  mutation tests use spy views, not business DB writes. These are not claimed as
  live authenticated PostgreSQL E2E mutation tests.
- JS: 87/87 affected tests passed, including all four real pending-flow harnesses
  retaining old generation proof on reload with byte-identical wire payloads,
  plus seven transport helper tests. Existing no-helper behavior remains covered.
- Django check and migration identity verified using read-only connections.
  Python/JS syntax and whitespace checks pass; no full regression suite.
- Protected evidence: `D:\SalesAI-Demo\sales_ai_copilot\reports\b2b2\`, including
  before/final preservation inventories and current dry-run plans.

All Demo business/auth/session data and sequences remain unchanged. Production,
original SQLite, credentials/fixture/profile files, existing preview databases,
stash and unrelated DEMO-02 planning are preserved. SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
No migrations, seeding, role changes, staging, commit or push.

Remaining approval: validate a real independent candidate, actual evidence/journal
storage and recovery protocol, exact candidate identity/profile activation guards,
quiescence/role fencing, retention/cleanup and post-write divergence handling.
No actual reset, promotion or future-day preparation is authorized by this work.
