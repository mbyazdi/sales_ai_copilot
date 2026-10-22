"""Focused stable UAT account proof, never business POSTs or persistent DB access."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import management_preview as preview
from scripts.management_preview_account import login_credentials, read_stable
from scripts.verify_management_preview import API, Browser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["http", "clone"])
    parser.add_argument("--state", type=Path, default=preview.STATE)
    args = parser.parse_args(); state = args.state.resolve()
    preview.require(state.is_relative_to(ROOT / "venv"), "Protected preview state required.")
    p, runtime = preview.load(state, check_source=False)
    account = json.loads((preview.STATE / "accounts.json").read_text(encoding="utf-8"))["manager"]
    credentials = login_credentials(account)
    passed = []
    def check(condition, name):
        preview.require(condition, name); passed.append(name)
    if args.mode == "http":
        preview.verified_health(p, runtime)
        browser = Browser()
        browser.request("/accounts/login/")
        status, body, _ = browser.request("/accounts/login/", dict(credentials, password=credentials["password"]+"-wrong"), form=True)
        check(status == 200 and b'name="password"' in body, "invalid credentials rejected")
        check(browser.request(API+"overview/")[0] == 401, "invalid login has no authorized session")
        browser.login(credentials)
        check(credentials["username"] == "manager", "stable username")
        for path in ("overview/", "versions/", "comparisons/2/"):
            check(browser.request(API+path)[0] == 200, "manager access "+path)
        check(browser.request(API+"draft/", {}, csrf=False)[0] == 403, "missing CSRF rejected")
        check(browser.request(API+"draft/", {}, headers={"X-CSRFToken": "invalid"}, csrf=False)[0] == 403, "invalid CSRF rejected")
        check(browser.request(API+"draft/", {})[0] == 400, "manage capability reaches strict input validation without mutation")
        check(browser.request("/accounts/logout/")[0] == 405, "GET logout forbidden")
        check(browser.request(API+"overview/")[0] == 200, "GET logout retains session")
        check(browser.request("/accounts/logout/", {}, csrf=False, form=True)[0] == 403, "logout requires CSRF")
        check(browser.request("/accounts/logout/", {}, form=True)[0] == 200, "normal POST logout")
        check(browser.request(API+"overview/")[0] == 401, "session invalidated")
    else:
        preview.require(state.name.startswith("management-uat-clone-") and state != preview.STATE.resolve(), "Offline clone only.")
        owner = json.loads((state / "owner.json").read_text(encoding="utf-8"))
        preview.configure(p, owner, p["owner"])
        from django.contrib.auth import authenticate, get_user_model
        from django.conf import settings
        from django.test import Client
        from django.db.migrations.loader import MigrationLoader
        from django.db import connection
        from apps.management.strategy_access import can_manage_strategy, can_view_strategy
        loader = MigrationLoader(connection)
        check(set(loader.applied_migrations) == set(loader.disk_migrations), "clone full migration graph")
        user = get_user_model().objects.get(username="manager")
        check(user.password == read_stable()["password_hash"], "exact hash restored from independent UAT evidence")
        check(user.is_active and user.is_staff and not user.is_superuser, "least authority TEST account")
        check(can_manage_strategy(user) and can_view_strategy(user), "strategy capabilities restored")
        check(authenticate(**credentials).pk == user.pk, "same password authenticates rebuilt account")
        client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost:8901")
        response = client.get("/accounts/login/")
        token = response.cookies[settings.CSRF_COOKIE_NAME].value
        check(client.post("/accounts/login/", credentials, HTTP_X_CSRFTOKEN=token).status_code == 302, "rebuilt normal login with real middleware/CSRF")
        check(client.get(API+"overview/").status_code == 200, "rebuilt manager overview")
        check(client.get(API+"versions/").status_code == 200, "rebuilt manager versions")
        check(not client.get(API+"overview/").json()["version_count"], "rebuild does not copy existing strategy/commercial history")
        # Exercise reset only in the clone, with a separate test provisioning store.
        # The test secret stays in memory and never touches arguments/environment/logs.
        import secrets
        from unittest.mock import patch
        from scripts.management_preview_account import update_account, write_stable
        stable_before = read_stable()
        directory = state / "reset-test-uat"
        write_stable(stable_before["password_hash"], directory=directory)
        replacement = secrets.token_urlsafe(32)
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", side_effect=[replacement, replacement]):
            update_account(state, reset=True, directory=directory)
        check(authenticate(username="manager", password=replacement).pk == user.pk, "clone explicit reset works and retains PK")
        check(authenticate(**credentials) is None, "clone prior password rejected after reset")
        check(client.get(API+"overview/").status_code == 401, "reset invalidates existing Django session")
        check(read_stable() == stable_before, "current UAT provisioning evidence untouched by clone reset")
        clone_account = json.loads((state / "accounts.json").read_text(encoding="utf-8"))["manager"]
        check("password" not in clone_account, "chosen password not retained reversibly")
    preview.dump(state / ("uat-account-"+args.mode+"-proof.json"), {"passed": len(passed), "checks": passed, "identity": p["identity"],
                 "username": "manager", "business_posts": 0})
    print(json.dumps({"passed": len(passed), "mode": args.mode, "username": "manager"}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        detail = str(error) if type(error) is RuntimeError else type(error).__name__
        print("UAT verification refused: "+detail+"; no automatic mutation/retry.", file=sys.stderr)
        raise SystemExit(1)
