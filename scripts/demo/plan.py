"""Read-only Demo maintenance plans. No apply/confirm/reset execution path."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from zoneinfo import ZoneInfo

from common import *

TEHRAN = ZoneInfo("Asia/Tehran")
FIXTURE_VERSION = "SYNTHETIC_DEMO_V1"
CUSTOMERS = ("C0003", "C0005", "C0013", "C0014", "C0029")
FRAMEWORK = {"django_migrations", "django_content_type", "auth_permission"}
SCENARIO_TABLES = {
    "visits_visit", "visits_visitcustomersnapshot", "visits_visitcommercialsnapshot",
    "sales_requests_salesrequest", "sales_requests_salesrequestline",
    "sales_requests_salesrequestacknowledgement", "sales_requests_salesrequestmutationreceipt",
    "recommendations_recommendationfeedbackevent", "visits_salesoutcome", "visits_followuptask",
    "sales_sale", "sales_saleitem", "django_admin_log",
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def resolve_date(explicit=None, now=None):
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None and now.utcoffset() is not None, "An aware clock is required.")
    today = now.astimezone(TEHRAN).date()
    return (date.fromisoformat(explicit) if explicit else today), today


def checked_json(path):
    require(path.with_suffix(".sha256").read_text(encoding="ascii").strip()
            == hashlib.sha256(path.read_bytes()).hexdigest(), "Protected fixture/ledger checksum mismatch.")
    return read_json(path)


def fixture_manifest(profile, state):
    manifest = checked_json(state / "fixtures/manifest.json")
    require(manifest.get("identity") == profile["identity"] and manifest.get("version") == FIXTURE_VERSION
            and manifest.get("phase") == "complete", "Incomplete or foreign fixture generation.")
    require(fingerprint(manifest["fixture"]) == manifest["fixture_sha256"], "Fixture payload fingerprint mismatch.")
    require(set(manifest["visits"]) == set(CUSTOMERS), "Unexpected fixture customer set.")
    return manifest


def registration(manifest, state, target):
    result = {code: v["id"] for code, v in manifest["visits"].items()} if target.isoformat() == manifest["preparation_date"] else {}
    path = state / "fixtures/prepared-days" / (target.isoformat() + ".json")
    if path.exists():
        ledger = checked_json(path)
        require(ledger.get("identity") == manifest["identity"] and ledger.get("version") == 1
                and ledger.get("date") == target.isoformat() and set(ledger.get("visits", {})) == set(CUSTOMERS),
                "Foreign or incomplete prepared-day ledger.")
        require(not result or result == ledger["visits"], "Conflicting prepared-day registrations.")
        result = ledger["visits"]
    require(all(type(v) is int and v > 0 for v in result.values()) and len(set(result.values())) == len(result),
            "Invalid prepared-day identities.")
    return result


def inventory(connection, profile):
    """One consistent read-only snapshot; report digests, never secret row values."""
    from psycopg import sql
    require(connection.execute("SHOW transaction_read_only").fetchone()[0] == "on", "Read-only transaction required.")
    migrations = [list(row) for row in connection.execute("SELECT app,name FROM django_migrations ORDER BY app,name")]
    require(migrations == profile["migration_keys"] and len(migrations) == 50
            and migration_fingerprint() == (50, profile["migration_fingerprint"]), "Schema/source migration drift.")
    tables = {}
    for name, in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall():
        rows = connection.execute(sql.SQL("SELECT row_to_json(t)::text FROM public.{} t ORDER BY row_to_json(t)::text")
                                  .format(sql.Identifier(name))).fetchall()
        tables[name] = {"count": len(rows), "sha256": hashlib.sha256("\n".join(row[0] for row in rows).encode()).hexdigest()}
    sequences = connection.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename").fetchall()
    visits = [dict(id=row[0], customer=row[1], salesperson_id=row[2], date=row[3].isoformat(), status=row[4])
              for row in connection.execute("SELECT v.id,c.customer_code,v.salesperson_id,v.visit_date,v.status "
                  "FROM visits_visit v JOIN customers_customer c ON c.id=v.customer_id ORDER BY v.id")]
    actor = connection.execute("SELECT s.id,s.is_active,u.is_active,u.is_staff FROM visits_salesperson s "
                               "JOIN auth_user u ON u.id=s.user_id WHERE s.employee_code='SP001'").fetchall()
    require(len(actor) == 1 and actor[0][1:] == (True, True, False), "Synthetic SP001 identity is unavailable.")
    customers = {row[0]: dict(id=row[1], active=row[2], assigned=row[3]) for row in connection.execute(
        "SELECT c.customer_code,c.id,c.is_active,EXISTS(SELECT 1 FROM visits_customerassignment a "
        "WHERE a.customer_id=c.id AND a.salesperson_id=%s AND a.is_active) FROM customers_customer c", [actor[0][0]])}
    sessions = connection.execute("SELECT count(*),count(*) FILTER(WHERE expire_date>CURRENT_TIMESTAMP) FROM django_session").fetchone()
    operational = {name: tables[name]["count"] for name in sorted(SCENARIO_TABLES) if name in tables}
    state_hash = fingerprint({"tables": tables, "sequences": sequences, "migrations": migrations})
    return dict(tables=tables, sequences=sequences, state_sha256=state_hash, migrations=migrations,
                visits=visits, salesperson_id=actor[0][0], customers=customers,
                sessions={"stored": sessions[0], "unexpired": sessions[1]}, operational_counts=operational)


def prepare_day(snapshot, manifest, target, today, registered):
    rows, warnings = [], []
    past = target < today
    for code in CUSTOMERS:
        customer = snapshot["customers"].get(code)
        same_day = [v for v in snapshot["visits"] if v["customer"] == code
                    and v["salesperson_id"] == snapshot["salesperson_id"] and v["date"] == target.isoformat()]
        other_active = [v["id"] for v in snapshot["visits"] if v["customer"] == code
                        and v["salesperson_id"] == snapshot["salesperson_id"]
                        and v["status"] == "IN_PROGRESS" and v["date"] < target.isoformat()]
        item = dict(customer_code=code, salesperson_code="SP001", date=target.isoformat(), existing_visit_ids=[v["id"] for v in same_day])
        if past:
            item.update(action="BLOCKED", reason="PAST_DATE")
        elif not customer or not customer["active"] or not customer["assigned"]:
            item.update(action="BLOCKED", reason="CUSTOMER_OR_ASSIGNMENT_UNAVAILABLE")
        elif len(same_day) > 1:
            item.update(action="BLOCKED", reason="DUPLICATE_DAY_VISITS")
        elif same_day:
            visit = same_day[0]
            if registered.get(code) != visit["id"]:
                item.update(action="BLOCKED", reason="UNREGISTERED_EXISTING_VISIT")
            elif visit["status"] in {"COMPLETED", "CANCELLED"}:
                item.update(action="PRESERVE_CLOSED", reason="DAY_ALREADY_USED", status=visit["status"])
            else:
                item.update(action="KEEP_EXISTING", status=visit["status"])
        elif code in registered:
            item.update(action="BLOCKED", reason="REGISTERED_VISIT_MISSING_OR_CHANGED")
        else:
            item.update(action="WOULD_INSERT", table="visits_visit", status="PLANNED")
        if other_active:
            item.update(action="BLOCKED",reason="OLDER_IN_PROGRESS_VISIT")
            item["other_date_in_progress_visit_ids"] = other_active
            warnings.append(dict(code="OLDER_IN_PROGRESS_BLOCKS_DAY", customer_code=code, visit_ids=other_active))
        rows.append(item)
    blocked = any(r["action"] in {"BLOCKED", "PRESERVE_CLOSED"} for r in rows)
    count = sum(row["action"] == "WOULD_INSERT" for row in rows)
    return dict(status="BLOCKED" if blocked else "REVIEW_REQUIRED" if warnings else "NO_OP" if not count else "READY_FOR_APPROVAL",
        target_date=target.isoformat(), timezone="Asia/Tehran", today=today.isoformat(), visits=rows,
        proposed_insert_count=0 if blocked else count, unblocked_candidate_count=count, warnings=warnings,
        preserved="All existing Visits, dates, statuses, requests, lines, receipts, acknowledgements and snapshots remain unchanged.",
        c0005_activation="Any new C0005 starts PLANNED; a separate explicit authorized Start creates IN_PROGRESS and snapshots. No direct status seeding.",
        repeat_run="Future executor must serialize maintenance, recheck state, insert atomically and publish a checksummed date ledger. Registered open rows are reused; closed/unregistered/duplicate rows are never reopened/adopted.",
        prerequisite="No customer+salesperson+date database uniqueness exists: quiesce competing maintenance and use transaction/recheck plus durable prepared-day registration.")


def reset_plan(snapshot, manifest, profile, target, today):
    from collections import Counter
    from generation import PHASES
    token = fingerprint({"identity": profile["identity"], "state": snapshot["state_sha256"], "date": target.isoformat()})[:12]
    candidate = "sales_ai_demo_candidate_" + token
    fresh_counts = Counter(record["model"].replace(".", "_") for record in manifest["records"])
    fresh_counts.update({"django_migrations": 50, "django_content_type": 35, "auth_permission": 140,
                         "visits_visitcustomersnapshot": 1, "visits_visitcommercialsnapshot": 1})
    replacements = []
    for table, value in sorted(snapshot["tables"].items()):
        treatment = "REGENERATE_FRAMEWORK" if table in FRAMEWORK else "FRESH_SESSIONS_EMPTY" if table == "django_session" else "NEW_OPERATIONAL_BASELINE" if table in SCENARIO_TABLES else "FRESH_SYNTHETIC_FIXTURE_OR_EMPTY"
        replacements.append(dict(table=table, current_rows=value["count"], current_rows_deleted=0,
                                 candidate_expected_rows=fresh_counts[table],
                                 candidate_treatment=treatment, old_generation="RETAIN_UNCHANGED"))
    return dict(status="DESIGN_ONLY_OWNER_APPROVAL_REQUIRED" if target >= today else "BLOCKED_PAST_DATE",
        target_date=target.isoformat(), timezone="Asia/Tehran", current_generation=profile["identity"],
        candidate_database_proposal=candidate, tables=replacements,
        activation_journal_design=dict(phases=list(PHASES),multi_step_atomic=False,execution_available=False,
            minimum_previous_healthy_generations=1,interruption_policy="Fail closed; inspect exact identities and last durable phase. No automatic resume/promotion/rollback/cleanup."),
        fixture_source=dict(version=manifest["version"], payload_sha256=manifest["fixture_sha256"],
                            price_dataset_sha256=manifest["fixture"]["price_dataset_sha256"]),
        current_sessions=snapshot["sessions"], current_business_evidence=snapshot["operational_counts"],
        confirmation_design={"future_required_phrase": f"ACTIVATE DEMO CANDIDATE {candidate} FROM {profile['identity']} ON {target.isoformat()}",
            "must_bind": ["exact candidate DB/OID/identity", "container/image/volume/127.0.0.1:5433", "current state SHA256", "plan SHA256", "migration fingerprint", "fixture checksums", "date", "retention and browser fencing approval"],
            "cleanup": "Separate independent approval; activation never deletes the previous generation."},
        steps=[
            "Approve the exact candidate identity/name/credentials and generation registry design; owner lacks CREATEDB, so creation needs the dedicated Demo bootstrap operator, never production credentials.",
            "Create a new empty candidate on the dedicated Demo cluster; apply reviewed migrations and synthesize fixtures from the frozen definition, not an old/production DB clone. No old users/password hashes/sessions/history copied.",
            "Generate independent candidate roles/signing key/session namespace; validate grants, all fixture checksums and full journey in isolation. Proposed operational baseline is fresh five Visits (C0005 through authorized Start), with no old requests/events/receipts/acknowledgements/sales.",
            "Stop only the verified Demo app after explicit maintenance approval, reconcile old pending commands, and fence old-generation writes. Retain the old DB, credentials, manifest, all history and browser profile.",
            "After independent candidate validation and exact confirmation, use a durable ordered journal for recovery recording, verified app quiescence, old-write fencing, profile selection and new-app validation. Multi-step promotion is not atomic. Current launcher guards still hardcode sales_ai_demo_db; no candidate switch is implemented.",
            "Require server-validated document/command generation proofs and a generation-bound authenticated session, plus fresh browser storage. Never restamp old pending envelopes. Cookie/key/profile isolation alone is insufficient; no browser/profile change occurs now.",
            "Before first candidate business write, recovery may reactivate the preserved generation after verifying its profile/browser and explicitly reauthorizing any old-runtime grant unfencing. After candidate writes, stop and reconcile both generations; never silently merge or roll back new evidence.",
        ],
        browser_risks={"database_detection_limit": "Browser sessionStorage and in-flight requests cannot be observed from database rows; zero DB sessions/receipts is not proof of zero pending commands.",
            "stored_state": ["DB-backed login sessions", "guided-basket:v1:*", "guided-feedback:v1:*", "sales-request-submit:v1:*", "visit-completion:v1:*"],
            "hazard": "Same-origin tabs can pick up fresh cookies/CSRF and replay old UUIDs against reused IDs. Rotating keys or logging out alone is insufficient; completion has no signed catalog-context fence.",
            "policy": "Quarantine old profiles/tabs and never copy pending payloads to a candidate. Resolve old commands through old-generation status/receipts before retirement. No POST auto-retry.",
            "approval_required": "Independently validate candidate proof/session guards, exact profile selection and journal evidence, old-runtime write fencing, at least one retained healthy generation and post-write recovery. No browser clearing, logout, key rotation or grant change occurs now."})


def build_plan(operation, explicit_date=None, *, state=DEFAULT_STATE, now=None):
    state = Path(state)
    profile = load_profile(state)
    verify_container(profile)
    manifest = fixture_manifest(profile, state)
    target, today = resolve_date(explicit_date, now)
    registered = registration(manifest, state, target) if operation == "prepare-day" else {}
    require(operation in {"prepare-day", "reset"}, "Unsupported planning operation.")
    with connect(profile, state, readonly=True) as connection:
        connection.rollback()  # Finish only the identity SELECT transaction.
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        observed = inventory(connection, profile)
    result = dict(version=1, operation=operation, dry_run=True, execution_available=False,
        database=DATABASE, endpoint="127.0.0.1:5433", container=CONTAINER, identity=profile["identity"],
        fixture_generation=manifest["version"], fixture_preparation_date=manifest["preparation_date"],
        migration_count=50, migration_fingerprint=profile["migration_fingerprint"],
        database_state_sha256=observed["state_sha256"], database_transaction="REPEATABLE READ / READ ONLY",
        result=prepare_day(observed, manifest, target, today, registered) if operation == "prepare-day"
            else reset_plan(observed, manifest, profile, target, today))
    result["plan_sha256"] = fingerprint(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare-day", "reset"])
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--date", type=lambda value: date.fromisoformat(value).isoformat())
    args = parser.parse_args()
    print(json.dumps(build_plan(args.operation, args.date), indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Demo planning refused: " + (str(exc) if isinstance(exc, DemoError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
