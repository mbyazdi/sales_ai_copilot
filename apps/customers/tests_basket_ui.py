"""Guided basket presentation boundaries; isolated fixtures only."""
from django.apps import apps
from django.test import TestCase
from django.urls import reverse

from apps.products import tests_catalog
from apps.visits.models import Visit


class GuidedBasketUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def page(self):
        return self.client.get(reverse('recommendation-presentation', args=[self.customer.customer_code]), {'visit_id': self.visit.pk})

    def test_existing_slots_are_activated_without_new_order_submission_controls(self):
        response = self.page()
        for value in ('class="gc-quantity-slot"', 'data-basket-quantity', 'data-basket-add', 'class="gc-price-slot"',
                      'id="basketPanel"', 'id="basketLines"', 'id="basketDialog"', 'id="basketForm"',
                      'id="basketStatus"', 'id="basketRetryCommand"', 'name="csrfmiddlewaretoken"',
                      'core/js/guided_basket.js', 'core/css/guided_basket.css', 'data-feedback-reject', 'data-feedback-later',
                      'aria-labelledby="basketTitle"', 'aria-describedby="basketDescription"'):
            self.assertContains(response, value)
        self.assertContains(response, 'data-basket-url="' + reverse('visit-basket-v1', args=[self.visit.pk]) + '"')
        self.assertNotContains(response, 'id="submitRequest"')
        self.assertNotContains(response, 'add-to-cart')

    def test_planned_page_starts_with_disabled_controls_and_closed_page_has_no_catalog(self):
        Visit.objects.filter(pk=self.visit.pk).update(status='PLANNED')
        response = self.page()
        self.assertContains(response, 'data-basket-add class="ds-button gb-add" type="button" disabled')
        self.assertContains(response, 'inputmode="numeric" disabled')
        Visit.objects.filter(pk=self.visit.pk).update(status='COMPLETED')
        self.assertNotContains(self.page(), 'id="guidedCatalog"')

    def test_guided_get_and_basket_reads_do_not_create_draft_feedback_or_receipt(self):
        before = {model: list(model.objects.order_by('pk').values()) for model in apps.get_models()}
        self.assertEqual(self.page().status_code, 200)
        for method in (self.client.get, self.client.head):
            response = method(reverse('visit-basket-v1', args=[self.visit.pk]), {'customer_code': self.customer.customer_code})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.data['request'])
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), rows)

    def test_unauthorized_page_and_basket_do_not_expose_foreign_context(self):
        self.client.force_login(self.foreign_user)
        self.assertEqual(self.page().status_code, 404)
        self.assertIn(self.client.get(reverse('visit-basket-v1', args=[self.visit.pk]), {'customer_code': self.customer.customer_code}).status_code, (403, 404))
