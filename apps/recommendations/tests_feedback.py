"""Feedback decisions/authorization/replay; fixtures never touch runtime data."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections, models
from django.db.models import F
from django.middleware.csrf import get_token
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products import tests_catalog
from apps.products.catalog_access import catalog_access
from apps.recommendations.catalog_context import CONTEXT_MAX_AGE, saved_priority
from apps.recommendations.engine import RecommendationEngine
from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
from apps.visits.models import CustomerAssignment, FollowUpTask, Visit
from .feedback import FeedbackConflict, record_feedback
from .feedback_serializers import FeedbackCommandSerializer
from .models import CustomerRecommendation, RecommendationFeedbackEvent


class FeedbackAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.context = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token

    def url(self, visit=None):
        return reverse("recommendation-feedback-v1", args=[self.visit.pk if visit is None else visit])

    def command(self, **changes):
        return {"customer_code": self.customer.customer_code, "recommendation_id": self.recs[0].pk,
                "command_uuid": str(uuid4()), "action": "REJECTED", "reason_code": "PRICE", "note": "",
                "catalog_context": self.context, "expected_request_revision": None, **changes}

    def post(self, command=None, **changes):
        return self.api.post(self.url(), self.command(**changes) if command is None else command, format="json")

    def counts(self):
        return RecommendationFeedbackEvent.objects.count(), SalesRequestMutationReceipt.objects.count()

    def test_rejected_and_all_seven_existing_codes(self):
        for reason in RecommendationFeedbackEvent.RejectionReason.values:
            with self.subTest(reason=reason):
                response = self.post(reason_code=reason)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data["feedback"]["reason_code"], reason)
                self.assertEqual(response.data["feedback"]["event_type"], "REJECTED")
        self.assertEqual(self.counts(), (7, 7))

    def test_later_is_rejected_reason_later_without_followup_or_visit_mutation(self):
        before = list(Visit.objects.values())
        command = self.command(action="LATER")
        command.pop("reason_code")
        response = self.post(command)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["feedback"]["event_type"], "REJECTED")
        self.assertEqual(response.data["feedback"]["reason_code"], "LATER")
        self.assertEqual(response.data["feedback"]["action"], "LATER")
        self.assertFalse(FollowUpTask.objects.exists())
        self.assertEqual(list(Visit.objects.values()), before)
        self.assertFalse(SalesRequest.objects.exists())

    def test_reason_is_required_single_and_exact(self):
        command = self.command()
        command.pop("reason_code")
        self.assertEqual(self.post(command).status_code, 400)
        for reason in (None, "", "price", "FOLLOW_UP_LATER", "BAD", ["PRICE", "STOCK"], {"reason": "PRICE"}):
            self.assertEqual(self.post(reason_code=reason).status_code, 400)
        self.assertEqual(self.post(action="LATER", reason_code="OTHER").status_code, 400)
        self.assertEqual(self.counts(), (0, 0))

    def test_strict_commands_reject_invalid_ids_notes_and_extra_or_unsupported_fields(self):
        for changes in ({"recommendation_id": True}, {"recommendation_id": "1"}, {"recommendation_id": 1.5},
                        {"command_uuid": "bad"}, {"note": None}, {"note": 12}, {"note": "ن" * 201},
                        {"expected_request_revision": True}, {"expected_request_revision": -1},
                        {"action": "PURCHASED"}, {"action": "ADDED_TO_REQUEST"}, {"action": "REMOVED_FROM_REQUEST"},
                        {"is_prioritized": True}, {"product_id": self.products[0].pk}):
            self.assertEqual(self.post(**changes).status_code, 400, changes)
        self.assertEqual(self.counts(), (0, 0))

    def test_malformed_top_level_bodies_are_safe_400_responses(self):
        for body in ([], [self.command()], "not an object", None):
            response = self.api.generic("POST", self.url(), json.dumps(body), content_type="application/json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.counts(), (0, 0))

    def test_planned_completed_cancelled_new_commands_are_blocked(self):
        for state in ("PLANNED", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            response = self.post()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "VISIT_NOT_ACTIVE")
        self.assertEqual(self.counts(), (0, 0))

    def test_anonymous_manager_missing_and_inactive_profiles_are_denied(self):
        for user in (None, self.staff, self.no_profile):
            self.api.force_authenticate(user)
            self.assertEqual(self.post().status_code, 403)
        self.api.force_authenticate(self.user)
        self.rep.is_active = False
        self.rep.save(update_fields=["is_active"])
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.counts(), (0, 0))

    def test_user_role_is_reread_and_revoked_assignment_prevents_mutation(self):
        type(self.user).objects.filter(pk=self.user.pk).update(is_staff=True)
        self.assertEqual(self.post().status_code, 403)
        type(self.user).objects.filter(pk=self.user.pk).update(is_staff=False)
        CustomerAssignment.objects.filter(customer=self.customer, salesperson=self.rep).update(is_active=False)
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(self.counts(), (0, 0))

    def test_foreign_customer_visit_and_recommendation_are_not_disclosed(self):
        foreign = CustomerRecommendation.objects.create(customer=self.foreign_customer, product=self.products[0], recommendation_type="CROSS_SELL")
        self.assertEqual(self.post(customer_code=self.foreign_customer.customer_code).status_code, 404)
        self.assertEqual(self.api.post(self.url(self.foreign_visit.pk), self.command(), format="json").status_code, 404)
        for recommendation in (foreign.pk, 99999999):
            self.assertEqual(self.post(recommendation_id=recommendation).status_code, 404)
        self.assertEqual(self.counts(), (0, 0))

    def test_ordinary_product_cannot_create_fake_recommendation_or_feedback(self):
        before = CustomerRecommendation.objects.count()
        command = self.command()
        command.pop("recommendation_id")
        self.assertEqual(self.post(command).status_code, 400)
        self.assertEqual(self.post(recommendation_id=99999999).status_code, 404)
        newly_added = CustomerRecommendation.objects.create(customer=self.customer, product=self.products[3], recommendation_type="CROSS_SELL")
        self.assertEqual(self.post(recommendation_id=newly_added.pk).status_code, 409)  # not in the saved context
        self.assertEqual(CustomerRecommendation.objects.count(), before + 1)
        self.assertEqual(self.counts(), (0, 0))

    def test_missing_tampered_foreign_expired_and_changed_context_are_blocked(self):
        self.assertEqual(self.post(catalog_context="").status_code, 400)
        self.assertEqual(self.post(catalog_context="tampered").status_code, 409)
        foreign_token = saved_priority(catalog_access(self.foreign_user, self.foreign_customer.customer_code, self.foreign_visit.pk)).token
        self.assertEqual(self.post(catalog_context=foreign_token).status_code, 409)
        now = signing.time.time()
        with patch("django.core.signing.time.time", return_value=now + CONTEXT_MAX_AGE + 5):
            self.assertEqual(self.post().status_code, 409)
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(reason="changed saved evidence")
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.counts(), (0, 0))

    def test_inactive_recommendation_or_product_cannot_receive_new_feedback(self):
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=False)
        self.assertEqual(self.post().status_code, 409)
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=True)
        type(self.products[0]).objects.filter(pk=self.products[0].pk).update(is_active=False)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.counts(), (0, 0))

    def test_identical_command_replays_exact_body_status_without_extra_writes(self):
        command = self.command(note="یادداشت فارسی")
        first = self.post(command)
        before = list(RecommendationFeedbackEvent.objects.values()), list(SalesRequestMutationReceipt.objects.values())
        second = self.post(command)
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(first.data, second.data)
        self.assertEqual(second["Idempotent-Replayed"], "true")
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual((list(RecommendationFeedbackEvent.objects.values()), list(SalesRequestMutationReceipt.objects.values())), before)

    def test_same_uuid_different_intent_conflicts(self):
        command = self.command()
        self.assertEqual(self.post(command).status_code, 201)
        for changes in ({"reason_code": "OTHER"}, {"note": "different"}, {"recommendation_id": self.recs[1].pk},
                        {"expected_request_revision": 1}, {"action": "LATER", "reason_code": "LATER"}):
            response = self.post({**command, **changes})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.counts(), (1, 1))

    def test_different_commands_preserve_separate_explicit_history(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post(action="LATER", reason_code="LATER").status_code, 201)
        self.assertEqual(self.counts(), (2, 2))
        self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("reason_code", flat=True)), ["PRICE", "LATER"])

    def test_replay_survives_context_expiry_deactivation_and_completion_but_rechecks_access(self):
        command = self.command()
        first = self.post(command)
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=False)
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        with patch("django.core.signing.time.time", return_value=signing.time.time() + CONTEXT_MAX_AGE + 5):
            replay = self.post(command)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.data, first.data)
        CustomerAssignment.objects.filter(customer=self.customer, salesperson=self.rep).update(is_active=False)
        self.assertEqual(self.post(command).status_code, 404)
        self.assertEqual(self.counts(), (1, 1))

    def test_selected_recommended_or_ordinary_source_product_blocks_rejection_and_defer(self):
        request = SalesRequest.objects.create(visit=self.visit)
        for source in ("ORDINARY", "RECOMMENDATION"):
            line = SalesRequestLine.objects.create(sales_request=request, product=self.products[0], quantity=1,
                selection_source=source, recommendation=self.recs[0] if source == "RECOMMENDATION" else None,
                lineage_snapshot={"recommendation_id": self.recs[0].pk} if source == "RECOMMENDATION" else {})
            for action, reason in (("REJECTED", "PRICE"), ("LATER", "LATER")):
                response = self.post(action=action, reason_code=reason, expected_request_revision=0)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.data["code"], "PRODUCT_ALREADY_SELECTED")
            line.delete()  # fixture cleanup only; no removal API/event is implemented
        self.assertEqual(self.counts(), (0, 0))

    def test_existing_request_revision_is_checked_without_mutating_draft(self):
        request = SalesRequest.objects.create(visit=self.visit)
        before = SalesRequest.objects.values().get(pk=request.pk)
        self.assertEqual(self.post().data["code"], "REVISION_CONFLICT")
        self.assertEqual(self.post(expected_request_revision=1).data["code"], "REVISION_CONFLICT")
        command = self.command(expected_request_revision=0)
        first = self.post(command)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(SalesRequest.objects.values().get(pk=request.pk), before)
        SalesRequest.objects.filter(pk=request.pk, revision=0).update(revision=F("revision") + 1)
        self.assertEqual(self.post(command).data, first.data)
        receipt = SalesRequestMutationReceipt.objects.get()
        receipt.full_clean()
        self.assertEqual(receipt.applied_revision, 0)

    def test_failed_receipt_creation_rolls_back_event_and_leaves_no_success_receipt(self):
        with patch.object(SalesRequestMutationReceipt.objects, "create", side_effect=ValidationError("controlled failure")):
            self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.counts(), (0, 0))

    def test_saved_lineage_values_preserved_and_only_event_receipt_tables_change(self):
        all_models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in all_models}
        with patch.object(RecommendationEngine, "generate", side_effect=AssertionError("No generation")):
            self.assertEqual(self.post(note="<script>متن</script>").status_code, 201)
        event = RecommendationFeedbackEvent.objects.get()
        self.assertEqual(event.lineage_snapshot["reason"], self.recs[0].reason)
        self.assertEqual(event.lineage_snapshot["rank"], self.recs[0].rank)
        self.assertEqual(event.lineage_snapshot["score_breakdown"], self.recs[0].score_breakdown)
        self.assertEqual(event.lineage_snapshot["explanation_snapshot"], self.recs[0].explanation_snapshot)
        self.assertEqual(event.lineage_snapshot["actor_id"], self.user.pk)
        self.assertEqual(len(event.lineage_snapshot["context_fingerprint"]), 64)
        self.assertNotIn("catalog_context", event.lineage_snapshot)
        for model, rows in before.items():
            if model not in (RecommendationFeedbackEvent, SalesRequestMutationReceipt):
                self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)

    def test_feedback_and_receipt_normal_orm_history_is_append_only(self):
        self.assertEqual(self.post().status_code, 201)
        for model in (RecommendationFeedbackEvent, SalesRequestMutationReceipt):
            record = model.objects.get()
            before = list(model.objects.values())
            for operation in (lambda: record.save(), lambda: record.delete(),
                              lambda: model.objects.all().update(created_at=record.created_at),
                              lambda: model.objects.all().delete(), lambda: model.objects.bulk_update([record], ["created_at"]),
                              lambda: model.objects.bulk_create([])):
                with self.assertRaises(ValidationError):
                    operation()
                self.assertEqual(list(model.objects.values()), before)

    def test_get_head_empty_history_are_zero_write_and_never_generate_context(self):
        self.client.force_login(self.user)
        all_models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in all_models}
        with patch("apps.recommendations.feedback.saved_priority", side_effect=AssertionError("No context generation")), CaptureQueriesContext(connection) as queries:
            for method in (self.client.get, self.client.head):
                response = method(self.url(), {"customer_code": self.customer.customer_code})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)

    def test_history_reads_preserve_deactivated_recommendation_and_closed_visit(self):
        self.assertEqual(self.post().status_code, 201)
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=False)
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        response = self.api.get(self.url(), {"customer_code": self.customer.customer_code, "recommendation_id": self.recs[0].pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["events"][0]["reason_code"], "PRICE")
        self.api.force_authenticate(self.foreign_user)
        self.assertEqual(self.api.get(self.url(), {"customer_code": self.customer.customer_code}).status_code, 404)

    def test_other_mutation_methods_are_not_supported(self):
        for method in (self.api.put, self.api.patch, self.api.delete):
            self.assertEqual(method(self.url(), {}, format="json").status_code, 405)
        self.assertEqual(self.counts(), (0, 0))

    def test_real_session_post_requires_valid_csrf_and_basic_auth_cannot_bypass(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url(), self.command(), format="json").status_code, 403)
        csrf = get_token(RequestFactory().get("/"))
        client.cookies["csrftoken"] = csrf
        self.assertEqual(client.post(self.url(), self.command(), format="json", HTTP_X_CSRFTOKEN="bad").status_code, 403)
        response = client.post(self.url(), self.command(), format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201)
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(anonymous.post(self.url(), self.command(), format="json", HTTP_AUTHORIZATION="Basic ZmFrZTpmYWtl").status_code, 403)
        self.assertEqual(self.counts(), (1, 1))


class FeedbackConcurrencyTests(TransactionTestCase):
    def test_concurrent_conflicting_uuid_has_one_success_and_one_conflict(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires independent PostgreSQL transactions")
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(type(self))
        token = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token
        command_uuid = str(uuid4())
        commands = []
        for reason in ("PRICE", "OTHER"):
            serializer = FeedbackCommandSerializer(data={"customer_code": self.customer.customer_code,
                "recommendation_id": self.recs[0].pk, "command_uuid": command_uuid,
                "action": "REJECTED", "reason_code": reason, "catalog_context": token})
            serializer.is_valid(raise_exception=True)
            commands.append(serializer.validated_data)
        gate = Barrier(2)
        def writer(command):
            close_old_connections()
            try:
                gate.wait(timeout=10)
                try:
                    record_feedback(self.user, self.visit.pk, command)
                    return "APPLIED"
                except FeedbackConflict as error:
                    return error.code
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, commands))
        self.assertEqual(sorted(results), ["APPLIED", "COMMAND_CONFLICT"])
        self.assertEqual(self.count_records(), (1, 1))

    def test_concurrent_identical_commands_apply_once(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires independent PostgreSQL transactions")
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(type(self))
        token = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token
        serializer = FeedbackCommandSerializer(data={"customer_code": self.customer.customer_code,
            "recommendation_id": self.recs[0].pk, "command_uuid": str(uuid4()), "action": "REJECTED",
            "reason_code": "PRICE", "catalog_context": token})
        serializer.is_valid(raise_exception=True)
        command = serializer.validated_data
        gate = Barrier(2)
        def writer():
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return record_feedback(self.user, self.visit.pk, command)
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: writer(), range(2)))
        self.assertEqual(self.count_records(), (1, 1))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(r[2] for r in results), [False, True])

    def count_records(self):
        return RecommendationFeedbackEvent.objects.count(), SalesRequestMutationReceipt.objects.count()
