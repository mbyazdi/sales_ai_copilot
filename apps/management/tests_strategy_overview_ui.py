"""M-E3 read-only shell and authoritative API contracts; disposable fixtures only."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from .models import StrategyPolicy
from .strategy_serialization import neutral_config
from .tests_strategy_api import APIFixture, ROOT
from .tests_strategy_evaluator import config, priority


class StrategyOverviewUITests(APIFixture):
    def setUp(self):
        super().setUp()
        self.page = reverse("strategy-overview")

    def test_authorized_shell_rtl_sections_and_read_only_navigation(self):
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.page, "/management/strategy/")
        self.assertEqual(resolve(self.page).url_name, "strategy-overview")
        for value in ('dir="rtl"', 'id="strategyOverview"', 'id="overviewStatus"', 'id="overviewError"',
                      'id="overviewHistory"', 'id="overviewPriorities"', 'id="overviewPromotions"',
                      "پیشنهادهای ذخیره‌شده", "زمینهٔ فروش تازه", "افزایش علّی فروش", "داده ارائه نشده",
                      'href="/management/strategy/comparisons/"', 'name="csrfmiddlewaretoken"'):
            self.assertContains(response, value)
        self.assertIn("no-store", response.headers["Cache-Control"])
        for forbidden in ("command_uuid", "accepted_source_fingerprint", "config_hash", "source_evidence_json", 'type="number"', "درصد افزایش فروش"):
            self.assertNotContains(response, forbidden)

    def test_login_and_strategy_view_required_without_api_bootstrap_on_denial(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.page).status_code, 302)
        user = get_user_model().objects.create_user(username="overview-nonstaff", password=self.password)
        self.client = self.login(user, self.password)
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "دسترسی مجاز نیست", status_code=403)
        self.assertNotContains(response, 'id="strategyOverview"', status_code=403)
        self.assertNotContains(response, "strategy_overview.js", status_code=403)

    def test_current_view_capability_is_rechecked(self):
        with patch("apps.management.strategy_ui_views.require_strategy_viewer", side_effect=PermissionDenied):
            self.assertEqual(self.client.get(self.page).status_code, 403)

    def test_first_use_get_head_never_initialize_policy_or_write_business_data(self):
        before = self.business_digest(), self.counts()
        self.assertFalse(StrategyPolicy.objects.exists())
        with CaptureQueriesContext(connection) as queries:
            for url in (self.page, ROOT+"overview/", ROOT+"versions/", ROOT+"options/"):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.head(url).status_code, 200)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertFalse(StrategyPolicy.objects.exists())
        self.assertEqual((self.business_digest(), self.counts()), before)
        response = self.client.get(ROOT+"overview/").data
        self.assertIsNone(response["active_version_id"])
        self.assertIsNone(response["draft_version_id"])
        self.assertEqual(response["active_config"], neutral_config())
        self.assertEqual(response["comparison_count"], 0)

    def test_page_rejects_post_and_preserves_existing_routes(self):
        before = self.business_digest(), self.counts()
        self.assertEqual(self.client.post(self.page, {}, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 405)
        self.assertEqual((self.business_digest(), self.counts()), before)
        self.assertEqual(resolve("/management/").url_name, "management-dashboard")
        self.assertEqual(resolve("/management/strategy/comparisons/").url_name, "strategy-comparison-create")
        self.assertEqual(resolve("/management/strategy/comparisons/2/").url_name, "strategy-comparison")

    def test_configuration_counts_and_publication_flags_are_authoritative(self):
        desired = config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                         promotion_rules=[{"promotion_id": 1, "points": 5}])
        self.api_draft(config=desired)
        evidence, _, _ = self.api_preview()
        draft = self.client.get(ROOT+"overview/").data
        self.assertEqual(draft["active_config"], neutral_config())
        self.assertIsNotNone(draft["draft_version_id"])
        self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 200)
        before = self.business_digest(), self.counts()
        head = self.client.get(ROOT+"overview/").data
        self.assertEqual(head["active_config"], desired)
        self.assertEqual(head["active_version_id"], evidence["after_version_id"])
        self.assertIsNone(head["draft_version_id"])
        self.assertEqual(head["comparison_count"], 1)
        self.assertEqual(head["version_count"], 1)
        self.assertTrue(head["selling_context_integration"])
        self.assertFalse(head["impact_available"])
        history = self.client.get(ROOT+"versions/?after_id=0&limit=6").data
        self.assertTrue(history["results"][0]["published"])
        self.assertIn("created_at", history["results"][0])
        self.assertNotIn("published_at", history["results"][0])
        self.assertEqual(self.client.get(self.page).status_code, 200)
        self.assertEqual(self.client.get(ROOT+f"comparisons/{evidence['comparison_id']}/").data, evidence)
        self.assertEqual((self.business_digest(), self.counts()), before)

    def test_reference_choices_are_read_only_and_do_not_invent_unavailable_labels(self):
        before = self.business_digest(), self.counts()
        for kind in ("products", "brands", "categories", "promotions"):
            response = self.client.get(ROOT+f"options/?kind={kind}&after_id=0&limit=100")
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(len(response.data["results"]), 100)
            self.assertTrue(all("id" in row for row in response.data["results"]))
        self.assertEqual((self.business_digest(), self.counts()), before)

    def test_history_and_impact_copy_do_not_claim_publication_time_or_measured_revenue(self):
        response = self.client.get(self.page)
        self.assertContains(response, "زمان ایجاد نسخه است، نه زمان انتشار")
        self.assertContains(response, "اندازه‌گیری نشده")
        self.assertContains(response, "سود منتسب به سیاست")
        self.assertContains(response, "در این نما ارزیابی نمی‌شود")
        self.assertNotContains(response, "رشد فروش:")
