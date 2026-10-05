"""Customer360 presentation/access contracts with isolated, real business data."""
from unittest.mock import patch
from html.parser import HTMLParser

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from apps.products.models import Product
from apps.recommendations.models import CustomerRecommendation
from apps.visits import tests_authorization
from apps.visits.models import Visit, VisitCustomerSnapshot, VisitCommercialSnapshot, SalesOutcome
from .models import Customer360


class ElementParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class Customer360ProductTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.alternative = Product.objects.create(product_code="UI-ALT", name="گزینه جایگزین",
            brand=cls.product.brand, category=cls.product.category)
        cls.alternative_recommendation = CustomerRecommendation.objects.create(
            customer=cls.customer, product=cls.alternative, recommendation_type="CATEGORY",
            rank=2, score=40, reason="دلیل گزینه جایگزین")

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self, visit_id=None, prefix="/customers/", code=None):
        query = {"customer_code": code or self.customer.customer_code}
        if visit_id is not None:
            query["visit_id"] = visit_id
        return self.client.get(prefix, query)

    def test_authorized_customer_only_page_has_primary_decision_and_shared_foundations(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "css/design-system.css")
        self.assertContains(response, "core/css/customer_workspace.css?v=002d-1")
        self.assertContains(response, 'id="workspace-decision"')
        self.assertContains(response, self.product.name)
        self.assertContains(response, response.context["sales_session"]["next_best_action"])
        self.assertContains(response, "امتیاز تجاری")
        self.assertIsNone(response.context["current_visit"])
        self.assertContains(response, "بدون ویزیت انتخاب‌شده")

    def test_access_matrix_remains_server_enforced_on_both_search_routes(self):
        for prefix in ("/customers/", "/api/customers/"):
            self.client.logout()
            self.assertEqual(self.page(prefix=prefix).status_code, 403)
            self.client.force_login(self.user)
            self.assertEqual(self.page(prefix=prefix, code=self.other_customer.customer_code).status_code, 404)
            self.client.force_login(self.staff)
            self.assertEqual(self.page(prefix=prefix, code=self.other_customer.customer_code).status_code, 200)
            self.client.force_login(self.no_profile)
            self.assertEqual(self.page(prefix=prefix).status_code, 403)

    def test_visit_context_and_mutation_bindings_keep_the_selected_visit(self):
        response = self.page(self.visits[0].pk)
        self.assertEqual(response.context["current_visit"].pk, self.visits[0].pk)
        self.assertContains(response, f'name="visit_id" value="{self.visits[0].pk}"')
        self.assertContains(response, f'visitId: {self.visits[0].pk}')
        self.assertContains(response, 'id="startVisitButton"')
        self.assertContains(response, 'id="visitWorkflowMessage"')
        self.assertContains(response, 'id="salesCopilotMessage"')
        self.assertContains(response, 'id="outcomeModal"')

    def test_invalid_other_customer_visit_never_populates_actions(self):
        response = self.page(self.visits[1].pk)
        self.assertIsNone(response.context["current_visit"])
        self.assertContains(response, "بدون زمینه ویزیت")
        self.assertNotContains(response, 'id="startVisitButton"')
        self.assertNotContains(response, 'name="visit_id"')

    def test_alternatives_keep_rank_identity_and_distinct_outcome_bindings(self):
        response = self.page()
        self.assertEqual([r.pk for r in response.context["recommendations"]],
                         [self.recommendations[0].pk, self.alternative_recommendation.pk])
        self.assertContains(response, "گزینه جایگزین · رتبه 2")
        self.assertContains(response, "دلیل گزینه جایگزین")
        elements = ElementParser(response.content.decode()).elements
        for recommendation in (self.recommendations[0], self.alternative_recommendation):
            buttons = [attrs for tag, attrs in elements if tag == "button"
                       and attrs.get("data-recommendation-id") == str(recommendation.pk)]
            self.assertEqual({b["data-outcome"] for b in buttons},
                             {"PURCHASED", "INTERESTED", "FOLLOW_UP", "REJECTED", "NOT_PRESENTED"})

    def test_outcome_controls_follow_existing_visit_state(self):
        for status in ("PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visits[0].pk).update(status=status)
            response = self.page(self.visits[0].pk)
            buttons = [attrs for tag, attrs in ElementParser(response.content.decode()).elements
                       if tag == "button" and "data-outcome" in attrs]
            self.assertTrue(buttons)
            self.assertTrue(all(("disabled" in attrs) == (status != "IN_PROGRESS") for attrs in buttons))

    def test_no_recommendation_keeps_safe_decision_and_existing_copilot(self):
        CustomerRecommendation.objects.filter(customer=self.customer).update(is_active=False)
        for visit_id in (None, self.visits[0].pk):
            response = self.page(visit_id)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "پیشنهاد فعال برای این مشتری موجود نیست")
            self.assertContains(response, 'id="salesCopilotSubmit"')
            self.assertNotContains(response, 'data-outcome="PURCHASED"')

    def test_missing_snapshot_and_optional_ai_context_render_safely(self):
        Customer360.objects.filter(customer=self.customer).delete()
        response = self.page(self.visits[0].pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اطلاعات تحلیلی مشتری هنوز ثبت نشده")
        self.assertContains(response, "زمینه تحلیلی کافی برای دستیار موجود نیست")
        Customer360.objects.create(customer=self.customer)
        with patch("apps.customers.views.build_sales_ai_context", return_value=None):
            response = self.page()
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'id="salesCopilotMessage"')

    def test_opening_page_does_not_mutate_visits_snapshots_outcomes_or_invoke_ai(self):
        models = (Visit, VisitCustomerSnapshot, VisitCommercialSnapshot, SalesOutcome, CustomerRecommendation)
        before = [model.objects.count() for model in models]
        with patch("apps.ai.services.OllamaClient") as provider, CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.page(self.visits[0].pk).status_code, 200)
            self.assertEqual(self.page().status_code, 200)
            provider.assert_not_called()
        for query in queries:
            self.assertFalse(query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")), query["sql"])
        self.assertEqual([model.objects.count() for model in models], before)
        self.visits[0].refresh_from_db()
        self.assertEqual(self.visits[0].status, "PLANNED")
