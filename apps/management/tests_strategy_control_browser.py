"""Real Edge acceptance, run ONLY through the guarded disposable PG runner."""
from datetime import timedelta
import json
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from socketserver import ThreadingMixIn
import subprocess
from threading import Thread
from unittest import skipUnless
from uuid import uuid4
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from django.conf import settings
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from django.db import connection, connections
from django.test import override_settings

from apps.products.models import Brand, Category, Product
from apps.promotions.models import Promotion
from .models import StrategyPolicyEvent, StrategyPolicyVersion, StrategyPolicy
from .models import StrategyComparison
from .strategy_serialization import fingerprint
from .tests_strategy_api import APIFixture
from .tests_strategy_evaluator import DAY


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass  # Never log submitted values, passwords, sessions or query strings.


class BrowserServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    block_on_close = True


@skipUnless(connection.vendor == "postgresql" and os.environ.get("STRATEGY_BROWSER_ACCEPTANCE")=="1",
            "Explicit disposable PostgreSQL browser execution required")
class StrategyControlBrowserTests(APIFixture):
    def source_digest(self):
        excluded={StrategyPolicy,StrategyPolicyVersion,StrategyPolicyEvent,StrategyComparison}
        result={}
        for model in apps.get_models():
            if model in excluded or model._meta.label_lower=="sessions.session":
                continue
            rows=list(model.objects.order_by("pk").values())
            if model==get_user_model():
                for row in rows: row.pop("last_login",None)
            result[model._meta.label_lower]=json.dumps(rows,default=str,sort_keys=True)
        return fingerprint(result)

    def test_real_browser_interactions_and_durable_recovery(self):
        self.assertTrue(os.environ.get("STRATEGY_BROWSER_ACCEPTANCE") == "1", "Explicit browser execution required")
        db = connections["default"]
        runtime = settings.STRATEGY_PUBLICATION_RUNTIME
        self.assertEqual(db.settings_dict["NAME"], runtime["NAME"])
        self.assertTrue(runtime["NAME"].startswith("test_mc1_"))  # Driver also attests exact UUID/OID/marker.
        self.assertFalse(settings.DATABASES["default"].get("ATOMIC_REQUESTS", False))
        self.assertFalse(hasattr(settings, "DEMO_GENERATION_CONFIG"))
        Brand.objects.bulk_create([Brand(id=1000+i, code=f"F2-B{i}", name=f"برند آزمایشی {i}") for i in range(105)])
        Category.objects.bulk_create([Category(id=2000+i, code=f"F2-C{i}", name=f"گروه آزمایشی {i}") for i in range(105)])
        Product.objects.bulk_create([Product(id=3000+i, product_code=f"F2-P{i}", name=f"محصول آزمایشی {i}",
                                            brand_id=11, category_id=21, product_group="HOME_APPLIANCE") for i in range(105)])
        Promotion.objects.bulk_create([Promotion(id=4000+i,code=f"F2-PR{i}",name=f"ترویج آزمایشی {i}",promotion_type="PERCENTAGE",
            start_date=DAY,end_date=DAY+timedelta(days=10),discount_percent=5) for i in range(105)])
        Product.objects.create(id=3900,product_code="F2-INACTIVE",name="مرجع غیرفعال آزمایشی",brand_id=11,category_id=21,
                               product_group="HOME_APPLIANCE",is_active=False)
        nonstaff_password=secrets.token_urlsafe(32)
        nonstaff = get_user_model().objects.create_user(username="f2-nonstaff", password=nonstaff_password)
        before = self.source_digest()
        root=Path(__file__).resolve().parents[2]
        output=root/"venv"/"me4b-f2-artifacts"/uuid4().hex
        output.mkdir(parents=True)
        attestation_key=secrets.token_urlsafe(48)
        application=StaticFilesHandler(get_wsgi_application())
        def fixture_application(environ,start_response):
            if environ.get("PATH_INFO")=="/__f2_fixture_identity__/":
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT current_database(),current_user")
                    database,role=cursor.fetchone()
                value={"database":database,"role":role}
                encoded=json.dumps(value,sort_keys=True,separators=(",",":")).encode()
                value["attestation"]=hmac.new(attestation_key.encode(),encoded,hashlib.sha256).hexdigest()
                start_response("200 OK",[("Content-Type","application/json"),("Cache-Control","no-store")])
                connections["default"].close()
                return [json.dumps(value).encode()]
            return application(environ,start_response)
        server=make_server("127.0.0.1",0,fixture_application,server_class=BrowserServer,handler_class=QuietHandler)
        port=server.server_port
        prior={k:db.settings_dict[k] for k in ("USER","PASSWORD")}
        db.close()
        db.settings_dict.update({k:runtime[k] for k in prior})
        worker=None
        try:
            with override_settings(ALLOWED_HOSTS=["localhost","testserver"],SESSION_COOKIE_NAME="f2_session_"+uuid4().hex,
                                   CSRF_COOKIE_NAME="f2_csrf_"+uuid4().hex,CSRF_TRUSTED_ORIGINS=[f"http://localhost:{port}"],DEBUG=False):
                worker=Thread(target=server.serve_forever,daemon=True);worker.start()
                with db.cursor() as cursor:
                    cursor.execute("SELECT current_database(),current_user")
                    self.assertEqual(cursor.fetchone(),(runtime["NAME"],runtime["USER"]))
                payload={"base":f"http://localhost:{port}","database":runtime["NAME"],"username":self.manager.username,
                         "runtime":runtime["USER"],"attestation_key":attestation_key,
                         "password":self.password,"nonstaff":nonstaff.username,"nonstaff_password":nonstaff_password,"output":str(output)}
                # Random disposable credentials travel over stdin, never CLI/env/logs or files.
                result=subprocess.run(["node",str(root/"scripts"/"verify_strategy_control_browser.cjs")],input=json.dumps(payload),
                                      text=True,capture_output=True,cwd=root,timeout=240)
                print(result.stdout)
                self.assertEqual(result.returncode,0,"Browser acceptance failed; inspect redacted browser report. "+result.stderr[-1200:])
                proof=json.loads((output/"browser-proof.json").read_text(encoding="utf-8"))
                self.assertTrue(proof["passed"])
                self.assertEqual(proof["browser_errors"],[])
                with db.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM django_session")
                    self.assertGreater(cursor.fetchone()[0],0)
        finally:
            if worker:
                server.shutdown();worker.join(timeout=10)
            server.server_close()
            db.close();db.settings_dict.update(prior)
        self.assertEqual(self.source_digest(),before)
        self.assertGreaterEqual(StrategyPolicyVersion.objects.count(),3)
        self.assertEqual(StrategyPolicyEvent.objects.filter(operation="SAVE_DRAFT").count(),StrategyPolicyVersion.objects.count())
        self.assertIsNone(StrategyPolicy.objects.get(pk=1).active_version_id)
        print("Browser fixture evidence:",output)
