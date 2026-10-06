"""002-I visit outcome read/write/continuity regressions in isolated fixtures."""
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.products.models import Product
from apps.recommendations.models import CustomerRecommendation
from apps.sales.models import Sale, SaleItem
from . import tests_authorization
from .models import Visit, SalesOutcome, FollowUpTask, VisitCustomerSnapshot, VisitCommercialSnapshot
from .services import resolve_recommendation_outcome, build_outcome_analytics_contract, build_recommendation_type_analytics


class VisitRecommendationOutcomeTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.visit = cls.visits[0]
        cls.visit.status = "IN_PROGRESS"
        cls.visit.save()
        cls.rec = cls.recommendations[0]
        cls.alternative = Product.objects.create(
            product_code="OUT-ALT", name="محصول جایگزین", brand=cls.product.brand, category=cls.product.category,
        )
        cls.alt_rec = CustomerRecommendation.objects.create(
            customer=cls.customer, product=cls.alternative, rank=2, score=99,
            recommendation_type="CATEGORY", explanation_snapshot={"signals": [{"name": "repurchase", "score": 5, "active": True}]},
        )
        cls.older_visit = Visit.objects.create(
            customer=cls.customer, salesperson=cls.rep, visit_date=cls.TODAY-timedelta(days=1), status="COMPLETED",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def read(self, visit=None, customer=None):
        return self.client.get(reverse("visit-recommendation-outcomes", args=[(visit or self.visit).pk]),
                               {"customer_code": (customer or self.customer).customer_code})

    def write(self, outcome="PURCHASED", **extra):
        return self.client.post(reverse("sales-outcome-create"), {
            "visit_id": self.visit.pk, "customer_code": self.customer.customer_code,
            "recommendation_id": self.rec.pk, "outcome": outcome, **extra,
        }, content_type="application/json")

    def event(self, **extra):
        return SalesOutcome.objects.create(visit=self.visit, recommendation=self.rec,
                                          outcome=extra.pop("outcome", "PURCHASED"), **extra)

    def test_selected_visit_excludes_other_visit_results_and_empty_is_explicit(self):
        SalesOutcome.objects.create(visit=self.older_visit, recommendation=self.rec, outcome="PURCHASED", quantity=3, sales_amount=700)
        response = self.read()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendation_outcomes"], [])
        self.assertTrue(response.json()["can_record"])
        self.assertEqual(self.read(visit=self.older_visit).json()["recommendation_outcomes"][0]["quantity"], 3)

    def test_repeated_events_and_purchase_fallback_match_existing_resolver(self):
        valued = self.event(quantity=3, sales_amount=700)
        last = self.event(quantity=0, sales_amount=0)
        result = self.read().json()["recommendation_outcomes"][0]
        expected = resolve_recommendation_outcome(self.visit.pk, self.rec.pk)
        self.assertEqual(result["final_outcome"], expected["outcome"])
        for key in ("quantity", "sales_amount", "events_count", "last_event_id"):
            self.assertEqual(result[key], expected[key])
        self.assertEqual(result["last_event_id"], last.pk)
        self.assertEqual(result["quantity"], 3)
        self.assertTrue(SalesOutcome.objects.filter(pk=valued.pk, sales_amount=700).exists())

    def test_equal_timestamps_use_canonical_id_tie_break(self):
        first = self.event(outcome="INTERESTED")
        last = self.event(outcome="REJECTED")
        SalesOutcome.objects.filter(pk__in=[first.pk, last.pk]).update(created_at=timezone.now())
        row = self.read().json()["recommendation_outcomes"][0]
        self.assertEqual(row["last_event_id"], last.pk)
        self.assertEqual(row["final_outcome"], "REJECTED")

    def test_all_five_outcomes_keep_writer_and_resolver_behavior(self):
        for outcome in ("PURCHASED", "INTERESTED", "FOLLOW_UP", "REJECTED", "NOT_PRESENTED"):
            extra = {"follow_up_date": (self.TODAY+timedelta(days=1)).isoformat()} if outcome == "FOLLOW_UP" else {}
            response = self.write(outcome, **extra)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(self.read().json()["recommendation_outcomes"][0]["final_outcome"], outcome)

    def test_follow_up_requires_date_and_preserves_existing_task_sync(self):
        before = list(FollowUpTask.objects.filter(visit=self.visit).values())
        self.assertEqual(self.write("FOLLOW_UP").status_code, 400)
        self.assertEqual(list(FollowUpTask.objects.filter(visit=self.visit).values()), before)
        due = (self.TODAY+timedelta(days=1)).isoformat()
        self.assertEqual(self.write("FOLLOW_UP", follow_up_date=due).status_code, 201)
        task = FollowUpTask.objects.get(visit=self.visit)
        self.assertEqual(task.status, "OPEN")
        self.assertEqual(self.write("REJECTED").status_code, 201)
        task.refresh_from_db()
        self.assertEqual(task.status, "CANCELLED")
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.follow_up_required)

    def test_foreign_wrong_customer_missing_and_revoked_context_have_generic_denial(self):
        missing = self.client.get(reverse("visit-recommendation-outcomes", args=[999999]), {"customer_code": self.customer.customer_code})
        foreign = Visit.objects.create(customer=self.customer, salesperson=self.other_rep, visit_date=self.TODAY, status="IN_PROGRESS")
        for response in (self.read(visit=foreign), self.read(customer=self.other_customer),
                         self.client.get(reverse("visit-recommendation-outcomes", args=[self.visit.pk]))):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, missing.content)
        self.customer.salesperson_assignments.update(is_active=False)
        self.assertEqual(self.read().content, missing.content)
        self.assertEqual(self.write().status_code, 404)
        self.assertFalse(SalesOutcome.objects.filter(visit=self.visit).exists())

    def test_writer_context_cannot_select_other_owned_customer_or_foreign_visit(self):
        for extra in ({"visit_id": self.visits[1].pk}, {"customer_code": self.other_customer.customer_code}):
            self.assertEqual(self.write(**extra).status_code, 404)
        self.assertFalse(SalesOutcome.objects.filter(visit=self.visit).exists())

    def test_non_progress_visits_are_readable_but_not_actionable(self):
        for state in ("PLANNED", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            self.assertFalse(self.read().json()["can_record"])
            self.assertEqual(self.write().status_code, 403)

    def test_staff_and_dual_role_inspection_never_receive_operational_context(self):
        self.user.is_staff = True
        self.user.save()
        for user in (self.staff, self.user):
            self.client.force_login(user)
            self.assertEqual(self.read().status_code, 403)
            self.assertEqual(self.write().status_code, 403)
            page = self.client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk})
            self.assertIsNone(page.context["current_visit"])
            for marker in ("outcomeModal", "outcome-btn", 'id="visitOutcomeRegion"'):
                self.assertNotContains(page, marker)

    def test_legacy_dual_role_and_owned_historical_writer_contract_is_preserved(self):
        self.customer.salesperson_assignments.update(is_active=False)
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(reverse("sales-outcome-create"), {
            "visit_id": self.visit.pk, "recommendation_id": self.rec.pk, "outcome": "INTERESTED",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_inactive_missing_profile_and_anonymous_cannot_read(self):
        self.rep.is_active = False
        self.rep.save()
        self.assertEqual(self.read().status_code, 403)
        self.client.force_login(self.no_profile)
        self.assertEqual(self.read().status_code, 403)
        self.client.logout()
        self.assertEqual(self.read().status_code, 403)

    def test_foreign_visit_never_populates_customer360_operational_controls(self):
        foreign = Visit.objects.create(customer=self.customer, salesperson=self.other_rep, visit_date=self.TODAY, status="IN_PROGRESS")
        response = self.client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": foreign.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["current_visit"])
        self.assertContains(response, "بدون زمینه ویزیت")
        self.assertNotContains(response, 'data-read-url=')

    def test_return_anchor_is_server_derived_and_order_is_unchanged(self):
        url = reverse("product-commercial-brief", args=[self.alternative.product_code])
        response = self.client.get(url, {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk,
                                         "recommendation_id": self.rec.pk, "next": "https://example.invalid/"})
        self.assertEqual(response.context["return_url"], f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}#recommendation-{self.alt_rec.pk}")
        page = self.client.get(response.context["return_url"].split("#")[0])
        self.assertContains(page, f'id="recommendation-{self.alt_rec.pk}" tabindex="-1"')
        self.assertEqual([rec.pk for rec in page.context["recommendations"]], [self.rec.pk, self.alt_rec.pk])

    def test_no_matching_saved_recommendation_returns_to_generic_section(self):
        self.alt_rec.is_active = False
        self.alt_rec.save()
        response = self.client.get(reverse("product-commercial-brief", args=[self.alternative.product_code]),
                                   {"customer_code": self.customer.customer_code})
        self.assertTrue(response.context["return_url"].endswith("#workspace-recommendations"))

    def test_current_customer_pages_reads_and_returns_have_zero_business_writes_and_ai_calls(self):
        urls = [f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}",
                reverse("product-commercial-brief", args=[self.product.product_code])+f"?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}",
                reverse("visit-recommendation-outcomes", args=[self.visit.pk])+f"?customer_code={self.customer.customer_code}"]
        with patch("apps.ai.ollama_client.OllamaClient.generate") as llm, CaptureQueriesContext(connection) as queries:
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200)
        llm.assert_not_called()
        self.assertEqual([q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))], [])

    def test_csrf_enforced_and_successful_form_token_keeps_explicit_writer(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("sales-outcome-create")
        payload = {"visit_id": self.visit.pk, "customer_code": self.customer.customer_code,
                   "recommendation_id": self.rec.pk, "outcome": "INTERESTED"}
        self.assertEqual(client.post(url, payload, content_type="application/json").status_code, 403)
        page = client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk})
        self.assertContains(page, 'name="csrfmiddlewaretoken"')
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, payload, content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_failed_submission_creates_no_false_saved_result(self):
        self.assertEqual(self.write("INVALID").status_code, 400)
        self.assertEqual(self.write(recommendation_id=self.recommendations[1].pk).status_code, 404)
        self.assertEqual(self.read().json()["recommendation_outcomes"], [])

    def test_outcome_keeps_snapshots_ranking_sale_inventory_and_analytics_semantics(self):
        customer_snapshot = VisitCustomerSnapshot.objects.create(visit=self.visit, customer=self.customer)
        commercial_snapshot = VisitCommercialSnapshot.objects.create(visit=self.visit, customer=self.customer, salesperson=self.rep)
        snapshots = [VisitCustomerSnapshot.objects.filter(pk=customer_snapshot.pk).values().get(),
                     VisitCommercialSnapshot.objects.filter(pk=commercial_snapshot.pk).values().get()]
        rec_before = CustomerRecommendation.objects.filter(pk=self.rec.pk).values().get()
        sale_counts = (Sale.objects.count(), SaleItem.objects.count())
        self.assertEqual(self.write("PURCHASED", quantity=2, sales_amount=100).status_code, 201)
        self.assertEqual(self.write("NOT_PRESENTED", recommendation_id=self.alt_rec.pk).status_code, 201)
        self.assertEqual(VisitCustomerSnapshot.objects.filter(pk=customer_snapshot.pk).values().get(), snapshots[0])
        self.assertEqual(VisitCommercialSnapshot.objects.filter(pk=commercial_snapshot.pk).values().get(), snapshots[1])
        self.assertEqual(CustomerRecommendation.objects.filter(pk=self.rec.pk).values().get(), rec_before)
        self.assertEqual((Sale.objects.count(), SaleItem.objects.count()), sale_counts)
        canonical = build_outcome_analytics_contract(customer=self.customer)["summary"]
        types = build_recommendation_type_analytics(customer=self.customer)["summary"]
        self.assertEqual(canonical["presented"], 1)
        self.assertEqual(canonical["not_presented"], 1)
        self.assertEqual(types["conversion_rate"], canonical["conversion_rate"])
