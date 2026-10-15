"""Review/submit contracts; mutations run only in isolated test databases."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.middleware.csrf import get_token
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.customers.models import CustomerGrade
from apps.inventory.models import Inventory
from apps.products.models import ProductDemoPrice
from apps.products import tests_catalog
from apps.recommendations.models import RecommendationFeedbackEvent
from apps.recommendations.catalog_context import CONTEXT_SALT
from apps.visits.models import CustomerAssignment, Visit
from . import submission
from .basket import BasketConflict, mutate_basket
from .models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
from .tests_basket import BasketFixtures


class SubmissionFixtures(BasketFixtures):
    def review(self):
        return self.api.get(reverse("visit-request-review-v1", args=[self.visit.pk]),
                            {"customer_code": self.customer.customer_code})

    def submit_command(self, **changes):
        state = self.review().data
        return {"customer_code": self.customer.customer_code, "command_uuid": str(uuid4()),
                "catalog_context": self.context, "expected_request_revision": state["request"]["revision"],
                "accepted_review_fingerprint": state["review_fingerprint"], **changes}

    def submit(self, command=None):
        return self.api.post(reverse("visit-request-submit-v1", args=[self.visit.pk]),
                             command or self.submit_command(), format="json")


class SubmissionAPITests(SubmissionFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.prepare()

    def test_missing_request_reads_and_submit_never_create_a_draft(self):
        before = self.rows()
        url = reverse("visit-request-review-v1", args=[self.visit.pk])
        self.assertEqual(self.api.get(url, {"customer_code": self.customer.customer_code}).status_code, 404)
        self.assertEqual(self.submit({"customer_code": self.customer.customer_code, "command_uuid": str(uuid4()),
            "catalog_context": self.context, "expected_request_revision": 0,
            "accepted_review_fingerprint": "a" * 64}).status_code, 404)
        self.assertEqual(self.rows(), before)

    def test_review_get_head_and_submission_get_head_are_zero_write(self):
        self.add()
        before = self.rows()
        url = reverse("visit-request-review-v1", args=[self.visit.pk])
        for method in (self.api.get, self.api.head):
            response = method(url, {"customer_code": self.customer.customer_code})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store, private")
        for method in (self.api.get, self.api.head):
            self.assertEqual(method(reverse("visit-request-submit-v1", args=[self.visit.pk])).status_code, 405)
        self.assertEqual(self.rows(), before)

    def test_success_persists_complete_snapshots_and_only_submission_effects(self):
        self.add(); self.add(product=self.products[3], quantity=3)
        review = self.review().data
        self.assertTrue(review["can_submit"])
        before = self.rows()
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response["Idempotent-Replayed"], "false")
        request = SalesRequest.objects.get()
        self.assertEqual(request.status, "SUBMITTED")
        self.assertEqual(request.revision, 3)
        self.assertEqual(response.data["totals"], {"base": "615", "discount": "0", "final": "615"})
        self.assertEqual(request.customer_snapshot["id"], self.customer.pk)
        self.assertEqual(request.salesperson_snapshot["id"], self.rep.pk)
        self.assertEqual(request.salesperson_snapshot["user_id"], self.user.pk)
        self.assertEqual(request.number, f"SR-{request.pk:08d}")
        self.assertIn("درخواست فروش", request.prepared_message_snapshot)
        self.assertIn(self.customer.name, request.prepared_message_snapshot)
        self.assertIn(request.number, request.prepared_message_snapshot)
        self.assertIn("۶۱۵ تومان", request.prepared_message_snapshot)
        self.assertIn(submission.MESSAGE_DISCLOSURE, request.prepared_message_snapshot)
        self.assertNotIn("خرید", request.prepared_message_snapshot)
        self.assertEqual(response.data["prepared_message_snapshot"], request.prepared_message_snapshot)
        after = self.rows()
        self.assertEqual({table for table in before if before[table] != after[table]},
                         {"sales_requests_salesrequest", "sales_requests_salesrequestline"})
        self.visit.refresh_from_db(); self.assertEqual(self.visit.status, "IN_PROGRESS")
        self.assertEqual(RecommendationFeedbackEvent.objects.get().event_type, "ADDED_TO_REQUEST")
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 2)

    def test_new_snapshot_formats_whole_toman_in_persian_without_changing_amounts(self):
        for base, expected in ((0, "۰"), (1000, "۱٬۰۰۰"), (1234567, "۱٬۲۳۴٬۵۶۷"),
                               (9999999999999999, "۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹٬۹۹۹")):
            with self.subTest(base=base):
                # Formatting has no arithmetic/rounding or database side effect.
                request = SalesRequest(final_total=Decimal(base), number="SR-FIXTURE",
                                       customer_snapshot={"name": "مشتری"})
                message = submission._prepared_customer_message(request)
                self.assertIn(f"به مبلغ {expected} تومان", message)
                self.assertEqual(request.final_total, Decimal(base))
        ProductDemoPrice.objects.filter(product=self.products[3]).update(base_price=1234567)
        self.add(product=self.products[3], quantity=1)
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["totals"]["final"], "1234567")
        self.assertIn("۱٬۲۳۴٬۵۶۷ تومان", SalesRequest.objects.get().prepared_message_snapshot)

    def test_legacy_snapshot_is_not_formatted_again_by_read_or_exact_replay(self):
        self.add(); command = self.submit_command()
        legacy = "مشتری، درخواست فروش با مبلغ 246 تومان ثبت شد.\n" + submission.MESSAGE_DISCLOSURE
        with patch.object(submission, "_prepared_customer_message", return_value=legacy):
            original = self.submit(command)
        self.assertEqual(original.status_code, 201)
        before = self.rows()
        with patch.object(submission, "_prepared_customer_message", side_effect=AssertionError("Never regenerate submitted text")):
            replay = self.submit(command)
            read = self.review()
        self.assertEqual(replay.data, original.data)
        self.assertEqual(read.data, original.data)
        self.assertEqual(SalesRequest.objects.get().prepared_message_snapshot, legacy)
        self.assertEqual(self.rows(), before)

    def test_grade_a_rounding_snapshots_are_not_discounted_again(self):
        self.customer.grade = CustomerGrade.objects.create(code="A", name="الف")
        self.customer.save(update_fields=["grade"])
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=105)
        self.add(quantity=3)
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["totals"], {"base": "315", "discount": "30", "final": "285"})
        line = SalesRequestLine.objects.get()
        self.assertEqual(line.final_unit_price, Decimal(95))
        self.assertEqual(line.discount_amount, Decimal(10))

    def test_explicit_zero_price_is_valid_not_missing(self):
        ProductDemoPrice.objects.filter(product=self.products[3]).update(base_price=0)
        self.add(product=self.products[3]); response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["totals"]["final"], "0")
        self.assertFalse(RecommendationFeedbackEvent.objects.exists())

    def test_identical_replay_returns_frozen_result_without_writes_or_repricing(self):
        self.add(); command = self.submit_command(); original = self.submit(command)
        ProductDemoPrice.objects.all().delete()
        Inventory.objects.all().update(available_quantity=0)
        self.customer.name = "نام جدید"; self.customer.save(update_fields=["name"])
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        before = self.rows()
        with patch.object(submission, "_commercial", side_effect=AssertionError("Replay must not reprice")):
            replay = self.submit(command)
            read = self.review()
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(replay.data, original.data)
        self.assertEqual(read.data, original.data)
        self.assertEqual(self.rows(), before)

    def test_same_key_different_intent_conflicts_and_new_key_cannot_resubmit(self):
        self.add(); command = self.submit_command(); self.assertEqual(self.submit(command).status_code, 201)
        before = self.rows()
        self.assertEqual(self.submit({**command, "expected_request_revision": 0}).data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.submit({**command, "command_uuid": str(uuid4())}).data["code"], "REQUEST_NOT_DRAFT")
        self.assertEqual(self.rows(), before)

    def test_basket_receipt_uuid_cannot_be_reused_for_submission(self):
        command = self.command(); self.add(command)
        before = self.rows()
        self.assertEqual(self.submit(self.submit_command(command_uuid=command["command_uuid"])).data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.rows(), before)

    def test_removed_history_is_retained_frozen_and_not_submitted_content(self):
        self.add(); old = SalesRequestLine.objects.get(); self.change(old, remove=True)
        self.add(product=self.products[3])
        old.refresh_from_db(); before = old.pricing_snapshot
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["item_count"], 1)
        self.assertEqual(response.data["lines"][0]["product_id"], self.products[3].pk)
        old.refresh_from_db(); self.assertEqual(old.pricing_snapshot, before)
        with self.assertRaises(ValidationError):
            old.save()
        self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("event_type", flat=True)),
                         ["ADDED_TO_REQUEST", "REMOVED_FROM_REQUEST"])

    def test_submitted_request_lines_and_basket_are_immutable(self):
        self.add(); self.submit(); request = SalesRequest.objects.get(); line = SalesRequestLine.objects.get()
        before = self.rows()
        for operation in (request.save, request.delete, line.save, line.delete,
                          lambda: SalesRequest.objects.filter(pk=request.pk).update(revision=4),
                          lambda: SalesRequestLine.objects.filter(pk=line.pk).update(quantity=4)):
            with self.assertRaises(ValidationError):
                operation()
        for action in (lambda: self.add(product=self.products[3]), lambda: self.change(line),
                       lambda: self.change(line, remove=True)):
            self.assertEqual(action().data["code"], "REQUEST_NOT_DRAFT")
        self.assertEqual(self.rows(), before)

    def test_empty_draft_cannot_submit(self):
        SalesRequest.objects.create(visit=self.visit)
        before = self.rows(); review = self.review().data
        self.assertFalse(review["can_submit"])
        self.assertEqual(self.submit().data["code"], "EMPTY_BASKET")
        self.assertEqual(self.rows(), before)

    def test_invalid_saved_snapshot_cannot_be_silently_repaired(self):
        self.add(); line = SalesRequestLine.objects.get()
        line.final_unit_price = Decimal(1); line.save()
        before = self.rows()
        self.assertEqual(self.submit().data["code"], "DRAFT_INVALID")
        self.assertEqual(self.rows(), before)

    def test_malformed_saved_amount_and_header_snapshot_are_actionable_not_repaired(self):
        self.add(); line = SalesRequestLine.objects.get(); request = SalesRequest.objects.get()
        quote = line.pricing_snapshot.copy()
        for invalid in ("not-a-number", None):
            line.pricing_snapshot = {**quote, "line_base": invalid}; line.save()
            before = self.rows(); response = self.submit()
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data["code"], "DRAFT_INVALID")
            self.assertEqual(self.rows(), before)
        line.pricing_snapshot = quote; line.save()
        request.pricing_snapshot["totals"] = {"base": "1", "discount": "0", "final": "1"}; request.save()
        before = self.rows()
        self.assertEqual(self.submit().data["code"], "DRAFT_INVALID")
        self.assertEqual(self.rows(), before)

    def test_price_change_requires_explicit_basket_requote_then_new_review(self):
        self.add(); command = self.submit_command()
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=200)
        before = self.rows(); response = self.submit(command)
        self.assertEqual(response.data["code"], "PRICE_CHANGED")
        self.assertEqual(response.data["review"]["saved_totals"]["final"], "246")
        self.assertEqual(response.data["review"]["current_quote"]["totals"]["final"], "400")
        self.assertEqual(self.rows(), before)
        # Even acknowledging a new review doesn't silently replace saved prices.
        self.assertEqual(self.submit(self.submit_command()).data["code"], "PRICE_CHANGED")
        self.change(SalesRequestLine.objects.get(), quantity=2)
        self.assertEqual(self.submit().data["totals"]["final"], "400")

    def test_missing_fractional_price_and_stock_failures_leave_draft_unchanged(self):
        self.add(); command = self.submit_command()
        changes = (
            (lambda: ProductDemoPrice.objects.filter(product=self.products[0]).delete(), "PRICE_UNAVAILABLE"),
            (lambda: ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("123.5")), "PRICE_CONFIGURATION_ERROR"),
            (lambda: Inventory.objects.filter(product=self.products[0]).delete(), "INVENTORY_UNKNOWN"),
            (lambda: Inventory.objects.filter(product=self.products[0]).update(available_quantity=2), "OUT_OF_STOCK"),
            (lambda: Inventory.objects.filter(product=self.products[0]).update(available_quantity=3), "INSUFFICIENT_STOCK"),
        )
        for modify, code in changes:
            with self.subTest(code=code):
                ProductDemoPrice.objects.update_or_create(product=self.products[0], defaults={
                    "base_price": 123, "currency": "TOMAN", "source": "test-fixture", "source_version": "1"})
                Inventory.objects.update_or_create(product=self.products[0], defaults={"available_quantity": 10, "reserved_quantity": 2})
                modify(); before = self.rows(); response = self.submit(command)
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data["code"], code)
                self.assertEqual(self.rows(), before)

    def test_valid_changed_stock_requires_explicit_fresh_review(self):
        self.add(); command = self.submit_command()
        Inventory.objects.filter(product=self.products[0]).update(available_quantity=9)
        before = self.rows(); response = self.submit(command)
        self.assertEqual(response.data["code"], "REVIEW_CHANGED")
        self.assertEqual(response.data["review"]["lines"][0]["current"]["inventory"]["available_quantity"], 7)
        self.assertEqual(self.rows(), before)
        response = self.submit(self.submit_command())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["lines"][0]["eligibility_snapshot"]["available_quantity"], 7)

    def test_grade_and_price_version_changes_need_requote(self):
        self.add()
        for change in ("grade", "version"):
            with self.subTest(change=change):
                command = self.submit_command()
                if change == "grade":
                    self.customer.grade = CustomerGrade.objects.create(code="B", name="ب")
                    self.customer.save(update_fields=["grade"])
                else:
                    ProductDemoPrice.objects.filter(product=self.products[0]).update(source_version="2")
                before = self.rows()
                self.assertEqual(self.submit(command).data["code"], "PRICE_CHANGED")
                self.assertEqual(self.rows(), before)
                self.change(SalesRequestLine.objects.get(), quantity=2)

    def test_inactive_product_cannot_submit_even_with_current_review(self):
        self.add(); self.products[0].is_active = False; self.products[0].save(update_fields=["is_active"])
        before = self.rows()
        self.assertEqual(self.submit().data["code"], "INACTIVE_PRODUCT")
        self.assertEqual(self.rows(), before)

    def test_stale_revision_and_unaccepted_review_fail_before_write(self):
        self.add()
        for changes, code in (({"expected_request_revision": 0}, "REVISION_CONFLICT"),
                              ({"accepted_review_fingerprint": "a" * 64}, "REVIEW_CHANGED")):
            before = self.rows()
            self.assertEqual(self.submit(self.submit_command(**changes)).data["code"], code)
            self.assertEqual(self.rows(), before)

    def test_non_active_visits_are_reviewable_but_cannot_submit(self):
        self.add()
        for status in ("PLANNED", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=status)
            before = self.rows()
            self.assertFalse(self.review().data["can_submit"])
            self.assertEqual(self.submit().data["code"], "VISIT_NOT_ACTIVE")
            self.assertEqual(self.rows(), before)

    def test_authorization_customer_visit_roles_and_revoked_assignment(self):
        self.add(); command = self.submit_command(); before = self.rows()
        self.assertEqual(self.submit({**command, "customer_code": self.foreign_customer.customer_code}).status_code, 404)
        self.assertEqual(self.api.post(reverse("visit-request-submit-v1", args=[self.foreign_visit.pk]), command, format="json").status_code, 404)
        for actor in (None, self.foreign_user, self.staff, self.no_profile):
            self.api.force_authenticate(actor)
            self.assertIn(self.submit(command).status_code, (403, 404))
            self.assertIn(self.review().status_code, (403, 404))
        self.api.force_authenticate(self.user)
        CustomerAssignment.objects.filter(customer=self.customer).update(is_active=False)
        revoked = self.rows()
        self.assertIn(self.submit(command).status_code, (403, 404))
        self.assertEqual(self.rows(), revoked)
        self.assertEqual(SalesRequest.objects.get().status, "DRAFT")
        self.assertEqual(before["sales_requests_salesrequest"], revoked["sales_requests_salesrequest"])

    def test_replay_rechecks_current_authorization(self):
        self.add(); command = self.submit_command(); self.submit(command)
        CustomerAssignment.objects.filter(customer=self.customer).update(is_active=False)
        before = self.rows()
        self.assertIn(self.submit(command).status_code, (403, 404))
        self.assertEqual(self.rows(), before)

    def test_signed_context_and_strict_inputs_are_required(self):
        self.add(); command = self.submit_command()
        self.assertEqual(self.submit({**command, "catalog_context": "tampered"}).data["code"], "CATALOG_CONTEXT_UNAVAILABLE")
        for changes in ({"expected_request_revision": True}, {"expected_request_revision": None},
                        {"command_uuid": "bad"}, {"final_total": "1"}, {"accepted_review_fingerprint": "bad"}):
            before = self.rows()
            self.assertEqual(self.submit({**command, **changes}).status_code, 400)
            self.assertEqual(self.rows(), before)

    def test_post_requires_session_csrf(self):
        self.add(); command = self.submit_command()
        api = APIClient(enforce_csrf_checks=True); api.force_login(self.user)
        url = reverse("visit-request-submit-v1", args=[self.visit.pk])
        before = self.rows()
        self.assertEqual(api.post(url, command, format="json").status_code, 403)
        token = get_token(RequestFactory().get("/")); api.cookies["csrftoken"] = token
        self.assertEqual(api.post(url, command, format="json", HTTP_X_CSRFTOKEN="bad").status_code, 403)
        self.assertEqual(self.rows(), before)
        self.assertEqual(api.post(url, command, format="json", HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_failure_after_revision_and_line_writes_rolls_everything_back(self):
        self.add(); command = self.submit_command(); before = self.rows()
        with patch.object(SalesRequest, "save", side_effect=RuntimeError("isolated failure")):
            with self.assertRaises(RuntimeError):
                self.submit(command)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.submit(command).status_code, 201)

    def test_batched_review_queries_are_bounded_and_zero_write(self):
        self.add()
        with CaptureQueriesContext(connection) as one:
            self.review()
        self.add(product=self.products[3])
        with CaptureQueriesContext(connection) as two:
            self.review()
        self.assertEqual(len(one), len(two))
        self.assertLessEqual(len(two), 13)
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in two))
        print(f"SUBMISSION_REVIEW_QUERIES: one={len(one)}, two={len(two)}")

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL runtime grants required")
    def test_runtime_role_can_submit_with_select_only_demo_prices(self):
        # Grants affect this isolated test DB only; the existing cluster role and
        # production grants remain untouched. Other PG environments may lack it.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='sales_ai_runtime'")
            if cursor.fetchone() is None:
                self.skipTest("Local approved runtime role not installed")
            cursor.execute("GRANT USAGE ON SCHEMA public TO sales_ai_runtime")
            cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO sales_ai_runtime")
            cursor.execute("GRANT UPDATE ON customers_customer, customers_customergrade, products_product, "
                           "inventory_inventory, visits_visit, sales_requests_salesrequest, "
                           "sales_requests_salesrequestline TO sales_ai_runtime")
        self.add(); command = self.submit_command()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE sales_ai_runtime")
                cursor.execute("SELECT has_table_privilege(current_user, 'products_productdemoprice', 'SELECT'), "
                               "has_table_privilege(current_user, 'products_productdemoprice', 'UPDATE')")
                self.assertEqual(cursor.fetchone(), (True, False))
            response = self.submit(command)
            self.assertEqual(response.status_code, 201, response.data)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")


@skipUnless(connection.vendor == "postgresql", "Real PostgreSQL connections/transactions required")
class SubmissionConcurrencyTests(SubmissionFixtures, TransactionTestCase):
    def setUp(self):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(type(self))
        self.prepare()
        self.assertEqual(self.add().status_code, 201)

    def race(self, commands):
        gate = Barrier(2)
        def writer(command):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    return submission.submit_request(user, self.visit.pk, {**command, "command_uuid": UUID(command["command_uuid"])})
                except BasketConflict as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(writer, commands))

    def test_concurrent_different_keys_submit_once(self):
        results = self.race([self.submit_command(), self.submit_command()])
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertIn("REQUEST_NOT_DRAFT", results)
        self.assertEqual(SalesRequest.objects.get().revision, 2)
        self.assertEqual(SalesRequest.objects.filter(status="SUBMITTED").count(), 1)
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)

    def test_concurrent_same_key_same_intent_replays_one_submission(self):
        command = self.submit_command(); results = self.race([command, command])
        self.assertEqual(sorted(result[2] for result in results), [False, True])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(SalesRequest.objects.get().revision, 2)

    def test_concurrent_same_key_different_intent_conflicts(self):
        command = self.submit_command()
        with patch("django.core.signing.time.time", return_value=0):
            other_context = signing.dumps(signing.loads(self.context, salt=CONTEXT_SALT), salt=CONTEXT_SALT)
        results = self.race([command, {**command, "catalog_context": other_context}])
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertIn("COMMAND_CONFLICT", results)

    def test_submission_and_quantity_change_serialize_without_lost_update(self):
        submit = self.submit_command(); quantity = self.command(quantity=3); quantity.pop("product_id")
        line = SalesRequestLine.objects.get()
        gate = Barrier(2)
        def writer(operation):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    if operation == "submit":
                        return submission.submit_request(user, self.visit.pk, {**submit, "command_uuid": UUID(submit["command_uuid"])})
                    return mutate_basket(user, self.visit.pk, "SET_QUANTITY", quantity,
                                         request_id=line.sales_request_id, line_id=line.pk)
                except BasketConflict as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, ["submit", "quantity"]))
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertTrue(any(code in results for code in ("REVISION_CONFLICT", "REQUEST_NOT_DRAFT")))
        request = SalesRequest.objects.get(); line.refresh_from_db()
        self.assertEqual(request.revision, 2)
        self.assertEqual(line.quantity, 2 if request.status == "SUBMITTED" else 3)
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)

    def test_global_submission_key_conflict_keeps_other_visits_draft(self):
        command = self.submit_command(); self.submit(command)
        self.user, self.customer, self.visit = self.foreign_user, self.foreign_customer, self.foreign_visit
        self.prepare(); self.assertEqual(self.add(product=self.products[3]).status_code, 201)
        before = self.rows()
        response = self.submit(self.submit_command(command_uuid=command["command_uuid"]))
        self.assertEqual(response.data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.rows(), before)

    def test_replay_in_fresh_python_process_reads_original_committed_snapshot(self):
        command = self.submit_command(); original = self.submit(command)
        self.assertEqual(original.status_code, 201)
        before = self.rows()
        root = Path(__file__).resolve().parents[2]
        # Django switches the connection NAME, not the inherited process env.
        # Bind the child to this active test connection, never a naming prefix.
        database = connection.settings_dict.copy()
        self.assertEqual(connection.vendor, "postgresql")
        for field in ("NAME", "HOST", "PORT", "USER"):
            self.assertTrue(database.get(field), "Explicit test endpoint required")
        self.assertNotIn(database["NAME"], {"sales_ai_db", "postgres", "template0", "template1"})
        identity_sql = (
            "SELECT current_database(), oid, inet_server_addr()::text, "
            "inet_server_port(), current_user FROM pg_database "
            "WHERE datname = current_database()"
        )
        with connection.cursor() as cursor:
            cursor.execute(identity_sql)
            identity = list(cursor.fetchone())
        self.assertEqual(identity[0], database["NAME"])
        self.assertEqual(identity[4], database["USER"])
        self.assertTrue(identity[1] and identity[2] and identity[3])
        script = '''import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "venv/Lib/site-packages"))
data = json.load(sys.stdin)
database, identity = data["database"], data["identity"]
assert database["ENGINE"] == "django.db.backends.postgresql"
assert all(database.get(key) for key in ("NAME", "HOST", "PORT", "USER"))
assert database["NAME"] not in {"sales_ai_db", "postgres", "template0", "template1"}
assert database["NAME"] == identity[0] and database["USER"] == identity[4]
assert identity[1] and identity[2] and identity[3]
assert set(database.get("OPTIONS", {})) <= {"sslmode", "connect_timeout"}
from django.conf import settings
settings.DATABASES = {"default": database}
from django.db.backends.postgresql.base import DatabaseWrapper
original_connect = DatabaseWrapper.get_new_connection
def verified_connect(self, params):
    assert self.alias == "default" and self.settings_dict == database
    for parameter, field in (("dbname", "NAME"), ("host", "HOST"),
                             ("port", "PORT"), ("user", "USER"), ("password", "PASSWORD")):
        assert str(params.get(parameter, "")) == str(database.get(field, ""))
    assert not ({"service", "hostaddr"} & params.keys())
    conn = original_connect(self, params)
    try:
        # First SQL is identity-only; no application query precedes verification.
        with conn.cursor() as cursor:
            cursor.execute(data["identity_sql"])
            assert list(cursor.fetchone()) == identity
        conn.rollback()
    except BaseException:
        conn.close()
        raise
    return conn
DatabaseWrapper.get_new_connection = verified_connect
import django
django.setup()
from django.contrib.auth import get_user_model
from apps.sales_requests.submission import submit_request
from uuid import UUID
data["command"]["command_uuid"] = UUID(data["command"]["command_uuid"])
body, status, replayed = submit_request(get_user_model().objects.get(pk=data["user"]), data["visit"], data["command"])
print(json.dumps({"body": body, "status": status, "replayed": replayed}))
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=root, input=json.dumps({"user": self.user.pk,
            "visit": self.visit.pk, "command": command, "database": database,
            "identity": identity, "identity_sql": identity_sql}), text=True, encoding="utf-8", capture_output=True,
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "sales_ai_copilot.settings"}, timeout=40)
        self.assertEqual(result.returncode, 0, "Fresh-process replay failed")
        replay = json.loads(result.stdout)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["body"], original.data)
        self.assertEqual(self.rows(), before)
