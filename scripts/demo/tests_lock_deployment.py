"""B7 deployment/readiness tests, exclusively inside the disposable B3 runner."""
import hashlib
from unittest.mock import patch

from common import BOOTSTRAP, DemoError, write_json
from tests_generation_postgres import LiveGenerationTests


class DeploymentTests(LiveGenerationTests):
    def test_42_launcher_missing_registry_fails_before_django_setup(self):
        import demo
        import tempfile
        with tempfile.TemporaryDirectory(dir=self.artifacts) as state:
            with patch.object(demo, 'verify_container'), patch.object(demo, 'connect', side_effect=lambda *a: self.probe()), \
                 patch.object(demo, 'configure_django') as configure:
                with self.assertRaises(DemoError):
                    demo.preflight(self.test_profile, state)
                configure.assert_not_called()

    def test_40_exact_runtime_inspection_idempotent_install_and_drift_rejection(self):
        from lock_capabilities import inspect, install, validate_runtime
        from plan import fingerprint
        import tempfile
        from pathlib import Path
        with self.probe() as raw:
            before = inspect(raw, owner=self.capability_owner)
        with self.probe(BOOTSTRAP) as raw:
            row = raw.execute("SELECT current_database(),d.oid,shobj_description(d.oid,'pg_database') "
                              "FROM pg_database d WHERE datname=current_database()").fetchone()
            # Identity SELECT has already begun the transaction; explicit LOCAL
            # read-only makes repeat install prove it issues no DDL or grants.
            raw.execute('SET LOCAL transaction_read_only=on')
            after = install(raw, database=row[0], oid=row[1], marker=row[2], owner=self.capability_owner)
            self.assertEqual(after, before)
        with tempfile.TemporaryDirectory(dir=self.artifacts) as directory:
            path = Path(directory) / 'lock-capabilities.json'
            write_json(path, dict(identity=self.test_profile['identity'], database=self.test_profile['database'],
                                  database_oid=self.test_profile['database_oid'], snapshot=before))
            path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding='ascii')
            with self.probe() as raw:
                self.assertEqual(validate_runtime(raw, self.test_profile, directory, owner=self.capability_owner), before)
                with self.assertRaises(DemoError):
                    validate_runtime(raw, {**self.test_profile, 'database_oid': 0}, directory, owner=self.capability_owner)
                with patch('lock_capabilities.inspect', return_value={**before, 'schema_oid': 0}):
                    with self.assertRaises(DemoError):
                        validate_runtime(raw, self.test_profile, directory, owner=self.capability_owner)
            path.with_suffix('.sha256').write_text('bad', encoding='ascii')
            with self.probe() as raw, self.assertRaises(DemoError):
                validate_runtime(raw, self.test_profile, directory, owner=self.capability_owner)
        # An incompatible catalog body fails closed, and rollback restores it.
        with self.probe(BOOTSTRAP) as raw:
            raw.execute("COMMENT ON FUNCTION sales_ai_locks.lock_feedback_references(bigint,bigint) IS 'WRONG'")
            with self.assertRaises(DemoError):
                inspect(raw, owner=self.capability_owner)
            raw.rollback()
        with self.probe() as raw:
            self.assertEqual(fingerprint(inspect(raw, owner=self.capability_owner)), fingerprint(before))

    def test_41_service_rollback_probe_does_not_advance_sequences(self):
        from django.db import connection
        from lock_rollback_probe import exercise
        with connection.cursor() as cursor:
            cursor.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY 1")
            before_seq = cursor.fetchall()
        before = self.state()
        result = exercise(self.user, self.visit, self.recs[0])
        self.assertEqual((result['request_status'], result['completion'], result['acknowledgements']),
                         ('SUBMITTED', 'COMPLETED', 1))
        self.assertEqual(self.state(), before)
        with connection.cursor() as cursor:
            cursor.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY 1")
            self.assertEqual(cursor.fetchall(), before_seq)
