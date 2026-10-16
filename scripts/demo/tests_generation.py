"""Generation safety tests: memory sessions/views only; no DB mutation probes."""
import copy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import *


class MemorySession(dict):
    def cycle_key(self): self.cycled=True
    def flush(self): self.clear()


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.demo import generation as g
        cls.g=g;cls.profile=load_profile();cls.current=cls.profile["identity"]
        cls.other="00000000-0000-0000-0000-000000000002"

    def setUp(self):
        self.calls=[]
        self.guard=self.g.DemoGenerationMiddleware(self.view)

    def view(self,request):
        from django.http import HttpResponse
        from django.middleware.csrf import CsrfViewMiddleware
        self.calls.append(request.body if request.content_type=="application/json" else dict(request.POST))
        # Exercise the real CSRF validator as the Django handler would.
        csrf=CsrfViewMiddleware(lambda r:HttpResponse("ok"));csrf.process_request(request)
        failure=csrf.process_view(request,lambda r:None,(),{})
        if failure:return failure
        return HttpResponse("<html><head></head><body>ok</body></html>")

    def request(self,proof=None,session=None,path="/api/visits/v1/visits/1/completion/",authenticated=True):
        from django.test import RequestFactory
        from django.middleware.csrf import get_token
        request=RequestFactory().post(path,json.dumps({"command_uuid":"4e635b90-2c75-4c7b-9730-65374ec02d18","customer_code":"C0003"}),
            content_type="application/json",HTTP_HOST="localhost:8900",HTTP_ORIGIN="http://localhost:8900")
        masked=get_token(request);request.COOKIES["csrftoken"]=request.META["CSRF_COOKIE"]
        request.META["HTTP_X_CSRFTOKEN"]=masked
        if proof is not None:request.META[self.g.PROOF_HEADER]=proof
        request.session=MemorySession({self.g.SESSION_KEY:self.current} if session is None else session)
        request.user=SimpleNamespace(is_authenticated=authenticated)
        return request

    def test_current_generation_mutation_and_same_generation_retry(self):
        token=self.g.document_proof(self.current)
        first=self.request(token);wire=first.body
        self.assertEqual(self.guard(first).status_code,200)
        second=self.request(token)
        self.assertEqual(self.guard(second).status_code,200)
        self.assertEqual(self.calls,[wire,wire])

    def test_stale_session_rejected_even_with_new_document_proof(self):
        response=self.guard(self.request(self.g.document_proof(self.current),{self.g.SESSION_KEY:self.other}))
        self.assertEqual(response.status_code,403);self.assertEqual(self.calls,[])

    def test_old_pending_proof_rejected_even_with_new_cookies_and_session(self):
        response=self.guard(self.request(self.g.document_proof(self.other)))
        self.assertEqual(response.status_code,409);self.assertEqual(self.calls,[])

    def test_missing_unsigned_or_tampered_pending_fails(self):
        for value in (None,"",self.current,self.g.document_proof(self.current)+"x"):
            with self.subTest(value_present=bool(value)):
                self.assertEqual(self.guard(self.request(value)).status_code,409)
        self.assertEqual(self.calls,[])

    def test_legacy_unbound_session_requires_login(self):
        self.assertEqual(self.guard(self.request(self.g.document_proof(self.current),{})).status_code,403)
        self.assertEqual(self.calls,[])

    def test_csrf_still_required_with_current_generation_proof(self):
        request=self.request(self.g.document_proof(self.current));request.META.pop("HTTP_X_CSRFTOKEN")
        self.assertEqual(self.guard(request).status_code,403)

    def test_normal_django_login_binds_memory_session(self):
        from django.contrib.auth import login
        request=self.request(self.g.document_proof(self.current),{},path="/accounts/login/",authenticated=False)
        saved=[]
        user=SimpleNamespace(pk=900001,backend="django.contrib.auth.backends.ModelBackend",get_session_auth_hash=lambda:"memory-only-hash",
            _meta=SimpleNamespace(pk=SimpleNamespace(value_to_string=lambda u:str(u.pk))),save=lambda **kwargs:saved.append(kwargs))
        def normal_login(r):
            login(r,user)
            from django.http import HttpResponse
            return HttpResponse("ok")
        response=self.g.DemoGenerationMiddleware(normal_login)(request)
        self.assertEqual(response.status_code,200)
        self.assertEqual(request.session[self.g.SESSION_KEY],self.current)
        self.assertEqual(request.session["_auth_user_id"],"900001")
        self.assertTrue(saved)  # Normal last_login signal ran only on a memory object.

    def test_native_form_proof_is_stripped_but_csrf_is_preserved(self):
        from django.test import RequestFactory
        from django.middleware.csrf import get_token
        request=RequestFactory().post('/accounts/login/',{'username':'test-only'},HTTP_HOST='localhost:8900',HTTP_ORIGIN='http://localhost:8900')
        token=get_token(request);request.COOKIES['csrftoken']=request.META['CSRF_COOKIE']
        fields=request.POST.copy();fields['csrfmiddlewaretoken']=token;fields[self.g.FORM_FIELD]=self.g.document_proof(self.current)
        request.POST=fields;request.session=MemorySession();request.user=SimpleNamespace(is_authenticated=False)
        self.assertEqual(self.guard(request).status_code,200)
        self.assertNotIn(self.g.FORM_FIELD,request.POST)
        self.assertEqual(request.POST['csrfmiddlewaretoken'],token)

    def test_html_transport_bootstrap_has_no_visible_ui_change(self):
        response=self.guard(self.request(self.g.document_proof(self.current)))
        self.assertIn(b'data-demo-generation=',response.content)
        self.assertIn(b'/__demo_infrastructure__/generation.js',response.content)
        self.assertIn(b'<body>ok</body>',response.content)

    def test_uncertain_registry_fails_before_view(self):
        with patch.object(self.g,"active_generation",side_effect=self.g.GenerationRefused("partial")):
            self.assertEqual(self.guard(self.request()).status_code,503)
        self.assertEqual(self.calls,[])

    def test_registry_pins_exact_generation_database_endpoint_and_container(self):
        registry=self.g.initial_registry(self.profile)
        for key,value in (("database","sales_ai_db"),("database_port",5432),("container","sales-ai-postgres"),
                          ("identity",self.other),("database_oid",self.profile["database_oid"]+1)):
            with self.subTest(key=key),self.assertRaises(self.g.GenerationRefused):
                self.g.validate_registry(registry,self.profile,{**self.profile,key:value})

    def test_all_maintenance_phases_reject_runtime_requests(self):
        for phase in self.g.PHASES:
            registry=self.g.initial_registry(self.profile);registry.update(phase=phase,maintenance="operation-1")
            with self.subTest(phase=phase),self.assertRaises(self.g.GenerationRefused):
                self.g.validate_registry(registry,self.profile,self.profile)

    def journal(self):
        evidence={"exact_identity":True,"independent_validation":True,"owner_approval":True,"old_profile":True,"old_identity":True,
            "retained_healthy_generation":True,"rollback_grants":True,"verified_process":True,"drained_requests":True,
            "verified_old_role_fence":True,"recorded_profile_selection":True,"normal_auth":True,"generation_fence":True,
            "read_only_reconciliation":True,"explicit_activation_approval":True,"previous_healthy_retained":True,
            "retained_healthy_generations":[self.current]}
        entries=[]
        for i,phase in enumerate(self.g.PHASES):
            row=dict(sequence=i,phase=phase,old_generation=self.current,candidate_generation=self.other,
                     previous_sha256=entries[-1]["sha256"] if entries else None,evidence=dict(evidence))
            row["sha256"]=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
            entries.append(row)
        return entries

    def test_every_journal_interruption_remains_fail_closed(self):
        entries=self.journal()
        for i in range(len(entries)+1):
            result=self.g.validate_journal(entries[:i],self.current,self.other)
            self.assertFalse(result["mutations_allowed"]);self.assertFalse(result["execution_available"])
            self.assertFalse(result["multi_step_atomic"])

    def test_journal_reordering_tampering_or_missing_retained_generation_rejected(self):
        for mode in ("order","tamper","retention"):
            entries=self.journal()
            if mode=="order":entries[2],entries[3]=entries[3],entries[2]
            elif mode=="tamper":entries[1]["candidate_generation"]=self.current
            else:entries[-1]["evidence"]["previous_healthy_retained"]=False
            with self.subTest(mode=mode),self.assertRaises(self.g.GenerationRefused):self.g.validate_journal(entries,self.current,self.other)


if __name__=="__main__":
    profile=load_profile();verify_container(profile);configure_django(profile,DEFAULT_STATE)
    from django.db import connection
    require(connection.connection is None,"Unexpected early connection")
    connection.settings_dict["OPTIONS"]["options"]+=" -c default_transaction_read_only=on"
    check_schema(profile)
    unittest.main(verbosity=2)
