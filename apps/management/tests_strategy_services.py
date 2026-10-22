"""M-C4 internal commands; all write fixtures belong to disposable databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import json
from queue import Queue
from threading import Barrier
from time import monotonic, sleep
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, connections, models, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.inventory.models import Inventory
from apps.products.models import ProductDemoPrice
from apps.promotions.models import Promotion
from apps.recommendations.models import CustomerRecommendation
from apps.targets.models import SalesTarget
from apps.visits.models import CustomerAssignment
from . import tests_strategy_evaluator_db as fixtures
from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_comparisons import create_strategy_comparison
from .strategy_persistence import StrategyConflict
from .strategy_serialization import configuration_fingerprint, fingerprint, neutral_config
from .strategy_services import (
    create_strategy_draft, prepare_strategy_rollback, publish_strategy, recover_strategy_command, rollback_strategy,
)
from .strategy_snapshots import capture_strategy_snapshot
from .tests_strategy_evaluator import DAY, config, priority


class ServiceFixture(TransactionTestCase):
    def setUp(self):
        fixtures.StrategyEvaluatorDatabaseTests.setUpTestData.__func__(type(self))
        self.manager = get_user_model().objects.create_user(username="publication-manager", is_staff=True)
        CustomerAssignment.objects.create(customer=self.customer, salesperson=self.rep, start_date=DAY - timedelta(days=1))

    def head(self):
        return StrategyPolicy.objects.get(pk=1)

    def draft(self, rules=None, **kwargs):
        revision = StrategyPolicy.objects.filter(pk=1).values_list("revision", flat=True).first() or 0
        return create_strategy_draft(**{"actor": self.manager, "command_uuid": uuid4(), "expected_revision": revision,
                                        "config": rules if rules is not None else config(priority_rules=[priority("PRODUCT", 3, 20)]), **kwargs})

    def preview(self):
        head = self.head()
        context = {"actor": self.manager, "customer_id": self.customer.pk, "salesperson_id": self.rep.pk,
                   "proposed_version_id": head.draft_version_id, "expected_revision": head.revision, "evaluation_date": DAY}
        captured = capture_strategy_snapshot(**context)
        return create_strategy_comparison(**context, command_uuid=uuid4(), accepted_source_fingerprint=captured.source_fingerprint).event.comparison

    def envelope(self, comparison, **kwargs):
        return {"actor": self.manager, "command_uuid": uuid4(), "expected_revision": self.head().revision,
                "draft_version_id": comparison.after_version_id, "comparison_id": comparison.pk,
                "accepted_comparison_digest": comparison.output_digest, **kwargs}

    def publish(self):
        return publish_strategy(**self.envelope(self.preview()))

    def counts(self):
        return [model.objects.count() for model in (StrategyPolicy, StrategyPolicyVersion, StrategyComparison, StrategyPolicyEvent)]

    def business_digest(self):
        # Include sessions, request/receipt/snapshot/history tables as well as
        # recommendation/pricing/stock. No underlying row values are logged.
        return fingerprint({model._meta.label_lower: json.dumps(list(model.objects.order_by("pk").values()),
                            default=str, sort_keys=True, ensure_ascii=False)
                            for model in apps.get_models() if model not in
                            (StrategyPolicy, StrategyPolicyVersion, StrategyComparison, StrategyPolicyEvent)})


class StrategyServiceTests(ServiceFixture):
    def test_first_draft_initializes_neutral_head_without_activation(self):
        self.assertFalse(StrategyPolicy.objects.exists())
        result = self.draft()
        self.assertEqual(self.counts(), [1, 1, 0, 1])
        self.assertIsNone(self.head().active_version_id)
        self.assertEqual(self.head().revision, 1)
        self.assertEqual(self.head().draft_version_id, result.event.version_id)
        self.assertIsNone(result.event.version.parent_id)
        self.assertEqual(result.event.version.config_hash, configuration_fingerprint(result.event.version.config))
        with self.assertRaises(ValidationError):
            result.event.version.save()

    def test_config_normalization_specificity_zero_and_semantic_retry(self):
        rules = [priority("PRODUCT", 1, 0), priority("BRAND", 11, 19), priority("CATEGORY", 21, 20)]
        command = uuid4()
        first = self.draft(config(priority_rules=rules), command_uuid=command)
        replay = self.draft(config(priority_rules=list(reversed(rules))), command_uuid=command, expected_revision=0)
        self.assertTrue(replay.replayed)
        self.assertEqual(first.event.pk, replay.event.pk)
        comparison = self.preview()
        row = next(row for row in comparison.outputs["after"]["rows"] if row["source"]["product_id"] == 1)
        self.assertEqual(row["priority"]["points"], "0.00")

    def test_invalid_config_bounds_duplicates_unknown_references_have_zero_partial_writes(self):
        cases = [config(target_weight=True), config(target_weight=6), config(extra=1),
                 config(priority_rules=[priority("PRODUCT", 1, 21)]),
                 config(priority_rules=[priority("PRODUCT", 1, 1)] * 2),
                 config(priority_rules=[priority("PRODUCT", 999999, 1)]),
                 config(promotion_rules=[{"promotion_id": 999999, "points": 1}]),
                 config(promotion_rules=[{"promotion_id": 1, "points": 6}])]
        for rules in cases:
            with self.subTest(rules=rules), self.assertRaises(ValidationError):
                self.draft(rules)
            self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_draft_revision_conflict_and_uuid_conflict_preserve_old_versions(self):
        command = uuid4()
        first = self.draft(command_uuid=command)
        before = self.counts()
        with self.assertRaises(StrategyConflict):
            self.draft(neutral_config(), expected_revision=0)
        with self.assertRaises(StrategyConflict):
            self.draft(neutral_config(), expected_revision=0, command_uuid=command)
        self.assertEqual(before, self.counts())
        second = self.draft(neutral_config())
        self.assertNotEqual(first.event.version_id, second.event.version_id)
        self.assertEqual(self.head().revision, 2)

    def test_publish_updates_only_head_and_audit_with_exact_comparison(self):
        self.draft()
        comparison = self.preview()
        before, counts = self.business_digest(), self.counts()
        result = publish_strategy(**self.envelope(comparison))
        self.assertFalse(result.replayed)
        self.assertEqual(self.head().active_version_id, comparison.after_version_id)
        self.assertIsNone(self.head().draft_version_id)
        self.assertEqual(self.head().revision, 2)
        self.assertEqual(self.counts(), [counts[0], counts[1], counts[2], counts[3] + 1])
        self.assertEqual(before, self.business_digest())
        self.assertEqual(result.event.comparison_id, comparison.pk)
        self.assertEqual(result.event.result["application_scope"], "FRESH_SELLING_CONTEXTS_ONLY")

    def test_preview_is_required_and_unknown_comparison_fails_without_mutation(self):
        draft = self.draft()
        before = self.counts()
        with self.assertRaises(StrategyComparison.DoesNotExist):
            publish_strategy(actor=self.manager, command_uuid=uuid4(), expected_revision=1,
                             draft_version_id=draft.event.version_id, comparison_id=999999, accepted_comparison_digest="0" * 64)
        self.assertEqual(before, self.counts())
        self.assertIsNone(self.head().active_version_id)

    def test_bad_or_altered_accepted_digest_rejects(self):
        self.draft()
        comparison = self.preview()
        for digest in (None, "bad", "0" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                publish_strategy(**self.envelope(comparison, accepted_comparison_digest=digest))
        self.assertIsNone(self.head().active_version_id)

    def test_changed_price_and_inventory_reject_then_require_new_preview(self):
        self.draft()
        comparison = self.preview()
        ProductDemoPrice.objects.filter(product_id=1).update(base_price=101)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        comparison = self.preview()
        Inventory.objects.filter(product_id=1).update(available_quantity=1)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        self.assertIsNone(self.head().active_version_id)
        self.publish()

    def test_assignment_drift_and_removed_assignment_fail_closed(self):
        self.draft()
        comparison = self.preview()
        CustomerAssignment.objects.update(end_date=DAY + timedelta(days=1))
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        comparison = self.preview()
        CustomerAssignment.objects.update(is_active=False)
        with self.assertRaises(PermissionDenied):
            publish_strategy(**self.envelope(comparison))

    def test_unauthorized_and_fresh_manager_role_checks(self):
        self.draft()
        comparison = self.preview()
        ordinary = get_user_model().objects.create_user(username="ordinary")
        for actor in (AnonymousUser(), ordinary):
            with self.assertRaises(PermissionDenied):
                self.draft(actor=actor)
            with self.assertRaises(PermissionDenied):
                publish_strategy(**self.envelope(comparison, actor=actor))
        other = get_user_model().objects.create_user(username="other-publisher", is_staff=True)
        get_user_model().objects.filter(pk=self.manager.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            publish_strategy(**self.envelope(comparison, actor=other))  # Preview author's role drift.
        with self.assertRaises(PermissionDenied):
            publish_strategy(**self.envelope(comparison))

    def test_old_draft_and_revision_cannot_be_published(self):
        self.draft()
        comparison = self.preview()
        envelope = self.envelope(comparison)
        self.draft(neutral_config())
        with self.assertRaises(StrategyConflict):
            publish_strategy(**envelope)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**{**envelope, "expected_revision": 2})

    def test_changed_active_baseline_with_same_revision_detected(self):
        first = self.draft(neutral_config()).event.version_id
        self.publish()
        self.draft()
        comparison = self.preview()
        models.QuerySet.update(StrategyPolicy.objects.filter(pk=1), active_version_id=None)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        self.assertEqual(comparison.before_version_id, first)

    def test_tampered_comparison_or_receipt_is_not_accepted_or_repaired(self):
        self.draft()
        comparison = self.preview()
        models.QuerySet.update(StrategyComparison.objects.filter(pk=comparison.pk), output_digest="0" * 64)
        with self.assertRaises(ValidationError):
            publish_strategy(**self.envelope(comparison))
        self.assertIsNone(self.head().active_version_id)
        self.assertEqual(StrategyComparison.objects.get(pk=comparison.pk).output_digest, "0" * 64)

    def test_preview_command_evidence_is_verified(self):
        self.draft()
        comparison = self.preview()
        models.QuerySet.update(StrategyPolicyEvent.objects.filter(operation="PREVIEW"), result={"altered": True})
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        self.assertIsNone(self.head().active_version_id)

    def test_recommendation_target_and_promotion_drift_reject_publication(self):
        self.draft()
        for model, changes in ((CustomerRecommendation, {"reason": "دلیل تغییرکرده"}),
                               (SalesTarget, {"actual_value": 60}), (Promotion, {"is_active": False})):
            comparison = self.preview()
            model.objects.update(**changes)  # Controlled source change in isolated fixture only.
            with self.subTest(model=model), self.assertRaises(StrategyConflict):
                publish_strategy(**self.envelope(comparison))
            self.assertIsNone(self.head().active_version_id)

    def test_missing_stored_digests_fail_without_reconstructing_evidence(self):
        self.draft()
        comparison = self.preview()
        models.QuerySet.update(StrategyComparison.objects.filter(pk=comparison.pk), input_digest="")
        with self.assertRaises(ValidationError):
            publish_strategy(**self.envelope(comparison))
        self.assertEqual(StrategyComparison.objects.get(pk=comparison.pk).input_digest, "")
        preview = StrategyPolicyEvent.objects.get(operation="PREVIEW")
        models.QuerySet.update(StrategyPolicyEvent.objects.filter(pk=preview.pk), intent_fingerprint="")
        with self.assertRaises(ValidationError):
            recover_strategy_command(actor=self.manager, command_uuid=preview.command_uuid)
        self.assertIsNone(self.head().active_version_id)

    def test_rehashed_but_contradictory_comparison_outputs_are_rejected(self):
        self.draft()
        comparison = self.preview()
        altered = {**comparison.outputs, "revenue_uplift": "fabricated"}
        altered_digest = fingerprint({"input_digest": comparison.input_digest, "outputs": altered})
        models.QuerySet.update(StrategyComparison.objects.filter(pk=comparison.pk), outputs=altered, output_digest=altered_digest)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison, accepted_comparison_digest=altered_digest))
        self.assertIsNone(self.head().active_version_id)

    def test_missing_preview_command_fails_closed(self):
        self.draft()
        comparison = self.preview()
        models.QuerySet.delete(StrategyPolicyEvent.objects.filter(operation="PREVIEW"))
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(comparison))
        self.assertIsNone(self.head().active_version_id)

    def test_publish_replay_after_reconnect_and_changed_sources_is_exact(self):
        self.draft()
        comparison = self.preview()
        envelope = self.envelope(comparison)
        first = publish_strategy(**envelope)
        counts = self.counts()
        Inventory.objects.update(available_quantity=0)
        CustomerAssignment.objects.update(is_active=False)
        connection.close()
        replay = publish_strategy(**envelope)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.event.result, first.event.result)
        self.assertEqual(replay.event.pk, first.event.pk)
        self.assertEqual(counts, self.counts())
        self.assertEqual(recover_strategy_command(actor=self.manager, command_uuid=envelope["command_uuid"]),
                         {"operation": "PUBLISH", "result": first.event.result})

    def test_publish_uuid_conflict_and_actor_bound_recovery(self):
        self.draft()
        comparison = self.preview()
        envelope = self.envelope(comparison)
        publish_strategy(**envelope)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**{**envelope, "accepted_comparison_digest": "0" * 64})
        other = get_user_model().objects.create_user(username="other-reader", is_staff=True)
        with self.assertRaises(PermissionDenied):
            recover_strategy_command(actor=other, command_uuid=envelope["command_uuid"])

    def test_rollback_new_version_preview_publish_and_neutral_preserve_history(self):
        old = self.draft(neutral_config()).event.version
        self.publish()
        self.draft()
        self.publish()
        history = list(StrategyPolicyVersion.objects.values())
        before = self.business_digest()
        prepared = prepare_strategy_rollback(actor=self.manager, command_uuid=uuid4(), expected_revision=4, target_version_id=old.pk)
        clone = prepared.event.version
        self.assertNotEqual(old.pk, clone.pk)
        self.assertEqual(clone.parent_id, old.pk)
        self.assertEqual(clone.config_hash, old.config_hash)
        self.assertEqual(list(StrategyPolicyVersion.objects.filter(pk__in=[v["id"] for v in history]).values()), history)
        comparison = self.preview()
        envelope = self.envelope(comparison)
        result = rollback_strategy(**envelope)
        self.assertEqual(self.head().active_version_id, clone.pk)
        self.assertEqual(result.event.operation, "ROLLBACK")
        self.assertTrue(rollback_strategy(**envelope).replayed)
        neutral = prepare_strategy_rollback(actor=self.manager, command_uuid=uuid4(), expected_revision=6, target_version_id=None)
        self.assertIsNone(neutral.event.version.parent_id)
        self.assertEqual(neutral.event.version.config, neutral_config())
        rollback_strategy(**self.envelope(self.preview()))
        self.assertEqual(self.head().active_version_id, neutral.event.version_id)
        self.assertEqual(before, self.business_digest())

    def test_rollback_preparation_replay_and_unpublished_target_rejection(self):
        draft = self.draft()
        with self.assertRaises(StrategyConflict):
            prepare_strategy_rollback(actor=self.manager, command_uuid=uuid4(), expected_revision=1, target_version_id=draft.event.version_id)
        command = uuid4()
        first = prepare_strategy_rollback(actor=self.manager, command_uuid=command, expected_revision=1, target_version_id=None)
        replay = prepare_strategy_rollback(actor=self.manager, command_uuid=command, expected_revision=1, target_version_id=None)
        self.assertTrue(replay.replayed)
        self.assertEqual(first.event.version_id, replay.event.version_id)

    def test_normal_publish_and_rollback_cannot_be_relabelled(self):
        self.draft()
        comparison = self.preview()
        with self.assertRaises(StrategyConflict):
            rollback_strategy(**self.envelope(comparison))
        prepare_strategy_rollback(actor=self.manager, command_uuid=uuid4(), expected_revision=1, target_version_id=None)
        with self.assertRaises(StrategyConflict):
            publish_strategy(**self.envelope(self.preview()))

    def test_failure_after_pointer_update_rolls_back_all_command_effects(self):
        self.draft()
        comparison = self.preview()
        head, counts, before = list(StrategyPolicy.objects.values()), self.counts(), self.business_digest()
        def failed_save(*args, **kwargs):
            self.assertEqual(self.head().revision, 2)  # CAS has already run inside the transaction.
            raise ValidationError("injected")
        with patch.object(StrategyPolicyEvent, "save", side_effect=failed_save):
            with self.assertRaises(ValidationError):
                publish_strategy(**self.envelope(comparison))
        self.assertEqual(head, list(StrategyPolicy.objects.values()))
        self.assertEqual(counts, self.counts())
        self.assertEqual(before, self.business_digest())

    def test_new_draft_failure_rolls_back_initial_head_and_version(self):
        with patch.object(StrategyPolicyEvent, "clean", side_effect=ValidationError("injected")):
            with self.assertRaises(ValidationError):
                self.draft()
        self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_read_only_recovery_absence_and_invalid_envelopes(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertIsNone(recover_strategy_command(actor=self.manager, command_uuid=uuid4()))
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        for command in (None, "not-a-uuid"):
            with self.assertRaises(ValidationError):
                self.draft(command_uuid=command)
            with self.assertRaises(ValidationError):
                recover_strategy_command(actor=self.manager, command_uuid=command)
        with transaction.atomic(), self.assertRaises(ValidationError):
            self.draft()
        self.assertEqual(self.counts(), [0, 0, 0, 0])


@skipUnless(connection.vendor == "postgresql", "PostgreSQL independent connections/least-privilege roles required")
class StrategyPublicationPostgresTests(ServiceFixture):
    def concurrent_publish(self, identical):
        self.draft()
        comparison = self.preview()
        first = self.envelope(comparison)
        envelopes = [first, first if identical else {**first, "command_uuid": uuid4()}]
        barrier, pids = Barrier(2), Queue()
        def worker(envelope):
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                barrier.wait(timeout=15)
                try:
                    result = publish_strategy(**envelope)
                    return result.event.pk, result.replayed
                except StrategyConflict:
                    return "conflict"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                StrategyPolicy.objects.select_for_update().get(pk=1)
                futures = [pool.submit(worker, e) for e in envelopes]
                worker_pids = [pids.get(timeout=15) for _ in range(2)]
                self.assertEqual(len(set(worker_pids)), 2)
                deadline = monotonic() + 15
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid=ANY(%s)", [worker_pids])
                        states = cursor.fetchall()
                    if len(states) == 2 and all(row[0] == "Lock" for row in states):
                        break
                    sleep(0.01)
                else:
                    self.fail("Both publication snapshots must wait before either command commits")
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(self.head().revision, 2)
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="PUBLISH").count(), 1)
        return results

    def test_concurrent_different_commands_have_one_publication_and_one_conflict(self):
        results = self.concurrent_publish(False)
        self.assertEqual(results.count("conflict"), 1)

    def test_concurrent_identical_commands_recover_exact_committed_result(self):
        results = self.concurrent_publish(True)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [False, True])

    @contextmanager
    def runtime(self):
        db, credentials = connections["default"], settings.STRATEGY_PUBLICATION_RUNTIME
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

    def test_separate_publication_role_creates_previews_publishes_and_rolls_back(self):
        before = self.business_digest()
        with self.runtime():
            self.draft()
            self.publish()
            prepared = prepare_strategy_rollback(actor=self.manager, command_uuid=uuid4(), expected_revision=2, target_version_id=None)
            result = rollback_strategy(**self.envelope(self.preview()))
            self.assertEqual(result.event.version_id, prepared.event.version_id)
        self.assertEqual(before, self.business_digest())

    def test_runtime_reference_history_and_ddl_writes_denied(self):
        self.draft()
        self.publish()
        before = self.business_digest()
        with self.runtime():
            for statement in (
                "UPDATE products_productdemoprice SET base_price=0", "UPDATE inventory_inventory SET available_quantity=0",
                "UPDATE recommendations_customerrecommendation SET score=0", "UPDATE targets_salestarget SET actual_value=0",
                "UPDATE management_strategypolicyversion SET config_hash='bad'", "DELETE FROM management_strategycomparison",
                "UPDATE management_strategypolicyevent SET result='{}'", "DELETE FROM management_strategypolicy",
                "CREATE TABLE public.mc4_forbidden(id integer)",
            ):
                with self.subTest(statement=statement), self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(statement)
        self.assertEqual(before, self.business_digest())

    def test_missing_head_update_privilege_fails_closed(self):
        self.draft()
        comparison = self.preview()
        from psycopg import sql
        role = settings.STRATEGY_PUBLICATION_RUNTIME["USER"]
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("REVOKE UPDATE (active_version_id) ON management_strategypolicy FROM {}").format(sql.Identifier(role)))
        before = self.counts()
        try:
            with self.runtime(), self.assertRaises(DatabaseError):
                publish_strategy(**self.envelope(comparison))
            self.assertEqual(before, self.counts())
            self.assertIsNone(self.head().active_version_id)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("GRANT UPDATE (active_version_id) ON management_strategypolicy TO {}").format(sql.Identifier(role)))
