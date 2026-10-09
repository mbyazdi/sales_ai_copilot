"""Guided presentation integrates the real catalog and leaves business state untouched."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.products import tests_catalog
from apps.products.models import Product, ProductDemoPrice
from apps.recommendations.engine import RecommendationEngine
from apps.recommendations.models import CustomerRecommendation
from apps.visits.models import Visit


class GuidedCatalogUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def page(self, **query):
        return self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]), {"visit_id": self.visit.pk, **query})

    def api(self, **query):
        return self.client.get(reverse("product-catalog-v1"), {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk, **query})

    def test_operational_context_title_and_real_catalog_endpoint(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        for value in ('lang="fa" dir="rtl"', "فروش هوشمند", self.customer.name, self.customer.customer_code, 'data-status="IN_PROGRESS"', 'data-api-url="/api/products/v1/catalog/"', f'data-visit-id="{self.visit.pk}"'):
            self.assertContains(response, value)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertTemplateUsed(response, "components/salesperson_context.html")

    def test_group_hierarchy_and_full_page_are_not_recommendation_only(self):
        response = self.page()
        html = response.content.decode()
        self.assertLess(html.index('id="catalogPrioritized"'), html.index('id="catalogOrdinary"'))
        self.assertContains(response, "پیشنهادهای هوشمند برای این مشتری")
        self.assertContains(response, "سایر محصولات قابل ارائه")
        data = self.api().json()
        self.assertEqual(len(data["items"]), 6)
        self.assertEqual([item["product_id"] for item in data["items"]], [self.products[i].pk for i in (1, 2, 0, 3, 4, 5)])
        self.assertTrue(all(item["priority_label"] == "بدون اولویت ویژه" and item["recommendation"] is None for item in data["items"][3:]))

    def test_search_category_priority_controls_have_labels_and_get_semantics(self):
        response = self.page()
        for name in ("catalogSearch", "catalogCategory", "catalogPriority"):
            self.assertContains(response, f'for="{name}"')
            self.assertContains(response, f'id="{name}"')
        self.assertContains(response, 'method="get"')
        self.assertContains(response, 'type="search" maxlength="200"')
        self.assertEqual([item["product_id"] for item in self.api(q="CAT-3").json()["items"]], [self.products[3].pk])
        self.assertEqual(len(self.api(category_id=self.other_category.pk, priority="ordinary").json()["items"]), 3)

    def test_loading_empty_and_error_regions_are_accessible(self):
        response = self.page()
        self.assertContains(response, 'aria-busy="true"')
        self.assertContains(response, 'role="status" aria-live="polite"')
        self.assertContains(response, 'role="alert" hidden')
        self.assertContains(response, 'id="catalogEmpty"')
        self.assertContains(response, 'id="catalogRetry"')
        self.assertEqual(self.api(q="هیچ محصولی").json()["items"], [])

    def test_mockup_anatomy_has_real_filter_chips_and_fixed_truthful_visual_slots(self):
        response = self.page()
        for value in ('class="gc-appbar"', 'class="gc-customer-image"', 'class="gc-catalog-tabs"',
                      'data-priority-filter="all"', 'data-priority-filter="prioritized"', 'data-priority-filter="ordinary"',
                      'aria-controls="catalogFilterOptions"', 'class="gc-price-slot"', 'class="gc-stock-slot"',
                      'class="gc-priority-star"', 'class="gc-section-heading"'):
            self.assertContains(response, value)
        self.assertContains(response, "قیمت پایه")
        self.assertContains(response, "قیمت واحد برای این مشتری")
        self.assertContains(response, "قیمت فرضی دمو؛ قیمت بازار نیست")
        self.assertContains(response, 'open hidden', count=2)

    def test_final_fidelity_uses_category_chips_separate_identity_and_unimplemented_footer_slots(self):
        response = self.page()
        for value in ('id="catalogCategoryChips"', '<legend>اولویت محصولات</legend>', 'data-code', 'data-brand', 'data-category',
                      'class="gc-commercial-status"', 'class="gc-secondary-actions"', 'data-cue-details'):
            self.assertContains(response, value)
        self.assertContains(response, '<div class="gc-quantity-slot" aria-hidden="true"></div>')
        self.assertContains(response, '<div class="gc-add-slot" aria-hidden="true"></div>')
        css = (Path(settings.BASE_DIR) / "static/core/css/guided_catalog.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-areas: 'add price quantity'", css)
        self.assertIn("repeat(2, minmax(0, 1fr))", css)
        self.assertNotIn(".gc-grid { grid-template-columns: repeat(3", css)
        self.assertNotIn("-webkit-line-clamp", css)
        self.assertIn("--gc-navy: #07335b", css)
        self.assertIn("--gc-amber: #fee9b5", css)

    def test_no_recommendations_does_not_remove_the_catalog(self):
        CustomerRecommendation.objects.filter(customer=self.customer).update(is_active=False)
        self.assertContains(self.page(), 'id="guidedCatalog"')
        data = self.api().json()
        self.assertEqual(len(data["items"]), 6)
        self.assertTrue(all(not item["is_prioritized"] for item in data["items"]))

    def test_no_products_is_a_truthful_empty_catalog(self):
        Product.objects.all().update(is_active=False)
        self.assertContains(self.page(), 'id="catalogEmpty"')
        self.assertEqual(self.api().json()["counts"]["overall"]["total"], 0)

    def test_stock_price_and_image_states_are_truthful_backend_values(self):
        ProductDemoPrice.objects.filter(product=self.products[3]).delete()
        data = self.api().json()
        by_id = {item["product_id"]: item for item in data["items"]}
        self.assertFalse(by_id[self.products[3].pk]["pricing"]["has_demo_price"])
        self.assertEqual(by_id[self.products[4].pk]["inventory_state"], "UNAVAILABLE")
        self.assertEqual(by_id[self.products[5].pk]["inventory_state"], "UNKNOWN")
        self.assertIsNone(by_id[self.products[5].pk]["available_quantity"])
        self.assertTrue(all(item["image"]["url"] is None for item in data["items"]))
        self.assertTrue(all("final_price" not in item and "discount" not in item for item in data["items"]))

    def test_recommended_and_ordinary_detail_links_restore_the_same_guided_context(self):
        data = self.api(q="محصول", page_size=2, page=2).json()
        for item in data["items"]:  # Page crosses recommended/ordinary boundary.
            with self.subTest(product=item["product_id"]):
                detail = self.client.get(item["brief_url"])
                self.assertEqual(detail.status_code, 200)
                back = detail.context["return_url"]
                query = parse_qs(urlsplit(back).query)
                self.assertEqual(query["product_id"], [str(item["product_id"])])
                self.assertEqual(query["catalog_context"], [data["catalog_context"]])
                self.assertEqual(query["q"], ["محصول"])
                self.assertEqual(query["page"], ["2"])
                returned = self.client.get(back.split("#")[0])
                self.assertContains(returned, 'id="guidedCatalog"')
                self.assertEqual(returned.context["current_visit"].pk, self.visit.pk)
                self.assertContains(detail, "بازگشت</a>", count=2)

    def test_customer_only_and_closed_visits_have_safe_read_only_presentation(self):
        self.assertContains(self.page(visit_id=""), "ویزیت را انتخاب کنید")
        self.assertNotContains(self.page(visit_id=""), 'id="guidedCatalog"')
        for state in ("COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            response = self.page()
            self.assertContains(response, "این ویزیت دیگر فعال نیست")
            self.assertNotContains(response, 'id="guidedCatalog"')

    def test_no_add_quantity_feedback_or_completion_mutation_controls(self):
        response = self.page()
        for forbidden in ('data-outcome="', 'id="outcomeModal"', 'name="quantity"', "افزودن به درخواست", 'id="completeVisitButton"', 'method="post"'):
            self.assertNotContains(response, forbidden)
        self.assertContains(response, "جزئیات محصول")
        self.assertContains(response, "مرور ویزیت")

    def test_get_shell_api_detail_and_return_create_no_business_records(self):
        labels = ("sales_requests", "recommendations", "visits", "products", "inventory", "sales")
        models = [model for label in labels for model in apps.get_app_config(label).get_models()]
        before = {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}
        with patch.object(RecommendationEngine, "generate", side_effect=AssertionError("No generation")), patch("apps.ai.ollama_client.OllamaClient.generate", side_effect=AssertionError("No AI")), CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.page().status_code, 200)
            data = self.api().json()
            detail = self.client.get(data["items"][-1]["brief_url"])
            self.assertEqual(self.client.get(detail.context["return_url"].split("#")[0]).status_code, 200)
        self.assertEqual([query["sql"] for query in queries if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))], [])
        self.assertEqual(before, {model._meta.label: list(model.objects.order_by("pk").values()) for model in models})

    def test_responsive_structure_uses_scoped_tokens_flow_pagination_and_focus(self):
        response = self.page()
        self.assertContains(response, 'class="gs-page gc-page"')
        self.assertContains(response, 'id="catalogPagination" class="gc-pagination"')
        self.assertContains(response, 'id="main-content" tabindex="-1"')
        css = (Path(settings.BASE_DIR) / "static/core/css/guided_catalog.css").read_text(encoding="utf-8")
        for value in ("min-width: 768px", "min-width: 1024px", "minmax(0, 1fr)", "var(--ds-control-size)", "env(safe-area-inset-bottom)", ":focus-visible"):
            self.assertIn(value, css)
        self.assertNotIn("position: fixed", css)
        self.assertNotIn("position: sticky", css)

    def test_long_persian_customer_text_is_escaped_and_isolated(self):
        payload = "<script>bad()</script>"
        maximum = self.customer._meta.get_field("name").max_length
        self.customer.name = ("نام طولانی فروشگاه " * 12)[:maximum - len(payload)] + payload
        self.assertEqual(len(self.customer.name), maximum)
        self.customer.save()
        response = self.page()
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.assertNotContains(response, "<script>bad()</script>")
        self.assertContains(response, "<bdi>نام طولانی")

    def test_manager_is_not_given_the_guided_catalog_or_changed_chrome(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.page().status_code, 403)
        response = self.client.get("/customers/", {"customer_code": self.customer.customer_code})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "guided_catalog.css")
        self.assertNotContains(response, "guided_catalog.js")
