"""SELECT-only PostgreSQL checksum regressions; no test database writes.

Run with RECONCILIATION_TEST_DSN pointing to a read-only PostgreSQL connection.
The controlled auth_user fixtures are typed inline records, never INSERTs.
"""
import json
import os
import unittest

import psycopg
from psycopg import sql

from apps.core.reconciliation import canonical_row_expression, canonical_table_checksums, checksum_rows


class ReconciliationChecksumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("RECONCILIATION_TEST_DSN")
        if not dsn:
            raise unittest.SkipTest("Explicit read-only PostgreSQL DSN required")
        cls.conn = psycopg.connect(dsn)
        cls.conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        if cls.conn.execute("SHOW transaction_read_only").fetchone()[0] != "on":
            cls.conn.close()
            raise AssertionError("Checksum tests require database-enforced read-only access")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.rollback()
        self.fixture = {
            "id": 991, "username": "isolated-fixture", "password": "not-a-real-password-hash",
            "first_name": "نمونه", "last_name": "آزمایش", "email": "before@example.invalid",
            "is_active": True, "is_staff": False, "is_superuser": False,
            "last_login": "2026-10-09T05:12:55.763574Z",
            "date_joined": "2026-01-01T01:02:03.000004Z",
        }

    def timezone(self, zone):
        self.conn.execute("SELECT set_config('TimeZone', %s, true)", (zone,))

    def row(self, fixture=None, canonical=True):
        expression = canonical_row_expression("t", ["last_login", "date_joined"]) if canonical else sql.SQL("row_to_json(t)")
        query = sql.SQL("SELECT {row}::text FROM jsonb_populate_record(NULL::public.auth_user, %s::jsonb) AS t").format(row=expression)
        return self.conn.execute(query, (json.dumps(self.fixture if fixture is None else fixture),)).fetchone()[0]

    def test_raw_timezone_mismatch_and_canonical_equality(self):
        self.timezone("Asia/Tehran")
        raw_tehran, canonical_tehran = self.row(canonical=False), self.row()
        self.timezone("UTC")
        self.assertNotEqual(checksum_rows([raw_tehran]), checksum_rows([self.row(canonical=False)]))
        self.assertEqual(checksum_rows([canonical_tehran]), checksum_rows([self.row()]))

    def test_utc_six_microsecond_format_and_same_instant(self):
        self.assertEqual(json.loads(self.row())["last_login"], "2026-10-09T05:12:55.763574Z")
        equivalent = {**self.fixture, "last_login": "2026-10-09T08:42:55.763574+03:30"}
        self.assertEqual(self.row(), self.row(equivalent))
        self.assertEqual(json.loads(self.row())["date_joined"], "2026-01-01T01:02:03.000004Z")

    def test_real_table_checksums_match_across_timezones(self):
        self.timezone("Asia/Tehran")
        before = canonical_table_checksums(self.conn)
        self.timezone("UTC")
        self.assertEqual(before, canonical_table_checksums(self.conn))
        self.assertIn("auth_user", before)

    def test_controlled_auth_user_changes_remain_detectable(self):
        before = checksum_rows([self.row()])
        for column, value in {
            "email": "changed@example.invalid", "username": "changed-fixture",
            "password": "different-fixture-placeholder", "is_active": False,
            "last_login": "2026-10-09T05:12:55.763575Z",
            "date_joined": "2026-01-01T01:02:03.000005Z",
        }.items():
            with self.subTest(column=column):
                self.assertNotEqual(before, checksum_rows([self.row({**self.fixture, column: value})]))

    def test_timestamp_like_text_is_not_normalized(self):
        before = self.row({**self.fixture, "first_name": "2026-10-09T05:12:55Z"})
        after = self.row({**self.fixture, "first_name": "2026-10-09T08:42:55+03:30"})
        self.assertNotEqual(checksum_rows([before]), checksum_rows([after]))

    def test_null_infinity_numeric_and_json_values_are_preserved(self):
        rows = [self.row({**self.fixture, "last_login": value}) for value in [None, "infinity", "-infinity"]]
        self.assertEqual(len({checksum_rows([row])["digest"] for row in rows}), 3)
        self.assertIsNone(json.loads(rows[0])["last_login"])
        query = sql.SQL("""SELECT {row}::text FROM
            (SELECT %s::numeric AS amount, %s::jsonb AS evidence, %s::timestamp AS local_time) AS t
            """).format(row=canonical_row_expression("t", []))
        params = ("12345678901234567890.123456", '{"text":"2026-10-09T08:42:55+03:30"}', "2026-10-09 01:02:03.123456")
        self.timezone("UTC")
        before = self.conn.execute(query, params).fetchone()[0]
        self.timezone("Asia/Tehran")
        self.assertEqual(before, self.conn.execute(query, params).fetchone()[0])
        self.assertIn("12345678901234567890.123456", before)
        changed = ("12345678901234567890.123457", *params[1:])
        self.assertNotEqual(checksum_rows([before]), checksum_rows([self.conn.execute(query, changed).fetchone()[0]]))
