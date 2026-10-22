"""M-E1 frozen viewer/projection tests. Writes belong to the disposable runner."""
from copy import deepcopy
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, DatabaseError
from django.test.utils import CaptureQueriesContext
from django.urls import reverse, resolve

from apps.customers.models import Customer
from apps.products.models import Product
from apps.visits.models import Salesperson
from .tests_strategy_api import APIFixture, ROOT
from .tests_strategy_evaluator import DAY
from .strategy_api_reads import frozen_comparison_labels
from .strategy_comparisons import get_strategy_comparison
from .strategy_serialization import neutral_config
from .tests_strategy_evaluator import config, priority


class StrategyComparisonUITests(APIFixture):
    def setUp(self):
        super().setUp()
        self.api_draft(config=config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                                     promotion_rules=[{"promotion_id": 1, "points": 5}]))
        self.evidence, _, _ = self.api_preview()
        self.cid = self.evidence["comparison_id"]
        self.page = reverse("strategy-comparison", args=[self.cid])

    def test_authorized_page_shell_and_unchanged_navigation(self):
        self.assertEqual(resolve(self.page).url_name, "strategy-comparison")
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 200)
        for content in ("پیش از تغییر", "پس از تغییر", "مقایسهٔ اولویت پیشنهادها", "امتیاز موتور", "احتمال خرید", "ثبت‌شده", "comparisonRetry"):
            self.assertContains(response, content)
        self.assertContains(response, f'data-api-url="{ROOT}comparisons/{self.cid}/"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'href="/management/"')
        self.assertIn("no-store", response.headers["Cache-Control"])
        for absent in ("command_uuid", "accepted_comparison_digest", "source_evidence_json", 'type="number"'):
            self.assertNotContains(response, absent)

    def test_page_requires_login_and_strategy_view_capability(self):
        self.client.logout()
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/?next="))
        user = get_user_model().objects.create_user(username="ui-nonstaff", password=self.password)
        self.client = self.login(user, self.password)
        response = self.client.get(self.page)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "دسترسی مجاز نیست", status_code=403)
        self.assertNotContains(response, "data-api-url", status_code=403)

    def test_responsive_tabs_and_native_disclosures_preserve_evidence_surfaces(self):
        response = self.client.get(self.page)
        self.assertContains(response, 'id="comparisonTabs" class="strategy-tabs" role="tablist"')
        for side, label in (("before", "قبل از تغییر"), ("after", "بعد از تغییر")):
            self.assertContains(response, f'id="{side}Tab" type="button" role="tab" aria-controls="{side}Panel"')
            self.assertContains(response, label)
            self.assertContains(response, f'id="{side}Panel" class="strategy-panel')
        self.assertContains(response, '<details id="focusDetails" class="strategy-factor-details" open>')
        self.assertContains(response, '<summary>جزئیات رتبه و عوامل سیاست</summary>')
        self.assertContains(response, '<details id="limitations" class="strategy-limitations strategy-section">')
        self.assertContains(response, '<summary id="limitationsTitle">مبنای خواندن این مقایسه</summary>')
        self.assertContains(response, 'class="strategy-focus-summary" id="focusSummary"')
        for identity in ("focusRanks", "focusFactors", "focusReasons", "focusCommercial"):
            self.assertContains(response, f'id="{identity}"')
        self.assertContains(response, "این مقایسه پیش‌بینی خرید یا اندازه‌گیری افزایش فروش نیست.")

    def test_fresh_viewer_denial_has_accessible_state(self):
        with patch("apps.management.strategy_ui_views.require_strategy_viewer", side_effect=PermissionDenied):
            self.assertEqual(self.client.get(self.page).status_code, 403)

    def test_page_and_frozen_api_get_head_are_zero_write(self):
        before = self.business_digest(), self.counts()
        with CaptureQueriesContext(connection) as queries:
            for path in (self.page, ROOT+f"comparisons/{self.cid}/"):
                self.assertEqual(self.client.get(path).status_code, 200)
                self.assertEqual(self.client.head(path).status_code, 200)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual((self.business_digest(), self.counts()), before)

    def test_page_has_no_mutation_method(self):
        response = self.client.post(self.page, {}, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 405)

    def test_exact_order_score_and_contributions_come_from_frozen_api(self):
        response = self.client.get(ROOT+f"comparisons/{self.cid}/").data
        self.assertEqual(response["outputs"]["before"]["after_ids"], [101, 102, 103, 104])
        self.assertEqual(response["outputs"]["after"]["after_ids"], [103, 101, 102, 104])
        row = response["outputs"]["after"]["rows"][0]
        self.assertEqual([row["source"]["base_score"], row["base_priority"], row["priority"]["points"], row["target"]["points"],
                          row["promotion"]["points"], row["effective_priority"]], ["70.0000", "10.00", "20.00", "2.50", "5.00", "37.50"])
        self.assertTrue(response["outputs"]["simulation_only"])
        self.assertIsNone(response["outputs"]["revenue_uplift"])
        self.assertTrue(row["priority"]["reasons"][0]["text_fa"])

    def test_frozen_labels_survive_current_name_changes_and_no_raw_capture_leaks(self):
        before = self.client.get(ROOT+f"comparisons/{self.cid}/").data
        Customer.objects.filter(pk=self.customer.pk).update(name="CURRENT CUSTOMER")
        Salesperson.objects.filter(pk=self.rep.pk).update(first_name="CURRENT REP")
        Product.objects.filter(pk=3).update(name="CURRENT PRODUCT")
        after = self.client.get(ROOT+f"comparisons/{self.cid}/").data
        self.assertEqual(after, before)
        self.assertNotIn("inputs", after)
        self.assertNotIn("capture", after)
        self.assertEqual(set(after["labels"]), {"customer", "salesperson", "products"})
        for label in [after["labels"]["customer"], after["labels"]["salesperson"], *after["labels"]["products"]]:
            self.assertEqual(set(label), {"id", "code", "name"})

    def test_projection_has_no_queries_missing_labels_remain_missing(self):
        value = get_strategy_comparison(actor=self.manager, comparison_id=self.cid)
        value = deepcopy(value)
        sources = value["inputs"]["capture"]["sources"]
        sources["customer"].pop("name", None)
        sources["salesperson"].pop("first_name", None); sources["salesperson"].pop("last_name", None)
        for row in sources["products"]:
            row.pop("name", None)
        sources["products"].append({"id": 9999, "name": "NOT SHORTLIST", "password": "not-a-real-secret"})
        with CaptureQueriesContext(connection) as queries:
            result = frozen_comparison_labels(value)
        self.assertEqual(len(queries), 0)
        self.assertIsNone(result["customer"]["name"])
        self.assertIsNone(result["salesperson"]["name"])
        self.assertTrue(all(item["name"] is None for item in result["products"]))
        self.assertNotIn(9999, [item["id"] for item in result["products"]])

    def test_history_stays_fixed_after_later_publication(self):
        original = self.client.get(ROOT+f"comparisons/{self.cid}/").data
        self.assertEqual(self.post("publish/", self.publish_body(self.evidence)).status_code, 200)
        self.api_draft(config=neutral_config())
        neutral, _, _ = self.api_preview()
        self.assertEqual(neutral["outputs"]["before"]["after_ids"], [103, 101, 102, 104])
        self.assertEqual(neutral["outputs"]["after"]["after_ids"], [101, 102, 103, 104])
        self.assertEqual(neutral["outputs"]["before"]["rows"][0]["source"]["saved_rank"], 3)
        self.assertEqual(self.post("publish/", self.publish_body(neutral)).status_code, 200)
        self.assertEqual(self.client.get(ROOT+f"comparisons/{self.cid}/").data, original)

    def test_older_evidence_without_label_sources_has_no_live_fallback(self):
        value = deepcopy(get_strategy_comparison(actor=self.manager, comparison_id=self.cid))
        value["inputs"]["capture"].pop("sources")
        with CaptureQueriesContext(connection) as queries:
            labels = frozen_comparison_labels(value)
        self.assertEqual(len(queries), 0)
        self.assertIsNone(labels["customer"]["name"])
        self.assertIsNone(labels["salesperson"]["name"])
        self.assertEqual(labels["products"], [])

    def test_api_errors_remain_redacted_and_stable(self):
        self.assertEqual(self.client.get(ROOT+"comparisons/999999/").status_code, 404)
        for error, expected in ((ValidationError("bad", code="INVALID_STRATEGY_EVIDENCE"), 409), (DatabaseError("private SQL"), 503)):
            with patch("apps.management.strategy_api_views.get_strategy_comparison", side_effect=error):
                response = self.client.get(ROOT+f"comparisons/{self.cid}/")
            self.assertEqual(response.status_code, expected)
            self.assertNotIn("private", str(response.data))

    def test_zero_identifier_has_accessible_not_found_state(self):
        response = self.client.get(reverse("strategy-comparison", args=[0]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "مقایسه پیدا نشد", status_code=404)

    def test_creation_landing_is_authorized_read_only_and_needs_no_comparison_id(self):
        path = reverse("strategy-comparison-create")
        before = self.business_digest(), self.counts()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(path)
            self.assertEqual(self.client.head(path).status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<details class="strategy-create" id="comparisonCreation" open>')
        for field in ("creationSalesperson", "creationCustomer", "creationDate", "creationDraft", "prepareComparison", "recoverComparison"):
            self.assertContains(response, f'id="{field}"')
        self.assertNotContains(response, 'id="beforeRanking"')
        self.assertNotContains(response, 'data-api-url=')
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual((self.business_digest(), self.counts()), before)
        self.assertEqual(self.client.post(path, {}, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_view_only_staff_keep_historical_viewer_without_creation_controls(self):
        with patch("apps.management.strategy_ui_views.can_manage_strategy", return_value=False):
            response = self.client.get(self.page)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="beforeRanking"')
        self.assertContains(response, "ایجاد مقایسه به دسترسی مدیریت راهبرد نیاز دارد")
        self.assertNotContains(response, 'id="strategyCreation"')
        self.assertNotContains(response, "strategy_comparison_create.js")
        # The API capability boundary remains server-side and independent.
        with patch("apps.management.strategy_api_views.can_manage_strategy", return_value=False):
            self.assertEqual(self.post("comparisons/", {}).status_code, 403)

    def test_creation_uses_prepared_context_then_frozen_result_without_source_writes(self):
        before, counts = self.business_digest(), self.counts()
        head = self.head()
        query = dict(customer_id=self.customer.pk, salesperson_id=self.rep.pk, proposed_version_id=head.draft_version_id,
                     expected_revision=head.revision, evaluation_date=DAY.isoformat())
        with CaptureQueriesContext(connection) as queries:
            prepared = self.client.get(ROOT+"options/", query)
        self.assertEqual(prepared.status_code, 200)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        body = {"command_uuid": str(uuid4()), **prepared.data["preview_context"]}
        no_csrf = self.client.post(ROOT+"comparisons/", body, format="json")
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(no_csrf.data["code"], "CSRF_FAILED")
        created = self.post("comparisons/", body)
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(self.post("comparisons/", body).data, created.data)
        recovered = self.client.get(ROOT+f"commands/{body['command_uuid']}/")
        self.assertEqual(recovered.data["result"], created.data["result"])
        detail = self.client.get(ROOT+f"comparisons/{created.data['result']['comparison_id']}/")
        self.assertEqual(detail.data["outputs"], self.evidence["outputs"])
        self.assertEqual(self.client.get(reverse("strategy-comparison", args=[detail.data["comparison_id"]])).status_code, 200)
        self.assertEqual(self.counts(), [counts[0], counts[1], counts[2]+1, counts[3]+1])
        self.assertEqual(self.business_digest(), before)

    def test_published_policy_without_draft_never_initializes_one_on_ui_reads(self):
        self.assertEqual(self.post("publish/", self.publish_body(self.evidence)).status_code, 200)
        before = self.counts(), self.business_digest()
        self.assertEqual(self.client.get(reverse("strategy-comparison-create")).status_code, 200)
        overview = self.client.get(ROOT+"overview/")
        self.assertIsNone(overview.data["draft_version_id"])
        self.assertEqual((self.counts(), self.business_digest()), before)
