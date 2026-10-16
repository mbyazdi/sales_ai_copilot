"""Explicit B3 integration runner; disposable DB only, never persistent fixtures.

Run with the repository Python: python scripts/demo/verify_generation_postgres.py
The independent Demo cluster's operator creates/drops one UUID-named test DB.
All HTTP probes use normal middleware, CSRF and the Demo runtime's real grants.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import unittest
from uuid import uuid4

from common import *
from preservation import preservation, record_before, verify_before


def main():
    global OWNER, RUNTIME
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", help="Exact focused test method names; default runs the B3 class.")
    parser.add_argument("--lock-capabilities", action="store_true", help="Install B6 capabilities only in the disposable DB and include their tests.")
    parser.add_argument("--maintenance-gate", action="store_true", help="Include cross-process B1 maintenance admission tests in this disposable DB.")
    parser.add_argument("--gate-recovery",action="store_true",help="Include B2 disposable-only recovery tests (also enables B1).")
    parser.add_argument("--prepare-day",action="store_true",help="Run isolated H4-B3 synthetic Prepare Day tests only.")
    parser.add_argument("--control-bundle",action="store_true",help="Include H4-B6 read-only readiness and disposable writer retirement tests.")
    args = parser.parse_args()
    if args.gate_recovery:args.maintenance_gate=True
    if args.prepare_day:args.lock_capabilities=args.maintenance_gate=True
    if args.control_bundle:args.lock_capabilities=args.maintenance_gate=True
    import psycopg
    from psycopg import sql
    profile = load_profile()
    verify_container(profile)
    clean_database_environment()  # Before any libpq connect; no inherited service/hostaddr routing.
    require(migration_fingerprint() == (50, profile["migration_fingerprint"]), "Migration baseline changed.")
    state = DEFAULT_STATE / "reports" / ("b2b3-" + uuid4().hex)
    state.mkdir()
    (state/'credentials').mkdir()
    (state/'credentials/control-token.key').write_text(secrets.token_urlsafe(64),encoding='ascii')
    before = preservation(profile)
    operation = record_before(state / 'before.json', profile, before, purpose='generation-postgres-tests')
    name = "test_stage3h3b3_" + uuid4().hex
    identity = str(uuid4())
    marker = "sales-ai-demo-b3-disposable:" + identity
    operator = dict(host="127.0.0.1", port=5433, dbname="postgres", user=BOOTSTRAP,
        password=(DEFAULT_STATE / "credentials/bootstrap-password.txt").read_text(encoding="utf-8").strip(),
        connect_timeout=5, options="-c statement_timeout=30000")
    require(name not in {DATABASE, "sales_ai_db", "postgres"}, "Invalid disposable identity.")
    oid = None
    result = None
    capability_owner = None
    with psycopg.connect(**operator, autocommit=True) as control:
        require(control.execute("SELECT current_database(),current_user,inet_server_port()::int").fetchone()
                == ("postgres", BOOTSTRAP, 5432), "Demo operator endpoint mismatch.")
        require(control.execute("SELECT 1 FROM pg_database WHERE datname=%s", [name]).fetchone() is None,
                "Disposable name already exists.")
        import common as shared
        persistent_roles = (OWNER,RUNTIME)
        suffix = name.removeprefix('test_stage3h3b3_')
        OWNER, RUNTIME = 'sa_b3_owner_'+suffix, 'sa_b3_runtime_'+suffix
        test_passwords = {OWNER:secrets.token_urlsafe(48),RUNTIME:secrets.token_urlsafe(48)}
        created_roles = []
        try:
            for role in (OWNER,RUNTIME):
                control.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}')
                                .format(sql.Identifier(role),sql.Literal(test_passwords[role])))
                created_roles.append(role)
            control.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'")
                            .format(sql.Identifier(name), sql.Identifier(OWNER)))
        except BaseException:
            for role in reversed(created_roles):
                control.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
            OWNER,RUNTIME=persistent_roles
            raise
        shared.OWNER,shared.RUNTIME=OWNER,RUNTIME
        # Evidence sealing already imported the SQL fingerprint validator. Bind
        # its runtime target to this independent test role too, not the live Demo.
        import lock_capabilities as test_locks
        test_locks.RUNTIME=RUNTIME
        oid = control.execute("SELECT oid FROM pg_database WHERE datname=%s", [name]).fetchone()[0]
        control.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(name), sql.Literal(marker)))
        control.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
        control.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(name), sql.Identifier(RUNTIME)))
        try:
            owner = dict(password=test_passwords[OWNER])
            runtime = dict(password=test_passwords[RUNTIME])
            os.environ.update(DJANGO_SETTINGS_MODULE="sales_ai_copilot.settings", DB_ENGINE="postgresql",
                POSTGRES_DB=name, POSTGRES_USER=OWNER, POSTGRES_PASSWORD=owner["password"],
                POSTGRES_HOST="127.0.0.1", POSTGRES_PORT="5433")
            from django.conf import settings
            settings.SECRET_KEY = secrets.token_urlsafe(64)
            settings.DEBUG = False
            settings.ALLOWED_HOSTS = ["localhost"]
            settings.SESSION_ENGINE = "django.contrib.sessions.backends.db"
            settings.SESSION_COOKIE_NAME = "sales_ai_b3_test_session"
            settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
            from django.db.backends.postgresql.base import DatabaseWrapper
            original = DatabaseWrapper.get_new_connection

            def isolated_connection(wrapper, params):
                require(wrapper.alias == "default" and params.get("dbname") == name
                    and params.get("host") == "127.0.0.1" and str(params.get("port")) == "5433"
                    and params.get("user") in {OWNER, RUNTIME}
                    and not params.get("service") and not params.get("hostaddr"), "Test connection refused before connect.")
                raw = original(wrapper, params)
                try:
                    actual = raw.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database'),"
                        "inet_server_port() FROM pg_database d WHERE datname=current_database()").fetchone()
                    require(actual == (name, params["user"], oid, marker, 5432), "Live disposable identity mismatch.")
                    raw.rollback()
                    return raw
                except BaseException:
                    raw.close()
                    raise

            DatabaseWrapper.get_new_connection = isolated_connection
            import django
            django.setup()
            from django.core.management import call_command
            from django.db import connection, connections
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('ALTER SCHEMA public OWNER TO {}').format(sql.Identifier(OWNER)))
            call_command("migrate", interactive=False, verbosity=0)
            from django.db.migrations.loader import MigrationLoader
            loader = MigrationLoader(connection)
            require(set(loader.applied_migrations) == set(loader.disk_migrations) and len(loader.disk_migrations) == 50,
                    "Disposable migrations mismatch.")
            from tests_generation_postgres import LiveGenerationTests, seed, endpoint_inventory
            if args.prepare_day:
                from tests_prepare_day import PrepareDayTests, seed as seed_preparation
                seed_preparation(PrepareDayTests,state,identity,name)
            else:seed(LiveGenerationTests)
            if args.lock_capabilities and not args.prepare_day:
                # Existing fixtures otherwise have no grade; C exercises the grade lock without a discount.
                from apps.customers.models import CustomerGrade, Customer
                grade = CustomerGrade.objects.create(code="C", name="Capability test grade")
                Customer.objects.filter(pk=LiveGenerationTests.customer.pk).update(grade=grade)
                LiveGenerationTests.customer.refresh_from_db()
                LiveGenerationTests.grade = grade
            # Reproduce B1 grants only inside the disposable database.
            from provision import APPEND_ONLY, MUTABLE
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM PUBLIC"))
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(RUNTIME)))
                cursor.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(RUNTIME)))
                for table in sorted(APPEND_ONLY | MUTABLE | {"django_session"}):
                    privileges = "INSERT" if table in APPEND_ONLY else "INSERT,UPDATE" if table in MUTABLE else "INSERT,UPDATE,DELETE"
                    cursor.execute(sql.SQL("GRANT " + privileges + " ON {} TO {}").format(sql.Identifier(table), sql.Identifier(RUNTIME)))
                    cursor.execute("SELECT pg_get_serial_sequence(%s,'id') WHERE EXISTS "
                        "(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name='id')", [table, table])
                    seq = cursor.fetchone()
                    if seq and seq[0]:
                        cursor.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(sql.Identifier(*seq[0].split('.')), sql.Identifier(RUNTIME)))
                cursor.execute(sql.SQL("GRANT UPDATE ON visits_visit TO {}").format(sql.Identifier(RUNTIME)))
                cursor.execute(sql.SQL("GRANT UPDATE(last_login,password) ON auth_user TO {}").format(sql.Identifier(RUNTIME)))
            if args.lock_capabilities:
                capability_owner = "sa_lock_b6_" + uuid4().hex
                require(control.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [capability_owner]).fetchone() is None,
                        "Capability owner already exists.")
                control.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS")
                                .format(sql.Identifier(capability_owner)))
                from lock_capabilities import install
                with psycopg.connect(**{**operator, "dbname": name}) as installer:
                    receipt = install(installer, database=name, oid=oid, marker=marker, owner=capability_owner)
                    # Hostile names exist only in this disposable DB. Runtime cannot create them.
                    installer.execute("CREATE SCHEMA b6_hostile")
                    installer.execute(sql.SQL("GRANT USAGE ON SCHEMA b6_hostile TO {}").format(sql.Identifier(RUNTIME)))
                    for table in ("customers_customer", "products_product", "inventory_inventory", "recommendations_customerrecommendation"):
                        installer.execute(sql.SQL("CREATE TABLE b6_hostile.{} (id bigint)").format(sql.Identifier(table)))
                write_json(state / "capabilities.json", receipt)
                LiveGenerationTests.capability_owner = capability_owner

                def isolated_probe(role=RUNTIME):
                    require(role in {RUNTIME, OWNER, BOOTSTRAP}, "Unsupported probe role.")
                    password = operator["password"] if role == BOOTSTRAP else test_passwords[role]
                    raw = psycopg.connect(host="127.0.0.1", port=5433, dbname=name, user=role, password=password,
                        connect_timeout=5, options="-c statement_timeout=15000 -c lock_timeout=5000")
                    try:
                        require(raw.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database') "
                            "FROM pg_database d WHERE datname=current_database()").fetchone() == (name, role, oid, marker),
                            "Independent probe identity mismatch.")
                        raw.rollback()
                        return raw
                    except BaseException:
                        raw.close()
                        raise

                LiveGenerationTests.probe = staticmethod(isolated_probe)
            connections.close_all()
            connection.settings_dict.update(USER=RUNTIME, PASSWORD=runtime["password"])
            test_profile = {**profile, "identity": identity, "database": name, "database_oid": oid,
                            "owner_role":OWNER,"runtime_role":RUNTIME,"gate_test_marker":marker}
            if args.prepare_day:
                test_profile['capability_owner']=capability_owner
                registry=dict(identity=identity,database_oid=oid,database=name,snapshot=receipt)
                path=state/'lock-capabilities.json';write_json(path,registry)
                path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='ascii')
            from scripts.demo.maintenance_gate import install_disposable
            with psycopg.connect(host="127.0.0.1", port=5433, dbname=name, user=OWNER,
                                 password=owner["password"], connect_timeout=5) as raw:
                install_disposable(raw, test_profile)
                from scripts.demo.prepare_day import install_disposable as install_preparation
                install_preparation(raw,test_profile)
            write_json(state / "profile.json", test_profile)
            from scripts.demo import generation
            write_json(state / "generation-state.json", generation.initial_registry(test_profile))
            generation.install(test_profile, state)
            LiveGenerationTests.test_profile = test_profile
            LiveGenerationTests.artifacts = state
            LiveGenerationTests.routes = endpoint_inventory()
            write_json(state / "endpoints.json", LiveGenerationTests.routes)
            call_command("check")
            call_command("makemigrations", check=True, dry_run=True, verbosity=1)
            classes = [LiveGenerationTests]
            if args.maintenance_gate:
                from tests_maintenance_gate import MaintenanceTests
                MaintenanceTests.profile = test_profile
                MaintenanceTests.connection_values = dict(host="127.0.0.1",port=5433,dbname=name,
                    connect_timeout=5,options="-c statement_timeout=15000 -c lock_timeout=4000")
                MaintenanceTests.passwords = test_passwords
                MaintenanceTests.state_dir = state
                classes += [MaintenanceTests]
                if args.prepare_day:classes=[PrepareDayTests]
                if args.gate_recovery:
                    from tests_gate_recovery import RecoveryTests
                    classes += [RecoveryTests]
            if args.lock_capabilities and not args.prepare_day:
                from tests_lock_capabilities import CapabilitySecurityTests, CapabilityConcurrencyTests
                classes += [CapabilitySecurityTests, CapabilityConcurrencyTests]
                from tests_lock_deployment import DeploymentTests
                classes += [DeploymentTests]
            if args.control_bundle:
                from tests_control_bundle import ControlBundleTests
                classes += [ControlBundleTests]
            methods = {n: cls for cls in classes for n, value in cls.__dict__.items() if n.startswith("test_") and callable(value)}
            if args.only:
                require(all(n in methods for n in args.only),
                        "Unknown focused test selection.")
                suite = unittest.TestSuite(methods[n](n) for n in args.only)
            else:
                suite = unittest.TestSuite(methods[n](n) for n in sorted(methods))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            write_json(state / "results.json", dict(database=name, oid=oid, marker=marker, migrations=50,
                tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                routes=len(LiveGenerationTests.routes), role=RUNTIME, capabilities_enabled=args.lock_capabilities,
                selected=args.only or "all", failed=[t.id() for t, _ in result.failures],
                errored=[t.id() for t, _ in result.errors]))
        finally:
            from django.db import connections
            connections.close_all()
            require(control.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [name])
                    .fetchone() == (oid, marker), "Cleanup refused: disposable identity changed.")
            require(control.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", [name]).fetchone()[0] == 0,
                    "Cleanup refused: disposable connections remain.")
            control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            require(control.execute("SELECT 1 FROM pg_database WHERE datname=%s", [name]).fetchone() is None,
                    "Disposable cleanup failed.")
            if capability_owner:
                control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(capability_owner)))
                require(control.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [capability_owner]).fetchone() is None,
                        "Capability owner cleanup failed.")
            for role in (RUNTIME,OWNER):
                control.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
            OWNER,RUNTIME=persistent_roles
            shared.OWNER,shared.RUNTIME=persistent_roles
            test_locks.RUNTIME=RUNTIME
            write_json(state / "cleanup.json", dict(database=name, oid=oid, removed=True,
                capability_owner=capability_owner, capability_owner_removed=bool(capability_owner)))
            after = preservation(profile)
            write_json(state / "after.json", after)
            require(verify_before(state/'before.json',profile,purpose='generation-postgres-tests',operation=operation)==before,
                    'Original test operation evidence changed.')
            require(before == after, "Persistent preservation differs; inspect protected before/after reports.")
    print("Disposable database removed; persistent Demo/production/SQLite/stash/index unchanged.")
    print("Evidence: " + str(state))
    return 0 if result and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
