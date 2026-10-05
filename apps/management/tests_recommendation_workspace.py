"""Canonical management presentation and retained tuning/security contracts."""

from datetime import timedelta
from decimal import Decimal
from html.parser import HTMLParser
from unittest.mock import patch

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.products.models import Product
from apps.recommendations.models import (
    CustomerRecommendation, RecommendationConfig, RecommendationTuningSuggestion,
)
from apps.visits.models import SalesOutcome, Visit
from apps.visits.tests_authorization import AuthorizationBaselineTests


class RecommendationVisualParser(HTMLParser):
    """Read numeric visual inputs without depending on whitespace/formatting."""

    def __init__(self, html):
        super().__init__()
        self.stages, self.outcomes, self.disclosures = {}, {}, {}
        self.current_type = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-stage" in attrs:
            self.stages[attrs["data-stage"]] = int(attrs["data-count"])
        if tag == "figure" and "data-type" in attrs:
            self.current_type = attrs["data-type"]
            self.outcomes[self.current_type] = {}
        if "data-outcome" in attrs and self.current_type:
            count = int(attrs["data-count"])
            self.outcomes[self.current_type][attrs["data-outcome"]] = (count, attrs["style"])
        if tag == "details" and "id" in attrs:
            self.disclosures[attrs["id"]] = "open" in attrs

    def handle_endtag(self, tag):
        if tag == "figure":
            self.current_type = None


class RecommendationWorkspaceTests(TestCase):
    TODAY = AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.config = RecommendationConfig.objects.create(name="workspace-active")
        cls.snapshot = {"presented": 5, "not_presented": 2, "conversion_rate": 20,
                        "learning_signal": "WEAK", "data_quality": "LIMITED_DATA"}
        cls.suggestion = RecommendationTuningSuggestion.objects.create(
            recommendation_type="CROSS_SELL", metric="similar_product_score",
            current_value=15, suggested_value=20, reason="دلیل ثبت‌شده تنظیم",
            performance_snapshot=cls.snapshot,
        )

    def page(self):
        return self.client.get(reverse("recommendation-performance-dashboard"))

    def as_staff(self):
        self.client.force_login(self.staff)

    def result(self, offset, outcome, amount=0, recommendation=None):
        visit = Visit.objects.create(
            salesperson=self.rep, customer=self.customer,
            visit_date=self.TODAY + timedelta(days=offset),
        )
        return SalesOutcome.objects.create(
            visit=visit, recommendation=recommendation or self.recommendations[0],
            outcome=outcome, sales_amount=amount,
            quantity=1 if outcome == "PURCHASED" else 0,
        )

    def test_staff_access_and_denial_before_context_building(self):
        with patch("apps.management.views.build_recommendation_type_analytics") as builder:
            self.assertEqual(self.page().status_code, 302)
            self.client.force_login(self.user)
            self.assertEqual(self.page().status_code, 302)
            builder.assert_not_called()
        self.as_staff()
        self.assertEqual(self.page().status_code, 200)

    def test_canonical_not_presented_and_manager_parity_without_legacy_api_change(self):
        self.result(1, "NOT_PRESENTED")
        self.result(2, "PURCHASED", 1200)
        self.as_staff()
        response = self.page()
        summary = response.context["summary"]
        self.assertEqual(summary["resolved_recommendations"], 3)
        self.assertEqual(summary["presented"], 2)
        self.assertEqual(summary["not_presented"], 1)
        self.assertEqual(summary["conversion_rate"], 50)
        self.assertEqual(summary["engagement_rate"], 50)
        self.assertEqual(summary["total_revenue"], 1200)
        manager = self.client.get(reverse("management-dashboard")).context["summary"]
        for key in ("presented", "purchased", "not_presented", "conversion_rate",
                    "engagement_rate", "total_revenue", "data_quality"):
            self.assertEqual(summary[key], manager[key], key)
        legacy = self.client.get(reverse("recommendation-performance-all")).json()
        self.assertEqual(legacy["summary"]["presented"], 3)
        self.assertEqual(legacy["summary"]["conversion_rate"], 33.33)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.performance_snapshot, self.snapshot)

    def test_latest_outcome_is_one_resolved_pair(self):
        result = self.result(1, "PURCHASED", 500)
        SalesOutcome.objects.create(visit=result.visit, recommendation=result.recommendation,
                                    outcome="NOT_PRESENTED")
        self.as_staff()
        summary = self.page().context["summary"]
        self.assertEqual(summary["resolved_recommendations"], 2)
        self.assertEqual(summary["presented"], 1)
        self.assertEqual(summary["purchased"], 0)
        self.assertEqual(summary["not_presented"], 1)
        self.assertEqual(summary["total_revenue"], 0)

    def test_type_breakdown_uses_canonical_order_and_values(self):
        product = Product.objects.create(product_code="WORKSPACE-CATEGORY", name="محصول دسته",
                                         brand=self.product.brand, category=self.product.category)
        recommendation = CustomerRecommendation.objects.create(
            customer=self.customer, product=product, recommendation_type="CATEGORY", score=70,
            rank=2, reason="دلیل موجود",
        )
        self.result(1, "PURCHASED", 900, recommendation)
        self.result(2, "NOT_PRESENTED", recommendation=recommendation)
        self.result(3, "INTERESTED")
        self.as_staff()
        response = self.page()
        rows = response.context["performance"]["items"]
        self.assertEqual([item["recommendation_type"] for item in rows], ["CATEGORY", "CROSS_SELL"])
        self.assertEqual((rows[0]["resolved_recommendations"], rows[0]["presented"],
                          rows[0]["purchased"], rows[0]["not_presented"]), (2, 1, 1, 1))
        self.assertEqual(rows[0]["conversion_rate"], 100)
        self.assertEqual(rows[1]["interested"], 1)
        self.assertEqual(rows[1]["conversion_rate"], 0)
        self.assertEqual(rows[1]["engagement_rate"], 50)
        self.assertContains(response, "پیشنهاد دسته")
        self.assertContains(response, "ارائه نشده")

    def test_empty_and_only_not_presented_do_not_claim_zero_conversion(self):
        SalesOutcome.objects.all().delete()
        self.as_staff()
        response = self.page()
        self.assertFalse(response.context["performance"]["ready"])
        self.assertContains(response, "نبود داده به معنی عملکرد ضعیف نیست")
        self.assertContains(response, "بدون داده ارائه‌شده")
        self.assertContains(response, "هنوز نتیجه‌ای به تفکیک نوع پیشنهاد ثبت نشده است")
        self.assertContains(response, "<span>نرخ تبدیل</span><strong>—</strong>", html=True)
        self.result(1, "NOT_PRESENTED")
        response = self.page()
        self.assertEqual(response.context["summary"]["resolved_recommendations"], 1)
        self.assertEqual(response.context["summary"]["presented"], 0)
        self.assertContains(response, "<span>نرخ تبدیل</span><strong>—</strong>", html=True)

    def test_sparse_zero_performance_and_quality_are_distinct(self):
        self.as_staff()
        response = self.page()
        self.assertEqual(response.context["summary"]["presented"], 1)
        self.assertEqual(response.context["summary"]["conversion_rate"], 0)
        self.assertContains(response, "داده ناکافی")
        self.assertNotContains(response, "<span>نرخ تبدیل</span><strong>—</strong>", html=True)
        for day in (1, 2):
            self.result(day, "FOLLOW_UP")
        response = self.page()
        self.assertEqual(response.context["summary"]["data_quality"], "LIMITED_DATA")
        self.assertContains(response, "داده محدود")

    def test_explainability_returns_existing_evidence_without_generation(self):
        recommendation = self.recommendations[0]
        recommendation.reason = "دلیل اصلی <script>موجود</script>"
        recommendation.confidence_score = 80
        recommendation.evidence_quality = "MEDIUM"
        recommendation.score_breakdown = {"group_score": 30, "rule_score": 60, "feedback_score": -5}
        recommendation.explanation_snapshot = {"signals": [
            {"name": "group_affinity", "score": 30, "active": True}], "active_signal_count": 1}
        recommendation.save()
        self.as_staff()
        with patch("apps.ai.services.OllamaClient") as provider, patch(
            "apps.recommendations.engine.RecommendationEngine"
        ) as engine:
            listed = self.client.get(reverse("recommendation-diagnostics")).json()["results"]
            detail = self.client.get(reverse("recommendation-diagnostics-detail", args=[recommendation.pk])).json()
        provider.assert_not_called()
        engine.assert_not_called()
        item = next(item for item in listed if item["id"] == recommendation.pk)
        self.assertEqual(item["explanation_snapshot"], recommendation.explanation_snapshot)
        self.assertEqual(detail["reason"], recommendation.reason)
        self.assertEqual(detail["score_breakdown"], recommendation.score_breakdown)
        self.assertEqual(detail["explanation_snapshot"], recommendation.explanation_snapshot)
        self.assertEqual(detail["confidence_score"], 80)
        recommendation.refresh_from_db()
        self.assertEqual(recommendation.rank, 1)
        self.assertEqual(recommendation.score, 60)

    def test_empty_and_missing_evidence_remain_empty(self):
        self.as_staff()
        detail = self.client.get(reverse("recommendation-diagnostics-detail",
                                         args=[self.recommendations[0].pk])).json()
        self.assertEqual(detail["explanation_snapshot"], {})
        self.assertEqual(detail["score_breakdown"], {})
        CustomerRecommendation.objects.update(is_active=False)
        self.assertEqual(self.client.get(reverse("recommendation-diagnostics")).json()["results"], [])
        self.assertEqual(self.client.get(reverse("recommendation-diagnostics-summary")).json()["total_recommendations"], 0)

    def test_diagnostics_and_tuning_staff_boundary_including_real_mutation_ids(self):
        for user in (None, self.user):
            client = Client()
            if user:
                client.force_login(user)
            for name, args in (("recommendation-diagnostics", []),
                               ("recommendation-diagnostics-summary", []),
                               ("recommendation-diagnostics-detail", [self.recommendations[0].pk]),
                               ("recommendation-tuning-suggestions", [])):
                response = client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(self.customer.customer_code, response.content.decode())
            for action in ("status", "apply", "rollback"):
                response = client.post(reverse("recommendation-tuning-suggestion-" + action,
                                               args=[self.suggestion.pk]), {"status": "APPROVED"})
                self.assertEqual(response.status_code, 403)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, "PENDING")

    def test_tuning_csrf_validation_apply_and_rollback_are_preserved(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        page = client.get(reverse("recommendation-performance-dashboard"))
        self.assertEqual(page.status_code, 200)
        token = client.cookies["csrftoken"].value
        urls = {action: reverse("recommendation-tuning-suggestion-" + action,
                               args=[self.suggestion.pk]) for action in ("status", "apply", "rollback")}
        for url in urls.values():
            self.assertEqual(client.post(url, {}, content_type="application/json").status_code, 403)
        def post(action, data=None):
            return client.post(urls[action], data or {}, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(post("status", {"status": "APPLIED"}).status_code, 400)
        self.assertEqual(post("apply").status_code, 400)
        self.assertEqual(post("rollback").status_code, 400)
        self.assertEqual(post("status", {"status": "APPROVED"}).status_code, 200)
        for value in (101, 30):
            self.suggestion.suggested_value = value
            self.suggestion.save(update_fields=["suggested_value"])
            self.assertEqual(post("apply").status_code, 400)
        self.suggestion.suggested_value = 20
        self.suggestion.save(update_fields=["suggested_value"])
        self.config.similar_product_score = 16
        self.config.save()
        self.assertEqual(post("apply").status_code, 400)
        self.config.similar_product_score = 15
        self.config.save()
        self.assertEqual(post("apply").status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.similar_product_score, Decimal("20"))
        self.assertEqual(post("apply").status_code, 400)
        self.assertEqual(post("rollback").status_code, 200)
        self.config.refresh_from_db()
        self.suggestion.refresh_from_db()
        self.assertEqual(self.config.similar_product_score, Decimal("15"))
        self.assertEqual(self.suggestion.status, "ROLLED_BACK")
        self.assertEqual(self.suggestion.performance_snapshot, self.snapshot)

    def test_active_config_is_actual_selected_record_and_missing_config_is_not_created(self):
        self.as_staff()
        newer = RecommendationConfig.objects.create(name="newer-active", max_recommendations=7)
        RecommendationConfig.objects.create(name="inactive-config", is_active=False)
        response = self.page()
        self.assertEqual(response.context["active_config"].pk, newer.pk)
        self.assertEqual(response.context["config_values"][1]["value"], 7)
        RecommendationConfig.objects.update(is_active=False)
        self.assertContains(self.page(), "پیکربندی فعال ثبت نشده است")
        self.assertFalse(RecommendationConfig.objects.filter(is_active=True).exists())

    def test_all_workspace_gets_have_no_business_writes_and_keep_shell(self):
        self.as_staff()
        before = list(RecommendationTuningSuggestion.objects.values())
        config_before = list(RecommendationConfig.objects.values())
        with patch("apps.ai.services.OllamaClient") as provider, CaptureQueriesContext(connection) as queries:
            response = self.page()
            for name, args in (("recommendation-diagnostics", []),
                               ("recommendation-diagnostics-summary", []),
                               ("recommendation-diagnostics-detail", [self.recommendations[0].pk]),
                               ("recommendation-tuning-suggestions", [])):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)
        provider.assert_not_called()
        self.assertEqual([query["sql"] for query in queries if query["sql"].lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE"))], [])
        self.assertEqual(list(RecommendationTuningSuggestion.objects.values()), before)
        self.assertEqual(list(RecommendationConfig.objects.values()), config_before)
        self.assertContains(response, '<html lang="fa" dir="rtl">')
        self.assertContains(response, "css/design-system.css")
        self.assertContains(response, "تنظیمات پیشرفته موتور پیشنهاد")
        self.assertNotContains(response, "salesRecommendationPerformance")
        self.assertContains(response, 'id="diagnosticsSummaryError"')
        self.assertContains(response, 'id="diagnosticsEmpty"')
        self.assertContains(response, 'id="tuningStatusFilter"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_visual_flow_and_outcomes_preserve_canonical_counts(self):
        self.result(1, "NOT_PRESENTED")
        self.result(2, "PURCHASED", 1200)
        self.as_staff()
        response = self.page()
        parsed = RecommendationVisualParser(response.content.decode())
        self.assertEqual(parsed.stages, {"evaluated": 3, "presented": 2, "purchased": 1})
        expected = {"purchased": 1, "interested": 0, "follow_up": 0,
                    "rejected": 1, "not_presented": 1}
        self.assertEqual({key: value[0] for key, value in parsed.outcomes["CROSS_SELL"].items()}, expected)
        for count, style in parsed.outcomes["CROSS_SELL"].values():
            self.assertEqual(style, f"flex-grow:{count}")
        self.assertFalse(parsed.disclosures["comparison-details"])
        self.assertFalse(parsed.disclosures["recommendationTuningSection"])
        self.assertContains(response, "تعداد نتایج ثبت‌شده")

    def test_empty_and_not_presented_only_visuals_are_truthful(self):
        SalesOutcome.objects.all().delete()
        self.as_staff()
        parsed = RecommendationVisualParser(self.page().content.decode())
        self.assertEqual(parsed.stages, {"evaluated": 0, "presented": 0, "purchased": 0})
        self.assertEqual(parsed.outcomes, {})
        self.result(1, "NOT_PRESENTED")
        response = self.page()
        parsed = RecommendationVisualParser(response.content.decode())
        self.assertEqual(parsed.stages, {"evaluated": 1, "presented": 0, "purchased": 0})
        self.assertEqual(parsed.outcomes["CROSS_SELL"]["not_presented"][0], 1)
        self.assertContains(response, "<span>نرخ تبدیل</span><strong>—</strong>", html=True)
