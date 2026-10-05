"""Follow-up productization regressions using isolated, non-demo fixtures."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from . import tests_authorization
from .models import CustomerAssignment, FollowUpTask, Salesperson


class FollowUpWorkspaceTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self):
        return self.client.get(reverse("follow-up-dashboard"))

    def task(self, offset, **kwargs):
        return FollowUpTask.objects.create(
            customer=self.customer, visit=self.visits[0], salesperson=self.rep,
            due_date=self.TODAY + timedelta(days=offset), **kwargs,
        )

    def test_owned_open_tasks_only_and_real_summary_counts(self):
        self.task(-1)
        self.task(2)
        self.task(0, status="DONE")
        self.task(-2, status="CANCELLED")
        response = self.page()
        self.assertEqual(response.status_code, 200)
        for key, expected in (("open_count", 3), ("overdue_count", 1),
                              ("today_count", 1), ("upcoming_count", 1)):
            self.assertEqual(response.context[key], expected)
        self.assertContains(response, "<dt>کل پیگیری‌های باز</dt><dd>3</dd>", html=True)
        self.assertNotContains(response, self.other_customer.name)
        self.assertNotContains(response, self.other_customer.customer_code)

    def test_date_boundaries_and_rendered_operational_order(self):
        late = self.task(-1)
        early = self.task(-3)
        tied = self.task(-1)
        future = self.task(1)
        response = self.page()
        self.assertEqual(list(response.context["overdue_tasks"]), [early, late, tied])
        self.assertEqual(list(response.context["today_tasks"]), [self.tasks[0]])
        self.assertEqual(list(response.context["upcoming_tasks"]), [future])
        html = response.content.decode()
        positions = [html.index(f'id="follow-up-task-{task.pk}"')
                     for task in (early, late, tied, self.tasks[0], future)]
        self.assertEqual(positions, sorted(positions))

    def test_global_empty_explains_actual_creation_and_next_step(self):
        FollowUpTask.objects.filter(salesperson=self.rep).update(status="DONE")
        response = self.page()
        self.assertEqual(response.context["open_count"], 0)
        self.assertContains(response, "پیگیری بازی ندارید")
        self.assertContains(response, "نیاز به پیگیری")
        self.assertContains(response, "تاریخ پیگیری")
        self.assertContains(response, reverse("salesperson-dashboard"))
        self.assertNotContains(response, 'class="follow-up-task-card')

    def test_individual_group_empty_states(self):
        response = self.page()
        self.assertContains(response, "هیچ پیگیری عقب‌افتاده‌ای ندارید.")
        self.assertContains(response, "پیگیری بازی برای روزهای آینده ندارید.")
        FollowUpTask.objects.filter(pk=self.tasks[0].pk).update(due_date=self.TODAY - timedelta(days=1))
        self.assertContains(self.page(), "امروز پیگیری سررسیدشده‌ای ندارید.")

    def test_customer_navigation_retains_visit_and_checks_current_access(self):
        path = f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visits[0].pk}"
        self.assertContains(self.page(), path)
        self.assertEqual(self.client.get(path).status_code, 200)
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        # Historical owned task access stays distinct from current customer access.
        self.assertContains(self.page(), path)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_minimal_source_data_shell_and_existing_action_contract(self):
        response = self.page()
        self.assertContains(response, "مشتری و زمینه ویزیت")
        self.assertContains(response, "زمینه ویزیت و جزئیات")
        self.assertContains(response, 'data-status="DONE"')
        self.assertContains(response, 'data-status="CANCELLED"')
        self.assertContains(response, 'data-task-id="%s"' % self.tasks[0].pk)
        self.assertContains(response, "core/js/follow_up_dashboard.js")
        self.assertContains(response, "css/design-system.css")
        self.assertContains(response, "visits/css/follow_up_workspace.css")
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, 'href="%s" aria-current="page"' % reverse("follow-up-dashboard"))
        self.assertContains(response, 'href="#main-content"')

    def test_notes_render_safely_and_remain_real_next_action(self):
        FollowUpTask.objects.filter(pk=self.tasks[0].pk).update(notes="<script>unsafe</script> تماس با مشتری")
        response = self.page()
        self.assertContains(response, "تماس با مشتری")
        self.assertContains(response, "&lt;script&gt;unsafe&lt;/script&gt;")
        self.assertNotContains(response, "<script>unsafe</script>")

    def test_staff_missing_and_inactive_profiles_cannot_impersonate(self):
        for user in (self.staff, self.no_profile):
            self.client.force_login(user)
            self.assertEqual(self.page().status_code, 403)
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        self.client.force_login(self.user)
        self.assertEqual(self.page().status_code, 403)
        self.client.logout()
        self.assertEqual(self.page().status_code, 302)
