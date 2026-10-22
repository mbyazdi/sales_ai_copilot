"""M-C3 service contracts; all fixtures/writes belong to disposable test DBs."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, connections, models, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.customers.models import Customer
from apps.inventory.models import Inventory
from apps.products.models import Product, ProductDemoPrice
from apps.promotions.models import Promotion
from apps.recommendations.models import CustomerRecommendation
from apps.targets.models import SalesTarget
from apps.visits.models import CustomerAssignment
from . import strategy_snapshots as adapter
from . import tests_strategy_evaluator_db as previous_fixture
from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_comparisons import create_strategy_comparison, get_strategy_comparison, recover_strategy_comparison
from .strategy_evaluator import evaluate_strategy
from .strategy_persistence import StrategyConflict, StrategyEffect, run_strategy_command
from .strategy_serialization import fingerprint, neutral_config
from .strategy_snapshots import capture_strategy_snapshot, evaluate_comparison
from .tests_strategy_evaluator import DAY, config, priority


class ComparisonFixture(TransactionTestCase):
    def setUp(self):
        previous_fixture.StrategyEvaluatorDatabaseTests.setUpTestData.__func__(type(self))
        self.manager = get_user_model().objects.create_user(username="comparison-manager", is_staff=True)
        CustomerAssignment.objects.create(customer=self.customer, salesperson=self.rep, start_date=DAY - timedelta(days=1))
        self.policy = StrategyPolicy.objects.create()
        self.proposed = StrategyPolicyVersion.objects.create(
            policy=self.policy, author=self.manager,
            config=config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                          promotion_rules=[{"promotion_id": 1, "points": 5}]),
        )
        run_strategy_command(actor=self.manager, command_uuid=uuid4(), operation="SAVE_DRAFT", expected_revision=0,
                             intent={"version": self.proposed.pk}, handler=lambda _: StrategyEffect(self.proposed, {"draft": self.proposed.pk}))
        self.policy.refresh_from_db()

    def context(self, **kwargs):
        return {"actor": self.manager, "customer_id": self.customer.pk, "salesperson_id": self.rep.pk,
                "proposed_version_id": self.proposed.pk, "expected_revision": self.policy.revision, "evaluation_date": DAY, **kwargs}

    def capture(self, **kwargs):
        return capture_strategy_snapshot(**self.context(**kwargs))

    def create(self, captured=None, command_uuid=None, **kwargs):
        captured = captured or self.capture()
        return create_strategy_comparison(command_uuid=command_uuid or uuid4(), accepted_source_fingerprint=captured.source_fingerprint,
                                          **self.context(**kwargs))

    def source_rows(self):
        return previous_fixture.StrategyEvaluatorDatabaseTests.business_rows(self)


class StrategySnapshotTests(ComparisonFixture):
    def test_read_capture_is_deterministic_bounded_and_has_no_writes(self):
        before = self.source_rows()
        with CaptureQueriesContext(connection) as queries:
            first = self.capture()
        self.assertLessEqual(len(queries), 25)
        self.assertTrue(all(not query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for query in queries))
        self.assertEqual(first, self.capture())
        self.assertEqual(first.source_fingerprint, fingerprint(first.as_dict()))
        self.assertEqual(before, self.source_rows())
        self.assertFalse(StrategyComparison.objects.exists())
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="PREVIEW").count(), 0)
        if connection.vendor == "postgresql":
            self.assertTrue(any("REPEATABLE READ, READ ONLY" in query["sql"] for query in queries))

    def test_active_and_proposed_share_exact_facts_without_rescoring_base(self):
        captured = self.capture()
        outputs = evaluate_comparison(captured)
        self.assertEqual(outputs["before"]["after_ids"], [101, 102, 103, 104])
        self.assertEqual(outputs["after"]["after_ids"], [103, 101, 102, 104])
        self.assertEqual(outputs["before"]["before_ids"], outputs["after"]["before_ids"])
        before = {row["source"]["recommendation_id"]: row["source"] for row in outputs["before"]["rows"]}
        after = {row["source"]["recommendation_id"]: row["source"] for row in outputs["after"]["rows"]}
        self.assertEqual(before, after)
        self.assertEqual(after[103]["base_score"], "70.0000")
        self.assertIn('"promotion_score":20.0', after[103]["source_evidence_json"])
        self.assertTrue(outputs["simulation_only"])
        self.assertIsNone(outputs["revenue_uplift"])

    def test_neutral_policy_parity_and_non_neutral_active_baseline(self):
        neutral = StrategyPolicyVersion.objects.create(policy=self.policy, author=self.manager, config=neutral_config())
        # Fixture-only representation of an already active policy, not a publish service.
        models.QuerySet.update(StrategyPolicy.objects.filter(pk=1), active_version_id=neutral.pk, draft_version_id=neutral.pk)
        captured = self.capture(proposed_version_id=neutral.pk)
        outputs = evaluate_comparison(captured)
        self.assertEqual(outputs["before"]["after_ids"], outputs["after"]["after_ids"])
        models.QuerySet.update(StrategyPolicy.objects.filter(pk=1), active_version_id=self.proposed.pk)
        outputs = evaluate_comparison(self.capture(proposed_version_id=neutral.pk))
        self.assertEqual(outputs["before"]["after_ids"], [103, 101, 102, 104])
        self.assertEqual(outputs["after"]["after_ids"], [101, 102, 103, 104])

    def test_target_promotion_qualification_and_current_quote_annotations(self):
        captured = self.capture()
        row = next(row for row in evaluate_strategy(captured.snapshot).rows if row.source.product_id == 3)
        self.assertEqual((row.target.points, row.promotion.points), (Decimal("2.50"), Decimal("5.00")))
        quote = captured.as_dict()["quotes"]["3"]["quote"]
        self.assertEqual((quote["base_unit_price"], quote["final_unit_price"], quote["currency"]), ("100", "90", "TOMAN"))
        Promotion.objects.filter(pk=1).update(minimum_quantity=2)
        row = next(row for row in evaluate_strategy(self.capture().snapshot).rows if row.source.product_id == 3)
        self.assertEqual(row.promotion.points, Decimal(0))
        self.assertIn("PROMOTION_QUANTITY_ONE_INELIGIBLE", [reason.code for reason in row.promotion.reasons])
        SalesTarget.objects.filter(pk=1).update(target_unit="MSU")
        row = next(row for row in evaluate_strategy(self.capture().snapshot).rows if row.source.product_id == 3)
        self.assertEqual(row.target.points, Decimal(0))

    def test_unknown_zero_stock_missing_zero_and_invalid_price_remain_distinct(self):
        Inventory.objects.filter(product_id=1).delete()
        Inventory.objects.filter(product_id=2).update(available_quantity=2, reserved_quantity=2)
        ProductDemoPrice.objects.filter(product_id=3).delete()
        ProductDemoPrice.objects.filter(product_id=4).update(base_price=Decimal(0))
        captured = self.capture()
        facts = {row.product_id: row.commercial for row in captured.snapshot.recommendations}
        self.assertIsNone(facts[1].sellable_quantity)
        self.assertEqual(facts[2].sellable_quantity, 0)
        self.assertEqual(facts[3].pricing_reason, "MISSING_PRICE")
        self.assertTrue(facts[4].can_add)
        self.assertEqual(captured.as_dict()["quotes"]["4"]["quote"]["final_unit_price"], "0")
        ProductDemoPrice.objects.filter(product_id=4).update(base_price=Decimal("1.50"))
        facts = {row.product_id: row.commercial for row in self.capture().snapshot.recommendations}
        self.assertEqual(facts[4].pricing_reason, "FRACTIONAL_BASE_PRICE")

    def test_manager_access_does_not_require_salesperson_impersonation(self):
        self.assertFalse(hasattr(self.manager, "salesperson_profile"))
        self.assertEqual(self.capture().snapshot.salesperson_id, self.rep.pk)
        for actor in (AnonymousUser(), get_user_model().objects.create_user(username="nonmanager")):
            with self.assertRaises(PermissionDenied):
                self.capture(actor=actor)
        get_user_model().objects.filter(pk=self.manager.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            self.capture()

    def test_inactive_unassigned_wrong_customer_and_outside_assignment_are_rejected(self):
        unassigned = Customer.objects.create(customer_code="UNASSIGNED-CMP", name="مشتری بدون تخصیص")
        with self.assertRaises(PermissionDenied):
            self.capture(customer_id=unassigned.pk)
        with self.assertRaises(PermissionDenied):
            self.capture(customer_id=999999)
        with self.assertRaises(PermissionDenied):
            self.capture(salesperson_id=999999)
        with self.assertRaises(PermissionDenied):
            self.capture(evaluation_date=DAY - timedelta(days=2))
        CustomerAssignment.objects.update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.capture()

    def test_empty_shortlist_and_missing_targets_promotions_are_known_none(self):
        CustomerRecommendation.objects.update(is_active=False)
        captured = self.capture()
        self.assertEqual(captured.snapshot.recommendations, ())
        self.assertEqual(evaluate_comparison(captured)["after"]["after_ids"], [])

    def test_context_policy_revision_missing_reference_and_nested_capture_fail_closed(self):
        with self.assertRaises(StrategyConflict):
            self.capture(expected_revision=0)
        with self.assertRaises(StrategyConflict):
            self.capture(proposed_version_id=999999)
        with self.assertRaises(ValidationError):
            self.capture(evaluation_date="2026-10-16")
        with transaction.atomic(), self.assertRaises(ValidationError):
            self.capture()
        # A referenced promotion removed administratively is not assumed zero.
        Promotion.objects.all().delete()
        with self.assertRaises(ValidationError):
            self.capture()


class StrategyComparisonTests(ComparisonFixture):
    def test_explicit_comparison_writes_only_comparison_event_and_preserves_head(self):
        captured = self.capture()
        before, head = self.source_rows(), list(StrategyPolicy.objects.values())
        result = self.create(captured)
        comparison = result.event.comparison
        self.assertFalse(result.replayed)
        self.assertEqual(comparison.inputs["source_fingerprint"], captured.source_fingerprint)
        self.assertEqual(comparison.inputs["capture"], captured.as_dict())
        self.assertEqual(comparison.outputs, evaluate_comparison(captured))
        self.assertEqual(before, self.source_rows())
        self.assertEqual(head, list(StrategyPolicy.objects.values()))
        self.assertEqual(StrategyComparison.objects.count(), 1)
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="PREVIEW").count(), 1)

    def test_source_and_assignment_changes_reject_new_commands_without_evidence(self):
        captured = self.capture()
        CustomerAssignment.objects.update(end_date=DAY + timedelta(days=1))
        with self.assertRaises(StrategyConflict):
            self.create(captured)  # Still eligible, but the accepted assignment evidence changed.
        captured = self.capture()
        Inventory.objects.filter(product_id=3).update(available_quantity=1)
        with self.assertRaises(StrategyConflict):
            self.create(captured)
        CustomerAssignment.objects.update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.create(captured)
        self.assertFalse(StrategyComparison.objects.exists())
        self.assertFalse(StrategyPolicyEvent.objects.filter(operation="PREVIEW").exists())

    def test_replay_and_recovery_return_frozen_success_after_live_facts_change(self):
        captured, command = self.capture(), uuid4()
        original = self.create(captured, command)
        stored = get_strategy_comparison(actor=self.manager, comparison_id=original.event.comparison_id)
        CustomerRecommendation.objects.update(reason="دلیل جدید")
        Inventory.objects.update(available_quantity=0)
        CustomerAssignment.objects.update(is_active=False)
        models.QuerySet.update(StrategyPolicy.objects.filter(pk=1), revision=2)
        connection.close()  # Fresh physical PostgreSQL connection; no process-local receipt cache.
        replay = self.create(captured, command)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.event.result, original.event.result)
        self.assertEqual(get_strategy_comparison(actor=self.manager, comparison_id=original.event.comparison_id), stored)
        recovered = recover_strategy_comparison(actor=self.manager, command_uuid=command)
        self.assertEqual(recovered["comparison"], stored)
        self.assertEqual(StrategyComparison.objects.count(), 1)
        with self.assertRaises(ValidationError):
            original.event.comparison.save()

    def test_conflicting_uuid_actor_and_unauthorized_reads_are_rejected(self):
        captured, command = self.capture(), uuid4()
        result = self.create(captured, command)
        other = get_user_model().objects.create_user(username="other-manager", is_staff=True)
        with self.assertRaises(StrategyConflict):
            self.create(captured, command, evaluation_date=DAY + timedelta(days=1))
        with self.assertRaises(StrategyConflict):
            self.create(captured, command, actor=other)
        with self.assertRaises(PermissionDenied):
            recover_strategy_comparison(actor=other, command_uuid=command)
        with self.assertRaises(PermissionDenied):
            get_strategy_comparison(actor=AnonymousUser(), comparison_id=result.event.comparison_id)

    def test_readonly_recovery_absence_and_malformed_envelope(self):
        before = self.source_rows()
        with CaptureQueriesContext(connection) as queries:
            self.assertIsNone(recover_strategy_comparison(actor=self.manager, command_uuid=uuid4()))
        self.assertTrue(all(not row["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for row in queries))
        with self.assertRaises(ValidationError):
            recover_strategy_comparison(actor=self.manager, command_uuid=None)
        with self.assertRaises(ValidationError):
            create_strategy_comparison(**self.context(), command_uuid=uuid4(), accepted_source_fingerprint="bad")
        self.assertEqual(before, self.source_rows())

    def test_result_validation_failure_rolls_back_comparison_and_event(self):
        captured = self.capture()
        before = self.source_rows()
        with patch("apps.management.strategy_comparisons.StrategyPolicyEvent.clean", side_effect=ValidationError("injected")):
            with self.assertRaises(ValidationError):
                self.create(captured)
        self.assertFalse(StrategyComparison.objects.exists())
        self.assertFalse(StrategyPolicyEvent.objects.filter(operation="PREVIEW").exists())
        self.assertEqual(before, self.source_rows())

    def test_tampered_stored_digest_is_detected_without_repair(self):
        result = self.create()
        # Privileged corruption simulation only in this disposable fixture.
        models.QuerySet.update(StrategyComparison.objects.filter(pk=result.event.comparison_id), output_digest="0" * 64)
        with self.assertRaises(ValidationError):
            get_strategy_comparison(actor=self.manager, comparison_id=result.event.comparison_id)
        self.assertEqual(StrategyComparison.objects.get().output_digest, "0" * 64)


@skipUnless(connection.vendor == "postgresql", "Real PostgreSQL MVCC and independent connections required")
class StrategySnapshotPostgresTests(ComparisonFixture):
    def test_capture_retains_one_mvcc_image_during_source_writes(self):
        paused, resume = Event(), Event()
        original = adapter._rows
        def read(queryset, *args, **kwargs):
            result = original(queryset, *args, **kwargs)
            if queryset.model is Product and args == ("id", "brand_id", "category_id", "product_group"):
                paused.set()
                self.assertTrue(resume.wait(15))
            return result
        def worker():
            try:
                return self.capture()
            finally:
                connections["default"].close()
        with patch.object(adapter, "_rows", side_effect=read), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            self.assertTrue(paused.wait(15))
            try:
                with transaction.atomic():
                    Inventory.objects.filter(product_id=3).update(available_quantity=2)
                    SalesTarget.objects.filter(pk=1).update(actual_value=100)
            finally:
                resume.set()
            captured = future.result(timeout=15)
        self.assertEqual(next(row for row in captured.snapshot.recommendations if row.product_id == 3).commercial.sellable_quantity, 10)
        self.assertEqual(captured.snapshot.targets[0].actual_value, Decimal(50))
        with self.assertRaises(StrategyConflict):
            self.create(captured)

    def test_concurrent_identical_previews_replay_without_duplicate_evidence(self):
        captured, command, start, pids = self.capture(), uuid4(), Barrier(2), Queue()
        def worker():
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                    pids.put(pid)
                start.wait(timeout=15)
                result = self.create(captured, command)
                return pid, result.event.pk, result.replayed
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                StrategyPolicy.objects.select_for_update().get(pk=1)
                futures = [pool.submit(worker) for _ in range(2)]
                worker_pids = [pids.get(timeout=15) for _ in range(2)]
                deadline = monotonic() + 15
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT pid,wait_event_type FROM pg_stat_activity WHERE pid=ANY(%s)", [worker_pids])
                        states = cursor.fetchall()
                    if len(states) == 2 and all(state == "Lock" for _, state in states):
                        break
                    sleep(0.01)
                else:
                    self.fail("Both preview snapshots must predate either successful comparison")
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(len({row[0] for row in results}), 2)
        self.assertEqual(len({row[1] for row in results}), 1)
        self.assertEqual(sorted(row[2] for row in results), [False, True])
        self.assertEqual(StrategyComparison.objects.count(), 1)

    def test_concurrent_revision_change_conflicts_and_rolls_back(self):
        captured, pids = self.capture(), Queue()
        def worker():
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                try:
                    self.create(captured)
                except StrategyConflict:
                    return "conflict"
                return "unexpected success"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                StrategyPolicy.objects.select_for_update().get(pk=1)
                future = pool.submit(worker)
                pid = pids.get(timeout=15)
                deadline = monotonic() + 15
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", [pid])
                        state = cursor.fetchone()
                    if state and state[0] == "Lock":
                        break
                    sleep(0.01)
                else:
                    self.fail("Preview never waited for the locked policy head")
                next_version = StrategyPolicyVersion.objects.create(policy=self.policy, author=self.manager, config=neutral_config())
                run_strategy_command(actor=self.manager, command_uuid=uuid4(), operation="SAVE_DRAFT", expected_revision=1,
                                     intent={"new_version": next_version.pk}, handler=lambda _: StrategyEffect(next_version, {"draft": next_version.pk}))
            self.assertEqual(future.result(timeout=15), "conflict")
        self.assertFalse(StrategyComparison.objects.exists())

    @contextmanager
    def runtime(self):
        credentials = settings.STRATEGY_TEST_RUNTIME
        db = connections["default"]
        self.assertEqual(db.settings_dict["NAME"], credentials["NAME"])
        prior = {key: db.settings_dict[key] for key in ("USER", "PASSWORD")}
        db.close()
        db.settings_dict.update({key: credentials[key] for key in prior})
        try:
            with db.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_user")
                self.assertEqual(cursor.fetchone(), (credentials["NAME"], credentials["USER"]))
            yield
        finally:
            db.close()
            db.settings_dict.update(prior)

    def test_real_least_privilege_runtime_captures_compares_replays_and_recovers(self):
        before = self.source_rows()
        with self.runtime():
            captured, command = self.capture(), uuid4()
            result = self.create(captured, command)
            self.assertTrue(self.create(captured, command).replayed)
            recovered = recover_strategy_comparison(actor=self.manager, command_uuid=command)
            self.assertEqual(recovered["result"], result.event.result)
            self.assertEqual(get_strategy_comparison(actor=self.manager, comparison_id=result.event.comparison_id)["outputs"], evaluate_comparison(captured))
        self.assertEqual(before, self.source_rows())

    def test_runtime_cannot_modify_sources_history_publish_or_schema(self):
        self.create()
        statements = (
            "UPDATE products_product SET name=name WHERE id=1",
            "UPDATE products_productdemoprice SET base_price=0 WHERE product_id=1",
            "UPDATE recommendations_customerrecommendation SET score=0 WHERE id=101",
            "UPDATE targets_salestarget SET actual_value=0 WHERE id=1",
            "UPDATE management_strategycomparison SET source_version='bad'",
            "DELETE FROM management_strategypolicyevent",
            "UPDATE management_strategypolicy SET active_version_id=NULL",
            "CREATE TABLE public.mc3_forbidden(id integer)",
        )
        before = self.source_rows()
        with self.runtime():
            for statement in statements:
                with self.subTest(statement=statement), self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(statement)
        self.assertEqual(before, self.source_rows())
