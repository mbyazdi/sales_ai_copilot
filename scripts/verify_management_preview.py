"""Real HTTP/session/CSRF proof. Writes ONLY the explicitly provisioned TEST DB.

Run once on a fresh preview. Evidence stays in protected Git-ignored state.
"""
import argparse
from http.cookiejar import CookieJar
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request, ProxyHandler
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.management_preview import STATE, SOURCE_TABLES, dump, encoded, verified_health, load, require

BASE = "http://localhost:8901"
API = "/api/management/v1/strategy/"


class Browser:
    def __init__(self):
        self.cookies = CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(self.cookies))

    def csrf(self):
        return next(c.value for c in self.cookies if c.name.startswith("management_test_csrf_"))

    def request(self, path, data=None, *, csrf=True, method=None, headers=None, form=False):
        headers = dict(headers or {})
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
            if csrf:
                headers["X-CSRFToken"] = self.csrf()
            data = urlencode(data).encode() if form else encoded(data)
        request = Request(BASE+path, data=data, method=method, headers=headers)
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            content = response.headers.get("Content-Type", "")
            return response.status, json.loads(body) if "application/json" in content and body else body, response.headers

    def login(self, account):
        status, page, _ = self.request("/accounts/login/")
        require(status == 200 and re.search(rb'name="csrfmiddlewaretoken" value="[A-Za-z0-9]{64}"', page), "Normal login CSRF field absent.")
        from scripts.management_preview_account import login_credentials
        status, body, _ = self.request("/accounts/login/", login_credentials(account), form=True)
        # Default destination is a strategy API: nonstaff logins succeed but then receive 403.
        require(status in (200, 403), "Normal session login failed.")
        return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--recovery-only", action="store_true", help="Login and retrieve prior frozen evidence; never resend a business POST.")
    mode.add_argument("--readiness-negative", action="store_true", help="Explicitly revoke/restore one grant ONLY in this disposable DB to prove fail-closed readiness.")
    args = parser.parse_args(); state = args.state.resolve()
    p, credentials = load(state); verified_health(p, credentials)
    accounts = json.loads((state / "accounts.json").read_text(encoding="utf-8"))
    if args.readiness_negative:
        import psycopg
        from psycopg import sql
        owner = json.loads((state / "owner.json").read_text(encoding="utf-8"))
        from scripts.management_test_isolation import connect_preview
        with connect_preview(p, owner, p["owner"], autocommit=True) as raw:
            table = "management_strategypolicyevent"
            require(raw.execute("SELECT has_table_privilege(%s,%s,'SELECT')", [p["runtime"], table]).fetchone() == (True,),
                    "Expected original grant absent; do not adopt unknown ACL.")
            try:
                raw.execute(sql.SQL("REVOKE SELECT ON {} FROM {}").format(sql.Identifier(table), sql.Identifier(p["runtime"])))
                command = [sys.executable, "-B", str(Path(__file__).with_name("management_preview.py")), "checks", "--state", str(state)]
                result = subprocess.run(command, capture_output=True, timeout=30)
                require(result.returncode == 1, "Missing grant did not fail readiness.")
                require(raw.execute("SELECT has_table_privilege(%s,%s,'SELECT')", [p["runtime"], table]).fetchone() == (False,),
                        "Readiness unexpectedly repaired permissions.")
            finally:
                raw.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(p["runtime"])))
            require(subprocess.run(command, capture_output=True, timeout=30).returncode == 0, "Restored preview not ready.")
        dump(state / "readiness-negative-proof.json", {"identity": p["identity"], "missing_grant_rejected": True,
              "startup_repairs": 0, "exact_disposable_grant_restored": True})
        print("Readiness negative proof passed: missing grant refused, zero automatic repairs, explicit disposable grant restored.")
        return
    if args.recovery_only:
        proof = json.loads((state / "http-proof.json").read_text(encoding="utf-8"))
        require(proof["identity"] == p["identity"] and proof["source_sha256"] == p["source_sha256"], "Recovery evidence mismatch.")
        browser = Browser(); browser.login(accounts["manager"])
        status, evidence, _ = browser.request(API+f"comparisons/{proof['comparison_id']}/")
        require(status == 200 and evidence["output_digest"] == proof["output_digest"], "Historical recovery mismatch.")
        require(evidence["outputs"]["after"]["after_ids"] == proof["after_ids"], "Historical ranking mismatch.")
        require(browser.request(API+"overview/")[0] == 200, "Restart snapshot transaction failed.")
        require(browser.request("/accounts/logout/", {}, form=True)[0] == 200, "Recovery logout failed.")
        require(browser.request(API+"overview/")[0] == 401, "Recovery session not invalidated.")
        dump(state / "restart-proof.json", {"identity": p["identity"], "historical_digest_unchanged": True,
                                           "business_posts": 0, "normal_login_logout": True})
        print("Restart recovery passed: normal login/logout, frozen comparison/digest, zero business POSTs.")
        return
    import psycopg
    from scripts.management_test_isolation import connect_preview
    raw = connect_preview(p, credentials, p["runtime"])
    passed = []
    def check(condition, label):
        require(condition, label); passed.append(label)
    def source_digest():
        from psycopg import sql
        raw.execute("SET TIME ZONE 'UTC'")
        digest = hashlib.sha256()
        for table in SOURCE_TABLES:
            if table.startswith(("auth_", "management_")):
                continue
            rows = raw.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text")
                               .format(sql.Identifier(table))).fetchall()
            digest.update(encoded([table, rows]))
        raw.rollback()
        return digest.hexdigest()
    try:
        check(raw.execute("SELECT count(*) FROM management_strategypolicy").fetchone()[0] == 0, "fresh preview only; no silent reseed")
        raw.rollback(); before = source_digest()
        manager = Browser()
        check(manager.request(API+"overview/")[0] == 401, "unauthenticated API denied")
        manager.request("/accounts/login/")
        check(manager.request("/accounts/login/", accounts["manager"], csrf=False, form=True)[0] == 403, "login missing CSRF denied")
        manager.login(accounts["manager"])
        check(raw.execute("SELECT last_login IS NOT NULL FROM auth_user WHERE username=%s", [accounts["manager"]["username"]]).fetchone()[0], "normal login updates last_login")
        raw.rollback()
        session = next(c.value for c in manager.cookies if c.name.startswith("management_test_session_"))
        check(raw.execute("SELECT count(*) FROM django_session WHERE session_key=%s", [session]).fetchone()[0] == 1, "database-backed session created")
        raw.rollback()
        status, initial, _ = manager.request(API+"overview/")
        check(status == 200 and initial["revision"] == 0, "top-level read snapshot HTTP succeeds")
        check(raw.execute("SELECT count(*) FROM management_strategypolicy").fetchone()[0] == 0, "GET never initializes head")
        raw.rollback()
        for role in ("salesperson", "unauthorized"):
            browser = Browser(); browser.login(accounts[role])
            check(browser.request(API+"overview/")[0] == 403, role+" denied management read")
            check(browser.request(API+"draft/", {"command_uuid": str(uuid4()), "expected_revision": 0, "config": {}})[0] == 403,
                  role+" denied management mutation")
            browser.request("/accounts/logout/", {}, form=True)
        neutral = {"schema_version": 1, "priority_rules": [], "target_weight": 0, "promotion_rules": []}
        command = {"command_uuid": str(uuid4()), "expected_revision": 0, "config": neutral}
        check(manager.request(API+"draft/", command, csrf=False)[0] == 403, "API missing CSRF denied")
        check(manager.request(API+"draft/", command, headers={"X-CSRFToken": "invalid"}, csrf=False)[0] == 403, "API invalid CSRF denied")
        check(manager.request(API+"draft/", command, headers={"Origin": "http://hostile.invalid"})[0] == 403, "hostile origin denied")
        check(manager.request("/api/visits/")[0] == 404, "unrelated mutation surfaces not exposed")
        check(manager.request(API+"draft/", command)[0] == 201, "explicit neutral draft created")
        def overview():
            status, value, _ = manager.request(API+"overview/"); require(status == 200, "overview failed"); return value
        def comparison():
            head = overview(); f = p["fixture"]
            context = dict(customer_id=f["customer_id"], salesperson_id=f["salesperson_id"], evaluation_date=f["evaluation_date"],
                           proposed_version_id=head["draft_version_id"], expected_revision=head["revision"])
            status, value, _ = manager.request(API+"options/?"+urlencode(context))
            check(status == 200, "authoritative source capture via HTTP")
            payload = dict(**value["preview_context"], command_uuid=str(uuid4()))
            status, result, _ = manager.request(API+"comparisons/", payload)
            check(status == 201, "comparison persisted through normal HTTP")
            status, replay, headers = manager.request(API+"comparisons/", payload)
            check(status == 200 and replay == result and headers.get("Idempotent-Replayed") == "true", "exact comparison replay")
            altered = dict(payload, evaluation_date="2000-01-01")
            check(manager.request(API+"comparisons/", altered)[0] == 409, "conflicting UUID rejected")
            status, recovered, _ = manager.request(API+"commands/"+payload["command_uuid"]+"/")
            check(status == 200 and recovered["result"] == result["result"], "explicit read-only command recovery")
            cid = result["result"]["comparison_id"]
            status, evidence, _ = manager.request(API+f"comparisons/{cid}/")
            check(status == 200, "immutable historical retrieval")
            return evidence
        def publish(evidence):
            head = overview()
            payload = dict(command_uuid=str(uuid4()), expected_revision=head["revision"], draft_version_id=head["draft_version_id"],
                           comparison_id=evidence["comparison_id"], accepted_comparison_digest=evidence["output_digest"])
            status, result, _ = manager.request(API+"publish/", payload)
            check(status == 200, "explicit publication via runtime HTTP")
            check(manager.request(API+"publish/", payload)[1] == result, "publication exact replay")
        neutral_comparison = comparison(); publish(neutral_comparison)
        head = overview(); f = p["fixture"]
        boosted = dict(neutral, priority_rules=[{"scope_type": "PRODUCT", "scope_id": f["product_ids"][2], "points": 20}],
                       target_weight=5, promotion_rules=[{"promotion_id": f["promotion_id"], "points": 5}])
        check(manager.request(API+"draft/", dict(command_uuid=str(uuid4()), expected_revision=head["revision"], config=boosted))[0] == 201,
              "proposed boost draft created")
        evidence = comparison()
        before_ids, after_ids = evidence["outputs"]["before"]["after_ids"], evidence["outputs"]["after"]["after_ids"]
        check(after_ids == [before_ids[2], before_ids[0], before_ids[1], before_ids[3]], "genuine before/after reranking")
        row = next(r for r in evidence["outputs"]["after"]["rows"] if r["source"]["product_id"] == f["product_ids"][2])
        check(row["effective_priority"] == "37.50" and row["target"]["points"] == "2.50", "server Decimal contribution evidence")
        publish(evidence)
        check(manager.request(API+f"comparisons/{evidence['comparison_id']}/")[1] == evidence, "frozen evidence unchanged after publication")
        for statement in ("UPDATE products_product SET name=name", "UPDATE products_productdemoprice SET base_price=base_price",
                          "UPDATE management_strategycomparison SET outputs=outputs", "DELETE FROM management_strategypolicyevent",
                          "CREATE TABLE public.preview_forbidden(id int)"):
            try:
                raw.execute(statement)
            except psycopg.errors.InsufficientPrivilege:
                raw.rollback(); check(True, "runtime denied "+statement.split()[0]+" "+statement.split()[1])
            else:
                raw.rollback(); raise RuntimeError("Unexpected runtime write/DDL privilege")
        counts = raw.execute("SELECT (SELECT count(*) FROM management_strategycomparison),(SELECT count(*) FROM management_strategypolicyevent)").fetchone()
        raw.rollback()
        for suffix in ("overview/", "options/", "versions/", f"comparisons/{evidence['comparison_id']}/"):
            check(manager.request(API+suffix)[0] == 200, "read-only GET "+suffix)
            check(manager.request(API+suffix, method="HEAD")[0] == 200, "read-only HEAD "+suffix)
        check(raw.execute("SELECT (SELECT count(*) FROM management_strategycomparison),(SELECT count(*) FROM management_strategypolicyevent)").fetchone() == counts,
              "GET/HEAD preserve strategy evidence counts")
        raw.rollback()
        check(manager.request("/accounts/logout/", {}, form=True)[0] == 200, "standard POST logout")
        check(manager.request(API+"overview/")[0] == 401, "logout invalidates authenticated access")
        check(raw.execute("SELECT count(*) FROM django_session WHERE session_key=%s", [session]).fetchone()[0] == 0, "old session removed")
        raw.rollback()
        check(source_digest() == before, "all fixture/source rows unchanged")
        dump(state / "http-proof.json", {"passed": len(passed), "checks": passed, "database": p["database"], "identity": p["identity"],
            "source_sha256": p["source_sha256"], "before_ids": before_ids, "after_ids": after_ids,
            "comparison_id": evidence["comparison_id"], "output_digest": evidence["output_digest"], "source_preserved": True})
        print(json.dumps({"passed": len(passed), "comparison_id": evidence["comparison_id"], "before_ids": before_ids, "after_ids": after_ids}))
    finally:
        raw.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        detail = str(error) if type(error) is RuntimeError else type(error).__name__
        print("Management HTTP proof failed: "+detail+"; no automatic retry. Protected state retained.", file=sys.stderr)
        raise SystemExit(1)
