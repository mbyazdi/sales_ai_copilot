"""V3.0.10.9 characterization using isolated Django test-database records."""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.models import Customer, Customer360, CustomerGrade
from apps.inventory.models import Inventory
from apps.products.models import Brand, Category, Product
from apps.recommendations.models import CustomerRecommendation
from apps.sales.models import Sale, SaleItem

from .models import (
    CustomerAssignment, FollowUpTask, SalesOutcome, Salesperson, Visit,
    VisitCommercialSnapshot, VisitCustomerSnapshot,
)
from .services import capture_visit_commercial_snapshot, capture_visit_customer_snapshot


class VisitBaselineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="owner")
        cls.other_user = get_user_model().objects.create_user(username="other")
        cls.salesperson = Salesperson.objects.create(
            user=cls.user, employee_code="SP001", first_name="Test", last_name="Owner",
        )
        Salesperson.objects.create(
            user=cls.other_user, employee_code="SP002", first_name="Other", last_name="Rep",
        )
        cls.customer = Customer.objects.create(
            customer_code="C0003", name="Test customer",
            grade=CustomerGrade.objects.create(code="A", name="Grade A"),
        )
        cls.customer360 = Customer360.objects.create(
            customer=cls.customer, total_orders=3, total_sales_amount=Decimal("300"),
            average_order_value=Decimal("100"), segment="HIGH_VALUE", rfm_score=12,
        )
        cls.product = Product.objects.create(
            product_code="TEST-PRODUCT", name="Test product",
            brand=Brand.objects.create(code="TEST", name="Test brand"),
            category=Category.objects.create(code="TEST", name="Test category"),
        )
        cls.inventory = Inventory.objects.create(
            product=cls.product, available_quantity=12, reserved_quantity=2, minimum_stock=3,
        )
        cls.recommendation = CustomerRecommendation.objects.create(
            customer=cls.customer, product=cls.product, recommendation_type="CROSS_SELL",
            score=Decimal("60"), rank=1, reason="Baseline reason", confidence_score=70,
        )
        cls.visit = Visit.objects.create(
            customer=cls.customer, salesperson=cls.salesperson, visit_date=timezone.localdate(),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def transition(self, action):
        return self.client.post(reverse("visit-" + action, args=[self.visit.pk]), {}, format="json")

    def record_outcome(self, outcome, **extra):
        return self.client.post(reverse("sales-outcome-create"), {
            "visit_id": self.visit.pk, "recommendation_id": self.recommendation.pk,
            "outcome": outcome, **extra,
        }, format="json")

    def start(self):
        response = self.transition("start")
        self.assertEqual(response.status_code, 200, response.data)

    def test_start_captures_customer_and_commercial_facts(self):
        self.start()
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, Visit.VisitStatus.IN_PROGRESS)
        customer_snapshot = VisitCustomerSnapshot.objects.get(visit=self.visit)
        self.assertEqual(customer_snapshot.customer_id, self.customer.pk)
        self.assertEqual(customer_snapshot.customer_grade_code, "A")
        self.assertEqual(customer_snapshot.total_orders, 3)
        self.assertEqual(customer_snapshot.total_sales_amount, Decimal("300"))
        self.assertEqual(customer_snapshot.segment, "HIGH_VALUE")
        self.assertEqual(customer_snapshot.rfm_score, 12)
        self.assertEqual(customer_snapshot.source_customer360_calculated_at, self.customer360.calculated_at)
        commercial = VisitCommercialSnapshot.objects.get(visit=self.visit)
        self.assertEqual(commercial.customer_id, self.customer.pk)
        self.assertEqual(commercial.salesperson_id, self.salesperson.pk)
        self.assertEqual(commercial.primary_product_code, self.product.product_code)
        self.assertEqual(commercial.recommendation_type, "CROSS_SELL")
        self.assertEqual(commercial.inventory_context["sellable_quantity"], 10)
        self.assertEqual(commercial.commercial_signals, ["IN_STOCK"])
        self.assertFalse(commercial.commercial_blocked)
        self.assertFalse(SalesOutcome.objects.exists())
        self.assertFalse(FollowUpTask.objects.exists())

    def test_snapshot_recapture_returns_existing_facts_unchanged(self):
        self.start()
        customer_before = VisitCustomerSnapshot.objects.get(visit=self.visit).__dict__.copy()
        commercial_before = VisitCommercialSnapshot.objects.get(visit=self.visit).__dict__.copy()
        Customer360.objects.filter(pk=self.customer360.pk).update(total_orders=99)
        Inventory.objects.filter(pk=self.inventory.pk).update(available_quantity=0)
        # Use a fresh Visit, so the assertion cannot pass because of relation caches.
        visit = Visit.objects.get(pk=self.visit.pk)
        customer = capture_visit_customer_snapshot(visit)
        commercial = capture_visit_commercial_snapshot(visit)
        self.assertEqual(
            {key: value for key, value in customer.__dict__.items() if key != "_state"},
            {key: value for key, value in customer_before.items() if key != "_state"},
        )
        self.assertEqual(
            {key: value for key, value in commercial.__dict__.items() if key != "_state"},
            {key: value for key, value in commercial_before.items() if key != "_state"},
        )
        self.assertEqual(VisitCustomerSnapshot.objects.count(), 1)
        self.assertEqual(VisitCommercialSnapshot.objects.count(), 1)

    def test_completion_preserves_snapshots_and_requires_no_outcome(self):
        self.start()
        customer_before = list(VisitCustomerSnapshot.objects.values())
        commercial_before = list(VisitCommercialSnapshot.objects.values())
        response = self.transition("complete")
        self.assertEqual(response.status_code, 200, response.data)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, Visit.VisitStatus.COMPLETED)
        self.assertEqual(list(VisitCustomerSnapshot.objects.values()), customer_before)
        self.assertEqual(list(VisitCommercialSnapshot.objects.values()), commercial_before)
        self.assertFalse(SalesOutcome.objects.exists())

    def test_start_rejects_every_non_planned_status_without_artifacts(self):
        for status in ("IN_PROGRESS", "COMPLETED", "CANCELLED"):
            with self.subTest(status=status):
                Visit.objects.filter(pk=self.visit.pk).update(status=status)
                response = self.transition("start")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["visit_status"], status)
                self.visit.refresh_from_db()
                self.assertEqual(self.visit.status, status)
                self.assertFalse(VisitCustomerSnapshot.objects.exists())
                self.assertFalse(VisitCommercialSnapshot.objects.exists())

    def test_completion_rejects_every_non_in_progress_status(self):
        for status in ("PLANNED", "COMPLETED", "CANCELLED"):
            with self.subTest(status=status):
                Visit.objects.filter(pk=self.visit.pk).update(status=status)
                response = self.transition("complete")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["visit_status"], status)
                self.visit.refresh_from_db()
                self.assertEqual(self.visit.status, status)

    def test_other_salesperson_cannot_start_or_complete_visit(self):
        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.transition("start").status_code, 404)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "PLANNED")
        self.assertFalse(VisitCustomerSnapshot.objects.exists())
        self.assertFalse(VisitCommercialSnapshot.objects.exists())
        Visit.objects.filter(pk=self.visit.pk).update(status="IN_PROGRESS")
        self.assertEqual(self.transition("complete").status_code, 404)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_inactive_salesperson_cannot_start_or_complete_visit(self):
        Salesperson.objects.filter(pk=self.salesperson.pk).update(is_active=False)
        self.client.force_authenticate(user=get_user_model().objects.get(pk=self.user.pk))
        self.assertEqual(self.transition("start").status_code, 403)
        self.assertEqual(self.transition("complete").status_code, 403)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, "PLANNED")
        self.assertFalse(VisitCustomerSnapshot.objects.exists())

    def test_purchase_then_rejection_preserves_events_and_updates_summary(self):
        self.start()
        response = self.record_outcome("PURCHASED", quantity=2, sales_amount="250.00")
        self.assertEqual(response.status_code, 201, response.data)
        first = SalesOutcome.objects.get()
        self.assertEqual(first.quantity, 2)
        self.assertEqual(first.sales_amount, Decimal("250"))
        self.visit.refresh_from_db()
        self.assertTrue(self.visit.order_created)
        self.assertEqual(self.visit.order_amount, Decimal("250"))
        response = self.record_outcome("REJECTED")
        self.assertEqual(response.status_code, 201, response.data)
        first.refresh_from_db()
        self.assertEqual(first.outcome, "PURCHASED")
        self.assertEqual(first.sales_amount, Decimal("250"))
        self.assertEqual(SalesOutcome.objects.count(), 2)
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.order_created)
        self.assertEqual(self.visit.order_amount, Decimal("0"))
        self.assertEqual(self.visit.status, "IN_PROGRESS")

    def test_follow_up_creates_then_updates_one_open_task(self):
        self.start()
        due = self.visit.visit_date + timedelta(days=1)
        response = self.record_outcome("FOLLOW_UP", follow_up_date=due.isoformat(), notes="First")
        self.assertEqual(response.status_code, 201, response.data)
        task = FollowUpTask.objects.get()
        self.assertEqual((task.visit_id, task.customer_id, task.salesperson_id),
                         (self.visit.pk, self.customer.pk, self.salesperson.pk))
        self.assertEqual((task.status, task.due_date, task.notes), ("OPEN", due, "First"))
        self.visit.refresh_from_db()
        self.assertTrue(self.visit.follow_up_required)
        self.assertEqual(self.visit.follow_up_date, due)
        new_due = due + timedelta(days=1)
        response = self.record_outcome("FOLLOW_UP", follow_up_date=new_due.isoformat(), notes="Second")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        task.refresh_from_db()
        self.assertEqual((task.status, task.due_date, task.notes), ("OPEN", new_due, "Second"))
        self.assertEqual(SalesOutcome.objects.count(), 2)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.follow_up_date, new_due)
        self.assertFalse(self.visit.order_created)
        self.assertEqual(self.visit.order_amount, Decimal("0"))

    def test_rejection_after_follow_up_cancels_task_without_deleting_history(self):
        self.start()
        response = self.record_outcome(
            "FOLLOW_UP", follow_up_date=(self.visit.visit_date + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.record_outcome("REJECTED").status_code, 201)
        self.assertEqual(SalesOutcome.objects.count(), 2)
        self.assertEqual(FollowUpTask.objects.get().status, "CANCELLED")
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.follow_up_required)
        self.assertIsNone(self.visit.follow_up_date)

    def test_follow_up_requires_a_valid_date_without_creating_events(self):
        self.start()
        for extra in ({}, {"follow_up_date": "not-a-date"}):
            with self.subTest(extra=extra):
                self.assertEqual(self.record_outcome("FOLLOW_UP", **extra).status_code, 400)
                self.assertFalse(SalesOutcome.objects.exists())
                self.assertFalse(FollowUpTask.objects.exists())
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.follow_up_required)

    def test_outcome_requires_an_in_progress_visit(self):
        for status in ("PLANNED", "COMPLETED", "CANCELLED"):
            with self.subTest(status=status):
                Visit.objects.filter(pk=self.visit.pk).update(status=status)
                self.assertEqual(self.record_outcome("PURCHASED", sales_amount="100").status_code, 403)
                self.assertFalse(SalesOutcome.objects.exists())
                self.visit.refresh_from_db()
                self.assertEqual(self.visit.status, status)
                self.assertFalse(self.visit.order_created)

    def test_other_salesperson_cannot_record_outcome(self):
        self.start()
        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.record_outcome("PURCHASED", sales_amount="100").status_code, 404)
        self.assertFalse(SalesOutcome.objects.exists())
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.order_created)


class ScopedDemoResetTests(TestCase):
    TODAY = date(2026, 8, 28)
    CUSTOMER_CODES = ("C0003", "C0005", "C0013", "C0014", "C0029")

    def setUp(self):
        # Freeze only the command's clock, never use pre-existing demo records.
        clock = patch("apps.visits.management.commands.reset_daily_workspace_demo.timezone.localdate",
                      return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)
        self.salesperson = Salesperson.objects.create(
            employee_code="SP001", first_name="Demo", last_name="Rep",
        )
        other = Salesperson.objects.create(employee_code="SP002", first_name="Other", last_name="Rep")
        grade = CustomerGrade.objects.create(code="A", name="Grade A")
        self.product = Product.objects.create(
            product_code="RESET-PRODUCT", name="Reset product",
            brand=Brand.objects.create(code="RESET", name="Reset brand"),
            category=Category.objects.create(code="RESET", name="Reset category"),
        )
        self.scoped = []
        for code in self.CUSTOMER_CODES:
            customer = Customer.objects.create(customer_code=code, name=code, grade=grade)
            Customer360.objects.create(customer=customer, total_orders=2)
            CustomerAssignment.objects.create(
                customer=customer, salesperson=self.salesperson, start_date=self.TODAY,
            )
            self.scoped.append(self.make_visit(customer, self.salesperson, self.TODAY))
        customer = self.scoped[0].customer
        outside = Customer.objects.create(customer_code="C9999", name="Outside scope")
        self.unrelated = [
            self.make_visit(customer, other, self.TODAY),
            self.make_visit(customer, self.salesperson, self.TODAY - timedelta(days=1)),
            self.make_visit(customer, self.salesperson, self.TODAY + timedelta(days=1)),
            self.make_visit(outside, self.salesperson, self.TODAY),
        ]
        sale = Sale.objects.create(
            customer=customer, invoice_number="RESET-INVOICE", sale_date=self.TODAY,
            total_amount=Decimal("100"),
        )
        SaleItem.objects.create(sale=sale, product=self.product, quantity=1, unit_price=Decimal("100"))

    def make_visit(self, customer, salesperson, visit_date):
        visit = Visit.objects.create(
            customer=customer, salesperson=salesperson, visit_date=visit_date,
            status="IN_PROGRESS", customer_request="Request", customer_feedback="Feedback",
            competitor_information="Competitor", notes="Recorded notes", order_created=True,
            order_amount=Decimal("120"), follow_up_required=True,
            follow_up_date=self.TODAY + timedelta(days=2),
        )
        recommendation, _ = CustomerRecommendation.objects.get_or_create(
            customer=customer, product=self.product,
            defaults={"recommendation_type": "CROSS_SELL", "score": 60, "rank": 1},
        )
        SalesOutcome.objects.create(visit=visit, recommendation=recommendation, outcome="FOLLOW_UP")
        FollowUpTask.objects.create(
            visit=visit, customer=customer, salesperson=salesperson,
            due_date=self.TODAY + timedelta(days=2), notes="Keep outside scope",
        )
        VisitCustomerSnapshot.objects.create(visit=visit, customer=customer, total_orders=2)
        VisitCommercialSnapshot.objects.create(
            visit=visit, customer=customer, salesperson=salesperson,
            primary_product_code=self.product.product_code, inventory_context={"sellable_quantity": 7},
        )
        return visit

    def reset_demo(self):
        output, errors = StringIO(), StringIO()
        call_command("reset_daily_workspace_demo", stdout=output, stderr=errors)
        self.assertEqual(errors.getvalue(), "")
        return output.getvalue()

    def assert_baseline(self):
        for visit in self.scoped:
            with self.subTest(customer=visit.customer_id):
                visit.refresh_from_db()
                self.assertEqual(visit.status, "PLANNED")
                self.assertEqual(visit.customer_request, "")
                self.assertEqual(visit.customer_feedback, "")
                self.assertEqual(visit.competitor_information, "")
                self.assertEqual(visit.notes, "V2 Daily Workspace Demo visit.")
                self.assertFalse(visit.order_created)
                self.assertEqual(visit.order_amount, Decimal("0"))
                self.assertFalse(visit.follow_up_required)
                self.assertIsNone(visit.follow_up_date)
        ids = [visit.pk for visit in self.scoped]
        for model in (SalesOutcome, FollowUpTask, VisitCustomerSnapshot, VisitCommercialSnapshot):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.filter(visit_id__in=ids).exists())

    def test_reset_restores_five_visits_and_preserves_all_out_of_scope_facts(self):
        unrelated_ids = [visit.pk for visit in self.unrelated]
        models = (Visit, SalesOutcome, FollowUpTask, VisitCustomerSnapshot, VisitCommercialSnapshot)
        before = {
            model: list(model.objects.filter(**(
                {"pk__in": unrelated_ids} if model is Visit else {"visit_id__in": unrelated_ids}
            )).order_by("pk").values()) for model in models
        }
        preserved_models = (CustomerGrade, Customer, Customer360, Brand, Category, Product,
                            CustomerRecommendation, Sale, SaleItem, CustomerAssignment, Salesperson)
        preserved = {model: list(model.objects.order_by("pk").values()) for model in preserved_models}
        output = self.reset_demo()
        self.assertIn("Visits reset: 5", output)
        self.assert_baseline()
        self.assertEqual(Visit.objects.count(), 9)
        for model, rows in before.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(list(model.objects.filter(**(
                    {"pk__in": unrelated_ids} if model is Visit else {"visit_id__in": unrelated_ids}
                )).order_by("pk").values()), rows)
        for model, rows in preserved.items():
            with self.subTest(preserved=model.__name__):
                self.assertEqual(list(model.objects.order_by("pk").values()), rows)

    def test_second_reset_is_idempotent(self):
        self.reset_demo()
        self.assert_baseline()
        models = (Visit, SalesOutcome, FollowUpTask, VisitCustomerSnapshot, VisitCommercialSnapshot)
        before = {model: list(model.objects.order_by("pk").values()) for model in models}
        output = self.reset_demo()
        self.assert_baseline()
        self.assertIn("Visits reset: 5", output)
        for label in ("Sales outcomes", "Follow-up tasks", "Customer snapshots", "Commercial snapshots"):
            self.assertIn(label + " deleted: 0", output)
        for model, rows in before.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(list(model.objects.order_by("pk").values()), rows)
