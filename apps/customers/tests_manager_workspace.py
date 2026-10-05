"""Manager customer inspection and existing customer-access regressions."""

from datetime import timedelta
from unittest.mock import patch
from urllib.parse import quote

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.visits import tests_authorization
from apps.visits.models import CustomerAssignment, FollowUpTask, SalesOutcome, Visit
from .models import Customer, CustomerGrade


class ManagerCustomerWorkspaceTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.customer.name = "فروشگاه نمونه"
        cls.customer.grade = CustomerGrade.objects.create(code="A", name="راهبردی")
        cls.customer.save(update_fields=["name", "grade"])
        snapshot = cls.customer.customer_360
        snapshot.segment = "STABLE"
        snapshot.last_purchase_date = cls.TODAY - timedelta(days=3)
        snapshot.save(update_fields=["segment", "last_purchase_date"])
        cls.unassigned = Customer.objects.create(
            customer_code="UNASSIGNED", name="مشتری بدون تخصیص",
        )
        cls.inactive = Customer.objects.create(
            customer_code="INACTIVE", name="مشتری غیرفعال محرمانه", is_active=False,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.staff)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self, prefix="/customers/", **query):
        return self.client.get(prefix, query)

    def test_staff_list_uses_company_active_scope_and_real_context(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customers/manager_workspace.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertEqual(response.context["page_obj"].paginator.count, 3)
        self.assertEqual(
            {customer.pk for customer in response.context["page_obj"]},
            {self.customer.pk, self.other_customer.pk, self.unassigned.pk},
        )
        for value in (
            self.customer.name, self.other_customer.name, self.unassigned.name,
            self.rep.full_name, self.rep.employee_code, "رتبه", "پایدار",
            "2026/09/12", "1 پیگیری باز", "تخصیص فعال ثبت نشده است",
            "تاریخ خرید ثبت نشده است", "همه مشتریان فعال شرکت",
        ):
            self.assertContains(response, value)
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, "management/css/customers.css")
        self.assertContains(response, '<th scope="col" role="columnheader">رتبه</th>', html=True)
        self.assertContains(response, '<th scope="col" role="columnheader">گروه مشتری</th>', html=True)
        self.assertContains(response, 'data-label="رتبه"')
        self.assertContains(response, 'data-label="گروه مشتری"')
        self.assertContains(response, 'class="manager-customer-row"', count=3)
        self.assertNotContains(response, "رتبه و گروه مشتری")
        self.assertContains(response, "/customers/?customer_code=AUTH-A")
        self.assertNotContains(response, self.inactive.name)
        self.assertNotContains(response, "مشتریان تیم")
        self.assertNotContains(response, 'name="customer_code"')

    def test_manager_search_by_code_and_name_on_both_routes(self):
        for prefix in ("/customers/", "/api/customers/"):
            for query in (" auth-a ", "فروشگاه"):
                with self.subTest(prefix=prefix, query=query):
                    response = self.page(prefix, q=query)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["query"], query.strip())
                    self.assertEqual(response.context["page_obj"].paginator.count, 1)
                    self.assertContains(response, 'href="/customers/">پاک کردن جستجو</a>')
                    self.assertContains(response, self.customer.name)
                    self.assertNotContains(response, self.other_customer.name)
                    self.assertNotContains(response, self.unassigned.name)

    def test_pagination_preserves_search_and_customer_order(self):
        Customer.objects.bulk_create([
            Customer(customer_code=f"PAGE-{index:02}", name=f"نمایش {index:02}")
            for index in range(21)
        ])
        query = "نمایش"
        first = self.page(q=query)
        self.assertEqual(first.context["page_obj"].paginator.count, 21)
        self.assertEqual(len(first.context["page_obj"]), 20)
        self.assertContains(first, 'class="manager-customer-row"', count=20)
        self.assertContains(first, f'?q={quote(query)}&amp;page=2')
        second = self.page(q=query, page=2)
        self.assertEqual(
            [customer.customer_code for customer in second.context["page_obj"]],
            ["PAGE-20"],
        )
        self.assertContains(second, "صفحه قبل")
        self.assertNotContains(second, "صفحه بعد")
        self.assertNotContains(second, self.other_customer.name)

    def test_no_result_and_empty_states_do_not_fabricate_customers(self):
        for query in ("INACTIVE", "DOES-NOT-EXIST"):
            response = self.page(q=query)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
            self.assertContains(response, "مشتری مطابق جستجو")
            self.assertContains(response, "پاک کردن جستجو")
            self.assertNotContains(response, 'class="manager-customer-row"')
            self.assertNotContains(response, self.inactive.name)
        Customer.objects.all().update(is_active=False)
        response = self.page()
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "مشتری فعالی برای نمایش وجود ندارد")
        self.assertNotContains(response, "بررسی مشتری")

    def test_list_requires_existing_role_and_never_exposes_rep_search_results(self):
        self.client.logout()
        self.assertEqual(self.page(q=self.other_customer.customer_code).status_code, 403)
        self.client.force_login(self.no_profile)
        self.assertEqual(self.page().status_code, 403)
        self.client.force_login(self.user)
        response = self.page(q=self.other_customer.customer_code)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.other_customer.name)
        self.assertNotContains(response, self.other_customer.customer_code)
        self.assertIsNone(response.context.get("page_obj"))
        self.rep.is_active = False
        self.rep.save(update_fields=["is_active"])
        self.assertEqual(self.page().status_code, 403)

    def test_manager_direct_customer360_ignores_visit_and_hides_operations(self):
        for prefix in ("/customers/", "/api/customers/"):
            response = self.page(
                prefix, customer_code=self.other_customer.customer_code,
                visit_id=self.visits[1].pk, salesperson_id=self.other_rep.pk,
            )
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "core/customer_360.html")
            self.assertTrue(response.context["manager_inspection"])
            self.assertIsNone(response.context["current_visit"])
            self.assertContains(response, "بررسی مدیریتی مشتری")
            self.assertContains(response, "گروه مشتری:")
            self.assertContains(response, "بررسی پیشنهادها")
            self.assertContains(response, "visitId: null")
            self.assertContains(response, 'id="salesCopilotSubmit"')
            for control in (
                "برنامه ویزیت امروز", "مشتریان تیم", 'id="startVisitButton"',
                'id="completeVisitButton"', 'id="outcomeModal"', "outcome-btn",
                'name="visit_id"', "آماده‌سازی پیگیری با Copilot",
            ):
                self.assertNotContains(response, control)
        for prefix in ("/customers/v1/customer-360/", "/api/customers/v1/customer-360/"):
            response = self.client.get(f"{prefix}{self.other_customer.customer_code}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["customer"]["code"], self.other_customer.customer_code)

    def test_unavailable_html_and_api_do_not_disclose_existence(self):
        self.client.force_login(self.user)
        for prefix in ("/customers/", "/api/customers/"):
            denied = self.page(prefix, customer_code=self.other_customer.customer_code)
            missing = self.page(prefix, customer_code="DOES-NOT-EXIST")
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(denied.content, missing.content)
            self.assertNotContains(denied, self.other_customer.name, status_code=404)
            self.assertNotContains(denied, self.other_customer.customer_code, status_code=404)
        for prefix in ("/customers/v1/customer-360/", "/api/customers/v1/customer-360/"):
            denied = self.client.get(f"{prefix}{self.other_customer.customer_code}/")
            missing = self.client.get(f"{prefix}DOES-NOT-EXIST/")
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(denied.data, missing.data)
        self.client.force_login(self.staff)
        for code in (self.inactive.customer_code, "DOES-NOT-EXIST"):
            self.assertEqual(self.page(customer_code=code).status_code, 404)
            response = self.client.get(reverse("customer-360-api", args=[code]))
            self.assertEqual(response.status_code, 404)

    def test_salesperson_assignment_boundary_and_operational_ui_are_preserved(self):
        self.client.force_login(self.user)
        allowed = self.page(customer_code=self.customer.customer_code, visit_id=self.visits[0].pk)
        self.assertEqual(allowed.status_code, 200)
        self.assertFalse(allowed.context["manager_inspection"])
        self.assertEqual(allowed.context["current_visit"].pk, self.visits[0].pk)
        self.assertContains(allowed, "برنامه ویزیت امروز")
        self.assertContains(allowed, 'id="outcomeModal"')
        self.assertContains(allowed, 'id="startVisitButton"')
        for customer, status in ((self.customer, 200), (self.other_customer, 404)):
            self.assertEqual(self.client.get(
                reverse("customer-360-api", args=[customer.customer_code]),
            ).status_code, status)
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        self.assertEqual(self.page(customer_code=self.customer.customer_code).status_code, 404)

    def test_manager_gets_do_not_write_business_data_or_invoke_llm(self):
        with patch("apps.ai.services.OllamaClient") as provider:
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.page().status_code, 200)
                self.assertEqual(self.page(q=self.customer.customer_code).status_code, 200)
                self.assertEqual(self.page(
                    customer_code=self.customer.customer_code, visit_id=self.visits[0].pk,
                ).status_code, 200)
                self.assertEqual(self.client.get(reverse(
                    "customer-360-api", args=[self.customer.customer_code],
                )).status_code, 200)
            provider.assert_not_called()
        writes = [query["sql"] for query in queries
                  if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        self.assertEqual(writes, [])
        self.visits[0].refresh_from_db()
        self.tasks[0].refresh_from_db()
        self.assertEqual(self.visits[0].status, "PLANNED")
        self.assertEqual(self.tasks[0].status, FollowUpTask.Status.OPEN)
        self.assertEqual(SalesOutcome.objects.count(), 1)

    def test_customer360_service_preserves_supplied_scope_and_trusted_default(self):
        from .access import customer_access_queryset
        from .services import get_customer_360

        scope = customer_access_queryset(self.user)
        self.assertEqual(get_customer_360(
            self.customer.customer_code, queryset=scope,
        )["customer"].pk, self.customer.pk)
        with self.assertRaises(Customer.DoesNotExist):
            get_customer_360(self.other_customer.customer_code, queryset=scope)
        self.assertEqual(get_customer_360(
            self.other_customer.customer_code,
        )["customer"].pk, self.other_customer.pk)

    def test_staff_without_profile_cannot_mutate_or_impersonate_salesperson(self):
        with CaptureQueriesContext(connection) as queries:
            for name, args, payload in (
                ("visit-start", [self.visits[0].pk], {}),
                ("visit-complete", [self.visits[0].pk], {}),
                ("sales-outcome-create", [], {
                    "visit_id": self.visits[0].pk, "recommendation_id": self.recommendations[0].pk,
                    "outcome": "PURCHASED", "salesperson_id": self.rep.pk,
                }),
                ("follow-up-task-status", [self.tasks[0].pk], {"status": "DONE"}),
            ):
                response = self.client.post(
                    reverse(name, args=args), {**payload, "salesperson_id": self.rep.pk},
                    format="json",
                )
                self.assertEqual(response.status_code, 403)
        self.assertFalse(any(query["sql"].lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE")) for query in queries))
        self.assertEqual(Visit.objects.get(pk=self.visits[0].pk).status, "PLANNED")

    def test_dual_role_inspects_as_staff_but_retains_own_operational_authority(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)
        inspection = self.page(
            customer_code=self.other_customer.customer_code, visit_id=self.visits[1].pk,
        )
        self.assertEqual(inspection.status_code, 200)
        self.assertIsNone(inspection.context["current_visit"])
        self.assertNotContains(inspection, "برنامه ویزیت امروز")
        self.assertNotContains(inspection, 'id="outcomeModal"')
        self.assertEqual(self.client.post(
            reverse("visit-start", args=[self.visits[1].pk]),
        ).status_code, 404)
        self.assertEqual(self.client.post(
            reverse("visit-start", args=[self.visits[0].pk]),
        ).status_code, 200)
        self.assertEqual(self.client.post(
            reverse("follow-up-task-status", args=[self.tasks[1].pk]),
            {"status": "DONE"}, format="json",
        ).status_code, 404)
        self.assertEqual(self.client.post(
            reverse("follow-up-task-status", args=[self.tasks[0].pk]),
            {"status": "DONE"}, format="json",
        ).status_code, 200)
