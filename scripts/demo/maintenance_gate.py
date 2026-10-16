"""Demo-only transaction admission. No Prepare Day, journal, reset or recovery CLI.

The control row is owner-written, runtime-read-only. PENDING is committed BEFORE
waiting for exclusive admission, so a lost maintenance connection stays fenced.
All app requests (including GET session writes) share the SAME business database
transaction/connection. No separate lock connection or process-local authority.
"""
from contextlib import contextmanager
import hashlib
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.db import DatabaseError, connections, transaction
from django.http import JsonResponse

VERSION = "DEMO_MAINTENANCE_V2"
KEY = (89005433, 3401)
OWNER_KEY = (89005433, 3402)
TABLE = "sales_ai_demo_control.admission"
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class GateRefused(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise GateRefused(message)


def identity(cursor, profile, role):
    require(cursor.connection.info.host == "127.0.0.1" and cursor.connection.info.port == 5433,
            "Gate connection endpoint mismatch.")
    cursor.execute("SELECT current_database(),current_user,d.oid,"
                   "shobj_description(d.oid,'pg_database'),inet_server_port(),"
                   "current_setting('transaction_isolation') "
                   "FROM pg_database d WHERE datname=current_database()")
    row = cursor.fetchone()
    import json
    require(row[:3] == (profile["database"], role, profile["database_oid"])
            and row[4:] == (5432, "read committed"), "Gate database/role/isolation mismatch.")
    marker = profile.get("gate_test_marker")
    require(row[3] == marker if marker else json.loads(row[3] or "null") ==
            {"kind": "sales-ai-isolated-demo", "identity": profile["identity"]},
            "Gate database marker mismatch.")


def inspect(cursor, profile, role):
    identity(cursor, profile, role)
    cursor.execute("SELECT pg_get_userbyid(c.relowner),pg_get_userbyid(n.nspowner),"
                   "has_schema_privilege(%s,n.oid,'CREATE'),"
                   "has_table_privilege(%s,c.oid,'SELECT'),"
                   "(has_table_privilege(%s,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR "
                   "has_any_column_privilege(%s,c.oid,'INSERT,UPDATE,REFERENCES')) "
                   "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "WHERE n.nspname='sales_ai_demo_control' AND c.relname='admission' AND c.relkind='r'",
                   [profile["runtime_role"]] * 4)
    require(cursor.fetchone() == (profile["owner_role"], profile["owner_role"], False, True, False),
            "Missing/unsafe maintenance gate ownership or runtime grants.")
    cursor.execute("SELECT version,generation,database_oid,phase,operation,backend_pid,evidence_sha FROM " + TABLE)
    rows = cursor.fetchall()
    require(len(rows) == 1 and rows[0][:3] ==
            (VERSION, UUID(profile["identity"]), profile["database_oid"]), "Gate identity/version mismatch.")
    import re
    require((rows[0][3] == 'ACTIVE' and rows[0][6] is None) or
            (rows[0][3] == 'PENDING' and isinstance(rows[0][6],str) and
             re.fullmatch('[0-9a-f]{64}',rows[0][6])), 'Missing maintenance operation evidence.')
    return rows[0][3:6]


def install(profile):
    """Configuration only, called exclusively by the dedicated Demo profile."""
    require(profile["host"] == "127.0.0.1" and profile["database_port"] == 5433,
            "Gate endpoint mismatch.")
    require(settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
            and set(settings.DATABASES) == {"default"}, "Gate requires one database and DB-backed sessions.")
    settings.DEMO_MAINTENANCE_PROFILE = dict(profile)
    middleware = "scripts.demo.maintenance_gate.DemoMaintenanceMiddleware"
    settings.MIDDLEWARE = [middleware] + [m for m in settings.MIDDLEWARE if m != middleware]


def verify_ready(raw, profile):
    """SELECT-only startup check; never install or repair objects."""
    from scripts.demo.control_bundle import inspect as inspect_bundle
    with raw.cursor() as cursor:
        return inspect_bundle(cursor, profile, profile["runtime_role"], serving=True)


class DemoMaintenanceMiddleware:
    """Outermost: includes SessionMiddleware response save and view transactions.

    Streaming and on_commit callbacks are unsupported and fail closed: their
    deferred work could run after the protecting transaction. Current app uses
    neither. Django-owned request connection must not be replaced mid-request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from scripts.demo.generation import active_generation, GenerationRefused, DemoGenerationMiddleware
        profile = settings.DEMO_MAINTENANCE_PROFILE
        connection = connections["default"]
        if connection.vendor != "postgresql":
            return self.denied()
        try:
            with transaction.atomic():
                raw = connection.connection
                with connection.cursor() as cursor:
                    # Nonblocking readers: no queue of waiting new admissions.
                    cursor.execute("SELECT pg_try_advisory_xact_lock_shared(%s,%s)", KEY)
                    require(cursor.fetchone()[0], "Exclusive maintenance in progress.")
                    require(inspect(cursor, profile, profile["runtime_role"]) == ("ACTIVE", None, None),
                            "Maintenance pending.")
                require(active_generation() == profile["identity"], "Generation mismatch after admission.")
                callbacks = list(connection.run_on_commit)
                response = self.get_response(request)
                require(connection.connection is raw and not connection.closed_in_transaction,
                        "Business connection changed during admission.")
                require(not response.streaming and connection.run_on_commit == callbacks,
                        "Deferred writes are not admitted.")
                if response.status_code >= 400:
                    transaction.set_rollback(True)
                return response
        except GenerationRefused:
            return DemoGenerationMiddleware.denied("DEMO_MAINTENANCE_UNCERTAIN", 503)
        except (GateRefused, DatabaseError, ValueError):
            return self.denied()

    @staticmethod
    def denied():
        response = JsonResponse({"code": "DEMO_MAINTENANCE_BLOCKED",
            "detail": "محیط نمایشی برای نگهداری در دسترس نیست؛ فرمان را خودکار تکرار نکنید."}, status=503)
        response["Cache-Control"] = "no-store"
        return response


def install_disposable(raw, profile):
    """Explicit test provisioning ONLY. Never a startup/persistent installer."""
    from psycopg import sql
    require(profile["database"].startswith("test_stage3h3b3_")
            and profile.get("gate_test_marker") == "sales-ai-demo-b3-disposable:" + profile["identity"]
            and raw.info.host == "127.0.0.1" and raw.info.port == 5433,
            "Gate provisioning requires an exact disposable identity.")
    with raw.cursor() as cursor:
        identity(cursor, profile, profile["owner_role"])
        cursor.execute("CREATE SCHEMA sales_ai_demo_control")
        cursor.execute("REVOKE ALL ON SCHEMA sales_ai_demo_control FROM PUBLIC")
        cursor.execute("CREATE TABLE " + TABLE + " ("
            "singleton boolean PRIMARY KEY CHECK(singleton),version text NOT NULL,"
            "generation uuid NOT NULL,database_oid oid NOT NULL,phase text NOT NULL,"
            "operation uuid,backend_pid integer,evidence_sha text,"
            "CHECK ((phase='ACTIVE' AND operation IS NULL AND backend_pid IS NULL AND evidence_sha IS NULL) OR "
            "(phase='PENDING' AND operation IS NOT NULL AND backend_pid IS NOT NULL AND evidence_sha IS NOT NULL AND evidence_sha ~ '^[0-9a-f]{64}$')))" )
        cursor.execute("CREATE TABLE sales_ai_demo_control.operations (operation uuid PRIMARY KEY,"
                       "envelope jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp())")
        cursor.execute("CREATE TABLE sales_ai_demo_control.results (operation uuid PRIMARY KEY REFERENCES "
                       "sales_ai_demo_control.operations(operation),recovery_uuid uuid UNIQUE,"
                       "envelope jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp())")
        cursor.execute("INSERT INTO " + TABLE + " VALUES(TRUE,%s,%s,%s,'ACTIVE',NULL,NULL,NULL)",
                       [VERSION, profile["identity"], profile["database_oid"]])
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA sales_ai_demo_control TO {}")
                       .format(sql.Identifier(profile["runtime_role"])))
        cursor.execute(sql.SQL("GRANT SELECT ON " + TABLE + " TO {}")
                       .format(sql.Identifier(profile["runtime_role"])))


class ExclusiveGate:
    """Low-level maintenance lease, not an executor or crash-recovery command.

    Uses one verified owner connection; never reconnects/reclaims pending state.
    Loss/timeout/exception leaves PENDING durable. Only clean finish reopens it.
    """
    def __init__(self, raw, profile, operation):
        self.raw, self.profile, self.operation = raw, profile, UUID(str(operation))
        self.pid = None

    def announce(self, *, prepare_plan=None):
        require(self.raw.info.transaction_status == 0, "Owner connection must be idle.")
        from scripts.demo.generation import active_generation
        require(active_generation() == self.profile["identity"], "Generation mismatch before announcement.")
        with self.raw.transaction(), self.raw.cursor() as cursor:
            identity(cursor,self.profile,self.profile['owner_role'])
            cursor.execute('SELECT pg_try_advisory_lock(%s,%s)',OWNER_KEY)
            require(cursor.fetchone()[0], 'Maintenance/recovery owner is still live.')
        try:
            with self.raw.transaction(), self.raw.cursor() as cursor:
                require(inspect(cursor, self.profile, self.profile["owner_role"]) == ("ACTIVE", None, None),
                        "Pending operation requires inspection; no automatic takeover.")
                cursor.execute('SELECT pg_backend_pid()');self.pid=cursor.fetchone()[0]
                from scripts.demo.gate_recovery import record_operation
                evidence_sha=record_operation(self.raw,self.profile,self.operation,self.pid,
                    purpose='PREPARE_DAY_V1' if prepare_plan is not None else 'GATE_ONLY_NO_BUSINESS_WRITES')
                if prepare_plan is not None:
                    from scripts.demo.prepare_day import record_intent
                    record_intent(self.raw,self.profile,self.operation,prepare_plan)
                cursor.execute("UPDATE " + TABLE + " SET phase='PENDING',operation=%s,backend_pid=pg_backend_pid(),evidence_sha=%s "
                               "WHERE singleton AND phase='ACTIVE' RETURNING backend_pid", [self.operation,evidence_sha])
                require(cursor.fetchone() == (self.pid,), "Another operation owns admission.")
        except BaseException:
            # A failed/uncertain announcement is never retried. Disconnecting the
            # owner releases its lease; any committed PENDING remains durable.
            self.raw.close()
            raise
        # Pending has committed; any subsequently admitted reader sees it.

    @contextmanager
    def _drained(self):
        """Retained V2 ownership only; callers must prove their exact outcome.

        Private shared mechanism for gate-only release and Prepare Day's signed
        journal. It NEVER clears PENDING or releases the owner lifetime lease.
        """
        require(self.pid is not None and self.raw.info.transaction_status == 0,
                "No live announcement/idle owner connection.")
        with self.raw.transaction(), self.raw.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s,%s)", KEY)
            require(inspect(cursor, self.profile, self.profile["owner_role"]) ==
                    ("PENDING", self.operation, self.pid), "Maintenance ownership changed.")
            cursor.execute("SELECT pg_backend_pid()")
            require(cursor.fetchone()[0] == self.pid, "Maintenance backend changed.")
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid() "
                           "AND classid=%s AND objid=%s AND objsubid=2 AND granted)",OWNER_KEY)
            require(cursor.fetchone()[0], 'Maintenance lifetime lease is missing.')
            from scripts.demo.generation import active_generation
            require(active_generation() == self.profile["identity"], "Generation changed while draining.")
            from scripts.demo.gate_recovery import verify_operation
            cursor.execute('SELECT evidence_sha FROM '+TABLE+' WHERE singleton')
            expected_sha=cursor.fetchone()[0]
            from scripts.demo.prepare_day import is_preparation
            verify_operation(self.raw,self.profile,self.operation,expected_sha,
                purpose='PREPARE_DAY_V1' if is_preparation(self.raw,self.operation) else 'GATE_ONLY_NO_BUSINESS_WRITES')
            yield cursor

    @contextmanager
    def exclusive(self):
        with self._drained() as cursor:
            from scripts.demo.prepare_day import is_preparation
            require(not is_preparation(self.raw,self.operation), 'Prepare Day requires its own signed outcome protocol.')
            from scripts.demo.gate_recovery import business_digest,record_result
            cursor.execute('SELECT evidence_sha FROM '+TABLE+' WHERE singleton')
            expected_sha=cursor.fetchone()[0]
            before=business_digest(self.raw)
            yield cursor
            require(business_digest(self.raw)==before, 'Gate-only operation changed protected data; rollback and inspect.')
            record_result(self.raw,self.profile,self.operation,kind='RELEASED',business_sha=before,evidence_sha=expected_sha)
            # Clean exit only. Exceptions/termination leave the committed fence.
            cursor.execute("UPDATE " + TABLE + " SET phase='ACTIVE',operation=NULL,backend_pid=NULL,evidence_sha=NULL "
                           "WHERE singleton AND operation=%s AND backend_pid=%s", [self.operation, self.pid])
            require(cursor.rowcount == 1, "Maintenance ownership lost.")
        self.pid = None
        with self.raw.transaction(),self.raw.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s,%s)',OWNER_KEY)
            require(cursor.fetchone()[0], 'Maintenance lifetime lease was lost.')
