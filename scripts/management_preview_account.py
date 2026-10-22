"""Stable manager UAT credentials: isolated TEST databases ONLY, never password CLI flags.

adopt retains the current usable secret/PK; reset prompts securely on a real TTY.
Future explicit provision restores the same hash without needing the password.
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
UAT_STATE = ROOT / "venv/management-preview-uat"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_stable(value):
    require(set(value) == {"version", "scope", "username", "password_hash", "is_active", "is_staff", "is_superuser"}, "Unexpected UAT evidence fields.")
    require(value["version"] == 1 and value["scope"] == "MANAGEMENT_TEST_PREVIEW_V1"
            and value["username"] == "manager" and value["is_active"] is True
            and value["is_staff"] is True and value["is_superuser"] is False, "Invalid UAT account scope/permissions.")
    from django.contrib.auth.hashers import PBKDF2PasswordHasher
    parts = PBKDF2PasswordHasher().decode(value["password_hash"])
    require(parts["algorithm"] == "pbkdf2_sha256" and parts["iterations"] >= 100000
            and len(parts["salt"]) >= 8 and len(base64.b64decode(parts["hash"], validate=True)) == 32,
            "Unsupported or unusable UAT password hash.")


def read_stable(*, required=True, directory=UAT_STATE):
    if not directory.exists() and not required:
        return None
    key = (directory / "account-signing.key").read_bytes()
    require(len(key) == 64, "Invalid UAT evidence key.")
    envelope = json.loads((directory / "manager.json").read_text(encoding="utf-8"))
    value = envelope["account"]
    require(hmac.compare_digest(envelope["signature"], hmac.new(key, canonical(value), hashlib.sha256).hexdigest()),
            "UAT provisioning evidence tampered or incomplete.")
    validate_stable(value)
    return value


def atomic_json(path, value):
    temporary = path.with_name(path.name+".pending")
    require(not temporary.exists(), "Interrupted account operation requires inspection; never overwrite pending evidence.")
    with temporary.open("xb") as output:
        output.write(canonical(value)); output.flush(); os.fsync(output.fileno())
    os.replace(temporary, path)


def write_stable(password_hash, *, directory=UAT_STATE):
    from scripts.management_preview import protect
    value = dict(version=1, scope="MANAGEMENT_TEST_PREVIEW_V1", username="manager", password_hash=password_hash,
                 is_active=True, is_staff=True, is_superuser=False)
    validate_stable(value)
    if not directory.exists():
        protect(directory)
        with (directory / "account-signing.key").open("xb") as output:
            output.write(secrets.token_bytes(64)); output.flush(); os.fsync(output.fileno())
    elif (directory / "manager.json").exists():
        read_stable(directory=directory)  # Never overwrite contradictory/tampered evidence.
    key = (directory / "account-signing.key").read_bytes()
    require(len(key) == 64, "Invalid UAT evidence key.")
    atomic_json(directory / "manager.json", dict(account=value, signature=hmac.new(key, canonical(value), hashlib.sha256).hexdigest()))


def prompt_password(user):
    require(sys.stdin.isatty(), "Secure password reset requires an interactive local terminal; no pipe, environment or CLI password.")
    password = getpass.getpass("New manager UAT password (hidden): ")
    confirmation = getpass.getpass("Repeat password (hidden): ")
    require(password == confirmation, "Passwords did not match; nothing changed.")
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    try:
        validate_password(password, user=user)
    except ValidationError:
        raise RuntimeError("Password does not meet Django password requirements; nothing changed.") from None
    return password


def login_credentials(entry):
    """Automation may recover legacy local secrets; chosen UAT passwords need a TTY."""
    password = entry.get("password")
    if not password:
        require(sys.stdin.isatty(), "Chosen UAT password is hash-only; run login verification in an interactive local terminal.")
        password = getpass.getpass("Manager UAT password (hidden): ")
    return {"username": entry["username"], "password": password}


def update_account(state, *, reset=False, directory=UAT_STATE):
    from scripts import management_preview as preview
    p, _ = preview.load(state, check_source=False)
    owner = json.loads((state / "owner.json").read_text(encoding="utf-8"))
    accounts = json.loads((state / "accounts.json").read_text(encoding="utf-8"))
    entry = accounts["manager"]
    preview.configure(p, owner, p["owner"])
    from django.contrib.auth import get_user_model
    from django.db import transaction
    with transaction.atomic():
        selected = get_user_model().objects.select_for_update()
        user = selected.get(pk=entry["user_id"]) if entry.get("user_id") else selected.get(username=entry["username"])
        require(user.username in {"manager", "me01-manager"}, "Unexpected account identity; no overwrite.")
        require(user.is_active and user.is_staff and not user.is_superuser, "Existing TEST account permissions mismatch.")
        require(not get_user_model().objects.filter(username="manager").exclude(pk=user.pk).exists(), "Conflicting manager username; no overwrite.")
        if reset:
            new_password = prompt_password(user)
            user.set_password(new_password)
        else:
            current = read_stable(required=False, directory=directory)
            require((current is None or current["password_hash"] == user.password)
                    and (not entry.get("password") or user.check_password(entry["password"])),
                    "Stored and current account credentials conflict; explicit local reset required.")
        # Publish reusable evidence before DB change. Failure afterwards remains
        # detectable; never silently replace evidence from the database on retry.
        write_stable(user.password, directory=directory)
        user.username = "manager"
        user.save(update_fields=["username", "password"])
        entry["username"] = "manager"
        entry["user_id"] = user.pk
        entry["credential_source"] = "PROTECTED_UAT_HASH"
        if reset:
            entry.pop("password", None)  # A chosen password is never retained reversibly.
        atomic_json(state / "accounts.json", accounts)
    print("Stable manager TEST account ready; existing user ID/history retained. No password/hash printed.")


def main():
    from scripts import management_preview as preview
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["adopt", "reset", "initialize", "where", "provision-clone", "cleanup-clone"])
    parser.add_argument("--state", type=Path, default=preview.STATE)
    args = parser.parse_args(); state = args.state.resolve()
    require(state.is_relative_to(ROOT / "venv"), "Account state must remain in protected Git-ignored venv.")
    if args.command == "initialize":
        require(not UAT_STATE.exists(), "UAT evidence already exists; use explicit reset instead.")
        os.environ["DJANGO_SETTINGS_MODULE"] = "sales_ai_copilot.settings"
        from django.contrib.auth.hashers import make_password
        write_stable(make_password(prompt_password(None)))
        print("Hash-only UAT credential initialized; no database connection or plaintext retention.")
    elif args.command in {"adopt", "reset"}:
        update_account(state, reset=args.command == "reset")
    elif args.command == "where":
        preview.load(state, check_source=False)
        print("Username: manager; preview: http://localhost:8901/accounts/login/")
        print("Existing recoverable credential, if retained: " + str(state / "accounts.json"))
        print("Reusable nonreversible UAT evidence: " + str(UAT_STATE / "manager.json"))
        print("Read locally; never paste credentials or hashes into logs/chat. Use reset to choose a password.")
    else:
        require(state.name.startswith("management-uat-clone-") and state != preview.STATE.resolve(), "Exact offline UAT clone state required.")
        if args.command == "provision-clone":
            read_stable()
            preview.provision(state, check_port=False)  # Offline only: no listener/port or existing DB changes.
        else:
            p, _ = preview.load(state, check_source=False)
            live, _ = preview.load(preview.STATE, check_source=False)
            require(p["database"] != live["database"] and p["identity"] != live["identity"], "Clone cannot be the current preview.")
            from psycopg import sql
            with preview.operator() as control:
                actual = control.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [p["database"]]).fetchone()
                require(actual == (p["oid"], p["marker"]), "Clone cleanup identity mismatch.")
                require(control.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", [p["database"]]).fetchone()[0] == 0,
                        "Clone connections remain; no termination allowed.")
                control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(p["database"])))
                for role in (p["runtime"], p["owner"]):
                    control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
            atomic_json(state / "cleanup.json", {"identity": p["identity"], "removed": True})
            print("Only the verified offline UAT clone database/roles removed; current preview retained.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        detail = str(error) if type(error) is RuntimeError else type(error).__name__
        print("UAT account operation refused: "+detail+"; no fallback or automatic reset.", file=sys.stderr)
        raise SystemExit(1)
