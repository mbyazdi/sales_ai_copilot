"""Management workspace regressions using isolated business records."""

from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.recommendations.models import CustomerRecommendation
from apps.products.models import Product
from apps.visits.models import SalesOutcome, Visit
from apps.visits import tests_authorization


class ManagementWorkspaceTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)

    def page(self):
        return self.client.get(reverse("management-dashboard"))

    def as_staff(self):
        self.client.force_login(self.staff)

    def add_result(self, day, outcome, amount=0, category="CROSS_SELL"):
        visit = Visit.objects.create(
            salesperson=self.rep, customer=self.customer,
            visit_date=self.TODAY + timedelta(days=day),
        )
        if category == "CROSS_SELL":
            recommendation = self.recommendations[0]
        else:
            product = Product.objects.create(
                product_code="AUTH-P-" + category, name="Category product",
                brand=self.product.brand, category=self.product.category,
            )
            recommendation = CustomerRecommendation.objects.create(
                customer=self.customer, product=product,
                recommendation_type=category, score=60, rank=2,
                reason="Recorded outcome fixture",
            )
        return SalesOutcome.objects.create(
            visit=visit, recommendation=recommendation, outcome=outcome,
            quantity=1 if outcome == "PURCHASED" else 0,
            sales_amount=amount,
        )

    def test_staff_only_html_and_api_boundaries(self):
        self.assertEqual(self.page().status_code, 302)
        self.assertIn(self.client.get(reverse("management_api:dashboard")).status_code, (401, 403))
        self.client.force_login(self.user)
        self.assertEqual(self.page().status_code, 302)
        self.assertEqual(self.client.get(reverse("management_api:dashboard")).status_code, 403)
        self.as_staff()
        self.assertEqual(self.page().status_code, 200)

    def test_real_metrics_attention_and_limited_data(self):
        self.add_result(0, "PURCHASED", amount=1200)
        self.add_result(1, "INTERESTED")
        self.add_result(2, "FOLLOW_UP")
        self.as_staff()
        response = self.page()
        self.assertEqual(response.status_code, 200)
        summary = response.context["summary"]
        # The inherited fixture also has one other salesperson's REJECTED result.
        self.assertEqual(summary["presented"], 4)
        self.assertEqual(summary["purchased"], 1)
        self.assertEqual(summary["follow_up"], 1)
        self.assertEqual(summary["total_revenue"], 1200)
        self.assertEqual(summary["conversion_rate"], 25)
        self.assertEqual(summary["engagement_rate"], 75)
        self.assertEqual(summary["data_quality"], "LIMITED_DATA")
        self.assertContains(response, "داده محدود")
        self.assertContains(response, "1 نتیجه نیازمند پیگیری")
        self.assertContains(response, "این عدد، تعداد کارهای پیگیری باز یا عقب‌افتاده نیست.")
        self.assertContains(response, 'data-value="1200')
        self.assertContains(response, "25")
        self.assertContains(response, "نیازمند توجه")
        self.assertContains(response, '<th scope="col">نیاز به پیگیری</th>', html=True)
        self.assertContains(response, '<th scope="col">ارائه نشده</th>', html=True)

    def test_sparse_and_no_data_are_truthful(self):
        self.as_staff()
        sparse = self.page()
        self.assertEqual(sparse.context["summary"]["presented"], 1)
        self.assertContains(sparse, "داده ناکافی")
        self.assertNotContains(sparse, "نتیجه نیازمند پیگیری")
        self.assertContains(sparse, "فقط یک فروشنده دارای نتیجه ثبت‌شده است")
        SalesOutcome.objects.all().delete()
        empty = self.page()
        self.assertEqual(empty.context["summary"]["presented"], 0)
        self.assertContains(empty, "هنوز نتیجه‌ای برای تحلیل مدیریت ثبت نشده است")
        self.assertContains(empty, "بدون داده ارائه‌شده")
        self.assertContains(empty, "هنوز نتیجه‌ای برای هیچ فروشنده‌ای ثبت نشده است")
        self.assertContains(empty, "نتیجه‌ای برای این بخش ثبت نشده است")

    def test_real_trends_team_and_recommendation_type_diagnostics(self):
        self.add_result(0, "PURCHASED", amount=900, category="CATEGORY")
        self.add_result(1, "INTERESTED")
        self.as_staff()
        response = self.page()
        self.assertEqual(len(response.context["trend"]["trends"]["day"]), 2)
        self.assertContains(response, 'id="management-trends"')
        self.assertContains(response, "2026/09/15")
        self.assertContains(response, "نتایج ثبت‌شده فروشندگان")
        self.assertContains(response, "AUTH-A")
        self.assertContains(response, "پیشنهاد دسته")
        self.assertContains(response, "نتایج به تفکیک نوع پیشنهاد")
        self.assertContains(response, reverse("recommendation-performance-dashboard"))

    def test_shell_and_no_unapproved_customer_or_salesperson_actions(self):
        self.as_staff()
        response = self.page()
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, "css/design-system.css")
        self.assertContains(response, "management/js/dashboard.js")
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, 'aria-current="page"')
        self.assertNotContains(response, self.other_customer.name)
        self.assertNotContains(response, "/api/visits/follow-ups/")
        self.assertNotContains(response, 'href="/customers/?customer_code=')

    def test_rendering_uses_resolved_outcomes_without_writes_or_ai(self):
        result = self.add_result(0, "INTERESTED")
        SalesOutcome.objects.create(
            visit=result.visit, recommendation=result.recommendation,
            outcome="PURCHASED", quantity=2, sales_amount=2500,
        )
        self.as_staff()
        with patch("apps.ai.services.OllamaClient") as provider:
            with CaptureQueriesContext(connection) as queries:
                response = self.page()
        self.assertEqual(response.status_code, 200)
        provider.assert_not_called()
        self.assertEqual(response.context["summary"]["resolved_recommendations"], 2)
        self.assertEqual(response.context["summary"]["interested"], 0)
        self.assertEqual(response.context["summary"]["total_revenue"], 2500)
        writes = [query["sql"] for query in queries
                  if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        self.assertEqual(writes, [])
