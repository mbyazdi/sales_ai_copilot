"""H4-B6 disposable-only readiness and legacy/V2 identity isolation probes.

Invoked by verify_generation_postgres.py --control-bundle. The runtime created by
that runner is the independent V2 identity; the legacy/canary identities below
are new UUID-scoped roles, never existing Demo roles. Secrets use private stdin.
"""
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4

from tests_maintenance_gate import MaintenanceTests, Child


class ControlBundleTests(MaintenanceTests):
    def bundle(self, raw, **options):
        from scripts.demo.control_bundle import inspect
        return inspect(raw.cursor(),self.profile,raw.info.user,**options)

    def test_110_complete_bundle_readonly_and_shared_startup_inspector(self):
        from scripts.demo.maintenance_gate import verify_ready
        from scripts.demo.gate_readiness import worker_signature
        from scripts.demo.gate_recovery import business_digest
        with self.raw() as raw:before=business_digest(raw)
        with self.raw(self.profile['runtime_role']) as raw:
            raw.execute('SET TRANSACTION READ ONLY')
            result=verify_ready(raw,self.profile)
            self.assertTrue(result['serving_ready'])
            self.assertEqual(result,self.bundle(raw,serving=True))
            self.assertEqual(result['contract_sha256'],worker_signature()['contract_sha256'])
        with self.raw() as raw:self.assertEqual(business_digest(raw),before)

    def test_111_each_missing_table_refuses_without_repair(self):
        from scripts.demo.control_bundle import TABLES
        from scripts.demo.maintenance_gate import GateRefused,verify_ready
        for table in TABLES:
            with self.subTest(table=table),self.raw() as raw:
                # Rename, not DROP/CASCADE: valid original OIDs restored by rollback.
                raw.execute('ALTER TABLE sales_ai_demo_control.'+table+' RENAME TO b6_missing')
                with self.assertRaises(GateRefused):self.bundle(raw)
                raw.rollback()
        with self.raw(self.profile['runtime_role']) as raw:verify_ready(raw,self.profile)

    def test_112_structural_tampering_and_column_acl_refuse(self):
        from scripts.demo.maintenance_gate import GateRefused
        from psycopg import sql
        statements=[
            'ALTER TABLE sales_ai_demo_control.results DROP CONSTRAINT results_operation_fkey',
            'DROP INDEX sales_ai_demo_control.prepared_day_identity',
            'ALTER TABLE sales_ai_demo_control.prepared_days ALTER COLUMN intent_sha DROP NOT NULL',
            'ALTER TABLE sales_ai_demo_control.operations ALTER COLUMN created_at DROP DEFAULT',
            'ALTER TABLE sales_ai_demo_control.admission DROP CONSTRAINT admission_check',
            'GRANT SELECT ON sales_ai_demo_control.operations TO PUBLIC',
            sql.SQL('GRANT UPDATE(intent_sha) ON sales_ai_demo_control.prepared_days TO {}').format(sql.Identifier(self.profile['runtime_role'])),
            sql.SQL('GRANT SELECT(envelope) ON sales_ai_demo_control.results TO {}').format(sql.Identifier(self.profile['runtime_role'])),
            sql.SQL('GRANT SELECT ON sales_ai_demo_control.admission TO {} WITH GRANT OPTION').format(sql.Identifier(self.profile['runtime_role'])),
            sql.SQL('GRANT CREATE ON SCHEMA sales_ai_demo_control TO {}').format(sql.Identifier(self.profile['runtime_role'])),
        ]
        for statement in statements:
            with self.subTest(statement=str(statement)),self.raw() as raw:
                raw.execute(statement)
                with self.assertRaises(GateRefused):self.bundle(raw)
                raw.rollback()

    def test_113_identity_version_generation_source_and_owner_refuse(self):
        from scripts.demo import control_bundle
        from scripts.demo.maintenance_gate import GateRefused
        from unittest.mock import patch
        from psycopg import sql
        for changed in ({'identity':str(uuid4())},{'database_oid':0},{'database':'sales_ai_db'},
                        {'owner_role':self.profile['runtime_role']}, {'gate_test_marker':'wrong'}):
            with self.raw() as raw,self.assertRaises(GateRefused):
                control_bundle.inspect(raw.cursor(),{**self.profile,**changed},raw.info.user)
        for statement,parameters in [
            ("UPDATE sales_ai_demo_control.admission SET version='wrong'",None),
            ('UPDATE sales_ai_demo_control.admission SET generation=%s',[uuid4()]),
            (sql.SQL('ALTER TABLE sales_ai_demo_control.results OWNER TO {}').format(sql.Identifier(self.profile['runtime_role'])),None),
        ]:
            with self.raw() as raw:
                # Ownership change needs a narrowly scoped disposable superuser.
                if not isinstance(statement,str):
                    raw.rollback()
                    from common import BOOTSTRAP
                    with self.probe(BOOTSTRAP) as admin:
                        admin.execute(statement)
                        with self.assertRaises(GateRefused):self.bundle(admin)
                        admin.rollback()
                else:
                    raw.execute(statement,parameters)
                    with self.assertRaises(GateRefused):self.bundle(raw)
                    raw.rollback()
        with self.raw() as raw,patch.dict(control_bundle.LOADED_SOURCES,{'prepare_day.py':'0'*64}),self.assertRaises(GateRefused):self.bundle(raw)
        with self.raw() as raw,patch.object(control_bundle,'LOADED_CONTRACT_SHA256','0'*64),self.assertRaises(GateRefused):self.bundle(raw)

    def test_114_pending_inspectable_but_never_serving_ready(self):
        from scripts.demo.maintenance_gate import verify_ready,GateRefused
        writer=self.writer()
        with self.raw(self.profile['runtime_role']) as raw:
            result=self.bundle(raw)
            self.assertEqual(result['phase'],'PENDING');self.assertFalse(result['serving_ready'])
            with self.assertRaises(GateRefused):verify_ready(raw,self.profile)
        self.assertEqual(writer.read()['phase'],'EXCLUSIVE')
        writer.send('finish');writer.wait()

    def test_115_retired_legacy_existing_backend_reconnect_and_unrelated_isolation(self):
        import psycopg
        from psycopg import sql
        from common import BOOTSTRAP
        from scripts.demo.gate_recovery import business_digest
        from scripts.demo.maintenance_gate import identity
        suffix=uuid4().hex
        legacy='sa_h4b6_legacy_'+suffix;other='sa_h4b6_other_'+suffix
        other_db='test_stage3h4b6_other_'+suffix;marker='h4b6-unrelated:'+suffix
        password=secrets.token_urlsafe(48);other_password=secrets.token_urlsafe(48)
        admin=self.probe(BOOTSTRAP);admin.autocommit=True
        created=[];child=None;other_oid=None
        try:
            # These operations are intentionally not a persistent deployment tool.
            with admin.cursor() as cursor:identity(cursor,self.profile,BOOTSTRAP)
            self.assertTrue(self.profile['database'].startswith('test_stage3h3b3_'))
            for role,secret in ((legacy,password),(other,other_password)):
                self.assertIsNone(admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[role]).fetchone())
                admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}')
                              .format(sql.Identifier(role),sql.Literal(secret)));created.append(role)
            admin.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0').format(sql.Identifier(other_db),sql.Identifier(other)))
            other_oid=admin.execute('SELECT oid FROM pg_database WHERE datname=%s',[other_db]).fetchone()[0]
            admin.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(other_db),sql.Literal(marker)))
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(other_db)))
            admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(self.profile['database']),sql.Identifier(legacy)))
            import provision
            from unittest.mock import patch
            with patch.object(provision,'RUNTIME',legacy):provision.grant_runtime(admin)
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA sales_ai_locks TO {}').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA sales_ai_locks TO {}').format(sql.Identifier(legacy)))
            # Independent canary DB has its own account and persistent-in-test row.
            canary_values={**self.connection_values,'dbname':other_db,'user':other,'password':other_password}
            with psycopg.connect(**canary_values) as raw:
                self.assertEqual(raw.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database') FROM pg_database d WHERE datname=current_database()").fetchone(),(other_db,other,other_oid,marker))
                raw.execute('CREATE TABLE canary(id integer PRIMARY KEY,value text NOT NULL)')
                raw.execute("INSERT INTO canary VALUES(1,'unchanged')")
            with self.raw() as raw:before=business_digest(raw)
            key='legacy-'+suffix
            values=dict(profile=self.profile,connection=self.connection_values,role=legacy,password=password,key=key)
            child=Child(values,worker_file=__file__);self.children.append(child)
            ready=child.read();self.assertEqual(ready['phase'],'LEGACY_UNCOMMITTED')
            pid=ready['pid'];backend_start=ready['backend_start']
            # Disable reconnection AND revoke write authority. Neither ends an
            # existing transaction or retroactively cancels an executing command.
            admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM {}').format(sql.Identifier(self.profile['database']),sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE UPDATE(last_login,password) ON auth_user FROM {}').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA sales_ai_locks FROM {}').format(sql.Identifier(legacy)))
            self.assertEqual(admin.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' AND (has_table_privilege(%s,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') "
                "OR has_any_column_privilege(%s,c.oid,'INSERT,UPDATE,REFERENCES'))",[legacy,legacy]).fetchone(),(0,))
            with self.assertRaises(psycopg.OperationalError):psycopg.connect(**self.connection_values,user=legacy,password=password)
            row=admin.execute('SELECT datname,usesysid::regrole::text,backend_start::text FROM pg_stat_activity WHERE pid=%s',[pid]).fetchone()
            self.assertEqual(row,(self.profile['database'],legacy,backend_start))
            # Exact test backend identity rechecked immediately before termination.
            self.assertTrue(admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid=%s AND datid=%s AND usename=%s AND backend_start::text=%s',
                [pid,self.profile['database_oid'],legacy,backend_start]).fetchone()[0])
            child.send('check');self.assertEqual(child.read()['phase'],'TERMINATED');child.wait()
            self.assertEqual(admin.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND usename=%s',[self.profile['database'],legacy]).fetchone(),(0,))
            self.assertEqual(admin.execute('SELECT count(*) FROM pg_prepared_xacts WHERE database=%s',[self.profile['database']]).fetchone(),(0,))
            # Even explicitly re-enabling LOGIN in this TEST does not recover DML
            # after reconnect: CONNECT alone is not restoration of write authority.
            admin.execute(sql.SQL('ALTER ROLE {} LOGIN').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(self.profile['database']),sql.Identifier(legacy)))
            with psycopg.connect(**self.connection_values,user=legacy,password=password) as raw:
                self.assertEqual(raw.execute('SELECT current_user').fetchone(),(legacy,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):raw.execute('DELETE FROM django_session WHERE session_key=%s',[key])
                raw.rollback()
            admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN').format(sql.Identifier(legacy)))
            with self.raw() as raw:self.assertEqual(business_digest(raw),before)
            with self.raw(self.profile['runtime_role']) as raw:
                self.assertTrue(self.bundle(raw,serving=True)['serving_ready'])
                for statement in ('CREATE TABLE public.denied(id integer)',
                    'UPDATE products_productdemoprice SET base_price=base_price',
                    'UPDATE recommendations_recommendationfeedbackevent SET reason_code=reason_code',
                    'DELETE FROM sales_requests_salesrequestmutationreceipt',
                    'SELECT * FROM sales_ai_demo_control.prepared_days',
                    'UPDATE sales_ai_demo_control.admission SET phase=phase'):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):raw.execute(statement)
                    raw.rollback()
            # Durable structured test evidence, excluding secrets and row payloads.
            from common import write_json
            write_json(self.state_dir/'writer-isolation.json',dict(database=self.profile['database'],
                legacy_role=legacy,v2_runtime=self.profile['runtime_role'],maintenance_owner=self.profile['owner_role'],
                terminated_test_backend=pid,retired_backends=0,reconnect_denied=True,
                reconnect_with_test_only_connect_restored_has_no_dml=True,business_digest_unchanged=True,
                unrelated_database=other_db,unrelated_role=other))
            with psycopg.connect(**canary_values) as raw:
                self.assertEqual(raw.execute('SELECT * FROM canary').fetchall(),[(1,'unchanged')])
                raw.execute("UPDATE canary SET value=value WHERE id=1")
                self.assertEqual(raw.execute('SELECT current_user').fetchone(),(other,))
        finally:
            if child:child.close()
            if other_oid:
                self.assertEqual(admin.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",[other_db]).fetchone(),(other_oid,marker))
                self.assertEqual(admin.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s',[other_db]).fetchone(),(0,))
                admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(other_db)))
            for role in reversed(created):
                # All owned objects are disposable and already removed/rolled back.
                admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
                admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
            admin.close()


def legacy_worker():
    import psycopg
    from common import clean_database_environment
    clean_database_environment()
    values=json.loads(sys.stdin.readline());profile=values['profile']
    assert profile['database'].startswith('test_stage3h3b3_')
    assert values['role'].startswith('sa_h4b6_legacy_')
    raw=psycopg.connect(**values['connection'],user=values['role'],password=values['password'])
    try:
        from scripts.demo.maintenance_gate import identity
        with raw.cursor() as cursor:identity(cursor,profile,values['role'])
        pid,start=raw.execute('SELECT pg_backend_pid(),backend_start::text FROM pg_stat_activity WHERE pid=pg_backend_pid()').fetchone()
        raw.execute("INSERT INTO django_session VALUES(%s,'never-committed',CURRENT_TIMESTAMP+INTERVAL '1 day')",[values['key']])
        print(json.dumps(dict(phase='LEGACY_UNCOMMITTED',pid=pid,backend_start=start)),flush=True)
        assert sys.stdin.readline().strip()=='check'
        try:raw.execute('SELECT 1')
        except psycopg.OperationalError:print(json.dumps(dict(phase='TERMINATED')),flush=True)
        else:raise AssertionError('Exact retired TEST backend still live')
    finally:raw.close()


if __name__=='__main__':legacy_worker()
