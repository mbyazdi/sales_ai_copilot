"""Full-catalog, saved-session, access, navigation and zero-write contracts."""
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.models import Customer, Customer360
from apps.inventory.models import Inventory
from apps.recommendations.catalog_context import CONTEXT_MAX_AGE
from apps.recommendations.engine import RecommendationEngine
from apps.recommendations.models import CustomerRecommendation
from apps.sales.models import Sale, SaleItem
from apps.visits.models import CustomerAssignment, Salesperson, Visit

from .catalog import build_catalog
from .eligibility import product_eligibility
from .models import Brand, Category, Product, ProductDemoPrice


class CatalogBackendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.user = users.objects.create_user(username="catalog-rep")
        cls.foreign_user = users.objects.create_user(username="catalog-foreign")
        cls.staff = users.objects.create_user(username="catalog-manager", is_staff=True)
        cls.no_profile = users.objects.create_user(username="catalog-no-profile")
        cls.rep = Salesperson.objects.create(user=cls.user, employee_code="CAT-A", first_name="فروشنده", last_name="الف")
        cls.foreign_rep = Salesperson.objects.create(user=cls.foreign_user, employee_code="CAT-B", first_name="فروشنده", last_name="ب")
        cls.customer = Customer.objects.create(customer_code="CAT-A", name="مشتری الف")
        cls.foreign_customer = Customer.objects.create(customer_code="CAT-B", name="مشتری ب")
        Customer360.objects.create(customer=cls.customer)
        for rep, customer in ((cls.rep, cls.customer), (cls.foreign_rep, cls.foreign_customer)):
            CustomerAssignment.objects.create(salesperson=rep, customer=customer, start_date=timezone.localdate())
        cls.visit = Visit.objects.create(customer=cls.customer, salesperson=cls.rep, visit_date=timezone.localdate(), status="IN_PROGRESS")
        cls.foreign_visit = Visit.objects.create(customer=cls.foreign_customer, salesperson=cls.foreign_rep, visit_date=timezone.localdate(), status="IN_PROGRESS")
        cls.brand = Brand.objects.create(code="CAT", name="برند آزمایشی")
        cls.category = Category.objects.create(code="CAT", name="بهداشت")
        cls.other_category = Category.objects.create(code="CAT-OTHER", name="لوازم")
        cls.products = []
        for index in range(6):
            cls.products.append(Product.objects.create(
                product_code=f"CAT-{index}", name=f"محصول {index}", brand=cls.brand,
                category=cls.category if index < 3 else cls.other_category, repurchase_cycle_days=30,
            ))
        cls.inactive = Product.objects.create(product_code="CAT-INACTIVE", name="غیرفعال", brand=cls.brand, category=cls.category, is_active=False)
        cls.recs = []
        # Rank wins over score; a saved rank tie is deterministically resolved by ID.
        for index, rank, score in ((0, 5, 99), (1, 1, 1), (2, 1, 2)):
            cls.recs.append(CustomerRecommendation.objects.create(
                customer=cls.customer, product=cls.products[index], rank=rank, score=score,
                recommendation_type="REPEAT_PURCHASE", reason="دلیل اول ذخیره‌شده. دلیل دوم ذخیره‌شده. جمله سوم.",
                explanation_snapshot={"signals": [{"name": "repurchase", "active": True}]},
            ))
        for product in cls.products[:4]:
            Inventory.objects.create(product=product, available_quantity=10, reserved_quantity=2)
        Inventory.objects.create(product=cls.products[4], available_quantity=10, reserved_quantity=10)
        for product in cls.products:
            ProductDemoPrice.objects.create(product=product, base_price=Decimal("123.00"), currency="TOMAN", source="test-fixture", source_version="1")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client.force_login(self.user)

    def catalog(self, **query):
        return build_catalog(self.user, self.customer.customer_code, self.visit.pk, query)

    def get(self, **query):
        return self.api.get(reverse("product-catalog-v1"), {
            "customer_code": self.customer.customer_code, "visit_id": self.visit.pk, **query,
        })

    def test_recommendations_first_in_saved_rank_order_then_all_ordinary_products(self):
        data = self.catalog()
        self.assertEqual([item["product_id"] for item in data["items"]], [self.products[i].pk for i in (1, 2, 0, 3, 4, 5)])
        self.assertEqual([item["recommendation"]["rank"] for item in data["items"][:3]], [1, 1, 5])
        self.assertEqual([item["recommendation"]["id"] for item in data["items"][:3]], [self.recs[i].pk for i in (1, 2, 0)])
        self.assertTrue(all(item["is_prioritized"] for item in data["items"][:3]))
        self.assertTrue(all(item["recommendation"] is None and item["priority_label"] == "بدون اولویت ویژه" for item in data["items"][3:]))
        self.assertEqual(data["counts"]["overall"], {"total": 6, "prioritized": 3, "ordinary": 3})

    def test_every_visible_product_appears_once_inactive_is_excluded(self):
        ids = [item["product_id"] for item in self.catalog()["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {p.pk for p in self.products})
        self.assertNotIn(self.inactive.pk, ids)

    def test_no_saved_recommendations_still_returns_full_ordinary_catalog(self):
        CustomerRecommendation.objects.filter(customer=self.customer).update(is_active=False)
        data = self.catalog()
        self.assertEqual(len(data["items"]), 6)
        self.assertTrue(all(not item["is_prioritized"] for item in data["items"]))
        self.assertEqual(data["counts"]["overall"]["prioritized"], 0)

    def test_candidate_excluded_recent_purchase_is_still_an_ordinary_catalog_product(self):
        product = self.products[3]
        sale = Sale.objects.create(customer=self.customer, invoice_number="CAT-HISTORY", sale_date=timezone.localdate() - timedelta(days=1))
        SaleItem.objects.create(sale=sale, product=product, unit_price=Decimal("99"))
        engine = RecommendationEngine(self.customer)
        self.assertNotIn(product.pk, {p.pk for p in engine._get_candidates()})
        item = next(item for item in self.catalog()["items"] if item["product_id"] == product.pk)
        self.assertFalse(item["is_prioritized"])
        self.assertTrue(item["can_add"])

    def test_positive_sellable_stock_is_addable_and_reservations_are_respected(self):
        item = next(item for item in self.catalog()["items"] if item["product_id"] == self.products[3].pk)
        self.assertTrue(item["can_add"])
        self.assertTrue(item["inventory_can_add"])
        self.assertEqual(item["inventory_state"], "AVAILABLE")
        self.assertEqual(item["available_quantity"], 8)

    def test_zero_sellable_stock_remains_visible_and_not_addable(self):
        item = next(item for item in self.catalog()["items"] if item["product_id"] == self.products[4].pk)
        self.assertEqual(item["inventory_state"], "UNAVAILABLE")
        self.assertEqual(item["available_quantity"], 0)
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "OUT_OF_STOCK")

    def test_missing_inventory_is_unknown_not_zero_and_still_visible(self):
        item = next(item for item in self.catalog()["items"] if item["product_id"] == self.products[5].pk)
        self.assertEqual(item["inventory_state"], "UNKNOWN")
        self.assertIsNone(item["available_quantity"])
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "INVENTORY_UNKNOWN")

    def test_overreserved_stock_uses_canonical_clamp(self):
        Inventory.objects.filter(product=self.products[3]).update(reserved_quantity=20)
        product = Product.objects.select_related("inventory").get(pk=self.products[3].pk)
        self.assertEqual(product_eligibility(product)["available_quantity"], 0)

    def test_inactive_or_foreign_recommendations_do_not_confer_priority(self):
        CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(is_active=False)
        CustomerRecommendation.objects.create(customer=self.foreign_customer, product=self.products[3], rank=0, recommendation_type="CATEGORY")
        data = self.catalog()
        self.assertEqual(data["counts"]["overall"]["prioritized"], 2)
        self.assertFalse(next(item for item in data["items"] if item["product_id"] == self.products[0].pk)["is_prioritized"])
        self.assertFalse(next(item for item in data["items"] if item["product_id"] == self.products[3].pk)["is_prioritized"])

    def test_no_unsupported_brand_category_or_grade_restrictions(self):
        Brand.objects.filter(pk=self.brand.pk).update(is_active=False)
        Category.objects.filter(pk=self.category.pk).update(is_active=False)
        self.assertEqual(len(self.catalog()["items"]), 6)

    def test_missing_current_price_is_not_a_free_quote_or_catalog_exclusion(self):
        ProductDemoPrice.objects.filter(product=self.products[3]).delete()
        item = next(item for item in self.catalog()["items"] if item["product_id"] == self.products[3].pk)
        self.assertTrue(item["inventory_can_add"])
        self.assertFalse(item["can_add"])
        self.assertEqual(item["non_addable_reason"], "PRICE_UNAVAILABLE")
        self.assertEqual(item["pricing"], {"has_demo_price": False, "state": "NOT_EVALUATED"})

    def test_item_contract_uses_saved_reason_and_truthful_price_image_placeholders(self):
        item = self.catalog()["items"][0]
        self.assertEqual(item["recommendation"]["short_reason"], "دلیل اول ذخیره‌شده. دلیل دوم ذخیره‌شده.")
        self.assertEqual(item["recommendation"]["explanation_snapshot"], self.recs[1].explanation_snapshot)
        self.assertEqual(item["image"], {"url": None, "state": "MISSING"})
        self.assertEqual(item["pricing"], {"has_demo_price": True, "state": "NOT_EVALUATED"})
        self.assertNotIn("final_price", item)
        self.assertNotIn("discount", item)

    def test_search_matches_code_name_brand_and_category_without_losing_priority(self):
        for query, expected in (("CAT-3", [3]), ("محصول 4", [4]), ("برند آزمایشی", [1, 2, 0, 3, 4, 5]), ("لوازم", [3, 4, 5])):
            with self.subTest(query=query):
                self.assertEqual([item["product_id"] for item in self.catalog(q=query)["items"]], [self.products[i].pk for i in expected])

    def test_category_filter_counts_and_discovery_choices(self):
        data = self.catalog(category_id=str(self.category.pk))
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["counts"]["overall"]["total"], 6)
        self.assertEqual(data["counts"]["filtered"], {"total": 3, "prioritized": 3, "ordinary": 0})
        self.assertEqual({row["id"] for row in data["categories"]}, {self.category.pk, self.other_category.pk})

    def test_priority_filters_and_combinations_are_deterministic(self):
        for value, count in (("prioritized", 3), ("ordinary", 3)):
            data = self.catalog(priority=value)
            self.assertEqual(len(data["items"]), count)
            self.assertTrue(all(item["is_prioritized"] == (value == "prioritized") for item in data["items"]))
        self.assertEqual(self.catalog(priority="ordinary", category_id=str(self.category.pk))["items"], [])

    def test_pagination_is_stable_and_does_not_duplicate_products(self):
        first = self.catalog(page_size="2")
        token = first["catalog_context"]
        second = self.catalog(page_size="2", page="2", catalog_context=token)
        third = self.catalog(page_size="2", page="3", catalog_context=token)
        ids = [item["product_id"] for data in (first, second, third) for item in data["items"]]
        self.assertEqual(ids, [self.products[i].pk for i in (1, 2, 0, 3, 4, 5)])
        self.assertEqual(second["items"], self.catalog(page_size="2", page="2", catalog_context=token)["items"])
        self.assertEqual(third["catalog_context"], token)
        self.assertFalse(third["pagination"]["has_next"])

    def test_empty_search_and_unknown_category_are_truthful_empty_results(self):
        for query in ({"q": "هیچ محصولی"}, {"category_id": "999999"}):
            data = self.catalog(**query)
            self.assertEqual(data["items"], [])
            self.assertEqual(data["counts"]["filtered"]["total"], 0)
            self.assertEqual(data["pagination"]["pages"], 1)

    def test_invalid_filters_ids_and_out_of_range_page_fail_safely(self):
        for query in ({"visit_id": "bad"}, {"visit_id": "9" * 50}, {"page": "0"}, {"page_size": "101"}, {"category_id": "-1"}, {"priority": "unknown"}, {"q": "x" * 201}):
            self.assertEqual(self.get(**query).status_code, 400, query)
        self.assertEqual(self.get(page="999").status_code, 404)

    def test_anonymous_manager_dual_role_and_missing_profile_are_denied(self):
        for user in (None, self.staff, self.no_profile):
            self.api.force_authenticate(user)
            self.assertEqual(self.get().status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.api.force_authenticate(self.user)
        self.assertEqual(self.get().status_code, 403)

    def test_inactive_account_profile_customer_and_revoked_assignment_are_denied(self):
        for model, pk, expected in ((get_user_model(), self.user.pk, 403), (Salesperson, self.rep.pk, 403), (Customer, self.customer.pk, 404), (CustomerAssignment, CustomerAssignment.objects.get(customer=self.customer).pk, 404)):
            with self.subTest(model=model):
                model.objects.filter(pk=pk).update(is_active=False)
                self.assertEqual(self.get().status_code, expected)
                model.objects.filter(pk=pk).update(is_active=True)

    def test_service_rechecks_stale_user_and_salesperson_objects(self):
        self.user.salesperson_profile  # Cache the active profile on the original caller.
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.catalog()

    def test_foreign_missing_and_mismatched_visit_customer_contexts_are_denied(self):
        for query in ({"visit_id": self.foreign_visit.pk}, {"visit_id": 999999}, {"customer_code": self.foreign_customer.customer_code}, {"customer_code": "missing"}):
            self.assertEqual(self.get(**query).status_code, 404)
        CustomerAssignment.objects.create(customer=self.customer, salesperson=self.foreign_rep, start_date=timezone.localdate())
        self.api.force_authenticate(self.foreign_user)
        self.assertEqual(self.get().status_code, 404)  # Assignment cannot replace ownership.

    def test_planned_preparation_is_read_only_and_closed_visit_context_is_unavailable(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="PLANNED")
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(not item["can_add"] for item in response.data["items"]))
        self.assertEqual(response.data["items"][0]["non_addable_reason"], "VISIT_NOT_ACTIVE")
        for state in ("COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=state)
            self.assertEqual(self.get().status_code, 404)

    def test_signed_context_is_bound_to_actor_customer_and_visit(self):
        token = self.catalog()["catalog_context"]
        other_visit = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=timezone.localdate())
        self.assertEqual(self.get(visit_id=other_visit.pk, catalog_context=token).status_code, 409)
        CustomerAssignment.objects.create(customer=self.customer, salesperson=self.foreign_rep, start_date=timezone.localdate())
        Visit.objects.filter(pk=self.visit.pk).update(salesperson=self.foreign_rep)
        self.api.force_authenticate(self.foreign_user)
        self.assertEqual(self.get(catalog_context=token).status_code, 409)

    def test_tampered_and_expired_context_never_silently_starts_a_new_session(self):
        token = self.catalog()["catalog_context"]
        self.assertEqual(self.get(catalog_context=token + "x").status_code, 409)
        with patch("django.core.signing.time.time", return_value=10):
            old = self.catalog()["catalog_context"]
        with patch("django.core.signing.time.time", return_value=CONTEXT_MAX_AGE + 11):
            self.assertEqual(self.get(catalog_context=old).status_code, 409)

    def test_changed_rank_reason_or_regenerated_rows_surface_stale_context(self):
        for change in ({"rank": 8}, {"reason": "تغییر دلیل"}, {"is_active": False}, {"explanation_snapshot": {"changed": True}}):
            token = self.catalog()["catalog_context"]
            original = CustomerRecommendation.objects.filter(pk=self.recs[0].pk).values().get()
            CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(**change)
            self.assertEqual(self.get(catalog_context=token).status_code, 409)
            CustomerRecommendation.objects.filter(pk=self.recs[0].pk).update(**{key: original[key] for key in change})

    def test_inventory_and_price_changes_do_not_reorder_priority(self):
        first = self.catalog()
        Inventory.objects.filter(product=self.products[1]).update(available_quantity=0)
        ProductDemoPrice.objects.filter(product=self.products[1]).update(base_price=Decimal("999"))
        later = self.catalog(catalog_context=first["catalog_context"])
        self.assertEqual([item["product_id"] for item in first["items"]], [item["product_id"] for item in later["items"]])
        self.assertFalse(later["items"][0]["can_add"])

    def test_new_recommendations_do_not_join_or_reorder_existing_session(self):
        token = self.catalog()["catalog_context"]
        CustomerRecommendation.objects.create(customer=self.customer, product=self.products[3], rank=0, recommendation_type="CATEGORY")
        resumed = self.catalog(catalog_context=token)
        self.assertEqual(resumed["counts"]["overall"]["prioritized"], 3)
        self.assertFalse(next(item for item in resumed["items"] if item["product_id"] == self.products[3].pk)["is_prioritized"])

    def test_empty_saved_priority_context_stays_empty_after_new_recommendations(self):
        CustomerRecommendation.objects.filter(customer=self.customer).update(is_active=False)
        token = self.catalog()["catalog_context"]
        CustomerRecommendation.objects.create(customer=self.customer, product=self.products[3], rank=1, recommendation_type="CATEGORY")
        self.assertTrue(all(not item["is_prioritized"] for item in self.catalog(catalog_context=token)["items"]))

    def test_inactive_product_becomes_invisible_without_reordering_saved_recommendations(self):
        first = self.catalog()
        Product.objects.filter(pk=self.products[1].pk).update(is_active=False)
        resumed = self.catalog(catalog_context=first["catalog_context"])
        self.assertEqual([item["product_id"] for item in resumed["items"]], [item["product_id"] for item in first["items"] if item["product_id"] != self.products[1].pk])

    def _business_state(self):
        labels = ("customers", "products", "inventory", "recommendations", "visits", "sales_requests", "sales")
        return {model._meta.label: list(model.objects.order_by("pk").values()) for label in labels for model in apps.get_app_config(label).get_models()}

    def test_get_head_service_and_brief_are_zero_write_with_no_generation_or_llm(self):
        before = self._business_state()
        with patch.object(RecommendationEngine, "generate", side_effect=AssertionError("No generation")), patch.object(RecommendationEngine, "_save_recommendations", side_effect=AssertionError("No saving")), patch("apps.ai.ollama_client.OllamaClient.generate", side_effect=AssertionError("No AI")), CaptureQueriesContext(connection) as queries:
            self.catalog()
            response = self.get()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.api.head(reverse("product-catalog-v1"), {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk}).status_code, 200)
            self.assertEqual(self.client.get(response.data["items"][-1]["brief_url"]).status_code, 200)
        writes = [query["sql"] for query in queries if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))]
        self.assertEqual(writes, [])
        self.assertEqual(before, self._business_state())
        self.assertEqual(apps.get_model("sales_requests", "SalesRequest").objects.count(), 0)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)

    def test_api_contract_cache_policy_and_no_mutation_methods(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response.data["visit"], {"id": self.visit.pk, "status": "IN_PROGRESS"})
        self.assertEqual(response.data["customer"]["code"], self.customer.customer_code)
        for method in (self.api.post, self.api.put, self.api.patch, self.api.delete):
            self.assertEqual(method(reverse("product-catalog-v1")).status_code, 405)
        self.assertEqual(self.get(catalog_context="bad")["Cache-Control"], "no-store, private")

    def test_ordinary_brief_returns_to_bounded_guided_destination_with_filters_and_context(self):
        data = self.catalog(priority="ordinary", q="محصول", page_size="2", page="2")
        item = data["items"][0]
        response = self.client.get(item["brief_url"] + "&return_url=https://evil.invalid/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["recommendation"])
        target = urlsplit(response.context["return_url"])
        self.assertEqual(target.path, reverse("recommendation-presentation", args=[self.customer.customer_code]))
        self.assertEqual(target.netloc, "")
        query = parse_qs(target.query)
        self.assertEqual(query["visit_id"], [str(self.visit.pk)])
        self.assertEqual(query["product_id"], [str(item["product_id"])])
        self.assertEqual(query["catalog_context"], [data["catalog_context"]])
        self.assertEqual(query["priority"], ["ordinary"])
        self.assertEqual(query["q"], ["محصول"])
        self.assertEqual(query["page"], ["2"])
        self.assertNotIn("return_url", query)
        self.assertNotIn("recommendation_id", query)

    def test_brief_catalog_return_rejects_missing_tampered_foreign_and_closed_context(self):
        token = self.catalog()["catalog_context"]
        url = reverse("product-commercial-brief", args=[self.products[3].product_code])
        baseline = {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk, "return_to": "catalog", "catalog_context": token}
        for extra in ({"catalog_context": ""}, {"catalog_context": token + "x"}, {"visit_id": self.foreign_visit.pk}, {"visit_id": ""}, {"priority": "bad"}):
            self.assertEqual(self.client.get(url, {**baseline, **extra}).status_code, 404)
        Visit.objects.filter(pk=self.visit.pk).update(status="COMPLETED")
        self.assertEqual(self.client.get(url, baseline).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url, baseline).status_code, 404)

    def test_legacy_recommendation_brief_returns_are_unchanged(self):
        url = reverse("product-commercial-brief", args=[self.products[0].product_code])
        for visit in (None, self.visit.pk):
            query = {"customer_code": self.customer.customer_code, "return_to": "presentation"}
            if visit:
                query["visit_id"] = visit
            response = self.client.get(url, query)
            self.assertEqual(response.status_code, 200)
            target = urlsplit(response.context["return_url"])
            self.assertEqual(target.path, reverse("recommendation-presentation", args=[self.customer.customer_code]))
            self.assertEqual(parse_qs(target.query)["recommendation_id"], [str(self.recs[0].pk)])
            self.assertEqual(target.fragment, f"recommendation-{self.recs[0].pk}")

    def test_legacy_manager_brief_and_ordinary_customer_return_are_unchanged(self):
        url = reverse("product-commercial-brief", args=[self.products[3].product_code])
        for user in (self.user, self.staff):
            self.client.force_login(user)
            response = self.client.get(url, {"customer_code": self.customer.customer_code})
            self.assertEqual(response.status_code, 200)
            target = urlsplit(response.context["return_url"])
            self.assertEqual(target.path, "/customers/")
            self.assertEqual(target.fragment, "workspace-recommendations")

    def test_catalog_query_count_is_bounded_for_larger_catalog_and_page(self):
        with self.assertNumQueries(8):
            small = self.catalog(page_size="100")
        Product.objects.bulk_create([Product(product_code=f"MANY-{index:03}", name=f"کالای اضافی {index}", brand=self.brand, category=self.category) for index in range(80)])
        with self.assertNumQueries(8):
            large = self.catalog(page_size="100", catalog_context=small["catalog_context"])
        self.assertEqual(len(large["items"]), 86)
