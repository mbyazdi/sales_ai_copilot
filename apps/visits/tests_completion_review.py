"""002-J review and optional completion guard; mutations use isolated fixtures."""
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.recommendations.models import CustomerRecommendation
from apps.products.models import Product
from .models import (CustomerAssignment, FollowUpTask, SalesOutcome, Visit,
                     VisitCustomerSnapshot, VisitCommercialSnapshot)
from .services import build_post_visit_intelligence
from . import tests_authorization


class VisitCompletionReviewTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.visit = cls.visits[0]
        cls.visit.status = "IN_PROGRESS"
        cls.visit.save()
        cls.rec = cls.recommendations[0]

    def setUp(self):
        self.client.force_login(self.user)

    def review(self, visit=None, code=None, **query):
        return self.client.get(reverse("visit-completion-review", args=[
            code or self.customer.customer_code, (visit or self.visit).pk]), query)

    def complete(self, visit=None, **body):
        return self.client.post(reverse("visit-complete", args=[(visit or self.visit).pk]),
                                body, content_type="application/json")

    def extra_recommendation(self, rank):
        product = Product.objects.create(product_code=f"REVIEW-{rank}", name="محصول آزمایشی",
            brand=self.product.brand, category=self.product.category)
        return CustomerRecommendation.objects.create(customer=self.customer, product=product,
            rank=rank, score=50, recommendation_type="CROSS_SELL")

    def test_authorized_review_and_return_preserve_visit_and_recommendation(self):
        response = self.review(recommendation_id=self.rec.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertIn(f"visit_id={self.visit.pk}", response.context["guided_url"])
        self.assertIn(f"recommendation_id={self.rec.pk}", response.context["guided_url"])
        self.assertContains(response, "پیشنهادهای دارای نتیجه ثبت‌شده")
        self.assertContains(response, 'id="finishVisitDialog"')
        self.assertContains(response, 'id="finishVisitButton" class="ds-button" type="button" disabled')

    def test_invalid_or_foreign_recommendation_is_not_carried_back(self):
        for value in (self.recommendations[1].pk, "javascript:alert(1)", "9" * 30):
            response = self.review(recommendation_id=value)
            self.assertNotIn("recommendation_id", response.context["guided_url"])

    def test_foreign_visit_and_customer_mismatch_have_generic_denial(self):
        foreign = Visit.objects.create(customer=self.customer, salesperson=self.other_rep, visit_date=self.TODAY)
        for visit in (foreign, self.visits[1]):
            response = self.review(visit=visit)
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, self.other_customer.phone, status_code=404)
            result = self.complete(visit=visit, customer_code=self.customer.customer_code)
            self.assertEqual(result.status_code, 404)
            self.assertEqual(result.json()["detail"], "زمینه ویزیت در دسترس نیست.")

    def test_revoked_access_denies_review_and_contextual_completion(self):
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        self.assertEqual(self.review().status_code, 404)
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 404)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_anonymous_missing_and_inactive_profile_rejected(self):
        self.client.logout()
        self.assertEqual(self.review().status_code, 403)
        self.client.force_login(self.no_profile)
        self.assertEqual(self.review().status_code, 403)
        self.rep.is_active = False
        self.rep.save()
        self.client.force_login(self.user)
        self.assertEqual(self.review().status_code, 403)

    def test_staff_and_dual_role_cannot_operate_new_flow(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.review().status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.review().status_code, 403)
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 403)
        # Existing legacy own-visit callers are deliberately unchanged.
        self.assertEqual(self.complete().status_code, 200)

    def test_review_get_has_no_business_writes_llm_or_task_creation(self):
        tasks = list(FollowUpTask.objects.values())
        with patch("apps.ai.ollama_client.OllamaClient.generate") as llm, CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.review().status_code, 200)
        llm.assert_not_called()
        writes = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        self.assertEqual(writes, [])
        self.assertEqual(list(FollowUpTask.objects.values()), tasks)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_review_post_is_not_a_completion_path(self):
        url = reverse("visit-completion-review", args=[self.customer.customer_code, self.visit.pk])
        self.assertEqual(self.client.post(url).status_code, 405)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_canonical_five_counts_not_events_and_cross_visit_isolation(self):
        for rank, outcome in enumerate(("PURCHASED", "INTERESTED", "FOLLOW_UP", "REJECTED", "NOT_PRESENTED"), 1):
            rec = self.extra_recommendation(rank + 5)
            SalesOutcome.objects.create(visit=self.visit, recommendation=rec, outcome="INTERESTED")
            SalesOutcome.objects.create(visit=self.visit, recommendation=rec, outcome=outcome)
        other = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=self.TODAY)
        SalesOutcome.objects.create(visit=other, recommendation=self.rec, outcome="PURCHASED")
        response = self.review()
        summary = response.context["summary"]
        self.assertEqual(summary, build_post_visit_intelligence(self.visit)["summary"])
        self.assertEqual(summary["resolved_recommendations"], 5)
        for key in ("purchased", "interested", "follow_up", "rejected", "not_presented"):
            self.assertEqual(summary[key], 1)

    def test_zero_outcome_review_and_completion_remain_allowed(self):
        response = self.review()
        self.assertEqual(response.context["summary"]["resolved_recommendations"], 0)
        self.assertContains(response, "ثبت نتیجه شرط پایان ویزیت نیست")
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 200)
        self.assertFalse(SalesOutcome.objects.filter(visit=self.visit).exists())

    def test_followup_outcomes_are_distinct_from_open_tasks(self):
        due = self.TODAY + timedelta(days=3)
        self.tasks[0].due_date = due
        self.tasks[0].save()
        for rec in (self.rec, self.extra_recommendation(2)):
            SalesOutcome.objects.create(visit=self.visit, recommendation=rec, outcome="FOLLOW_UP")
        response = self.review()
        self.assertEqual(response.context["summary"]["follow_up"], 2)
        self.assertEqual(response.context["follow_up"]["open"], 1)
        self.assertContains(response, "1 پیگیری باز")
        self.assertContains(response, due.strftime("%Y/%m/%d"))
        self.assertContains(response, reverse("follow-up-dashboard"))

    def test_followup_without_open_task_is_truthfully_unscheduled(self):
        self.tasks[0].status = "DONE"
        self.tasks[0].save()
        SalesOutcome.objects.create(visit=self.visit, recommendation=self.rec, outcome="FOLLOW_UP")
        response = self.review()
        self.assertContains(response, "پیگیری زمان‌بندی‌شده بازی در داده‌های این ویزیت موجود نیست")
        self.assertEqual(response.context["follow_up"]["open"], 0)
        self.assertEqual(response.context["follow_up"]["done"], 1)
        self.assertEqual(FollowUpTask.objects.filter(visit=self.visit).count(), 1)

    def test_end_all_goes_to_review_without_completing_or_recording(self):
        url = reverse("recommendation-presentation", args=[self.customer.customer_code])
        response = self.client.get(url, {"visit_id": self.visit.pk, "recommendation_id": self.rec.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("visit-completion-review", args=[self.customer.customer_code, self.visit.pk]), response.context["end_url"])
        self.assertContains(response, response.context["end_url"])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")
        self.assertFalse(SalesOutcome.objects.filter(visit=self.visit).exists())

    def test_customer_only_end_all_preserves_customer360_fallback(self):
        response = self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]))
        self.assertEqual(response.context["end_url"], response.context["customer_url"])

    def test_completed_and_planned_review_never_offer_operational_completion(self):
        for status in ("COMPLETED", "PLANNED", "CANCELLED"):
            self.visit.status = status
            self.visit.save()
            response = self.review()
            self.assertFalse(response.context["can_finish"])
            self.assertEqual(response.context["completed"], status == "COMPLETED")
            self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 400)

    def test_guard_rejects_empty_wrong_or_non_string_context(self):
        for code in ("", None, 123, self.other_customer.customer_code, "unknown"):
            self.assertEqual(self.complete(customer_code=code).status_code, 404)

    def test_completion_csrf_enforced_and_review_provides_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("visit-complete", args=[self.visit.pk])
        self.assertEqual(client.post(url, {"customer_code": self.customer.customer_code}, content_type="application/json").status_code, 403)
        client.get(reverse("visit-completion-review", args=[self.customer.customer_code, self.visit.pk]))
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, {"customer_code": self.customer.customer_code},
            content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_completion_preserves_snapshots_raw_history_and_followups(self):
        VisitCustomerSnapshot.objects.create(visit=self.visit, customer=self.customer)
        VisitCommercialSnapshot.objects.create(visit=self.visit, customer=self.customer, salesperson=self.rep)
        SalesOutcome.objects.create(visit=self.visit, recommendation=self.rec, outcome="FOLLOW_UP")
        models = (VisitCustomerSnapshot, VisitCommercialSnapshot, SalesOutcome, FollowUpTask, CustomerRecommendation)
        before = [list(model.objects.values()) for model in models]
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 200)
        self.assertEqual([list(model.objects.values()) for model in models], before)
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 400)
        self.assertEqual(self.review().context["completed"], True)

    def test_legacy_completion_keeps_historical_ownership_without_assignment(self):
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        self.assertEqual(self.complete().status_code, 200)
        self.assertEqual(self.complete().status_code, 400)

    def test_customer_visit_mismatch_even_when_both_customers_are_accessible(self):
        CustomerAssignment.objects.create(salesperson=self.rep, customer=self.other_customer, start_date=self.TODAY)
        self.assertEqual(self.review(code=self.other_customer.customer_code).status_code, 404)
        self.assertEqual(self.complete(customer_code=self.other_customer.customer_code).status_code, 404)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_missing_and_inactive_customer_do_not_leak_identity(self):
        missing = self.review(code="missing")
        self.customer.is_active = False
        self.customer.save()
        inactive = self.review()
        self.assertEqual(inactive.status_code, 404)
        self.assertEqual(missing.content, inactive.content)
        self.assertEqual(self.complete(customer_code=self.customer.customer_code).status_code, 404)
