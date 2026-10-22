"""Real normal Django login/session/CSRF API tests in disposable databases only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import secrets
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.color import no_style
from django.db import DatabaseError, connection, connections, models
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.inventory.models import Inventory
from apps.products.models import ProductDemoPrice
from apps.visits.models import CustomerAssignment
from . import tests_strategy_services as foundation
from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_serialization import neutral_config
from .tests_strategy_evaluator import DAY, config, priority


ROOT = "/api/management/v1/strategy/"


class APIFixture(foundation.ServiceFixture):
    def setUp(self):
        super().setUp()
        # The shared fixture explicitly inserts Customer(pk=1). PostgreSQL does
        # not advance its sequence for explicit PKs; later automatic identities
        # must not depend on which test happened to consume nextval first.
        with connection.cursor() as cursor:
            for statement in connection.ops.sequence_reset_sql(no_style(), [Customer]):
                cursor.execute(statement)
        self.password = secrets.token_urlsafe(32)
        self.manager.set_password(self.password)
        self.manager.save(update_fields=["password"])
        self.client = self.login(self.manager, self.password)

    def login(self, user, password):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.get("/accounts/login/").status_code, 200)
        response = client.post("/accounts/login/", {"username": user.username, "password": password,
                                                    "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Session.objects.filter(session_key=client.cookies[settings.SESSION_COOKIE_NAME].value).exists())
        return client

    def post(self, route, data, *, client=None):
        client = client or self.client
        return client.post(ROOT + route, data, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

    def api_draft(self, **overrides):
        body = {"command_uuid": str(uuid4()), "expected_revision": StrategyPolicy.objects.filter(pk=1).values_list("revision", flat=True).first() or 0,
                "config": config(priority_rules=[priority("PRODUCT", 3, 20)]), **overrides}
        response = self.post("draft/", body)
        self.assertEqual(response.status_code, 201, response.data)
        return body, response

    def api_preview(self):
        head = self.head()
        query = {"customer_id": self.customer.pk, "salesperson_id": self.rep.pk, "proposed_version_id": head.draft_version_id,
                 "expected_revision": head.revision, "evaluation_date": DAY.isoformat()}
        capture = self.client.get(ROOT + "options/", query)
        self.assertEqual(capture.status_code, 200, capture.data)
        body = {"command_uuid": str(uuid4()), **capture.data["preview_context"]}
        response = self.post("comparisons/", body)
        self.assertEqual(response.status_code, 201, response.data)
        evidence = self.client.get(ROOT + f"comparisons/{response.data['result']['comparison_id']}/")
        self.assertEqual(evidence.status_code, 200)
        return evidence.data, body, response

    def publish_body(self, evidence, **overrides):
        return {"command_uuid": str(uuid4()), "expected_revision": evidence["policy_revision"],
                "draft_version_id": evidence["after_version_id"], "comparison_id": evidence["comparison_id"],
                "accepted_comparison_digest": evidence["output_digest"], **overrides}


class StrategyAPITests(APIFixture):
    def test_routes_versioned_names_and_original_dashboard_preserved(self):
        for route, name in (("overview/", "overview"), ("options/", "options"), ("versions/", "versions"),
                            ("draft/", "draft"), ("comparisons/", "comparisons"), ("publish/", "publish"), ("rollback/", "rollback")):
            self.assertEqual(resolve(ROOT + route).view_name, "management_api:strategy:" + name)
            self.assertEqual(reverse("management_api:strategy:" + name), ROOT + route)
        self.assertEqual(resolve("/api/management/v1/dashboard/").url_name, "dashboard")

    def test_all_first_use_gets_and_heads_are_zero_write(self):
        before = self.business_digest()
        with CaptureQueriesContext(connection) as queries:
            for route, expected in (("overview/", 200), ("options/", 200), ("versions/", 200),
                                    (f"commands/{uuid4()}/", 404), ("comparisons/999999/", 404)):
                self.assertEqual(self.client.get(ROOT + route).status_code, expected)
                self.assertEqual(self.client.head(ROOT + route).status_code, expected)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(self.counts(), [0, 0, 0, 0])
        self.assertEqual(before, self.business_digest())
        overview = self.client.get(ROOT + "overview/").data
        self.assertEqual(overview["active_config"], neutral_config())
        self.assertFalse(overview["impact_available"])
        self.assertIsNone(overview["active_version_id"])

    def test_anonymous_routes_require_session_authentication(self):
        client = APIClient(enforce_csrf_checks=True)
        for route in ("overview/", "options/", "versions/", "comparisons/123/", f"commands/{uuid4()}/"):
            response = client.get(ROOT + route)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data["code"], "AUTHENTICATION_REQUIRED")
        for route in ("draft/", "comparisons/", "publish/", "rollback/"):
            self.assertEqual(client.post(ROOT + route, {}, format="json").status_code, 401)
        self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_nonstaff_and_deactivated_manager_cannot_access(self):
        user = get_user_model().objects.create_user(username="no-strategy", password=self.password)
        client = self.login(user, self.password)
        for route in ("overview/", "options/", "versions/", "comparisons/999/", f"commands/{uuid4()}/"):
            self.assertEqual(client.get(ROOT + route).status_code, 403)
        for route in ("draft/", "comparisons/", "publish/", "rollback/"):
            response = self.post(route, {}, client=client)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data["code"], "ACCESS_DENIED")
        get_user_model().objects.filter(pk=self.manager.pk).update(is_active=False)
        self.assertEqual(self.client.get(ROOT + "overview/").status_code, 401)

    def test_capabilities_can_be_separated_without_salesperson_impersonation(self):
        self.assertIsNone(getattr(self.manager, "salesperson_profile", None))
        with patch("apps.management.strategy_api_views.can_manage_strategy", return_value=False):
            self.assertEqual(self.client.get(ROOT + "overview/").status_code, 200)
            self.assertEqual(self.post("draft/", {}).status_code, 403)

    def test_all_mutations_enforce_missing_invalid_and_valid_csrf(self):
        for route in ("draft/", "comparisons/", "publish/", "rollback/"):
            for headers in ({}, {"HTTP_X_CSRFTOKEN": "invalid"}):
                response = self.client.post(ROOT + route, {}, format="json", **headers)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data["code"], "CSRF_FAILED")
        self.api_draft()  # Same normal session with valid CSRF succeeds.
        self.assertEqual(StrategyPolicyVersion.objects.count(), 1)

    def test_strict_typed_draft_rejects_unknown_fields_bounds_and_references(self):
        valid = {"command_uuid": str(uuid4()), "expected_revision": 0, "config": neutral_config()}
        for changes in ({"expected_revision": True}, {"expected_revision": "0"}, {"extra": "private"},
                        {"command_uuid": "bad"}, {"command_uuid": True}, {"command_uuid": 1}, {"config": config(target_weight=6)},
                        {"config": config(priority_rules=[priority("PRODUCT", 999999, 10)])},
                        {"config": config(priority_rules=[priority("PRODUCT", 1, 5)] * 2)}):
            with self.subTest(changes=changes):
                response = self.post("draft/", {**valid, **changes})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], "INVALID_INPUT")
                self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_complete_http_draft_preview_publish_flow_preserves_all_business_rows(self):
        before = self.business_digest()
        self.api_draft()
        evidence, _, _ = self.api_preview()
        self.assertEqual(evidence["outputs"]["before"]["after_ids"], [101, 102, 103, 104])
        self.assertIn("priority", evidence["outputs"]["after"]["rows"][0])
        self.assertEqual(evidence["quotes"]["1"]["quote"]["currency"], "TOMAN")
        self.assertNotIn("inputs", evidence)
        self.assertNotIn("database", str(evidence))
        self.assertEqual(evidence["availability_scope"], "COMMERCIAL_QUANTITY_ONE_NOT_VISIT_MUTATION_AUTHORIZATION")
        response = self.post("publish/", self.publish_body(evidence))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["result"]["active_version_id"], evidence["after_version_id"])
        self.assertIsNone(self.head().draft_version_id)
        self.assertEqual(before, self.business_digest())

    def test_preview_persists_only_comparison_and_event_and_returns_immutable_digest(self):
        self.api_draft()
        before, head = self.counts(), list(StrategyPolicy.objects.values())
        evidence, _, _ = self.api_preview()
        self.assertEqual(self.counts(), [before[0], before[1], before[2] + 1, before[3] + 1])
        self.assertEqual(head, list(StrategyPolicy.objects.values()))
        self.assertEqual(evidence["output_digest"], StrategyComparison.objects.get().output_digest)
        self.assertTrue(evidence["outputs"]["simulation_only"])
        self.assertIsNone(evidence["outputs"]["revenue_uplift"])

    def test_read_options_are_bounded_and_customer_options_require_assignment(self):
        Customer.objects.create(customer_code="UNASSIGNED-API", name="بدون تخصیص")
        response = self.client.get(ROOT + "options/", {"kind": "customers", "salesperson_id": self.rep.pk, "evaluation_date": DAY.isoformat()})
        self.assertEqual([row["id"] for row in response.data["results"]], [self.customer.pk])
        self.assertEqual(self.client.get(ROOT + "options/", {"kind": "customers"}).status_code, 400)
        for kind in ("products", "brands", "categories", "promotions", "salespersons"):
            response = self.client.get(ROOT + "options/", {"kind": kind, "limit": 1})
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(len(response.data["results"]), 1)
            self.assertNotIn("password", str(response.data))
        for query in ({"limit": 101}, {"after_id": -1}, {"kind": "wrong"}, {"customer_id": 1}, {"unknown": 1}):
            self.assertEqual(self.client.get(ROOT + "options/", query).status_code, 400)
        self.assertEqual(self.client.get(ROOT + "options/?limit=1&limit=2").status_code, 400)

    def test_cross_customer_and_inactive_assignment_reject_capture_and_preview(self):
        self.api_draft()
        head = self.head()
        wrong = Customer.objects.create(customer_code="OTHER-API", name="مشتری دیگر")
        context = {"customer_id": wrong.pk, "salesperson_id": self.rep.pk, "proposed_version_id": head.draft_version_id,
                   "expected_revision": head.revision, "evaluation_date": DAY.isoformat()}
        self.assertEqual(self.client.get(ROOT + "options/", context).status_code, 403)
        self.assertEqual(self.post("comparisons/", {**context, "command_uuid": str(uuid4()), "accepted_source_fingerprint": "0" * 64}).status_code, 403)
        context["customer_id"] = self.customer.pk
        CustomerAssignment.objects.update(is_active=False)
        self.assertEqual(self.client.get(ROOT + "options/", context).status_code, 403)
        self.assertFalse(StrategyComparison.objects.exists())

    def test_draft_replay_conflicting_intent_and_stale_revision_http_contracts(self):
        body, first = self.api_draft()
        replay = self.post("draft/", body)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        conflict = self.post("draft/", {**body, "config": neutral_config()})
        self.assertEqual((conflict.status_code, conflict.data["code"]), (409, "COMMAND_INTENT_CONFLICT"))
        stale = self.post("draft/", {**body, "command_uuid": str(uuid4())})
        self.assertEqual((stale.status_code, stale.data["code"]), (409, "STALE_POLICY_REVISION"))

    def test_preview_replay_and_frozen_historical_get_after_assignment_change(self):
        self.api_draft()
        evidence, body, first = self.api_preview()
        CustomerAssignment.objects.update(is_active=False)
        replay = self.post("comparisons/", body)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(self.client.get(ROOT + f"comparisons/{evidence['comparison_id']}/").data, evidence)
        response = self.client.get(ROOT + f"commands/{body['command_uuid']}/")
        self.assertEqual(response.data["result"], first.data["result"])

    def test_publication_replay_after_physical_reconnect_preserves_body(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        body = self.publish_body(evidence)
        first = self.post("publish/", body)
        self.assertEqual(first.status_code, 200)
        Inventory.objects.update(available_quantity=0)
        connection.close()
        replay = self.post("publish/", body)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="PUBLISH").count(), 1)

    def test_stale_comparison_source_and_assignment_drift(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        ProductDemoPrice.objects.filter(product_id=1).update(base_price=101)
        response = self.post("publish/", self.publish_body(evidence))
        self.assertEqual((response.status_code, response.data["code"]), (409, "STALE_STRATEGY_INPUTS"))
        evidence, _, _ = self.api_preview()
        CustomerAssignment.objects.update(end_date=DAY + timedelta(days=1))
        self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 409)
        self.assertIsNone(self.head().active_version_id)

    def test_tampered_evidence_returns_stable_redacted_error(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        models.QuerySet.update(StrategyComparison.objects.filter(pk=evidence["comparison_id"]), output_digest="0" * 64)
        for response in (self.post("publish/", self.publish_body(evidence)), self.client.get(ROOT + f"comparisons/{evidence['comparison_id']}/")):
            self.assertEqual((response.status_code, response.data["code"]), (409, "INVALID_STRATEGY_EVIDENCE"))
            self.assertNotIn("SELECT", str(response.data))
            self.assertNotIn("output_digest", str(response.data))

    def test_rollback_prepare_preview_activate_and_replay(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 200)
        prior = self.head().active_version_id
        prepare_body = {"action": "PREPARE", "target_version_id": None, "command_uuid": str(uuid4()), "expected_revision": 2}
        prepared = self.post("rollback/", prepare_body)
        self.assertEqual(prepared.status_code, 201, prepared.data)
        self.assertEqual(self.post("rollback/", prepare_body).data, prepared.data)
        self.assertEqual(self.head().active_version_id, prior)
        evidence, _, _ = self.api_preview()
        body = self.publish_body(evidence, action="ACTIVATE")
        result = self.post("rollback/", body)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["operation"], "ROLLBACK")
        self.assertNotEqual(self.head().active_version_id, prior)
        self.assertEqual(self.post("rollback/", body).data, result.data)
        self.assertEqual(StrategyPolicyVersion.objects.count(), 2)

    def test_commands_are_actor_bound_missing_and_malformed_are_distinct(self):
        body, first = self.api_draft()
        other = get_user_model().objects.create_user(username="other-strategy-manager", password=self.password, is_staff=True)
        client = self.login(other, self.password)
        self.assertEqual(client.get(ROOT + f"commands/{body['command_uuid']}/").status_code, 403)
        self.assertEqual(self.client.get(ROOT + f"commands/{uuid4()}/").status_code, 404)
        self.assertEqual(self.client.get(ROOT + "commands/not-a-uuid/").status_code, 400)
        self.assertEqual(self.client.get(ROOT + f"commands/{body['command_uuid']}/").data["result"], first.data["result"])

    def test_versions_pagination_and_no_history_mutation_routes(self):
        first, _ = self.api_draft()
        self.api_draft(config=neutral_config())
        page = self.client.get(ROOT + "versions/", {"limit": 1})
        self.assertEqual(len(page.data["results"]), 1)
        last = self.client.get(ROOT + "versions/", {"after_id": page.data["next_after_id"], "limit": 1})
        self.assertEqual(len(last.data["results"]), 1)
        self.assertIsNone(last.data["next_after_id"])
        before = self.counts()
        for route in ("versions/", "overview/", "options/"):
            self.assertEqual(self.post(route, first).status_code, 405)
        self.assertEqual(before, self.counts())

    def test_post_only_routes_get_and_head_never_write(self):
        before = self.business_digest()
        for route in ("draft/", "comparisons/", "publish/", "rollback/"):
            self.assertEqual(self.client.get(ROOT + route).status_code, 405)
            self.assertEqual(self.client.head(ROOT + route).status_code, 405)
        self.assertEqual(self.counts(), [0, 0, 0, 0])
        self.assertEqual(before, self.business_digest())

    def test_json_parse_errors_cache_and_missing_database_capability_fail_closed(self):
        response = self.client.post(ROOT + "draft/", "{", content_type="application/json", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual((response.status_code, response.data["code"]), (400, "INVALID_INPUT"))
        with patch("apps.management.strategy_api_views.create_strategy_draft", side_effect=DatabaseError("private endpoint/password must not leak")):
            response = self.post("draft/", {"command_uuid": str(uuid4()), "expected_revision": 0, "config": neutral_config()})
            self.assertEqual((response.status_code, response.data["code"]), (503, "STRATEGY_NOT_READY"))
            self.assertNotIn("private endpoint", str(response.data))
            self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_scalar_array_and_unknown_body_fields_return_structured_400(self):
        for body in ([1, 2], "wrong", {"unapproved": True}):
            with self.subTest(body=body):
                response = self.post("draft/", body)
                self.assertEqual((response.status_code, response.data["code"]), (400, "INVALID_INPUT"))
        self.assertEqual(self.counts(), [0, 0, 0, 0])

    def test_normal_logout_invalidates_api_session(self):
        session_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertIsNotNone(get_user_model().objects.get(pk=self.manager.pk).last_login)
        self.assertEqual(self.client.post("/accounts/logout/", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertEqual(self.client.get(ROOT + "overview/").status_code, 401)


@skipUnless(connection.vendor == "postgresql", "Real PostgreSQL publication races and runtime credentials required")
class StrategyAPIPostgresTests(APIFixture):
    def test_concurrent_http_publications_use_real_sessions_and_one_revision(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        clients = [self.login(self.manager, self.password) for _ in range(2)]
        barrier = Barrier(2)
        def worker(client):
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                barrier.wait(timeout=15)
                response = self.post("publish/", self.publish_body(evidence), client=client)
                return pid, response.status_code
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, clients))
        self.assertEqual(len({r[0] for r in results}), 2)
        self.assertEqual(sorted(r[1] for r in results), [200, 409])
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="PUBLISH").count(), 1)
        self.assertEqual(self.head().revision, 2)

    def test_concurrent_http_publish_and_rollback_have_one_winner(self):
        self.api_draft()
        evidence, _, _ = self.api_preview()
        self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 200)
        self.assertEqual(self.post("rollback/", {"action": "PREPARE", "target_version_id": None, "expected_revision": 2,
                                              "command_uuid": str(uuid4())}).status_code, 201)
        evidence, _, _ = self.api_preview()
        # A rollback draft can only activate through rollback; race two actual
        # HTTP activations using independent connections and real session cookies.
        clients = [self.login(self.manager, self.password) for _ in range(2)]
        barrier = Barrier(2)
        def worker(client):
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                barrier.wait(timeout=15)
                response = self.post("rollback/", self.publish_body(evidence, action="ACTIVATE"), client=client)
                return pid, response.status_code
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, clients))
        self.assertEqual(len({r[0] for r in results}), 2)
        self.assertEqual(sorted(r[1] for r in results), [200, 409])
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="ROLLBACK").count(), 1)

    @contextmanager
    def runtime(self):
        db, credentials = connections["default"], settings.STRATEGY_PUBLICATION_RUNTIME
        self.assertEqual(db.settings_dict["NAME"], credentials["NAME"])
        prior = {key: db.settings_dict[key] for key in ("USER", "PASSWORD")}
        db.close()
        db.settings_dict.update({key: credentials[key] for key in prior})
        try:
            with db.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_user")
                self.assertEqual(cursor.fetchone(), (credentials["NAME"], credentials["USER"]))
            yield
        finally:
            db.close()
            db.settings_dict.update(prior)

    def test_normal_http_login_commands_logout_under_independent_runtime_role(self):
        with self.runtime():
            self.client = self.login(self.manager, self.password)
            self.api_draft()
            evidence, _, _ = self.api_preview()
            self.assertEqual(self.post("publish/", self.publish_body(evidence)).status_code, 200)
            self.assertEqual(self.client.get(ROOT + "overview/").status_code, 200)
            session_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
            self.assertEqual(self.client.post("/accounts/logout/", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value).status_code, 302)
            self.assertFalse(Session.objects.filter(session_key=session_key).exists())
            self.assertEqual(self.client.get(ROOT + "overview/").status_code, 401)
