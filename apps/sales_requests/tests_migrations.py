"""Schema checks and migration round-trip using only Django's isolated test DB."""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .models import SalesRequest, SalesRequestLine


class FoundationSchemaTests(TestCase):
    def test_migrated_tables_and_constraints_are_present(self):
        tables = connection.introspection.table_names()
        for name in ("products_productdemoprice", "sales_requests_salesrequest", "sales_requests_salesrequestline", "sales_requests_salesrequestacknowledgement", "recommendations_recommendationfeedbackevent"):
            self.assertIn(name, tables)
        with connection.cursor() as cursor:
            header = connection.introspection.get_constraints(cursor, SalesRequest._meta.db_table)
            line = connection.introspection.get_constraints(cursor, SalesRequestLine._meta.db_table)
        self.assertTrue(header["sr_valid_status"]["check"])
        self.assertTrue(header["sr_submission_fields"]["check"])
        self.assertTrue(line["srl_positive_quantity"]["check"])
        self.assertTrue(line["srl_unique_selected_product"]["unique"])
        self.assertTrue(any(item["unique"] and item["columns"] == ["visit_id"] for item in header.values()))

    def test_new_migrations_are_schema_only_and_have_an_acyclic_plan(self):
        loader = MigrationExecutor(connection).loader
        new = (("products", "0003_productdemoprice"), ("sales_requests", "0001_initial"), ("recommendations", "0012_recommendationfeedbackevent"), ("recommendations", "0013_recommendationfeedbackevent_line_and_more"))
        for key in new:
            self.assertIn(key, loader.graph.forwards_plan(key))
            self.assertTrue(all(type(op).__name__ in {"CreateModel", "AddField", "AddConstraint"} for op in loader.disk_migrations[key].operations))


class FoundationMigrationRoundTripTests(TransactionTestCase):
    def test_additive_migrations_preserve_legacy_rows(self):
        executor = MigrationExecutor(connection)
        final_targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([
                ("recommendations", "0011_customerrecommendation_confidence_score_and_more"),
                ("sales_requests", None),
                ("products", "0002_alter_category_options_product_is_consumable_and_more"),
            ])
            executor = MigrationExecutor(connection)
            state = executor.loader.project_state([
                ("recommendations", "0011_customerrecommendation_confidence_score_and_more"),
                ("products", "0002_alter_category_options_product_is_consumable_and_more"),
                ("visits", "0007_alter_visitcommercialsnapshot_target_context"),
                ("sales", "0001_initial"),
            ]).apps
            Customer = state.get_model("customers", "Customer")
            Salesperson = state.get_model("visits", "Salesperson")
            Visit = state.get_model("visits", "Visit")
            Brand = state.get_model("products", "Brand")
            Category = state.get_model("products", "Category")
            Product = state.get_model("products", "Product")
            Recommendation = state.get_model("recommendations", "CustomerRecommendation")
            Outcome = state.get_model("visits", "SalesOutcome")
            Sale = state.get_model("sales", "Sale")
            SaleItem = state.get_model("sales", "SaleItem")
            customer = Customer.objects.create(customer_code="MIG-C", name="مشتری سابق")
            rep = Salesperson.objects.create(employee_code="MIG-SP", first_name="نماینده", last_name="سابق")
            visit = Visit.objects.create(customer=customer, salesperson=rep, visit_date=date(2026, 10, 7), status="IN_PROGRESS")
            product = Product.objects.create(product_code="MIG-P", name="محصول سابق", brand=Brand.objects.create(code="MIG", name="Brand"), category=Category.objects.create(code="MIG", name="Category"))
            rec = Recommendation.objects.create(customer=customer, product=product, recommendation_type="CATEGORY", rank=1, score=20)
            Outcome.objects.create(visit=visit, recommendation=rec, outcome="PURCHASED", quantity=2, sales_amount=123)
            sale = Sale.objects.create(customer=customer, invoice_number="MIG-HISTORICAL", sale_date=date(2026, 10, 1), total_amount=50)
            SaleItem.objects.create(sale=sale, product=product, quantity=1, unit_price=50, total_amount=50)
            tracked = (Customer, Salesperson, Visit, Product, Recommendation, Outcome, Sale, SaleItem)
            before = {model._meta.label_lower: list(model.objects.order_by("pk").values()) for model in tracked}
            MigrationExecutor(connection).migrate(final_targets)
            current = MigrationExecutor(connection).loader.project_state(final_targets).apps
            for label, rows in before.items():
                app, model = label.split(".")
                self.assertEqual(list(current.get_model(app, model).objects.order_by("pk").values()), rows)
            for app, model in (("sales_requests", "SalesRequest"), ("products", "ProductDemoPrice"), ("recommendations", "RecommendationFeedbackEvent")):
                self.assertEqual(current.get_model(app, model).objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(final_targets)
