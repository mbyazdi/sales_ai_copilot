"""Explicit completion contracts; all mutation fixtures belong to test DBs."""
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.middleware.csrf import get_token
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products import tests_catalog
from apps.sales_requests.models import SalesRequest, SalesRequestAcknowledgement, SalesRequestMutationReceipt
from apps.sales_requests.basket import BasketConflict
from apps.sales_requests import submission
from apps.sales_requests.submission import review_request
from apps.sales_requests.tests_submission import SubmissionFixtures
from . import completion
from .models import CustomerAssignment, Salesperson, Visit


class CompletionFixtures(SubmissionFixtures):
    def finish_command(self, **changes):
        return {"customer_code": self.customer.customer_code, "command_uuid": str(uuid4()), **changes}

    def finish(self, command=None, visit=None):
        return self.api.post(reverse("visit-completion-v1", args=[(visit or self.visit).pk]),
                             command or self.finish_command(), format="json")

    def read_finish(self):
        return self.api.get(reverse("visit-completion-v1", args=[self.visit.pk]),
                            {"customer_code": self.customer.customer_code})


class VisitCompletionAPITests(CompletionFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.prepare()

    def test_no_request_needs_no_outcome_or_reason_and_only_records_completion(self):
        before = self.rows()
        response = self.finish()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response["Idempotent-Replayed"], "false")
        self.assertEqual(response.data["visit"]["status"], "COMPLETED")
        self.assertIsNone(response.data["request"])
        self.assertIsNone(response.data["acknowledgement"])
        self.assertTrue(response.data["completed_at"])
        receipt = SalesRequestMutationReceipt.objects.get()
        self.assertEqual(receipt.operation, "COMPLETE_VISIT")
        self.assertIsNone(receipt.sales_request_id)
        self.assertIsNone(receipt.applied_revision)
        after = self.rows()
        self.assertEqual({table for table in before if before[table] != after[table]},
                         {"visits_visit", "sales_requests_salesrequestmutationreceipt"})
        self.assertEqual(receipt.result, {"http_status": 200, "body": response.data})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.updated_at.isoformat(), response.data["completed_at"])

    def test_retained_draft_and_lines_stay_unchanged_and_become_read_only(self):
        self.add()
        before = self.rows()
        response = self.finish()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["request"]["status"], "DRAFT")
        self.assertIsNone(response.data["acknowledgement"])
        after = self.rows()
        self.assertEqual({table for table in before if before[table] != after[table]},
                         {"visits_visit", "sales_requests_salesrequestmutationreceipt"})
        self.assertEqual(self.add().data["code"], "VISIT_NOT_ACTIVE")
        request = SalesRequest.objects.get()
        self.assertIsNone(request.submission_key)
        receipt = SalesRequestMutationReceipt.objects.get(operation="COMPLETE_VISIT")
        self.assertEqual((receipt.sales_request_id, receipt.applied_revision), (request.pk, request.revision))

    def test_submitted_request_gets_one_separate_ack_without_changing_any_snapshots(self):
        self.add()
        submit_command = self.submit_command()
        submitted = self.submit(submit_command)
        self.assertEqual(submitted.status_code, 201)
        before = self.rows()
        response = self.finish()
        self.assertEqual(response.status_code, 200, response.data)
        after = self.rows()
        self.assertEqual({table for table in before if before[table] != after[table]},
                         {"visits_visit", "sales_requests_salesrequestacknowledgement",
                          "sales_requests_salesrequestmutationreceipt"})
        ack = SalesRequestAcknowledgement.objects.get()
        self.assertEqual(ack.actor_id, self.rep.pk)
        self.assertEqual(ack.sales_request_id, SalesRequest.objects.get().pk)
        self.assertEqual(ack.metadata["command_uuid"], response.data["command_uuid"])
        self.assertEqual(response.data["acknowledgement"]["id"], ack.pk)
        self.assertEqual(review_request(self.user, self.customer.customer_code, self.visit.pk), submitted.data)
        self.assertEqual(self.submit(submit_command).data, submitted.data)
        self.assertEqual(self.add().data["code"], "VISIT_NOT_ACTIVE")

    def test_existing_acknowledgement_is_reused_without_rewriting_history(self):
        self.add(); self.submit()
        ack = SalesRequestAcknowledgement.objects.create(
            sales_request=SalesRequest.objects.get(), actor=self.rep, metadata={"previous": "viewed"},
        )
        before = list(SalesRequestAcknowledgement.objects.values())
        self.assertEqual(self.finish().data["acknowledgement"]["id"], ack.pk)
        self.assertEqual(list(SalesRequestAcknowledgement.objects.values()), before)

    def test_same_command_replays_frozen_result_without_any_new_write(self):
        self.add(); self.submit()
        command = self.finish_command()
        original = self.finish(command)
        before = self.rows()
        with patch("apps.visits.completion.timezone.now", side_effect=AssertionError("Replay must not generate time")):
            replay = self.finish(command)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay["Idempotent-Replayed"], "true")
        self.assertEqual(replay.data, original.data)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.read_finish().data["recorded_result"], original.data)

    def test_different_completion_command_cannot_repeat_effects(self):
        self.add(); self.submit(); self.finish()
        before = self.rows()
        response = self.finish()
        self.assertEqual((response.status_code, response.data["code"]), (409, "VISIT_NOT_ACTIVE"))
        self.assertEqual(self.rows(), before)

    def test_same_uuid_different_operation_or_canonical_intent_conflicts(self):
        self.add()
        old = SalesRequestMutationReceipt.objects.get()
        before = self.rows()
        response = self.finish(self.finish_command(command_uuid=str(old.command_uuid)))
        self.assertEqual((response.status_code, response.data["code"]), (409, "COMMAND_CONFLICT"))
        self.assertEqual(self.rows(), before)
        # Persisted evidence of a different canonical intent must never replay.
        key = uuid4()
        SalesRequestMutationReceipt.objects.create(
            visit=self.visit, actor=self.user, command_uuid=key, operation="COMPLETE_VISIT",
            intent_fingerprint="0" * 64, result={"http_status": 200, "body": {"different": True}},
        )
        before = self.rows()
        response = self.finish(self.finish_command(command_uuid=str(key)))
        self.assertEqual(response.data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.rows(), before)

    def test_submission_uuid_cannot_be_reused_as_completion_uuid(self):
        self.add(); self.submit()
        before = self.rows()
        response = self.finish(self.finish_command(command_uuid=str(SalesRequest.objects.get().submission_key)))
        self.assertEqual(response.data["code"], "COMMAND_CONFLICT")
        self.assertEqual(self.rows(), before)

    def test_planned_completed_and_cancelled_are_not_mutated(self):
        for status in ("PLANNED", "COMPLETED", "CANCELLED"):
            Visit.objects.filter(pk=self.visit.pk).update(status=status)
            before = self.rows()
            response = self.finish()
            self.assertEqual((response.status_code, response.data["code"]), (409, "VISIT_NOT_ACTIVE"))
            self.assertEqual(self.rows(), before)

    def test_strict_required_inputs_and_no_invented_completion_fields(self):
        valid = self.finish_command()
        commands = [{}, {"customer_code": valid["customer_code"]}, {"command_uuid": valid["command_uuid"]},
                    {**valid, "command_uuid": "invalid"}, {**valid, "customer_code": None},
                    {**valid, "customer_code": 5}, {**valid, "customer_code": ""},
                    {**valid, "reason": "no_sale"}, {**valid, "status": "COMPLETED"},
                    {**valid, "order_created": True}, []]
        before = self.rows()
        for command in commands:
            response = self.api.post(reverse("visit-completion-v1", args=[self.visit.pk]), command, format="json")
            self.assertEqual((response.status_code, response.data["code"]), (400, "INVALID_INPUT"))
        self.assertEqual(self.rows(), before)

    def test_current_role_owner_assignment_and_customer_are_always_authorized(self):
        before = self.rows()
        for user, expected in ((self.foreign_user, 404), (self.staff, 403), (self.no_profile, 403)):
            self.api.force_authenticate(user)
            self.assertEqual(self.finish().status_code, expected)
            self.assertEqual(self.read_finish().status_code, expected)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.finish(visit=self.foreign_visit).status_code, 404)
        self.assertEqual(self.finish(self.finish_command(customer_code=self.foreign_customer.customer_code)).status_code, 404)
        self.assertEqual(self.finish(self.finish_command(customer_code="missing")).status_code, 404)
        self.assertEqual(self.rows(), before)
        CustomerAssignment.objects.filter(salesperson=self.rep).update(is_active=False)
        before = self.rows()
        self.assertEqual(self.finish().status_code, 404)
        self.assertEqual(self.rows(), before)

    def test_replay_does_not_bypass_revocation_or_stale_actor_role(self):
        command = self.finish_command(); self.finish(command)
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=False)
        self.assertEqual(self.finish(command).status_code, 403)
        Salesperson.objects.filter(pk=self.rep.pk).update(is_active=True)
        get_user_model().objects.filter(pk=self.user.pk).update(is_staff=True)
        self.assertEqual(self.finish(command).status_code, 403)

    def test_completion_evidence_and_acknowledgement_remain_append_only(self):
        self.add(); self.submit(); self.finish()
        before = self.rows()
        for model in (SalesRequestMutationReceipt, SalesRequestAcknowledgement):
            row = model.objects.order_by("pk").last()
            for operation in (lambda: row.save(), lambda: row.delete(),
                              lambda: model.objects.filter(pk=row.pk).delete(),
                              lambda: model.objects.filter(pk=row.pk).update(pk=row.pk),
                              lambda: model.objects.bulk_update([row], ["actor"]),
                              lambda: model.objects.bulk_create([row])):
                with self.assertRaises(ValidationError):
                    operation()
        self.assertEqual(self.rows(), before)

    def test_session_auth_csrf_and_method_restrictions(self):
        url = reverse("visit-completion-v1", args=[self.visit.pk])
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.get(url).status_code, 403)
        self.assertEqual(client.post(url, self.finish_command(), format="json").status_code, 403)
        client.force_login(self.user)
        before = self.rows()
        self.assertEqual(client.post(url, self.finish_command(), format="json").status_code, 403)
        request = RequestFactory().get("/"); token = get_token(request)
        client.cookies["csrftoken"] = request.META["CSRF_COOKIE"]
        self.assertEqual(client.post(url, self.finish_command(), format="json", HTTP_X_CSRFTOKEN="bad").status_code, 403)
        for method in (client.put, client.patch, client.delete):
            self.assertEqual(method(url, self.finish_command(), format="json", HTTP_X_CSRFTOKEN=token).status_code, 405)
        self.assertEqual(self.rows(), before)
        self.assertEqual(client.post(url, self.finish_command(), format="json", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_read_get_head_before_and_after_completion_are_zero_write(self):
        url = reverse("visit-completion-v1", args=[self.visit.pk])
        for completed in (False, True):
            if completed:
                self.finish()
            before = self.rows()
            with CaptureQueriesContext(connection) as queries:
                get = self.read_finish()
                head = self.api.head(url, {"customer_code": self.customer.customer_code})
            self.assertEqual((get.status_code, head.status_code), (200, 200))
            self.assertEqual(get["Cache-Control"], "no-store, private")
            self.assertEqual(get.data["can_complete"], not completed)
            self.assertEqual(get.data["recorded_result"] is not None, completed)
            self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
            self.assertEqual(self.rows(), before)

    def test_legacy_completed_state_is_truthful_and_not_backfilled(self):
        legacy = reverse("visit-complete", args=[self.visit.pk])
        self.assertEqual(self.api.post(legacy, {}, format="json").status_code, 200)
        before = self.rows()
        state = self.read_finish().data
        self.assertEqual(state["visit"]["status"], "COMPLETED")
        self.assertFalse(state["can_complete"])
        self.assertIsNone(state["recorded_result"])
        self.assertEqual(self.finish().data["code"], "VISIT_NOT_ACTIVE")
        self.assertEqual(self.api.post(legacy, {}, format="json").status_code, 400)
        self.assertEqual(self.rows(), before)

    def test_ack_or_receipt_failure_rolls_back_status_and_all_new_evidence(self):
        self.add(); self.submit()
        for model in (SalesRequestAcknowledgement, SalesRequestMutationReceipt):
            before = self.rows()
            with patch.object(model.objects, "create", side_effect=ValidationError("Injected failure")):
                response = self.finish()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.rows(), before)


@skipUnless(connection.vendor == "postgresql", "Real PostgreSQL transactions required")
class VisitCompletionConcurrencyTests(CompletionFixtures, TransactionTestCase):
    def setUp(self):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(type(self))
        self.prepare()

    def race(self, commands):
        gate = Barrier(2)
        def writer(command):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    return completion.complete_visit(user, self.visit.pk,
                                                     {**command, "command_uuid": UUID(command["command_uuid"])})
                except completion.CompletionConflict as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(writer, commands))

    def test_concurrent_identical_commands_replay_one_effect_without_request(self):
        command = self.finish_command()
        results = self.race([command, command])
        self.assertEqual(sorted(result[2] for result in results), [False, True])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(SalesRequestMutationReceipt.objects.count(), 1)
        self.assertEqual(SalesRequest.objects.count(), 0)

    def test_concurrent_different_commands_acknowledge_submitted_request_once(self):
        self.add(); self.submit()
        results = self.race([self.finish_command(), self.finish_command()])
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertIn("VISIT_NOT_ACTIVE", results)
        self.assertEqual(SalesRequestMutationReceipt.objects.filter(operation="COMPLETE_VISIT").count(), 1)
        self.assertEqual(SalesRequestAcknowledgement.objects.count(), 1)
        self.assertEqual(Visit.objects.get(pk=self.visit.pk).status, "COMPLETED")

    def test_completion_and_submission_serialize_with_truthful_final_state(self):
        self.add()
        finish = self.finish_command(); submit = self.submit_command()
        gate = Barrier(2)
        def writer(operation):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    if operation == "finish":
                        return completion.complete_visit(user, self.visit.pk,
                            {**finish, "command_uuid": UUID(finish["command_uuid"])})
                    return submission.submit_request(user, self.visit.pk,
                        {**submit, "command_uuid": UUID(submit["command_uuid"])})
                except (completion.CompletionConflict, BasketConflict) as error:
                    return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, ["finish", "submit"]))
        self.assertIsInstance(results[0], tuple)
        self.assertEqual(Visit.objects.get(pk=self.visit.pk).status, "COMPLETED")
        request = SalesRequest.objects.get()
        self.assertEqual(SalesRequestAcknowledgement.objects.count(), int(request.status == "SUBMITTED"))
        self.assertEqual(SalesRequestMutationReceipt.objects.filter(operation="COMPLETE_VISIT").count(), 1)
        if request.status == "DRAFT":
            self.assertEqual(results[1], "VISIT_NOT_ACTIVE")
            self.assertIsNone(request.submitted_at)
        else:
            self.assertIsInstance(results[1], tuple)

    def test_replay_after_fresh_process_uses_committed_evidence(self):
        self.add(); self.submit()
        command = self.finish_command(); original = self.finish(command)
        self.assertEqual(original.status_code, 200)
        before = self.rows()
        database = connection.settings_dict.copy()
        identity_sql = ("SELECT current_database(), oid, inet_server_addr()::text, "
                        "inet_server_port(), current_user FROM pg_database WHERE datname = current_database()")
        with connection.cursor() as cursor:
            cursor.execute(identity_sql); identity = list(cursor.fetchone())
        self.assertEqual(identity[0], database["NAME"])
        self.assertNotIn(database["NAME"], {"sales_ai_db", "postgres", "template0", "template1"})
        script = '''import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "venv/Lib/site-packages"))
data = json.load(sys.stdin)
database, identity = data["database"], data["identity"]
assert database["ENGINE"] == "django.db.backends.postgresql"
assert all(database.get(k) for k in ("NAME", "HOST", "PORT", "USER"))
assert database["NAME"] not in {"sales_ai_db", "postgres", "template0", "template1"}
assert database["NAME"] == identity[0] and database["USER"] == identity[4]
assert identity[1] and identity[2] and identity[3]
assert set(database.get("OPTIONS", {})) <= {"sslmode", "connect_timeout"}
from django.conf import settings
settings.DATABASES = {"default": database}
from django.db.backends.postgresql.base import DatabaseWrapper
original_connect = DatabaseWrapper.get_new_connection
def verified_connect(self, params):
    assert self.alias == "default" and self.settings_dict == database
    for parameter, field in (("dbname", "NAME"), ("host", "HOST"), ("port", "PORT"),
                             ("user", "USER"), ("password", "PASSWORD")):
        assert str(params.get(parameter, "")) == str(database.get(field, ""))
    assert not ({"service", "hostaddr"} & params.keys())
    conn = original_connect(self, params)
    try:
        with conn.cursor() as cursor:
            cursor.execute(data["identity_sql"])
            assert list(cursor.fetchone()) == identity
        conn.rollback()
    except BaseException:
        conn.close()
        raise
    return conn
DatabaseWrapper.get_new_connection = verified_connect
import django
django.setup()
from django.contrib.auth import get_user_model
from apps.visits.completion import complete_visit
from uuid import UUID
data["command"]["command_uuid"] = UUID(data["command"]["command_uuid"])
body, status, replayed = complete_visit(get_user_model().objects.get(pk=data["user"]), data["visit"], data["command"])
print(json.dumps({"body": body, "status": status, "replayed": replayed}))
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
            input=json.dumps({"database": database, "identity": identity, "identity_sql": identity_sql,
                              "user": self.user.pk, "visit": self.visit.pk, "command": command}),
            text=True, encoding="utf-8", capture_output=True,
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "sales_ai_copilot.settings"}, timeout=40)
        self.assertEqual(result.returncode, 0, "Isolated fresh-process completion replay failed")
        replay = json.loads(result.stdout)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["status"], 200)
        self.assertEqual(replay["body"], original.data)
        self.assertEqual(self.rows(), before)
