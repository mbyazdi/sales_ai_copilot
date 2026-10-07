"""Real Workspace rendering contracts, independent of demo database contents."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.template.loader import render_to_string

from apps.customers.models import Customer, Customer360
from apps.recommendations.models import CustomerRecommendation
from . import tests_authorization
from .models import CustomerAssignment, Salesperson, Visit


class DailyWorkspaceTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        CustomerRecommendation.objects.filter(pk=cls.recommendations[0].pk).update(
            score=90, confidence_score=90,
        )
        cls.medium = Customer.objects.create(customer_code="WORK-M", name="مشتری متوسط")
        cls.normal = Customer.objects.create(customer_code="WORK-N", name="مشتری عادی")
        for customer in (cls.medium, cls.normal):
            Customer360.objects.create(customer=customer)
            CustomerAssignment.objects.create(salesperson=cls.rep, customer=customer,
                                               start_date=cls.TODAY)
            Visit.objects.create(salesperson=cls.rep, customer=customer, visit_date=cls.TODAY)
        CustomerRecommendation.objects.create(customer=cls.medium, product=cls.product,
            recommendation_type="CROSS_SELL", score=60, confidence_score=60, rank=1)
        Visit.objects.create(salesperson=cls.rep, customer=cls.customer,
                             visit_date=cls.TODAY - timedelta(days=1))

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self):
        return self.client.get(reverse("salesperson-dashboard"))

    def test_header_summary_today_and_owned_visits_use_actual_data(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.rep.full_name)
        self.assertContains(response, self.rep.employee_code)
        self.assertContains(response, f'datetime="{self.TODAY.isoformat()}"')
        self.assertEqual(response.context["summary"], {
            "total": 3, "planned": 3, "in_progress": 0, "completed": 0, "cancelled": 0,
        })
        self.assertEqual(len(response.context["visits"]), 3)
        self.assertNotContains(response, self.other_customer.name)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "visits/css/daily_workspace.css?v=002p-final-1")

    def test_real_priority_order_and_counts_are_preserved_with_persian_labels(self):
        response = self.page()
        visits = response.context["visits"]
        self.assertEqual([visit.pre_visit_brief["priority_level"] for visit in visits],
                         ["HIGH", "MEDIUM", "NORMAL"])
        self.assertEqual(response.context["priority_summary"], {"high": 1, "medium": 1, "normal": 1})
        for text in ("اولویت بالا", "اولویت متوسط", "اولویت عادی", "پیگیری باز"):
            self.assertContains(response, text)
        html = response.content.decode()
        self.assertLess(html.index(self.customer.name), html.index(self.medium.name))
        self.assertLess(html.index(self.medium.name), html.index(self.normal.name))
        self.assertNotContains(response, "TODAY'S PRIORITIES")

    def test_state_specific_primary_actions_keep_existing_visit_navigation(self):
        for state, label in (
            ("PLANNED", "آماده‌سازی و شروع ویزیت"), ("IN_PROGRESS", "ادامه و ثبت نتیجه"),
            ("COMPLETED", "مشاهده خلاصه ویزیت"), ("CANCELLED", "مشاهده اطلاعات مشتری"),
        ):
            with self.subTest(state=state):
                Visit.objects.filter(pk=self.visits[0].pk).update(status=state)
                response = self.page()
                visit = next(visit for visit in response.context["visits"] if visit.pk == self.visits[0].pk)
                card = render_to_string("visits/_visit_card.html", {"visit": visit})
                self.assertIn(label, card)
                self.assertIn("نمای ۳۶۰ درجه مشتری", card)
                self.assertIn(f'/customers/?customer_code={self.customer.customer_code}&visit_id={visit.pk}', card)
                self.assertNotIn("<form", card)
                visit.refresh_from_db()
                self.assertEqual(visit.status, state)

    def test_no_recommendation_card_is_safe_and_retains_customer_entry(self):
        response = self.page()
        visit = next(v for v in response.context["visits"] if v.customer_id == self.normal.pk)
        card = render_to_string("visits/_visit_card.html", {"visit": visit})
        self.assertIn("پیشنهاد فعال برای این مشتری موجود نیست", card)
        self.assertIn(f"customer_code={self.normal.customer_code}&visit_id={visit.pk}", card)
        self.assertNotIn(self.product.name, card)

    def test_empty_today_shows_recovery_links_without_fake_visits(self):
        Visit.objects.filter(salesperson=self.rep, visit_date=self.TODAY).update(
            visit_date=self.TODAY - timedelta(days=1),
        )
        response = self.page()
        self.assertContains(response, "برای امروز ویزیتی ثبت نشده است")
        self.assertContains(response, reverse("follow-up-dashboard"))
        self.assertContains(response, 'href="/customers/"')
        self.assertEqual(response.context["summary"]["total"], 0)

    def test_inactive_profile_renders_existing_error_and_anonymous_redirects(self):
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        response = self.page()
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "فروشنده مورد نظر پیدا نشد")
        self.assertNotContains(response, self.customer.name)
        self.client.logout()
        response = self.page()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_targets_remain_real_secondary_content_after_visits(self):
        response = self.page()
        self.assertTrue(response.context["target_progress"])
        self.assertContains(response, "هدف‌های فروش این دوره")
        html = response.content.decode()
        self.assertLess(html.index('id="visits-title"'), html.index("هدف‌های فروش این دوره"))

    def test_operational_card_puts_primary_action_before_collapsed_readiness_without_losing_data(self):
        response = self.page()
        visit = next(v for v in response.context["visits"] if v.pk == self.visits[0].pk)
        card = render_to_string("visits/_visit_card.html", {"visit": visit, "request": response.wsgi_request})
        self.assertLess(card.index('class="workspace-recommendation-cue"'), card.index('class="workspace-visit-actions'))
        self.assertLess(card.index('class="workspace-visit-actions'), card.index('class="workspace-visit-details"'))
        self.assertLess(card.index('class="workspace-visit-details"'), card.index('class="workspace-commercial'))
        self.assertEqual(card.count('class="workspace-visit-actions'), 1)
        self.assertIn('class="ds-button ds-button--quiet"', card)
        self.assertIn("آمادگی و جزئیات ویزیت", card)
        brief = visit.pre_visit_brief
        self.assertIn(brief["primary_recommendation"]["product_name"], card)
        self.assertIn(brief["commercial_decision"]["next_best_action"], card)
        self.assertIn("امتیاز اولویت", card)
        self.assertIn("پیگیری باز", card)
