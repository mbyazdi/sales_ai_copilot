"""Visit-scoped quote reads; all price/inventory fixtures are test-only."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerGrade
from apps.inventory.models import Inventory
from apps.recommendations.engine import RecommendationEngine
from apps.visits.models import CustomerAssignment, Salesperson, Visit

from .models import Product, ProductDemoPrice
from .pricing import DemoPriceProvider
from .quotes import MAX_QUOTE_ITEMS, candidate_quote
from . import tests_catalog


class VisitQuoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)
        cls.grade_a = CustomerGrade.objects.create(code="A", name="الف")
        cls.grade_b = CustomerGrade.objects.create(code="B", name="ب")
        cls.grade_c = CustomerGrade.objects.create(code="C", name="ج")
        cls.customer.grade = cls.grade_a
        cls.customer.save(update_fields=["grade"])
        ProductDemoPrice.objects.all().update(base_price=Decimal("105"))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def query(self, **changes):
        query = {"customer_code": self.customer.customer_code,
                 "items": json.dumps([{"product_id": self.products[0].pk, "quantity": 3}])}
        query.update(changes)
        return query

    def url(self, visit_id=None):
        return reverse("visit-quote-v1", args=[self.visit.pk if visit_id is None else visit_id])

    def get(self, **changes):
        return self.api.get(self.url(), self.query(**changes))

    def service(self, items):
        return candidate_quote(self.user, self.customer.customer_code, self.visit.pk, json.dumps(items))

    def test_a_b_c_and_missing_grade_reuse_whole_toman_unit_rounding(self):
        for grade, discount, final, total in ((self.grade_a, "10", "95", "285"),
                                             (self.grade_b, "5", "100", "300"),
                                             (self.grade_c, "0", "105", "315"),
                                             (None, "0", "105", "315")):
            with self.subTest(grade=grade):
                Customer.objects.filter(pk=self.customer.pk).update(grade=grade)
                response = self.get()
                self.assertEqual(response.status_code, 200)
                quote = response.data["items"][0]["pricing"]["quote"]
                self.assertEqual(quote["base_unit_price"], "105")
                self.assertEqual(quote["discount_percentage"], discount)
                self.assertEqual(quote["final_unit_price"], final)
                self.assertEqual(quote["line_total"], total)
                self.assertEqual(quote["currency"], "TOMAN")
                self.assertNotIn(".", quote["line_total"])

    def test_grade_b_rounding_tie_and_arithmetic_match_core(self):
        Customer.objects.filter(pk=self.customer.pk).update(grade=self.grade_b)
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("110"))
        item = self.get().data["items"][0]
        quote = item["pricing"]["quote"]
        self.assertEqual(quote["final_unit_price"], "105")
        self.assertEqual((quote["unit_discount"], quote["line_base"], quote["line_discount"], quote["line_total"]),
                         ("5", "330", "15", "315"))
        self.assertEqual(quote, DemoPriceProvider().quote(self.customer.pk, self.products[0].pk, 3).quote.as_dict())

    def test_missing_price_is_null_quote_not_zero_and_never_seeded(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).delete()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        item = response.data["items"][0]
        self.assertEqual(item["pricing"], {"state": "UNAVAILABLE", "reason_code": "MISSING_PRICE", "quote": None})
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "PRICE_UNAVAILABLE")
        self.assertEqual(item["inventory"]["sellable_quantity"], 8)
        self.assertFalse(ProductDemoPrice.objects.filter(product=self.products[0]).exists())

    def test_explicit_zero_is_available_and_distinct_from_missing(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("0"))
        item = self.get().data["items"][0]
        self.assertEqual(item["pricing"]["state"], "AVAILABLE")
        self.assertEqual(item["pricing"]["quote"]["final_unit_price"], "0")
        self.assertTrue(item["can_add"])

    def test_fractional_price_is_configuration_error_not_repaired(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("105.50"))
        item = self.get().data["items"][0]
        self.assertEqual(item["pricing"], {"state": "CONFIGURATION_ERROR", "reason_code": "FRACTIONAL_BASE_PRICE", "quote": None})
        self.assertEqual(item["non_addable_reason"], "PRICE_CONFIGURATION_ERROR")
        self.assertEqual(ProductDemoPrice.objects.get(product=self.products[0]).base_price, Decimal("105.50"))

    def test_stock_is_canonical_sellable_quantity_with_no_silent_cap(self):
        inventory = Inventory.objects.get(product=self.products[0])
        for available, reserved, expected, reason in ((10, 2, 8, None), (5, 2, 3, None),
                                                      (4, 2, 2, "INSUFFICIENT_STOCK"),
                                                      (2, 2, 0, "OUT_OF_STOCK"),
                                                      (1, 2, 0, "OUT_OF_STOCK")):
            with self.subTest(available=available, reserved=reserved):
                Inventory.objects.filter(pk=inventory.pk).update(available_quantity=available, reserved_quantity=reserved)
                item = self.get().data["items"][0]
                self.assertEqual(item["inventory"]["sellable_quantity"], expected)
                self.assertEqual(item["inventory"]["state"], "AVAILABLE" if expected else "UNAVAILABLE")
                self.assertEqual(item["non_addable_reason"], reason)
                self.assertEqual(item["quantity"], 3)
                self.assertEqual(item["pricing"]["quote"]["line_total"], "285")
                self.assertEqual(item["can_add"], reason is None)

    def test_unknown_and_zero_inventory_remain_distinct_from_missing_price(self):
        Inventory.objects.filter(product=self.products[0]).delete()
        ProductDemoPrice.objects.filter(product=self.products[0]).delete()
        unknown = self.get().data["items"][0]
        self.assertEqual(unknown["inventory"], {"state": "UNKNOWN", "sellable_quantity": None,
                                               "can_add": False, "reason_code": "INVENTORY_UNKNOWN"})
        self.assertEqual(unknown["pricing"]["reason_code"], "MISSING_PRICE")
        self.assertEqual(unknown["non_addable_reason"], "INVENTORY_UNKNOWN")
        Inventory.objects.create(product=self.products[0], available_quantity=0, reserved_quantity=0)
        zero = self.get().data["items"][0]
        self.assertEqual(zero["inventory"]["sellable_quantity"], 0)
        self.assertEqual(zero["non_addable_reason"], "OUT_OF_STOCK")

    def test_batch_prices_each_absolute_quantity_once_in_stable_product_order(self):
        items = [{"product_id": self.products[1].pk, "quantity": 2},
                 {"product_id": self.products[0].pk, "quantity": 3}]
        forward = self.service(items)
        reverse_order = self.service(list(reversed(items)))
        self.assertEqual(forward, reverse_order)
        self.assertEqual([x["product_id"] for x in forward["items"]], [self.products[0].pk, self.products[1].pk])
        self.assertEqual([x["pricing"]["quote"]["line_total"] for x in forward["items"]], ["285", "190"])

    def test_current_grade_price_source_and_quantity_change_fingerprints(self):
        original = self.get().data["items"][0]["pricing"]["quote"]["quote_fingerprint"]
        self.assertEqual(self.get().data["items"][0]["pricing"]["quote"]["quote_fingerprint"], original)
        Customer.objects.filter(pk=self.customer.pk).update(grade=self.grade_b)
        changed = self.get().data["items"][0]["pricing"]["quote"]["quote_fingerprint"]
        self.assertNotEqual(changed, original)
        ProductDemoPrice.objects.filter(product=self.products[0]).update(source_version="v2")
        self.assertNotEqual(self.get().data["items"][0]["pricing"]["quote"]["quote_fingerprint"], changed)

    def test_anonymous_manager_dual_role_and_missing_profile_are_denied(self):
        for user in (None, self.staff, self.no_profile):
            self.api.force_authenticate(user)
            self.assertEqual(self.get().status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.api.force_authenticate(self.user)
        self.assertEqual(self.get().status_code, 403)

    def test_inactive_user_profile_customer_or_assignment_fails_safely(self):
        assignment = CustomerAssignment.objects.get(customer=self.customer)
        for model, pk, expected in ((get_user_model(), self.user.pk, 403), (Salesperson, self.rep.pk, 403),
                                    (Customer, self.customer.pk, 404), (CustomerAssignment, assignment.pk, 404)):
            with self.subTest(model=model):
                model.objects.filter(pk=pk).update(is_active=False)
                self.assertEqual(self.get().status_code, expected)
                model.objects.filter(pk=pk).update(is_active=True)

    def test_foreign_missing_and_customer_mismatched_visits_have_generic_response(self):
        responses = [self.api.get(self.url(visit), self.query()) for visit in (self.foreign_visit.pk, 999999)]
        responses.extend(self.get(customer_code=code) for code in (self.foreign_customer.customer_code, "missing"))
        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data, responses[0].data)
        CustomerAssignment.objects.create(customer=self.customer, salesperson=self.foreign_rep,
                                          start_date=self.visit.visit_date)
        self.api.force_authenticate(self.foreign_user)
        self.assertEqual(self.get().status_code, 404)

    def test_unauthorized_context_precedes_price_and_product_reads(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.get(customer_code=self.foreign_customer.customer_code)
        self.assertEqual(response.status_code, 404)
        sql = " ".join(q["sql"] for q in queries)
        for table in ("products_product", "products_productdemoprice", "inventory_inventory"):
            self.assertNotIn(table, sql)

    def test_planned_quote_is_read_only_and_closed_visits_are_unavailable(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="PLANNED")
        item = self.get().data["items"][0]
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "VISIT_NOT_ACTIVE")
        self.assertEqual(item["pricing"]["state"], "AVAILABLE")
        for status in ("COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=status)
            self.assertEqual(self.get().status_code, 404)

    def test_inactive_and_missing_products_fail_without_returning_partial_quotes(self):
        Product.objects.filter(pk=self.products[0].pk).update(is_active=False)
        response = self.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.get(items=json.dumps([{"product_id": 999999, "quantity": 1}])).data, response.data)

    def test_invalid_items_and_quantity_types_are_rejected(self):
        for raw in ("", "bad", "{}", "[]", "null", "x" * 10001,
                    json.dumps([{"product_id": self.products[0].pk, "quantity": 1}] * (MAX_QUOTE_ITEMS + 1))):
            with self.subTest(raw=raw[:50]):
                self.assertEqual(self.get(items=raw).status_code, 400)
        for quantity in (0, -1, True, False, 1.5, 2.0, "3", None, 2147483648):
            with self.subTest(quantity=quantity):
                self.assertEqual(self.get(items=json.dumps([{"product_id": self.products[0].pk, "quantity": quantity}])).status_code, 400)
        for product_id in (0, -1, True, 1.0, "1", 10**30):
            self.assertEqual(self.get(items=json.dumps([{"product_id": product_id, "quantity": 1}])).status_code, 400)
        self.assertEqual(self.get(items=json.dumps([{"product_id": self.products[0].pk, "quantity": 1, "price": 0}])).status_code, 400)

    def test_duplicates_are_not_silently_aggregated(self):
        items = [{"product_id": self.products[0].pk, "quantity": q} for q in (1, 2)]
        self.assertEqual(self.get(items=json.dumps(items)).status_code, 400)

    def test_line_amount_overflow_is_a_safe_input_error(self):
        ProductDemoPrice.objects.filter(product=self.products[0]).update(base_price=Decimal("9999999999999999"))
        response = self.get()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "LINE_AMOUNT_OUT_OF_RANGE")

    def test_read_only_methods_and_private_cache_control(self):
        response = self.get()
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(self.api.head(self.url(), self.query()).status_code, 200)
        for method in (self.api.post, self.api.patch, self.api.delete):
            self.assertEqual(method(self.url(), {}, format="json").status_code, 405)

    def test_get_and_head_leave_all_managed_records_unchanged_without_generation(self):
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
        before = {m: list(m.objects.order_by("pk").values()) for m in models}
        with patch.object(RecommendationEngine, "generate", side_effect=AssertionError("No regeneration")), CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.get().status_code, 200)
            self.assertEqual(self.api.head(self.url(), self.query()).status_code, 200)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)

    def test_batch_query_count_is_constant_for_one_and_fifty_products(self):
        items = [{"product_id": self.products[0].pk, "quantity": 1}]
        for index in range(49):
            product = Product.objects.create(product_code=f"QUOTE-{index}", name="محصول", brand=self.brand, category=self.category)
            items.append({"product_id": product.pk, "quantity": 1})
            # Alternate missing/known inventory to catch hidden reverse-FK N+1s.
            if index % 2 == 0:
                Inventory.objects.create(product=product, available_quantity=10)
        with self.assertNumQueries(6):
            single = self.service(items[:1])
        with self.assertNumQueries(6):
            batch = self.service(items)
        self.assertEqual(single["items"][0], batch["items"][0])
        self.assertEqual(len(batch["items"]), 50)
