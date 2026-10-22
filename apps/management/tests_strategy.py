"""Focused persistence tests; no evaluator, publication endpoint or demo data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, connections, models, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.customers.models import Customer
from apps.products.models import Brand
from apps.visits.models import CustomerAssignment, Salesperson
from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_access import can_manage_strategy, can_view_strategy
from .strategy_persistence import StrategyConflict, StrategyEffect, run_strategy_command
from .strategy_serialization import canonical_json, configuration_fingerprint, fingerprint, neutral_config


class StrategyFixture:
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username="strategy-manager", is_staff=True)
        self.policy = StrategyPolicy.objects.create()

    def version(self, **kwargs):
        return StrategyPolicyVersion.objects.create(policy=self.policy, author=self.manager, config=neutral_config(), **kwargs)

    def draft(self, revision=0, command=None, intent=None, handler=None, actor=None):
        return run_strategy_command(
            actor=actor or self.manager, command_uuid=command or uuid4(), operation="SAVE_DRAFT",
            expected_revision=revision, intent=intent or {"config": neutral_config()},
            handler=handler or (lambda policy: StrategyEffect(self.version(), {"saved": True})),
        )

    def comparison(self, version=None, **kwargs):
        customer = Customer.objects.create(customer_code="STRATEGY-C", name="مشتری آزمایشی")
        rep = Salesperson.objects.create(employee_code="STRATEGY-SP", first_name="فروشنده", last_name="آزمایشی")
        CustomerAssignment.objects.create(customer=customer, salesperson=rep, start_date=date(2026, 1, 1))
        return StrategyComparison.objects.create(
            policy=self.policy, after_version=version or self.version(), author=self.manager,
            customer=customer, salesperson=rep, evaluation_date=date(2026, 10, 16), source_version="fixture-v1",
            inputs={"recommendations": [], "amount": Decimal("100.00")}, outputs={"before": [], "after": []}, **kwargs,
        )


class StrategySerializationTests(TestCase):
    def test_decimal_scale_key_order_unicode_and_utc_are_stable(self):
        utc = datetime(2026, 10, 16, 8, 30, 1, 123456, tzinfo=timezone.utc)
        first = {"amount": Decimal("12.500"), "time": utc, "name": "راهبرد"}
        second = {"name": "راهبرد", "time": utc.astimezone(timezone(timedelta(hours=3, minutes=30))), "amount": Decimal("12.5")}
        self.assertEqual(fingerprint(first), fingerprint(second))
        self.assertIn("2026-10-16T08:30:01.123456Z", canonical_json(first))
        self.assertEqual(fingerprint(Decimal("-0.000")), fingerprint(Decimal("0")))
        self.assertNotEqual(fingerprint(first), fingerprint({**first, "amount": Decimal("12.51")}))

    def test_floats_nonfinite_naive_timestamps_and_nonstring_keys_rejected(self):
        for value in (1.1, float("nan"), Decimal("Infinity"), datetime(2026, 1, 1), {1: "x"}, object()):
            with self.subTest(value=type(value)), self.assertRaises(ValidationError):
                fingerprint(value)

    def test_semantic_rule_order_and_algorithm_are_fingerprinted(self):
        rules = [{"scope_type": "PRODUCT", "scope_id": 2, "points": 20}, {"scope_type": "CATEGORY", "scope_id": 3, "points": 4}]
        first = {**neutral_config(), "priority_rules": rules}
        self.assertEqual(configuration_fingerprint(first), configuration_fingerprint({**first, "priority_rules": rules[::-1]}))
        self.assertNotEqual(configuration_fingerprint(first), configuration_fingerprint(neutral_config()))
        with self.assertRaises(ValidationError):
            configuration_fingerprint(first, "UNKNOWN")

    def test_exact_types_bounds_duplicates_and_unknown_keys(self):
        invalid = [
            {**neutral_config(), "target_weight": True}, {**neutral_config(), "target_weight": 6},
            {**neutral_config(), "schema_version": True}, {**neutral_config(), "extra": 1},
            {**neutral_config(), "priority_rules": [{"scope_type": "BRAND", "scope_id": 1, "points": 21}]},
            {**neutral_config(), "priority_rules": [{"scope_type": "UNKNOWN", "scope_id": 1, "points": 1}]},
            {**neutral_config(), "promotion_rules": [{"promotion_id": 1, "points": -1}]},
            {**neutral_config(), "promotion_rules": [{"promotion_id": 1, "points": 1}] * 2},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValidationError):
                configuration_fingerprint(config)


class StrategyIntegrityTests(StrategyFixture, TestCase):
    def test_singleton_head_and_empty_initial_state(self):
        with self.assertRaises(ValidationError):
            StrategyPolicy.objects.create(pk=2)
        with self.assertRaises(ValidationError):
            StrategyPolicy.objects.create(pk=1)
        self.assertEqual(self.policy.revision, 0)
        self.assertIsNone(self.policy.active_version_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet.bulk_create(StrategyPolicy.objects.all(), [StrategyPolicy(pk=2)])

    def test_configuration_reference_checks_and_explicit_zero(self):
        brand = Brand.objects.create(code="STRATEGY-B", name="Brand")
        config = {**neutral_config(), "priority_rules": [{"scope_type": "BRAND", "scope_id": brand.pk, "points": 0}]}
        version = StrategyPolicyVersion.objects.create(policy=self.policy, author=self.manager, config=config)
        self.assertEqual(version.config["priority_rules"][0]["points"], 0)
        for key, value in (("scope_type", "PRODUCT"), ("scope_id", 999999)):
            invalid = {**config, "priority_rules": [{**config["priority_rules"][0], key: value}]}
            with self.assertRaises(ValidationError):
                StrategyPolicyVersion.objects.create(policy=self.policy, author=self.manager, config=invalid)

    def test_supplied_wrong_hash_or_unknown_parent_rejected(self):
        with self.assertRaises(ValidationError):
            self.version(config_hash="0" * 64)
        with self.assertRaises(ValidationError):
            self.version(parent_id=999999)

    def test_same_config_can_have_multiple_immutable_versions_for_rollback(self):
        first = self.version()
        second = self.version(parent=first)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.config_hash, second.config_hash)

    def test_parent_cannot_be_self_and_protection_is_a_database_constraint(self):
        with self.assertRaises(ValidationError):
            self.version(pk=999999, parent_id=999999)
        with self.assertRaises(IntegrityError), transaction.atomic():
            version = StrategyPolicyVersion(pk=999999, parent_id=999999, policy=self.policy, author=self.manager, config=neutral_config())
            models.QuerySet.bulk_create(StrategyPolicyVersion.objects.all(), [version])

    def test_current_manager_role_and_fresh_actor_validation(self):
        regular = get_user_model().objects.create_user(username="ordinary")
        self.assertFalse(can_manage_strategy(regular))
        self.assertFalse(can_view_strategy(AnonymousUser()))
        self.assertTrue(can_view_strategy(self.manager))
        with self.assertRaises(PermissionDenied):
            StrategyPolicyVersion.objects.create(policy=self.policy, author=regular, config=neutral_config())
        get_user_model().objects.filter(pk=self.manager.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            self.draft()

    def test_comparison_freezes_binding_and_canonical_values(self):
        comparison = self.comparison()
        comparison.refresh_from_db()
        self.assertEqual(comparison.inputs["amount"], "100")
        original = comparison.input_digest
        comparison.evaluation_date = date(2026, 10, 17)
        with self.assertRaises(ValidationError):
            comparison.full_clean()
        self.assertEqual(StrategyComparison.objects.get(pk=comparison.pk).input_digest, original)

    def test_comparison_requires_genuine_assignment_and_matching_version(self):
        comparison = self.comparison()
        CustomerAssignment.objects.all().update(is_active=False)
        candidate = StrategyComparison(
            policy=self.policy, after_version=comparison.after_version, customer=comparison.customer,
            salesperson=comparison.salesperson, author=self.manager, evaluation_date=comparison.evaluation_date,
            source_version="fixture-v1", inputs={"x": 1}, outputs={"x": 1},
        )
        with self.assertRaises(ValidationError):
            candidate.save()
        comparison.full_clean()  # Historical assignment changes do not invalidate evidence.

    def test_immutable_guards_cover_instance_queryset_bulk_base_manager_and_pk_overwrite(self):
        receipt = self.draft().event
        comparison = self.comparison(receipt.version)
        for row in (self.policy, receipt.version, receipt, comparison):
            row.refresh_from_db()
            queryset = type(row).objects.filter(pk=row.pk)
            with self.subTest(model=type(row).__name__):
                for mutation in (
                    lambda: row.save(), lambda: row.delete(), lambda: queryset.delete(),
                    lambda: queryset.update(pk=row.pk), lambda: type(row)._base_manager.filter(pk=row.pk).update(pk=row.pk),
                    lambda: type(row).objects.bulk_update([row], ["id"]),
                    lambda: type(row).objects.bulk_create([row]),
                ):
                    with self.assertRaises(ValidationError):
                        mutation()
        clone = StrategyPolicyVersion(pk=receipt.version.pk, policy=self.policy, author=self.manager, config=neutral_config())
        with self.assertRaises(ValidationError):
            clone.save()

    def test_historical_evidence_survives_actor_deactivation_and_revision_advance(self):
        first = self.draft().event
        self.draft(revision=1)
        first.refresh_from_db()
        get_user_model().objects.filter(pk=self.manager.pk).update(is_active=False)
        first.full_clean()
        first.version.full_clean()
        self.assertEqual(first.applied_revision, 1)
        with self.assertRaises(ValidationError):
            first.save()

    def test_protected_references_cannot_be_deleted(self):
        self.draft()
        with self.assertRaises(models.ProtectedError):
            self.manager.delete()

    def test_reads_never_initialize_or_change_state(self):
        before = list(StrategyPolicy.objects.values())
        with CaptureQueriesContext(connection) as queries:
            list(StrategyPolicyVersion.objects.all())
            list(StrategyComparison.objects.all())
            list(StrategyPolicyEvent.objects.all())
            StrategyPolicy.objects.get(pk=1)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertEqual(list(StrategyPolicy.objects.values()), before)


class StrategyCommandTests(StrategyFixture, TestCase):
    def test_exact_replay_after_reload_returns_original_result_without_handler(self):
        command = uuid4()
        first = self.draft(command=command)
        self.draft(revision=1)
        replay = self.draft(command=command, handler=lambda _: self.fail("Replay invoked handler"))
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.event.pk, first.event.pk)
        self.assertEqual(replay.event.result, first.event.result)
        self.assertEqual(replay.event.applied_revision, 1)
        self.assertEqual(StrategyPolicyEvent.objects.count(), 2)

    def test_uuid_conflict_actor_conflict_and_stale_revision(self):
        command = uuid4()
        self.draft(command=command)
        other = get_user_model().objects.create_user(username="other-manager", is_staff=True)
        for kwargs in ({"command": command, "intent": {"different": True}}, {"command": command, "actor": other}, {}):
            with self.assertRaises(StrategyConflict):
                self.draft(**kwargs)
        self.assertEqual(StrategyPolicyEvent.objects.count(), 1)

    def test_bad_command_envelopes_are_rejected_before_handler(self):
        for kwargs in ({"command_uuid": "bad"}, {"expected_revision": True}, {"expected_revision": -1},
                       {"operation": "UNKNOWN"}, {"intent": {}}, {"intent": {"value": 1.1}}):
            envelope = dict(actor=self.manager, command_uuid=uuid4(), operation="SAVE_DRAFT", expected_revision=0,
                            intent={"config": neutral_config()}, handler=lambda _: self.fail("Invalid envelope reached handler"))
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                run_strategy_command(**{**envelope, **kwargs})
        self.assertFalse(StrategyPolicyEvent.objects.exists())

    def test_cas_targets_head_revision_directly_and_advances_successively(self):
        with CaptureQueriesContext(connection) as queries:
            self.draft()
            self.draft(revision=1)
        updates = [q["sql"] for q in queries if q["sql"].lstrip().startswith('UPDATE "management_strategypolicy"')]
        self.assertEqual(len(updates), 2)
        for sql in updates:
            self.assertIn('"management_strategypolicy"."revision" =', sql.split("WHERE", 1)[1])
        self.assertEqual(StrategyPolicy.objects.get().revision, 2)

    def test_mismatched_comparison_candidate_rolls_back(self):
        comparison = self.comparison()
        version = self.version()
        with self.assertRaises(ValidationError):
            run_strategy_command(actor=self.manager, command_uuid=uuid4(), operation="PUBLISH", expected_revision=0,
                                 intent={"candidate": version.pk},
                                 handler=lambda _: StrategyEffect(version, {"registered": True}, comparison))
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.revision, 0)
        self.assertIsNone(self.policy.active_version_id)
        self.assertFalse(StrategyPolicyEvent.objects.exists())

    def test_replay_rechecks_current_manager_authority(self):
        command = uuid4()
        self.draft(command=command)
        get_user_model().objects.filter(pk=self.manager.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.draft(command=command)

    def test_failure_rolls_back_version_head_and_receipt(self):
        def handler(policy):
            return StrategyEffect(self.version(), {})
        with self.assertRaises(ValidationError):
            self.draft(handler=handler)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.revision, 0)
        self.assertFalse(StrategyPolicyVersion.objects.exists())
        self.assertFalse(StrategyPolicyEvent.objects.exists())

    def test_failed_first_command_also_rolls_back_head_initialization(self):
        # Delete only fixture setup via the test framework's trusted low-level path.
        models.QuerySet.delete(StrategyPolicy.objects.all())
        with self.assertRaises(ValidationError):
            self.draft(handler=lambda p: None)
        self.assertFalse(StrategyPolicy.objects.exists())

    def test_preview_keeps_revision_and_pointers_unchanged(self):
        version = self.version()
        comparison = self.comparison(version)
        result = run_strategy_command(
            actor=self.manager, command_uuid=uuid4(), operation="PREVIEW", expected_revision=0,
            intent={"version": version.pk}, handler=lambda _: StrategyEffect(version, {"comparison": comparison.pk}, comparison),
        )
        self.policy.refresh_from_db()
        self.assertEqual(result.event.applied_revision, 0)
        self.assertEqual(self.policy.revision, 0)
        self.assertIsNone(self.policy.active_version_id)
        self.assertIsNone(self.policy.draft_version_id)

    def test_database_unique_command_and_revision_constraints(self):
        first = self.draft().event
        values = {field.attname: getattr(first, field.attname) for field in first._meta.fields if not field.primary_key}
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet.bulk_create(StrategyPolicyEvent.objects.all(), [StrategyPolicyEvent(**values)])
        values["command_uuid"] = uuid4()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet.bulk_create(StrategyPolicyEvent.objects.all(), [StrategyPolicyEvent(**values)])


@skipUnless(connection.vendor == "postgresql", "Requires separate PostgreSQL transactions")
class StrategyConcurrencyTests(StrategyFixture, TransactionTestCase):
    def compete(self, same_command=False, first_use=False):
        if first_use:
            models.QuerySet.delete(StrategyPolicy.objects.all())
        barrier = Barrier(2)
        command = uuid4()
        def worker():
            db = connections["default"]
            try:
                with db.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid(), current_database(), current_setting('transaction_isolation')")
                    pid, name, isolation = cursor.fetchone()
                self.assertEqual(name, connection.settings_dict["NAME"])
                self.assertEqual(isolation, "read committed")
                barrier.wait(timeout=15)
                try:
                    result = self.draft(command=command if same_command else uuid4())
                    return pid, "replay" if result.replayed else "applied"
                except StrategyConflict:
                    return pid, "conflict"
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(len({pid for pid, _ in results}), 2)
        self.assertEqual(sorted(state for _, state in results), ["applied", "replay" if same_command else "conflict"])
        self.assertEqual(StrategyPolicy.objects.get().revision, 1)
        self.assertEqual(StrategyPolicyVersion.objects.count(), 1)
        self.assertEqual(StrategyPolicyEvent.objects.count(), 1)

    def test_same_revision_has_one_winner_and_no_lost_update(self):
        self.compete()

    def test_concurrent_identical_command_creates_one_result(self):
        self.compete(same_command=True)

    def test_concurrent_first_use_safely_initializes_one_head(self):
        self.compete(first_use=True)


class StrategyMigrationTests(TransactionTestCase):
    def test_additive_schema_and_round_trip_preserve_existing_rows(self):
        executor = MigrationExecutor(connection)
        final = executor.loader.graph.leaf_nodes()
        migration = executor.loader.disk_migrations[("management", "0001_initial")]
        self.assertTrue(all(type(op).__name__ in {"CreateModel", "AddField", "AddConstraint"} for op in migration.operations))
        customer = Customer.objects.create(customer_code="MIG-STRATEGY", name="مشتری محفوظ")
        before = list(Customer.objects.filter(pk=customer.pk).values())
        try:
            executor.migrate([("management", None)])
            self.assertNotIn(StrategyPolicy._meta.db_table, connection.introspection.table_names())
            MigrationExecutor(connection).migrate(final)
            self.assertEqual(before, list(Customer.objects.filter(pk=customer.pk).values()))
            for model in (StrategyPolicy, StrategyPolicyVersion, StrategyComparison, StrategyPolicyEvent):
                self.assertEqual(model.objects.count(), 0)
            with connection.cursor() as cursor:
                constraints = connection.introspection.get_constraints(cursor, StrategyPolicyEvent._meta.db_table)
            for name in ("strategy_unique_command", "strategy_event_revision_step", "strategy_valid_operation"):
                self.assertIn(name, constraints)
        finally:
            MigrationExecutor(connection).migrate(final)
