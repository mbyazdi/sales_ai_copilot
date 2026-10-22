"""Explicit disposable management TEST profile; never the persistent Demo launcher.

No automatic migrations/seeding at startup. Provision/cleanup are operator commands.
Runtime routes are limited to normal login/logout, strategy APIs and static files.
"""
import argparse
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT / "venv/management-preview-live"
PORT = 8901
HEALTH = "/__management_test_preview__/"
PREFIX = "test_me01_"
SOURCE_TABLES = (
    "auth_user", "customers_customer", "customers_customergrade", "visits_salesperson",
    "visits_customerassignment", "products_product", "products_brand", "products_category",
    "products_productdemoprice", "inventory_inventory", "recommendations_customerrecommendation",
    "targets_salestarget", "promotions_promotion", "promotions_promotionproduct",
    "promotions_promotion_customer_grades", "management_strategypolicy",
    "management_strategypolicyversion", "management_strategycomparison", "management_strategypolicyevent",
    "django_migrations",
)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def fingerprint():
    paths = [ROOT / "sales_ai_copilot/settings.py", ROOT / "sales_ai_copilot/database.py",
             ROOT / "sales_ai_copilot/urls.py", Path(__file__), Path(__file__).with_name("management_preview_account.py")]
    paths += [p for p in (ROOT / "apps/management").rglob("*.py")
              if not p.name.startswith(("tests", "verify"))]
    paths += [ROOT / "templates/management/strategy_comparison.html", ROOT / "static/management/css/strategy.css",
              ROOT / "static/management/js/strategy_comparison.js", ROOT / "static/management/js/strategy_comparison_create.js",
              ROOT / "templates/management/_strategy_comparison_create.html",
              ROOT / "templates/management/strategy_overview.html", ROOT / "static/management/css/strategy_overview.css",
              ROOT / "static/management/js/strategy_overview.js"]
    paths += [ROOT / "templates/management/strategy_control.html", ROOT / "static/management/css/strategy_control.css",
              ROOT / "static/management/js/strategy_control.js"]
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(str(path.relative_to(ROOT)).encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def valid_profile(p):
    suffix = UUID(p["identity"]).hex
    require(p["kind"] == "MANAGEMENT_TEST_PREVIEW_V1" and p["database"] == PREFIX + suffix,
            "Not an exact disposable management preview identity.")
    require(p["owner"] == "me01_owner_" + suffix and p["runtime"] == "me01_runtime_" + suffix,
            "Independent preview roles mismatch.")
    require(p["host"] == "127.0.0.1" and p["port"] == 5433 and p["application_port"] == PORT,
            "Preview endpoint mismatch.")
    require(type(p["oid"]) is int and p["oid"] > 0 and p["marker"] == "management-test-preview:" + suffix,
            "Preview OID/marker missing.")


def load(state, *, check_source=True):
    p = json.loads((state / "profile.json").read_text(encoding="utf-8"))
    key = json.loads((state / "runtime.json").read_text(encoding="utf-8"))
    require(hmac.compare_digest((state / "profile.hmac").read_text().strip(),
            hmac.new(key["control"].encode(), encoded(p), hashlib.sha256).hexdigest()), "Profile evidence mismatch.")
    valid_profile(p)
    if check_source:
        require(p["source_sha256"] == fingerprint(), "Preview source changed; explicitly rebuild disposable preview.")
    return p, key


def params_allowed(params, p, role):
    require(params.get("dbname") == p["database"] and params.get("user") == role
            and params.get("host") == p["host"] and str(params.get("port")) == str(p["port"])
            and not any(k in params for k in ("service", "hostaddr", "passfile")),
            "Connection refused before network: exact preview endpoint/database/role required.")


def identity(raw, p, role):
    row = raw.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database'),"
                      "inet_server_port() FROM pg_database d WHERE datname=current_database()").fetchone()
    require(row == (p["database"], role, p["oid"], p["marker"], 5432), "Preview live identity mismatch.")
    raw.rollback()


def configure(p, credentials, role):
    """A separate base TEST profile, not a switch disabling any Demo middleware."""
    valid_profile(p)
    for key in list(os.environ):
        if key.startswith(("PG", "POSTGRES_")) or key in {"DATABASE_URL", "DB_ENGINE", "DJANGO_SETTINGS_MODULE"}:
            os.environ.pop(key, None)
    os.environ["DJANGO_SETTINGS_MODULE"] = "sales_ai_copilot.settings"
    import psycopg
    original = psycopg.connect

    def guarded(conninfo="", **kwargs):
        require(not conninfo, "Connection strings/services prohibited in preview.")
        params_allowed(kwargs, p, role)
        raw = original(**kwargs)
        try:
            identity(raw, p, role)
            return raw
        except BaseException:
            raw.close(); raise

    psycopg.connect = guarded
    from django.conf import settings
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": p["database"],
        "USER": role, "PASSWORD": credentials["password"], "HOST": p["host"], "PORT": p["port"],
        "CONN_MAX_AGE": 0, "ATOMIC_REQUESTS": False,
        "OPTIONS": {"connect_timeout": 5, "options": "-c statement_timeout=30000 -c lock_timeout=5000"}}}
    settings.SECRET_KEY = credentials["django_key"]
    settings.SECRET_KEY_FALLBACKS = []
    settings.DEBUG = False
    settings.ALLOWED_HOSTS = ["localhost"]
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.db"
    suffix = p["identity"].replace("-", "")
    settings.SESSION_COOKIE_NAME = "management_test_session_" + suffix
    settings.CSRF_COOKIE_NAME = "management_test_csrf_" + suffix
    settings.SESSION_COOKIE_HTTPONLY = True
    settings.SESSION_COOKIE_SAMESITE = "Strict"
    settings.CSRF_COOKIE_SAMESITE = "Strict"
    settings.CSRF_TRUSTED_ORIGINS = [f"http://localhost:{PORT}"]
    settings.LOGIN_REDIRECT_URL = "/api/management/v1/strategy/overview/"
    require(not any("scripts.demo" in item for item in settings.MIDDLEWARE), "Unexpected Demo middleware/profile.")
    require("django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
            and "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE,
            "Normal authentication/CSRF middleware required.")
    from django.db.backends.sqlite3.base import DatabaseWrapper
    def no_sqlite(*args, **kwargs):
        raise RuntimeError("SQLite is prohibited in management preview.")
    DatabaseWrapper.get_new_connection = no_sqlite
    import django
    django.setup()


def schema_ready(p):
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(connection)
    loader.check_consistent_history(connection)
    keys = sorted([list(k) for k in loader.disk_migrations])
    require(set(loader.disk_migrations) == set(loader.applied_migrations) and keys == p["migration_keys"],
            "Preview migration drift; startup never migrates.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        require(cursor.fetchone() == (False,)*5, "Unsafe preview runtime role.")
        cursor.execute("SELECT has_schema_privilege(current_user,'public','CREATE')")
        require(cursor.fetchone() == (False,), "Runtime schema creation is prohibited.")
        for table in SOURCE_TABLES:
            cursor.execute("SELECT has_table_privilege(current_user,%s,'SELECT')", [table])
            require(cursor.fetchone() == (True,), "Missing preview read privilege.")
        for table in SOURCE_TABLES:
            if table in ("auth_user", "management_strategypolicy"):
                continue
            cursor.execute("SELECT has_any_column_privilege(current_user,%s,'UPDATE'),has_table_privilege(current_user,%s,'DELETE')", [table, table])
            require(cursor.fetchone() == (False, False), "Unsafe reference/history write privilege.")


def seed(day, accounts, *, manager_hash=None):
    """Repository-owned synthetic-only fixtures; no imports from private artifacts."""
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from apps.customers.models import Customer, CustomerGrade
    from apps.products.models import Brand, Category, Product, ProductDemoPrice
    from apps.inventory.models import Inventory
    from apps.visits.models import CustomerAssignment, Salesperson
    from apps.recommendations.models import CustomerRecommendation
    from apps.promotions.models import Promotion, PromotionProduct
    from apps.targets.models import SalesTarget
    day = date.fromisoformat(day)
    with transaction.atomic():
        users = {}
        for name, data in accounts.items():
            users[name] = get_user_model().objects.create_user(username=data["username"], password=data["password"],
                                                              is_staff=name == "manager")
            if name == "manager" and manager_hash is not None:
                users[name].password = manager_hash
                users[name].save(update_fields=["password"])
        grade = CustomerGrade.objects.create(code="A", name="گروه آزمایشی الف")
        customer = Customer.objects.create(customer_code="ME01-C", name="مشتری ساختگی مدیریت", grade=grade)
        rep = Salesperson.objects.create(employee_code="ME01-SP", first_name="فروشنده", last_name="آزمایشی", user=users["salesperson"])
        CustomerAssignment.objects.create(customer=customer, salesperson=rep, start_date=day)
        brand = Brand.objects.create(code="ME01-B", name="برند ساختگی")
        category = Category.objects.create(code="ME01-CAT", name="دسته ساختگی")
        products = []
        for position, score in enumerate((40, 90, 70, 60), 1):
            product = Product.objects.create(product_code=f"ME01-P{position}", name=f"محصول ساختگی {position}",
                brand=brand, category=category, product_group="HOME_APPLIANCE")
            products.append(product)
            Inventory.objects.create(product=product, available_quantity=12, reserved_quantity=2)
            ProductDemoPrice.objects.create(product=product, base_price=Decimal(100), currency="TOMAN",
                                           source="SYNTHETIC_TEST_ONLY", source_version="ME01_V1")
            CustomerRecommendation.objects.create(customer=customer, product=product, rank=position, score=score,
                reason="پیشنهاد ذخیره‌شدهٔ ساختگی", recommendation_type="CATEGORY", explanation_snapshot={"synthetic": True})
        SalesTarget.objects.create(salesperson=rep, product=products[2], scope_type="PRODUCT", target_unit="QUANTITY",
            period_start=day, period_end=day, target_value=100, actual_value=50)
        promo = Promotion.objects.create(code="ME01-PROMO", name="تأکید ترویجی ساختگی", promotion_type="PERCENTAGE",
            start_date=day, end_date=day, minimum_quantity=1)
        promo.customer_grades.add(grade)
        PromotionProduct.objects.create(promotion=promo, product=products[2])
    return {"customer_id": customer.pk, "salesperson_id": rep.pk, "product_ids": [p.pk for p in products],
            "promotion_id": promo.pk, "evaluation_date": day.isoformat()}


def protect(state):
    state.mkdir(parents=True, exist_ok=False)
    if os.name == "nt":
        row = next(csv.reader(io.StringIO(subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True))))
        subprocess.run(["icacls", str(state), "/inheritance:r", "/grant:r", f"*{row[1]}:(OI)(CI)F",
                        "*S-1-5-18:(OI)(CI)F"], check=True, capture_output=True)
    else:
        state.chmod(0o700)


def operator():
    # Maintenance credential only; never copied into runtime profile or server environment.
    from scripts.demo.common import DEFAULT_STATE, load_profile, verify_container
    verify_container(load_profile())
    import psycopg
    for key in list(os.environ):
        if key.startswith("PG"):
            os.environ.pop(key, None)
    raw = psycopg.connect(host="127.0.0.1", port=5433, dbname="postgres", user="sales_ai_demo_bootstrap",
        password=(DEFAULT_STATE / "credentials/bootstrap-password.txt").read_text(encoding="utf-8").strip(),
        autocommit=True, connect_timeout=5)
    require(raw.execute("SELECT current_database(),current_user,inet_server_port()").fetchone()
            == ("postgres", "sales_ai_demo_bootstrap", 5432), "Operator identity mismatch.")
    return raw


def provision(state, *, check_port=True):
    require(not state.exists(), "State already exists; never overwrite or silently reseed.")
    if check_port:
        port_socket = socket.socket()
        if os.name == "nt":
            port_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            port_socket.bind(("127.0.0.1", PORT))
        finally:
            port_socket.close()
    from scripts.management_preview_account import read_stable
    stable = read_stable()  # A rebuild must not silently generate different UAT credentials.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from psycopg import sql
    identity_id = uuid4()
    suffix = identity_id.hex
    p = dict(kind="MANAGEMENT_TEST_PREVIEW_V1", identity=str(identity_id), database=PREFIX+suffix,
        owner="me01_owner_"+suffix, runtime="me01_runtime_"+suffix, host="127.0.0.1", port=5433,
        application_port=PORT, marker="management-test-preview:"+suffix, source_sha256=fingerprint())
    runtime = dict(password=secrets.token_urlsafe(48), django_key=secrets.token_urlsafe(64), control=secrets.token_urlsafe(48))
    owner = dict(password=secrets.token_urlsafe(48), django_key=runtime["django_key"])
    accounts = {name: {"username": "me01-"+name, "password": secrets.token_urlsafe(24)}
                for name in ("manager", "salesperson", "unauthorized")}
    if stable is not None:
        accounts["manager"] = {"username": "manager", "password": None, "credential_source": "PROTECTED_UAT_HASH"}
    protect(state)
    # Durable recovery evidence is written before any operator DDL.
    dump(state / "runtime.json", runtime); dump(state / "owner.json", owner); dump(state / "accounts.json", accounts)
    dump(state / "creation.json", p)
    with operator() as control:
        for role, credential in ((p["owner"], owner), (p["runtime"], runtime)):
            control.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}")
                .format(sql.Identifier(role), sql.Literal(credential["password"])))
        control.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'")
                        .format(sql.Identifier(p["database"]), sql.Identifier(p["owner"])))
        p["oid"] = control.execute("SELECT oid FROM pg_database WHERE datname=%s", [p["database"]]).fetchone()[0]
        control.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(p["database"]), sql.Literal(p["marker"])))
        control.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(p["database"])))
        control.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(p["database"]), sql.Identifier(p["runtime"])))
    dump(state / "creation.json", p)
    configure(p, owner, p["owner"])
    from django.core.management import call_command
    from django.db import connection, connections
    from django.db.migrations.loader import MigrationLoader
    call_command("migrate", interactive=False, verbosity=0)
    p["migration_keys"] = sorted([list(k) for k in MigrationLoader(connection).applied_migrations])
    p["fixture"] = seed(datetime.now(ZoneInfo("Asia/Tehran")).date().isoformat(), accounts,
                        manager_hash=stable["password_hash"] if stable else None)
    with connection.cursor() as c:
        c.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        c.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(p["runtime"])))
        for table in SOURCE_TABLES:
            c.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(p["runtime"])))
        c.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON django_session TO {}").format(sql.Identifier(p["runtime"])))
        c.execute(sql.SQL("GRANT UPDATE(last_login) ON auth_user TO {}").format(sql.Identifier(p["runtime"])))
        c.execute(sql.SQL("GRANT INSERT,UPDATE(revision,active_version_id,draft_version_id) ON management_strategypolicy TO {}")
                  .format(sql.Identifier(p["runtime"])))
        for table in ("management_strategypolicyversion", "management_strategycomparison", "management_strategypolicyevent"):
            c.execute(sql.SQL("GRANT INSERT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(p["runtime"])))
            c.execute("SELECT pg_get_serial_sequence(%s,'id')", [table]); sequence = c.fetchone()[0]
            c.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}")
                      .format(sql.Identifier(*sequence.split(".")), sql.Identifier(p["runtime"])))
    connections.close_all()
    dump(state / "profile.json", p)
    (state / "profile.hmac").write_text(hmac.new(runtime["control"].encode(), encoded(p), hashlib.sha256).hexdigest())
    print(json.dumps({"provisioned": p["database"], "migrations": len(p["migration_keys"]), "credentials": str(state / "accounts.json")}))


def health(p):
    from urllib.request import build_opener, ProxyHandler
    with build_opener(ProxyHandler({})).open(f"http://localhost:{PORT}"+HEALTH, timeout=4) as response:
        value = json.load(response)
    require(value["identity"] == p["identity"] and value["database"] == p["database"]
            and value["source_sha256"] == p["source_sha256"], "Listener identity mismatch.")
    return value


def verified_health(p, runtime):
    value = health(p)
    signature = value.pop("attestation", "")
    require(hmac.compare_digest(signature, hmac.new(runtime["control"].encode(), encoded(value), hashlib.sha256).hexdigest()),
            "Preview listener attestation invalid.")
    return value


def serve(state):
    p, runtime = load(state)
    configure(p, runtime, p["runtime"])
    schema_ready(p)
    from django.core.management import call_command
    call_command("check")
    from django.core.handlers.wsgi import WSGIHandler
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
    from socketserver import ThreadingMixIn
    application = StaticFilesHandler(WSGIHandler())
    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = False  # server_close waits for admitted HTTP workers, including session persistence.
        allow_reuse_address = False
    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass  # Never log query strings, submitted payloads or authentication material.
    server = None
    def wrapped(environ, start_response):
        path = environ.get("PATH_INFO", "")
        allowed_host = environ.get("HTTP_HOST") == f"localhost:{PORT}" and environ.get("REMOTE_ADDR") == "127.0.0.1"
        if allowed_host and path in (HEALTH, HEALTH+"stop/"):
            if path.endswith("stop/"):
                token = environ.get("HTTP_X_MANAGEMENT_PREVIEW_CONTROL", "")
                require(environ["REQUEST_METHOD"] == "POST" and hmac.compare_digest(token, runtime["control"]), "Control denied.")
                threading.Thread(target=server.shutdown, daemon=True).start()
            value = {"identity": p["identity"], "database": p["database"], "source_sha256": p["source_sha256"],
                     "pid": os.getpid(), "profile": p["kind"], "outer_atomic": False}
            value["attestation"] = hmac.new(runtime["control"].encode(), encoded(value), hashlib.sha256).hexdigest()
            start_response("200 OK", [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
            return [encoded(value)]
        import re
        comparison_page = bool(re.fullmatch(r"/management/strategy/comparisons/[1-9][0-9]*/", path))
        allowed_path = comparison_page or path in ("/management/strategy/", "/management/strategy/control/", "/management/strategy/comparisons/", "/accounts/login/", "/accounts/logout/") or path.startswith(("/api/management/v1/strategy/", "/static/"))
        if not allowed_host or not allowed_path:
            start_response("404 Not Found", [("Content-Type", "text/plain")]); return [b"Not found"]
        return application(environ, start_response)
    with make_server("127.0.0.1", PORT, wrapped, server_class=Server, handler_class=Quiet) as server:
        dump(state / "listener.json", {"pid": os.getpid(), "identity": p["identity"]})
        print(f"Management TEST preview: http://localhost:{PORT}/accounts/login/", flush=True)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["provision", "start", "serve", "status", "stop", "cleanup", "checks"])
    parser.add_argument("--state", type=Path, default=STATE)
    args = parser.parse_args(); state = args.state.resolve()
    require(state.is_relative_to(ROOT / "venv"), "Private preview state must remain in Git-ignored venv.")
    if args.command == "provision":
        provision(state); return
    p, runtime = load(state, check_source=args.command in {"serve", "start", "checks"})
    if args.command == "serve":
        serve(state)
    elif args.command == "checks":
        configure(p, runtime, p["runtime"]); schema_ready(p)
        from django.core.management import call_command
        call_command("check"); call_command("makemigrations", check=True, dry_run=True, interactive=False)
    elif args.command == "status":
        print(json.dumps(verified_health(p, runtime)))
    elif args.command == "start":
        # A bind failure never stops or adopts another service.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", PORT))
        with (state / "server.log").open("ab") as log:
            subprocess.Popen([sys.executable, "-B", str(Path(__file__)), "serve", "--state", str(state)],
                cwd=ROOT, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(40):
            try:
                print(json.dumps(verified_health(p, runtime))); return
            except (OSError, ValueError):
                time.sleep(.25)
        raise RuntimeError("Startup not ready; inspect protected server.log. No automatic retry/fallback.")
    elif args.command == "stop":
        observed = verified_health(p, runtime)
        # Open a handle to the authenticated process BEFORE shutdown; no PID-only kill/wait.
        require(os.name == "nt", "This operator shutdown helper requires Windows process handles.")
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, observed["pid"])
        require(handle, "Cannot retain verified preview process handle.")
        try:
            from urllib.request import Request, build_opener, ProxyHandler
            with build_opener(ProxyHandler({})).open(Request(f"http://localhost:{PORT}"+HEALTH+"stop/", data=b"",
                        headers={"X-Management-Preview-Control": runtime["control"]}), timeout=5) as response:
                require(json.load(response)["identity"] == p["identity"], "Stop identity mismatch.")
            require(kernel.WaitForSingleObject(handle, 15000) == 0, "Preview workers have not drained; no force termination.")
        finally:
            kernel.CloseHandle(handle)
        print("Authenticated preview process exited after worker drain; persistent services untouched.")
    elif args.command == "cleanup":
        # No force, backend termination, broad file deletion or adoption of partial provisioning.
        try:
            verified_health(p, runtime)
        except OSError:
            pass
        else:
            raise RuntimeError("Stop the verified preview before cleanup.")
        from psycopg import sql
        with operator() as control:
            actual = control.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [p["database"]]).fetchone()
            require(actual == (p["oid"], p["marker"]), "Cleanup identity mismatch; manual review required.")
            require(control.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", [p["database"]]).fetchone()[0] == 0,
                    "Preview connections remain; never terminate implicitly.")
            control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(p["database"])))
            for role in (p["runtime"], p["owner"]):
                control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        dump(state / "cleanup.json", {"database": p["database"], "identity": p["identity"], "removed": True})
        print("Exact disposable database/roles removed; protected evidence retained.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Driver/DDL exceptions can embed secrets; never print exception contents.
        detail = str(error) if type(error) is RuntimeError else type(error).__name__
        print("Management TEST preview refused: "+detail+"; no fallback.", file=sys.stderr)
        raise SystemExit(1)
