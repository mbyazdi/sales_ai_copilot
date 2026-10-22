"""DB-free routing tests. Mock connector/cursor sentinels must remain untouched."""
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from scripts.management_test_isolation import (
    ManagementTestBoundary, check_memory, clear_inherited_routing, connect_preview,
)


class ManagementIsolationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.suffix = uuid4().hex
        self.boundary = ManagementTestBoundary()
        self.name = self.boundary.enroll(suffix=self.suffix, oid=12345)
        self.params = dict(dbname=self.name, user="mc1_owner_"+self.suffix, host="127.0.0.1", port=5433)
        self.profile = dict(identity=str(uuid4()), kind="MANAGEMENT_TEST_PREVIEW_V1", host="127.0.0.1", port=5433,
                            application_port=8901, oid=23456)
        suffix = self.profile["identity"].replace("-", "")
        self.profile.update(database="test_me01_"+suffix, owner="me01_owner_"+suffix, runtime="me01_runtime_"+suffix,
                            marker="management-test-preview:"+suffix)

    def test_protected_and_unenrolled_targets_never_reach_connection_or_cursor(self):
        for database in ("sales_ai_db", "sales_ai_demo_db", "postgres", "test_other", "test_mc1_"+uuid4().hex, None, ""):
            connector = Mock()
            with self.subTest(database=database), self.assertRaises(RuntimeError):
                self.boundary.connect(connector, **dict(self.params, dbname=database))
            connector.assert_not_called(); connector.return_value.cursor.assert_not_called()

    def test_wrong_endpoint_role_and_routing_overrides_are_rejected_offline(self):
        for override in ({"host":"localhost"},{"host":"127.0.0.1,hostile"},{"port":5432},{"user":"sales_ai_demo_runtime"},
                         {"user":"mc1_owner_"+uuid4().hex},{"service":"hidden"},{"hostaddr":"127.0.0.1"},
                         {"passfile":"hidden"},{"servicefile":"hidden"},{"replication":"database"}):
            connector=Mock()
            with self.subTest(override=override), self.assertRaises(RuntimeError):
                self.boundary.connect(connector, **dict(self.params, **override))
            connector.assert_not_called()

    def test_dsn_and_inherited_libpq_settings_cannot_override_identity(self):
        connector=Mock()
        with self.assertRaises(RuntimeError):self.boundary.connect(connector,"dbname=sales_ai_demo_db",**self.params)
        for key in ("PGHOSTADDR","PGSERVICE","PGDATABASE","PGUSER","DATABASE_URL","DB_ENGINE","POSTGRES_DB"):
            with patch.dict(os.environ,{key:"protected"}),self.assertRaises(RuntimeError):
                self.boundary.connect(connector,**self.params)
        connector.assert_not_called()

    def test_environment_is_scrubbed_without_loading_inherited_settings(self):
        os.environ.update(PGHOSTADDR="protected",POSTGRES_DB="sales_ai_db",DATABASE_URL="protected",DB_ENGINE="postgresql",DJANGO_SETTINGS_MODULE="untrusted.settings")
        clear_inherited_routing()
        self.assertFalse(any(key in os.environ for key in ("PGHOSTADDR","POSTGRES_DB","DATABASE_URL","DB_ENGINE","DJANGO_SETTINGS_MODULE")))

    def test_exact_disposable_identity_is_attested_before_returning_connection(self):
        connector=Mock();raw=connector.return_value;raw.autocommit=False
        raw.execute.return_value.fetchone.return_value=(self.name,self.params["user"],12345,"strategy-foundation-disposable:"+self.suffix,5432)
        self.assertIs(self.boundary.connect(connector,**self.params),raw)
        raw.rollback.assert_called_once();raw.cursor.assert_not_called()
        self.assertEqual(self.boundary.attempts,[(self.name,self.params["user"])])

    def test_live_oid_marker_or_endpoint_mismatch_closes_without_test_sql(self):
        for actual in (None,(self.name,self.params["user"],12346,"wrong",5432),("sales_ai_demo_db",self.params["user"],12345,"wrong",5432)):
            connector=Mock();raw=connector.return_value;raw.execute.return_value.fetchone.return_value=actual
            with self.assertRaises(RuntimeError):self.boundary.connect(connector,**self.params)
            raw.close.assert_called_once();self.assertEqual(raw.execute.call_count,1);raw.cursor.assert_not_called()

    def test_configuration_rejected_before_django_setup_or_driver_connection(self):
        from apps.management.verify_strategy_foundation import configure
        for config in ({"ENGINE":"django.db.backends.postgresql","NAME":"sales_ai_demo_db"},
                       {"ENGINE":"django.db.backends.postgresql","NAME":self.name},
                       {"ENGINE":"django.db.backends.sqlite3","NAME":"db.sqlite3"},
                       {"ENGINE":"django.db.backends.mysql","NAME":"unexpected"}):
            with patch("django.setup") as setup,patch("psycopg.connect") as network,self.assertRaises(RuntimeError):
                configure(config)
            setup.assert_not_called();network.assert_not_called()

    def test_memory_only_sqlite_and_no_disk_fallback(self):
        for name in (":memory:","file:memorydb_default?mode=memory&cache=shared"):
            check_memory({"database":name})
        for name in ("db.sqlite3",Path("db.sqlite3"),"test.sqlite3","",None,"file:db.sqlite3?mode=ro"):
            with self.assertRaises(RuntimeError):check_memory({"database":name})

    def test_inherited_django_settings_are_not_adopted_even_for_valid_memory_config(self):
        from apps.management.verify_strategy_foundation import configure
        from django.conf import LazySettings
        with patch.object(LazySettings,"configured",True),patch("psycopg.connect") as network,patch("django.setup") as setup:
            with self.assertRaisesRegex(RuntimeError,"fresh process"):
                configure({"ENGINE":"django.db.backends.sqlite3","NAME":":memory:"})
        network.assert_not_called();setup.assert_not_called()

    def test_installed_driver_guard_rejects_direct_connections_not_just_django(self):
        from django.db.backends.sqlite3.base import DatabaseWrapper
        with patch("psycopg.connect") as network,patch.object(DatabaseWrapper,"get_new_connection") as sqlite:
            self.boundary.install()
            import psycopg
            with self.assertRaises(RuntimeError):psycopg.connect(**dict(self.params,dbname="sales_ai_demo_db"))
            with self.assertRaises(RuntimeError):DatabaseWrapper({},alias="default").get_new_connection({"database":"db.sqlite3"})
            network.assert_not_called();sqlite.assert_not_called()

    def test_catalog_channel_requires_explicit_provisioning_and_is_not_general_access(self):
        params=dict(dbname="postgres",user="sales_ai_demo_bootstrap",host="127.0.0.1",port=5433)
        connector=Mock()
        with self.assertRaises(RuntimeError):self.boundary.control(connector,**params)
        allowed=ManagementTestBoundary(allow_provisioning=True)
        for override in ({"dbname":"sales_ai_demo_db"},{"dbname":"sales_ai_db"},{"port":5432},{"user":"postgres"}):
            with self.assertRaises(RuntimeError):allowed.control(connector,**dict(params,**override))
        connector.assert_not_called()
        with self.assertRaises(RuntimeError):allowed.connect(connector,**params)
        connector.assert_not_called()

    def test_default_postgres_runner_refuses_before_any_connection(self):
        from apps.management.verify_strategy_foundation import main
        with patch("sys.argv",["runner"]),patch("psycopg.connect") as network,self.assertRaisesRegex(RuntimeError,"provision-disposable"):
            main(test_labels=["apps.management.tests_strategy_ui"])
        network.assert_not_called()

    def test_preview_verification_rejects_protected_profiles_before_connect(self):
        for change in ({"database":"sales_ai_demo_db"},{"database":"sales_ai_db"},{"port":5432},
                       {"oid":None},{"marker":"wrong"},{"application_port":8900}):
            with patch("psycopg.connect") as network,self.assertRaises((RuntimeError,TypeError)):
                connect_preview(dict(self.profile,**change),{"password":"unused"},self.profile["runtime"])
            network.assert_not_called();network.return_value.cursor.assert_not_called()

    def test_preview_overrides_environment_and_wrong_role_never_connect(self):
        for override in ({"hostaddr":"127.0.0.1"},{"service":"hidden"},{"dbname":"sales_ai_db"},{"host":"127.0.0.1"}):
            with patch("psycopg.connect") as network,self.assertRaises(RuntimeError):
                connect_preview(self.profile,{"password":"unused"},self.profile["runtime"],**override)
            network.assert_not_called()
        with patch.dict(os.environ,{"PGHOSTADDR":"protected"}),patch("psycopg.connect") as network,self.assertRaises(RuntimeError):
            connect_preview(self.profile,{"password":"unused"},self.profile["runtime"])
        network.assert_not_called()
        with patch("psycopg.connect") as network,self.assertRaises(RuntimeError):
            connect_preview(self.profile,{"password":"unused"},"sales_ai_demo_runtime")
        network.assert_not_called()

    def test_exact_preview_verification_attests_identity_before_return(self):
        with patch("psycopg.connect") as network:
            raw = network.return_value
            raw.execute.return_value.fetchone.return_value = (
                self.profile["database"], self.profile["runtime"], self.profile["oid"], self.profile["marker"], 5432)
            self.assertIs(connect_preview(self.profile, {"password":"unused"}, self.profile["runtime"]), raw)
            self.assertEqual(network.call_args.kwargs["dbname"], self.profile["database"])
            raw.rollback.assert_called_once()

    def test_disposable_enrollment_requires_exact_uuid_and_oid(self):
        for suffix, oid in (("test_",123), (self.suffix,None), (self.suffix,True), (self.suffix,0)):
            with self.assertRaises((RuntimeError,ValueError)):
                ManagementTestBoundary().enroll(suffix=suffix,oid=oid)

    def test_no_persistent_probe_remains_in_foundation_or_verification_calls(self):
        source=Path("apps/management/verify_strategy_foundation.py").read_text(encoding="utf-8")
        self.assertNotIn("persistent_digest",source);self.assertNotIn('dbname="sales_ai_demo_db"',source)
        # The one remaining direct installer call is guarded by the installed
        # driver boundary. Direct verification calls use connect_preview instead.
        verification=Path("scripts/verify_management_preview.py").read_text(encoding="utf-8")
        self.assertNotIn("psycopg.connect(",verification)


if __name__=="__main__":unittest.main()
