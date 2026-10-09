"""Static image approval/fallback boundaries and existing journey integration."""
from copy import deepcopy
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.demo_assets import _manifest, _verified_file, demo_image
from apps.products.catalog import build_catalog
from apps.products.tests_catalog import CatalogBackendTests


class DemoAssetRegistryTests(SimpleTestCase):
    def test_original_photos_and_owner_approved_generated_assets_are_distinct(self):
        enabled = {code for code, row in _manifest()["products"].items() if row["demo_enabled"]}
        self.assertEqual(len(enabled), 14)
        self.assertEqual(len(_manifest()["products"]), 14)
        self.assertEqual(len(_manifest()["stores"]), 10)
        for code in {"BRN001", "BRN002", "PHI002"}:
            image = demo_image("products", code)
            self.assertEqual(image["state"], "REPRESENTATIVE")
            self.assertTrue(image["url"].startswith("/static/demo/products/"))
            self.assertIn("مدل دقیق تأیید نشده", image["label"])
            self.assertTrue(image["credit"]["source_url"].startswith("https://"))
            self.assertTrue(image["credit"]["author"])
        for code in enabled - {"BRN001", "BRN002", "PHI002"}:
            image = demo_image("products", code)
            self.assertEqual(image["state"], "GENERATED_REPRESENTATIVE")
            self.assertIn("/generated-v1/", image["url"])
            self.assertIn("هوش مصنوعی", image["description"])
            self.assertIsNone(image["credit"]["source_url"])
            self.assertIsNone(image["credit"]["licence_url"])

    def test_unmapped_and_disabled_assets_keep_existing_fallback(self):
        missing = {"url": None, "state": "MISSING"}
        for code, entry in _manifest()["products"].items():
            if not entry["demo_enabled"]:
                self.assertEqual(demo_image("products", code), missing)
        self.assertEqual(demo_image("products", "not-a-demo-sku"), missing)
        self.assertEqual(demo_image("stores", "not-a-demo-customer"), missing)

    def test_missing_or_altered_file_fails_closed(self):
        document = deepcopy(_manifest())
        document["products"]["BRN001"]["files"]["thumb"]["sha256"] = "0" * 64
        with patch("apps.core.demo_assets._manifest", return_value=document):
            self.assertIsNone(demo_image("products", "BRN001")["url"])
        self.assertFalse(_verified_file("static/demo/../../db.sqlite3", "0" * 64))
        self.assertFalse(_verified_file("https://example.com/image.webp", "0" * 64))
        self.assertFalse(_verified_file("static/demo/missing.webp", "0" * 64))

    def test_approval_and_permission_are_not_inferred_from_file_existence(self):
        document = deepcopy(_manifest())
        document["products"]["BRN001"]["demo_enabled"] = False
        with patch("apps.core.demo_assets._manifest", return_value=document):
            self.assertIsNone(demo_image("products", "BRN001")["url"])

    def test_store_slots_disclose_generated_samples_and_dutch_geography_difference(self):
        for code in _manifest()["stores"]:
            image = demo_image("stores", code)
            self.assertEqual(image["label"], "تصویر نمونهٔ فروشگاه")
            self.assertEqual(image["state"], "GENERATED_REPRESENTATIVE")
            self.assertIn("محل واقعی مشتری در هلند نیست", image["description"])

    def test_archived_real_image_checksums_remain_valid(self):
        import json
        import hashlib
        from django.conf import settings
        old = json.loads((settings.BASE_DIR / "static/demo/products/manifest.v1.json").read_text(encoding="utf-8"))
        for entry in old["products"].values():
            for file in entry["files"].values():
                self.assertEqual(hashlib.sha256((settings.BASE_DIR / file["path"]).read_bytes()).hexdigest(), file["sha256"])


class DemoAssetJourneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        CatalogBackendTests.setUpTestData.__func__(cls)
        cls.products[0].product_code = "BRN001"
        cls.products[0].save(update_fields=["product_code"])

    def setUp(self):
        self.client.force_login(self.user)

    def test_catalog_image_addition_preserves_ranking_inventory_and_zero_write(self):
        with CaptureQueriesContext(connection) as queries:
            catalog = build_catalog(self.user, self.customer.customer_code, self.visit.pk)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertEqual([r["product_id"] for r in catalog["items"]], [self.products[i].pk for i in (1, 2, 0, 3, 4, 5)])
        selected = next(row for row in catalog["items"] if row["product_code"] == "BRN001")
        self.assertEqual(selected["image"]["state"], "REPRESENTATIVE")
        self.assertEqual(selected["available_quantity"], 8)
        self.assertNotIn("final_price", selected)
        self.assertIsNone(next(row for row in catalog["items"] if row["product_code"] == "CAT-5")["image"]["url"])

    def test_product_detail_uses_existing_slot_and_visible_label_credit(self):
        response = self.client.get(reverse("product-commercial-brief", args=["BRN001"]),
                                   {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk})
        self.assertContains(response, "demo/products/BRN001/hero.webp")
        self.assertContains(response, "تصویر نمونه محصول؛ مدل دقیق تأیید نشده")
        self.assertContains(response, '<details class="demo-image-info">')
        self.assertContains(response, '<summary>اطلاعات تصویر</summary>')
        self.assertNotContains(response, '<details class="demo-image-info" open')
        self.assertContains(response, "Malcolm Koo")
        self.assertContains(response, "CC BY-SA 4.0")
        self.assertContains(response, 'width="56" height="56"')
        self.assertContains(response, "data-demo-fallback hidden")
        self.assertEqual(response.context["return_url"].split("#")[0],
                         f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}")

    def test_detail_fallback_and_foreign_customer_denial_remain(self):
        url = reverse("product-commercial-brief", args=[self.products[4].product_code])
        response = self.client.get(url, {"customer_code": self.customer.customer_code})
        self.assertNotContains(response, "data-demo-image")
        self.assertEqual(self.client.get(url, {"customer_code": self.foreign_customer.customer_code}).status_code, 404)

    def test_guided_store_fallback_and_reserved_action_regions_remain(self):
        response = self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]),
                                   {"visit_id": self.visit.pk})
        self.assertContains(response, "تصویر مشتری ثبت نشده است")
        self.assertContains(response, 'class="gc-quantity-slot" aria-hidden="true"></div>')
        self.assertContains(response, 'class="gc-add-slot" aria-hidden="true"></div>')
        self.assertContains(response, "data-image-disclosure")

    def test_generated_store_in_guided_and_customer_preserves_city_and_read_only_context(self):
        self.customer.customer_code = "C0003"
        self.customer.city = "Eindhoven"
        self.customer.save(update_fields=["customer_code", "city"])
        for url in (reverse("recommendation-presentation", args=["C0003"]), "/customers/"):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url, {"customer_code": "C0003", "visit_id": self.visit.pk})
            self.assertContains(response, "demo/stores/C0003/thumb.webp")
            self.assertContains(response, "تصویر نمونهٔ فروشگاه")
            self.assertContains(response, "محل واقعی مشتری در هلند نیست")
            self.assertContains(response, '<details class="demo-store-info">')
            self.assertContains(response, '<summary>اطلاعات تصویر</summary>')
            self.assertNotContains(response, '<details class="demo-store-info" open')
            self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.city, "Eindhoven")

    def test_generated_product_is_labelled_without_fabricated_model_or_price(self):
        self.products[4].product_code = "PHD001"
        self.products[4].save(update_fields=["product_code"])
        response = self.client.get(reverse("product-commercial-brief", args=["PHD001"]),
                                   {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk})
        self.assertContains(response, "generated-v1/hero.webp")
        self.assertContains(response, "تصویر نمونه محصول؛ مدل دقیق تأیید نشده")
        self.assertContains(response, "عکس محصول واقعی نیست")
        self.assertNotContains(response, "قیمت نهایی")
