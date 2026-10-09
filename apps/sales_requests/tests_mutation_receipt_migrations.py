"""Additive receipt migration checks on Django's isolated test database only."""
from datetime import date
from uuid import uuid4

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .models import SalesRequestMutationReceipt


class MutationReceiptSchemaTests(TestCase):
    def test_receipt_table_and_database_constraints_are_migrated(self):
        self.assertIn(SalesRequestMutationReceipt._meta.db_table, connection.introspection.table_names())
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, SalesRequestMutationReceipt._meta.db_table)
        self.assertTrue(constraints["srmr_unique_visit_command"]["unique"])
        self.assertEqual(constraints["srmr_unique_visit_command"]["columns"], ["visit_id", "command_uuid"])
        for name in ("srmr_valid_operation", "srmr_intent_not_empty", "srmr_revision_request_pair"):
            self.assertTrue(constraints[name]["check"])
        self.assertEqual(sum(bool(item["foreign_key"]) for item in constraints.values()), 3)

    def test_new_migration_is_single_additive_model_with_acyclic_dependencies(self):
        loader = MigrationExecutor(connection).loader
        key = ("sales_requests", "0002_salesrequestmutationreceipt")
        plan = loader.graph.forwards_plan(key)
        self.assertIn(("sales_requests", "0001_initial"), plan)
        self.assertIn((settings.AUTH_USER_MODEL.split(".")[0], "0001_initial"), plan)
        operations = loader.disk_migrations[key].operations
        self.assertEqual([type(operation).__name__ for operation in operations], ["CreateModel"])
        self.assertEqual(operations[0].name, "SalesRequestMutationReceipt")


class MutationReceiptMigrationRoundTripTests(TransactionTestCase):
    def test_forward_and_reverse_preserve_existing_foundations(self):
        executor = MigrationExecutor(connection)
        final_targets = executor.loader.graph.leaf_nodes()
        before_targets = [
            (app, "0001_initial") if app == "sales_requests" else (app, migration)
            for app, migration in final_targets
        ]
        try:
            executor.migrate(before_targets)
            before_apps = MigrationExecutor(connection).loader.project_state(before_targets).apps
            User = before_apps.get_model(settings.AUTH_USER_MODEL)
            Customer = before_apps.get_model("customers", "Customer")
            Salesperson = before_apps.get_model("visits", "Salesperson")
            Visit = before_apps.get_model("visits", "Visit")
            Request = before_apps.get_model("sales_requests", "SalesRequest")
            Line = before_apps.get_model("sales_requests", "SalesRequestLine")
            Brand = before_apps.get_model("products", "Brand")
            Category = before_apps.get_model("products", "Category")
            Product = before_apps.get_model("products", "Product")
            DemoPrice = before_apps.get_model("products", "ProductDemoPrice")
            Recommendation = before_apps.get_model("recommendations", "CustomerRecommendation")
            Feedback = before_apps.get_model("recommendations", "RecommendationFeedbackEvent")
            actor = User.objects.create(username="receipt-migration")
            customer = Customer.objects.create(customer_code="RECEIPT-MIG-C", name="مشتری")
            rep = Salesperson.objects.create(user_id=actor.pk, employee_code="RECEIPT-MIG-SP", first_name="A", last_name="Rep")
            visit = Visit.objects.create(customer=customer, salesperson=rep, visit_date=date(2026, 10, 8), status="IN_PROGRESS")
            request = Request.objects.create(visit=visit, revision=7, note="Existing draft preserved")
            product = Product.objects.create(
                product_code="RECEIPT-MIG-P", name="محصول",
                brand=Brand.objects.create(code="RECEIPT-MIG", name="Brand"),
                category=Category.objects.create(code="RECEIPT-MIG", name="Category"),
            )
            Line.objects.create(sales_request=request, product=product, quantity=2)
            DemoPrice.objects.create(product=product, base_price="123", currency="TOMAN", source="isolated-test", source_version="v1")
            rec = Recommendation.objects.create(customer=customer, product=product, recommendation_type="CATEGORY", rank=1, score=20)
            Feedback.objects.create(visit=visit, recommendation=rec, event_type="REJECTED", reason_code="LATER", lineage_snapshot={"recommendation_id": rec.pk})
            tracked = (User, Customer, Salesperson, Visit, Request, Line, Product, DemoPrice, Recommendation, Feedback)
            before = {model._meta.label_lower: list(model.objects.order_by("pk").values()) for model in tracked}

            MigrationExecutor(connection).migrate(final_targets)
            after_apps = MigrationExecutor(connection).loader.project_state(final_targets).apps
            Receipt = after_apps.get_model("sales_requests", "SalesRequestMutationReceipt")
            self.assertEqual(Receipt.objects.count(), 0)  # No data population.
            Receipt.objects.create(
                visit_id=visit.pk, actor_id=actor.pk, sales_request_id=request.pk,
                command_uuid=uuid4(), operation="SET_QUANTITY", intent_fingerprint="a" * 64,
                applied_revision=7, result={"http_status": 200, "body": {"revision": 7}},
            )
            for label, rows in before.items():
                self.assertEqual(list(after_apps.get_model(label).objects.order_by("pk").values()), rows)

            MigrationExecutor(connection).migrate(before_targets)
            self.assertNotIn("sales_requests_salesrequestmutationreceipt", connection.introspection.table_names())
            reverted_apps = MigrationExecutor(connection).loader.project_state(before_targets).apps
            for label, rows in before.items():
                self.assertEqual(list(reverted_apps.get_model(label).objects.order_by("pk").values()), rows)
        finally:
            MigrationExecutor(connection).migrate(final_targets)
