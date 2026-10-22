"""Fresh-context integration; no fixtures/writes outside disposable databases."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import connection, connections, models, transaction
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.customers.models import Customer360
from apps.customers.selling_context import customer_selling_priority
from apps.products.catalog import build_catalog
from apps.products.catalog_access import catalog_access
from apps.inventory.models import Inventory
from apps.products.models import ProductDemoPrice
from apps.recommendations.catalog_context import CONTEXT_SALT, CatalogContextUnavailable, saved_priority
from apps.recommendations.feedback import record_feedback
from apps.recommendations.models import CustomerRecommendation, RecommendationFeedbackEvent
from apps.sales_requests.basket import basket_quote, mutate_basket
from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
from apps.visits.models import CustomerAssignment, Visit
from . import strategy_snapshots as adapter
from . import tests_strategy_services as fixtures
from .models import StrategyPolicy, StrategyPolicyVersion
from .strategy_serialization import neutral_config
from .tests_strategy_evaluator import DAY, config, priority


class SellingFixture(fixtures.ServiceFixture):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="strategy-rep")
        self.rep.user = self.user
        self.rep.save()
        self.visit = Visit.objects.create(customer=self.customer, salesperson=self.rep, visit_date=DAY, status="IN_PROGRESS")
        Customer360.objects.create(customer=self.customer)
        self.access = catalog_access(self.user, self.customer.customer_code, self.visit.pk)
        self.addCleanup(patch.stopall)
        patch("apps.management.selling_strategy.timezone.localdate", return_value=DAY).start()

    def activate(self, rules=None):
        self.draft(rules if rules is not None else config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                                                        promotion_rules=[{"promotion_id": 1, "points": 5}]))
        return self.publish().event.version_id

    def fresh(self):
        return saved_priority(self.access)

    def add_product(self, token, product_id=3, **overrides):
        quote = basket_quote(self.user, self.customer.customer_code, self.visit.pk, product_id, 1)
        command = {"customer_code": self.customer.customer_code, "catalog_context": token, "product_id": product_id,
                   "quantity": 1, "expected_request_revision": quote["expected_request_revision"],
                   "accepted_quote_fingerprint": quote["quote_fingerprint"], "command_uuid": uuid4(), **overrides}
        return command, mutate_basket(self.user, self.visit.pk, "ADD_PRODUCT", command)


class SellingStrategyTests(SellingFixture):
    def test_absent_policy_is_legacy_order_and_does_not_initialize_head(self):
        before = self.business_digest()
        result = self.fresh()
        self.assertEqual([row.pk for row in result.recommendations], [101, 102, 103, 104])
        self.assertIsNone(result.strategy)
        self.assertNotIn("strategy", signing.loads(result.token, salt=CONTEXT_SALT))
        self.assertFalse(StrategyPolicy.objects.exists())
        self.assertEqual(before, self.business_digest())

    def test_real_published_policy_reranks_without_source_edits(self):
        self.activate()
        before = self.business_digest()
        with CaptureQueriesContext(connection) as queries:
            result = self.fresh()
        self.assertEqual([r.pk for r in result.recommendations], [103, 101, 102, 104])
        self.assertLessEqual(len(queries), 50)  # Fixed capture + immutable publication verification; no per-product reads.
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        row = result.strategy_for(103)
        self.assertEqual(row["base_score"], "70.0000")
        self.assertEqual(row["saved_rank"], 3)
        self.assertEqual(row["effective_priority"], "37.50")
        self.assertEqual(row["target"]["points"], "2.50")
        self.assertEqual(row["promotion"]["points"], "5.00")
        self.assertEqual(before, self.business_digest())
        self.assertEqual(list(CustomerRecommendation.objects.order_by("rank").values_list("pk", flat=True)), [101, 102, 103, 104])

    def test_published_neutral_preserves_saved_order_not_score_order(self):
        self.activate(neutral_config())
        result = self.fresh()
        self.assertEqual([r.pk for r in result.recommendations], [101, 102, 103, 104])
        self.assertIsNotNone(result.strategy)
        self.assertEqual([r.score for r in result.recommendations], [40, 90, 70, 60])

    def test_legacy_and_overlay_contexts_ignore_subsequent_publication(self):
        legacy = self.fresh()
        first = self.activate()
        overlay = self.fresh()
        self.activate(neutral_config())
        with patch("apps.management.selling_strategy.resolve_fresh_strategy", side_effect=AssertionError("must not resolve on reuse")):
            self.assertEqual([r.pk for r in saved_priority(self.access, legacy.token).recommendations], [101, 102, 103, 104])
            reused = saved_priority(self.access, overlay.token)
        self.assertEqual(reused.token, overlay.token)
        self.assertEqual(reused.strategy, overlay.strategy)
        self.assertEqual(reused.strategy["policy_version_id"], first)
        self.assertEqual([r.pk for r in reused.recommendations], [103, 101, 102, 104])
        self.assertEqual([r.pk for r in self.fresh().recommendations], [101, 102, 103, 104])

    def test_customer360_and_catalog_share_order_and_signed_evidence(self):
        self.activate()
        customer = customer_selling_priority(self.user, self.customer, self.visit)
        catalog = build_catalog(self.user, self.customer.customer_code, self.visit.pk)
        self.assertEqual(customer.strategy, catalog["strategy"])
        self.assertEqual([r.pk for r in customer.recommendations], [r["recommendation"]["id"] for r in catalog["items"]])
        reused = build_catalog(self.user, self.customer.customer_code, self.visit.pk, {"catalog_context": customer.token})
        self.assertEqual(reused["catalog_context"], customer.token)

    def test_http_customer360_stamps_context_and_keeps_it_on_reload(self):
        self.activate()
        self.client.force_login(self.user)
        url = f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("catalog_context=", response.url)
        bound_url = response.url
        response = self.client.get(bound_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r.pk for r in response.context["recommendations"]], [103, 101, 102, 104])
        self.assertContains(response, "اولویت مؤثر")
        self.activate(neutral_config())
        response = self.client.get(bound_url)
        self.assertEqual([r.pk for r in response.context["recommendations"]], [103, 101, 102, 104])

    def test_customer360_read_api_opt_in_uses_same_context(self):
        self.activate()
        api = APIClient(); api.force_authenticate(self.user)
        response = api.get(reverse("customer-360-api", args=[self.customer.customer_code]), {"visit_id": self.visit.pk})
        self.assertEqual(response.status_code, 200)
        catalog = build_catalog(self.user, self.customer.customer_code, self.visit.pk, {"catalog_context": response.data["catalog_context"]})
        self.assertEqual(response.data["strategy"], catalog["strategy"])

    def test_signed_integrity_actor_binding_and_changed_recommendations_preserved(self):
        self.activate()
        result = self.fresh()
        for token in (result.token + "tampered", signing.dumps({"version": 1}, salt=CONTEXT_SALT)):
            with self.assertRaises(CatalogContextUnavailable):
                saved_priority(self.access, token)
        payload = signing.loads(result.token, salt=CONTEXT_SALT)
        payload["strategy"]["effective_order"] = list(reversed(payload["strategy"]["effective_order"]))
        with self.assertRaises(CatalogContextUnavailable):
            saved_priority(self.access, signing.dumps(payload, salt=CONTEXT_SALT))
        with self.assertRaises(CatalogContextUnavailable):
            saved_priority(replace(self.access, user=self.manager), result.token)
        CustomerRecommendation.objects.filter(pk=103).update(reason="تغییر واقعی پیشنهاد")
        with self.assertRaises(CatalogContextUnavailable):
            saved_priority(self.access, result.token)

    def test_authorization_and_assignment_checks_no_manager_impersonation(self):
        self.activate()
        with self.assertRaises(PermissionDenied):
            customer_selling_priority(self.manager, self.customer, self.visit, self.fresh().token)
        CustomerAssignment.objects.update(is_active=False)
        with self.assertRaises(Exception) as error:
            self.fresh()
        self.assertIn(type(error.exception).__name__, ("Http404", "PermissionDenied"))

    def test_new_selection_captures_strategy_legacy_selection_is_not_rewritten(self):
        legacy = self.fresh()
        first_command, first = self.add_product(legacy.token, 1)
        line = SalesRequestLine.objects.get(product_id=1)
        original = line.lineage_snapshot
        self.assertNotIn("strategy", original)
        self.activate()
        fresh = self.fresh()
        self.add_product(fresh.token)
        selected = SalesRequestLine.objects.get(product_id=3)
        self.assertEqual(selected.lineage_snapshot["rank"], 3)
        self.assertEqual(selected.lineage_snapshot["strategy"]["effective_position"], 1)
        self.assertEqual(selected.lineage_snapshot["strategy"]["policy_version_id"], self.head().active_version_id)
        line.refresh_from_db()
        self.assertEqual(line.lineage_snapshot, original)
        # Old UUID/payload recovers the exact committed result, not the current
        # policy or current request revision after the later addition.
        replay = mutate_basket(self.user, self.visit.pk, "ADD_PRODUCT", first_command)
        self.assertTrue(replay[2])
        self.assertEqual(replay[0], first[0])

    def test_feedback_context_lineage_and_replay_do_not_follow_new_policy(self):
        self.activate()
        context = self.fresh()
        command = {"customer_code": self.customer.customer_code, "recommendation_id": 103, "action": "LATER",
                   "reason_code": "LATER", "note": "", "expected_request_revision": None,
                   "command_uuid": uuid4(), "catalog_context": context.token}
        original = record_feedback(self.user, self.visit.pk, command)
        event = RecommendationFeedbackEvent.objects.get()
        self.assertEqual(event.lineage_snapshot["strategy"]["effective_position"], 1)
        self.activate(neutral_config())
        self.assertEqual(record_feedback(self.user, self.visit.pk, command)[0], original[0])
        self.assertEqual(RecommendationFeedbackEvent.objects.count(), 1)

    def test_quote_fingerprint_stock_and_prices_do_not_change_with_policy(self):
        before = basket_quote(self.user, self.customer.customer_code, self.visit.pk, 3, 1)
        self.activate()
        after = basket_quote(self.user, self.customer.customer_code, self.visit.pk, 3, 1)
        self.assertEqual(before, after)
        result = build_catalog(self.user, self.customer.customer_code, self.visit.pk)
        self.assertTrue(next(r for r in result["items"] if r["product_id"] == 3)["inventory_can_add"])

    def test_neutral_customer360_context_stays_neutral_after_publication(self):
        self.client.force_login(self.user)
        url = f"/customers/?customer_code={self.customer.customer_code}&visit_id={self.visit.pk}"
        original = self.client.get(url)
        self.assertEqual(original.status_code, 200)  # Legacy neutral HTTP shape retained.
        token = original.context["neutral_catalog_context"]
        self.assertContains(original, 'data-selling-context="' + token + '"')
        self.activate()
        resumed = self.client.get("/customers/", {"customer_code": self.customer.customer_code,
                                                  "visit_id": self.visit.pk, "catalog_context": token})
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual([r.pk for r in resumed.context["recommendations"]], [101, 102, 103, 104])

    def test_customer_product_return_retains_existing_policy_context(self):
        self.activate()
        context = self.fresh()
        self.activate(neutral_config())
        self.client.force_login(self.user)
        response = self.client.get(reverse("product-commercial-brief", args=["P3"]), {
            "customer_code": self.customer.customer_code, "visit_id": self.visit.pk, "catalog_context": context.token})
        self.assertEqual(response.status_code, 200)
        from urllib.parse import parse_qs, urlsplit
        self.assertEqual(parse_qs(urlsplit(response.context["return_url"]).query)["catalog_context"], [context.token])
        returned = self.client.get(response.context["return_url"])
        self.assertEqual(returned.status_code, 200)
        self.assertEqual([r.pk for r in returned.context["recommendations"]], [103, 101, 102, 104])

    def test_strategy_does_not_enable_unknown_zero_or_missing_price_products(self):
        self.activate()
        Inventory.objects.filter(product_id=3).delete()
        Inventory.objects.filter(product_id=1).update(available_quantity=0, reserved_quantity=0)
        ProductDemoPrice.objects.filter(product_id=2).delete()
        result = build_catalog(self.user, self.customer.customer_code, self.visit.pk)
        by_id = {row["product_id"]: row for row in result["items"]}
        self.assertEqual(result["strategy"]["effective_order"][0], 103)
        self.assertEqual(by_id[3]["non_addable_reason"], "INVENTORY_UNKNOWN")
        self.assertEqual(by_id[1]["non_addable_reason"], "OUT_OF_STOCK")
        self.assertEqual(by_id[2]["non_addable_reason"], "PRICE_UNAVAILABLE")
        self.assertTrue(all(not by_id[pk]["can_add"] for pk in (1, 2, 3)))

    def test_corrupt_active_policy_fails_closed_without_neutral_fallback(self):
        self.activate()
        old = self.fresh()
        models.QuerySet.update(StrategyPolicyVersion.objects.filter(pk=self.head().active_version_id), config_hash="0" * 64)
        with self.assertRaises(CatalogContextUnavailable):
            self.fresh()
        self.assertEqual(saved_priority(self.access, old.token).strategy, old.strategy)

    def test_pointer_to_unpublished_draft_is_not_an_active_policy(self):
        draft = self.draft()
        models.QuerySet.update(StrategyPolicy.objects.filter(pk=1), active_version_id=draft.event.version_id)
        with self.assertRaises(CatalogContextUnavailable):
            self.fresh()

    def test_evaluation_date_uses_explicit_tehran_zone_not_host_default(self):
        self.activate()
        with override_settings(TIME_ZONE="UTC"), patch("apps.management.selling_strategy.timezone.localdate", return_value=DAY) as clock:
            result = self.fresh()
        self.assertEqual(clock.call_args.kwargs["timezone"].key, "Asia/Tehran")
        self.assertEqual(result.strategy["evaluation_date"], DAY.isoformat())


@skipUnless(connection.vendor == "postgresql", "PostgreSQL snapshot publication race required")
class SellingStrategyPostgresTests(SellingFixture):
    def test_fresh_reads_under_independent_runtime_and_missing_grant_fail_closed(self):
        from django.conf import settings
        from psycopg import sql
        credentials = settings.STRATEGY_PUBLICATION_RUNTIME
        db = connections["default"]
        self.assertEqual(db.settings_dict["NAME"], credentials["NAME"])
        self.activate()
        before = self.business_digest()
        prior = {key: db.settings_dict[key] for key in ("USER", "PASSWORD")}
        def as_runtime():
            db.close(); db.settings_dict.update({key: credentials[key] for key in prior})
        def as_owner():
            db.close(); db.settings_dict.update(prior)
        try:
            as_runtime()
            with db.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_user")
                self.assertEqual(cursor.fetchone(), (credentials["NAME"], credentials["USER"]))
            result = self.fresh()
            self.assertEqual([r.pk for r in result.recommendations], [103, 101, 102, 104])
            as_owner()
            with db.cursor() as cursor:
                cursor.execute(sql.SQL("REVOKE SELECT ON management_strategypolicy FROM {}").format(sql.Identifier(credentials["USER"])))
            as_runtime()
            with self.assertRaises(CatalogContextUnavailable):
                self.fresh()
            # Existing signed context still resolves without any policy read.
            self.assertEqual(saved_priority(self.access, result.token).token, result.token)
        finally:
            as_owner()
            with db.cursor() as cursor:
                cursor.execute(sql.SQL("GRANT SELECT ON management_strategypolicy TO {}").format(sql.Identifier(credentials["USER"])))
        self.assertEqual(before, self.business_digest())

    def test_publication_during_issuance_cannot_mix_policy_and_source_image(self):
        first = self.activate()
        self.draft(neutral_config())
        comparison = self.preview()
        ready, resume = Event(), Event()
        original = adapter._capture_facts
        def paused(*args, **kwargs):
            ready.set()
            self.assertTrue(resume.wait(15))
            return original(*args, **kwargs)
        def worker():
            try:
                return self.fresh()
            finally:
                connections["default"].close()
        with patch("apps.management.selling_strategy._capture_facts", side_effect=paused), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            self.assertTrue(ready.wait(15))
            try:
                from .strategy_services import publish_strategy
                publish_strategy(**self.envelope(comparison))
            finally:
                resume.set()
            captured = future.result(timeout=20)
        self.assertEqual(captured.strategy["policy_version_id"], first)
        self.assertEqual([r.pk for r in captured.recommendations], [103, 101, 102, 104])
        self.assertEqual([r.pk for r in self.fresh().recommendations], [101, 102, 103, 104])
