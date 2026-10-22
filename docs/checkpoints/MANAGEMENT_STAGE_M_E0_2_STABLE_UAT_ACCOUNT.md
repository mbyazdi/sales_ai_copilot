# Stage M-E0.2 — Stable Management Preview UAT Account

Date: 2026-10-16. Baseline V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Scope: isolated management TEST preview only. No management UI or persistent deployment.

## Existing credential and retained identity

Verified the protected `venv/management-preview-live/accounts.json` manager entry
against its actual Django password hash before changing anything. The existing
`me01-manager` account was active staff, non-superuser and recoverable.

Retained its password, password hash, user PK **1**, history and permissions.
Renamed only its username to **manager**. Existing policy authors, comparisons,
command actors and commercial sources retain their original IDs and evidence.
The current password was NOT replaced with an invented owner password. The owner
can now choose their fixed UAT password using the secure local reset command.

Preview remains `http://localhost:8901/accounts/login/`, same database:
`test_me01_5d24c8a723614bcfaa3b6ea3fd0efe5a`. Same DB OID/marker, independent
owner/runtime identities, signing key, cookie names and synthetic fixtures.
Normal start/stop performs no account creation, reset or date preparation.

## Protected reusable provisioning

`D:\py project\sales_ai_copilot\venv\management-preview-uat\` stores:
- `manager.json`: signed, scoped nonreversible Django PBKDF2 hash and fixed
  username/active-staff/non-superuser requirements; no plaintext password.
- `account-signing.key`: independent local evidence key.

The directory is Git-ignored and ACL-protected for the current Windows user and
SYSTEM only. It is separate from every database's state. Database cleanup does
not remove it; retain this folder if replacing the Python virtual environment.

An explicitly requested fresh `provision` now requires valid UAT evidence and
restores the same manager hash inside the fixture transaction. It never generates
a different manager password on rebuild. Missing/tampered/incompatible evidence
fails before database/role creation. Other TEST users remain independent.
Existing state directories are never overwritten, rebuilt or reseeded silently.

The retained pre-existing plaintext password remains recoverable only in the
protected current `accounts.json` until the owner chooses a new password. Reset
removes that manager plaintext entry. Future rebuilt accounts contain no manager
plaintext, only a reference to the protected UAT provisioning mechanism.

## Owner instructions

Open `http://localhost:8901/accounts/login/` and use username **manager**.
To recover the currently retained password, inspect ONLY the manager entry in:

`D:\py project\sales_ai_copilot\venv\management-preview-live\accounts.json`

Open that file locally, for example with Notepad. Do not paste its contents into
chat, terminal output, screenshots, reports or Git. The locator command prints
only paths and username, never secrets:

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview_account.py where
```

Choose/change the fixed UAT password in an interactive local PowerShell terminal:

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview_account.py reset
```

Two hidden prompts require matching input and normal Django password validation.
No password CLI option, environment-variable input or piped-input mechanism.
Noninteractive execution refuses rather than falling back to echoed input.
The new password is stored only as a hash, never printed or retained reversibly.
Existing manager sessions become invalid under Django's standard password/session
hash behavior. Other accounts, pricing and strategy logic are unchanged.

Normal lifecycle (already running; no need to start twice):

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview.py status
.\venv\Scripts\python.exe -B scripts/management_preview.py stop
.\venv\Scripts\python.exe -B scripts/management_preview.py start
.\venv\Scripts\python.exe -B scripts/verify_management_preview_account.py http
```

After a chosen password is hash-only, the verifier prompts securely in a local
terminal; it cannot recover plaintext from the hash. Normal browser login uses
the owner's chosen password. Forgotten passwords require explicit reset.

Intentional rebuild requires separate explicit operator action. Preserve the
UAT store, stop the verified preview, and provision into a NEW protected state:

```powershell
.\venv\Scripts\python.exe -B scripts/management_preview.py provision --state venv/management-preview-next
.\venv\Scripts\python.exe -B scripts/management_preview.py start --state venv/management-preview-next
```

Use `--state venv/management-preview-next` for its later lifecycle/account commands.
This creates a new disposable DB/roles and synthetic fixtures; it does not clone,
delete or adopt the prior DB. The same UAT manager hash is restored. Remove an old
DB only through its separately selected, identity-verified cleanup command.

On a new machine without UAT evidence, `management_preview_account.py initialize`
prompts securely to create hash-only provisioning evidence without any DB access.
It refuses existing evidence; it does not alter an already provisioned DB.

## Real validation and restoration proof

- **13 focused unit tests passed**: six existing preview boundary tests and seven
  account tests for hash-only storage, HMAC tampering, missing evidence, unusable
  hashes, TTY requirement, hidden confirmation/validation and legacy recovery.
- Current preview real HTTP account validation: **14 checks passed before restart**:
  normal manager login; overview/versions/comparison access; invalid credentials;
  valid session and CSRF; missing/invalid CSRF rejection; manage permission reaches
  strict validation without business writes; GET logout rejected; POST logout and
  session invalidation. Repeated after controlled restart for persistence.
- First independent offline fresh DB applied all 51 migrations and restored the
  same hash: **9 checks passed**, including normal Django authentication and
  middleware/CSRF login, both capabilities and no copied strategy history.
- Second fresh DB: **14 checks passed**, adding actual explicit reset using
  securely mocked terminal input and a separate clone-local UAT evidence store.
  Verified original PK retention, new-password success, old-password rejection,
  old-session invalidation, no new plaintext retention, and unchanged main UAT
  provisioning evidence. No real owner password was changed by this test.
- Both offline DBs/independent roles removed using exact OID/marker verification
  and zero-session checks. No current preview DB removal or template cloning.
- A reset-clone verification was initially attempted before provisioning finished;
  it refused the missing profile before DB work. After completion the focused
  proof passed; no state was overwritten or silently adopted.

Protected evidence remains in `venv/management-uat-clone-e002-20261016/` and
`venv/management-uat-clone-e002-reset-proof/`; HTTP account proof is in the live
preview state. These artifacts, credentials and hashes are excluded from Git.

## Source-readiness transition and failure recovery

The reviewed provisioning extension changes the source fingerprint. After a
verified graceful shutdown, the operator explicitly advanced ONLY the isolated
preview's signed source pin, retaining all DB/profile/signing/cookie identities.
The exact previous expected source was checked, 8901 was verified unbound, and
protected before/after evidence was saved in `me02-reviewed-source-transition.json`.
Startup source checks were not disabled; no auto-rebinding command was introduced.
Persistent Demo source/profile/launcher were not changed or restarted.

Missing/tampered account evidence, wrong database/endpoint/OID/marker, conflicting
manager username or permission mismatch refuses the operation. Default adoption
checks the existing secret/hash, retains PK and never overwrites a conflicting
account. Password reset is explicit and limited to the verified isolated DB.

Filesystem evidence and PostgreSQL are not one atomic transaction. Hash evidence
is durably published before committing the account change; metadata uses atomic
file replacement. An interrupted operation may leave a detectable hash/account
mismatch or `.pending` file. Stop and inspect the exact DB/account and evidence;
never auto-adopt another hash, delete pending evidence or rebuild. An operator may
explicitly reset to a known password after resolving ownership/evidence ambiguity.
Current stable stores must not be reset concurrently with provisioning.

The original M-E0.1 HTTP proof remains evidence for its original source hash;
use the account-specific verifier for this task's restart proof rather than
relabeling or regenerating historical evidence.

## Exact source boundary and preservation

Modified: `scripts/management_preview.py` (hash restoration only on explicit
provision; source pin includes account helper), `scripts/verify_management_preview.py`
(normal login helper supports secure entry when only a hash remains).

Added: `scripts/management_preview_account.py`,
`scripts/verify_management_preview_account.py`,
`scripts/tests_management_preview_account.py`, this checkpoint.

No strategy, permission, application settings, middleware, Gate V2, API/model or
UI changes. No production PostgreSQL connection, persistent Demo writes/DDL/
grants/restart, reset, Prepare Day or generation switch. Original SQLite hash:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
No staging, commit or push. Visual-reference handoff and persistent deployment
remain separately blocked/unapproved.

Final checks: **14/14 HTTP account checks passed again after restart**; retained
DB/user ID/hash and original comparison digest independently verified. Both clone
DBs/roles confirmed absent. Persistent Demo user-table/sequence digest remained
`c42009b3f3fb59bb4c91a1d4a27f817db34c9251727512a355ae2a1283f4e86d`.
Port 8900 still uses PID 37632; management preview uses PID 46040. Of 57
pre-existing dirty/untracked files, only the two explicitly scoped preview scripts
changed; all other 55 match their initial SHA256 byte-for-byte. Django check,
migration drift, five Python syntax checks, six-file whitespace and Git diff
checks passed. No JavaScript changes or full suite. Git index remains empty.
