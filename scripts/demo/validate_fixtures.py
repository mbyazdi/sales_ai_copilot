"""Focused synthetic-Demo acceptance. Business mutation probes always roll back."""
import json
import re
from decimal import Decimal
import unittest
from uuid import uuid4

from common import *
from bootstrap import MANIFEST, ACCOUNTS, definition, digest, verify_existing


class FixtureAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read_json(MANIFEST)
        cls.accounts = read_json(ACCOUNTS)["accounts"]
        from django.test import Client
        cls.clients = {}
        for role, account in cls.accounts.items():
            client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost", SERVER_NAME="localhost")
            page = client.get("/accounts/login/")
            require(page.status_code == 200 and b"csrfmiddlewaretoken" in page.content, "Normal login form missing.")
            proof = re.search(rb'data-demo-proof="([^"]+)"', page.content)
            if proof:
                client.defaults["HTTP_X_DEMO_GENERATION_PROOF"] = proof.group(1).decode("ascii")
            token = client.cookies["csrftoken"].value
            response = client.post("/accounts/login/", dict(username=account["username"], password=account["password"],
                csrfmiddlewaretoken=token), HTTP_ORIGIN="http://localhost:8900")
            require(response.status_code == 302 and "sales_ai_demo_session" in client.cookies, "Normal TEST login failed.")
            cls.clients[role] = client

    @classmethod
    def tearDownClass(cls):
        from django.contrib.sessions.models import Session
        for client in cls.clients.values():
            key = client.cookies["sales_ai_demo_session"].value
            response = client.post("/accounts/logout/", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
                                   HTTP_ORIGIN="http://localhost:8900")
            require(response.status_code == 302 and not Session.objects.filter(session_key=key).exists(), "Session invalidation failed.")

    def request(self, path, body):
        client = self.clients["salesperson"]
        return client.post(path, json.dumps(body), content_type="application/json",
                           HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value, HTTP_ORIGIN="http://localhost:8900")

    def visit(self, code):
        return self.manifest["visits"][code]["id"]

    def start(self, code):
        self.assertEqual(self.request(f"/api/visits/v1/visits/{self.visit(code)}/start/", {}).status_code, 200)

    def catalog(self, code):
        response = self.clients["salesperson"].get("/api/products/v1/catalog/", {"customer_code": code, "visit_id": self.visit(code)})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def add(self, code, product_code, context):
        from apps.products.models import Product
        product_id = Product.objects.get(product_code=product_code).pk
        response = self.clients["salesperson"].get(f"/api/sales-requests/v1/visits/{self.visit(code)}/basket/quote/",
            {"customer_code": code, "product_id": product_id, "quantity": 1})
        self.assertEqual(response.status_code, 200)
        quote = response.json()
        self.assertTrue(quote["valid"])
        result = self.request(f"/api/sales-requests/v1/visits/{self.visit(code)}/lines/", dict(
            customer_code=code, product_id=product_id, quantity=1, catalog_context=context,
            expected_request_revision=quote["expected_request_revision"], command_uuid=str(uuid4()),
            accepted_quote_fingerprint=quote["quote_fingerprint"]))
        self.assertEqual(result.status_code, 201)
        return result.json()

    def test_01_fixture_identity_and_prices(self):
        from datetime import date
        fixture = definition(date.fromisoformat(self.manifest["preparation_date"]))
        self.assertEqual(digest(fixture), self.manifest["fixture_sha256"])
        verify_existing(self.manifest, fixture)
        from apps.products.models import Product, ProductDemoPrice
        from apps.recommendations.models import CustomerRecommendation
        from apps.inventory.models import Inventory
        self.assertEqual((Product.objects.count(), ProductDemoPrice.objects.count(), Inventory.objects.count(), CustomerRecommendation.objects.count()),
                         (14, 14, 13, 15))

    def test_02_initial_visit_states_and_lifecycle_snapshots(self):
        from apps.visits.models import Visit, VisitCustomerSnapshot, VisitCommercialSnapshot
        actual = dict(Visit.objects.values_list("customer__customer_code", "status"))
        self.assertEqual(actual, {code: "IN_PROGRESS" if code == "C0005" else "PLANNED" for code in self.manifest["visits"]})
        self.assertEqual(list(VisitCustomerSnapshot.objects.values_list("visit_id", flat=True)), [self.visit("C0005")])
        self.assertEqual(list(VisitCommercialSnapshot.objects.values_list("visit_id", flat=True)), [self.visit("C0005")])

    def test_03_grade_pricing(self):
        from apps.products.pricing import DemoPriceProvider
        from apps.products.models import Product
        from apps.customers.models import Customer
        pk = Product.objects.get(product_code="PHD001").pk
        for code, amount in (("C0003", 2160000), ("C0005", 2280000), ("C0013", 2400000)):
            quote = DemoPriceProvider().quote_many(Customer.objects.get(customer_code=code).pk, {pk: 1})[pk].quote
            self.assertEqual(quote.final_unit_price, Decimal(amount))

    def test_04_authorization_and_manager(self):
        path = f"/api/products/v1/catalog/?customer_code=C0003&visit_id={self.visit('C0003')}"
        self.assertEqual(self.clients["manager"].get("/management/").status_code, 200)
        for role in ("manager", "unauthorized"):
            self.assertEqual(self.clients[role].get(path).status_code, 403)
        self.assertEqual(self.clients["salesperson"].get("/management/").status_code, 302)
        self.assertIn(self.clients["salesperson"].get(f"/api/products/v1/catalog/?customer_code=C0003&visit_id={self.visit('C0013')}").status_code, (403,404))

    def test_05_daily_plan_all_today(self):
        from apps.visits.models import Visit
        from django.utils import timezone
        response = self.clients["salesperson"].get("/api/visits/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Visit.objects.filter(visit_date=timezone.localdate()).count(), 5)
        for code in self.manifest["visits"]:
            self.assertIn(code.encode(), response.content)

    def test_06_complete_sale_add_capability_rollback(self):
        from django.db import transaction
        from apps.sales_requests.models import SalesRequest
        from apps.recommendations.models import RecommendationFeedbackEvent
        with transaction.atomic():
            self.start("C0003")
            catalog = self.catalog("C0003")
            context = catalog["catalog_context"]
            self.add("C0003", "PHD001", context)
            result = self.add("C0003", "PHS001", context)
            self.assertEqual(result["request"]["status"], "DRAFT")
            self.assertEqual(SalesRequest.objects.get(visit_id=self.visit("C0003")).lines.filter(is_selected=True).count(), 2)
            self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("event_type", flat=True)), ["ADDED_TO_REQUEST"])
            transaction.set_rollback(True)
        self.assertEqual(SalesRequest.objects.count(), 0)

    def test_07_no_sale_completion_rollback(self):
        from django.db import transaction
        from apps.sales_requests.models import SalesRequest
        with transaction.atomic():
            self.start("C0013")
            response = self.request(f"/api/visits/v1/visits/{self.visit('C0013')}/completion/",
                {"customer_code": "C0013", "command_uuid": str(uuid4())})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["visit"]["status"], "COMPLETED")
            self.assertEqual(SalesRequest.objects.count(), 0)
            transaction.set_rollback(True)

    def test_08_retained_draft_and_low_stock_rollback(self):
        from django.db import transaction
        from apps.sales_requests.models import SalesRequest
        from apps.visits.models import Visit
        with transaction.atomic():
            self.start("C0014")
            self.add("C0014", "PHI004", self.catalog("C0014")["catalog_context"])
            draft = SalesRequest.objects.get(visit_id=self.visit("C0014"))
            before = (draft.status, draft.revision, list(draft.lines.values()))
            response = self.request(f"/api/visits/v1/visits/{self.visit('C0014')}/completion/",
                {"customer_code": "C0014", "command_uuid": str(uuid4())})
            self.assertEqual(response.status_code, 200)
            draft.refresh_from_db()
            self.assertEqual((draft.status, draft.revision, list(draft.lines.values())), before)
            self.assertEqual(Visit.objects.get(pk=self.visit("C0014")).status, "COMPLETED")
            transaction.set_rollback(True)

    def test_09_unknown_zero_low_stock(self):
        from apps.products.models import Product
        for code, quantity, expected in (("TEF003",1,"INVENTORY_UNKNOWN"), ("ROW001",1,"OUT_OF_STOCK"), ("PHI004",2,"INSUFFICIENT_STOCK")):
            pk = Product.objects.get(product_code=code).pk
            response = self.clients["salesperson"].get(f"/api/sales-requests/v1/visits/{self.visit('C0005')}/quote/",
                {"customer_code":"C0005", "items":json.dumps([{"product_id":pk,"quantity":quantity}])})
            self.assertEqual(response.status_code, 200)
            item = response.json()["items"][0]
            self.assertFalse(item["can_add"])
            self.assertEqual(item["non_addable_reason"], expected)

    def test_10_get_does_not_create_business_history(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestMutationReceipt, SalesRequestAcknowledgement
        from apps.recommendations.models import RecommendationFeedbackEvent
        self.catalog("C0005")
        response = self.clients["salesperson"].get(f"/api/sales-requests/v1/visits/{self.visit('C0005')}/basket/", {"customer_code":"C0005"})
        self.assertEqual(response.status_code, 200)
        for model in (SalesRequest, SalesRequestMutationReceipt, SalesRequestAcknowledgement, RecommendationFeedbackEvent):
            self.assertEqual(model.objects.count(), 0)

    def test_11_decimal_comparison_preserves_real_changes(self):
        from bootstrap import canonical_fields
        from apps.customers.models import Customer360
        self.assertEqual(canonical_fields(Customer360, {"total_sales_amount": "0"}),
                         canonical_fields(Customer360, {"total_sales_amount": "0.00"}))
        self.assertNotEqual(canonical_fields(Customer360, {"total_sales_amount": "0"}),
                            canonical_fields(Customer360, {"total_sales_amount": "0.01"}))


if __name__ == "__main__":
    profile = load_profile(); verify_container(profile)
    configure_django(profile, DEFAULT_STATE); check_schema(profile)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureAcceptance))
    write_json(DEFAULT_STATE / "reports/b2a/focused-validation.json", dict(
        database=DATABASE, tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), business_mutations="rollback-only", normal_test_login_logout=True))
    sys.exit(0 if result.wasSuccessful() else 1)
