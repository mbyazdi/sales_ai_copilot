"""Draft basket contracts; all mutations use isolated database fixtures."""
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.middleware.csrf import get_token
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.models import CustomerGrade
from apps.inventory.models import Inventory
from apps.products.catalog_access import catalog_access
from apps.products.models import Product, ProductDemoPrice
from apps.products import tests_catalog
from apps.recommendations.catalog_context import saved_priority
from apps.recommendations.feedback import FeedbackConflict, record_feedback
from apps.recommendations.models import CustomerRecommendation, RecommendationFeedbackEvent
from apps.visits.models import CustomerAssignment, Visit
from . import basket as basket_module
from .basket import BasketConflict, basket_quote, inspect_basket, mutate_basket
from .models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt


class BasketFixtures:
    def prepare(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.context = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token

    def quote(self, product=None, quantity=2):
        return basket_quote(self.user, self.customer.customer_code, self.visit.pk,
                            (product or self.products[0]).pk, quantity)

    def command(self, product=None, quantity=2, **changes):
        product = product or self.products[0]
        quote = self.quote(product, quantity)
        return {"customer_code": self.customer.customer_code, "product_id": product.pk, "quantity": quantity,
                "command_uuid": str(uuid4()), "catalog_context": self.context,
                "expected_request_revision": quote["expected_request_revision"],
                "accepted_quote_fingerprint": quote["quote_fingerprint"], **changes}

    def add(self, command=None, **changes):
        return self.api.post(reverse("visit-basket-add-v1", args=[self.visit.pk]),
                             command or self.command(**changes), format="json")

    def change(self, row, *, quantity=3, remove=False, **changes):
        request = SalesRequest.objects.get(pk=row.sales_request_id)
        command = {"customer_code": self.customer.customer_code, "command_uuid": str(uuid4()),
                   "catalog_context": self.context, "expected_request_revision": request.revision}
        if not remove:
            quote = self.quote(row.product, quantity)
            command.update(quantity=quantity, accepted_quote_fingerprint=quote["quote_fingerprint"])
        command.update(changes)
        url = reverse("request-basket-line-v1", args=[request.pk, row.pk])
        return (self.api.delete if remove else self.api.patch)(url, command, format="json")

    def rows(self):
        return {model._meta.db_table: list(model.objects.order_by("pk").values()) for model in apps.get_models()}


class BasketAPITests(BasketFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.prepare()

    def test_get_head_quote_and_missing_command_are_zero_write(self):
        before = self.rows()
        url = reverse("visit-basket-v1", args=[self.visit.pk])
        for method in (self.api.get, self.api.head):
            response = method(url, {"customer_code": self.customer.customer_code})
            self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.api.get(url, {"customer_code": self.customer.customer_code}).data["request"])
        response = self.api.get(reverse("visit-basket-quote-v1", args=[self.visit.pk]),
                                {"customer_code": self.customer.customer_code, "product_id": self.products[0].pk, "quantity": 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["valid"])
        self.assertEqual(self.api.get(reverse("visit-basket-command-v1", args=[self.visit.pk, uuid4()]),
                                     {"customer_code": self.customer.customer_code}).status_code, 404)
        self.assertEqual(self.rows(), before)

    def test_recommended_add_captures_quotes_lineage_and_only_draft_effects(self):
        before = self.rows()
        response = self.add()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["request"]["status"], "DRAFT")
        self.assertEqual(response.data["request"]["revision"], 1)
        self.assertEqual(response.data["saved_totals"], {"base": "246", "discount": "0", "final": "246"})
        line = SalesRequestLine.objects.get()
        self.assertEqual(line.recommendation_id, self.recs[0].pk)
        self.assertEqual(line.lineage_snapshot["rank"], self.recs[0].rank)
        self.assertEqual(line.lineage_snapshot["explanation_snapshot"], self.recs[0].explanation_snapshot)
        event = RecommendationFeedbackEvent.objects.get()
        self.assertEqual(event.event_type, "ADDED_TO_REQUEST")
        self.assertEqual(event.line_id, line.pk)
        after = self.rows()
        self.assertEqual({table for table in before if before[table] != after[table]},
                         {"sales_requests_salesrequest", "sales_requests_salesrequestline",
                          "recommendations_recommendationfeedbackevent", "sales_requests_salesrequestmutationreceipt"})
        request = SalesRequest.objects.get()
        self.assertIsNone(request.number)
        self.assertIsNone(request.submitted_at)
        self.assertEqual(request.prepared_message_snapshot, "")

    def test_ordinary_add_change_remove_never_creates_feedback(self):
        self.assertEqual(self.add(product=self.products[3]).status_code, 201)
        line = SalesRequestLine.objects.get()
        self.assertEqual(line.selection_source, "ORDINARY")
        self.assertIsNone(line.recommendation_id)
        self.assertEqual(self.change(line).status_code, 200)
        self.assertEqual(self.change(line, remove=True).status_code, 200)
        self.assertFalse(RecommendationFeedbackEvent.objects.exists())
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 3)
        self.assertFalse(SalesRequestLine.objects.get().is_selected)

    def test_ordinary_products_keep_unknown_zero_insufficient_and_missing_price_guards(self):
        for product, quantity, code in (
            (self.products[5], 1, "INVENTORY_UNKNOWN"),
            (self.products[4], 1, "OUT_OF_STOCK"),
            (self.products[3], 9, "INSUFFICIENT_STOCK"),
        ):
            with self.subTest(code=code):
                before = self.rows()
                self.assertEqual(self.add(product=product, quantity=quantity).data["code"], code)
                self.assertEqual(self.rows(), before)
        ProductDemoPrice.objects.filter(product=self.products[3]).delete()
        before = self.rows()
        self.assertEqual(self.add(product=self.products[3]).data["code"], "PRICE_UNAVAILABLE")
        self.assertEqual(self.rows(), before)
        self.assertFalse(RecommendationFeedbackEvent.objects.exists())
        self.assertFalse(SalesRequestMutationReceipt.objects.exists())

    def test_add_update_remove_readd_retains_exact_line_event_history(self):
        self.assertEqual(self.add().status_code, 201)
        first = SalesRequestLine.objects.get()
        lineage = first.lineage_snapshot
        self.assertEqual(self.change(first, quantity=4).status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.quantity, 4)
        self.assertEqual(first.lineage_snapshot, lineage)
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)
        self.assertEqual(self.change(first, remove=True).status_code, 200)
        first.refresh_from_db()
        self.assertFalse(first.is_selected)
        self.assertIsNotNone(first.removed_at)
        self.assertEqual(self.add(quantity=1).status_code, 201)
        second = SalesRequestLine.objects.get(is_selected=True)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("event_type", "line_id")),
                         [("ADDED_TO_REQUEST", first.pk), ("REMOVED_FROM_REQUEST", first.pk), ("ADDED_TO_REQUEST", second.pk)])
        self.assertEqual(SalesRequest.objects.get().revision, 4)

    def test_quantities_are_absolute_and_duplicate_selection_is_conflict(self):
        self.assertEqual(self.add(quantity=2).status_code, 201)
        self.assertEqual(self.add(quantity=3).data["code"], "PRODUCT_ALREADY_SELECTED")
        line = SalesRequestLine.objects.get()
        self.assertEqual(self.change(line, quantity=3).status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.quantity, 3)

    def test_invalid_and_missing_command_fields_create_nothing(self):
        command = self.command()
        for changes in ({"quantity": True}, {"quantity": "2"}, {"quantity": 1.5}, {"quantity": 0},
                        {"quantity": -1}, {"quantity": 2147483648}, {"product_id": True},
                        {"command_uuid": "bad"}, {"expected_request_revision": True},
                        {"base_price": "1"}, {"accepted_quote_fingerprint": "invalid"}, {"catalog_context": None}):
            response = self.add({**command, **changes})
            self.assertEqual(response.status_code, 400, changes)
        for key in ("expected_request_revision", "catalog_context", "accepted_quote_fingerprint", "command_uuid"):
            incomplete = dict(command); incomplete.pop(key)
            self.assertEqual(self.add(incomplete).status_code, 400)
        for body in ([], None, "bad"):
            response = self.api.generic("POST", reverse("visit-basket-add-v1", args=[self.visit.pk]),
                                        json.dumps(body), content_type="application/json")
            self.assertEqual(response.status_code, 400)
        self.assertFalse(SalesRequest.objects.exists())

    def test_available_reserved_zero_unknown_missing_invalid_price(self):
        self.assertEqual(self.add(quantity=9).data["code"], "INSUFFICIENT_STOCK")
        self.assertEqual(self.add(product=self.products[4]).data["code"], "OUT_OF_STOCK")
        self.assertEqual(self.add(product=self.products[5]).data["code"], "INVENTORY_UNKNOWN")
        ProductDemoPrice.objects.filter(product=self.products[0]).delete()
        self.assertEqual(self.add().data["code"], "PRICE_UNAVAILABLE")
        ProductDemoPrice.objects.filter(product=self.products[1]).update(base_price=Decimal("123.50"))
        self.assertEqual(self.add(product=self.products[1]).data["code"], "PRICE_CONFIGURATION_ERROR")
        self.assertFalse(SalesRequest.objects.exists())
        self.assertFalse(SalesRequestMutationReceipt.objects.exists())

    def test_stock_is_revalidated_and_never_reserved(self):
        command = self.command(quantity=8)
        Inventory.objects.filter(product=self.products[0]).update(reserved_quantity=4)
        self.assertEqual(self.add(command).data["code"], "INSUFFICIENT_STOCK")
        self.assertFalse(SalesRequest.objects.exists())
        self.assertEqual(self.add(quantity=6).status_code, 201)
        self.assertEqual(Inventory.objects.get(product=self.products[0]).reserved_quantity, 4)

    def test_grade_rounding_and_totals_use_rounded_units_once(self):
        for grade, final in (("A", "95"), ("B", "100"), ("C", "105")):
            with self.subTest(grade=grade):
                self.customer.grade = CustomerGrade.objects.create(code=grade, name=grade)
                self.customer.save()
                ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=105)
                quote = self.quote(quantity=3)
                self.assertEqual(quote["items"][0]["quote"]["final_unit_price"], final)
        self.customer.grade = CustomerGrade.objects.get(code="A"); self.customer.save()
        self.assertEqual(self.add(quantity=3).data["saved_totals"], {"base": "315", "discount": "30", "final": "285"})
        self.assertEqual(SalesRequestLine.objects.get().discount_amount, Decimal("10"))

    def test_explicit_zero_price_is_not_missing(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=0)
        response = self.add()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["saved_totals"]["final"], "0")

    def test_changed_price_grade_or_source_requires_new_basket_quote(self):
        for field, value in (("base_price", 124), ("source_version", "changed")):
            command = self.command()
            ProductDemoPrice.objects.filter(product=self.products[0]).update(**{field: value})
            self.assertEqual(self.add(command).data["code"], "PRICE_CHANGED")
        command = self.command()
        self.customer.grade = CustomerGrade.objects.create(code="A", name="A"); self.customer.save()
        self.assertEqual(self.add(command).data["code"], "PRICE_CHANGED")
        self.assertFalse(SalesRequest.objects.exists())

    def test_price_acceptance_covers_existing_lines_not_only_changed_product(self):
        self.assertEqual(self.add().status_code, 201)
        command = self.command(product=self.products[3])
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=200)
        self.assertEqual(self.add(command).data["code"], "PRICE_CHANGED")
        self.assertEqual(self.add(product=self.products[3]).status_code, 201)
        self.assertEqual(SalesRequestLine.objects.get(product=self.products[0]).base_unit_price, Decimal("200"))
        self.assertEqual(SalesRequest.objects.get().base_total, Decimal("646"))

    def test_stale_and_absent_request_expectations_fail(self):
        self.assertEqual(self.add(expected_request_revision=0).data["code"], "REVISION_CONFLICT")
        self.assertEqual(self.add().status_code, 201)
        self.assertEqual(self.add(product=self.products[3], expected_request_revision=None).data["code"], "REVISION_CONFLICT")
        self.assertEqual(self.add(product=self.products[3], expected_request_revision=0).data["code"], "REVISION_CONFLICT")
        self.assertEqual(SalesRequest.objects.get().revision, 1)

    def test_exact_retry_and_conflicting_uuid_and_command_status(self):
        command = self.command()
        first = self.add(command)
        self.assertEqual(self.add(product=self.products[3]).status_code, 201)
        replay = self.add(command)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(replay.data["request"]["revision"], 1)
        self.assertEqual(self.add({**command, "quantity": 3}).data["code"], "COMMAND_CONFLICT")
        status = self.api.get(reverse("visit-basket-command-v1", args=[self.visit.pk, command["command_uuid"]]),
                              {"customer_code": self.customer.customer_code})
        self.assertEqual(status.data["applied_revision"], 1)
        self.assertEqual(status.data["result"]["body"], first.data)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 2)

    def test_remove_replay_and_changed_operation_conflict(self):
        self.add(); line = SalesRequestLine.objects.get()
        uuid = str(uuid4())
        first = self.change(line, remove=True, command_uuid=uuid)
        replay = self.change(line, remove=True, command_uuid=uuid, expected_request_revision=1)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(self.change(line, quantity=2, command_uuid=uuid).data["code"], "COMMAND_CONFLICT")
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 2)

    def test_replay_closed_visit_but_never_replays_foreign_actor(self):
        command = self.command(); first = self.add(command)
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        self.assertEqual(self.add(command).data, first.data)
        self.api.force_authenticate(self.foreign_user)
        self.assertIn(self.add(command).status_code, (403, 404))

    def test_visit_states_and_read_only_closed_draft(self):
        for state in ("PLANNED", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            self.assertEqual(self.add().data["code"], "VISIT_NOT_ACTIVE")
        self.assertFalse(SalesRequest.objects.exists())
        Visit.objects.filter(pk=self.visit.pk).update(status="IN_PROGRESS")
        self.add(); line = SalesRequestLine.objects.get()
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        self.assertEqual(self.change(line, remove=True).data["code"], "VISIT_NOT_ACTIVE")
        self.assertFalse(inspect_basket(self.user, self.customer.customer_code, self.visit.pk)["editable"])

    def test_foreign_customer_visit_line_manager_anonymous_and_revoked_assignment(self):
        command = self.command()
        self.assertEqual(self.add({**command, "customer_code": self.foreign_customer.customer_code}).status_code, 404)
        self.assertEqual(self.api.post(reverse("visit-basket-add-v1", args=[self.foreign_visit.pk]), command, format="json").status_code, 404)
        for actor in (None, self.foreign_user, self.staff, self.no_profile):
            self.api.force_authenticate(actor)
            self.assertIn(self.add(command).status_code, (403, 404))
        self.api.force_authenticate(self.user)
        CustomerAssignment.objects.filter(customer=self.customer).update(is_active=False)
        self.assertIn(self.add(command).status_code, (403, 404))
        self.assertFalse(SalesRequest.objects.exists())

    def test_context_tampered_foreign_and_expired_new_add_blocked(self):
        self.assertEqual(self.add(catalog_context="bad").data["code"], "CATALOG_CONTEXT_UNAVAILABLE")
        foreign = saved_priority(catalog_access(self.foreign_user, self.foreign_customer.customer_code, self.foreign_visit.pk)).token
        self.assertEqual(self.add(catalog_context=foreign).data["code"], "CATALOG_CONTEXT_UNAVAILABLE")
        with patch("django.core.signing.time.time", return_value=0):
            old = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token
        self.assertEqual(self.add(catalog_context=old).data["code"], "CATALOG_CONTEXT_UNAVAILABLE")
        self.assertFalse(SalesRequest.objects.exists())

    def test_expired_context_deactivated_recommendation_edits_keep_captured_lineage(self):
        with patch("django.core.signing.time.time", return_value=0):
            old = saved_priority(catalog_access(self.user, self.customer.customer_code, self.visit.pk)).token
        self.add(); line = SalesRequestLine.objects.get()
        lineage = line.lineage_snapshot
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=False)
        self.assertEqual(self.change(line, quantity=3, catalog_context=old).status_code, 200)
        self.assertEqual(self.change(line, remove=True, catalog_context=old).status_code, 200)
        line.refresh_from_db(); self.assertEqual(line.lineage_snapshot, lineage)
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 2)

    def test_removal_unavailable_price_stock_preserves_saved_quotes_and_flags_remaining(self):
        self.add(); self.add(product=self.products[3])
        selected = SalesRequestLine.objects.get(product=self.products[3])
        saved = SalesRequestLine.objects.get(product=self.products[0]).pricing_snapshot
        ProductDemoPrice.objects.all().delete()
        Inventory.objects.all().update(available_quantity=0)
        self.assertEqual(self.change(selected, remove=True).status_code, 200)
        result = inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.assertFalse(result["current_quote"]["valid"])
        self.assertIsNone(result["current_quote"]["totals"])
        self.assertEqual(result["lines"][0]["pricing_snapshot"], saved)
        self.assertEqual(result["saved_totals"]["final"], "246")

    def test_remaining_overflow_price_does_not_strand_removal_or_inspection(self):
        self.add(); self.add(product=self.products[3])
        line = SalesRequestLine.objects.get(product=self.products[3])
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("9999999999999999"))
        self.assertEqual(self.change(line, remove=True).status_code, 200)
        result = inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.assertFalse(result["current_quote"]["valid"])
        self.assertIsNone(result["current_quote"]["items"][0]["quote"])

    def test_existing_line_cannot_use_foreign_context_or_foreign_request(self):
        self.add(); line = SalesRequestLine.objects.get()
        foreign = saved_priority(catalog_access(self.foreign_user, self.foreign_customer.customer_code, self.foreign_visit.pk)).token
        self.assertEqual(self.change(line, remove=True, catalog_context=foreign).data["code"], "CATALOG_CONTEXT_UNAVAILABLE")
        self.api.force_authenticate(self.foreign_user)
        self.assertIn(self.change(line, remove=True, customer_code=self.foreign_customer.customer_code).status_code, (403, 404))
        line.refresh_from_db(); self.assertTrue(line.is_selected)

    def test_submission_fixture_is_immutable_and_basket_api_cannot_mutate_it(self):
        self.add(); line = SalesRequestLine.objects.get(); request = SalesRequest.objects.get()
        request.status, request.number = "SUBMITTED", "ISOLATED-SUBMITTED"
        request.submission_key, request.submission_intent_hash = uuid4(), "a" * 64
        request.submitted_at = timezone.now()
        request.customer_snapshot = {"id": self.customer.pk, "code": self.customer.customer_code, "name": self.customer.name}
        request.salesperson_snapshot = {"id": self.rep.pk, "employee_code": self.rep.employee_code, "name": self.rep.full_name}
        request.prepared_message_snapshot = "پیام آزمایشی ارسال نمی‌شود."
        request.save()  # Isolated model fixture only; no submission service exists.
        before = self.rows()
        self.assertEqual(self.add(product=self.products[3]).data["code"], "REQUEST_NOT_DRAFT")
        self.assertEqual(self.change(line).data["code"], "REQUEST_NOT_DRAFT")
        self.assertEqual(self.change(line, remove=True).data["code"], "REQUEST_NOT_DRAFT")
        self.assertEqual(self.rows(), before)

    def test_removed_line_cannot_be_removed_or_updated_by_new_command(self):
        self.add(); line = SalesRequestLine.objects.get()
        self.assertEqual(self.change(line, remove=True).status_code, 200)
        self.assertEqual(self.change(line, remove=True).data["code"], "LINE_NOT_SELECTED")
        self.assertEqual(self.change(line).data["code"], "LINE_NOT_SELECTED")
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 2)

    def test_reads_show_changed_quotes_without_rewriting_saved_snapshots(self):
        self.add(); before = self.rows()
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=200)
        price_change = self.rows()
        result = inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.assertTrue(result["quote_changed"])
        self.assertEqual(result["saved_totals"]["final"], "246")
        self.assertEqual(result["current_quote"]["totals"]["final"], "400")
        self.assertEqual(self.rows(), price_change)
        self.assertEqual(before["sales_requests_salesrequest"], price_change["sales_requests_salesrequest"])

    def test_read_detects_a_revision_change_between_header_and_line_observation(self):
        self.add()
        command = self.command(product=self.products[3])
        original = basket_module._lines
        changed = False
        def interleaved(request):
            nonlocal changed
            if not changed:
                changed = True
                self.assertEqual(self.add(command).status_code, 201)
            return original(request)
        with patch.object(basket_module, "_lines", side_effect=interleaved):
            response = self.api.get(reverse("visit-basket-v1", args=[self.visit.pk]),
                                    {"customer_code": self.customer.customer_code})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "REVISION_CONFLICT")

    def test_rejection_requires_removal_and_prior_rejection_not_erased_on_add(self):
        rejection = {"customer_code": self.customer.customer_code, "recommendation_id": self.recs[0].pk,
                     "command_uuid": uuid4(), "catalog_context": self.context, "action": "REJECTED",
                     "reason_code": "PRICE", "note": "", "expected_request_revision": None}
        record_feedback(self.user, self.visit.pk, rejection)
        self.add(); line = SalesRequestLine.objects.get()
        with self.assertRaises(FeedbackConflict):
            record_feedback(self.user, self.visit.pk, {**rejection, "command_uuid": uuid4(), "expected_request_revision": 1})
        self.change(line, remove=True)
        record_feedback(self.user, self.visit.pk, {**rejection, "command_uuid": uuid4(), "expected_request_revision": 2})
        self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("event_type", flat=True)),
                         ["REJECTED", "ADDED_TO_REQUEST", "REMOVED_FROM_REQUEST", "REJECTED"])

    def test_receipt_failure_rolls_back_request_lines_revision_and_events(self):
        command = self.command()
        with patch.object(SalesRequestMutationReceipt.objects, "create", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                self.add(command)
        self.assertFalse(SalesRequest.objects.exists())
        self.assertFalse(SalesRequestLine.objects.exists())
        self.assertFalse(RecommendationFeedbackEvent.objects.exists())
        self.add(); line = SalesRequestLine.objects.get()
        before = self.rows()
        with patch.object(SalesRequestMutationReceipt.objects, "create", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                self.change(line, quantity=3)
        self.assertEqual(self.rows(), before)

    def test_session_mutations_require_csrf_and_get_never_mutates(self):
        api = APIClient(enforce_csrf_checks=True); api.force_login(self.user)
        command = self.command()
        url = reverse("visit-basket-add-v1", args=[self.visit.pk])
        self.assertEqual(api.get(url).status_code, 405)
        self.assertEqual(api.post(url, command, format="json").status_code, 403)
        token = get_token(RequestFactory().get("/")); api.cookies["csrftoken"] = token
        self.assertEqual(api.post(url, command, format="json", HTTP_X_CSRFTOKEN="bad").status_code, 403)
        self.assertEqual(api.post(url, command, format="json", HTTP_X_CSRFTOKEN=token).status_code, 201)
        line = SalesRequestLine.objects.get(); url = reverse("request-basket-line-v1", args=[line.sales_request_id, line.pk])
        self.assertEqual(api.get(url).status_code, 405)
        self.assertEqual(api.delete(url, {}, format="json").status_code, 403)
        self.assertEqual(api.patch(url, {}, format="json").status_code, 403)
        self.assertEqual(SalesRequest.objects.get().revision, 1)

    def test_batched_query_count_does_not_grow_with_selected_products(self):
        self.add()
        with CaptureQueriesContext(connection) as one:
            inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.add(product=self.products[3])
        with CaptureQueriesContext(connection) as two:
            inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.assertEqual(len(one), len(two))
        self.assertLessEqual(len(two), 12)
        request = SalesRequest.objects.get()
        for index in range(48):
            product = Product.objects.create(product_code=f"BASKET-LARGE-{index}", name="آزمایشی", brand=self.brand, category=self.category)
            Inventory.objects.create(product=product, available_quantity=3)
            ProductDemoPrice.objects.create(product=product, base_price=100, currency="TOMAN", source="fixture", source_version="1")
            SalesRequestLine.objects.create(sales_request=request, product=product, quantity=1)
        with CaptureQueriesContext(connection) as fifty:
            result = inspect_basket(self.user, self.customer.customer_code, self.visit.pk)
        self.assertEqual(result["item_count"], 50)
        self.assertEqual(len(one), len(fifty))
        print(f"BASKET_READ_QUERIES: 1={len(one)}, 2={len(two)}, 50={len(fifty)}")

    def test_planned_basket_quote_is_preparation_not_permission_to_mutate(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="PLANNED")
        result = self.quote()
        self.assertTrue(result["valid"])
        self.assertFalse(result["editable"])
        self.assertEqual(self.add().data["code"], "VISIT_NOT_ACTIVE")


@skipUnless(connection.vendor == "postgresql", "Real concurrent PostgreSQL transactions required")
class BasketConcurrencyTests(BasketFixtures, TransactionTestCase):
    def setUp(self):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(type(self))
        self.prepare()

    def race(self, commands, operation="ADD_PRODUCT", **targets):
        gate = Barrier(2)
        def writer(command):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    return mutate_basket(user, self.visit.pk, operation, command, **targets)
                except BasketConflict as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(writer, commands))

    def test_simultaneous_first_add_different_commands_one_lifecycle_one_success(self):
        results = self.race([self.command(), self.command(product=self.products[3])])
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertIn("REVISION_CONFLICT", results)
        self.assertEqual(SalesRequest.objects.get().revision, 1)
        self.assertEqual(SalesRequestLine.objects.count(), 1)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)

    def test_simultaneous_identical_command_applies_once_and_replays(self):
        command = self.command()
        results = self.race([command, command])
        self.assertEqual([result[2] for result in results].count(False), 1)
        self.assertEqual([result[2] for result in results].count(True), 1)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)

    def test_simultaneous_same_uuid_conflicting_intent_conflicts(self):
        first = self.command()
        results = self.race([first, self.command(product=self.products[3], command_uuid=first["command_uuid"])])
        self.assertIn("COMMAND_CONFLICT", results)
        self.assertEqual(SalesRequestLine.objects.count(), 1)

    def test_two_quantity_writers_expected_one_exactly_one_succeeds(self):
        self.add(); line = SalesRequestLine.objects.get()
        commands = []
        for quantity in (3, 4):
            command = self.command(quantity=quantity); command.pop("product_id")
            commands.append(command)
        results = self.race(commands, "SET_QUANTITY", request_id=line.sales_request_id, line_id=line.pk)
        self.assertIn("REVISION_CONFLICT", results)
        self.assertEqual(SalesRequest.objects.get().revision, 2)
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)
        line.refresh_from_db(); self.assertIn(line.quantity, (3, 4))
