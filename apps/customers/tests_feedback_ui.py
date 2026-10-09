"""Feedback presentation and zero-write GET bindings; isolated fixtures only."""
from html.parser import HTMLParser

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.products import tests_catalog
from apps.recommendations.models import RecommendationFeedbackEvent
from apps.visits.models import Visit


class ReasonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.selected = False
        self.codes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select" and attrs.get("id") == "feedbackReason":
            self.selected = True
        if self.selected and tag == "option" and attrs.get("value"):
            self.codes.append(attrs["value"])

    def handle_endtag(self, tag):
        if tag == "select":
            self.selected = False


class GuidedFeedbackUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def page(self):
        return self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]), {"visit_id": self.visit.pk})

    def test_bindings_dialog_csrf_and_exact_seven_reason_codes(self):
        response = self.page()
        parser = ReasonParser()
        parser.feed(response.content.decode())
        self.assertEqual(parser.codes, list(RecommendationFeedbackEvent.RejectionReason.values))
        for value in ('name="csrfmiddlewaretoken"', 'id="feedbackDialog"', 'aria-labelledby="feedbackTitle"',
                      'aria-describedby="feedbackDescription"', 'for="feedbackReason"', 'data-feedback-reject', 'data-feedback-later'):
            self.assertContains(response, value)
        self.assertContains(response, f'data-feedback-url="{reverse("recommendation-feedback-v1", args=[self.visit.pk])}"')
        self.assertContains(response, f'data-actor-id="{self.user.pk}"')
        self.assertNotContains(response, "textarea")

    def test_existing_product_slots_and_secondary_detail_are_preserved(self):
        response = self.page()
        for value in ('class="gc-quantity-slot" aria-hidden="true"></div>', 'class="gc-add-slot" aria-hidden="true"></div>',
                      'data-image', 'data-price', 'gc-detail', 'catalogCategoryChips'):
            self.assertContains(response, value)
        self.assertContains(response, "بعداً بررسی می‌کنم")
        self.assertContains(response, "core/js/guided_feedback.js")

    def test_saved_decision_change_and_history_bindings_are_accessible(self):
        response = self.page()
        for value in ('data-feedback-change', 'data-feedback-options', 'data-feedback-history-list', 'id="feedbackNotice"', 'aria-live="polite"'):
            self.assertContains(response, value)
        self.assertContains(response, "تغییر تصمیم")

    def test_closed_visit_has_guidance_instead_of_operational_catalog(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        response = self.page()
        self.assertNotContains(response, 'id="guidedCatalog"')
        self.assertContains(response, "این ویزیت دیگر فعال نیست")

    def test_page_and_history_get_head_do_not_write_any_records(self):
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in models}
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.page().status_code, 200)
            for method in (self.client.get, self.client.head):
                self.assertEqual(method(reverse("recommendation-feedback-v1", args=[self.visit.pk]), {"customer_code": self.customer.customer_code}).status_code, 200)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)
