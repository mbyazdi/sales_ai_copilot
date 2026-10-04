"""Small continuity regressions using the isolated authorization baseline data."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ai.ollama_client import OllamaClientError
from apps.ai.services import generate_sales_copilot_response
from apps.visits.services import build_pre_visit_briefs
from . import tests_authorization
from .models import SalesOutcome


class DemoContinuityTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        # Reuse data construction without inheriting/rerunning the security tests.
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self, **query):
        return self.client.get("/customers/", {"customer_code": self.customer.customer_code, **query})

    def test_customer_only_page_uses_real_product_context_without_fabricating_visit(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["current_visit"])
        self.assertEqual(response.context["sales_session"]["primary_product_code"], self.product.product_code)
        self.assertTrue(response.context["sales_session"]["inventory_context"])
        self.assertNotContains(response, 'name="visit_id"')

    def test_visit_search_preserves_valid_id_and_rejects_wrong_customer_or_invalid_id(self):
        response = self.page(visit_id=self.visits[0].pk)
        self.assertContains(response, f'name="visit_id" value="{self.visits[0].pk}"')
        self.assertEqual(response.context["current_visit"].pk, self.visits[0].pk)
        for visit_id in (self.visits[1].pk, 999999, "invalid"):
            with self.subTest(visit_id=visit_id):
                response = self.page(visit_id=visit_id)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["current_visit"])
                self.assertEqual(response.context["visit_id"], "")
                self.assertContains(response, "بدون زمینه ویزیت")
                self.assertNotContains(response, 'name="visit_id"')

    def test_workspace_and_followup_links_enter_with_their_original_visit(self):
        for name in ("salesperson-dashboard", "follow-up-dashboard"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'/customers/?customer_code={self.customer.customer_code}&visit_id={self.visits[0].pk}')

    def test_no_recommendation_page_previsit_and_ai_remain_usable(self):
        self.recommendations[0].is_active = False
        self.recommendations[0].save(update_fields=["is_active"])
        for query in ({}, {"visit_id": self.visits[0].pk}):
            response = self.page(**query)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "پیشنهاد فعال برای این مشتری موجود نیست")
            self.assertIsNone(response.context["sales_session"]["primary_product_code"])
            self.assertEqual(response.context["sales_session"]["inventory_context"], {})
        brief = build_pre_visit_briefs(visits=[self.visits[0]], salesperson=self.rep)[self.visits[0].pk]
        self.assertIsNone(brief["primary_recommendation"])
        self.client.force_authenticate(self.user)
        for visit_id in (None, self.visits[0].pk):
            with patch("apps.ai.services.OllamaClient") as provider:
                response = self.client.post("/api/ai/v1/sales-copilot/", {
                    "customer_code": self.customer.customer_code, "message": "راهنمایی",
                    "visit_id": visit_id,
                }, format="json")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertIn("پیشنهاد فعال", response.data["response"])
            provider.assert_not_called()
            self.assertEqual(response.data["visit_id"], visit_id)

    def test_no_recommendation_does_not_block_existing_visit_start_and_complete(self):
        self.recommendations[0].delete()
        self.client.force_authenticate(self.user)
        for name in ("visit-start", "visit-complete"):
            response = self.client.post(reverse(name, args=[self.visits[0].pk]))
            self.assertEqual(response.status_code, 200, response.content)
        self.visits[0].refresh_from_db()
        self.assertEqual(self.visits[0].status, "COMPLETED")

    @override_settings(OLLAMA_TIMEOUT=600)
    def test_provider_failure_retains_authoritative_sales_guidance_with_bounded_wait(self):
        self.client.force_authenticate(self.user)
        with patch("apps.ai.services.OllamaClient") as provider:
            provider.return_value.generate.side_effect = OllamaClientError("offline")
            response = self.client.post("/api/ai/v1/sales-copilot/", {
                "customer_code": self.customer.customer_code, "visit_id": self.visits[0].pk,
                "message": "راهنمایی",
            }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(self.product.product_code, response.data["response"])
        self.assertIn("هوش مصنوعی در دسترس نیست", response.data["response"])
        self.assertEqual(response.data["visit_id"], self.visits[0].pk)
        provider.assert_called_once_with(timeout=5)

    def test_unexpected_errors_are_not_converted_to_deterministic_success(self):
        with patch("apps.ai.services.OllamaClient") as provider:
            provider.return_value.generate.side_effect = ValueError("invalid business input")
            with self.assertRaises(ValueError):
                generate_sales_copilot_response({"recommendations": [{"product_code": "P"}]})

    @override_settings(OLLAMA_TIMEOUT=600)
    def test_management_real_contract_survives_optional_provider_failure(self):
        self.client.force_authenticate(self.staff)
        with patch("apps.ai.services.OllamaClient") as provider:
            provider.return_value.generate.side_effect = OllamaClientError("offline")
            response = self.client.get(reverse("management_api:dashboard"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.data["executive_intelligence"]["ready"])
        self.assertTrue(response.data["executive_intelligence"]["narrative"])
        self.assertFalse(response.data["executive_intelligence"]["llm_status"]["available"])
        provider.assert_called_once_with(timeout=5)
        self.assertEqual(response.data["schema_version"], "V3.0.9.2")

    def test_management_not_ready_context_skips_generation_and_returns_contract(self):
        SalesOutcome.objects.all().delete()
        self.client.force_authenticate(self.staff)
        with patch("apps.management.api_views.generate_management_executive_narrative") as generator:
            response = self.client.get(reverse("management_api:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["ready"])
        self.assertFalse(response.data["executive_intelligence"]["ready"])
        generator.assert_not_called()
