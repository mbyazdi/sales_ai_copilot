"""Presentation contracts across hosts; fixtures never use the demo database."""
from html.parser import HTMLParser
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.visits import tests_authorization
from apps.visits.models import Visit


class Elements(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.items = []
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


class SalespersonJourneyPresentationTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.visit = cls.visits[0]

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=tests_authorization.AuthorizationBaselineTests.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def guided(self):
        return self.client.get(reverse("recommendation-presentation", args=[self.customer.customer_code]), {"visit_id": self.visit.pk})

    def customer_page(self):
        return self.client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": self.visit.pk})

    def test_customer_controls_keep_ids_destinations_and_lifecycle_classes(self):
        planned = self.customer_page()
        controls = {a.get("id"): a for _, a in Elements(planned).items if a.get("id")}
        self.assertEqual(controls["startVisitButton"]["data-visit-id"], str(self.visit.pk))
        self.assertIn("visit-start-btn", controls["startVisitButton"]["class"])
        Visit.objects.filter(pk=self.visit.pk).update(status="IN_PROGRESS")
        active = self.customer_page()
        controls = {a.get("id"): a for _, a in Elements(active).items if a.get("id")}
        self.assertIn("visit-complete-btn", controls["completeVisitButton"]["class"])
        links = [a for tag, a in Elements(active).items if tag == "a" and "c360-guided-link" in a.get("class", "")]
        self.assertEqual(links[0]["href"], reverse("recommendation-presentation", args=[self.customer.customer_code]) + f"?visit_id={self.visit.pk}")
        self.assertContains(active, 'id="salesCopilotSubmit" class="ds-button ds-button--secondary"')

    def test_active_entry_precedes_intelligence_with_one_unchanged_guided_target(self):
        Visit.objects.filter(pk=self.visit.pk).update(status="IN_PROGRESS")
        response = self.customer_page()
        html = response.content.decode()
        links = [a for tag, a in Elements(response).items if tag == "a" and "c360-guided-link" in a.get("class", "")]
        self.assertEqual(len(links), 1)
        self.assertLess(html.index('id="currentVisitStatus"'), html.index('class="ds-button c360-guided-link"'))
        self.assertLess(html.index('class="c360-entry-cue"'), html.index('class="ds-button c360-guided-link"'))
        self.assertLess(html.index('class="ds-button c360-guided-link"'), html.index('id="completeVisitButton"'))
        self.assertEqual(html.count('id="completeVisitButton"'), 1)
        self.assertEqual(html.count('class="visit-workflow-actions'), 1)
        self.assertLess(html.index('class="ds-button c360-guided-link"'), html.index('class="search-bar ds-search"'))
        self.assertLess(html.index('class="ds-button c360-guided-link"'), html.index('id="workspace-decision"'))
        for section in ("workspace-copilot", "workspace-recommendations", "workspace-kpis", "workspace-details", "completeVisitButton"):
            self.assertContains(response, f'id="{section}"')
        self.assertContains(response, 'class="ds-surface c360-customer-background"')
        self.assertContains(response, f'name="visit_id" value="{self.visit.pk}"')

    def test_non_active_and_invalid_visit_keep_the_existing_entry_order(self):
        for status in ("PLANNED", "COMPLETED", "CANCELLED"):
            with self.subTest(status=status):
                Visit.objects.filter(pk=self.visit.pk).update(status=status)
                response = self.customer_page()
                html = response.content.decode()
                self.assertNotContains(response, 'class="ds-surface c360-customer-background"')
                self.assertLess(html.index('class="search-bar ds-search"'), html.index('class="ds-button c360-guided-link"'))
                self.assertLess(html.index('id="workspace-decision"'), html.index('class="ds-button c360-guided-link"'))
        response = self.client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": self.visits[1].pk})
        self.assertNotContains(response, 'class="ds-surface c360-customer-background"')
        self.assertIsNone(response.context["current_visit"])

    def test_customer_legacy_outcome_contract_remains_and_catalog_has_no_mutations(self):
        customer, guided = self.customer_page(), self.guided()
        self.assertEqual(customer.status_code, 200)
        self.assertContains(customer, "core/css/recommendation_outcome.css?v=002p-1")
        ids = {a["id"]: (tag, a) for tag, a in Elements(customer).items if a.get("id", "").startswith("outcome")}
        self.assertIn("hidden", ids["outcomeModal"][1])
        for name in ("outcomeForm", "outcomeModal", "outcomeQuantity", "outcomeSalesAmount", "outcomeFollowUpDate", "outcomeNotes", "outcomeSubmit"):
            self.assertIn(name, ids)
        self.assertContains(customer, "csrfmiddlewaretoken")
        self.assertEqual(guided.status_code, 200)
        self.assertNotContains(guided, 'id="outcomeModal"')
        self.assertNotContains(guided, "core/js/recommendation_outcome.js")
        self.assertContains(guided, "core/js/guided_catalog.js")

    def test_guided_and_review_share_identity_without_duplicate_navigation(self):
        guided = self.guided()
        review = self.client.get(reverse("visit-completion-review", args=[self.customer.customer_code, self.visit.pk]))
        for response in (guided, review):
            self.assertTemplateUsed(response, "components/salesperson_context.html")
            self.assertContains(response, 'class="sj-context"', count=1)
            self.assertContains(response, self.rep.employee_code)
            self.assertContains(response, "css/salesperson_journey.css?v=002p-1")
        links = [a for tag, a in Elements(review).items if tag == "a" and a.get("href") == reverse("salesperson-dashboard")]
        self.assertEqual(len(links), 2)  # Context link plus initially hidden completed acknowledgement.

    def test_brief_return_copy_is_truthful_and_target_is_unchanged(self):
        guided = self.guided()
        response = self.client.get(guided.context["brief_url"])
        self.assertContains(response, "بازگشت</a>", count=2)
        self.assertNotContains(response, "بازگشت به نمای مشتری")
        self.assertContains(response, response.context["return_url"].replace("&", "&amp;"), count=2)
        self.assertIn("/recommendations/presentation/", response.context["return_url"])
        self.assertContains(response, f"ویزیت <bdi>{self.visit.pk}</bdi>")

    def test_manager_default_shell_does_not_opt_into_salesperson_chrome(self):
        self.client.force_login(self.staff)
        response = self.customer_page()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "css/salesperson_journey.css")
        self.assertNotContains(response, 'class="product-shell sj-shell"')
        self.assertNotContains(response, 'id="completeVisitButton"')

    def test_persisted_status_text_is_preserved_across_guided_review_and_brief(self):
        for status, text in (("PLANNED", "برنامه‌ریزی‌شده"), ("IN_PROGRESS", "در حال انجام"), ("COMPLETED", "تکمیل‌شده"), ("CANCELLED", "لغوشده")):
            with self.subTest(status=status):
                Visit.objects.filter(pk=self.visit.pk).update(status=status)
                guided = self.guided()
                review = self.client.get(reverse("visit-completion-review", args=[self.customer.customer_code, self.visit.pk]))
                brief = self.client.get(guided.context["brief_url"])
                for response in (guided, review, brief):
                    self.assertContains(response, text)
                if status == "COMPLETED":
                    self.assertContains(review, 'id="completionAcknowledgement"')
