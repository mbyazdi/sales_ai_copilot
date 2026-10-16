"""B3 real-session integration probes, run only by verify_generation_postgres.py.

Each probe uses a rollback-only PostgreSQL transaction under B1 runtime grants.
No force_login, force_authenticate, memory sessions or CSRF exemptions.
"""
import json
import re
import secrets
import unittest
from uuid import uuid4

from common import read_json, write_json


def seed(case):
    from apps.products.tests_catalog import CatalogBackendTests
    from apps.visits.models import Visit
    CatalogBackendTests.setUpTestData.__func__(case)
    case.password = secrets.token_urlsafe(40)
    for user in (case.user, case.foreign_user, case.staff):
        user.set_password(case.password)
        user.save(update_fields=["password"])
    case.planned = Visit.objects.create(customer=case.customer, salesperson=case.rep,
        visit_date=case.visit.visit_date, status="PLANNED")


def endpoint_inventory():
    """Conservative route inventory: every explicit unsafe API and admin form route."""
    from django.urls import URLResolver, get_resolver
    found = []

    def walk(patterns, prefix=""):
        for pattern in patterns:
            route = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns, route)
                continue
            cls = getattr(pattern.callback, "view_class", None) or getattr(pattern.callback, "cls", None)
            methods = [m.upper() for m in ("post", "put", "patch", "delete") if cls and hasattr(cls, m)
                       and m in getattr(cls, "http_method_names", ("post", "put", "patch", "delete"))]
            if route.startswith("admin/"):
                # Include admin actions/changelists, login/logout and password forms;
                # some read-only admin handlers will reject POST after a valid guard.
                methods = ["POST"]
            if not methods:
                continue
            path = re.sub(r"<(?:[^:>]+:)?([^>]+)>",
                lambda m: str(uuid4()) if "uuid" in m.group(0) else "CAT-A" if "code" in m.group(1) else "1", route)
            path = path.replace("^", "").replace("$", "")
            found.append(dict(route=route, path="/" + path, methods=methods, name=pattern.name))

    walk(get_resolver().url_patterns)
    return found


class LiveGenerationTests(unittest.TestCase):
    def setUp(self):
        from django.db import connection, transaction
        self.assertEqual(connection.vendor, "postgresql")
        self.assertEqual(connection.settings_dict["NAME"], self.test_profile["database"])
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_stage3h3b3_"))
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.addCleanup(self.rollback)
        self.client = self.login(self.user)
        self.visit.refresh_from_db()
        self.planned.refresh_from_db()

    def rollback(self):
        from django.db import transaction
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def login(self, user):
        from django.test import Client
        from django.contrib.sessions.models import Session
        from scripts.demo import generation as g
        client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost", SERVER_NAME="localhost")
        page = client.get("/accounts/login/")
        self.assertEqual(page.status_code, 200)
        proof = re.search(rb'data-demo-proof="([^"]+)"', page.content).group(1).decode()
        client.defaults.update(HTTP_X_DEMO_GENERATION_PROOF=proof, HTTP_ORIGIN="http://localhost")
        result = client.post("/accounts/login/", dict(username=user.username, password=self.password,
            csrfmiddlewaretoken=client.cookies["csrftoken"].value))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(client.session[g.SESSION_KEY], self.test_profile["identity"])
        self.assertEqual(client.session["_auth_user_id"], str(user.pk))
        self.assertTrue(Session.objects.filter(session_key=client.session.session_key).exists())
        user.refresh_from_db()
        self.assertIsNotNone(user.last_login)
        return client

    def send(self, path, body=None, method="post", client=None, **headers):
        client = client or self.client
        return getattr(client, method)(path, json.dumps(body or {}), content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value, **headers)

    def state(self):
        from django.apps import apps
        return {m._meta.label: list(m.objects.order_by("pk").values()) for m in apps.get_models()}

    def context(self):
        response = self.client.get("/api/products/v1/catalog/", dict(customer_code=self.customer.customer_code, visit_id=self.visit.pk))
        self.assertEqual(response.status_code, 200)
        return response.json()["catalog_context"]

    def add_command(self, product=None, quantity=1):
        product = product or self.products[0]
        quote = self.client.get(f"/api/sales-requests/v1/visits/{self.visit.pk}/basket/quote/",
            dict(customer_code=self.customer.customer_code, product_id=product.pk, quantity=quantity))
        self.assertEqual(quote.status_code, 200)
        value = quote.json()
        return dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()),
            product_id=product.pk, quantity=quantity, catalog_context=self.context(),
            expected_request_revision=value["expected_request_revision"], accepted_quote_fingerprint=value["quote_fingerprint"])

    def add(self, command=None):
        return self.send(f"/api/sales-requests/v1/visits/{self.visit.pk}/lines/", command or self.add_command())

    def test_01_inventory_includes_all_business_auth_and_admin_mutators(self):
        names = {r["name"] for r in self.routes}
        self.assertTrue({"visit-start", "visit-complete", "visit-completion-v1", "sales-outcome-create",
            "follow-up-task-status", "visit-basket-add-v1", "request-basket-line-v1", "recommendation-feedback-v1",
            "visit-request-submit-v1", "login", "logout", "recommendation-tuning-suggestion-status",
            "recommendation-tuning-suggestion-apply", "recommendation-tuning-suggestion-rollback"} <= names)
        self.assertTrue(any(r["route"].startswith("admin/") for r in self.routes))

    def test_02_all_mutating_routes_missing_stale_tampered_proof_are_zero_write(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from scripts.demo import generation as g
        for proof in (None, "", g.document_proof(str(uuid4())), "unsigned", g.document_proof(self.test_profile["identity"]) + "x"):
            before = self.state()
            for route in self.routes:
                for method in route["methods"]:
                    with self.subTest(route=route["route"], method=method, proof_kind=(proof or "absent")[:6]):
                        with CaptureQueriesContext(connection) as queries:
                            response = self.send(route["path"], dict(command_uuid=str(uuid4())), method.lower(),
                                HTTP_X_DEMO_GENERATION_PROOF=proof)
                        self.assertEqual((response.status_code, response.json()["code"]), (409, "DEMO_COMMAND_GENERATION_STALE"))
                        self.assertFalse(any(re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", q["sql"], re.I) for q in queries))
            self.assertEqual(self.state(), before)

    def test_03_all_routes_stale_or_unbound_sessions_even_with_current_proof(self):
        from scripts.demo import generation as g
        for value in (None, str(uuid4())):
            session = self.client.session
            session.pop(g.SESSION_KEY, None)
            if value is not None:
                session[g.SESSION_KEY] = value
            session.save()
            before = self.state()
            for route in self.routes:
                if route["path"] == "/accounts/login/":
                    continue  # Deliberate recovery: normal reauthentication binds a new session.
                for method in route["methods"]:
                    with self.subTest(route=route["route"], binding=value):
                        response = self.send(route["path"], method=method.lower())
                        self.assertEqual((response.status_code, response.json()["code"]), (403, "DEMO_SESSION_STALE"))
            self.assertEqual(self.state(), before)

    def test_04_missing_registry_and_wrong_database_endpoint_fail_before_views(self):
        original = read_json(self.state_dir / "generation-state.json")
        profile = read_json(self.state_dir / "profile.json")
        before = self.state()
        try:
            for patch in ({"database": "sales_ai_db"}, {"database_port": 5432}, {"database_oid": profile["database_oid"] + 1},
                          {"identity": str(uuid4())}, {"container_id": "foreign"}):
                write_json(self.state_dir / "profile.json", {**profile, **patch})
                result = self.send(f"/api/visits/v1/visits/{self.planned.pk}/start/")
                self.assertEqual((result.status_code, result.json()["code"]), (503, "DEMO_MAINTENANCE_UNCERTAIN"))
            write_json(self.state_dir / "profile.json", profile)
            for state in ({}, {**original, "phase": "PROFILE_SELECTED"}, {**original, "active_generation": str(uuid4())}):
                write_json(self.state_dir / "generation-state.json", state)
                self.assertEqual(self.send(f"/api/visits/v1/visits/{self.planned.pk}/start/").status_code, 503)
            (self.state_dir / "generation-state.json").rename(self.state_dir / "registry-held.json")
            self.assertEqual(self.send(f"/api/visits/v1/visits/{self.planned.pk}/start/").status_code, 503)
            (self.state_dir / "registry-held.json").rename(self.state_dir / "generation-state.json")
        finally:
            write_json(self.state_dir / "profile.json", profile)
            write_json(self.state_dir / "generation-state.json", original)
        self.assertEqual(self.state(), before)

    def test_05_csrf_independent_of_valid_generation_for_session_api_and_logout(self):
        before = self.state()
        for path in (f"/api/visits/v1/visits/{self.planned.pk}/start/", "/accounts/logout/",
                     f"/api/recommendations/v1/visits/{self.visit.pk}/feedback/"):
            for token in (None, "invalid"):
                kwargs = {} if token is None else {"HTTP_X_CSRFTOKEN": token}
                response = self.client.post(path, "{}", content_type="application/json", **kwargs)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.state(), before)

    def test_06_start_and_legacy_completion_keep_original_lifecycle(self):
        response = self.send(f"/api/visits/v1/visits/{self.planned.pk}/start/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visit"]["status"], "IN_PROGRESS")
        path = f"/api/visits/v1/visits/{self.planned.pk}/complete/"
        self.assertEqual(self.send(path).status_code, 200)
        self.assertEqual(self.send(path).status_code, 400)

    def test_07_basket_replay_revision_intent_and_ordinary_history(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
        from apps.recommendations.models import RecommendationFeedbackEvent
        command = self.add_command(self.products[3])
        first = self.add(command)
        self.assertEqual(first.status_code, 201)
        before = self.state()
        replay = self.add(command)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.add({**command, "quantity": 2}).status_code, 409)
        self.assertEqual(self.add({**self.add_command(self.products[1]), "expected_request_revision": 0}).status_code, 409)
        line = SalesRequestLine.objects.get(is_selected=True)
        change = self.add_command(self.products[3], quantity=2)
        change.pop("product_id")
        path = f"/api/sales-requests/v1/requests/{line.sales_request_id}/lines/{line.pk}/"
        self.assertEqual(self.send(path, change, "patch").status_code, 200)
        remove = dict(customer_code=self.customer.customer_code, catalog_context=self.context(),
            command_uuid=str(uuid4()), expected_request_revision=2)
        self.assertEqual(self.send(path, remove, "delete").status_code, 200)
        self.assertEqual(SalesRequest.objects.get().revision, 3)
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 3)
        self.assertFalse(RecommendationFeedbackEvent.objects.exists())

    def test_08_feedback_later_rejection_replay_conflict(self):
        from apps.recommendations.models import RecommendationFeedbackEvent
        path = f"/api/recommendations/v1/visits/{self.visit.pk}/feedback/"
        command = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()),
            recommendation_id=self.recs[0].pk, action="LATER", catalog_context=self.context())
        result = self.send(path, command)
        self.assertEqual(result.status_code, 201)
        before = self.state()
        replay = self.send(path, command)
        self.assertEqual(replay.json(), result.json())
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.send(path, {**command, "action": "REJECTED", "reason_code": "PRICE"}).status_code, 409)
        rejected = self.send(path, {**command, "command_uuid": str(uuid4()), "action": "REJECTED", "reason_code": "PRICE"})
        self.assertEqual(rejected.status_code, 201)
        self.assertEqual(list(RecommendationFeedbackEvent.objects.values_list("event_type", "reason_code")),
            [("REJECTED", "LATER"), ("REJECTED", "PRICE")])

    def test_09_submit_completion_ack_recovery_and_immutable_history(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestAcknowledgement
        self.assertEqual(self.add().status_code, 201)
        review_path = f"/api/sales-requests/v1/visits/{self.visit.pk}/review/"
        review = self.client.get(review_path, dict(customer_code=self.customer.customer_code)).json()
        command = dict(customer_code=self.customer.customer_code, catalog_context=self.context(), command_uuid=str(uuid4()),
            expected_request_revision=review["request"]["revision"], accepted_review_fingerprint=review["review_fingerprint"])
        path = f"/api/sales-requests/v1/visits/{self.visit.pk}/submit/"
        first = self.send(path, command)
        self.assertEqual(first.status_code, 201)
        before = self.state()
        replay = self.send(path, command)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(self.state(), before)
        finish = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()))
        finish_path = f"/api/visits/v1/visits/{self.visit.pk}/completion/"
        result = self.send(finish_path, finish)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["visit"]["status"], "COMPLETED")
        self.assertEqual(SalesRequestAcknowledgement.objects.count(), 1)
        before = self.state()
        self.assertEqual(self.send(finish_path, finish).json(), result.json())
        self.assertEqual(self.client.get(finish_path, dict(customer_code=self.customer.customer_code)).json()["recorded_result"], result.json())
        self.assertEqual(self.send(path, command).json(), first.json())
        self.assertEqual(self.state(), before)
        self.assertEqual(SalesRequest.objects.get().status, "SUBMITTED")

    def test_10_auth_logout_invalidates_database_session_and_get_is_not_logout(self):
        from django.contrib.sessions.models import Session
        key = self.client.session.session_key
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertTrue(Session.objects.filter(session_key=key).exists())
        response = self.send("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.get("/customers/").status_code, 403)

    def test_11_authorization_not_weakened_by_valid_generation(self):
        for user in (self.foreign_user, self.staff):
            client = self.login(user)
            before = self.state()
            result = self.send(f"/api/visits/v1/visits/{self.planned.pk}/start/", client=client)
            self.assertIn(result.status_code, (403, 404))
            result = self.send(f"/api/visits/v1/visits/{self.visit.pk}/completion/",
                dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4())), client=client)
            self.assertIn(result.status_code, (403, 404))
            self.assertEqual(self.state(), before)

    def test_12_real_session_reauthentication_recovers_stale_binding(self):
        from scripts.demo import generation as g
        session = self.client.session
        session[g.SESSION_KEY] = str(uuid4())
        session.save()
        self.assertEqual(self.client.get("/api/visits/").status_code, 403)
        # Login is intentionally the recovery exception, still requiring both proofs.
        response = self.client.post("/accounts/login/", dict(username=self.user.username, password=self.password,
            csrfmiddlewaretoken=self.client.cookies["csrftoken"].value))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[g.SESSION_KEY], self.test_profile["identity"])
        self.assertEqual(self.client.get("/api/visits/").status_code, 200)

    def test_13_old_pending_wire_rejected_even_after_success_and_fresh_login(self):
        from scripts.demo import generation as g
        command = self.add_command()
        wire = json.dumps(command)
        self.assertEqual(self.add(command).status_code, 201)
        client = self.login(self.user)
        before = self.state()
        response = client.post(f"/api/sales-requests/v1/visits/{self.visit.pk}/lines/", wire,
            content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            HTTP_X_DEMO_GENERATION_PROOF=g.document_proof(str(uuid4())))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.state(), before)
        self.assertEqual(json.dumps(command), wire)
        self.assertEqual(self.add(command)["Idempotent-Replayed"], "true")

    def test_14_admin_login_logout_are_standard_and_generation_bound(self):
        client = self.login(self.staff)
        self.assertEqual(client.get("/admin/").status_code, 200)
        response = self.send("/admin/logout/", client=client)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", client.session)

    def test_15_no_request_completion_replay_and_conflict(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestMutationReceipt
        path = f"/api/visits/v1/visits/{self.visit.pk}/completion/"
        command = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()))
        first = self.send(path, command)
        self.assertEqual(first.status_code, 200)
        before = self.state()
        replay = self.send(path, command)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(self.send(path, {**command, "command_uuid": str(uuid4())}).status_code, 409)
        self.assertEqual(self.client.get(path, dict(customer_code=self.customer.customer_code)).json()["recorded_result"], first.json())
        self.assertEqual(self.state(), before)
        self.assertFalse(SalesRequest.objects.exists())
        self.assertEqual(SalesRequestMutationReceipt.objects.get().operation, "COMPLETE_VISIT")

    def test_16_retained_draft_completion_preserves_request(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestLine
        self.assertEqual(self.add().status_code, 201)
        before = (list(SalesRequest.objects.values()), list(SalesRequestLine.objects.values()))
        response = self.send(f"/api/visits/v1/visits/{self.visit.pk}/completion/",
            dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4())))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request"]["status"], "DRAFT")
        self.assertEqual((list(SalesRequest.objects.values()), list(SalesRequestLine.objects.values())), before)

    def test_17_login_rejects_invalid_csrf_and_stale_proof_without_auth_writes(self):
        from django.test import Client
        from scripts.demo import generation as g
        client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost", SERVER_NAME="localhost")
        page = client.get("/accounts/login/")
        current = re.search(rb'data-demo-proof="([^"]+)"', page.content).group(1).decode()
        before = self.state()
        body = dict(username=self.user.username, password=self.password)
        for proof, csrf, expected in ((current, None, 403), (g.document_proof(str(uuid4())), client.cookies["csrftoken"].value, 409)):
            value = {**body, g.FORM_FIELD: proof}
            if csrf:
                value["csrfmiddlewaretoken"] = csrf
            self.assertEqual(client.post("/accounts/login/", value, HTTP_ORIGIN="http://localhost").status_code, expected)
        self.assertEqual(self.state(), before)

    def test_18_native_form_generation_proof_keeps_standard_logout_csrf(self):
        from scripts.demo import generation as g
        proof = self.client.defaults.pop("HTTP_X_DEMO_GENERATION_PROOF")
        response = self.client.post("/accounts/logout/", {g.FORM_FIELD: proof,
            "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    @property
    def state_dir(self):
        return type(self).artifacts
