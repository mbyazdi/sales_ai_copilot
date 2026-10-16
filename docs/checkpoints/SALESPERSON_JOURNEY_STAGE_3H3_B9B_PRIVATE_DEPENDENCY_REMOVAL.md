# Stage 3H3-B9-B — Repository-owned preservation tooling

Date: 2026-10-15. Baseline: V3.0.21,
`1a96e92b938a5f64d586249245734f8e5d083b1e`, branch `fast-track`.
Scope: B8 blocker #2 only; preserve approved B9-A initialization and B7 security.

## Change and trust boundaries

`scripts/demo/preservation.py` replaces the ignored DB-01C2A provisioning import
with reviewed SELECT-only production metadata/connection code. It reuses
`apps/core/reconciliation.py` canonical UTC checksums. Comparison against the
original reader reproduced every production table/metadata value and the existing
Demo inventory exactly; all formerly protected file paths remain covered.
No credentials, password hashes, private reports or data snapshots enter source.

There is no mandatory historical `reports/b2b2/preserved-files.json`. Protection
uses current configured profile/generation/credentials, initialization manifests
and existing preview credential files, with explicit before/after operation
evidence. Missing files declared in that evidence cannot be silently omitted.
Unrelated untracked DEMO-02 planning is protected when present, not required on a
clean installation.

Capability deployment no longer imports a validation runner or needs a production
installation. Its EMPTY and PREPARED preservation paths both verify the live
endpoint/container/OID/marker, schema ownership, migration graph and active
generation. EMPTY requires empty non-framework tables and no orphan fixture data;
PREPARED requires the approved source/date-bound fixture manifest and current
record identities/values/relationships. Full operator-visible public row and
sequence evidence remains mandatory. Existing ACL, SQL-body, owner and runtime
privilege checks remain intact. Ordinary startup never deploys or bootstraps.

The cross-environment validation runners still require their configured read-only
production runtime credential and preserve production, Demo, original SQLite,
HEAD, stash and index. Production checks include all canonical table digests,
schema/constraint/owner metadata and operation-pinned database/endpoint identity.
Runtime-hidden production sequence values remain explicitly NULL; no additional
production privileges are requested or implied.

## Durable operation evidence and recovery

Before-state files use exclusive creation and an HMAC with the existing protected
Demo control key. They bind operation UUID/purpose, installation, generation,
migration/SQL/tooling fingerprints and required file hashes. The integration and
deployment commands revalidate their original record before accepting preservation.
The public checksum of a modified record cannot authorize it. Correctly signed
evidence for another identity/endpoint/source/operation is also refused.

`preservation.py capture` explicitly begins a NEW read-only operation;
`preservation.py verify` requires its original path, purpose and operation UUID.
Neither command reconstructs history. Missing/untrusted original evidence means
historical preservation is unproven: stop, inspect the original journal and live
identities, and obtain independent recovery approval. Never recapture over an
uncertain operation to report success. See `scripts/demo/README.md` for commands.

## Validation

- Clean-source initialization: **24/24 steps**, two independent disposable
  PostgreSQL DBs/owner/runtime/capability roles, on 2026-10-15 and 2026-10-16.
  Workers run from checksum-verified copies of reviewed source and tracked static
  assets, with no Git metadata, venv, source SQLite, private reports or copied
  existing credentials. All 50 migrations apply only in disposable DBs.
  Fresh install, repeat NO_OP, conflicting-date rejection, startup refusal,
  populated-install SELECT-only preservation and recovery negatives pass.
- Evidence tests: **4/4**, also executed directly from the source-only copy.
  Shared checks cover 15 valid/refused cases, including missing/invalid/tampered
  evidence, public-checksum forgery, wrong operation/purpose, signed foreign
  DB OID/endpoint/generation/SQL source, and changed/missing required files.
- B3/B6/B7 real-session/security/concurrency: **35/35**, independent disposable
  owner/runtime roles. Lock strength/order/lifetime, Feedback/Submit/completion,
  replay/rollback, stale generation and forbidden reference/append-only/DDL
  privileges remain covered. Disposable DBs and roles removed.
- Existing generation tests **14/14**; read-only plan tests **16/16**;
  generation-client JS **7/7**. Python/JS syntax passed.
- Django check clean; migration drift check reports no changes. Persistent Demo
  startup preflight verifies the 50-migration graph read-only. B7 recheck returns
  `READ_ONLY_VERIFIED_NO_OP` for the unchanged approved `REFERENCE_LOCKS_V1` SHA
  `7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1`.
- Explicit existing-install read-only capture/verify succeeds. Whitespace checks
  include the new/untracked source files, not just tracked diffs.

Two harness issues were corrected during validation: the first clean copy omitted
required tracked images and correctly failed bootstrap; the new independent test
runtime role initially was not propagated into an already imported capability
module. Final reruns above pass, without weakening application guards. Failed-run
disposable databases/roles were also removed.

Protected current-task evidence:
`D:\SalesAI-Demo\sales_ai_copilot\reports\b9b-d65390a7060d4d3c940777e5ca691ff8\`.
Clean installs: `reports/b9a-af8c7c09e1e64bc1a28d36012c889c9e` and
`reports/b9a-b940dd70e3374797af085ef4ab0243bf`.
Final 35-test run: `reports/b2b3-e92839834f004925b8ce32ca2b58f732`.
These are evidence locations, never executable or required historical dependencies.

## Preservation and remaining scope

No application business code, SQL capability definitions, schema migrations,
production/persistent Demo rows, roles/grants, fixtures, sessions, credentials,
generation or running preview were changed. Only disposable validation targets
received writes. Original SQLite remains at
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`;
stash remains `2dac7bdc26f07f611f471564476ceaa52ec367cc`. Nothing staged,
committed or pushed. Unrelated planning and previous uncommitted work preserved.

B8 blocker #2 is resolved; B9-A's blocker #1 correction is retained. Blocker #3
(production capability rollout/deployment compatibility) is not addressed or
approved here. No reset, Prepare Day, candidate activation or generation switch.
