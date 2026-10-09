"""Receipt persistence only; no basket/feedback/pricing operation is implemented."""
from datetime import date
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from apps.customers.models import Customer
from apps.visits.models import Salesperson, Visit
from .models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt


class MutationReceiptTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(username="receipt-owner")
        cls.other_actor = get_user_model().objects.create_user(username="receipt-other")
        cls.rep = Salesperson.objects.create(user=cls.actor, employee_code="RECEIPT-SP", first_name="A", last_name="Rep")
        cls.other_rep = Salesperson.objects.create(user=cls.other_actor, employee_code="RECEIPT-OTHER", first_name="B", last_name="Rep")
        cls.customer = Customer.objects.create(customer_code="RECEIPT-C", name="مشتری")
        cls.visit = Visit.objects.create(customer=cls.customer, salesperson=cls.rep, visit_date=date(2026, 10, 8), status="IN_PROGRESS")
        cls.other_visit = Visit.objects.create(customer=cls.customer, salesperson=cls.other_rep, visit_date=date(2026, 10, 8), status="IN_PROGRESS")

    def receipt(self, **kwargs):
        values = {
            "visit": self.visit, "actor": self.actor, "command_uuid": uuid4(),
            "operation": "REJECT_RECOMMENDATION", "intent_fingerprint": "a" * 64,
            "result": {"http_status": 200, "body": {"feedback_event_id": 123}},
        }
        values.update(kwargs)
        return SalesRequestMutationReceipt(**values)

    def raw_insert(self, receipt):
        # Intentional guard bypass to test actual database constraints.
        models.QuerySet(model=SalesRequestMutationReceipt, using="default").bulk_create([receipt])

    def test_success_receipt_before_request_has_no_domain_side_effects(self):
        before = list(Visit.objects.order_by("pk").values())
        receipt = self.receipt()
        receipt.save()
        receipt.refresh_from_db()
        self.assertIsNone(receipt.sales_request_id)
        self.assertIsNone(receipt.applied_revision)
        self.assertIsNotNone(receipt.created_at)
        self.assertEqual(SalesRequest.objects.count(), 0)
        self.assertEqual(SalesRequestLine.objects.count(), 0)
        self.assertEqual(list(Visit.objects.order_by("pk").values()), before)

    def test_receipt_captures_existing_request_revision_and_canonical_result(self):
        request = SalesRequest.objects.create(visit=self.visit, revision=3)
        result = {"http_status": 201, "body": {"request_id": request.pk, "revision": 3, "total": "12345"}}
        receipt = self.receipt(operation="ADD_PRODUCT", sales_request=request, applied_revision=3, result=result)
        receipt.save()
        request.refresh_from_db()
        self.assertEqual(request.revision, 3)
        self.assertEqual(request.status, "DRAFT")
        receipt.refresh_from_db()
        self.assertEqual(receipt.result, result)

    def test_same_command_lookup_preserves_prior_result_without_writes(self):
        receipt = self.receipt()
        receipt.save()
        with CaptureQueriesContext(connection) as queries:
            prior = SalesRequestMutationReceipt.objects.get(visit=self.visit, command_uuid=receipt.command_uuid)
            self.assertEqual(prior.actor_id, self.actor.pk)
            self.assertEqual(prior.intent_fingerprint, receipt.intent_fingerprint)
            self.assertEqual(prior.result, receipt.result)
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries))

    def test_duplicate_command_is_rejected_for_same_or_different_intent(self):
        key = uuid4()
        self.receipt(command_uuid=key).save()
        for fingerprint in ("a" * 64, "b" * 64):
            with self.subTest(fingerprint=fingerprint), self.assertRaises(ValidationError):
                self.receipt(command_uuid=key, intent_fingerprint=fingerprint).save()
            with self.subTest(database=fingerprint), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(self.receipt(command_uuid=key, intent_fingerprint=fingerprint))
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)

    def test_command_uuid_is_scoped_to_visit(self):
        key = uuid4()
        self.receipt(command_uuid=key).save()
        self.receipt(visit=self.other_visit, actor=self.other_actor, command_uuid=key).save()
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 2)

    def test_actor_must_match_persisted_visit_owner(self):
        with self.assertRaises(ValidationError):
            self.receipt(actor=self.other_actor).save()
        self.visit.salesperson = self.other_rep  # Unsaved cache must not grant access.
        with self.assertRaises(ValidationError):
            self.receipt(actor=self.other_actor).save()

    def test_actor_without_visit_owner_profile_is_rejected(self):
        stranger = get_user_model().objects.create_user(username="receipt-no-profile")
        with self.assertRaises(ValidationError):
            self.receipt(actor=stranger).save()

    def test_request_must_match_persisted_visit(self):
        foreign = SalesRequest.objects.create(visit=self.other_visit)
        foreign.visit = self.visit  # Validate the persisted relation.
        with self.assertRaises(ValidationError):
            self.receipt(sales_request=foreign, applied_revision=0).save()

    def test_applied_revision_must_match_request_at_creation(self):
        request = SalesRequest.objects.create(visit=self.visit, revision=3)
        request.revision = 4
        for revision in (2, 4):
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                self.receipt(sales_request=request, applied_revision=revision).save()
        self.receipt(sales_request=request, applied_revision=3).save()

    def test_revision_request_pair_is_model_and_database_enforced(self):
        request = SalesRequest.objects.create(visit=self.visit)
        for changes in ({"applied_revision": 0}, {"sales_request": request}, {"sales_request": request, "applied_revision": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.receipt(**changes).save()
            with self.subTest(database=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(self.receipt(**changes))

    def test_noninteger_revision_is_rejected_without_coercion(self):
        request = SalesRequest.objects.create(visit=self.visit)
        for revision in (True, 0.5, "0"):
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                self.receipt(sales_request=request, applied_revision=revision).save()

    def test_required_uuid_fingerprint_and_result_have_no_fake_defaults(self):
        for changes in ({"command_uuid": None}, {"command_uuid": "bad-uuid"}, {"intent_fingerprint": ""},
                        {"intent_fingerprint": "x" * 64}, {"intent_fingerprint": "a" * 63},
                        {"result": {}}, {"result": []}, {"result": "success"}, {"result": None}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.receipt(**changes).save()
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 0)

    def test_invalid_operation_and_empty_intent_are_database_rejected(self):
        for changes in ({"operation": "SUBMIT"}, {"intent_fingerprint": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.receipt(**changes).save()
            with self.subTest(database=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(self.receipt(**changes))

    def test_all_stage_three_operations_can_be_recorded(self):
        request = SalesRequest.objects.create(visit=self.visit)
        for operation in SalesRequestMutationReceipt.Operation.values:
            self.receipt(operation=operation, sales_request=request, applied_revision=0).save()
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 4)

    def test_receipt_remains_unchanged_when_request_revision_advances(self):
        request = SalesRequest.objects.create(visit=self.visit)
        receipt = self.receipt(sales_request=request, applied_revision=0)
        receipt.save()
        SalesRequest.objects.filter(pk=request.pk, revision=0).update(revision=F("revision") + 1)
        receipt.refresh_from_db()
        self.assertEqual(receipt.applied_revision, 0)
        self.assertEqual(receipt.result["body"]["feedback_event_id"], 123)

    def test_historical_receipt_stays_valid_readable_and_immutable_after_later_revisions(self):
        request = SalesRequest.objects.create(visit=self.visit, revision=1)
        result = {"http_status": 200, "body": {"request_id": request.pk, "revision": 1}}
        receipt = self.receipt(sales_request=request, applied_revision=1, result=result)
        receipt.save()
        before = SalesRequestMutationReceipt.objects.values().get(pk=receipt.pk)
        for revision in (2, 3):
            self.assertEqual(SalesRequest.objects.filter(pk=request.pk, revision=revision - 1).update(revision=F("revision") + 1), 1)
            with CaptureQueriesContext(connection) as queries:
                prior = SalesRequestMutationReceipt.objects.get(visit=self.visit, command_uuid=receipt.command_uuid)
                prior.full_clean()
                self.assertEqual(prior.intent_fingerprint, receipt.intent_fingerprint)
                self.assertEqual(prior.applied_revision, 1)
                self.assertEqual(prior.result, result)
            # Constraint validation may use SAVEPOINT/RELEASE; it must not write rows.
            self.assertTrue(all(not query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for query in queries))
            self.assertEqual(SalesRequestMutationReceipt.objects.values().get(pk=receipt.pk), before)
        with self.assertRaises(ValidationError):
            self.receipt(sales_request=request, applied_revision=1).save()  # New receipt must use current revision 3.
        for operation in (
            prior.save,
            lambda: prior.save(update_fields=["applied_revision"]),
            prior.delete,
            lambda: SalesRequestMutationReceipt.objects.filter(pk=prior.pk).update(applied_revision=3),
            lambda: SalesRequestMutationReceipt.objects.filter(pk=prior.pk).delete(),
            lambda: SalesRequestMutationReceipt.objects.bulk_update([prior], ["applied_revision"]),
            lambda: SalesRequestMutationReceipt.objects.bulk_create([self.receipt()]),
        ):
            with self.assertRaises(ValidationError):
                operation()
        self.assertEqual(SalesRequestMutationReceipt.objects.values().get(pk=receipt.pk), before)

    def test_failed_atomic_command_leaves_no_receipt_or_request(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                request = SalesRequest.objects.create(visit=self.visit)
                self.receipt(sales_request=request, applied_revision=0).save()
                raise RuntimeError("Simulated later command failure")
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 0)
        self.assertEqual(SalesRequest.objects.count(), 0)

    def test_save_and_partial_save_cannot_change_any_receipt_field(self):
        receipt = self.receipt()
        receipt.save()
        before = SalesRequestMutationReceipt.objects.values().get(pk=receipt.pk)
        for field, value in (("actor", self.other_actor), ("visit", self.other_visit),
                             ("command_uuid", uuid4()), ("intent_fingerprint", "b" * 64),
                             ("operation", "ADD_PRODUCT"), ("result", {"changed": True}),
                             ("applied_revision", 1), ("created_at", None)):
            for partial in (False, True):
                receipt.refresh_from_db()
                setattr(receipt, field, value)
                with self.subTest(field=field, partial=partial), self.assertRaises(ValidationError):
                    receipt.save(**({"update_fields": [field]} if partial else {}))
        self.assertEqual(SalesRequestMutationReceipt.objects.values().get(pk=receipt.pk), before)

    def test_new_receipt_partial_save_cannot_freeze_incomplete_data(self):
        receipt = self.receipt()
        with self.assertRaises(ValueError):
            receipt.save(update_fields=["operation"])
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 0)

    def test_instance_and_queryset_delete_are_blocked(self):
        receipt = self.receipt()
        receipt.save()
        for operation in (receipt.delete, lambda: SalesRequestMutationReceipt.objects.filter(pk=receipt.pk).delete()):
            with self.assertRaises(ValidationError):
                operation()
        self.assertTrue(SalesRequestMutationReceipt.objects.filter(pk=receipt.pk).exists())

    def test_queryset_update_and_bulk_writes_are_blocked(self):
        receipt = self.receipt()
        receipt.save()
        receipt.result = {"changed": True}
        for operation in (
            lambda: SalesRequestMutationReceipt.objects.filter(pk=receipt.pk).update(result={"changed": True}),
            lambda: SalesRequestMutationReceipt.objects.bulk_update([receipt], ["result"]),
            lambda: SalesRequestMutationReceipt.objects.bulk_create([self.receipt()]),
        ):
            with self.assertRaises(ValidationError):
                operation()
        receipt.refresh_from_db()
        self.assertEqual(receipt.result["body"]["feedback_event_id"], 123)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)

    def test_visit_actor_and_request_deletion_are_protected(self):
        request = SalesRequest.objects.create(visit=self.visit)
        receipt = self.receipt(sales_request=request, applied_revision=0)
        receipt.save()
        for parent in (self.visit, self.actor, request):
            with self.subTest(parent=type(parent).__name__), self.assertRaises(ProtectedError):
                parent.delete()
        self.assertTrue(SalesRequestMutationReceipt.objects.filter(pk=receipt.pk).exists())

    def test_admin_is_inspection_only(self):
        model_admin = admin.site._registry[SalesRequestMutationReceipt]
        request = RequestFactory().get("/admin/")
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertIsNone(model_admin.actions)
        self.assertEqual(set(model_admin.get_readonly_fields(request)), {field.name for field in SalesRequestMutationReceipt._meta.fields})
