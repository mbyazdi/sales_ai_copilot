# DB-01A — PostgreSQL configuration and connectivity

Date: 2026-10-08. Scope: opt-in configuration and read-only verification only.
No migration, table creation, data transfer, demo seed or active-database switch.
Stage 3A1/3B1/3C1 work remains unchanged; DB-01B/01C are not started.

## Configuration

SQLite remains exactly `BASE_DIR / "db.sqlite3"` when DB_ENGINE is unset/empty or
sqlite. Merely defining PostgreSQL credentials does not change the backend.
Unknown selectors or incomplete PostgreSQL configuration fail explicitly.

| Process environment variable | Contract |
| --- | --- |
| DB_ENGINE | sqlite by default; postgresql explicitly opts in. |
| POSTGRES_DB | Required database name when PostgreSQL is selected. |
| POSTGRES_USER | Required authenticated database user. |
| POSTGRES_PASSWORD | Required secret; preserved exactly, never stored in project code. |
| POSTGRES_HOST | Default 127.0.0.1; override per home/office environment. |
| POSTGRES_PORT | Default 5432; valid integer 1–65535. |
| POSTGRES_SSLMODE | Default prefer for loopback demo; configure verify-full for remote TLS. |
| POSTGRES_CONNECT_TIMEOUT | Default 5 seconds; positive integer. |
| PGSSLROOTCERT | Optional libpq environment setting for the remote trusted CA file. |

Django does not automatically load `.env`, `.env.example` or Docker Compose's
external `.env`. Inject variables into the process using secure local tooling or
the prompt below. Do not copy the Docker password into Git, print connection
dictionaries/DSNs or place passwords in command arguments. Local `.env` files stay
ignored. The example file contains no password and selects SQLite.

Driver: `psycopg[binary]==3.3.6`, compatible with the installed Django 6.1 backend
(minimum Psycopg 3.1.12). Binary wheels avoid a local compiler/libpq installation.
References: [Django PostgreSQL support](https://docs.djangoproject.com/en/6.0/ref/databases/#postgresql-notes),
[Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html#binary-installation).
The existing UTF-16 requirements file is now UTF-8 with its original dependencies
preserved and the driver added. No pool or unrelated settings change is introduced.

## Setup commands

From the repository, with its virtual environment active:

```powershell
python -m pip install -r requirements.txt
python manage.py check  # Default SQLite; no migration.
```

Use a dedicated shell for PostgreSQL checks; the existing development shell stays
on SQLite. The known local Docker server is sales-ai-postgres, with Compose files
outside Git at `D:\docker\sales-ai-postgres`. Do not change its files or container.

```powershell
$env:DB_ENGINE = 'postgresql'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5432'
$env:POSTGRES_DB = 'sales_ai_db'
$env:POSTGRES_USER = 'sales_ai_user'
$pgSecurePassword = Read-Host 'PostgreSQL password' -AsSecureString
$pgPasswordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pgSecurePassword)
try {
    $env:POSTGRES_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pgPasswordPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pgPasswordPointer)
}
$env:PGOPTIONS = '-c default_transaction_read_only=on'
python manage.py check --database default
@'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_ai_copilot.settings")
import django
django.setup()
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user, current_setting('server_version'), current_setting('transaction_read_only')")
        print(cursor.fetchone())  # Non-secret connection identity and read-only flag.
finally:
    connection.close()
'@ | python -
# Close this dedicated shell after verification; do not run migrate/runserver here.
```

These checks require no application tables; an empty PostgreSQL database is valid.
The PGOPTIONS startup guard makes verification sessions read-only; Django may set
session parameters such as timezone, which do not change stored database contents.
The guard is scoped to the verification process, not a new application default.

## Test isolation and delivery safety

No TEST database name/mirror override is added. Django retains isolated SQLite
test databases and the PostgreSQL `test_<database>` naming default. PostgreSQL
tests that create schema/databases require separate future authorization; DB-01A
configuration tests are SimpleTestCase tests with no SQL/database setup.

Accepted local SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Preserve both; never stage db.sqlite3. No stage/commit/push is part of DB-01A.

## Executed validation

- Default SQLite Django check: no issues. Its JSON-support probe was permitted
  through a verification-only `mode=ro&immutable=1` connection; the configured path
  remained unchanged. An initial deny-all connection guard blocked that probe
  before any SQLite connection, then was replaced with the read-only guard.
- PostgreSQL Django check with `databases=["default"]`: no issues.
- Read-only Django/Psycopg connection: sales_ai_db / sales_ai_user at
  127.0.0.1:5432; PostgreSQL 17.11 (Debian 17.11-1.pgdg13+2), Psycopg 3.3.6.
  `transaction_read_only=on`; SELECT 1 succeeded. Public table count was 0 before
  and after verification. Secret read privately from the external Docker `.env`
  and injected into this verification process only; no password was output/copied.
- Focused configuration tests: 15 passed; no test database created or migrated.
- No full suite, migrations, DDL, data writes/transfer, seed or Docker change.
- Diff whitespace passed. Final hashes confirmed the eight pre-existing Stage 3
  files and SQLite database unchanged; original stash unchanged and index empty.
- Dependency comparison confirmed all original versions preserved. Private secret
  verification found no Docker password in any of the six DB-01A files.
