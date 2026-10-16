"""Explicit, insert-only synthetic Demo preparation. No reset or startup seeding."""
import argparse
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
import secrets
import subprocess
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar

from common import *

VERSION = "SYNTHETIC_DEMO_V1"
MANIFEST = DEFAULT_STATE / "fixtures" / "manifest.json"
ACCOUNTS = DEFAULT_STATE / "credentials" / "test-accounts.json"
MANIFEST_CHECKSUM = MANIFEST.with_suffix(".sha256")
SCENARIOS = (
    ("C0003", "A", "HOME_APPLIANCE_STORE", "فروشگاه نمایشی سپهر", "full_sale"),
    ("C0005", "B", "ELECTRICAL_STORE", "فروشگاه نمایشی آفتاب", "cross_sell"),
    ("C0013", "C", "STORE", "فروشگاه نمایشی بهار", "no_sale"),
    ("C0014", "B", "WHOLESALER", "عمده‌فروشی نمایشی پارس", "retained_draft_low_stock"),
    ("C0029", "C", "STORE", "فروشگاه نمایشی روشن", "unknown_stock"),
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def publish_manifest(manifest):
    write_json(MANIFEST, manifest)
    MANIFEST_CHECKSUM.write_text(hashlib.sha256(MANIFEST.read_bytes()).hexdigest() + "\n", encoding="ascii")


def activate_initial():
    subprocess.run([sys.executable,'-B',str(ROOT/'scripts/demo/initialize.py'),
                    'activate','--confirm-database',DATABASE],check=True,cwd=ROOT)


def definition(preparation_date):
    """Public fixture facts derive from the committed approval, never a DB export."""
    # Pure source verification is also needed before Django/app startup. The
    # actual loader independently verifies the same approved dataset at INSERT.
    price_sha = '1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648'
    prices = read_json(ROOT/'apps/products/data/demo_prices_DEMO_06_V1.json')
    require(digest(prices) == price_sha, 'Approved price dataset checksum mismatch.')
    products = []
    path = ROOT / "docs/checkpoints/DEMO_06_CONTROLLED_PRICING_PROPOSAL.md"
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 3 and re.fullmatch(r"[A-Z]{3}\d{3}", cells[1]):
            name, metadata = cells[2].split("; ", 1)
            brand, category = metadata.split(" / ", 1)
            products.append(dict(code=cells[1], name=name, brand=brand, category=category))
    require(len(products) == 14 and {p["code"] for p in products} == set(prices["prices"]), "Approved product coverage mismatch.")
    return dict(version=VERSION, preparation_date=preparation_date.isoformat(), timezone="Asia/Tehran",
                origin="Synthetic fixtures; no production records, passwords or hashes copied",
                price_dataset_sha256=price_sha, prices=prices, products=products, scenarios=SCENARIOS,
                asset_manifest_sha256=hashlib.sha256((ROOT / "static/demo/manifest.v2.json").read_bytes()).hexdigest())


def record(model, row):
    from django.core.serializers.json import DjangoJSONEncoder
    # Login timestamps/passwords and evolving Visit results are not bootstrap authority.
    excluded = {"password", "last_login"}
    if model._meta.label_lower == "visits.visit":
        excluded |= {"status", "updated_at", "customer_request", "customer_feedback", "competitor_information",
                     "notes", "order_created", "order_amount", "follow_up_required", "follow_up_date"}
    values = {f.attname: getattr(row, f.attname) for f in model._meta.concrete_fields if f.name not in excluded}
    return dict(model=model._meta.label_lower, pk=row.pk,
                fields=canonical_fields(model, json.loads(json.dumps(values, cls=DjangoJSONEncoder))))


def canonical_fields(model, values):
    # Numeric scale can change on a PostgreSQL round trip (0 -> 0.00).
    # Strip only insignificant decimal zeros; never quantize or round a value.
    return {key: format(Decimal(str(value)).normalize(), "f")
            if value is not None and model._meta.get_field(key).get_internal_type() == "DecimalField" else value
            for key, value in values.items()}


def verify_existing(manifest, fixture):
    from django.apps import apps
    require(manifest["identity"] == load_profile()["identity"] and manifest["fixture_sha256"] == digest(fixture),
            "Fixture identity/version/date conflict; no existing row will be overwritten.")
    for expected in manifest["records"]:
        model = apps.get_model(expected["model"])
        row = model.objects.filter(pk=expected["pk"]).first()
        canonical_expected = {**expected, "fields": canonical_fields(model, expected["fields"])}
        require(row is not None and record(model, row) == canonical_expected,
                "Existing fixture conflict in " + expected["model"] + "; inspect, never overwrite.")
    from django.contrib.auth import get_user_model
    accounts = read_json(ACCOUNTS)
    require(accounts["identity"] == manifest["identity"], "TEST account identity mismatch.")
    for account in accounts["accounts"].values():
        user = get_user_model().objects.get(username=account["username"])
        from django.contrib.auth.hashers import check_password
        require(check_password(account["password"], user.password), "TEST credential conflict; no password reset performed.")


class NormalSession:
    """Real session/CSRF HTTP client, restricted to this exact Demo listener."""
    def __init__(self, profile, account):
        import demo
        demo.health(profile)
        self.base = profile["url"]
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))
        _, login_html = self.get("/accounts/login/")
        match = re.search(rb'data-demo-proof="([^"]+)"', login_html)
        self.generation_proof = match.group(1).decode("ascii") if match else None
        status, _ = self.request("/accounts/login/", "POST", urlencode({
            "username": account["username"], "password": account["password"],
            "csrfmiddlewaretoken": self.csrf(), "next": "/api/visits/"}).encode(),
            "application/x-www-form-urlencoded")
        require(status == 200 and any(c.name == "sales_ai_demo_session" for c in self.cookies), "Normal TEST login failed.")

    def csrf(self):
        return next(c.value for c in self.cookies if c.name == "csrftoken")

    def request(self, path, method="GET", body=None, content_type="application/json"):
        require(path.startswith("/") and not path.startswith("//"), "Unsafe Demo HTTP path.")
        headers = {"Referer": self.base + "/", "Origin": self.base}
        if getattr(self, "generation_proof", None):
            headers["X-Demo-Generation-Proof"] = self.generation_proof
        if method != "GET":
            headers.update({"X-CSRFToken": self.csrf(), "Content-Type": content_type})
        with self.opener.open(Request(self.base + path, data=body, headers=headers, method=method), timeout=30) as response:
            require(response.url.startswith(self.base + "/"), "Unexpected authentication redirect.")
            return response.status, response.read()

    def get(self, path):
        return self.request(path)

    def logout(self):
        status, _ = self.request("/accounts/logout/", "POST", b"")
        require(status == 200 and not any(c.name == "sales_ai_demo_session" for c in self.cookies), "Normal TEST logout failed.")


def bootstrap(preparation_date):
    profile = load_profile()
    verify_container(profile)
    from initialization import generation_ready
    from lock_capabilities import validate_runtime
    generation_ready(profile,DEFAULT_STATE)
    with connect(profile, DEFAULT_STATE) as runtime:
        validate_runtime(runtime,profile,DEFAULT_STATE)
        for table, privilege in (("visits_visit", "UPDATE"), ("django_session", "INSERT"),
                                 ("visits_visitcustomersnapshot", "INSERT"), ("visits_visitcommercialsnapshot", "INSERT"),
                                 ("sales_requests_salesrequest", "INSERT"), ("sales_requests_salesrequestline", "UPDATE"),
                                 ("sales_requests_salesrequestmutationreceipt", "INSERT"),
                                 ("recommendations_recommendationfeedbackevent", "INSERT")):
            require(runtime.execute("SELECT has_table_privilege(current_user,%s,%s)", [table, privilege]).fetchone()[0],
                    "Required Demo runtime grant is missing.")
    with connect(profile, DEFAULT_STATE, OWNER):
        pass
    configure_django(profile, DEFAULT_STATE, OWNER)
    check_schema(profile)
    fixture = definition(preparation_date)
    if MANIFEST.exists():
        require(MANIFEST_CHECKSUM.exists() and MANIFEST_CHECKSUM.read_text(encoding="ascii").strip()
                == hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "Protected fixture manifest checksum mismatch.")
        manifest = read_json(MANIFEST)
        verify_existing(manifest, fixture)
        require(manifest.get("phase") == "complete", "Partial bootstrap requires inspection; no automatic restart.")
        print(json.dumps(dict(result="NO_OP", version=VERSION, fixture_sha256=manifest["fixture_sha256"],
                              database=DATABASE, preparation_date=manifest["preparation_date"])))
        return

    from django.db import transaction, connection
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from apps.products.models import Brand, Category, Product
    from apps.products.demo_price_loader import apply_demo_prices
    from apps.customers.models import CustomerGrade, Customer, Customer360
    from apps.inventory.models import Inventory
    from apps.visits.models import Salesperson, CustomerAssignment, Visit
    from apps.recommendations.models import CustomerRecommendation
    from apps.core.demo_assets import demo_image
    require(preparation_date == timezone.localdate(), "First preparation requires today's explicit Asia/Tehran date.")
    (DEFAULT_STATE / "fixtures").mkdir(exist_ok=True)
    require(not ACCOUNTS.exists(), "Existing TEST credentials require inspection; no overwrite.")
    accounts = dict(identity=profile["identity"], accounts={
        key: dict(username=username, password=secrets.token_urlsafe(30))
        for key, username in (("salesperson", "demo-sp001-test"), ("manager", "demo-manager-test"),
                              ("unauthorized", "demo-unassigned-test"))})
    records, visits, images = [], {}, {}

    def insert(model, **fields):
        row = model(**fields)
        row.full_clean()
        row.save(force_insert=True)
        records.append(record(model, row))
        return row

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [89005433])
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            for table, in cursor.fetchall():
                if table not in {"auth_permission", "django_content_type", "django_migrations"}:
                    cursor.execute('SELECT count(*) FROM "' + table.replace('"', '""') + '"')
                    require(cursor.fetchone()[0] == 0, "Existing Demo rows without a manifest; refusing bootstrap.")
        write_json(ACCOUNTS, accounts)
        users = {}
        for key, account in accounts["accounts"].items():
            user = get_user_model()(username=account["username"], first_name="کاربر آزمایشی", last_name=key,
                                   is_staff=key == "manager", is_superuser=False, is_active=True)
            user.set_password(account["password"])
            user.full_clean(); user.save(force_insert=True)
            records.append(record(get_user_model(), user)); users[key] = user
        rep = insert(Salesperson, employee_code="SP001", user=users["salesperson"], first_name="فروشنده", last_name="نمایشی")
        grades = {code: insert(CustomerGrade, code=code, name="رتبه نمایشی " + code) for code in ("A", "B", "C")}
        brands, categories, products = {}, {}, {}
        for item in fixture["products"]:
            brand_name, category_name, code = item["brand"], item["category"], item["code"]
            if brand_name not in brands:
                brands[brand_name] = insert(Brand, name=brand_name, code=brand_name.upper())
            if category_name not in categories:
                categories[category_name] = insert(Category, name=category_name,
                    code="DEMO-" + category_name.upper().replace(" ", "-"))
            products[code] = insert(Product, product_code=code, name=item["name"], brand=brands[brand_name],
                category=categories[category_name], unit=fixture["prices"]["unit"], package_size=fixture["prices"]["package_size"],
                product_group="HOME_APPLIANCE" if brand_name in {"Bosch", "Tefal", "Rowenta"} or code in {"PHI003", "PHI004"} else "PERSONAL_ELECTRICAL",
                description="محصول سناریوی مصنوعی Demo؛ مشخصات مدل دقیق تأیید نشده است.",
                is_consumable=code == "PHI002", is_durable=code != "PHI002")
            if code != "TEF003":
                insert(Inventory, product=products[code], available_quantity=0 if code == "ROW001" else 3 if code == "PHI004" else 25,
                       reserved_quantity=0 if code == "ROW001" else 2 if code == "PHI004" else 3)
            images[code] = demo_image("products", code)
            require(images[code]["url"] is not None, "Approved product image unavailable: " + code)
        price_report = apply_demo_prices(expected_database=DATABASE)
        require(price_report["created_count"] == 14, "Unexpected price bootstrap set.")
        from apps.products.models import ProductDemoPrice
        records.extend(record(ProductDemoPrice, row) for row in ProductDemoPrice.objects.order_by("pk"))
        for code, grade, kind, name, scenario in SCENARIOS:
            customer = insert(Customer, customer_code=code, name=name, grade=grades[grade], customer_type=kind,
                              city="هلند ـ مکان فرضی نمایشی")
            insert(Customer360, customer=customer)  # Honest NEW/zero-history synthetic baseline.
            insert(CustomerAssignment, customer=customer, salesperson=rep, start_date=preparation_date)
            visit = insert(Visit, customer=customer, salesperson=rep, visit_date=preparation_date,
                           status="PLANNED", notes=VERSION + " / " + scenario)
            visits[code] = dict(id=visit.pk, customer_code=code, scenario=scenario)
            priorities = ["TEF003", "PHD001", "BOS002"] if code == "C0029" else ["PHI004", "PHD001", "BOS002"] if code == "C0014" else ["PHD001", "BRN001", "BOS002"]
            recommendation_type = "CROSS_SELL" if code == "C0005" else "REPEAT_PURCHASE" if code == "C0003" else "CATEGORY"
            for rank, product_code in enumerate(priorities, 1):
                insert(CustomerRecommendation, customer=customer, product=products[product_code], rank=rank,
                       score=90-rank, recommendation_type=recommendation_type,
                       reason="اولویت ذخیره‌شده برای تمرین سناریوی مصنوعی؛ متکی به سابقه خرید واقعی نیست.",
                       explanation_snapshot={"fixture_version": VERSION, "scenario": scenario, "synthetic": True})
            images[code] = demo_image("stores", code)
            require(images[code]["url"] is not None, "Approved store image unavailable: " + code)
        manifest = dict(identity=profile["identity"], version=VERSION, phase="fixtures_committed", preparation_date=fixture["preparation_date"],
                        fixture_sha256=digest(fixture), fixture=fixture, records=records, visits=visits, images=images,
                        price_load=price_report)
    # If a crash occurs before this file is published, future bootstrap refuses
    # the populated DB instead of assuming ownership or recreating anything.
    publish_manifest(manifest)
    from django.db import connections
    connections.close_all()
    activate_initial()
    print(json.dumps(dict(result="CREATED", version=VERSION, fixture_sha256=manifest["fixture_sha256"],
                         database=DATABASE, preparation_date=fixture["preparation_date"], visits=visits)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--confirm-database", required=True, choices=[DATABASE])
    args = parser.parse_args()
    try:
        bootstrap(args.date)
    except Exception as exc:
        print("Bootstrap stopped: " + (str(exc) if isinstance(exc, DemoError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
