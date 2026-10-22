"""Connection boundary for explicit management test/verification tools only.

Not imported by application/business code. No protected-database probes.
Offline routing checks precede the connector; live OID/marker attestation then
precedes all test SQL. Catalog provisioning has a separate explicit authority.
"""
import os
from uuid import UUID


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def clear_inherited_routing():
    for key in list(os.environ):
        if key.startswith(("PG", "POSTGRES_")) or key in {"DATABASE_URL", "DB_ENGINE", "DJANGO_SETTINGS_MODULE"}:
            os.environ.pop(key, None)


def check_environment():
    require(not any(key.startswith(("PG", "POSTGRES_")) or key in {"DATABASE_URL", "DB_ENGINE"}
                    for key in os.environ), "Inherited database routing prohibited in management verification.")


def check_params(params, *, database, roles):
    check_environment()
    require(params.get("dbname") == database and params.get("user") in roles
            and params.get("host") == "127.0.0.1" and str(params.get("port")) == "5433"
            and not any(key in params for key in ("conninfo", "service", "servicefile", "hostaddr", "passfile", "replication")),
            "Unapproved management database/role/endpoint; refused before connection.")


def check_memory(params):
    require(params.get("database") in {":memory:", "file:memorydb_default?mode=memory&cache=shared"},
            "Only in-memory SQLite is authorized; refused before file connection.")


class ManagementTestBoundary:
    def __init__(self, *, allow_memory=False, allow_provisioning=False):
        self.allow_memory = allow_memory
        self.allow_provisioning = allow_provisioning
        self.targets = {}
        self.attempts = []  # Approved identity metadata only; never credentials.

    def enroll(self, *, suffix, oid, journey=False):
        require(type(suffix) is str and UUID(suffix).hex == suffix and type(oid) is int and oid > 0,
                "Exact disposable UUID/OID required.")
        database = ("test_stage3h3b3_" if journey else "test_mc1_") + suffix
        marker = ("sales-ai-demo-b3-disposable:" if journey else "strategy-foundation-disposable:") + suffix
        roles = {prefix + suffix for prefix in ("mc1_owner_", "mc3_runtime_", "mc4_runtime_")}
        if journey:
            roles.add("sales_ai_demo_bootstrap")  # Explicit isolated capability installer only.
        self.targets[database] = (roles, oid, marker)
        return database

    def validate(self, params):
        require(params.get("dbname") in self.targets, "Database is not enrolled for this management test run.")
        roles, oid, marker = self.targets[params["dbname"]]
        check_params(params, database=params["dbname"], roles=roles)
        return oid, marker

    def validate_django(self, database):
        engine = database.get("ENGINE")
        if engine == "django.db.backends.sqlite3":
            require(self.allow_memory, "SQLite is not authorized in PostgreSQL verification.")
            check_memory({"database": database.get("NAME")})
        else:
            require(engine == "django.db.backends.postgresql", "Unapproved management test backend.")
            params = {"dbname": database.get("NAME"), "user": database.get("USER"),
                      "host": database.get("HOST"), "port": database.get("PORT"), **database.get("OPTIONS", {})}
            self.validate(params)

    def connect(self, connector, conninfo="", **params):
        require(not conninfo, "DSN/service strings prohibited before management test connection.")
        oid, marker = self.validate(params)
        self.attempts.append((params["dbname"], params["user"]))
        raw = connector(**params)
        try:
            actual = raw.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database'),"
                                 "inet_server_port() FROM pg_database d WHERE datname=current_database()").fetchone()
            require(actual == (params["dbname"], params["user"], oid, marker, 5432), "Disposable live identity mismatch.")
            if not raw.autocommit:
                raw.rollback()
            return raw
        except BaseException:
            raw.close()
            raise

    def control(self, connector, **params):
        """Only catalog CREATE/DROP provisioning, never Django/test SQL access.

        Requires --provision-disposable. postgres is NOT a general allowed target.
        The caller owns exact-UUID creation/cleanup; no persistent business reads.
        """
        require(self.allow_provisioning, "PostgreSQL provisioning requires explicit --provision-disposable.")
        check_params(params, database="postgres", roles={"sales_ai_demo_bootstrap"})
        raw = connector(**params)
        try:
            require(raw.execute("SELECT current_database(),current_user,inet_server_port()").fetchone()
                    == ("postgres", "sales_ai_demo_bootstrap", 5432), "Provisioning catalog endpoint mismatch.")
            self.attempts.append(("postgres", "sales_ai_demo_bootstrap"))
            return raw
        except BaseException:
            raw.close()
            raise

    def install(self):
        if getattr(self, "connector", None) is not None:
            return self.connector
        import psycopg
        connector = psycopg.connect
        self.connector = connector
        psycopg.connect = lambda conninfo="", **params: self.connect(connector, conninfo, **params)
        from django.db.backends.sqlite3.base import DatabaseWrapper
        sqlite_connect = DatabaseWrapper.get_new_connection
        def memory_only(wrapper, params):
            require(self.allow_memory, "SQLite disabled for this management test run.")
            check_memory(params)
            return sqlite_connect(wrapper, params)
        DatabaseWrapper.get_new_connection = memory_only
        return connector  # Used ONLY by the explicit catalog provisioning channel.


def connect_preview(profile, credentials, role, **options):
    """Direct verification connection: validate exact preview BEFORE networking."""
    from scripts.management_preview import valid_profile, identity
    valid_profile(profile)
    require(role in {profile["owner"], profile["runtime"]}, "Unapproved preview verification role.")
    require(not set(options) & {"host", "port", "dbname", "database", "user", "password", "conninfo", "service", "servicefile", "hostaddr", "passfile", "replication"},
            "Preview routing overrides prohibited before connection.")
    params = dict(options, host=profile["host"], port=profile["port"], dbname=profile["database"],
                  user=role, password=credentials["password"], connect_timeout=5)
    check_params(params, database=profile["database"], roles={role})
    import psycopg
    raw = psycopg.connect(**params)
    try:
        identity(raw, profile, role)
        return raw
    except BaseException:
        raw.close()
        raise
