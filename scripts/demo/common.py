"""Shared Demo identity/configuration checks. Never read production credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = Path(r"D:\SalesAI-Demo\sales_ai_copilot")
COMPOSE = Path(r"D:\docker\sales-ai-demo\compose.yaml")
CONTAINER = "sales-ai-demo-postgres"
VOLUME = "sales_ai_demo_pgdata"
DATABASE = "sales_ai_demo_db"
OWNER = "sales_ai_demo_owner"
RUNTIME = "sales_ai_demo_runtime"
BOOTSTRAP = "sales_ai_demo_bootstrap"
APP_PORT = 8900  # Owner-approved replacement for Windows-reserved 8800.
IMAGE = "postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "venv/Lib/site-packages"))


class DemoError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise DemoError(message)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DemoError("Required protected configuration is missing or invalid.") from None


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def clean_database_environment():
    # Child process only; libpq service/hostaddr settings must not redirect traffic.
    for key in list(os.environ):
        if key.startswith(("PG", "POSTGRES_")) or key in {"DB_ENGINE", "DATABASE_URL", "DJANGO_SETTINGS_MODULE"}:
            os.environ.pop(key, None)


def validate_profile(profile, state):
    require(profile.get("version") == 1 and profile.get("ready") is True, "Demo provisioning is not complete.")
    require(profile.get("database") == DATABASE and profile.get("host") == "127.0.0.1"
            and profile.get("database_port") == 5433, "Refusing a non-Demo database endpoint.")
    require(profile.get("container") == CONTAINER and profile.get("volume") == VOLUME,
            "Unexpected Demo container or volume.")
    require(profile.get("runtime_role") == RUNTIME and profile.get("owner_role") == OWNER,
            "Unexpected Demo role.")
    require(profile.get("application_port") == APP_PORT
            and profile.get("url") == f"http://localhost:{APP_PORT}"
            and profile.get("listen") == f"127.0.0.1:{APP_PORT}",
            "Unexpected Demo application endpoint.")
    require(Path(profile.get("state_root", "")).resolve() == Path(state).resolve(), "Demo state directory mismatch.")
    require(Path(profile.get("project_root", "")).resolve() == ROOT.resolve(), "Demo repository path mismatch.")
    try:
        UUID(profile["identity"])
    except (KeyError, ValueError, TypeError):
        raise DemoError("Invalid Demo identity marker.") from None
    return profile


def load_profile(state=DEFAULT_STATE):
    return validate_profile(read_json(Path(state) / "profile.json"), state)


def credentials(state, role):
    require(role in {OWNER, RUNTIME}, "Unsupported Demo credential role.")
    value = read_json(Path(state) / "credentials" / ("owner.json" if role == OWNER else "runtime.json"))
    require(value.get("host") == "127.0.0.1" and value.get("port") == 5433
            and value.get("database") == DATABASE and value.get("user") == role,
            "Credential identity mismatch; no connection attempted.")
    require(isinstance(value.get("password"), str) and len(value["password"]) >= 32,
            "Demo credential is unavailable.")
    return value


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    require(result.returncode == 0, "Docker operation failed; inspect the dedicated Demo service.")
    return result.stdout


def verify_container(profile, running=True):
    try:
        value = json.loads(docker("inspect", CONTAINER))[0]
    except (ValueError, IndexError):
        raise DemoError("Demo container identity could not be read.") from None
    require(value["Id"] == profile["container_id"] and value["Image"] == profile["image_id"],
            "Demo container/image identity mismatch.")
    require(value["Config"].get("Labels", {}).get("com.sales-ai.demo.identity") == profile["identity"],
            "Demo container marker mismatch.")
    require(value["HostConfig"]["PortBindings"] == {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5433"}]},
            "Demo port binding mismatch.")
    data = [m for m in value["Mounts"] if m["Destination"] == "/var/lib/postgresql/data"]
    require(len(data) == 1 and data[0].get("Name") == VOLUME and data[0]["Type"] == "volume",
            "Demo data volume mismatch.")
    volume = json.loads(docker("volume", "inspect", VOLUME))[0]
    require(volume.get("Labels", {}).get("com.sales-ai.demo.identity") == profile["identity"],
            "Demo volume marker mismatch.")
    if running:
        require(value["State"]["Running"] and value["State"].get("Health", {}).get("Status") == "healthy",
                "Dedicated Demo PostgreSQL is not healthy; no fallback was selected.")
    return value


def verify_connection(connection, profile, role):
    row = connection.execute(
        "SELECT current_database(),current_user,current_setting('server_version_num')::int,"
        "current_setting('server_encoding'),oid,shobj_description(oid,'pg_database') "
        "FROM pg_database WHERE datname=current_database()"
    ).fetchone()
    require(row[:4] == (DATABASE, role, profile["server_version_num"], "UTF8")
            and row[4] == profile["database_oid"], "Connected database identity mismatch.")
    try:
        marker = json.loads(row[5])
    except (ValueError, TypeError):
        raise DemoError("Database is not marked as the isolated Demo.") from None
    require(marker == {"kind": "sales-ai-isolated-demo", "identity": profile["identity"]},
            "Owner-controlled Demo database marker mismatch.")


def connect(profile, state, role=RUNTIME, readonly=True):
    validate_profile(profile, state)
    value = credentials(state, role)
    clean_database_environment()
    import psycopg
    connection = psycopg.connect(host="127.0.0.1", port=5433, dbname=DATABASE, user=role,
        password=value["password"], connect_timeout=5, application_name="sales-ai-isolated-demo",
        options="-c default_transaction_read_only=" + ("on" if readonly else "off") +
                " -c statement_timeout=30000 -c lock_timeout=5000")
    try:
        verify_connection(connection, profile, role)
    except BaseException:
        connection.close()
        raise
    return connection


def migration_fingerprint():
    import django
    files = [(p.relative_to(ROOT).as_posix(), p) for p in (ROOT / "apps").glob("*/migrations/[0-9]*.py")]
    for app in ("admin", "auth", "contenttypes", "sessions"):
        for path in (Path(django.__file__).parent / "contrib" / app / "migrations").glob("[0-9]*.py"):
            files.append(("django/" + app + "/" + path.name, path))
    digest = hashlib.sha256()
    for name, path in sorted(files):
        digest.update(name.encode()); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
    return len(files), digest.hexdigest()


def configure_django(profile, state, role=RUNTIME):
    validate_profile(profile, state)
    value = credentials(state, role)
    clean_database_environment()
    os.environ.update(DB_ENGINE="postgresql", POSTGRES_DB=DATABASE, POSTGRES_USER=role,
        POSTGRES_PASSWORD=value["password"], POSTGRES_HOST="127.0.0.1", POSTGRES_PORT="5433",
        DJANGO_SETTINGS_MODULE="sales_ai_copilot.settings")
    from django.conf import settings
    try:
        key = (Path(state) / "credentials/django-secret.key").read_text(encoding="utf-8").strip()
    except OSError:
        raise DemoError("Protected Demo signing key is unavailable.") from None
    require(len(key) >= 48, "Invalid Demo signing key.")
    settings.SECRET_KEY = key
    settings.DEBUG = False
    settings.SECRET_KEY_FALLBACKS = []
    settings.ALLOWED_HOSTS = ["localhost"]
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.db"
    settings.SESSION_COOKIE_NAME = "sales_ai_demo_session"
    settings.SESSION_COOKIE_HTTPONLY = True
    settings.SESSION_COOKIE_SAMESITE = "Strict"
    settings.CSRF_COOKIE_NAME = "csrftoken"
    settings.CSRF_TRUSTED_ORIGINS = [profile["url"]]
    settings.LOGIN_REDIRECT_URL = "/api/visits/"
    if role == RUNTIME:
        from scripts.demo.generation import install
        install(profile, state)
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0
    settings.DATABASES["default"]["OPTIONS"]["options"] = "-c statement_timeout=30000"
    from django.db.backends.postgresql.base import DatabaseWrapper as PG
    from django.db.backends.sqlite3.base import DatabaseWrapper as SQLite
    original = PG.get_new_connection

    def guarded(self, params):
        require(self.alias == "default" and params.get("dbname") == DATABASE and params.get("user") == role
                and params.get("host") == "127.0.0.1" and str(params.get("port")) == "5433"
                and not ({"service", "hostaddr"} & params.keys()), "Non-Demo Django connection prohibited.")
        result = original(self, params)
        try:
            with result.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_user,oid,shobj_description(oid,'pg_database') "
                               "FROM pg_database WHERE datname=current_database()")
                row = cursor.fetchone()
            require(row[:3] == (DATABASE, role, profile["database_oid"])
                    and json.loads(row[3]) == {"kind": "sales-ai-isolated-demo", "identity": profile["identity"]},
                    "Django connection marker mismatch.")
            if role == RUNTIME:
                from lock_capabilities import validate_runtime
                validate_runtime(result, profile, state)
            result.rollback()
        except BaseException:
            result.close()
            raise
        return result

    PG.get_new_connection = guarded
    def no_sqlite(*args, **kwargs):
        raise DemoError("SQLite is unavailable to the Demo launcher.")
    SQLite.get_new_connection = no_sqlite
    import django
    django.setup()


def check_schema(profile):
    require(migration_fingerprint() == (profile["migration_count"], profile["migration_fingerprint"]),
            "Migration source fingerprint changed; explicit maintenance is required.")
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(connection)
    loader.check_consistent_history(connection)
    require(set(loader.applied_migrations) == set(loader.disk_migrations)
            and sorted([list(k) for k in loader.disk_migrations]) == profile["migration_keys"]
            and ("sales_requests", "0003_complete_visit_receipt") in loader.applied_migrations,
            "Migration drift; startup never applies migrations.")
    from django.core.management import call_command
    call_command("check", databases=["default"])
    connection.close()
