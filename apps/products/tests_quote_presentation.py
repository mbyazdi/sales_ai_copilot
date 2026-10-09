"""Quote presentation bindings and zero-write journey reads in isolated fixtures."""
import json
from decimal import Decimal

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.customers.models import CustomerGrade
from apps.inventory.models import Inventory
from apps.visits.models import Visit
from .models import ProductDemoPrice
from . import tests_catalog


class CommercialQuotePresentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)
        cls.grade = CustomerGrade.objects.create(code="A", name="الف")
        cls.customer.grade = cls.grade
        cls.customer.save(update_fields=["grade"])
        ProductDemoPrice.objects.filter(product=cls.products[0]).update(base_price=Decimal("105"))

    def setUp(self):
        self.client.force_login(self.user)

    def guided(self):
        return self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]), {"visit_id": self.visit.pk})

    def detail(self, **changes):
        query = {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk, **changes}
        return self.client.get(f"/products/{self.products[0].product_code}/", query)

    def quote(self, product=None, quantity=1):
        return self.client.get(reverse("visit-quote-v1", args=[self.visit.pk]), {
            "customer_code": self.customer.customer_code,
            "items": json.dumps([{"product_id": (product or self.products[0]).pk, "quantity": quantity}]),
        })

    def test_both_surfaces_share_quote_component_and_authorized_endpoint(self):
        for response in (self.guided(), self.detail()):
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "components/commercial_quote.html")
            self.assertContains(response, f'data-quote-url="{reverse("visit-quote-v1", args=[self.visit.pk])}"')
            self.assertContains(response, f'data-customer-code="{self.customer.customer_code}"')
            for binding in ("data-quote-base", "data-quote-discount", "data-quote-saving", "data-quote-final", "data-quote-stock", "data-quote-availability"):
                self.assertContains(response, binding)
            self.assertContains(response, "قیمت فرضی دمو؛ قیمت بازار نیست")
            self.assertContains(response, "products/js/commercial_quotes.js")

    def test_single_unit_quotes_match_for_guided_and_detail(self):
        self.assertEqual(self.guided().status_code, 200)
        guided = self.quote().json()["items"][0]
        self.assertEqual(self.detail().status_code, 200)
        detail = self.quote().json()["items"][0]
        self.assertEqual(guided, detail)
        self.assertEqual(detail["pricing"]["quote"]["final_unit_price"], "95")

    def test_missing_price_and_inventory_do_not_become_zero(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).delete()
        Inventory.objects.filter(product=self.products[0]).delete()
        item = self.quote().json()["items"][0]
        self.assertEqual(item["pricing"]["state"], "UNAVAILABLE")
        self.assertIsNone(item["pricing"]["quote"])
        self.assertEqual(item["inventory"]["state"], "UNKNOWN")
        self.assertIsNone(item["inventory"]["sellable_quantity"])
        self.assertFalse(item["can_add"])
        self.assertContains(self.detail(), "data-product-quote")

    def test_zero_and_insufficient_stock_retain_quotes_and_block_addability(self):
        for available, expected in ((0, "OUT_OF_STOCK"), (2, "INSUFFICIENT_STOCK")):
            Inventory.objects.filter(product=self.products[0]).update(available_quantity=available, reserved_quantity=0)
            item = self.quote(quantity=3).json()["items"][0]
            self.assertEqual(item["pricing"]["state"], "AVAILABLE")
            self.assertFalse(item["can_add"])
            self.assertEqual(item["non_addable_reason"], expected)

    def test_planned_quotes_are_not_permission_to_add(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="PLANNED")
        item = self.quote().json()["items"][0]
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "VISIT_NOT_ACTIVE")
        self.assertContains(self.detail(), "data-product-quote")

    def test_manager_customer_only_and_closed_details_do_not_request_quotes(self):
        self.assertNotContains(self.client.get(f"/products/{self.products[0].product_code}/", {"customer_code": self.customer.customer_code}), "data-product-quote")
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        self.assertNotContains(self.detail(), "data-product-quote")
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(f"/products/{self.products[0].product_code}/", {"customer_code": self.customer.customer_code}), "data-product-quote")
        self.assertEqual(self.quote().status_code, 403)

    def test_page_and_quote_reads_preserve_all_records(self):
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in models}
        with CaptureQueriesContext(connection) as queries:
            for response in (self.guided(), self.detail(), self.quote()):
                self.assertEqual(response.status_code, 200)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)
