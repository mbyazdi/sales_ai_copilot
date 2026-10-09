# DEMO-06C-F1 — deterministic reconciliation checksums

## Cause and evidence

The authorized DEMO-06C transaction rolled back before commit. The old audit
hashed `row_to_json(t)::text`, whose `timestamptz` encoding depends on the
connection TimeZone. The read-only inspector used Asia/Tehran; Django's
connection used UTC. Identical stored instants therefore produced different
`auth_user` checksums. No user row needed to change to reproduce the failure.

Reproduction used `sales_ai_runtime`, database-enforced read-only connections,
and a repeatable-read snapshot. All four users remained present:

| Encoding | Asia/Tehran auth_user SHA256 | UTC auth_user SHA256 |
| --- | --- | --- |
| Previous raw JSON | d8baf4ef9f0bd0a1b5ef562ae7f7b95dc32b8b23fd0a6f1048eca5f0a5972f85 | 2d6e3d4d4c98f75541f21a3ae8ffec5247b155b5584ee6655c03e08a023205ad |
| Canonical V1 | 7484bc29f6e20dbceee33b92a1623d2f0ecaac30e2b064cc5fbedfae0c97f552 | 7484bc29f6e20dbceee33b92a1623d2f0ecaac30e2b064cc5fbedfae0c97f552 |

## Correction

`apps/core/reconciliation.py` introduces `PG_JSONB_UTC_MICROSECONDS_V1`.
Every typed timestamp-with-time-zone column is encoded in UTC as
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Nulls, infinities and BC dates remain distinct.
All public tables and all columns remain included, including `auth_user` and
password values internally. Password values are never printed or reported.
Ordinary text, JSON strings and timestamps without timezone are not reinterpreted.
PostgreSQL JSONB handles deterministic key ordering and exact numeric values;
Python floating-point conversion is not used. Complete canonical rows are
sorted and hashed with newline separators.

The protected, Git-ignored `venv/demo06c-artifacts/run_approved_load.py` now
uses this same implementation for initial, precommit, postcommit and quote-read
reconciliation. Schema, constraint, ownership and sequence checks remain.
The old raw baseline is still checked in its original Asia/Tehran timezone;
a fresh canonical baseline is then captured with an explicit checksum-format
version. Old and new digest formats must never be compared directly.
The failed-run artifacts are retained. A separate owner-authorized retry and
a fresh protected `canonical-retry` artifact directory are required; F1 did
not execute the harness or authorize another price load.

## Focused validation

Six SELECT-only PostgreSQL regressions passed, with zero failures, errors or
skips. Controlled fixtures use `jsonb_populate_record(NULL::public.auth_user, ...)`
and inline SELECT values, not database inserts or copied production user data:

- Old timezone discrepancy reproduced; canonical digests equal.
- UTC six-digit microsecond precision and equivalent offsets verified.
- All 40 production table digests equal across UTC and Asia/Tehran.
- Changes to fixture username, password placeholder, email, active flag and
  either timestamp remain detectable, including a one-microsecond change.
- Timestamp-looking ordinary text remains exact.
- Null/infinite timestamps, high-precision numeric values and JSON retained.

Tests are in `apps/core/tests_reconciliation.py`; their explicit
`RECONCILIATION_TEST_DSN` must select a database-enforced read-only connection.
Without that opt-in connection the integration class skips. No secrets are
stored in repository files. The protected result is
`venv/demo06c-artifacts/approved-load/f1-checksum-validation.json`.

Final read-only reconciliation matched every table against the failed-run
before-state and matched canonical data/metadata before versus after F1.
`sales_ai_db` retains 49 migrations and **zero ProductDemoPrice rows**.
No production data writes, migrations, sequence resets or SQLite access occurred.

## Safe retry boundary

The checksum blocker is resolved; another DEMO-06C load needs explicit owner
authorization. Before that load, verify database identity, 49 migrations,
zero existing prices, the 14 SKU/FK mappings and dataset SHA256
`1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648`.
Recheck the prior approved baseline and capture a fresh canonical baseline.
Prepare a new owner-protected, Git-ignored artifact directory, preserve the
failed-run evidence, and enable the local harness's explicit retry authorization
gate only after approval.

Keep the original scope: one atomic transaction containing exactly the 14
approved price INSERTs; all other table checks must match before commit.
After commit, reconcile again and verify Quote API reads without mutations.
Stop on any discrepancy; never exclude auth_user, automatically retry a load,
or reset identity sequences to compensate for rolled-back INSERT allocations.
No price load was retried in F1.
