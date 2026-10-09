"""Approved price configuration validation; all writes belong to isolated tests."""
import copy
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerGrade
from apps.visits.models import CustomerAssignment, Salesperson, Visit

from .demo_price_loader import (
    DATASET_PATH, DATASET_SHA256, DemoPriceLoadError, apply_demo_prices,
    plan_demo_prices, read_frozen_dataset, rollback_demo_prices,
)
from .models import Brand, Category, Product, ProductDemoPrice
from .pricing import DemoPriceProvider, calculate_demo_quote


class DemoPriceLoaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Existing catalog names/types retained; no inferred model or specifications.
        identities = {
            "PHD001": ("Philips", "Hair Dryer", "Philips Hair Dryer 2100W"),
            "PHS001": ("Philips", "Hair Straightener", "Philips Hair Straightener"),
            "BRN001": ("Braun", "Electric Shaver", "Braun Electric Shaver Series 3"),
            "BRN002": ("Braun", "Trimmer", "Braun Beard Trimmer"),
            "PAN001": ("Panasonic", "Hair Curler", "Panasonic Hair Curler"),
            "PHI002": ("Philips", "Electric Toothbrush", "Philips Electric Toothbrush"),
            "BOS001": ("Bosch", "Vacuum Cleaner", "Bosch Vacuum Cleaner"),
            "TEF001": ("Tefal", "Steam Iron", "Tefal Steam Iron"),
            "BOS002": ("Bosch", "Blender", "Bosch Blender"),
            "PHI003": ("Philips", "Electric Kettle", "Philips Electric Kettle"),
            "TEF002": ("Tefal", "Air Fryer", "Tefal Air Fryer"),
            "ROW001": ("Rowenta", "Coffee Maker", "Rowenta Coffee Maker"),
            "PHI004": ("Philips", "Blender", "Philips Blender"),
            "TEF003": ("Tefal", "Blender", "Tefal Blender"),
        }
        cls.products = {}
        for code, (brand_name, category_name, name) in identities.items():
            brand, _ = Brand.objects.get_or_create(code=brand_name.upper(), defaults={"name": brand_name})
            category, _ = Category.objects.get_or_create(code=category_name.replace(" ", "-").upper(), defaults={"name": category_name})
            cls.products[code] = Product.objects.create(
                product_code=code, name=name, brand=brand, category=category,
                description=name, unit="PCS", package_size="1 PCS",
                is_consumable=code == "PHI002", is_durable=True,
            )
        cls.user = get_user_model().objects.create_user(username="demo06-validation")
        cls.rep = Salesperson.objects.create(user=cls.user, employee_code="DEMO06-R",
                                            first_name="نماینده", last_name="آزمایشی")
        cls.grade_a = CustomerGrade.objects.create(code="A", name="الف")
        cls.grade_b = CustomerGrade.objects.create(code="B", name="ب")
        cls.grade_c = CustomerGrade.objects.create(code="C", name="ج")
        cls.customer = Customer.objects.create(customer_code="DEMO06-C", name="مشتری آزمایشی", grade=cls.grade_a)
        cls.visit = Visit.objects.create(customer=cls.customer, salesperson=cls.rep,
                                        visit_date=timezone.localdate(), status="IN_PROGRESS")
        CustomerAssignment.objects.create(customer=cls.customer, salesperson=cls.rep, start_date=timezone.localdate())

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Controlled loader validation requires isolated PostgreSQL")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            self.target = cursor.fetchone()[0]
        self.assertTrue(self.target.startswith("test_"), "Never run load-validation tests against runtime data")

    def load(self):
        return apply_demo_prices(expected_database=self.target)

    def unrelated_price(self):
        first = self.products["PHD001"]
        product = Product.objects.create(product_code="UNRELATED", name="محصول دیگر",
                                         brand=first.brand, category=first.category)
        return ProductDemoPrice.objects.create(product=product, base_price=Decimal("777"),
                                              currency="TOMAN", source="other-source", source_version="v1")

    def test_frozen_checksum_is_line_ending_independent_and_tampering_is_rejected(self):
        original = read_frozen_dataset()
        self.assertEqual(len(original["prices"]), 14)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dataset.json"
            path.write_bytes(DATASET_PATH.read_bytes().replace(b"\n", b"\r\n"))
            self.assertEqual(read_frozen_dataset(path), original)
            changed = copy.deepcopy(original)
            changed["prices"]["PHD001"] = "1"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(DemoPriceLoadError) as error:
                read_frozen_dataset(path)
            self.assertEqual(error.exception.code, "DATASET_CHECKSUM_MISMATCH")

    def test_preflight_is_select_only_and_no_price_is_created(self):
        with CaptureQueriesContext(connection) as queries:
            plan = plan_demo_prices(expected_database=self.target)
        self.assertEqual(len(plan["create_codes"]), 14)
        self.assertEqual(plan["skip_codes"], [])
        self.assertEqual(plan["dataset_sha256"], DATASET_SHA256)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertFalse(ProductDemoPrice.objects.exists())

    def test_first_load_creates_exact_dataset_and_identical_rerun_is_no_op(self):
        first = self.load()
        self.assertEqual((first["created_count"], first["skipped_count"]), (14, 0))
        before = list(ProductDemoPrice.objects.order_by("pk").values())
        fingerprints = DemoPriceProvider().quote_many(self.customer.pk, {p.pk: 1 for p in self.products.values()})
        with CaptureQueriesContext(connection) as queries:
            second = self.load()
        self.assertEqual((second["created_count"], second["skipped_count"]), (0, 14))
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(list(ProductDemoPrice.objects.order_by("pk").values()), before)
        self.assertEqual(DemoPriceProvider().quote_many(self.customer.pk, {p.pk: 1 for p in self.products.values()}), fingerprints)
        data = read_frozen_dataset()
        for code, amount in data["prices"].items():
            row = ProductDemoPrice.objects.get(product=self.products[code])
            self.assertEqual((row.base_price, row.currency, row.source, row.source_version),
                             (Decimal(amount), "TOMAN", "DEMO_ONLY_FICTIONAL", "DEMO_06_V1"))

    def test_all_14_quote_api_prices_match_a_b_other_and_missing_grade(self):
        self.load()
        api = APIClient()
        api.force_authenticate(self.user)
        items = [{"product_id": p.pk, "quantity": 1} for p in self.products.values()]
        data = read_frozen_dataset()
        for grade in (self.grade_a, self.grade_b, self.grade_c, None):
            Customer.objects.filter(pk=self.customer.pk).update(grade=grade)
            response = api.get(reverse("visit-quote-v1", args=[self.visit.pk]),
                               {"customer_code": self.customer.customer_code, "items": json.dumps(items)})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data["items"]), 14)
            for item in response.data["items"]:
                code = item["product_code"]
                expected = calculate_demo_quote(customer_id=self.customer.pk, product_id=self.products[code].pk,
                    grade_code=grade.code if grade else None, quantity=1, base_price=Decimal(data["prices"][code]),
                    currency="TOMAN", price_source="DEMO_ONLY_FICTIONAL", price_source_version="DEMO_06_V1")
                self.assertEqual(item["pricing"]["state"], "AVAILABLE")
                self.assertEqual(item["pricing"]["quote"], expected.as_dict())
                # No stock fixture fabricated: price availability is not addability.
                self.assertEqual(item["inventory"]["state"], "UNKNOWN")
                self.assertFalse(item["can_add"])

    def test_conflicting_amount_or_source_version_aborts_without_partial_load(self):
        for changes in ({"base_price": Decimal("1")}, {"source": "other-source"}, {"source_version": "OTHER"}):
            with self.subTest(changes=changes):
                data = dict(product=self.products["PHD001"], base_price=Decimal("2400000"), currency="TOMAN",
                            source="DEMO_ONLY_FICTIONAL", source_version="DEMO_06_V1")
                data.update(changes)
                row = ProductDemoPrice.objects.create(**data)
                before = list(ProductDemoPrice.objects.values())
                with self.assertRaises(DemoPriceLoadError) as error:
                    self.load()
                self.assertEqual(error.exception.code, "EXISTING_PRICE_CONFLICT")
                self.assertEqual(list(ProductDemoPrice.objects.values()), before)
                row.delete()

    def test_mid_load_failure_rolls_back_all_price_inserts(self):
        original = ProductDemoPrice.save
        calls = []
        def fail_later(row, *args, **kwargs):
            calls.append(row.product_id)
            if len(calls) == 4:
                raise RuntimeError("Injected isolated validation failure")
            return original(row, *args, **kwargs)
        with patch.object(ProductDemoPrice, "save", fail_later), self.assertRaises(RuntimeError):
            self.load()
        self.assertEqual(len(calls), 4)
        self.assertFalse(ProductDemoPrice.objects.exists())

    def test_load_and_rollback_preserve_unrelated_and_all_nonprice_records(self):
        unrelated = self.unrelated_price()
        unrelated_before = list(ProductDemoPrice.objects.filter(pk=unrelated.pk).values())
        models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy and m is not ProductDemoPrice]
        before = {m: list(m.objects.order_by("pk").values()) for m in models}
        report = self.load()
        self.assertEqual(rollback_demo_prices(json.loads(json.dumps(report)), expected_database=self.target)["deleted_count"], 14)
        self.assertEqual(list(ProductDemoPrice.objects.values()), unrelated_before)
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows, model._meta.label)
        self.assertTrue(Product.objects.get(product_code="PHI002").is_consumable)

    def test_matching_preexisting_row_is_skipped_and_not_owned_by_rollback(self):
        existing = ProductDemoPrice.objects.create(product=self.products["PHD001"], base_price=Decimal("2400000"),
            currency="TOMAN", source="DEMO_ONLY_FICTIONAL", source_version="DEMO_06_V1")
        before = list(ProductDemoPrice.objects.filter(pk=existing.pk).values())
        report = self.load()
        self.assertEqual((report["created_count"], report["skipped_count"]), (13, 1))
        self.assertEqual(rollback_demo_prices(report, expected_database=self.target)["deleted_count"], 13)
        self.assertEqual(list(ProductDemoPrice.objects.values()), before)

    def test_later_edits_block_rollback_before_any_delete(self):
        report = self.load()
        row = ProductDemoPrice.objects.get(product=self.products["PHD001"])
        row.base_price = Decimal("1")
        row.save()
        before = list(ProductDemoPrice.objects.order_by("pk").values())
        with self.assertRaises(DemoPriceLoadError) as error:
            rollback_demo_prices(report, expected_database=self.target)
        self.assertEqual(error.exception.code, "ROLLBACK_CONFLICT")
        self.assertEqual(list(ProductDemoPrice.objects.order_by("pk").values()), before)

    def test_repeat_rollback_is_no_op_and_wrong_target_is_rejected(self):
        report = self.load()
        rollback_demo_prices(report, expected_database=self.target)
        second = rollback_demo_prices(report, expected_database=self.target)
        self.assertEqual(second["deleted_count"], 0)
        self.assertEqual(len(second["already_absent_codes"]), 14)
        with self.assertRaises(DemoPriceLoadError) as error:
            plan_demo_prices(expected_database="not-this-database")
        self.assertEqual(error.exception.code, "DATABASE_MISMATCH")

    def test_master_unit_mismatch_is_rejected_without_repair_or_price_write(self):
        product = self.products["PAN001"]
        product.unit = "BOX"
        product.save(update_fields=["unit"])
        with self.assertRaises(DemoPriceLoadError) as error:
            self.load()
        self.assertEqual(error.exception.code, "PRODUCT_UNIT_OR_STATUS_MISMATCH")
        product.refresh_from_db()
        self.assertEqual(product.unit, "BOX")
        self.assertFalse(ProductDemoPrice.objects.exists())
