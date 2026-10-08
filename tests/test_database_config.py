"""Configuration tests only: no database setup, SQL or credential-file reads."""
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db.utils import ConnectionHandler
from django.test import SimpleTestCase

from sales_ai_copilot.database import database_configuration


class DatabaseConfigurationTests(SimpleTestCase):
    base_dir = Path("portable-project")

    def postgres_env(self, **changes):
        values = {
            "DB_ENGINE": "postgresql", "POSTGRES_DB": "config_example",
            "POSTGRES_USER": "config_user", "POSTGRES_PASSWORD": "fixture-only-not-a-real-password",
        }
        values.update(changes)
        return values

    def test_unset_selector_preserves_exact_sqlite_configuration(self):
        self.assertEqual(database_configuration(self.base_dir, {}), {
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": self.base_dir / "db.sqlite3"},
        })

    def test_postgres_values_do_not_implicitly_select_postgres(self):
        environ = self.postgres_env()
        environ.pop("DB_ENGINE")
        self.assertEqual(database_configuration(self.base_dir, environ)["default"]["ENGINE"], "django.db.backends.sqlite3")

    def test_sqlite_ignores_invalid_unused_postgres_values(self):
        environ = self.postgres_env(DB_ENGINE="sqlite", POSTGRES_PORT="invalid", POSTGRES_PASSWORD="")
        self.assertEqual(database_configuration(self.base_dir, environ)["default"]["NAME"], self.base_dir / "db.sqlite3")

    def test_empty_selector_and_case_whitespace_handling(self):
        self.assertEqual(database_configuration(self.base_dir, {"DB_ENGINE": " "})["default"]["ENGINE"], "django.db.backends.sqlite3")
        environ = self.postgres_env(DB_ENGINE=" PostgreSQL ")
        self.assertEqual(database_configuration(self.base_dir, environ)["default"]["ENGINE"], "django.db.backends.postgresql")

    def test_unknown_selector_fails_without_sqlite_fallback_or_value_disclosure(self):
        with self.assertRaises(ImproperlyConfigured) as failure:
            database_configuration(self.base_dir, {"DB_ENGINE": "unknown-private-value"})
        self.assertNotIn("unknown-private-value", str(failure.exception))

    def test_postgres_configuration_has_explicit_credentials_and_portable_defaults(self):
        config = database_configuration(self.base_dir, self.postgres_env())["default"]
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((config["NAME"], config["USER"]), ("config_example", "config_user"))
        self.assertEqual(config["PASSWORD"], "fixture-only-not-a-real-password")
        self.assertEqual((config["HOST"], config["PORT"]), ("127.0.0.1", 5432))
        self.assertEqual(config["OPTIONS"], {"sslmode": "prefer", "connect_timeout": 5})

    def test_required_credentials_fail_closed_when_missing_or_blank(self):
        for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            for value in (None, "", " "):
                environ = self.postgres_env()
                if value is None:
                    environ.pop(name)
                else:
                    environ[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ImproperlyConfigured) as failure:
                    database_configuration(self.base_dir, environ)
                self.assertIn(name, str(failure.exception))
                self.assertNotIn("fixture-only-not-a-real-password", str(failure.exception))

    def test_password_special_characters_and_whitespace_are_preserved(self):
        password = " fixture:$#= 'quoted' \\ value "
        config = database_configuration(self.base_dir, self.postgres_env(POSTGRES_PASSWORD=password))["default"]
        self.assertEqual(config["PASSWORD"], password)

    def test_office_environment_can_override_connection_parameters(self):
        config = database_configuration(self.base_dir, self.postgres_env(
            POSTGRES_HOST="office-db.example", POSTGRES_PORT="6543", POSTGRES_DB="office_example",
            POSTGRES_USER="office_user", POSTGRES_SSLMODE="verify-full", POSTGRES_CONNECT_TIMEOUT="12",
        ))["default"]
        self.assertEqual((config["HOST"], config["PORT"], config["NAME"], config["USER"]),
                         ("office-db.example", 6543, "office_example", "office_user"))
        self.assertEqual(config["OPTIONS"], {"sslmode": "verify-full", "connect_timeout": 12})

    def test_invalid_port_is_rejected(self):
        for port in ("0", "65536", "-1", "5432.0", "", "port", "۵۴۳۲"):
            with self.subTest(port=port), self.assertRaises(ImproperlyConfigured):
                database_configuration(self.base_dir, self.postgres_env(POSTGRES_PORT=port))

    def test_invalid_timeout_is_rejected(self):
        for timeout in ("0", "-1", "1.5", "", "2147483648"):
            with self.subTest(timeout=timeout), self.assertRaises(ImproperlyConfigured):
                database_configuration(self.base_dir, self.postgres_env(POSTGRES_CONNECT_TIMEOUT=timeout))

    def test_invalid_sslmode_and_empty_host_are_rejected(self):
        for changes in ({"POSTGRES_SSLMODE": "invalid"}, {"POSTGRES_HOST": " "}):
            with self.subTest(changes=changes), self.assertRaises(ImproperlyConfigured):
                database_configuration(self.base_dir, self.postgres_env(**changes))

    def test_configuration_reads_process_environment_without_loading_files(self):
        with patch.dict("os.environ", self.postgres_env(), clear=True):
            config = database_configuration(self.base_dir)["default"]
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")

    def test_configuration_does_not_mutate_supplied_environment(self):
        environ = self.postgres_env()
        before = dict(environ)
        database_configuration(self.base_dir, environ)
        self.assertEqual(environ, before)

    def test_django_test_database_name_is_separate_for_both_backends_without_connecting(self):
        for environ in ({}, self.postgres_env()):
            handler = ConnectionHandler(database_configuration(self.base_dir, environ))
            connection = handler["default"]
            self.assertIsNone(connection.connection)
            test_name = connection.creation._get_test_db_name()
            self.assertNotEqual(test_name, str(connection.settings_dict["NAME"]))
            self.assertFalse(connection.settings_dict["TEST"]["MIRROR"])
            self.assertIsNone(connection.connection)
            if connection.vendor == "postgresql":
                self.assertEqual(test_name, "test_config_example")
