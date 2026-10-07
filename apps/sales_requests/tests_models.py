"""Isolated persistence tests; no price, basket or submission service is exercised."""
from decimal import Decimal
from uuid import uuid4

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.inventory.models import Inventory
from apps.products.models import Product, ProductDemoPrice
from apps.recommendations.models import CustomerRecommendation, RecommendationFeedbackEvent
from apps.sales.models import Sale, SaleItem
from apps.visits import tests_authorization
from apps.visits.models import FollowUpTask, SalesOutcome, Visit, VisitCommercialSnapshot, VisitCustomerSnapshot
from .models import SalesRequest, SalesRequestAcknowledgement, SalesRequestLine


class PersistenceFoundationTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.visit = cls.visits[0]
        cls.visit.status = Visit.VisitStatus.IN_PROGRESS
        cls.visit.save(update_fields=["status"])
        cls.rec = cls.recommendations[0]
        cls.extra_product = Product.objects.create(
            product_code="FOUNDATION-OTHER", name="محصول دیگر", brand=cls.product.brand, category=cls.product.category,
        )

    def draft(self, **kwargs):
        return SalesRequest.objects.create(visit=kwargs.pop("visit", self.visit), **kwargs)

    def line(self, request, **kwargs):
        return SalesRequestLine.objects.create(sales_request=request, product=kwargs.pop("product", self.product), quantity=kwargs.pop("quantity", 1), **kwargs)

    def recommended_line(self, request):
        return self.line(request, selection_source="RECOMMENDATION", recommendation=self.rec,
                         lineage_snapshot={"recommendation_id": self.rec.pk, "rank": self.rec.rank, "reason": self.rec.reason})

    def quoted_line(self, request):
        # Explicit fixture snapshots, not a pricing-provider implementation.
        return self.line(request, product_snapshot={"id": self.product.pk, "code": self.product.product_code, "name": self.product.name, "unit": self.product.unit},
                         base_unit_price=Decimal("1000"), discount_percentage=Decimal("10"), discount_amount=Decimal("100"),
                         final_unit_price=Decimal("900"), line_total=Decimal("900"), currency="TOMAN",
                         pricing_source="isolated-fixture", pricing_version="fixture-v1")

    def submitted(self):
        request = self.draft()
        line = self.quoted_line(request)
        request.status = "SUBMITTED"
        request.number = f"FIXTURE-{request.pk}"
        request.submission_key = uuid4()
        request.submission_intent_hash = "a" * 64
        request.submitted_at = timezone.now()
        request.base_total = Decimal("1000")
        request.discount_total = Decimal("100")
        request.final_total = Decimal("900")
        request.currency = "TOMAN"
        request.customer_snapshot = {"id": request.customer_id, "code": request.customer.customer_code, "name": request.customer.name}
        request.salesperson_snapshot = {"id": request.salesperson_id, "employee_code": request.salesperson.employee_code, "name": request.salesperson.full_name}
        request.pricing_snapshot = {"source": "isolated-fixture", "version": "fixture-v1"}
        request.prepared_message_snapshot = "درخواست فروش ثبت شده است؛ این پیام فقط نمایش داده می‌شود."
        request.save()
        return request, line

    def feedback(self, request=None, line=None, **kwargs):
        return RecommendationFeedbackEvent.objects.create(
            visit=kwargs.pop("visit", self.visit), recommendation=kwargs.pop("recommendation", self.rec),
            sales_request=request, line=line, event_type=kwargs.pop("event_type", "REJECTED"),
            reason_code=kwargs.pop("reason_code", "NOT_INTERESTED"),
            lineage_snapshot=kwargs.pop("lineage_snapshot", {"recommendation_id": self.rec.pk, "rank": self.rec.rank}), **kwargs,
        )

    def raw_insert(self, record):
        # Deliberately bypass model validation to exercise actual DB constraints.
        models.QuerySet(model=type(record), using="default").bulk_create([record])

    def test_draft_defaults_and_authoritative_owner_are_not_duplicated(self):
        request = self.draft()
        self.assertEqual(request.status, "DRAFT")
        self.assertEqual(request.revision, 0)
        self.assertEqual(request.customer_id, self.visit.customer_id)
        self.assertEqual(request.salesperson_id, self.visit.salesperson_id)
        self.assertEqual(request.customer, self.customer)
        self.assertEqual(request.salesperson, self.rep)
        self.assertNotIn("customer", {f.name for f in SalesRequest._meta.fields})
        self.assertNotIn("salesperson", {f.name for f in SalesRequest._meta.fields})
        for field in ("number", "submission_key", "submitted_at", "base_total", "discount_total", "final_total", "currency"):
            self.assertIsNone(getattr(request, field))

    def test_one_request_per_visit_has_model_and_database_protection(self):
        self.draft()
        with self.assertRaises(ValidationError):
            self.draft()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_insert(SalesRequest(visit=self.visit))

    def test_status_and_revision_have_database_checks(self):
        for changes in ({"status": "APPROVED"}, {"revision": -1}, {"submitted_at": timezone.now()}, {"status": "SUBMITTED"}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(SalesRequest(visit=self.visit, **changes))
        with self.assertRaises(ValidationError):
            self.draft(status="INVOICED")

    def test_revision_supports_guarded_compare_and_set_without_other_effects(self):
        request = self.draft()
        changed = SalesRequest.objects.filter(pk=request.pk, status="DRAFT", revision=0).update(revision=F("revision") + 1)
        self.assertEqual(changed, 1)
        self.assertEqual(SalesRequest.objects.filter(pk=request.pk, status="DRAFT", revision=0).update(revision=F("revision") + 1), 0)
        request.refresh_from_db()
        self.assertEqual(request.revision, 1)
        self.assertEqual(request.status, "DRAFT")

    def test_request_cannot_move_to_a_different_visit(self):
        request = self.draft()
        request.visit = self.visits[1]
        with self.assertRaises(ValidationError):
            request.save()
        request.refresh_from_db()
        self.assertEqual(request.visit_id, self.visit.pk)

    def test_line_requires_positive_quantity_in_model_and_database(self):
        request = self.draft()
        for quantity in (0, -1):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.line(request, quantity=quantity)
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(SalesRequestLine(sales_request=request, product=self.product, quantity=quantity))

    def test_fractional_and_boolean_quantities_are_not_silently_truncated(self):
        request = self.draft()
        for quantity in (1.5, Decimal("1.5"), True):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.line(request, quantity=quantity)
            with self.assertRaises(ValidationError):
                SalesRequestLine(sales_request=request, product=self.product, quantity=quantity).full_clean()

    def test_draft_line_prices_are_unknown_not_fake_zero(self):
        line = self.line(self.draft())
        for field in ("base_unit_price", "discount_percentage", "discount_amount", "final_unit_price", "line_total", "currency", "pricing_source", "pricing_version"):
            self.assertIsNone(getattr(line, field))

    def test_duplicate_selected_product_is_prevented_and_removed_history_can_coexist(self):
        request = self.draft()
        original = self.line(request)
        with self.assertRaises(ValidationError):
            self.line(request)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_insert(SalesRequestLine(sales_request=request, product=self.product, quantity=2))
        original.is_selected = False
        original.removed_at = timezone.now()
        original.save()
        replacement = self.line(request)
        self.assertNotEqual(original.pk, replacement.pk)
        self.assertEqual(request.lines.count(), 2)
        self.assertEqual(request.lines.filter(is_selected=True).count(), 1)

    def test_removal_metadata_has_database_consistency(self):
        request = self.draft()
        for changes in ({"is_selected": False}, {"removed_at": timezone.now()}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(SalesRequestLine(sales_request=request, product=self.product, quantity=1, **changes))

    def test_ordinary_line_has_optional_recommendation_and_no_generated_feedback(self):
        line = self.line(self.draft())
        self.assertIsNone(line.recommendation_id)
        self.assertEqual(line.selection_source, "ORDINARY")
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 0)

    def test_recommended_line_preserves_link_and_supplied_evidence(self):
        line = self.recommended_line(self.draft())
        line.refresh_from_db()
        self.assertEqual(line.recommendation_id, self.rec.pk)
        self.assertEqual(line.lineage_snapshot["rank"], self.rec.rank)
        self.assertEqual(line.lineage_snapshot["reason"], self.rec.reason)

    def test_line_rejects_foreign_customer_or_wrong_product_recommendations(self):
        request = self.draft()
        for rec in (self.recommendations[1], CustomerRecommendation.objects.create(customer=self.customer, product=self.extra_product, recommendation_type="CATEGORY", score=30, rank=2)):
            with self.subTest(rec=rec.pk), self.assertRaises(ValidationError):
                self.line(request, selection_source="RECOMMENDATION", recommendation=rec, lineage_snapshot={"recommendation_id": rec.pk})

    def test_line_source_and_recommendation_pair_are_checked_by_database(self):
        request = self.draft()
        for changes in ({"selection_source": "RECOMMENDATION"}, {"recommendation": self.rec}, {"selection_source": "UNKNOWN"}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(SalesRequestLine(sales_request=request, product=self.product, quantity=1, **changes))

    def test_line_identity_and_evidence_cannot_be_rewritten(self):
        line = self.recommended_line(self.draft())
        line.lineage_snapshot = {"recommendation_id": self.rec.pk, "rank": 99}
        with self.assertRaises(ValidationError):
            line.save()
        line.refresh_from_db()
        line.product = self.extra_product
        with self.assertRaises(ValidationError):
            line.save()

    def test_snapshot_shapes_and_numeric_bounds_are_validated(self):
        request = self.draft()
        for changes in ({"base_unit_price": -1}, {"discount_percentage": 101}, {"discount_percentage": -1}, {"currency": "RIAL"}, {"product_snapshot": []}, {"product_snapshot": {"id": self.extra_product.pk}}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.line(request, **changes)

    def test_submission_requires_supplied_complete_snapshots(self):
        request = self.draft()
        self.line(request)
        request.status = "SUBMITTED"
        with self.assertRaises(ValidationError):
            request.save()
        request.refresh_from_db()
        self.assertEqual(request.status, "DRAFT")

    def test_submitted_header_and_pricing_are_immutable_without_visit_completion(self):
        request, line = self.submitted()
        request.refresh_from_db()
        self.assertEqual(request.final_total, Decimal("900"))
        self.assertEqual(request.prepared_message_snapshot, "درخواست فروش ثبت شده است؛ این پیام فقط نمایش داده می‌شود.")
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")
        request.status = "DRAFT"
        with self.assertRaises(ValidationError):
            request.save()
        for field, value in (("note", "changed"), ("final_total", Decimal("10")), ("prepared_message_snapshot", "changed")):
            request.refresh_from_db()
            setattr(request, field, value)
            with self.assertRaises(ValidationError):
                request.save()
        with self.assertRaises(ValidationError):
            request.delete()

    def test_submission_customer_and_owner_snapshots_must_match_visit(self):
        request, line = self.submitted()
        # Separate visits are needed because the one-request relation is unique.
        other_visit = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=self.TODAY, status="IN_PROGRESS")
        other = self.draft(visit=other_visit)
        self.quoted_line(other)
        for field in ("status", "number", "submission_intent_hash", "submitted_at", "base_total", "discount_total", "final_total", "currency", "pricing_snapshot", "prepared_message_snapshot"):
            setattr(other, field, getattr(request, field))
        other.number = "OTHER-FIXTURE"
        other.submission_key = uuid4()
        other.customer_snapshot = {**request.customer_snapshot, "id": self.other_customer.pk}
        other.salesperson_snapshot = dict(request.salesperson_snapshot)
        with self.assertRaises(ValidationError):
            other.save()
        other.customer_snapshot = dict(request.customer_snapshot)
        other.salesperson_snapshot = {**request.salesperson_snapshot, "id": self.other_rep.pk}
        with self.assertRaises(ValidationError):
            other.save()

    def test_submitted_line_cannot_change_delete_or_be_added_even_from_stale_parent(self):
        request, line = self.submitted()
        for field, value in (("quantity", 2), ("line_total", Decimal("10")), ("is_selected", False), ("pricing_version", "different")):
            line.refresh_from_db()
            setattr(line, field, value)
            with self.assertRaises(ValidationError):
                line.save()
        with self.assertRaises(ValidationError):
            line.delete()
        request.status = "DRAFT"  # Unsaved stale/cached parent does not permit writes.
        with self.assertRaises(ValidationError):
            self.line(request, product=self.extra_product)

    def test_queryset_and_bulk_writes_cannot_bypass_submitted_protection(self):
        request, line = self.submitted()
        for call in (
            lambda: SalesRequest.objects.filter(pk=request.pk).update(note="bypass"),
            lambda: SalesRequest.objects.filter(pk=request.pk).update(revision=F("revision") + 1),
            lambda: SalesRequest.objects.bulk_update([request], ["note"]),
            lambda: SalesRequest.objects.filter(pk=request.pk).delete(),
            lambda: SalesRequestLine.objects.filter(pk=line.pk).update(quantity=2),
            lambda: SalesRequestLine.objects.bulk_update([line], ["quantity"]),
            lambda: SalesRequestLine.objects.filter(pk=line.pk).delete(),
            lambda: SalesRequestLine.objects.bulk_create([SalesRequestLine(sales_request=request, product=self.extra_product, quantity=1)]),
        ):
            with self.subTest(call=call), self.assertRaises(ValidationError):
                call()

    def test_referenced_visit_product_recommendation_are_protected(self):
        line = self.recommended_line(self.draft())
        for record in (self.visit, self.product, self.rec):
            with self.subTest(record=type(record).__name__), self.assertRaises(ProtectedError):
                record.delete()

    def test_recommendation_deactivation_preserves_saved_lineage(self):
        line = self.recommended_line(self.draft())
        CustomerRecommendation.objects.filter(pk=self.rec.pk).update(is_active=False)
        line.quantity = 2
        line.save()
        line.refresh_from_db()
        self.assertEqual(line.lineage_snapshot["recommendation_id"], self.rec.pk)

    def test_add_then_remove_history_is_explicit_append_only_and_no_rejection(self):
        request = self.draft()
        line = self.recommended_line(request)
        added = self.feedback(request, line, event_type="ADDED_TO_REQUEST", reason_code="")
        line.is_selected = False
        line.removed_at = timezone.now()
        line.save()
        removed = self.feedback(request, line, event_type="REMOVED_FROM_REQUEST", reason_code="")
        self.assertEqual(list(request.feedback_events.values_list("event_type", flat=True)), ["ADDED_TO_REQUEST", "REMOVED_FROM_REQUEST"])
        self.assertEqual(request.lines.filter(is_selected=True).count(), 0)
        self.assertEqual(RecommendationFeedbackEvent.objects.filter(event_type="REJECTED").count(), 0)
        added.refresh_from_db()
        self.assertEqual(added.event_type, "ADDED_TO_REQUEST")
        for event in (added, removed):
            event.note = "rewrite"
            with self.assertRaises(ValidationError):
                event.save()
            with self.assertRaises(ValidationError):
                event.delete()
        with self.assertRaises(ValidationError):
            RecommendationFeedbackEvent.objects.all().update(note="rewrite")
        with self.assertRaises(ValidationError):
            RecommendationFeedbackEvent.objects.all().delete()

    def test_rejection_reason_does_not_schedule_a_followup(self):
        before = FollowUpTask.objects.count()
        event = self.feedback(reason_code="LATER", note="یادداشت اختیاری")
        self.assertEqual(event.event_type, "REJECTED")
        self.assertEqual(FollowUpTask.objects.count(), before)

    def test_feedback_rejects_wrong_customer_request_or_line(self):
        request = self.draft()
        line = self.recommended_line(request)
        ordinary = self.line(request, product=self.extra_product)
        for kwargs in ({"visit": self.visits[1]}, {"recommendation": self.recommendations[1]}, {"lineage_snapshot": {"recommendation_id": 999}}, {"line": ordinary}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.feedback(request, kwargs.pop("line", line), **kwargs)

    def test_feedback_database_checks_require_line_for_acceptance_and_reason_for_rejection(self):
        for changes in ({"event_type": "PURCHASED"}, {"event_type": "ADDED_TO_REQUEST"}, {"event_type": "REJECTED", "reason_code": ""}):
            values = {"event_type": "REJECTED", "reason_code": "NOT_INTERESTED", **changes}
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(RecommendationFeedbackEvent(visit=self.visit, recommendation=self.rec, lineage_snapshot={"recommendation_id": self.rec.pk}, **values))

    def test_acknowledgement_is_separate_unique_append_only_without_completion(self):
        request, line = self.submitted()
        before = SalesRequest.objects.values().get(pk=request.pk)
        ack = SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep, metadata={"source": "isolated-fixture"})
        self.assertEqual(SalesRequest.objects.values().get(pk=request.pk), before)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")
        with self.assertRaises(ValidationError):
            SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        ack.metadata = {"changed": True}
        with self.assertRaises(ValidationError):
            ack.save()
        with self.assertRaises(ValidationError):
            ack.delete()

    def test_acknowledgement_rejects_draft_or_wrong_actor(self):
        request = self.draft()
        with self.assertRaises(ValidationError):
            SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        request.status = "SUBMITTED"  # Cached, unsaved status is not authoritative.
        with self.assertRaises(ValidationError):
            SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        request.refresh_from_db()
        # Remove the empty draft through its validated instance, then build a fixture.
        request.delete()
        request, line = self.submitted()
        with self.assertRaises(ValidationError):
            SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.other_rep)

    def test_demo_price_is_explicit_unique_current_data_without_provider_defaults(self):
        with self.assertRaises(ValidationError):
            ProductDemoPrice.objects.create(product=self.product)
        price = ProductDemoPrice.objects.create(product=self.product, base_price=Decimal("12345"), currency="TOMAN", source="controlled-fixture", source_version="v1")
        self.assertEqual(price.base_price, Decimal("12345"))
        with self.assertRaises(ValidationError):
            ProductDemoPrice.objects.create(product=self.product, base_price=100, currency="TOMAN", source="fixture", source_version="v2")
        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_demo_price_database_rejects_negative_currency_and_missing_source(self):
        for changes in ({"base_price": -1}, {"currency": "RIAL"}, {"source": ""}, {"source_version": ""}):
            values = {"base_price": Decimal("100"), "currency": "TOMAN", "source": "fixture", "source_version": "v1", **changes}
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                self.raw_insert(ProductDemoPrice(product=self.product, **values))

    def test_closed_visit_retains_draft_without_submission(self):
        request = self.draft()
        self.line(request)
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        request.refresh_from_db()
        self.assertEqual(request.status, "DRAFT")
        self.assertIsNone(request.submitted_at)
        self.assertEqual(request.lines.count(), 1)
        request.note = "closed draft edit"
        with self.assertRaises(ValidationError):
            request.save()
        line = request.lines.get()
        line.quantity = 2
        with self.assertRaises(ValidationError):
            line.save()
        with self.assertRaises(ValidationError):
            SalesRequest.objects.filter(pk=request.pk).update(revision=F("revision") + 1)

    def test_new_persistence_has_no_legacy_sales_snapshot_stock_or_outcome_effects(self):
        Inventory.objects.create(product=self.product, available_quantity=10)
        VisitCustomerSnapshot.objects.create(visit=self.visit, customer=self.customer)
        VisitCommercialSnapshot.objects.create(visit=self.visit, customer=self.customer, salesperson=self.rep)
        tracked = (Sale, SaleItem, SalesOutcome, FollowUpTask, Inventory, VisitCustomerSnapshot, VisitCommercialSnapshot, Visit)
        before = {model: list(model.objects.order_by("pk").values()) for model in tracked}
        request, line = self.submitted()
        self.feedback(reason_code="LATER")
        SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        self.assertEqual({model: list(model.objects.order_by("pk").values()) for model in tracked}, before)

    def test_all_new_admins_are_inspection_only(self):
        request = RequestFactory().get("/admin/")
        request.user = self.staff
        for model in (SalesRequest, SalesRequestLine, SalesRequestAcknowledgement, RecommendationFeedbackEvent, ProductDemoPrice):
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
                self.assertEqual(set(model_admin.get_readonly_fields(request)), {field.name for field in model._meta.fields})

    def test_line_and_feedback_validate_persisted_not_unsaved_recommendation_identity(self):
        request = self.draft()
        foreign = self.recommendations[1]
        foreign.customer = self.customer
        foreign.product = self.product
        with self.assertRaises(ValidationError):
            self.line(request, selection_source="RECOMMENDATION", recommendation=foreign, lineage_snapshot={"recommendation_id": foreign.pk})
        with self.assertRaises(ValidationError):
            self.feedback(recommendation=foreign, lineage_snapshot={"recommendation_id": foreign.pk})

    def test_nonexistent_recommendation_fails_as_validation_error(self):
        request = self.draft()
        with self.assertRaises(ValidationError):
            self.line(request, selection_source="RECOMMENDATION", recommendation_id=999999, lineage_snapshot={"recommendation_id": 999999})
        with self.assertRaises(ValidationError):
            self.feedback(recommendation_id=999999)

    def test_submitted_line_requires_identity_labels_and_unit_not_only_foreign_key(self):
        line = self.quoted_line(self.draft())
        line.product_snapshot.pop("unit")
        line.save()  # Draft enrichment is allowed; submitted completeness is stricter.
        with self.assertRaises(ValidationError) as failure:
            line.validate_submission_snapshot()
        self.assertIn("product_snapshot", failure.exception.message_dict)

    def test_complete_header_cannot_freeze_an_unpriced_line(self):
        reference, _ = self.submitted()
        visit = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=self.TODAY, status="IN_PROGRESS")
        draft = self.draft(visit=visit)
        self.line(draft)
        for field in ("status", "submission_intent_hash", "submitted_at", "base_total", "discount_total", "final_total", "currency", "customer_snapshot", "salesperson_snapshot", "pricing_snapshot", "prepared_message_snapshot"):
            setattr(draft, field, getattr(reference, field))
        draft.number = "UNPRICED-FIXTURE"
        draft.submission_key = uuid4()
        with self.assertRaises(ValidationError) as failure:
            draft.save()
        self.assertIn("base_unit_price", failure.exception.message_dict)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")


class PartialSubmissionSaveRegressionTests(TestCase):
    TODAY = PersistenceFoundationTests.TODAY
    draft = PersistenceFoundationTests.draft
    line = PersistenceFoundationTests.line
    quoted_line = PersistenceFoundationTests.quoted_line
    submitted = PersistenceFoundationTests.submitted
    feedback = PersistenceFoundationTests.feedback

    @classmethod
    def setUpTestData(cls):
        PersistenceFoundationTests.setUpTestData.__func__(cls)

    def ready_for_submission(self):
        request = self.draft()
        self.quoted_line(request)
        request.number = f"PARTIAL-REGRESSION-{request.pk}"
        request.submission_key = uuid4()
        request.submission_intent_hash = "b" * 64
        request.base_total = Decimal("1000")
        request.discount_total = Decimal("100")
        request.final_total = Decimal("900")
        request.currency = "TOMAN"
        request.save()
        before = SalesRequest.objects.values().get(pk=request.pk)
        request.status = "SUBMITTED"
        request.submitted_at = timezone.now()
        request.customer_snapshot = {"id": self.customer.pk, "code": self.customer.customer_code, "name": self.customer.name}
        request.salesperson_snapshot = {"id": self.rep.pk, "employee_code": self.rep.employee_code, "name": self.rep.full_name}
        request.pricing_snapshot = {"source": "isolated-fixture", "version": "fixture-v1"}
        request.prepared_message_snapshot = "درخواست فروش ثبت شده است؛ این پیام فقط نمایش داده می‌شود."
        request.full_clean()  # The entire in-memory submission is valid.
        return request, before

    def test_partial_transition_is_rejected_before_any_persistence(self):
        from django.db import connection

        request, before = self.ready_for_submission()
        complete_fields = [field.name for field in SalesRequest._meta.concrete_fields if not field.primary_key]
        for fields in (["status", "submitted_at"], ("status", "submitted_at"), {"status", "submitted_at"}, ["status"], [], complete_fields):
            with self.subTest(fields=fields), CaptureQueriesContext(connection) as queries:
                with self.assertRaises(ValidationError):
                    request.save(update_fields=fields)
                self.assertFalse(any(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for query in queries))
            self.assertEqual(SalesRequest.objects.values().get(pk=request.pk), before)
        request.refresh_from_db()
        self.assertEqual(request.status, "DRAFT")
        self.assertIsNone(request.submitted_at)
        self.assertEqual(request.customer_snapshot, {})
        self.assertEqual(request.salesperson_snapshot, {})
        self.assertEqual(request.pricing_snapshot, {})
        self.assertEqual(request.prepared_message_snapshot, "")

    def test_full_save_after_rejected_partial_persists_complete_submission(self):
        request, before = self.ready_for_submission()
        with self.assertRaises(ValidationError):
            request.save(update_fields=["status", "submitted_at"])
        expected = {field: getattr(request, field) for field in ("status", "number", "submission_key", "submission_intent_hash", "submitted_at", "base_total", "discount_total", "final_total", "currency", "customer_snapshot", "salesperson_snapshot", "pricing_snapshot", "prepared_message_snapshot")}
        request.save()
        request.refresh_from_db()
        self.assertEqual({field: getattr(request, field) for field in expected}, expected)
        self.assertNotEqual(request.customer_snapshot, before["customer_snapshot"])
        self.assertEqual(request.lines.get().line_total, Decimal("900"))
        request.note = "immutable after full save"
        with self.assertRaises(ValidationError):
            request.save()

    def test_explicit_update_fields_none_is_a_full_valid_save(self):
        request, _ = self.ready_for_submission()
        request.save(update_fields=None)
        request.refresh_from_db()
        self.assertEqual(request.status, "SUBMITTED")
        self.assertEqual(request.customer_snapshot["id"], self.customer.pk)
        self.assertTrue(request.prepared_message_snapshot)

    def test_draft_header_partial_save_keeps_existing_projection_behavior(self):
        request = self.draft()
        request.note = "saved note"
        request.pricing_snapshot = {"not_persisted": True}
        request.save(update_fields=["note"])
        request.refresh_from_db()
        self.assertEqual(request.note, "saved note")
        self.assertEqual(request.pricing_snapshot, {})
        self.assertEqual(request.status, "DRAFT")
        self.assertIsNone(request.submitted_at)

    def test_draft_line_partial_save_does_not_freeze_or_expand_fields(self):
        line = self.line(self.draft())
        line.quantity = 2
        line.pricing_source = "not persisted"
        line.save(update_fields=["quantity"])
        line.refresh_from_db()
        self.assertEqual(line.quantity, 2)
        self.assertIsNone(line.pricing_source)
        self.assertEqual(line.sales_request.status, "DRAFT")

    def test_new_append_only_partial_saves_do_not_insert_records(self):
        request, _ = self.submitted()
        event = RecommendationFeedbackEvent(visit=self.visit, recommendation=self.rec, event_type="REJECTED", reason_code="NOT_INTERESTED", lineage_snapshot={"recommendation_id": self.rec.pk})
        acknowledgement = SalesRequestAcknowledgement(sales_request=request, actor=self.rep)
        for record, field in ((event, "note"), (acknowledgement, "metadata")):
            before = type(record).objects.count()
            with self.subTest(model=type(record).__name__), self.assertRaises(ValueError):
                record.save(update_fields=[field])
            self.assertEqual(type(record).objects.count(), before)

    def test_all_24_normal_orm_immutability_guards_remain_blocked(self):
        request, line = self.submitted()
        event = self.feedback()
        acknowledgement = SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        for record, field, value in ((request, "note", "change"), (line, "quantity", 2), (event, "note", "change"), (acknowledgement, "metadata", {"change": True})):
            model = type(record)
            before = model.objects.values().get(pk=record.pk)
            operations = (
                ("save", lambda: record.save()),
                ("delete", lambda: record.delete()),
                ("queryset update", lambda: model.objects.filter(pk=record.pk).update(**{field: value})),
                ("queryset delete", lambda: model.objects.filter(pk=record.pk).delete()),
                ("bulk update", lambda: model.objects.bulk_update([record], [field])),
                ("bulk create", lambda: model.objects.bulk_create([record])),
            )
            for name, operation in operations:
                with self.subTest(model=model.__name__, operation=name), self.assertRaises(ValidationError):
                    operation()
                self.assertEqual(model.objects.values().get(pk=record.pk), before)

    def test_existing_submitted_partial_saves_and_unsaved_reversion_still_fail(self):
        request, line = self.submitted()
        event = self.feedback()
        acknowledgement = SalesRequestAcknowledgement.objects.create(sales_request=request, actor=self.rep)
        for record, field in ((request, "note"), (line, "quantity"), (event, "note"), (acknowledgement, "metadata")):
            before = type(record).objects.values().get(pk=record.pk)
            with self.subTest(model=type(record).__name__), self.assertRaises(ValidationError):
                record.save(update_fields=[field])
            self.assertEqual(type(record).objects.values().get(pk=record.pk), before)
        request.status = "DRAFT"
        request.note = "unsaved reversal cannot bypass persisted-state protection"
        with self.assertRaises(ValidationError):
            request.save(update_fields=["note"])
        request.refresh_from_db()
        self.assertEqual(request.status, "SUBMITTED")
        self.assertEqual(request.note, "")
