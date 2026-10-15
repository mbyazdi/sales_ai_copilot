"""Completion operation migration: isolated schema/data preservation checks."""
from datetime import date
from unittest import skipUnless
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase


class CompletionMigrationShapeTests(TestCase):
    def test_only_operation_choices_and_check_are_extended(self):
        loader = MigrationExecutor(connection).loader
        key = ("sales_requests", "0003_complete_visit_receipt")
        migration = loader.disk_migrations[key]
        self.assertEqual(migration.dependencies, [("sales_requests", "0002_salesrequestmutationreceipt")])
        self.assertEqual([type(op).__name__ for op in migration.operations],
                         ["RemoveConstraint", "AlterField", "AddConstraint"])
        with connection.cursor() as cursor:
            checks = connection.introspection.get_constraints(cursor, "sales_requests_salesrequestmutationreceipt")
        self.assertTrue(checks["srmr_valid_operation"]["check"])
        self.assertTrue(checks["srmr_unique_visit_command"]["unique"])


class CompletionMigrationRoundTripTests(TransactionTestCase):
    def targets(self):
        final = MigrationExecutor(connection).loader.graph.leaf_nodes()
        previous = [(app, "0002_salesrequestmutationreceipt") if app == "sales_requests" else (app, name)
                    for app, name in final]
        return previous, final

    def fixture(self, targets, operation):
        state = MigrationExecutor(connection).loader.project_state(targets).apps
        User = state.get_model(settings.AUTH_USER_MODEL)
        Customer = state.get_model("customers", "Customer")
        Rep = state.get_model("visits", "Salesperson")
        Visit = state.get_model("visits", "Visit")
        Receipt = state.get_model("sales_requests", "SalesRequestMutationReceipt")
        actor = User.objects.create(username="completion-migration")
        customer = Customer.objects.create(customer_code="FIN-MIG", name="مشتری سابق")
        rep = Rep.objects.create(user=actor, employee_code="FIN-MIG", first_name="A", last_name="B")
        visit = Visit.objects.create(customer=customer, salesperson=rep, visit_date=date(2026, 10, 15), status="IN_PROGRESS")
        receipt = Receipt.objects.create(visit=visit, actor=actor, command_uuid=uuid4(), operation=operation,
                                         intent_fingerprint="a" * 64, result={"http_status": 200, "body": {"old": True}})
        return state, (User, Customer, Rep, Visit, Receipt), receipt

    def test_forward_and_reverse_preserve_legacy_receipts_and_relations(self):
        previous, final = self.targets()
        try:
            MigrationExecutor(connection).migrate(previous)
            state, tracked, receipt = self.fixture(previous, "REJECT_RECOMMENDATION")
            before = {model._meta.label_lower: list(model.objects.order_by("pk").values()) for model in tracked}
            MigrationExecutor(connection).migrate(final)
            latest = MigrationExecutor(connection).loader.project_state(final).apps
            choices = dict(latest.get_model("sales_requests", "SalesRequestMutationReceipt")._meta.get_field("operation").choices)
            self.assertEqual(set(choices), {"ADD_PRODUCT", "SET_QUANTITY", "REMOVE_PRODUCT", "REJECT_RECOMMENDATION", "COMPLETE_VISIT"})
            for label, rows in before.items():
                self.assertEqual(list(latest.get_model(label).objects.order_by("pk").values()), rows)
            MigrationExecutor(connection).migrate(previous)
            reverted = MigrationExecutor(connection).loader.project_state(previous).apps
            for label, rows in before.items():
                self.assertEqual(list(reverted.get_model(label).objects.order_by("pk").values()), rows)
            Receipt = reverted.get_model("sales_requests", "SalesRequestMutationReceipt")
            with self.assertRaises(IntegrityError), transaction.atomic():
                Receipt.objects.create(visit_id=receipt.visit_id, actor_id=receipt.actor_id, command_uuid=uuid4(),
                                       operation="COMPLETE_VISIT", intent_fingerprint="b" * 64, result={"body": {"new": True}})
        finally:
            MigrationExecutor(connection).migrate(final)

    @skipUnless(connection.vendor == "postgresql", "Transactional PostgreSQL DDL rollback required")
    def test_reverse_with_completion_evidence_fails_without_deleting_history(self):
        previous, final = self.targets()
        state, tracked, receipt = self.fixture(final, "COMPLETE_VISIT")
        before = list(state.get_model("sales_requests", "SalesRequestMutationReceipt").objects.values())
        try:
            with self.assertRaises(IntegrityError):
                MigrationExecutor(connection).migrate(previous)
            self.assertEqual(list(state.get_model("sales_requests", "SalesRequestMutationReceipt").objects.values()), before)
            self.assertIn(("sales_requests", "0003_complete_visit_receipt"),
                          MigrationExecutor(connection).loader.applied_migrations)
        finally:
            MigrationExecutor(connection).migrate(final)
