"""Focused M-C1 runner. Only UUID-marked disposable databases may be written.

Run: venv/Scripts/python.exe -B -m apps.management.verify_strategy_foundation
Add --sqlite for in-memory SQLite, or --checks for DB-free checks/drift.
PostgreSQL provisioning requires --provision-disposable. Only the maintenance
catalog and exact enrolled disposable databases are contacted, never persistent
Demo/production. No preservation probes against protected databases.
"""
import argparse
import os
from pathlib import Path
import secrets
from uuid import uuid4


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def configure(database, *, boundary=None):
    from scripts.management_test_isolation import ManagementTestBoundary, clear_inherited_routing
    boundary = boundary or ManagementTestBoundary(allow_memory=True)
    clear_inherited_routing()
    boundary.validate_django(database)  # Before settings, driver, cursor or connection.
    from django.apps import apps
    from django.conf import settings
    require(not settings.configured and not apps.ready,
            "Management test runner requires a fresh process; inherited Django connections/settings are not adopted.")
    boundary.install()
    # Ignore inherited libpq routing, Django profile and database selectors.
    for key in list(os.environ):
        if key.startswith(("PG", "POSTGRES_")) or key in {"DJANGO_SETTINGS_MODULE", "DB_ENGINE", "DATABASE_URL"}:
            os.environ.pop(key, None)
    os.environ["DJANGO_SETTINGS_MODULE"] = "sales_ai_copilot.settings"
    settings.DATABASES = {"default": database}
    settings.SECRET_KEY = secrets.token_urlsafe(48)
    import django
    django.setup()


def checks():
    from django.core.management import call_command
    call_command("check")
    call_command("makemigrations", check=True, dry_run=True, interactive=False)


def main(*, test_labels=None, runtime_tests=False, publication_tests=False, api_tests=False, journey_tests=False):
    test_labels = test_labels or ["apps.management.tests_strategy"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", action="store_true")
    parser.add_argument("--checks", action="store_true")
    parser.add_argument("--provision-disposable", action="store_true", help="Explicitly authorize disposable PostgreSQL CREATE/DROP via maintenance catalog only.")
    args = parser.parse_args()
    if args.sqlite or args.checks:
        configure({"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"})
        checks()
        if not args.checks:
            from django.test.runner import DiscoverRunner
            failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(test_labels)
            raise SystemExit(bool(failures))
        return

    import psycopg
    from psycopg import sql
    from scripts.management_test_isolation import ManagementTestBoundary, clear_inherited_routing
    require(args.provision_disposable, "PostgreSQL tests require explicit --provision-disposable; no connection opened.")
    clear_inherited_routing()
    boundary = ManagementTestBoundary(allow_provisioning=True)
    connector = boundary.install()  # All ordinary driver connections deny unenrolled DBs.
    # Verify the existing dedicated cluster without starting/stopping anything.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/demo"))
    from common import DEFAULT_STATE, load_profile, verify_container
    verify_container(load_profile())
    for key in list(os.environ):
        if key.startswith(("PG", "POSTGRES_")):
            os.environ.pop(key, None)
    password = (DEFAULT_STATE / "credentials/bootstrap-password.txt").read_text(encoding="utf-8").strip()
    suffix = uuid4().hex
    name, role = ("test_stage3h3b3_" if journey_tests else "test_mc1_") + suffix, "mc1_owner_" + suffix
    marker = ("sales-ai-demo-b3-disposable:" if journey_tests else "strategy-foundation-disposable:") + suffix
    isolated_password = secrets.token_urlsafe(48)
    runtime_role = "mc3_runtime_" + suffix
    runtime_password = secrets.token_urlsafe(48)
    runtime_created = False
    publication_role = "mc4_runtime_" + suffix
    publication_password = secrets.token_urlsafe(48)
    publication_created = False
    capability_owner = "sa_lock_b6_" + suffix
    capability_created = False
    with boundary.control(connector, host="127.0.0.1", port=5433, dbname="postgres", user="sales_ai_demo_bootstrap",
                        password=password, autocommit=True, connect_timeout=5) as control:
        control.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(role), sql.Literal(isolated_password)))
        created = False
        oid = None
        try:
            control.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name), sql.Identifier(role)))
            created = True
            oid = control.execute("SELECT oid FROM pg_database WHERE datname=%s", [name]).fetchone()[0]
            control.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(name), sql.Literal(marker)))
            control.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
            require(boundary.enroll(suffix=suffix, oid=oid, journey=journey_tests) == name, "Disposable enrollment mismatch.")
            configure({"ENGINE": "django.db.backends.postgresql", "NAME": name, "USER": role,
                       "PASSWORD": isolated_password, "HOST": "127.0.0.1", "PORT": "5433", "CONN_MAX_AGE": 0}, boundary=boundary)
            from django.core.management import call_command
            from django.db import connection, connections
            from django.test.runner import DiscoverRunner
            call_command("migrate", interactive=False, verbosity=0)
            from django.db.migrations.loader import MigrationLoader
            loader = MigrationLoader(connection)
            require(set(loader.disk_migrations) == set(loader.applied_migrations), "Disposable migration graph mismatch.")
            print("Disposable identity verified:", name, "migrations:", len(loader.applied_migrations))
            checks()

            if runtime_tests:
                # Disposable-only role and exact object grants. Runtime cannot
                # publish, edit source tables, create versions or alter schema.
                control.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}")
                                .format(sql.Identifier(runtime_role), sql.Literal(runtime_password)))
                runtime_created = True
                control.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(name), sql.Identifier(runtime_role)))
                from django.conf import settings
                from apps.management.models import StrategyComparison, StrategyPolicyEvent
                source_tables = (
                    "auth_user", "customers_customer", "customers_customergrade", "visits_salesperson", "visits_customerassignment",
                    "products_product", "products_brand", "products_category", "products_productdemoprice", "inventory_inventory",
                    "recommendations_customerrecommendation", "targets_salestarget", "promotions_promotion",
                    "promotions_promotionproduct", "promotions_promotion_customer_grades",
                    "management_strategypolicy", "management_strategypolicyversion", "management_strategycomparison", "management_strategypolicyevent",
                )
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime_role)))
                    for table in source_tables:
                        cursor.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(runtime_role)))
                    cursor.execute(sql.SQL("GRANT UPDATE (revision) ON management_strategypolicy TO {}").format(sql.Identifier(runtime_role)))
                    for model in (StrategyComparison, StrategyPolicyEvent):
                        table = model._meta.db_table
                        cursor.execute(sql.SQL("GRANT INSERT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(runtime_role)))
                        cursor.execute("SELECT pg_get_serial_sequence(%s,'id')", [table])
                        sequence = cursor.fetchone()[0]
                        cursor.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}")
                                       .format(sql.Identifier(*sequence.split(".")), sql.Identifier(runtime_role)))
                settings.STRATEGY_TEST_RUNTIME = {"NAME": name, "USER": runtime_role, "PASSWORD": runtime_password}

                if publication_tests:
                    # Separate disposable publication identity: preserve C3's
                    # SELECT/preview-only role and its negative grant tests.
                    control.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}")
                                    .format(sql.Identifier(publication_role), sql.Literal(publication_password)))
                    publication_created = True
                    control.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(name), sql.Identifier(publication_role)))
                    with connection.cursor() as cursor:
                        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(publication_role)))
                        for table in source_tables:
                            cursor.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(publication_role)))
                        cursor.execute(sql.SQL("GRANT INSERT, UPDATE (revision, active_version_id, draft_version_id) ON management_strategypolicy TO {}")
                                       .format(sql.Identifier(publication_role)))
                        for table in ("management_strategypolicyversion", "management_strategycomparison", "management_strategypolicyevent"):
                            cursor.execute(sql.SQL("GRANT INSERT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(publication_role)))
                            cursor.execute("SELECT pg_get_serial_sequence(%s,'id')", [table])
                            sequence = cursor.fetchone()[0]
                            cursor.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}")
                                           .format(sql.Identifier(*sequence.split(".")), sql.Identifier(publication_role)))
                    settings.STRATEGY_PUBLICATION_RUNTIME = {"NAME": name, "USER": publication_role, "PASSWORD": publication_password}
                    if api_tests:
                        # Normal Django login/session writes in the disposable
                        # API environment only; no persistent role changes.
                        with connection.cursor() as cursor:
                            cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON django_session TO {}")
                                           .format(sql.Identifier(publication_role)))
                            cursor.execute(sql.SQL("GRANT UPDATE (last_login) ON auth_user TO {}")
                                           .format(sql.Identifier(publication_role)))

            if journey_tests:
                require(publication_created, "Journey capability tests require independent runtime setup.")
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL("GRANT SELECT ON visits_visit TO {}").format(sql.Identifier(publication_role)))
                control.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS")
                                .format(sql.Identifier(capability_owner)))
                capability_created = True
                import lock_capabilities
                prior_runtime = lock_capabilities.RUNTIME
                try:
                    lock_capabilities.RUNTIME = publication_role
                    with psycopg.connect(host="127.0.0.1", port=5433, dbname=name, user="sales_ai_demo_bootstrap", password=password) as isolated:
                        # Existing installer independently verifies exact
                        # endpoint/database/OID/marker and approved SQL hash.
                        lock_capabilities.install(isolated, database=name, oid=oid, marker=marker, owner=capability_owner)
                        for signature in lock_capabilities.SIGNATURES:
                            isolated.execute(sql.SQL("GRANT EXECUTE ON FUNCTION sales_ai_locks.{} TO {}")
                                             .format(sql.SQL(signature), sql.Identifier(role)))
                        isolated.execute(sql.SQL("GRANT USAGE ON SCHEMA sales_ai_locks TO {}").format(sql.Identifier(role)))
                finally:
                    lock_capabilities.RUNTIME = prior_runtime

            class IsolatedRunner(DiscoverRunner):
                def setup_databases(self, **kwargs):
                    return []  # Already migrated exclusively-owned, UUID-marked DB.

                def teardown_databases(self, old_config, **kwargs):
                    connections.close_all()  # Cleanup below revalidates OID/marker.

            failures = IsolatedRunner(verbosity=2, interactive=False).run_tests(test_labels)
            if failures:
                raise SystemExit(1)
        finally:
            try:
                from django.db import connections
                connections.close_all()
            finally:
                if created:
                    identity = control.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [name]).fetchone()
                    if identity != (oid, marker):
                        raise RuntimeError("Cleanup refused: disposable identity changed.")
                    control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
                control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
                if runtime_created:
                    control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_role)))
                if publication_created:
                    control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(publication_role)))
                if capability_created:
                    control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(capability_owner)))
                print("Disposable database/test roles removed. No persistent Demo/production connection or preservation probe.")
                print("Verified connection targets:", sorted({database for database, _ in boundary.attempts}))


if __name__ == "__main__":
    main()
