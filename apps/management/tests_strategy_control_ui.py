"""Control Center shell and existing command boundary; disposable databases only."""
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from .tests_strategy_api import APIFixture, ROOT
from .tests_strategy_evaluator import config, priority
from .strategy_serialization import normalize_config


class StrategyControlUITests(APIFixture):
    def setUp(self):
        super().setUp()
        self.page = reverse("strategy-control")

    def test_authorized_shell_scoped_identity_and_sections(self):
        response = self.client.get(self.page)
        self.assertEqual(self.page, "/management/strategy/control/")
        self.assertEqual(resolve(self.page).url_name, "strategy-control")
        for text in ("مرکز تنظیم سیاست‌های فروش", "سیاست فعال", "پیش‌نویس فعلی", "ذخیره پیش‌نویس",
                     "مقایسه پیش‌نویس", "بازنشانی تغییرات", 'id="controlFields" disabled', 'dir="rtl"',
                     'name="csrfmiddlewaretoken"', 'data-can-edit="true"', 'id="controlRecover"', 'id="controlTarget"'):
            self.assertContains(response, text)
        self.assertIn("no-store", response.headers["Cache-Control"])
        for text in ("config_hash", "source_evidence_json", "accepted_comparison_digest", 'id="publish"'):
            self.assertNotContains(response, text)
        self.assertContains(self.client.get(reverse("strategy-overview")), f'href="{self.page}"')

    def test_compact_navigation_preserves_destinations_active_state_and_native_disclosure(self):
        response = self.client.get(self.page)
        self.assertContains(response, '<details id="controlNavigation" class="control-navigation" open>')
        self.assertContains(response, '<summary id="controlNavigationSummary">')
        self.assertContains(response, f'href="{self.page}" aria-current="page"')
        for name in ("strategy-overview", "strategy-comparison-create"):
            self.assertContains(response, f'href="{reverse(name)}"')
        self.assertNotContains(response, 'role="menu"')

    def test_view_only_capability_has_no_save_controls_or_overview_editor_link(self):
        with patch("apps.management.strategy_ui_views.can_manage_strategy", return_value=False):
            response = self.client.get(self.page)
            self.assertContains(response, 'data-can-edit="false"')
            self.assertContains(response, "فقط برای مشاهده")
            self.assertNotContains(response, 'id="controlSave"')
            self.assertNotContains(response, 'id="controlRecover"')
            self.assertNotContains(self.client.get(reverse("strategy-overview")), f'href="{self.page}"')
        with patch("apps.management.strategy_api_views.can_manage_strategy", return_value=False):
            self.assertEqual(self.post("draft/", {"command_uuid": str(uuid4()), "expected_revision": 0, "config": config()}).status_code, 403)

    def test_denied_and_anonymous_shells_do_not_bootstrap_editor(self):
        with patch("apps.management.strategy_ui_views.require_strategy_viewer", side_effect=PermissionDenied):
            response = self.client.get(self.page)
            self.assertContains(response, "دسترسی مجاز نیست", status_code=403)
            self.assertNotContains(response, 'id="strategyControl"', status_code=403)
        self.client.logout()
        self.assertEqual(self.client.get(self.page).status_code, 302)

    def test_get_head_shell_and_loading_calls_are_zero_write_and_post_shell_rejected(self):
        before = self.business_digest(), self.counts()
        with CaptureQueriesContext(connection) as queries:
            for url in (self.page, ROOT+"overview/", ROOT+"versions/?after_id=0&limit=1", ROOT+"options/?kind=products&after_id=0&limit=100"):
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.head(url).status_code, 200)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(self.client.post(self.page, {}, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 405)
        self.assertEqual((self.business_digest(), self.counts()), before)

    def test_draft_replacement_csrf_exact_replay_recovery_and_stale_revision(self):
        before = self.business_digest()
        body = {"command_uuid": str(uuid4()), "expected_revision": 0,
                "config": config(priority_rules=[priority("PRODUCT", 3, 0), priority("BRAND", 11, 20)])}
        self.assertEqual(self.client.post(ROOT+"draft/", body, format="json").status_code, 403)
        first = self.post("draft/", body)
        self.assertEqual(first.status_code, 201, first.data)
        replay = self.post("draft/", body)
        self.assertEqual((replay.status_code, replay.data), (200, first.data))
        self.assertEqual(self.client.get(ROOT+f"commands/{body['command_uuid']}/").data["result"], first.data["result"])
        changed = {**body, "config": config()}
        self.assertEqual(self.post("draft/", changed).data["code"], "COMMAND_INTENT_CONFLICT")
        self.assertEqual(self.post("draft/", {**body, "command_uuid": str(uuid4())}).data["code"], "STALE_POLICY_REVISION")
        _, second = self.api_draft(config=config(target_weight=5))
        head = self.client.get(ROOT+"overview/").data
        self.assertIsNone(head["active_version_id"])
        self.assertEqual(head["draft_version_id"], second.data["result"]["version_id"])
        version_id = first.data["result"]["version_id"]
        history = self.client.get(ROOT+f"versions/?after_id={version_id-1}&limit=1").data
        self.assertEqual(history["results"][0]["config"], normalize_config(body["config"]))
        self.assertEqual(self.business_digest(), before)

    def test_saved_draft_does_not_replace_published_policy_or_frozen_comparison(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 200)
        active = self.head().active_version_id
        before = self.business_digest()
        self.api_draft(config=config(target_weight=5))
        self.assertEqual(self.head().active_version_id, active)
        self.assertEqual(self.client.get(ROOT+f"comparisons/{evidence['comparison_id']}/").data, evidence)
        self.assertEqual(self.business_digest(), before)
