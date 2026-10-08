"""Permanent PostgreSQL READ COMMITTED regression; never uses demo data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from queue import Queue
from threading import Barrier
from time import monotonic, sleep
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.db.models import F
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.customers.models import Customer
from apps.products.models import Brand, Category, Product
from apps.visits.models import Salesperson, Visit
from .models import SalesRequest, SalesRequestLine


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL row-lock/READ COMMITTED behavior")
class RequestRevisionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="revision-owner")
        self.customer = Customer.objects.create(customer_code="REVISION-C", name="مشتری")
        self.rep = Salesperson.objects.create(user=self.owner, employee_code="REVISION-SP", first_name="A", last_name="Rep")
        self.visit = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=date(2026, 10, 8), status="IN_PROGRESS")
        self.request = SalesRequest.objects.create(visit=self.visit)

    def cas(self, expected, joined=False):
        queryset = SalesRequest.objects.filter(pk=self.request.pk, status="DRAFT", revision=expected)
        if joined:
            queryset = queryset.filter(visit__salesperson_id=self.rep.pk, visit__customer_id=self.customer.pk)
        return queryset.update(revision=F("revision") + 1)

    def concurrent_cas(self, joined):
        barrier = Barrier(3)
        pids = Queue()
        request_id, owner_id, customer_id = self.request.pk, self.rep.pk, self.customer.pk
        database = connection.settings_dict["NAME"]

        def worker():
            worker_connection = connections["default"]
            try:
                self.assertEqual(worker_connection.settings_dict["NAME"], database)
                with transaction.atomic():
                    with worker_connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid(), current_setting('transaction_isolation')")
                        pid, isolation = cursor.fetchone()
                    self.assertEqual(isolation, "read committed")
                    pids.put(pid)
                    barrier.wait(timeout=10)
                    queryset = SalesRequest.objects.filter(pk=request_id, status="DRAFT", revision=0)
                    if joined:
                        queryset = queryset.filter(visit__salesperson_id=owner_id, visit__customer_id=customer_id)
                    return queryset.update(revision=F("revision") + 1)
            finally:
                worker_connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                # Test coordination only: force both UPDATE snapshots to precede either commit.
                # The implementation's CAS must work without this lock or any Python mutex.
                SalesRequest.objects.select_for_update().get(pk=request_id)
                futures = [pool.submit(worker) for _ in range(2)]
                barrier.wait(timeout=10)
                worker_pids = [pids.get(timeout=10) for _ in range(2)]
                self.assertEqual(len(set(worker_pids)), 2)
                deadline = monotonic() + 10
                both_blocked = False
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute(
                            "SELECT pid, wait_event_type, query FROM pg_stat_activity "
                            "WHERE pid = ANY(%s) AND datname = current_database()", [worker_pids],
                        )
                        activity = cursor.fetchall()
                    both_blocked = len(activity) == 2 and all(
                        event == "Lock" and query.lstrip().upper().startswith("UPDATE")
                        for pid, event, query in activity
                    )
                    if both_blocked:
                        break
                    sleep(0.01)
                self.assertTrue(both_blocked, "Both actual PostgreSQL UPDATEs must wait before release")
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(results), [0, 1])  # 0 matched rows is the existing revision-conflict signal.
        self.request.refresh_from_db()
        self.assertEqual(self.request.revision, 1)
        self.assertEqual(self.request.status, "DRAFT")

    def test_two_connections_allow_exactly_one_expected_revision_zero_update(self):
        self.concurrent_cas(joined=False)

    def test_joined_ownership_filters_also_allow_only_one_update(self):
        self.concurrent_cas(joined=True)

    def test_pending_revision_update_cannot_modify_a_newly_submitted_row(self):
        product = Product.objects.create(
            product_code="REVISION-P", name="محصول", brand=Brand.objects.create(code="REVISION", name="Brand"),
            category=Category.objects.create(code="REVISION", name="Category"),
        )
        SalesRequestLine.objects.create(
            sales_request=self.request, product=product, quantity=1,
            product_snapshot={"id": product.pk, "code": product.product_code, "name": product.name, "unit": product.unit},
            base_unit_price=Decimal("10"), discount_percentage=Decimal("10"), discount_amount=Decimal("1"),
            final_unit_price=Decimal("9"), line_total=Decimal("9"), currency="TOMAN",
            pricing_source="isolated-fixture", pricing_version="v1",
        )
        pids = Queue()

        def worker():
            try:
                with transaction.atomic():
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        pids.put(cursor.fetchone()[0])
                    return SalesRequest.objects.filter(pk=self.request.pk, status="DRAFT", revision=0).update(revision=F("revision") + 1)
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                SalesRequest.objects.select_for_update().get(pk=self.request.pk)
                future = pool.submit(worker)
                pid = pids.get(timeout=10)
                deadline = monotonic() + 10
                blocked = False
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT wait_event_type, query FROM pg_stat_activity WHERE pid=%s", [pid])
                        activity = cursor.fetchone()
                    blocked = activity and activity[0] == "Lock" and activity[1].lstrip().upper().startswith("UPDATE")
                    if blocked:
                        break
                    sleep(0.01)
                self.assertTrue(blocked, "Revision UPDATE must be waiting before submission")
                self.request.status = "SUBMITTED"
                self.request.number = "REVISION-SUBMITTED"
                self.request.submission_key = uuid4()
                self.request.submission_intent_hash = "a" * 64
                self.request.submitted_at = timezone.now()
                self.request.base_total, self.request.discount_total, self.request.final_total = Decimal("10"), Decimal("1"), Decimal("9")
                self.request.currency = "TOMAN"
                self.request.customer_snapshot = {"id": self.customer.pk, "code": self.customer.customer_code, "name": self.customer.name}
                self.request.salesperson_snapshot = {"id": self.rep.pk, "employee_code": self.rep.employee_code, "name": self.rep.full_name}
                self.request.pricing_snapshot = {"source": "isolated-fixture", "version": "v1"}
                self.request.prepared_message_snapshot = "درخواست آزمایشی"
                self.request.save()
                frozen = SalesRequest.objects.values().get(pk=self.request.pk)
            self.assertEqual(future.result(timeout=15), 0)
        self.assertEqual(SalesRequest.objects.values().get(pk=self.request.pk), frozen)
        self.assertEqual(frozen["revision"], 0)

    def test_target_row_predicates_and_joined_ownership_scope_are_preserved(self):
        self.assertEqual(SalesRequest.objects.filter(pk=self.request.pk, revision=0, visit__salesperson_id=self.rep.pk + 100).update(revision=F("revision") + 1), 0)
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(self.cas(0, joined=True), 1)
        updates = [row["sql"] for row in captured if row["sql"].lstrip().upper().startswith("UPDATE")]
        self.assertEqual(len(updates), 1)
        self.assertIn('"sales_requests_salesrequest"."status" =', updates[0])
        self.assertIn('"sales_requests_salesrequest"."revision" = (SELECT', updates[0])

    def test_successive_and_stale_revisions(self):
        self.assertEqual(self.cas(0), 1)
        self.assertEqual(self.cas(0), 0)
        self.assertEqual(self.cas(1), 1)
        self.assertEqual(self.cas(0), 0)
        self.assertEqual(self.cas(1), 0)
        self.request.refresh_from_db()
        self.assertEqual(self.request.revision, 2)

    def test_closed_visits_still_block_revision_mutations(self):
        for status in ("COMPLETED", "CANCELLED"):
            self.visit.status = status
            self.visit.save(update_fields=["status"])
            with self.subTest(status=status), self.assertRaises(ValidationError):
                self.cas(0)
        self.request.refresh_from_db()
        self.assertEqual(self.request.revision, 0)
