"""No database access: fail-closed TEST profile and connection routing contracts."""
import unittest
import hashlib
import hmac
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4
from scripts.management_preview import params_allowed, valid_profile, configure, load, dump, encoded


class PreviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        token = uuid4()
        self.p = dict(identity=str(token), kind="MANAGEMENT_TEST_PREVIEW_V1", database="test_me01_"+token.hex,
            owner="me01_owner_"+token.hex, runtime="me01_runtime_"+token.hex, host="127.0.0.1", port=5433,
            application_port=8901, oid=12345, marker="management-test-preview:"+token.hex)
        self.params = dict(dbname=self.p["database"], user=self.p["runtime"], host="127.0.0.1", port=5433)

    def test_exact_disposable_identity(self):
        valid_profile(self.p)
        params_allowed(self.params, self.p, self.p["runtime"])

    def test_protected_and_ambiguous_profiles_rejected(self):
        for changes in ({"database": "sales_ai_db"}, {"database": "sales_ai_demo_db"}, {"database": "test_other"},
                        {"port": 5432}, {"host": "localhost"}, {"application_port": 8900}, {"oid": None},
                        {"marker": "wrong"}, {"runtime": "sales_ai_demo_runtime"}, {"kind": "DEMO"}):
            with self.subTest(changes=changes), self.assertRaises((RuntimeError, TypeError)):
                valid_profile(dict(self.p, **changes))

    def test_connection_routing_is_exact_before_any_network(self):
        for changes in ({"dbname": "sales_ai_db"}, {"dbname": "sales_ai_demo_db"}, {"dbname": None},
                        {"host": "localhost"}, {"port": 5432}, {"user": self.p["owner"]},
                        {"service": "anything"}, {"hostaddr": "127.0.0.1"}, {"passfile": "anything"}):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                params_allowed(dict(self.params, **changes), self.p, self.p["runtime"])

    def test_invalid_profile_cannot_initialize_django_or_connect(self):
        with patch("psycopg.connect") as connect:
            with self.assertRaises(RuntimeError):
                configure(dict(self.p, database="sales_ai_demo_db"), {}, self.p["runtime"])
            connect.assert_not_called()

    def test_missing_tampered_and_changed_source_evidence(self):
        with TemporaryDirectory() as directory:
            state = Path(directory)
            with self.assertRaises(FileNotFoundError):
                load(state)
            profile = dict(self.p, source_sha256="reviewed-source")
            dump(state / "profile.json", profile)
            dump(state / "runtime.json", {"control": "unit-test-only"})
            (state / "profile.hmac").write_text(hmac.new(b"unit-test-only", encoded(profile), hashlib.sha256).hexdigest())
            with patch("scripts.management_preview.fingerprint", return_value="reviewed-source"):
                self.assertEqual(load(state)[0], profile)
            with patch("scripts.management_preview.fingerprint", return_value="changed-source"), self.assertRaises(RuntimeError):
                load(state)
            # Source drift must not make authenticated shutdown/recovery impossible.
            self.assertEqual(load(state, check_source=False)[0], profile)
            dump(state / "profile.json", dict(profile, oid=999))
            with self.assertRaises(RuntimeError):
                load(state, check_source=False)

    def test_runtime_driver_and_sqlite_guards_fail_before_network(self):
        import psycopg
        with patch("psycopg.connect") as network:
            configure(self.p, {"password": "unused-test-only", "django_key": "test-only-"*8}, self.p["runtime"])
            for changes in ({"dbname": "sales_ai_db"}, {"dbname": "sales_ai_demo_db"}, {"port": 5432},
                            {"user": self.p["owner"]}, {"hostaddr": "127.0.0.1"}):
                with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                    psycopg.connect(**dict(self.params, **changes))
            with self.assertRaises(RuntimeError):
                psycopg.connect("dbname=sales_ai_demo_db")
            network.assert_not_called()
        from django.conf import settings
        self.assertFalse(settings.DATABASES["default"]["ATOMIC_REQUESTS"])
        self.assertFalse(hasattr(settings, "DEMO_GENERATION_CONFIG"))
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)
        self.assertIn("django.contrib.sessions.middleware.SessionMiddleware", settings.MIDDLEWARE)
        from django.db.backends.sqlite3.base import DatabaseWrapper
        with self.assertRaises(RuntimeError):
            DatabaseWrapper({"NAME": "db.sqlite3"}, alias="forbidden").get_new_connection({})


if __name__ == "__main__":
    unittest.main()
