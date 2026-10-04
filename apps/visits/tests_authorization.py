"""Task 001-B baseline plus Task 001-B.1A approved security regressions.

Unresolved customer-scope gaps remain explicitly characterized.

Fixtures are independent of demo data. Only the external AI response generator
is replaced; authorization, queries and context builders execute normally.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.customers.models import Customer, Customer360
from apps.ai.views import build_base_sales_session
from apps.products.models import Brand, Category, Product
from apps.recommendations.models import CustomerRecommendation
from apps.targets.models import SalesTarget

from .models import CustomerAssignment, FollowUpTask, SalesOutcome, Salesperson, Visit


class AuthorizationBaselineTests(TestCase):
    TODAY = date(2026, 9, 15)

    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.user = users.objects.create_user(username="scope-a")
        cls.other_user = users.objects.create_user(username="scope-b")
        cls.no_profile = users.objects.create_user(username="no-profile")
        cls.staff = users.objects.create_user(username="staff", is_staff=True)
        cls.rep = Salesperson.objects.create(
            user=cls.user, employee_code="AUTH-A", first_name="A", last_name="Rep",
        )
        cls.other_rep = Salesperson.objects.create(
            user=cls.other_user, employee_code="AUTH-B", first_name="B", last_name="Rep",
        )
        cls.customer = Customer.objects.create(customer_code="AUTH-A", name="Customer A")
        cls.other_customer = Customer.objects.create(
            customer_code="AUTH-B", name="Customer B", phone="02112345678",
        )
        cls.product = Product.objects.create(
            product_code="AUTH-P", name="Product",
            brand=Brand.objects.create(code="AUTH", name="Brand"),
            category=Category.objects.create(code="AUTH", name="Category"),
        )
        cls.visits, cls.tasks, cls.targets, cls.recommendations = [], [], [], []
        for rep, customer in ((cls.rep, cls.customer), (cls.other_rep, cls.other_customer)):
            Customer360.objects.create(customer=customer, total_orders=2, total_sales_amount=200)
            CustomerAssignment.objects.create(
                salesperson=rep, customer=customer, start_date=cls.TODAY,
            )
            visit = Visit.objects.create(
                salesperson=rep, customer=customer, visit_date=cls.TODAY,
            )
            cls.visits.append(visit)
            cls.tasks.append(FollowUpTask.objects.create(
                visit=visit, salesperson=rep, customer=customer, due_date=cls.TODAY,
            ))
            cls.targets.append(SalesTarget.objects.create(
                salesperson=rep, period_start=cls.TODAY, period_end=cls.TODAY,
                scope_type="PRODUCT", product=cls.product, target_value=100,
            ))
            recommendation = CustomerRecommendation.objects.create(
                customer=customer, product=cls.product, recommendation_type="CROSS_SELL",
                score=60, rank=1, reason="Scope fixture",
            )
            cls.recommendations.append(recommendation)
        cls.other_outcome = SalesOutcome.objects.create(
            visit=cls.visits[1], recommendation=cls.recommendations[1],
            outcome="REJECTED", notes="Other rep's customer feedback",
        )

    def setUp(self):
        self.client = APIClient()
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_anonymous_business_reads_currently_allow_customer_code_access_gap(self):
        for name in (
            "customer-360-api", "customer-recommendations", "customer-sales-history",
            "customer-sales-outcome-history", "customer-recommendation-performance",
            "recommendation-performance",
        ):
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name, args=[self.other_customer.customer_code]))
                self.assertEqual(response.status_code, 200, response.content)
        response = self.client.get(reverse("customer-360-api", args=[self.other_customer.customer_code]))
        self.assertEqual(response.data["customer"]["phone"], self.other_customer.phone)
        self.assertEqual(response.data["sales_context"]["latest_visit"]["id"], self.visits[1].pk)
        response = self.client.get(reverse("customer-sales-outcome-history", args=[self.other_customer.customer_code]))
        self.assertEqual(response.data["sales_outcomes"][0]["id"], self.other_outcome.pk)
        self.assertEqual(response.data["sales_outcomes"][0]["notes"], self.other_outcome.notes)

    def test_authenticated_rep_can_read_other_assignment_customer_and_recommendations_gap(self):
        self.authenticate()
        self.assertFalse(CustomerAssignment.objects.filter(
            salesperson=self.rep, customer=self.other_customer, is_active=True,
        ).exists())
        for name in ("customer-360-api", "customer-recommendations"):
            response = self.client.get(reverse(name, args=[self.other_customer.customer_code]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["recommendations"][0]["product_code"], self.product.product_code)

    def test_public_customer_page_accepts_other_rep_visit_id_gap(self):
        response = self.client.get("/customers/", {
            "customer_code": self.other_customer.customer_code, "visit_id": self.visits[1].pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_visit"].pk, self.visits[1].pk)
        self.assertEqual(response.context["current_follow_up_task"].pk, self.tasks[1].pk)

    def test_anonymous_protected_apis_reject_requests_without_mutation(self):
        for name, args in (
            ("visit-start", [self.visits[0].pk]), ("visit-complete", [self.visits[0].pk]),
            ("sales-outcome-create", []), ("follow-up-task-status", [self.tasks[0].pk]),
        ):
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.post(reverse(name, args=args), {}, format="json").status_code, 403)
        for name, args in (
            ("visit-commercial-decision", [self.visits[0].pk]), ("follow-up-task-list", []),
            ("targets:my-target-progress", []),
            ("product-commercial-context", [self.customer.customer_code, self.product.product_code]),
        ):
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403)
        self.visits[0].refresh_from_db()
        self.assertEqual(self.visits[0].status, "PLANNED")
        self.tasks[0].refresh_from_db()
        self.assertEqual(self.tasks[0].status, "OPEN")
        self.assertEqual(SalesOutcome.objects.count(), 1)

    def test_workspace_filters_to_logged_in_rep_even_with_other_identifiers(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("salesperson-dashboard"), {
            "salesperson_id": self.other_rep.pk, "customer_code": self.other_customer.customer_code,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([v.pk for v in response.context["visits"]], [self.visits[0].pk])
        self.assertEqual(response.context["salesperson"].pk, self.rep.pk)

    def test_workspace_requires_login_and_returns_empty_for_missing_or_inactive_profile(self):
        self.assertEqual(self.client.get(reverse("salesperson-dashboard")).status_code, 302)
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        for user in (self.no_profile, self.user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("salesperson-dashboard"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["visits"]), [])

    def test_visit_decision_denies_other_owner_but_reveals_existing_id(self):
        self.authenticate()
        self.assertEqual(self.client.get(reverse("visit-commercial-decision", args=[self.visits[0].pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("visit-commercial-decision", args=[self.visits[1].pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("visit-commercial-decision", args=[999999])).status_code, 404)

    def test_cross_owner_visit_start_complete_and_outcome_rejected_without_changes(self):
        self.authenticate()
        visit = self.visits[1]
        self.assertEqual(self.client.post(reverse("visit-start", args=[visit.pk])).status_code, 404)
        Visit.objects.filter(pk=visit.pk).update(status="IN_PROGRESS")
        self.assertEqual(self.client.post(reverse("visit-complete", args=[visit.pk])).status_code, 404)
        response = self.client.post(reverse("sales-outcome-create"), {
            "visit_id": visit.pk, "recommendation_id": self.recommendations[1].pk,
            "outcome": "PURCHASED", "sales_amount": "100",
        }, format="json")
        self.assertEqual(response.status_code, 404)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "IN_PROGRESS")
        self.assertFalse(visit.order_created)
        self.assertEqual(SalesOutcome.objects.count(), 1)

    def test_outcome_rejects_recommendation_id_from_other_customer(self):
        self.authenticate()
        Visit.objects.filter(pk=self.visits[0].pk).update(status="IN_PROGRESS")
        response = self.client.post(reverse("sales-outcome-create"), {
            "visit_id": self.visits[0].pk, "recommendation_id": self.recommendations[1].pk,
            "outcome": "REJECTED",
        }, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(SalesOutcome.objects.count(), 1)

    def test_owned_visit_start_does_not_require_current_customer_assignment(self):
        self.authenticate()
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        response = self.client.post(reverse("visit-start", args=[self.visits[0].pk]))
        self.assertEqual(response.status_code, 200)
        self.visits[0].refresh_from_db()
        self.assertEqual(self.visits[0].status, "IN_PROGRESS")

    def test_follow_up_list_and_direct_status_id_enforce_owner(self):
        self.authenticate()
        response = self.client.get(reverse("follow-up-task-list"), {"salesperson_id": self.other_rep.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([task["id"] for task in response.data["tasks"]], [self.tasks[0].pk])
        response = self.client.post(reverse("follow-up-task-status", args=[self.tasks[1].pk]),
                                    {"status": "DONE"}, format="json")
        self.assertEqual(response.status_code, 404)
        self.tasks[1].refresh_from_db()
        self.assertEqual(self.tasks[1].status, "OPEN")
        self.assertEqual(self.client.post(reverse("follow-up-task-status", args=[self.tasks[0].pk]),
                                         {"status": "DONE"}, format="json").status_code, 200)
        self.tasks[0].refresh_from_db()
        self.assertEqual(self.tasks[0].status, "DONE")

    def test_inactive_profile_cannot_read_or_mutate_own_follow_up(self):
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        self.authenticate(get_user_model().objects.get(pk=self.user.pk))
        task_before = FollowUpTask.objects.filter(pk=self.tasks[0].pk).values().get()
        visit_before = Visit.objects.filter(pk=self.visits[0].pk).values().get()
        self.assertEqual(self.client.get(reverse("follow-up-task-list")).status_code, 403)
        for status in ("DONE", "CANCELLED"):
            with self.subTest(status=status):
                response = self.client.post(reverse("follow-up-task-status", args=[self.tasks[0].pk]),
                                            {"status": status}, format="json")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(FollowUpTask.objects.filter(pk=self.tasks[0].pk).values().get(), task_before)
                self.assertEqual(Visit.objects.filter(pk=self.visits[0].pk).values().get(), visit_before)

    def test_follow_up_dashboard_requires_login_and_active_profile_and_preserves_owner_scope(self):
        url = reverse("follow-up-dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        for user in (self.no_profile, self.user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.other_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([task.pk for task in response.context["today_tasks"]], [self.tasks[1].pk])
        self.assertEqual(response.context["open_count"], 1)

    def test_targets_ignore_other_rep_identifiers_and_return_only_own_target(self):
        self.authenticate()
        response = self.client.get(reverse("targets:my-target-progress"), {
            "salesperson_id": self.other_rep.pk, "employee_code": self.other_rep.employee_code,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([target["id"] for target in response.data["targets"]], [self.targets[0].pk])

    def test_missing_and_inactive_profiles_rejected_by_active_profile_endpoints(self):
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        for user in (self.no_profile, get_user_model().objects.get(pk=self.user.pk)):
            self.authenticate(user)
            for name, args in (("targets:my-target-progress", []),
                               ("visit-commercial-decision", [self.visits[0].pk])):
                with self.subTest(user=user.username, endpoint=name):
                    self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403)
            for name in ("visit-start", "visit-complete"):
                self.assertEqual(self.client.post(reverse(name, args=[self.visits[0].pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse("sales-outcome-create"), {}, format="json").status_code, 403)
        self.authenticate(self.no_profile)
        self.assertEqual(self.client.get(reverse("follow-up-task-list")).status_code, 403)
        self.assertEqual(self.client.post(reverse("follow-up-task-status", args=[self.tasks[0].pk]),
                                         {"status": "DONE"}, format="json").status_code, 403)

    def test_commercial_context_has_authentication_but_no_assignment_check_gap(self):
        self.authenticate(self.no_profile)
        response = self.client.get(reverse("product-commercial-context", args=[
            self.other_customer.customer_code, self.product.product_code,
        ]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["customer"]["customer_code"], self.other_customer.customer_code)

    def test_management_html_and_api_require_staff(self):
        with patch("apps.management.api_views.generate_management_executive_narrative",
                   return_value={"ready": False}) as narrator:
            with patch("apps.management.api_views.build_management_dashboard_contract") as dashboard:
                for user in (None, self.user):
                    with self.subTest(user=user):
                        self.client.force_authenticate(user=user)
                        response = self.client.get(reverse("management_api:dashboard"))
                        self.assertEqual(response.status_code, 403)
                        dashboard.assert_not_called()
                        narrator.assert_not_called()
            self.authenticate(self.staff)
            response = self.client.get(reverse("management_api:dashboard"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("sales_team", response.data)
            self.assertIn(self.other_rep.employee_code, str(response.data["sales_team"]))
            narrator.assert_called_once()
        self.client.force_authenticate(user=None)
        for user in (None, self.user, self.staff):
            if user:
                self.client.force_login(user)
            for name in ("management-dashboard", "recommendation-performance-dashboard"):
                with self.subTest(user=user, page=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200 if user == self.staff else 302)

    def test_diagnostics_and_tuning_enforce_staff_including_direct_mutation_ids(self):
        for user in (None, self.user, self.staff):
            self.client.force_authenticate(user=user)
            for name, args in (
                ("recommendation-diagnostics", []), ("recommendation-diagnostics-summary", []),
                ("recommendation-diagnostics-detail", [self.recommendations[1].pk]),
                ("recommendation-tuning-suggestions", []),
            ):
                with self.subTest(user=user, endpoint=name):
                    self.assertEqual(self.client.get(reverse(name, args=args)).status_code,
                                     200 if user == self.staff else 403)
            for action in ("status", "apply", "rollback"):
                with self.subTest(user=user, action=action):
                    response = self.client.post(reverse("recommendation-tuning-suggestion-" + action,
                                                        args=[999999]), {"status": "APPROVED"}, format="json")
                    self.assertEqual(response.status_code, 404 if user == self.staff else 403)

    def test_ai_rejects_foreign_visit_before_generation(self):
        self.authenticate()
        with patch("apps.ai.views.generate_sales_copilot_response") as generate:
            response = self.client.post(reverse("ai:sales-copilot"), {
                "customer_code": self.other_customer.customer_code,
                "visit_id": self.visits[1].pk, "message": "Explain",
            }, format="json")
            self.assertEqual(response.status_code, 404)
            generate.assert_not_called()

    def test_ai_anonymous_requests_rejected_before_generation(self):
        with patch("apps.ai.views.generate_sales_copilot_response") as generate:
            for extra in ({}, {"visit_id": self.visits[0].pk}):
                with self.subTest(extra=extra):
                    response = self.client.post(reverse("ai:sales-copilot"), {
                        "customer_code": self.customer.customer_code, "message": "Explain", **extra,
                    }, format="json")
                    self.assertEqual(response.status_code, 403)
                    generate.assert_not_called()

    def test_ai_visit_requires_active_profile_without_staff_override(self):
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        with patch("apps.ai.views.generate_sales_copilot_response") as generate:
            for user in (self.no_profile, self.staff, get_user_model().objects.get(pk=self.user.pk)):
                with self.subTest(user=user.username):
                    self.authenticate(user)
                    response = self.client.post(reverse("ai:sales-copilot"), {
                        "customer_code": self.customer.customer_code,
                        "visit_id": self.visits[0].pk, "message": "Explain",
                    }, format="json")
                    self.assertEqual(response.status_code, 403)
                    generate.assert_not_called()

    def test_ai_owner_visit_retains_context_and_response_contract(self):
        self.authenticate()
        with patch("apps.ai.views.generate_sales_copilot_response",
                   return_value={"model": "test-model", "response": "Test response", "done": True}) as generate:
            response = self.client.post(reverse("ai:sales-copilot"), {
                "customer_code": self.customer.customer_code,
                "visit_id": self.visits[0].pk, "message": "Explain",
            }, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {
                "success": True, "customer_code": self.customer.customer_code,
                "visit_id": self.visits[0].pk, "model": "test-model",
                "response": "Test response", "done": True,
            })
            generate.assert_called_once()
            self.assertEqual(generate.call_args.kwargs["user_message"], "Explain")
            context = generate.call_args.kwargs["sales_ai_context"]
            self.assertIn(self.customer.customer_code, str(context))
            self.assertIn(self.rep.employee_code, str(context))

    def test_ai_customer_only_reaches_unassigned_customer_context_gap(self):
        with patch("apps.ai.views.generate_sales_copilot_response") as generate, \
                patch("apps.ai.views.build_base_sales_session", wraps=build_base_sales_session) as session:
            # Authentication is enforced; customer access policy remains deferred.
            # Preserve the existing customer-only builder failure, without masking
            # it with a stub or changing unrelated production behavior.
            for user in (self.user, self.no_profile):
                self.authenticate(user)
                with self.assertRaisesMessage(AttributeError, "'NoneType' object has no attribute 'get'"):
                    self.client.post(reverse("ai:sales-copilot"), {
                        "customer_code": self.other_customer.customer_code,
                        "message": "Explain",
                    }, format="json")
                self.assertEqual(session.call_args.kwargs["customer"].pk, self.other_customer.pk)
                self.assertIsNone(session.call_args.kwargs["commercial_context"])
            self.assertEqual(session.call_count, 2)
            generate.assert_not_called()

    def test_ai_supplied_invalid_visit_ids_rejected_before_generation(self):
        self.authenticate()
        with patch("apps.ai.views.generate_sales_copilot_response") as generate:
            for visit_id in (0, "", "invalid", 999999):
                with self.subTest(visit_id=visit_id):
                    response = self.client.post(reverse("ai:sales-copilot"), {
                        "customer_code": self.customer.customer_code,
                        "visit_id": visit_id, "message": "Explain",
                    }, format="json")
                    self.assertEqual(response.status_code, 404)
                    generate.assert_not_called()

    def test_ai_rejects_visit_from_different_customer_before_generation(self):
        self.authenticate()
        with patch("apps.ai.views.generate_sales_copilot_response") as generate:
            response = self.client.post(reverse("ai:sales-copilot"), {
                "customer_code": self.other_customer.customer_code,
                "visit_id": self.visits[0].pk, "message": "Explain",
            }, format="json")
            self.assertEqual(response.status_code, 404)
            generate.assert_not_called()
