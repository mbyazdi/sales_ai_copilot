"""Focused B1 infrastructure checks. No fixture creation or sequence consumption."""
import io
import socket
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import common
import demo
from common import *
from provision import APPEND_ONLY, MUTABLE


def database_state(connection):
    from psycopg import sql
    tables = [r[0] for r in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    counts = {table: connection.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))).fetchone()[0]
              for table in tables}
    sequences = connection.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename").fetchall()
    return dict(counts=counts, sequences=sequences)


class InfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_profile()
        verify_container(cls.profile)

    def test_wrong_database_and_database_port_fail_before_connect(self):
        for key, value in (("database", "sales_ai_db"), ("database_port", 5432), ("host", "localhost")):
            profile = {**self.profile, key: value}
            with self.subTest(key=key), patch("psycopg.connect") as network:
                with self.assertRaises(DemoError):
                    connect(profile, DEFAULT_STATE)
                network.assert_not_called()

    def test_wrong_application_endpoint_rejected(self):
        for key, value in (("application_port", 8800), ("url", "http://localhost:8800"), ("listen", "0.0.0.0:8900")):
            with self.subTest(key=key), self.assertRaises(DemoError):
                validate_profile({**self.profile, key: value}, DEFAULT_STATE)

    def test_wrong_owner_marker_rejected_by_real_connection(self):
        with self.assertRaises(DemoError):
            connect({**self.profile, "identity": str(uuid4())}, DEFAULT_STATE)

    def test_wrong_database_oid_rejected_by_real_connection(self):
        with self.assertRaises(DemoError):
            connect({**self.profile, "database_oid": self.profile["database_oid"] + 1}, DEFAULT_STATE)

    def test_missing_credentials_fail_before_connect(self):
        with tempfile.TemporaryDirectory(dir=DEFAULT_STATE / "reports") as directory:
            profile = {**self.profile, "state_root": directory}
            with patch("psycopg.connect") as network:
                with self.assertRaises(DemoError):
                    connect(profile, Path(directory))
                network.assert_not_called()

    def test_occupied_port_preserves_foreign_listener(self):
        # Run validation while the Demo app is stopped; never stop an existing listener.
        with socket.socket() as listener:
            if os.name == "nt":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", APP_PORT))
            listener.listen()
            with self.assertRaises(DemoError):
                demo.port_free()
            self.assertEqual(listener.getsockname(), ("127.0.0.1", APP_PORT))

    def test_foreign_health_never_authorizes_shutdown(self):
        foreign = io.BytesIO(json.dumps(dict(identity="foreign", database=DATABASE, role=RUNTIME)).encode())
        with patch.object(demo, "urlopen", return_value=foreign):
            with self.assertRaises(DemoError):
                demo.health(self.profile)

    def test_runtime_flags_ownership_and_schema_privileges(self):
        with connect(self.profile, DEFAULT_STATE) as conn:
            self.assertEqual(conn.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                                         "FROM pg_roles WHERE rolname=current_user").fetchone(), (False,) * 5)
            self.assertEqual(conn.execute("SELECT has_schema_privilege(current_user,'public','USAGE'),"
                "has_schema_privilege(current_user,'public','CREATE'),has_database_privilege(current_user,current_database(),'TEMP')").fetchone(),
                (True, False, False))
            self.assertEqual(conn.execute("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)").fetchone()[0], 0)
            owners = conn.execute("SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                  "WHERE n.nspname='public' AND c.relkind IN ('r','S','i')").fetchall()
            self.assertEqual(owners, [(OWNER,)])
            self.assertEqual(conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()").fetchone(), (OWNER,))

    def test_empty_business_tables_and_framework_metadata_only(self):
        with connect(self.profile, DEFAULT_STATE) as conn:
            state = database_state(conn)
        counts = state["counts"]
        self.assertEqual(len(counts), 40)
        self.assertEqual({k: v for k, v in counts.items() if v}, {
            "django_migrations": 50, "django_content_type": 35, "auth_permission": 140})

    def test_runtime_allowed_zero_row_writes(self):
        from psycopg import sql
        with connect(self.profile, DEFAULT_STATE, readonly=False) as conn:
            before = database_state(conn)
            for table in sorted(APPEND_ONLY | MUTABLE | {"django_session"}):
                columns = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", [table])]
                fields = sql.SQL(",").join(map(sql.Identifier, columns))
                # Explicit columns and zero rows: no defaults, IDs or timestamps are generated.
                with conn.transaction(force_rollback=True):
                    result = conn.execute(sql.SQL("INSERT INTO public.{} ({}) SELECT {} FROM public.{} WHERE FALSE")
                                          .format(sql.Identifier(table), fields, fields, sql.Identifier(table)))
                    self.assertEqual(result.rowcount, 0)
                sequence = conn.execute("SELECT pg_get_serial_sequence(%s,'id')", [table]).fetchone() if "id" in columns else None
                if sequence and sequence[0]:
                    self.assertEqual(conn.execute("SELECT has_sequence_privilege(current_user,%s,'USAGE'),"
                        "has_sequence_privilege(current_user,%s,'UPDATE')", [sequence[0], sequence[0]]).fetchone(), (True, False))
            for statement in (
                "UPDATE auth_user SET last_login=last_login,password=password WHERE FALSE",
                "UPDATE visits_visit SET status=status WHERE FALSE",
                "UPDATE sales_requests_salesrequest SET revision=revision WHERE FALSE",
                "UPDATE sales_requests_salesrequestline SET quantity=quantity WHERE FALSE",
                "UPDATE django_session SET expire_date=expire_date WHERE FALSE",
                "DELETE FROM django_session WHERE FALSE",
            ):
                with conn.transaction(force_rollback=True):
                    self.assertEqual(conn.execute(statement).rowcount, 0)
            self.assertEqual(database_state(conn), before)

    def test_append_only_catalog_and_ddl_denied(self):
        import psycopg
        from psycopg import sql
        with connect(self.profile, DEFAULT_STATE, readonly=False) as conn:
            before = database_state(conn)
            statements = []
            for table in sorted(APPEND_ONLY):
                statements.extend([sql.SQL("UPDATE {} SET id=id WHERE FALSE").format(sql.Identifier(table)),
                                   sql.SQL("DELETE FROM {} WHERE FALSE").format(sql.Identifier(table))])
            statements.extend([
                "UPDATE auth_user SET username=username WHERE FALSE",
                "UPDATE products_productdemoprice SET base_price=base_price WHERE FALSE",
                "DELETE FROM products_product WHERE FALSE",
                "UPDATE inventory_inventory SET available_quantity=available_quantity WHERE FALSE",
                "CREATE TABLE public.__demo_denied (id integer)",
                "CREATE TEMP TABLE __demo_denied (id integer)",
                "CREATE SCHEMA __demo_denied",
                "SET ROLE sales_ai_demo_owner",
            ])
            for statement in statements:
                with self.subTest(statement=str(statement)), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction(force_rollback=True):
                        conn.execute(statement)
            self.assertEqual(database_state(conn), before)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InfrastructureTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    profile = load_profile()
    with connect(profile, DEFAULT_STATE) as connection:
        state = database_state(connection)
    write_json(DEFAULT_STATE / "reports/infrastructure-validation.json", dict(
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        identity=profile["identity"], migration_fingerprint=profile["migration_fingerprint"], state=state))
