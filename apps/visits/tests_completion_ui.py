"""Finish page and journey entries; GETs must preserve every business record."""
from django.test import TestCase
from django.urls import reverse

from apps.products import tests_catalog
from apps.sales_requests.models import SalesRequest
from apps.sales_requests.tests_submission import SubmissionFixtures
from .completion import complete_visit
from .models import CustomerAssignment, Visit
from uuid import uuid4


class VisitFinishUITests(SubmissionFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.prepare()
        self.client.force_login(self.user)

    def url(self):
        return reverse("visit-finish", args=[self.customer.customer_code, self.visit.pk])

    def test_no_request_page_exposes_explicit_confirmation_and_no_get_writes(self):
        before = self.rows()
        response = self.client.get(self.url(), {"return_url": "https://evil.example/"})
        self.assertEqual(response.status_code, 200)
        for item in ('lang="fa" dir="rtl"', 'data-visit-finish', 'id="finishDialog"',
                     'aria-describedby="finishDescription"', 'name="csrfmiddlewaretoken"',
                     'id="finishPrepare"', 'id="finishConfirm"', 'id="finishCancel"',
                     'id="finishRecover"', 'id="finishRetry"', 'visits/js/visit_finish.js',
                     'visits/css/visit_finish.css', 'ویزیت را بدون درخواست فروش پایان دهید'):
            self.assertContains(response, item)
        self.assertContains(response, reverse("visit-completion-v1", args=[self.visit.pk]))
        self.assertNotContains(response, "evil.example")
        self.assertNotContains(response, '/complete/"')
        self.assertIsNone(response.context["initial_state"]["request"])
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(self.client.head(self.url()).status_code, 200)
        self.assertEqual(self.client.post(self.url(), {}).status_code, 405)
        self.assertEqual(self.rows(), before)

    def test_draft_warning_does_not_submit_delete_or_change_draft(self):
        self.add(); before = self.rows()
        response = self.client.get(self.url())
        self.assertContains(response, "پیش‌نویس ثبت نمی‌شود و حذف نخواهد شد.")
        self.assertContains(response, 'id="finishDraftWarning" class="vf-warning" >')
        self.assertEqual(response.context["initial_state"]["request"]["status"], "DRAFT")
        self.assertEqual(self.rows(), before)

    def test_submitted_result_links_to_finish_without_finishing_on_get(self):
        self.add(); self.submit(); before = self.rows()
        response = self.client.get(reverse("sales-request-result", args=[self.customer.customer_code, self.visit.pk]))
        self.assertContains(response, 'href="' + self.url() + '">پایان ویزیت</a>')
        finish = self.client.get(self.url())
        self.assertEqual(finish.context["initial_state"]["request"]["status"], "SUBMITTED")
        self.assertContains(finish, SalesRequest.objects.get().number)
        self.assertEqual(self.rows(), before)

    def test_completed_page_is_read_only_with_canonical_result_and_daily_return(self):
        self.add(); self.submit()
        body, _, _ = complete_visit(self.user, self.visit.pk,
                                   {"customer_code": self.customer.customer_code, "command_uuid": uuid4()})
        before = self.rows()
        response = self.client.get(self.url())
        self.assertFalse(response.context["initial_state"]["can_complete"])
        self.assertEqual(response.context["initial_state"]["recorded_result"], body)
        self.assertContains(response, "ویزیت تکمیل شد")
        self.assertContains(response, reverse("salesperson-dashboard"))
        self.assertContains(response, 'id="finishReady" class="sr-card vf-stack" hidden')
        result = self.client.get(reverse("sales-request-result", args=[self.customer.customer_code, self.visit.pk]))
        self.assertNotContains(result, 'href="' + self.url() + '">پایان ویزیت</a>')
        self.assertEqual(self.rows(), before)

    def test_planned_cancelled_and_legacy_completed_remain_read_only(self):
        for status in ("PLANNED", "CANCELLED", "COMPLETED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=status)
            before = self.rows()
            response = self.client.get(self.url())
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["initial_state"]["can_complete"])
            self.assertIsNone(response.context["initial_state"]["recorded_result"])
            self.assertEqual(self.rows(), before)

    def test_anonymous_foreign_manager_and_revoked_assignment_are_denied(self):
        for user, status in ((self.foreign_user, 404), (self.staff, 403), (self.no_profile, 403)):
            self.client.force_login(user)
            before = self.rows()
            self.assertEqual(self.client.get(self.url()).status_code, status)
            self.assertEqual(self.rows(), before)
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.user)
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        before = self.rows()
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.rows(), before)

    def test_customer360_entry_is_current_salesperson_only(self):
        query = {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk}
        response = self.client.get("/customers/", query)
        self.assertContains(response, 'href="' + self.url() + '">پایان ویزیت</a>')
        for status in ("PLANNED", "COMPLETED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=status)
            self.assertNotContains(self.client.get("/customers/", query), 'href="' + self.url() + '"')
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get("/customers/", query), 'href="' + self.url() + '"')
