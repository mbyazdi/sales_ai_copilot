"""Focused pure/read-only planner tests. No fixtures, login, DML or DDL."""
import copy
from datetime import date, datetime, timezone
import json
import subprocess
import unittest
from unittest.mock import patch

from common import *
import plan


def example():
    return dict(salesperson_id=1, customers={c:dict(id=i,active=True,assigned=True) for i,c in enumerate(plan.CUSTOMERS,1)},
                visits=[dict(id=i,customer=c,salesperson_id=1,date="2026-10-15",status="IN_PROGRESS" if c=="C0005" else "PLANNED")
                        for i,c in enumerate(plan.CUSTOMERS,1)])


class PlanningTests(unittest.TestCase):
    def test_tehran_midnight_boundary(self):
        self.assertEqual(plan.resolve_date(now=datetime(2026,10,15,20,29,59,tzinfo=timezone.utc))[0], date(2026,10,15))
        self.assertEqual(plan.resolve_date(now=datetime(2026,10,15,20,30,tzinfo=timezone.utc))[0], date(2026,10,16))

    def test_tehran_year_boundary_and_leap_day(self):
        self.assertEqual(plan.resolve_date(now=datetime(2026,12,31,21,tzinfo=timezone.utc))[0], date(2027,1,1))
        self.assertEqual(plan.resolve_date("2028-02-29")[0], date(2028,2,29))
        with self.assertRaises(ValueError): plan.resolve_date("2027-02-29")

    def test_naive_clock_fails(self):
        with self.assertRaises(DemoError): plan.resolve_date(now=datetime(2026,10,15))

    def test_current_day_keeps_all_registered_visits(self):
        source=example(); before=copy.deepcopy(source)
        result=plan.prepare_day(source,{},date(2026,10,15),date(2026,10,15),dict(zip(plan.CUSTOMERS,range(1,6))))
        self.assertEqual(result["status"],"NO_OP")
        self.assertEqual(result["proposed_insert_count"],0)
        self.assertEqual(source,before)

    def test_future_day_proposes_only_planned_inserts_preserves_old_active(self):
        result=plan.prepare_day(example(),{},date(2026,10,16),date(2026,10,15),{})
        self.assertEqual(result["proposed_insert_count"],0)
        self.assertEqual(result["unblocked_candidate_count"],4)
        self.assertEqual(result["visits"][1]["reason"],"OLDER_IN_PROGRESS_VISIT")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["warnings"][0]["visit_ids"],[2])

    def test_repeat_plan_is_identical(self):
        args=(example(),{},date(2026,10,16),date(2026,10,15),{})
        self.assertEqual(plan.prepare_day(*args),plan.prepare_day(*args))

    def test_registered_future_day_reuses_rows(self):
        source=example()
        for row in source["visits"]:row["date"]="2026-10-16"
        result=plan.prepare_day(source,{},date(2026,10,16),date(2026,10,15),dict(zip(plan.CUSTOMERS,range(1,6))))
        self.assertEqual(result["status"],"NO_OP")

    def test_completed_or_cancelled_is_preserved_not_reopened(self):
        for state in ("COMPLETED","CANCELLED"):
            source=example();source["visits"][0]["status"]=state
            result=plan.prepare_day(source,{},date(2026,10,15),date(2026,10,15),dict(zip(plan.CUSTOMERS,range(1,6))))
            self.assertEqual(result["visits"][0]["action"],"PRESERVE_CLOSED")
            self.assertEqual(result["status"],"BLOCKED")
            self.assertEqual(source["visits"][0]["status"],state)

    def test_duplicate_and_unregistered_visit_block(self):
        source=example();source["visits"].append({**source["visits"][0],"id":99})
        result=plan.prepare_day(source,{},date(2026,10,15),date(2026,10,15),{})
        self.assertEqual(result["visits"][0]["reason"],"DUPLICATE_DAY_VISITS")
        source=example()
        result=plan.prepare_day(source,{},date(2026,10,15),date(2026,10,15),{})
        self.assertEqual(result["visits"][0]["reason"],"UNREGISTERED_EXISTING_VISIT")

    def test_missing_registered_visit_and_assignment_block(self):
        source=example();source["visits"].pop(0)
        result=plan.prepare_day(source,{},date(2026,10,15),date(2026,10,15),{"C0003":1})
        self.assertEqual(result["visits"][0]["reason"],"REGISTERED_VISIT_MISSING_OR_CHANGED")
        source["customers"]["C0003"]["assigned"]=False
        result=plan.prepare_day(source,{},date(2026,10,16),date(2026,10,15),{})
        self.assertEqual(result["visits"][0]["reason"],"CUSTOMER_OR_ASSIGNMENT_UNAVAILABLE")

    def test_past_date_never_proposes_creation(self):
        result=plan.prepare_day(example(),{},date(2026,10,14),date(2026,10,15),{})
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["proposed_insert_count"],0)

    def test_wrong_database_endpoint_container_fail_before_connection(self):
        profile=load_profile()
        for key,value in (("database","sales_ai_db"),("database_port",5432),("host","localhost"),
                          ("container","sales-ai-postgres"),("volume","sales-ai_postgres_data")):
            with self.subTest(key=key),patch("psycopg.connect") as network:
                with self.assertRaises(DemoError):connect({**profile,key:value},DEFAULT_STATE)
                network.assert_not_called()

    def test_actual_container_id_mismatch_fails_before_db(self):
        profile=load_profile()
        with patch("psycopg.connect") as network:
            with self.assertRaises(DemoError):verify_container({**profile,"container_id":"incorrect"})
            network.assert_not_called()

    def test_actual_wrong_marker_and_oid_fail_readonly(self):
        profile=load_profile()
        for changes in ({"identity":"00000000-0000-0000-0000-000000000001"},{"database_oid":profile["database_oid"]+1}):
            with self.subTest(changes=changes),self.assertRaises(DemoError):connect({**profile,**changes},DEFAULT_STATE,readonly=True)

    def test_cli_cannot_execute_or_skip_dry_run(self):
        for args in (["reset"],["prepare-day"],["reset","--dry-run","--execute"],["reset","--dry-run","--confirm","yes"]):
            result=subprocess.run([sys.executable,"-B",str(ROOT/"scripts/demo/plan.py"),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)

    def test_real_readonly_plans_repeat_and_preserve_inventory(self):
        first=plan.build_plan("prepare-day","2026-10-15")
        second=plan.build_plan("prepare-day","2026-10-15")
        self.assertEqual(first,second)
        reset=plan.build_plan("reset","2026-10-16")
        self.assertFalse(reset["execution_available"])
        self.assertEqual(first["database_state_sha256"],reset["database_state_sha256"])
        self.assertEqual(reset["database_transaction"],"REPEATABLE READ / READ ONLY")
        self.assertTrue(all(t["current_rows_deleted"]==0 for t in reset["result"]["tables"]))
        self.assertIn("cannot be observed",reset["result"]["browser_risks"]["database_detection_limit"])


if __name__=="__main__":
    unittest.main(verbosity=2)
