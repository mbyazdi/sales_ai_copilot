"""UI-04 bindings, safe returns and unchanged server-side commercial contracts."""
from html.parser import HTMLParser

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.recommendations.models import RecommendationFeedbackEvent
from apps.visits.models import Visit
from . import tests_catalog
from .catalog import build_catalog
from .templatetags.product_display import package_label, unit_label


class ProductDisplayTests(SimpleTestCase):
    def test_pcs_alias_and_unrecognized_units_are_presentation_only(self):
        self.assertEqual(unit_label("PCS"), "عدد")
        self.assertEqual(unit_label("KG"), "KG")
        self.assertEqual(package_label("6 PCS"), "6 عدد")
        self.assertEqual(package_label("PCSBOX"), "PCSBOX")
        self.assertEqual(package_label(None), "")


class ReasonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_reason = False
        self.codes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select" and attrs.get("id") == "feedbackReason":
            self.in_reason = True
        if self.in_reason and tag == "option" and attrs.get("value"):
            self.codes.append(attrs["value"])

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_reason = False


class ProductHeroUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def page(self, product=None, **query):
        return self.client.get(reverse("product-commercial-brief", args=[(product or self.products[0]).product_code]),
                               {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk, **query})

    def test_hero_identity_commercial_evidence_feedback_order_and_bound_context(self):
        response = self.page()
        html = response.content.decode()
        zones = ('class="ph-hero"', 'class="ph-card ph-identity"', 'class="ph-card ph-commercial',
                 'class="pb-evidence ph-card ph-recommendation', 'id="productFeedback"')
        offsets = [html.index(zone) for zone in zones]
        self.assertEqual(offsets, sorted(offsets))
        self.assertContains(response, f'data-product-id="{self.products[0].pk}"')
        self.assertContains(response, f'data-visit-status="IN_PROGRESS"')
        self.assertContains(response, "products/js/product_feedback.js")
        self.assertContains(response, "data-product-quote")
        self.assertContains(response, self.recs[0].reason)
        for copy in ("قیمت فرضی", "تصویر نمونه", "تصویر تولیدشده", "ACCEPTED"):
            self.assertNotContains(response, copy)
        self.assertNotContains(response, "data-basket-add")
        self.assertContains(response, "قیمت و موجودی")
        self.assertNotContains(response, "شرایط تجاری فعلی")
        self.assertNotContains(response, ">PCS<")
        self.assertContains(response, ">عدد<")

    def test_exact_reason_codes_csrf_and_explicit_actions(self):
        response = self.page()
        parser = ReasonParser()
        parser.feed(response.content.decode())
        self.assertEqual(parser.codes, list(RecommendationFeedbackEvent.RejectionReason.values))
        for binding in ('name="csrfmiddlewaretoken"', 'data-feedback-reject', 'data-feedback-later',
                        'data-feedback-history-list', 'id="feedbackRecovery"', 'aria-describedby="feedbackDescription"'):
            self.assertContains(response, binding)
        self.assertContains(response, f'data-feedback-url="{reverse("recommendation-feedback-v1", args=[self.visit.pk])}"')

    def test_ordinary_product_has_no_feedback_actions_or_invented_evidence(self):
        response = self.page(self.products[3])
        self.assertNotContains(response, "data-feedback-reject")
        self.assertNotContains(response, "data-feedback-later")
        self.assertContains(response, "بدون اولویت ویژه")
        self.assertContains(response, "پیشنهاد فعالی برای این محصول و مشتری ثبت نشده")

    def test_planned_closed_and_no_visit_are_truthful(self):
        for state in ("PLANNED", "COMPLETED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            response = self.page()
            self.assertContains(response, f'data-visit-status="{state}"')
            if state == "PLANNED":
                self.assertContains(response, "data-product-quote")
            else:
                self.assertNotContains(response, "data-product-quote")
        response = self.client.get(reverse("product-commercial-brief", args=[self.products[0].product_code]),
                                   {"customer_code": self.customer.customer_code})
        self.assertContains(response, "ثبت بازخورد نیاز به ویزیت معتبر دارد")
        self.assertNotContains(response, "data-product-quote")

    def test_signed_return_keeps_catalog_filters_and_product_focus(self):
        catalog = build_catalog(self.user, self.customer.customer_code, self.visit.pk, {"q": "محصول", "page_size": "2"})
        item = catalog["items"][0]
        response = self.client.get(item["brief_url"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("q=", response.context["return_url"])
        self.assertIn("page_size=2", response.context["return_url"])
        self.assertIn(f'#catalog-product-{item["product_id"]}', response.context["return_url"])
        self.assertContains(response, "بازگشت")

    def test_manager_layout_is_unchanged_and_has_no_operational_feedback(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("product-commercial-brief", args=[self.products[0].product_code]),
                                   {"customer_code": self.customer.customer_code})
        self.assertContains(response, 'class="pb-workspace ds-stack"')
        self.assertNotContains(response, "product_hero.css")
        self.assertNotContains(response, 'id="productFeedback"')

    def test_page_reads_preserve_all_managed_records(self):
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in models}
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.page().status_code, 200)
            self.assertEqual(self.page(self.products[4]).status_code, 200)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)
