"""Explicit one-time infrastructure provisioning. Never clones data or resets a DB."""
import json
from pathlib import Path
import secrets
import socket
import subprocess
import time
from uuid import uuid4

from common import *


APPEND_ONLY = {
    "recommendations_recommendationfeedbackevent", "sales_requests_salesrequestacknowledgement",
    "sales_requests_salesrequestmutationreceipt", "visits_visitcommercialsnapshot",
    "visits_visitcustomersnapshot", "visits_salesoutcome", "django_admin_log",
}
MUTABLE = {"sales_requests_salesrequest", "sales_requests_salesrequestline"}


def grant_runtime(conn):
    """Reviewed grants, shared by explicit provisioning and disposable validation."""
    from psycopg import sql
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(RUNTIME)))
    conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(RUNTIME)))
    for table in sorted(APPEND_ONLY | MUTABLE | {"django_session"}):
        privileges = "INSERT" if table in APPEND_ONLY else "INSERT,UPDATE" if table in MUTABLE else "INSERT,UPDATE,DELETE"
        conn.execute(sql.SQL("GRANT " + privileges + " ON TABLE {} TO {}").format(sql.Identifier(table), sql.Identifier(RUNTIME)))
        sequence = conn.execute("SELECT pg_get_serial_sequence(%s,'id') WHERE EXISTS "
            "(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name='id')",
            [table, table]).fetchone()
        if sequence and sequence[0]:
            conn.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(sql.Identifier(*sequence[0].split('.')), sql.Identifier(RUNTIME)))
    conn.execute(sql.SQL("GRANT UPDATE ON visits_visit TO {}").format(sql.Identifier(RUNTIME)))
    conn.execute(sql.SQL("GRANT UPDATE(last_login,password) ON auth_user TO {}").format(sql.Identifier(RUNTIME)))


def private_directory(path):
    path.mkdir(parents=True, exist_ok=False)
    user = subprocess.check_output(["whoami"], text=True).strip()
    subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", user + ":(OI)(CI)F",
                    "SYSTEM:(OI)(CI)F"], check=True, capture_output=True)


def provision():
    import psycopg
    from psycopg import sql
    require(sys.argv[1:] == ["--confirm-create-isolated-demo"], "Explicit provisioning confirmation required.")
    require(not DEFAULT_STATE.exists() and not COMPOSE.parent.exists(), "Target paths already exist; inspect, never overwrite.")
    require(not docker("ps", "-aq", "--filter", "name=^/" + CONTAINER + "$").strip(), "Demo container already exists.")
    require(VOLUME not in docker("volume", "ls", "--format", "{{.Name}}").splitlines(), "Demo volume already exists.")
    require(migration_fingerprint()[0] == 50, "Reviewed 50-migration baseline changed.")
    for port in (5433, APP_PORT):
        with socket.socket() as sock:
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", port))
    private_directory(DEFAULT_STATE)
    private_directory(COMPOSE.parent)
    for directory in ("credentials", "run", "reports"):
        (DEFAULT_STATE / directory).mkdir()
    identity = str(uuid4())
    bootstrap_password = secrets.token_urlsafe(48)
    (DEFAULT_STATE / "credentials/bootstrap-password.txt").write_text(bootstrap_password, encoding="utf-8")
    for role, filename in ((OWNER, "owner.json"), (RUNTIME, "runtime.json")):
        write_json(DEFAULT_STATE / "credentials" / filename, dict(host="127.0.0.1", port=5433,
                   database=DATABASE, user=role, password=secrets.token_urlsafe(48)))
    for filename in ("django-secret.key", "control-token.key"):
        (DEFAULT_STATE / "credentials" / filename).write_text(secrets.token_urlsafe(64), encoding="utf-8")
    secret_path = (DEFAULT_STATE / "credentials/bootstrap-password.txt").as_posix()
    compose = f'''name: sales-ai-demo
services:
  postgres:
    image: {IMAGE}
    container_name: {CONTAINER}
    restart: unless-stopped
    ports:
      - "127.0.0.1:5433:5432"
    environment:
      POSTGRES_USER: {BOOTSTRAP}
      POSTGRES_DB: {DATABASE}
      POSTGRES_PASSWORD_FILE: /run/secrets/demo_bootstrap_password
      TZ: Asia/Tehran
    secrets:
      - demo_bootstrap_password
    volumes:
      - demo_pgdata:/var/lib/postgresql/data
    labels:
      com.sales-ai.demo.identity: "{identity}"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {BOOTSTRAP} -d {DATABASE}"]
      interval: 3s
      timeout: 3s
      retries: 30
volumes:
  demo_pgdata:
    name: {VOLUME}
    labels:
      com.sales-ai.demo.identity: "{identity}"
secrets:
  demo_bootstrap_password:
    file: "{secret_path}"
'''
    COMPOSE.write_text(compose, encoding="utf-8")
    write_json(DEFAULT_STATE / "reports/provision-journal.json", {"identity": identity, "phase": "credentials-created"})
    docker("compose", "-f", str(COMPOSE), "up", "-d", "--pull", "never")
    for _ in range(60):
        container = json.loads(docker("inspect", CONTAINER))[0]
        if container["State"].get("Health", {}).get("Status") == "healthy":
            break
        time.sleep(1)
    require(container["State"].get("Health", {}).get("Status") == "healthy", "Demo PostgreSQL startup failed.")
    clean_database_environment()
    with psycopg.connect(host="127.0.0.1", port=5433, dbname=DATABASE, user=BOOTSTRAP,
                          password=bootstrap_password, autocommit=True, connect_timeout=5) as conn:
        require(conn.execute("SELECT current_database(),current_user,current_setting('server_version_num')::int").fetchone()
                == (DATABASE, BOOTSTRAP, 170011), "Bootstrap endpoint/version mismatch.")
        require(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0] == 0,
                "Target schema unexpectedly populated.")
        for role in (OWNER, RUNTIME):
            value = credentials(DEFAULT_STATE, role)
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}")
                         .format(sql.Identifier(role), sql.Literal(value["password"])))
        conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(DATABASE), sql.Identifier(OWNER)))
        conn.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(OWNER)))
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for database in (DATABASE, "postgres", "template1"):
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(DATABASE), sql.Identifier(RUNTIME)))
        marker = json.dumps({"kind": "sales-ai-isolated-demo", "identity": identity}, sort_keys=True)
        conn.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(DATABASE), sql.Literal(marker)))
        oid = conn.execute("SELECT oid FROM pg_database WHERE datname=current_database()").fetchone()[0]
    count, fingerprint = migration_fingerprint()
    profile = dict(version=1, ready=True, identity=identity, database=DATABASE, host="127.0.0.1", database_port=5433,
                   container=CONTAINER, volume=VOLUME, owner_role=OWNER, runtime_role=RUNTIME,
                   application_port=APP_PORT, url=f"http://localhost:{APP_PORT}", listen=f"127.0.0.1:{APP_PORT}",
                   state_root=str(DEFAULT_STATE), project_root=str(ROOT),
                   container_id=container["Id"], image_id=container["Image"], database_oid=oid,
                   server_version_num=170011, migration_count=count, migration_fingerprint=fingerprint)
    verify_container(profile)
    configure_django(profile, DEFAULT_STATE, OWNER)
    from django.core.management import call_command
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(connections["default"])
    require(len(loader.disk_migrations) == 50, "Unexpected migration graph.")
    profile["migration_keys"] = sorted([list(k) for k in loader.disk_migrations])
    call_command("migrate", interactive=False, verbosity=1)
    connections.close_all()
    with connect(profile, DEFAULT_STATE, OWNER, readonly=False) as conn:
        grant_runtime(conn)
    # Ready profile is published only after schema and grants are complete.
    write_json(DEFAULT_STATE / "profile.json", profile)
    from initialization import register_generation
    with connect(profile, DEFAULT_STATE, OWNER) as conn:
        register_generation(conn, profile, DEFAULT_STATE)
    write_json(DEFAULT_STATE / "reports/provision-journal.json", {"identity": identity, "phase": "complete", "migrations": 50})
    print("Dedicated Demo schema provisioned; no users or business fixtures created.")


if __name__ == "__main__":
    try:
        provision()
    except Exception as exc:
        # Never print driver exceptions/SQL containing credentials. No automatic cleanup/retry.
        print("Provisioning stopped: " + (str(exc) if isinstance(exc, DemoError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
