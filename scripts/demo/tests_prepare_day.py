"""Prepare Day disposable-only fixtures and real-process safety probes.

Invoked by verify_generation_postgres.py --prepare-day. Never a Demo seeder.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4

from common import require, write_json, ROOT
from tests_maintenance_gate import MaintenanceTests, Child


def seed(case, state, identity, database):
    """Independent synthetic fixtures, not a copy/export of any existing DB."""
    from bootstrap import definition, record, digest, SCENARIOS, VERSION
    from plan import resolve_date
    from django.contrib.auth import get_user_model
    from apps.products.models import Brand, Category, Product, ProductDemoPrice
    from apps.products.demo_price_loader import apply_demo_prices
    from apps.inventory.models import Inventory
    from apps.customers.models import Customer, Customer360, CustomerGrade
    from apps.visits.models import Salesperson, CustomerAssignment, Visit
    from apps.recommendations.models import CustomerRecommendation
    day = resolve_date()[1] - timedelta(days=2)
    fixture = definition(day)
    records = []

    def insert(model, **fields):
        row = model(**fields); row.full_clean(); row.save(force_insert=True)
        records.append(record(model, row))
        return row

    case.password = secrets.token_urlsafe(40)
    users = []
    for name, staff in (('pd-salesperson', False), ('pd-manager', True), ('pd-unassigned', False)):
        user = get_user_model()(username=name, is_staff=staff, is_active=True)
        user.set_password(case.password); user.full_clean(); user.save(force_insert=True)
        records.append(record(get_user_model(), user)); users.append(user)
    case.user, case.staff, case.foreign_user = users
    case.rep = insert(Salesperson, employee_code='SP001', user=case.user, first_name='Test', last_name='Synthetic')
    grades = {c: insert(CustomerGrade, code=c, name='Synthetic '+c) for c in ('A','B','C')}
    brands, categories, products = {}, {}, {}
    for item in fixture['products']:
        brand, category, code = item['brand'], item['category'], item['code']
        if brand not in brands: brands[brand] = insert(Brand, code=brand.upper(), name=brand)
        if category not in categories:
            categories[category] = insert(Category, code='DEMO-'+category.upper().replace(' ','-'), name=category)
        products[code] = insert(Product, product_code=code, name=item['name'], brand=brands[brand],
            category=categories[category], unit=fixture['prices']['unit'], package_size=fixture['prices']['package_size'])
        if code != 'TEF003':
            insert(Inventory, product=products[code], available_quantity=0 if code=='ROW001' else 3 if code=='PHI004' else 25,
                   reserved_quantity=0 if code=='ROW001' else 2 if code=='PHI004' else 3)
    require(apply_demo_prices(expected_database=database)['created_count']==14,'Disposable price fixture mismatch.')
    records.extend(record(ProductDemoPrice,row) for row in ProductDemoPrice.objects.order_by('pk'))
    customers, visits, recommendations = {}, {}, []
    for code, grade, kind, name, scenario in SCENARIOS:
        customer = insert(Customer, customer_code=code, name=name, grade=grades[grade], customer_type=kind)
        customers[code] = customer
        insert(Customer360, customer=customer)
        insert(CustomerAssignment, customer=customer, salesperson=case.rep, start_date=day)
        visit = insert(Visit, customer=customer, salesperson=case.rep, visit_date=day, status='PLANNED')
        visits[code] = dict(id=visit.pk, customer_code=code, scenario=scenario)
        for rank, product in enumerate(('PHD001','BRN001','BOS002'),1):
            recommendations.append(insert(CustomerRecommendation, customer=customer, product=products[product],
                rank=rank, score=90-rank, recommendation_type='CATEGORY', reason='Synthetic rehearsal only'))
    case.customer = customers['C0003']; case.visit = Visit.objects.get(pk=visits['C0003']['id']); case.planned = case.visit
    case.products = [products['PHD001'],products['BOS001']]; case.recs = recommendations
    case.fixture_visits = visits
    case.target = (resolve_date()[1]+timedelta(days=2)).isoformat()
    manifest = dict(identity=identity, version=VERSION, phase='complete', preparation_date=day.isoformat(),
                    fixture=fixture, fixture_sha256=digest(fixture), records=records, visits=visits)
    (state/'fixtures').mkdir()
    path = state/'fixtures/manifest.json'; write_json(path,manifest)
    path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='ascii')


class PrepareDayTests(MaintenanceTests):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.clean_preparation)

    def clean_preparation(self):
        """Only this runner's disposable fixture teardown; never an operator reset."""
        from django.db import connections
        for child in self.children: child.close()
        self.children.clear(); connections.close_all()
        with self.raw() as raw:
            raw.execute('DELETE FROM sales_ai_demo_control.preparation_recoveries')
            raw.execute('DELETE FROM sales_ai_demo_control.prepared_days')
            raw.execute('DELETE FROM sales_ai_demo_control.results')
            raw.execute('DELETE FROM sales_ai_demo_control.operations')
            for table in ('recommendations_recommendationfeedbackevent','sales_requests_salesrequestmutationreceipt',
                          'sales_requests_salesrequestacknowledgement','sales_requests_salesrequestline',
                          'sales_requests_salesrequest','visits_visitcommercialsnapshot','visits_visitcustomersnapshot'):
                raw.execute('DELETE FROM '+table)
            ids = [v['id'] for v in self.fixture_visits.values()]
            raw.execute('DELETE FROM visits_visit WHERE NOT(id=ANY(%s))',[ids])
            raw.execute("UPDATE visits_visit SET status='PLANNED' WHERE id=ANY(%s)",[ids])
            raw.execute('UPDATE visits_customerassignment SET is_active=TRUE')
            directory = self.state_dir/'fixtures/prepared-days'
            # Retain all files (including failed-publication evidence) for audit.

    def plan(self, *, target=None, now=None):
        from scripts.demo.prepare_day import make_plan
        with self.raw() as raw:
            return make_plan(raw,self.profile,self.state_dir,target or self.target,now=now)

    def execute(self, plan, *, operation=None, recover=False, hook=lambda phase:None, now=None):
        from scripts.demo.prepare_day import execute_disposable, confirmation
        operation = operation or uuid4()
        return execute_disposable(self.raw(),self.profile,self.state_dir,target=plan['payload']['target'],plan=plan,
            operation=operation,confirm=confirmation(self.profile,operation,plan['fingerprint'],recover=recover),
            recover=recover,hook=hook,now=now)

    def public(self):
        from deploy_lock_capabilities import public_state
        with self.raw() as raw: return public_state(raw)

    def fixture_visit(self, target):
        """Owner-only disposable test fixture; runtime must NOT gain Visit INSERT."""
        from apps.visits.models import Visit
        with self.raw() as raw:
            pk=raw.execute("INSERT INTO visits_visit(salesperson_id,customer_id,visit_date,status,customer_request,"
                "customer_feedback,competitor_information,notes,order_created,order_amount,follow_up_required,follow_up_date,created_at,updated_at) "
                "VALUES(%s,%s,%s,'PLANNED','','','','',FALSE,0,FALSE,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING id",
                [self.rep.pk,self.customer.pk,target]).fetchone()[0]
        return Visit.objects.get(pk=pk)

    def preparation_child(self, plan, operation, pause, *, recover=False, expect_failure=False):
        child = Child(dict(profile=self.profile, connection=self.connection_values, passwords=self.passwords,
            state=str(self.state_dir), plan=plan, operation=str(operation), pause=pause, recover=recover,
            expect_failure=expect_failure),worker_file=__file__)
        self.children.append(child); return child

    def test_80_exact_five_and_canonical_replay(self):
        from scripts.demo.prepare_day import confirmation
        plan=self.plan(); before=self.public(); operation=uuid4()
        self.assertEqual(plan['payload']['assessment']['proposed_insert_count'],5)
        result=self.execute(plan,operation=operation)
        self.assertEqual(len(result['inserted_ids']),5)
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT status,count(*) FROM visits_visit WHERE id=ANY(%s) GROUP BY status',
                                        [result['inserted_ids']]).fetchall(),[('PLANNED',5)])
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone(),('ACTIVE',))
        after=self.public()
        self.assertEqual(before['tables']['visits_visit']['count']+5,after['tables']['visits_visit']['count'])
        self.assertEqual(self.execute(plan,operation=operation),result)
        self.assertEqual(self.public(),after)
        repeat=self.plan()
        self.assertEqual(repeat['payload']['assessment']['status'],'NO_OP')
        self.assertEqual(self.execute(repeat)['inserted_ids'],[])
        self.assertEqual(self.public(),after)
        with self.assertRaisesRegex(RuntimeError,'different preparation intent'):
            self.execute(repeat,operation=operation)

    def test_81_older_visit_policy_whole_batch_and_consumed_target(self):
        from scripts.demo.maintenance_gate import GateRefused
        for status in ('PLANNED','COMPLETED'):
            with self.raw() as raw:raw.execute('UPDATE visits_visit SET status=%s',[status])
            self.assertEqual(self.plan()['payload']['assessment']['proposed_insert_count'],5)
        with self.raw() as raw:raw.execute("UPDATE visits_visit SET status='IN_PROGRESS' WHERE id=%s",[self.fixture_visits['C0005']['id']])
        blocked=self.plan(); before=self.public()
        self.assertEqual(blocked['payload']['assessment']['status'],'BLOCKED')
        with self.assertRaisesRegex(GateRefused,'batch blocked'):self.execute(blocked)
        self.assertEqual(self.public(),before)
        with self.raw() as raw:raw.execute("UPDATE visits_visit SET status='COMPLETED'")
        result=self.execute(self.plan())
        with self.raw() as raw:raw.execute("UPDATE visits_visit SET status='COMPLETED' WHERE id=%s",[result['visits']['C0013']])
        consumed=self.plan()
        self.assertEqual(consumed['payload']['assessment']['status'],'BLOCKED')
        self.assertIn('PRESERVE_CLOSED',[r['action'] for r in consumed['payload']['assessment']['visits']])

    def test_82_partial_unregistered_and_stale_assignment(self):
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan()
        with self.raw() as raw:raw.execute('UPDATE visits_customerassignment SET is_active=FALSE WHERE customer_id=%s',[self.customer.pk])
        before=self.public()
        with self.assertRaisesRegex((GateRefused,RuntimeError),'changed|conflict'):self.execute(plan)
        self.assertEqual(self.public(),before)
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone()[0],'ACTIVE')

    def test_83_draft_history_preserved_and_pending_routes_rejected(self):
        self.client=self.login(self.user)
        start=self.send(f'/api/visits/v1/visits/{self.visit.pk}/start/')
        self.assertEqual(start.status_code,200)
        self.assertEqual(self.add().status_code,201)
        # An active older Visit blocks the entire batch, without changing Draft evidence.
        plan=self.plan();before=self.public()
        self.assertEqual(plan['payload']['assessment']['status'],'BLOCKED')
        self.assertEqual(self.public(),before)
        from tests_generation_postgres import endpoint_inventory
        from scripts.demo.maintenance_gate import ExclusiveGate
        raw=self.raw();gate=ExclusiveGate(raw,self.profile,uuid4());gate.announce()
        try:
            for route in endpoint_inventory():
                for method in route['methods']:
                    response=self.send(route['path'],method=method.lower())
                    self.assertEqual(response.status_code,503,route['name'])
            self.assertEqual(self.public(),before)
        finally:raw.close()

    def test_84_owner_crash_after_allocation_recovery(self):
        plan=self.plan();operation=uuid4();before=self.public()
        child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');child.close()
        allocated=self.public()
        self.assertEqual(allocated['tables'],before['tables'])
        result=self.execute(plan,operation=operation,recover=True)
        self.assertEqual(len(result['inserted_ids']),5)
        self.assertEqual(self.public()['sequences'],allocated['sequences'])

    def test_85_rollback_partial_insert_then_explicit_recovery(self):
        plan=self.plan();operation=uuid4();before=self.public()
        child=self.preparation_child(plan,operation,'inserted')
        self.assertEqual(child.read()['phase'],'inserted');child.close()
        self.assertEqual(self.public()['tables'],before['tables'])
        result=self.execute(plan,operation=operation,recover=True)
        self.assertEqual(len(result['inserted_ids']),5)

    def test_86_committed_response_lost_and_publication_interrupted(self):
        for pause in ('after_commit','publication_temporary'):
            plan=self.plan();operation=uuid4()
            child=self.preparation_child(plan,operation,pause)
            self.assertEqual(child.read()['phase'],pause);child.close()
            after=self.public()
            result=self.execute(plan,operation=operation)
            self.assertEqual(self.public(),after)
            self.assertTrue((self.state_dir/'fixtures/prepared-days'/f'{operation}.json').exists())
            self.assertEqual(result['operation'],str(operation))

    def test_87_competing_executor_and_live_owner_recovery_rejected(self):
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');before=self.public()
        with self.assertRaisesRegex(GateRefused,'still live'):self.execute(plan,operation=operation,recover=True)
        with self.assertRaisesRegex(GateRefused,'still live'):self.execute(plan)
        self.assertEqual(self.public(),before)
        child.send('continue');self.assertEqual(child.read()['phase'],'DONE');child.wait()

    def test_88_missing_and_tampered_journal_never_unlock(self):
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');child.close()
        with self.raw() as raw:raw.execute("UPDATE sales_ai_demo_control.prepared_days SET intent_sha='tampered' WHERE operation=%s",[operation])
        before=self.public()
        with self.assertRaisesRegex(GateRefused,'tampered'):self.execute(plan,operation=operation,recover=True)
        self.assertEqual(self.public(),before)
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone()[0],'PENDING')

    def test_89_clock_signature_and_target_fail_closed(self):
        from scripts.demo.maintenance_gate import GateRefused
        from plan import resolve_date
        with self.assertRaisesRegex(RuntimeError,'aware'):self.plan(now=datetime(2026,1,1))
        self.assertEqual(resolve_date(None,datetime(2026,1,1,20,29,tzinfo=timezone.utc))[1].isoformat(),'2026-01-01')
        self.assertEqual(resolve_date(None,datetime(2026,1,1,20,30,tzinfo=timezone.utc))[1].isoformat(),'2026-01-02')
        plan=self.plan();tampered=json.loads(json.dumps(plan));tampered['payload']['target']='2099-01-01'
        before=self.public()
        with self.assertRaisesRegex(GateRefused,'signature'):self.execute(tampered)
        self.assertEqual(self.public(),before)

    def test_90_published_tamper_and_runtime_journal_denial(self):
        import psycopg
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan();operation=uuid4();self.execute(plan,operation=operation)
        path=self.state_dir/'fixtures/prepared-days'/f'{operation}.json';path.write_text('{}',encoding='ascii')
        before=self.public()
        with self.assertRaisesRegex(GateRefused,'tampered'):self.execute(plan,operation=operation)
        self.assertEqual(self.public(),before)
        with self.raw(self.profile['runtime_role']) as raw:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):raw.execute('SELECT * FROM sales_ai_demo_control.prepared_days')
            raw.rollback()

    def test_91_before_allocation_and_before_commit_death(self):
        for phase in ('announced','before_commit'):
            # Each rehearsal uses a different future day, retaining earlier prepared rows.
            target=(datetime.fromisoformat(self.target).date()+timedelta(days=1 if phase=='before_commit' else 0)).isoformat()
            plan=self.plan(target=target);operation=uuid4();before=self.public()
            child=self.preparation_child(plan,operation,phase)
            self.assertEqual(child.read()['phase'],phase);child.close()
            self.assertEqual(self.public()['tables'],before['tables'])
            result=self.execute(plan,operation=operation,recover=True)
            self.assertEqual(len(result['inserted_ids']),5)

    def test_92_unjournalled_sequence_gap_never_adopted(self):
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'reserved')
        self.assertEqual(child.read()['phase'],'reserved');child.close()
        before=self.public()
        with self.assertRaisesRegex(GateRefused,'sequence state'):self.execute(plan,operation=operation,recover=True)
        self.assertEqual(self.public(),before)
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone()[0],'PENDING')

    def test_93_real_start_submit_completion_drain_and_stale_plan(self):
        from django.conf import settings
        from apps.visits.models import Visit
        for action in ('start','submit','completion'):
            if action!='start':
                # A future operational fixture avoids an older-IN_PROGRESS policy blocker.
                # Never change an original fixture's date or complete C0005.
                self.visit=self.fixture_visit(datetime.fromisoformat(self.target).date()+timedelta(days=1))
            self.client=self.login(self.user)
            if action!='start':
                self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/start/').status_code,200)
            body={}
            path=f'/api/visits/v1/visits/{self.visit.pk}/start/'
            if action=='submit':
                self.assertEqual(self.add().status_code,201)
                review=self.client.get(f'/api/sales-requests/v1/visits/{self.visit.pk}/review/',
                    dict(customer_code=self.customer.customer_code)).json()
                body=dict(customer_code=self.customer.customer_code,catalog_context=self.context(),command_uuid=str(uuid4()),
                    expected_request_revision=review['request']['revision'],accepted_review_fingerprint=review['review_fingerprint'])
                path=f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/'
            if action=='completion':
                path=f'/api/visits/v1/visits/{self.visit.pk}/completion/'
                body=dict(customer_code=self.customer.customer_code,command_uuid=str(uuid4()))
            client=self.child('http',mode_name='command',path=path,body=body,secret_key=settings.SECRET_KEY)
            self.assertEqual(client.read()['phase'],'LOGGED_IN')
            # Start from a plan captured before a real authenticated transaction is admitted.
            # Earlier loop's Start is explicitly completed, never silently resolved by preparation.
            plan=self.plan()
            self.assertEqual(plan['payload']['assessment']['status'],'READY_FOR_APPROVAL')
            client.send('go');view=client.read()
            self.assertEqual(view['phase'],'VIEW_DONE');self.assertIn(view['status'],(200,201))
            operation=uuid4();executor=self.preparation_child(plan,operation,'announced',expect_failure=True)
            self.assertEqual(executor.read()['phase'],'announced')
            with self.raw() as raw:
                self.assertEqual(raw.execute('SELECT state FROM sales_ai_demo_control.prepared_days WHERE operation=%s',[operation]).fetchone()[0],'PREPARING')
            executor.send('continue')
            self.assertTrue(executor.messages.empty())
            client.send('continue');self.assertIn(client.read()['status'],(200,201));client.wait()
            self.assertEqual(executor.read()['phase'],'REFUSED');executor.wait()
            with self.raw() as raw:
                self.assertEqual(raw.execute('SELECT count(*) FROM visits_visit WHERE visit_date=%s',[self.target]).fetchone()[0],0)
                self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone()[0],'PENDING')
                # Fixture teardown between independent race cases, NOT an operator recovery.
                raw.execute("UPDATE sales_ai_demo_control.admission SET phase='ACTIVE',operation=NULL,backend_pid=NULL,evidence_sha=NULL")
            if action=='start':
                # Explicit normal completion in the disposable fixture only.
                self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/completion/',
                    dict(customer_code=self.customer.customer_code,command_uuid=str(uuid4()))).status_code,200)
            if action=='submit':
                self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/completion/',
                    dict(customer_code=self.customer.customer_code,command_uuid=str(uuid4()))).status_code,200)

    def test_94_preserve_submitted_and_retained_draft_evidence(self):
        self.client=self.login(self.user)
        self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/start/').status_code,200)
        self.assertEqual(self.add().status_code,201)
        review=self.client.get(f'/api/sales-requests/v1/visits/{self.visit.pk}/review/',dict(customer_code=self.customer.customer_code)).json()
        command=dict(customer_code=self.customer.customer_code,catalog_context=self.context(),command_uuid=str(uuid4()),
            expected_request_revision=review['request']['revision'],accepted_review_fingerprint=review['review_fingerprint'])
        self.assertEqual(self.send(f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/',command).status_code,201)
        self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/completion/',
            dict(customer_code=self.customer.customer_code,command_uuid=str(uuid4()))).status_code,200)
        from apps.visits.models import Visit
        from apps.customers.models import Customer
        self.customer=Customer.objects.get(customer_code='C0014');self.visit=Visit.objects.get(pk=self.fixture_visits['C0014']['id'])
        self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/start/').status_code,200)
        self.assertEqual(self.add().status_code,201)
        self.assertEqual(self.send(f'/api/visits/v1/visits/{self.visit.pk}/completion/',
            dict(customer_code=self.customer.customer_code,command_uuid=str(uuid4()))).status_code,200)
        before=self.public();self.execute(self.plan());after=self.public()
        for table in before['tables']:
            if table!='visits_visit':self.assertEqual(before['tables'][table],after['tables'][table],table)
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT status,count(*) FROM sales_requests_salesrequest GROUP BY status ORDER BY status').fetchall(),
                             [('DRAFT',1),('SUBMITTED',1)])
            self.assertEqual(raw.execute('SELECT count(*) FROM sales_requests_salesrequestacknowledgement').fetchone()[0],1)
            self.assertEqual(raw.execute("SELECT count(*) FROM recommendations_recommendationfeedbackevent WHERE event_type='PURCHASED'").fetchone()[0],0)

    def test_95_partial_target_no_adoption_and_missing_journal(self):
        from apps.visits.models import Visit
        from scripts.demo.maintenance_gate import GateRefused
        row=self.fixture_visit(self.target)
        blocked=self.plan();before=self.public()
        self.assertEqual(blocked['payload']['assessment']['status'],'BLOCKED')
        self.assertIn('UNREGISTERED_EXISTING_VISIT',[v.get('reason') for v in blocked['payload']['assessment']['visits']])
        with self.assertRaises(GateRefused):self.execute(blocked)
        self.assertEqual(self.public(),before)
        with self.raw() as raw:raw.execute('DELETE FROM visits_visit WHERE id=%s',[row.pk])
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');child.close()
        with self.raw() as raw:raw.execute('DELETE FROM sales_ai_demo_control.prepared_days WHERE operation=%s',[operation])
        before=self.public()
        with self.assertRaisesRegex(GateRefused,'journal missing'):self.execute(plan,operation=operation,recover=True)
        self.assertEqual(self.public(),before)

    def test_96_midnight_rollover_rolls_back_then_stays_fenced(self):
        from scripts.demo.maintenance_gate import GateRefused
        from plan import resolve_date
        today=resolve_date()[1];clock=[datetime.combine(today,datetime.min.time(),timezone.utc)]
        plan=self.plan(now=lambda:clock[0]);operation=uuid4();before=self.public()
        def hook(phase):
            if phase=='before_commit':clock[0]+=timedelta(days=1)
        with self.assertRaisesRegex(GateRefused,'midnight'):self.execute(plan,operation=operation,now=lambda:clock[0],hook=hook)
        self.assertEqual(self.public()['tables'],before['tables'])
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT state FROM sales_ai_demo_control.prepared_days WHERE operation=%s',[operation]).fetchone()[0],'ALLOCATED')
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone()[0],'PENDING')

    def test_97_prepare_cannot_use_gate_only_release_or_recovery(self):
        from scripts.demo.maintenance_gate import GateRefused,ExclusiveGate
        from scripts.demo.gate_recovery import recover_disposable,confirmation
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');child.close()
        with self.raw() as raw:
            evidence=raw.execute('SELECT evidence_sha FROM sales_ai_demo_control.admission').fetchone()[0];raw.rollback()
            with self.assertRaisesRegex(GateRefused,'journal reconciliation'):
                recover_disposable(raw,self.profile,operation=operation,recovery_uuid=uuid4(),evidence_sha=evidence,
                    confirm=confirmation(self.profile,operation,evidence))

    def test_98_wrong_identity_and_zero_write_plan(self):
        from scripts.demo.prepare_day import make_plan
        from scripts.demo.maintenance_gate import GateRefused
        from generation import GenerationRefused
        before=self.public();self.plan();self.assertEqual(self.public(),before)
        for patch in ({'database':'sales_ai_demo_db'},{'database_port':5432},{'database_oid':0},{'identity':str(uuid4())}):
            with self.raw() as raw:
                with self.assertRaises((RuntimeError,GenerationRefused)):make_plan(raw,{**self.profile,**patch},self.state_dir,self.target)
        self.assertEqual(self.public(),before)

    def test_99_interrupted_recovery_and_missing_owner_claim(self):
        from scripts.demo.maintenance_gate import GateRefused
        plan=self.plan();operation=uuid4();child=self.preparation_child(plan,operation,'allocated')
        self.assertEqual(child.read()['phase'],'allocated');child.close()
        recovery=self.preparation_child(plan,operation,'announced',recover=True)
        self.assertEqual(recovery.read()['phase'],'announced');recovery.close()
        # A further explicit recovery follows the committed signed ownership chain.
        result=self.execute(plan,operation=operation,recover=True)
        self.assertEqual(len(result['inserted_ids']),5)
        before=self.public()
        with self.raw() as raw:raw.execute('DELETE FROM sales_ai_demo_control.preparation_recoveries WHERE operation=%s',[operation])
        with self.assertRaisesRegex(GateRefused,'evidence changed/missing'):self.execute(plan,operation=operation)
        self.assertEqual(self.public(),before)

    def test_100_column_grant_drift_rejected(self):
        from psycopg import sql
        from scripts.demo.prepare_day import make_plan
        from scripts.demo.maintenance_gate import GateRefused
        before=self.public()
        with self.raw() as raw:
            raw.execute(sql.SQL('GRANT UPDATE(intent_sha) ON sales_ai_demo_control.prepared_days TO {}')
                        .format(sql.Identifier(self.profile['runtime_role'])))
            try:
                with self.assertRaisesRegex(GateRefused,'runtime grants'):
                    make_plan(raw,self.profile,self.state_dir,self.target)
            finally:
                raw.execute(sql.SQL('REVOKE UPDATE(intent_sha) ON sales_ai_demo_control.prepared_days FROM {}')
                            .format(sql.Identifier(self.profile['runtime_role'])))
        self.assertEqual(self.public(),before)


def worker():
    values=json.loads(sys.stdin.readline())
    sys.path.insert(0,str(ROOT))
    import os, psycopg
    os.environ['DJANGO_SETTINGS_MODULE']='sales_ai_copilot.settings'
    from django.conf import settings
    profile=values['profile'];state=Path(values['state'])
    settings.DEMO_GENERATION_CONFIG={'profile':profile,'state':str(state)}
    def hook(phase):
        if phase==values['pause']:
            print(json.dumps(dict(phase=phase)),flush=True)
            require(sys.stdin.readline().strip()=='continue','Disposable worker interrupted.')
    from scripts.demo.prepare_day import execute_disposable,confirmation
    raw=psycopg.connect(**values['connection'],user=profile['owner_role'],password=values['passwords'][profile['owner_role']])
    try:
        result=execute_disposable(raw,profile,state,target=values['plan']['payload']['target'],plan=values['plan'],
            operation=values['operation'],recover=values['recover'],hook=hook,
            confirm=confirmation(profile,values['operation'],values['plan']['fingerprint'],recover=values['recover']))
    except RuntimeError:
        if not values.get('expect_failure'):raise
        print(json.dumps(dict(phase='REFUSED')),flush=True);return
    print(json.dumps(dict(phase='DONE',result=result)),flush=True)


if __name__=='__main__':worker()
