"""Single-product presentation, navigation and source/access contracts."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.inventory.models import Inventory
from apps.products.models import Product
from apps.recommendations.models import CustomerRecommendation
from apps.visits import tests_authorization
from apps.visits.models import Visit


class PageElements(HTMLParser):
    def __init__(self, content):
        super().__init__(); self.elements = []; self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class RecommendationPresentationTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.visit = cls.visits[0]
        cls.visit.status = "IN_PROGRESS"; cls.visit.save()
        cls.rec = cls.recommendations[0]
        cls.rec.recommendation_type = "REPEAT_PURCHASE"
        cls.rec.reason = "دلیل اول ثبت‌شده. دلیل دوم ثبت‌شده. توضیح سوم ثبت‌شده."
        cls.rec.save()
        cls.recs = [cls.rec]
        for rank, kind in ((2, "CATEGORY"), (3, "CATEGORY"), (4, "CROSS_SELL"), (5, "CATEGORY")):
            product = Product.objects.create(product_code=f"PRESENT-{rank}", name=f"محصول {rank}",
                brand=cls.product.brand, category=cls.product.category)
            cls.recs.append(CustomerRecommendation.objects.create(customer=cls.customer, product=product,
                recommendation_type=kind, rank=rank, score=100-rank, reason="دلیل ذخیره‌شده"))
        cls.inventory = Inventory.objects.create(product=cls.product, available_quantity=10, reserved_quantity=2)

    def setUp(self):
        self.client.force_login(self.user)

    def page(self, rec=None, **extra):
        query = {"visit_id": self.visit.pk, **extra}
        if rec:
            query["recommendation_id"] = rec.pk
        return self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]), query)

    def test_authorized_salesperson_sees_only_one_product_without_raw_diagnostics(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        elements = PageElements(response.content.decode()).elements
        cards = [attrs for tag, attrs in elements if tag == "article" and "recommendation-outcome-card" in attrs.get("class", "")]
        self.assertEqual(len(cards), 1)
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, self.recs[1].product.name)
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertNotContains(response, "ترکیب امتیاز")
        self.assertNotContains(response, "امتیاز ثبت‌شده")
        self.assertEqual(response.context["short_reason"], "دلیل اول ثبت‌شده. دلیل دوم ثبت‌شده.")
        self.assertEqual(response.context["recommendation"].pk, self.rec.pk)

    def test_manager_and_dual_role_are_not_forced_into_operational_presentation(self):
        self.user.is_staff = True; self.user.save()
        for user in (self.staff, self.user):
            self.client.force_login(user)
            response = self.page()
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, "outcome-btn", status_code=403)
            inspection = self.client.get("/customers/", {"customer_code": self.customer.customer_code})
            self.assertEqual(inspection.status_code, 200)
            self.assertNotContains(inspection, "شروع نمایش پیشنهادها")

    def test_foreign_revoked_and_invalid_context_is_not_presentable(self):
        self.assertEqual(self.page(visit_id=self.visits[1].pk).status_code, 404)
        for value in ("bad", "9" * 50, "-1"):
            self.assertEqual(self.page(visit_id=value).status_code, 404)
        self.customer.salesperson_assignments.update(is_active=False)
        self.assertEqual(self.page().status_code, 404)

    def test_anonymous_and_missing_profile_denied(self):
        self.client.logout(); self.assertEqual(self.page().status_code, 403)
        self.client.force_login(self.no_profile); self.assertEqual(self.page().status_code, 403)

    def test_next_previous_last_and_refresh_preserve_backend_order_and_visit(self):
        for index, rec in enumerate(self.recs):
            response = self.page(rec)
            self.assertEqual(response.context["position"], index+1)
            self.assertEqual(response.context["total"], 5)
            self.assertEqual(response.context["remaining"], 4-index)
            for key, expected_index in (("previous_url", index-1), ("next_url", index+1)):
                url = response.context[key]
                if expected_index < 0 or expected_index >= len(self.recs):
                    self.assertIsNone(url)
                else:
                    query = parse_qs(urlsplit(url).query)
                    self.assertEqual(query["visit_id"], [str(self.visit.pk)])
                    self.assertEqual(query["recommendation_id"], [str(self.recs[expected_index].pk)])
                    self.assertEqual(self.client.get(url).context["recommendation"].pk, self.recs[expected_index].pk)
            self.assertEqual(self.page(rec).context["recommendation"].pk, rec.pk)

    def test_end_group_moves_to_next_contiguous_type_without_global_reordering(self):
        response = self.page(self.recs[1])
        query = parse_qs(urlsplit(response.context["group_next_url"]).query)
        self.assertEqual(query["recommendation_id"], [str(self.recs[3].pk)])
        later_category = self.page(self.recs[4])
        self.assertIsNone(later_category.context["group_next_url"])
        self.assertContains(later_category, 'id="endAll"')
        self.assertContains(later_category, 'id="endPresentationDialog"')
        self.assertNotContains(later_category, "گروه تکمیل شد")

    def test_single_and_empty_recommendations_are_intentional_states(self):
        CustomerRecommendation.objects.filter(customer=self.customer).exclude(pk=self.rec.pk).update(is_active=False)
        single = self.page()
        self.assertEqual(single.context["total"], 1)
        self.assertIsNone(single.context["next_url"])
        self.assertIsNone(single.context["previous_url"])
        self.rec.is_active = False; self.rec.save()
        empty = self.page()
        self.assertContains(empty, "پیشنهاد فعالی موجود نیست")
        self.assertNotContains(empty, 'class="gs-product"')

    def test_image_missing_and_zero_stock_remain_truthful(self):
        response = self.page()
        self.assertIsNone(response.context["image_url"])
        self.assertContains(response, "تصویر محصول ثبت نشده است")
        self.assertNotContains(response, 'data-product-image')
        self.assertEqual(response.context["commercial"]["inventory"]["sellable_quantity"], 8)
        self.inventory.available_quantity = 0; self.inventory.reserved_quantity = 0; self.inventory.save()
        zero = self.page()
        self.assertContains(zero, "ناموجود برای فروش")
        self.assertEqual(zero.context["commercial"]["inventory"]["sellable_quantity"], 0)
        self.inventory.delete()
        missing = self.page()
        self.assertContains(missing, "اطلاعات موجودی در دسترس نیست")
        self.assertIsNone(missing.context["commercial"]["inventory"]["sellable_quantity"])

    def test_unavailable_product_and_recommendation_fail_safely(self):
        self.product.is_active = False; self.product.save()
        unavailable = self.page()
        self.assertContains(unavailable, "محصول این پیشنهاد در دسترس نیست")
        self.assertEqual(unavailable.content.decode().count('data-unavailable="true"'), 5)
        self.assertEqual(self.page(recommendation_id=self.recommendations[1].pk).status_code, 404)

    def test_customer_only_and_planned_context_never_auto_start_or_record(self):
        page = self.page(visit_id="")
        self.assertIsNone(page.context["current_visit"])
        self.assertNotContains(page, "data-read-url=")
        Visit.objects.filter(pk=self.visit.pk).update(status="PLANNED")
        planned = self.page()
        self.assertContains(planned, "برنامه‌ریزی‌شده")
        self.assertNotContains(planned, 'id="startVisitButton"')

    def test_product_brief_return_uses_validated_presentation_target(self):
        response = self.page(self.recs[1])
        brief = self.client.get(response.context["brief_url"])
        back = brief.context["return_url"]
        self.assertEqual(urlsplit(back).fragment, f"recommendation-{self.recs[1].pk}")
        target = self.client.get(back.split("#")[0])
        self.assertEqual(target.context["recommendation"].pk, self.recs[1].pk)
        self.assertEqual(target.context["current_visit"].pk, self.visit.pk)

    def test_get_navigation_and_brief_return_perform_no_writes_or_llm_calls(self):
        with patch("apps.ai.ollama_client.OllamaClient.generate") as llm, CaptureQueriesContext(connection) as queries:
            response = self.page(self.recs[1])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get(response.context["next_url"]).status_code, 200)
            brief = self.client.get(response.context["brief_url"])
            self.assertEqual(self.client.get(brief.context["return_url"].split("#")[0]).status_code, 200)
        llm.assert_not_called()
        self.assertEqual([q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))], [])
