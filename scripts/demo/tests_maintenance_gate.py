"""B1 disposable-only cross-process probes; invoked by the B3 isolated runner."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
from threading import Thread
import unittest
from uuid import uuid4

from tests_generation_postgres import LiveGenerationTests


def probe_view(request):
    from django.http import HttpResponse, StreamingHttpResponse
    from django.db import transaction
    if not request.user.is_authenticated:
        return HttpResponse(status=403)
    request.session['maintenance_probe'] = 'persisted'
    if request.GET.get('mode') == 'callback':
        transaction.on_commit(lambda: None)
    if request.GET.get('mode') == 'stream':
        return StreamingHttpResponse(iter([b'unsupported']))
    return HttpResponse('probe', status=int(request.GET.get('status', '200')))


class Child:
    def __init__(self, values, *, worker_file=__file__):
        self.process = subprocess.Popen([sys.executable, '-B', str(Path(worker_file).resolve()), '--worker'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.messages = queue.Queue()
        def receive():
            for line in self.process.stdout:self.messages.put(line)
            self.messages.put(None)
        Thread(target=receive,daemon=True).start()
        self.send(json.dumps(values))

    def send(self, value):
        self.process.stdin.write(value + '\n'); self.process.stdin.flush()

    def read(self):
        try:
            line=self.messages.get(timeout=12)
            if line is None:raise AssertionError('Disposable child exited: '+self.process.stderr.read()[-1800:])
            return json.loads(line)
        except queue.Empty:
            raise AssertionError('Disposable child timed out; no automatic retry.') from None

    def wait(self):
        code = self.process.wait(timeout=12)
        if code:
            raise AssertionError('Disposable child failed: ' + self.process.stderr.read()[-1800:])

    def close(self):
        if self.process.poll() is None:
            self.process.kill(); self.process.wait(timeout=8)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


class MaintenanceTests(LiveGenerationTests):
    def setUp(self):
        from django.db import connections
        connections.close_all()
        self.children = []
        self.keys = []
        self.addCleanup(self.clean)

    def raw(self, role=None):
        import psycopg
        role = role or self.profile['owner_role']
        raw = psycopg.connect(**self.connection_values, user=role, password=self.passwords[role])
        from scripts.demo.maintenance_gate import identity
        with raw.cursor() as cursor:
            identity(cursor, self.profile, role)
        raw.rollback()
        return raw

    def clean(self):
        from django.db import connections
        for child in self.children:
            child.close()
        connections.close_all()
        # Independent TEST fixture cleanup, never a maintenance recovery command.
        with self.raw() as conn:
            conn.execute("UPDATE sales_ai_demo_control.admission SET phase='ACTIVE',operation=NULL,backend_pid=NULL,evidence_sha=NULL")
            for key in self.keys:
                conn.execute('DELETE FROM django_session WHERE session_key=%s', [key])

    def child(self, mode, **extra):
        values = dict(mode=mode, profile=self.profile, connection=self.connection_values,
            passwords=self.passwords, state=str(self.state_dir), username=self.user.username,
            password=self.password, **extra)
        child = Child(values); self.children.append(child)
        return child

    def count(self, key):
        with self.raw() as conn:
            return conn.execute('SELECT count(*) FROM django_session WHERE session_key=%s', [key]).fetchone()[0]

    def writer(self):
        child = self.child('exclusive')
        self.assertEqual(child.read()['phase'], 'PENDING')
        return child

    def test_40_cross_process_drain_commit_and_prevent_new_admission(self):
        key = 'gate-' + uuid4().hex; self.keys.append(key)
        reader = self.child('shared', key=key)
        self.assertEqual(reader.read()['phase'], 'ADMITTED')
        writer = self.writer()
        with self.raw(self.profile['runtime_role']) as raw:
            from scripts.demo.maintenance_gate import inspect, KEY
            raw.execute('SELECT pg_try_advisory_xact_lock_shared(%s,%s)', KEY)
            self.assertEqual(inspect(raw.cursor(), self.profile, self.profile['runtime_role'])[0], 'PENDING')
        self.assertEqual(self.count(key), 0)
        self.assertTrue(writer.messages.empty())
        reader.send('commit'); reader.wait()
        self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
        self.assertEqual(self.count(key), 1)
        writer.send('finish'); writer.wait()

    def test_41_rollback_and_worker_death_release_same_connection_lock(self):
        for action in ('rollback', 'crash'):
            key = 'gate-' + uuid4().hex; self.keys.append(key)
            reader = self.child('shared', key=key)
            self.assertEqual(reader.read()['phase'], 'ADMITTED')
            writer = self.writer()
            if action == 'crash':
                reader.close()
            else:
                reader.send(action); reader.wait()
            self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
            self.assertEqual(self.count(key), 0)
            writer.send('finish'); writer.wait()

    def test_42_owner_crash_leaves_durable_pending_and_no_takeover(self):
        writer = self.writer(); self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
        writer.close()
        from scripts.demo.maintenance_gate import ExclusiveGate, GateRefused
        with self.raw() as raw:
            gate = ExclusiveGate(raw, self.profile, uuid4())
            with self.assertRaises(GateRefused): gate.announce()
        client = self.child('http', mode_name='new')
        self.assertEqual(client.read(), {'status': 503, 'phase': 'LOGIN_BLOCKED'})
        client.wait()

    def test_43_runtime_cannot_change_fence_or_do_ddl(self):
        import psycopg
        for query in ("UPDATE sales_ai_demo_control.admission SET phase='ACTIVE'",
                      'DELETE FROM sales_ai_demo_control.admission',
                      'CREATE TABLE sales_ai_demo_control.hostile(id int)'):
            with self.raw(self.profile['runtime_role']) as raw:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege): raw.execute(query)

    def test_44_real_django_session_save_drains_before_exclusive(self):
        client = self.child('http', mode_name='pause')
        self.assertEqual(client.read()['phase'], 'LOGGED_IN')
        client.send('go')
        self.assertEqual(client.read()['phase'], 'SESSION_SAVE_PENDING')
        writer = self.writer()
        self.assertTrue(writer.messages.empty())
        client.send('continue')
        self.assertEqual(client.read(), {'phase': 'RESPONSE', 'status': 200, 'session_saved': True})
        client.wait()
        self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
        writer.send('finish'); writer.wait()

    def test_45_http_error_and_deferred_work_roll_back_session_changes(self):
        for mode in ('error', 'callback', 'stream'):
            client = self.child('http', mode_name=mode)
            self.assertEqual(client.read()['phase'], 'LOGGED_IN')
            client.send('go')
            result = client.read(); client.wait()
            self.assertEqual(result['status'], 400 if mode == 'error' else 503)
            self.assertFalse(result['session_saved'])

    def test_46_two_workers_drain_and_exclusive_timeout_remains_fenced(self):
        from scripts.demo.maintenance_gate import ExclusiveGate
        import psycopg
        readers = []
        for _ in range(2):
            key = 'gate-' + uuid4().hex; self.keys.append(key)
            child = self.child('shared', key=key); readers.append(child)
            self.assertEqual(child.read()['phase'], 'ADMITTED')
        with self.raw() as raw:
            gate = ExclusiveGate(raw, self.profile, uuid4()); gate.announce()
            raw.execute("SET lock_timeout='100ms'"); raw.commit()
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                with gate.exclusive(): self.fail('Must not acquire while requests are admitted')
        for reader in readers: reader.send('rollback'); reader.wait()
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone(), ('PENDING',))

    def test_47_identity_mismatch_and_missing_gate_fail_closed(self):
        from scripts.demo.maintenance_gate import inspect, GateRefused
        with self.raw(self.profile['runtime_role']) as raw:
            with self.assertRaises(GateRefused):
                inspect(raw.cursor(), {**self.profile, 'database_oid': self.profile['database_oid'] + 1}, self.profile['runtime_role'])
        from django.conf import settings
        chain = settings.MIDDLEWARE
        self.assertEqual(chain[0], 'scripts.demo.maintenance_gate.DemoMaintenanceMiddleware')
        self.assertLess(chain.index('scripts.demo.maintenance_gate.DemoMaintenanceMiddleware'),
                        chain.index('django.contrib.sessions.middleware.SessionMiddleware'))
        self.client = self.login(self.user)
        with self.raw() as raw:
            raw.execute('ALTER TABLE sales_ai_demo_control.admission RENAME TO admission_missing')
        try:
            self.assertEqual(self.client.get('/api/visits/').status_code, 503)
        finally:
            with self.raw() as raw:
                raw.execute('ALTER TABLE sales_ai_demo_control.admission_missing RENAME TO admission')

    def test_48_pending_blocks_all_direct_routes_before_domain_or_session_writes(self):
        from scripts.demo.maintenance_gate import ExclusiveGate
        self.client = self.login(self.user)
        before = self.state()
        with self.raw() as raw:
            gate = ExclusiveGate(raw, self.profile, uuid4()); gate.announce()
            for route in self.routes:
                for method in route['methods']:
                    with self.subTest(route=route['route'], method=method):
                        response = self.send(route['path'], method=method.lower())
                        self.assertEqual((response.status_code, response.json()['code']),
                                         (503, 'DEMO_MAINTENANCE_BLOCKED'))
            self.assertEqual(self.state(), before)
            with gate.exclusive(): pass

    def test_49_readiness_is_select_only_and_partial_grants_rejected(self):
        from scripts.demo.maintenance_gate import verify_ready, GateRefused
        from psycopg import sql
        with self.raw(self.profile['runtime_role']) as raw:
            raw.execute('SET TRANSACTION READ ONLY')
            verify_ready(raw,self.profile)
        with self.raw() as raw:
            raw.execute(sql.SQL('GRANT UPDATE(phase) ON sales_ai_demo_control.admission TO {}')
                        .format(sql.Identifier(self.profile['runtime_role'])))
        try:
            with self.raw(self.profile['runtime_role']) as raw:
                with self.assertRaises(GateRefused): verify_ready(raw,self.profile)
        finally:
            with self.raw() as raw:
                raw.execute(sql.SQL('REVOKE UPDATE(phase) ON sales_ai_demo_control.admission FROM {}')
                            .format(sql.Identifier(self.profile['runtime_role'])))

    def test_50_database_timeout_rolls_back_protected_write_before_drain(self):
        key = 'gate-' + uuid4().hex; self.keys.append(key)
        reader = self.child('shared', key=key)
        self.assertEqual(reader.read()['phase'], 'ADMITTED')
        writer = self.writer()
        reader.send('timeout')
        self.assertNotEqual(reader.process.wait(timeout=12), 0)
        self.assertIn('QueryCanceled', reader.process.stderr.read())
        self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
        self.assertEqual(self.count(key), 0)
        writer.send('finish'); writer.wait()

    def test_51_pending_between_lock_and_validation_never_admits_write(self):
        key = 'gate-' + uuid4().hex; self.keys.append(key)
        reader = self.child('shared', key=key, pause_before_validation=True)
        self.assertEqual(reader.read()['phase'], 'LOCKED_BEFORE_VALIDATION')
        writer = self.writer()
        self.assertTrue(writer.messages.empty())
        reader.send('continue')
        self.assertNotEqual(reader.process.wait(timeout=12), 0)
        self.assertIn('Pending maintenance', reader.process.stderr.read())
        self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
        self.assertEqual(self.count(key), 0)
        writer.send('finish'); writer.wait()

    def test_52_real_start_commit_or_response_failure_before_exclusive(self):
        for success in (False, True):
            client = self.child('http', mode_name='start' if success else 'start-fail',
                visit_id=self.planned.pk)
            self.assertEqual(client.read()['phase'], 'LOGGED_IN')
            client.send('go')
            self.assertEqual(client.read(), {'phase': 'VIEW_DONE', 'status': 200})
            writer = self.writer()
            with self.raw() as raw:
                self.assertEqual(raw.execute('SELECT status FROM visits_visit WHERE id=%s', [self.planned.pk]).fetchone(), ('PLANNED',))
                self.assertEqual(raw.execute('SELECT count(*) FROM visits_visitcustomersnapshot WHERE visit_id=%s', [self.planned.pk]).fetchone(), (0,))
            client.send('continue')
            self.assertEqual(client.read()['status'], 200 if success else 400)
            client.wait()
            self.assertEqual(writer.read()['phase'], 'EXCLUSIVE')
            with self.raw() as raw:
                self.assertEqual(raw.execute('SELECT status FROM visits_visit WHERE id=%s', [self.planned.pk]).fetchone(),
                                 ('IN_PROGRESS' if success else 'PLANNED',))
                for table in ('visits_visitcustomersnapshot', 'visits_visitcommercialsnapshot'):
                    self.assertEqual(raw.execute('SELECT count(*) FROM '+table+' WHERE visit_id=%s', [self.planned.pk]).fetchone(),
                                     (1 if success else 0,))
            writer.send('finish'); writer.wait()


def worker():
    values = json.loads(sys.stdin.readline()); profile = values['profile']
    # No inherited libpq routing; credentials travel over private stdin only.
    from common import clean_database_environment
    clean_database_environment()
    from django.conf import settings
    def say(**value): print(json.dumps(value), flush=True)
    if values['mode'] in ('shared', 'exclusive','pending-only','recovery'):
        settings.configure(DEMO_GENERATION_CONFIG={'profile':profile,'state':values['state']})
        import psycopg
        from scripts.demo.maintenance_gate import inspect, ExclusiveGate, KEY, require
        role = profile['runtime_role'] if values['mode'] == 'shared' else profile['owner_role']
        with psycopg.connect(**values['connection'],user=role,password=values['passwords'][role]) as raw:
            with raw.cursor() as cursor: inspect(cursor,profile,role)
            raw.rollback()
            if values['mode'] in ('exclusive','pending-only'):
                gate=ExclusiveGate(raw,profile,uuid4());gate.announce()
                digest=raw.execute('SELECT evidence_sha FROM sales_ai_demo_control.admission').fetchone()[0];raw.rollback()
                say(phase='PENDING',operation=str(gate.operation),evidence_sha=digest)
                if values['mode']=='pending-only':
                    assert sys.stdin.readline().strip()=='stop'
                    return
                with gate.exclusive():
                    say(phase='EXCLUSIVE');assert sys.stdin.readline().strip()=='finish'
            elif values['mode']=='recovery':
                from scripts.demo.gate_recovery import recover_disposable
                from scripts.demo.maintenance_gate import GateRefused
                def pause():
                    say(phase='RECOVERY_UNCOMMITTED')
                    assert sys.stdin.readline().strip()=='commit'
                try:
                    result=recover_disposable(raw,profile,operation=values['operation'],
                        recovery_uuid=values['recovery_uuid'],evidence_sha=values['evidence_sha'],confirm=values['confirm'],
                        _before_commit=pause if values.get('pause') else None)
                    say(phase='RECOVERED',result=result)
                except GateRefused as exc:say(phase='REFUSED',reason=str(exc))
            else:
                with raw.transaction():
                    raw.execute('SELECT pg_advisory_xact_lock_shared(%s,%s)',KEY)
                    if values.get('pause_before_validation'):
                        say(phase='LOCKED_BEFORE_VALIDATION');assert sys.stdin.readline().strip()=='continue'
                    require(inspect(raw.cursor(),profile,role)==('ACTIVE',None,None),'Pending maintenance')
                    raw.execute("INSERT INTO django_session(session_key,session_data,expire_date) VALUES(%s,'gate-probe',CURRENT_TIMESTAMP+INTERVAL '1 day')",[values['key']])
                    say(phase='ADMITTED');action=sys.stdin.readline().strip()
                    if action=='rollback':raise psycopg.Rollback()
                    if action=='timeout':
                        raw.execute("SET LOCAL statement_timeout='50ms'")
                        raw.execute('SELECT pg_sleep(1)')
                    assert action=='commit'
        return
    os.environ.update(DJANGO_SETTINGS_MODULE='sales_ai_copilot.settings', DB_ENGINE='postgresql',
        POSTGRES_DB=profile['database'],POSTGRES_HOST='127.0.0.1',POSTGRES_PORT='5433',
        POSTGRES_USER=profile['runtime_role'],POSTGRES_PASSWORD=values['passwords'][profile['runtime_role']])
    settings.ALLOWED_HOSTS=['localhost'];settings.CSRF_TRUSTED_ORIGINS=['http://localhost']
    settings.SECRET_KEY=values.get('secret_key') or __import__('secrets').token_urlsafe(48)
    settings.SESSION_ENGINE='django.contrib.sessions.backends.db'
    settings.ROOT_URLCONF=__name__
    import django
    django.setup()
    from django.urls import include,path
    global urlpatterns
    urlpatterns=[path('__gate_probe__/',probe_view),path('',include('sales_ai_copilot.urls'))]
    from scripts.demo import generation
    generation.install(profile,Path(values['state']))
    from django.db.backends.postgresql.base import DatabaseWrapper
    original=DatabaseWrapper.get_new_connection
    def guarded(wrapper,params):
        assert params['dbname']==profile['database'] and params['host']=='127.0.0.1' and str(params['port'])=='5433'
        assert params['user']==profile['runtime_role'] and not params.get('service') and not params.get('hostaddr')
        raw=original(wrapper,params)
        from scripts.demo.maintenance_gate import identity
        try:
            with raw.cursor() as cursor:identity(cursor,profile,profile['runtime_role'])
            raw.rollback();return raw
        except BaseException:raw.close();raise
    DatabaseWrapper.get_new_connection=guarded
    from django.test import Client
    import re
    client=Client(enforce_csrf_checks=True,HTTP_HOST='localhost',HTTP_ORIGIN='http://localhost')
    page=client.get('/accounts/login/')
    if page.status_code==503:
        say(phase='LOGIN_BLOCKED',status=503);return
    assert page.status_code==200
    proof=re.search(rb'data-demo-proof="([^"]+)"',page.content).group(1).decode()
    client.defaults['HTTP_X_DEMO_GENERATION_PROOF']=proof
    result=client.post('/accounts/login/',{'username':values['username'],'password':values['password'],
        'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
    assert result.status_code==302
    say(phase='LOGGED_IN');assert sys.stdin.readline().strip()=='go'
    from django.contrib.sessions.backends.db import SessionStore
    from unittest.mock import patch
    original_save=SessionStore.save
    def saving(session,*args,**kwargs):
        if values['mode_name']=='pause':
            say(phase='SESSION_SAVE_PENDING');assert sys.stdin.readline().strip()=='continue'
        return original_save(session,*args,**kwargs)
    suffix='?status=400' if values['mode_name']=='error' else '?mode='+values['mode_name']
    from django.contrib.sessions.middleware import SessionMiddleware
    original_response=SessionMiddleware.process_response
    def session_response(middleware,request,response):
        if values['mode_name'] in ('start','start-fail','command'):
            say(phase='VIEW_DONE',status=response.status_code)
            assert sys.stdin.readline().strip()=='continue'
            if values['mode_name']=='start-fail': response.status_code=400
        return original_response(middleware,request,response)
    target=f"/api/visits/v1/visits/{values['visit_id']}/start/" if values['mode_name'] in ('start','start-fail') else '/__gate_probe__/'+suffix
    if values['mode_name']=='command':target=values['path']
    with patch.object(SessionStore,'save',saving),patch.object(SessionMiddleware,'process_response',session_response):
        response=client.post(target,json.dumps(values.get('body',{})).encode(),content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
    say(phase='RESPONSE',status=response.status_code,session_saved=client.session.get('maintenance_probe')=='persisted')
    from django.db import connections
    connections.close_all()


if __name__=='__main__' and '--worker' in sys.argv:
    worker()
