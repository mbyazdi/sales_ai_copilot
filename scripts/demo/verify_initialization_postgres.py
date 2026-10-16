"""B9-A fresh initialization integration. Disposable DBs/independent roles only.

Worker remapping is confined to this test process, after exact live DB/OID/marker
and unique role/endpoint verification. It never relaxes a persistent launcher.
"""
import argparse
from datetime import date, timedelta
import hashlib
import json
import secrets
import shutil
import socket
import subprocess
from unittest.mock import patch
from uuid import uuid4

from common import *


def worker(config, action):
    import common as c
    import psycopg
    config=config.resolve()
    require(config.parent.parent == DEFAULT_STATE/'reports' and config.parent.name.startswith('b9a-'),
            'Worker configuration must be in the protected B9 artifact directory.')
    value=read_json(config);uid=value['uuid'];profile=value['profile'];state=config.parent
    # A source-only checkout has its OWN project root. The parent installation
    # is used solely for read-only container verification, never worker writes.
    installation_root=Path(value['installation_root']).resolve()
    with patch.object(c,'ROOT',installation_root):
        parent=c.load_profile()
    require(parent['identity']==value['parent_identity'],'Parent installation identity changed.')
    c.verify_container(parent)
    if value.get('clean_source'):
        require(ROOT.resolve()==(state/'checkout').resolve() and not (ROOT/'venv').exists()
                and not (ROOT/'.git').exists(),'Worker is not the isolated source-only checkout.')
        for relative,digest in value['source_files'].items():
            path=ROOT/relative
            require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,
                    'Source checkout fingerprint mismatch.')
    require(str(__import__('uuid').UUID(uid)) == uid and profile['database']=='test_stage3h3b9_'+uid.replace('-','')
            and profile['owner_role']=='sa_b9_owner_'+uid.replace('-','')
            and profile['runtime_role']=='sa_b9_runtime_'+uid.replace('-','')
            and profile['identity']==uid and profile['host']=='127.0.0.1' and profile['database_port']==5433,
            'Worker identity is not the exact disposable configuration.')
    clean_database_environment()
    password=(DEFAULT_STATE/'credentials/bootstrap-password.txt').read_text().strip()
    with psycopg.connect(host='127.0.0.1',port=5433,dbname=profile['database'],user=BOOTSTRAP,password=password) as conn:
        row=conn.execute("SELECT current_database(),d.oid,shobj_description(d.oid,'pg_database'),pg_get_userbyid(d.datdba) "
                         "FROM pg_database d WHERE datname=current_database()").fetchone()
        require(row==(profile['database'],profile['database_oid'],value['marker'],profile['owner_role']),
                'Live worker database identity mismatch.')
    # All imported script constants/connection fences now pin this ONE test DB.
    # No production credential, business fixture, password hash or runtime role is copied.
    c.DATABASE=profile['database'];c.OWNER=profile['owner_role'];c.RUNTIME=profile['runtime_role']
    c.DEFAULT_STATE=state;c.APP_PORT=profile['application_port']
    original_connect=c.connect
    original_configure=c.configure_django
    c.connect=lambda profile,state,role=None,readonly=True: original_connect(profile,state,role=role or c.RUNTIME,readonly=readonly)
    c.configure_django=lambda profile,state,role=None: original_configure(profile,state,role=role or c.RUNTIME)
    original_verify=c.verify_container
    c.verify_container=lambda *args,**kw: original_verify(parent)
    c.load_profile=lambda *args: c.validate_profile(read_json(state/'profile.json'),state)
    import lock_capabilities
    lock_capabilities.PERSISTENT_OWNER='sa_b9_cap_'+uid.replace('-','')
    original_validate=lock_capabilities.validate_runtime
    lock_capabilities.validate_runtime=lambda conn,profile,state,owner=None: original_validate(
        conn,profile,state,owner=owner or lock_capabilities.PERSISTENT_OWNER)
    import bootstrap, demo, deploy_lock_capabilities as deploy, initialization as init
    from plan import fingerprint

    if action=='migrate':
        c.configure_django(profile,state,c.OWNER)
        from django.core.management import call_command
        from django.db import connection,connections
        from django.db.migrations.loader import MigrationLoader
        keys=sorted([list(k) for k in MigrationLoader(connection).disk_migrations])
        require(len(keys)==50,'Unexpected migration graph.')
        profile['migration_keys']=keys;write_json(state/'profile.json',profile)
        call_command('migrate',interactive=False,verbosity=0)
        connections.close_all()
        from provision import grant_runtime
        with c.connect(profile,state,c.OWNER,readonly=False) as conn: grant_runtime(conn)
    elif action=='generation':
        with c.connect(profile,state,c.OWNER) as conn:
            require(init.register_generation(conn,profile,state)=='CREATED','Fresh registration failed.')
            before=(state/'generation-state.json').read_bytes()
            require(init.register_generation(conn,profile,state)=='NO_OP','Registration replay failed.')
            require((state/'generation-state.json').read_bytes()==before,'Registry was rewritten.')
    elif action=='caps':
        with deploy.maintenance(profile) as conn: before=deploy.public_state(conn)
        deploy.run('install',True)
        with deploy.maintenance(profile) as conn:
            require(deploy.public_state(conn)==before,'Capability installation changed public data/sequences.')
        deploy.run('install',True)
    elif action in {'bootstrap','repeat','conflict'}:
        original=subprocess.run
        def activation():
            return original([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(config),'activate'],
                            check=True,cwd=ROOT)
        day=date.fromisoformat(value['date'])
        with deploy.maintenance(profile) as conn: before=deploy.public_state(conn)
        if action=='conflict':
            try: bootstrap.bootstrap(day+timedelta(days=1))
            except DemoError: pass
            else: raise DemoError('Conflicting bootstrap date was accepted.')
        else:
            # Second clean environment simulates a different host's Demo day.
            with patch('django.utils.timezone.localdate',return_value=day),patch.object(bootstrap,'activate_initial',activation):
                bootstrap.bootstrap(day)
        if action in {'repeat','conflict'}:
            with deploy.maintenance(profile) as conn:
                require(deploy.public_state(conn)==before,'Repeat/conflict changed rows or sequences.')
    elif action=='activate':
        from initialize import activate
        activate(profile,state)
    elif action=='ready':
        demo.preflight(profile,state)
        from django.core.management import call_command
        call_command('makemigrations',check=True,dry_run=True,verbosity=0)
        with c.connect(profile,state) as conn:
            require(conn.execute("SELECT c.customer_code,v.status FROM visits_visit v JOIN customers_customer c ON c.id=v.customer_id ORDER BY c.customer_code").fetchall()
                    == [('C0003','PLANNED'),('C0005','IN_PROGRESS'),('C0013','PLANNED'),('C0014','PLANNED'),('C0029','PLANNED')],
                    'Fresh Visit lifecycle differs.')
            require(conn.execute('SELECT count(*) FROM visits_visitcustomersnapshot').fetchone()[0]==1
                    and conn.execute('SELECT count(*) FROM visits_visitcommercialsnapshot').fetchone()[0]==1,
                    'Authorized Start snapshots missing/duplicated.')
            require(conn.execute('SELECT count(*) FROM django_session').fetchone()[0]==0,'Activation session not invalidated.')
            for table in ['sales_requests_salesrequest','sales_requests_salesrequestline',
                          'sales_requests_salesrequestmutationreceipt','recommendations_recommendationfeedbackevent']:
                require(conn.execute('SELECT count(*) FROM '+table).fetchone()[0]==0,'Unexpected scenario writes.')
    elif action=='negative':
        with deploy.maintenance(profile) as conn: before=deploy.public_state(conn)
        def blocked():
            try: demo.preflight(profile,state)
            except (DemoError,ValueError,FileNotFoundError): return
            raise DemoError('Incomplete/mismatched initialization admitted startup.')
        for relative in ['generation-state.json','fixtures/manifest.json','lock-capabilities.json']:
            path=state/relative;data=path.read_bytes()
            try:
                path.unlink();blocked()
                path.write_text('{}',encoding='utf-8');blocked()
            finally: path.write_bytes(data)
        # Recomputed checksum cannot authorize foreign source/date/live identities.
        path=state/'fixtures/manifest.json';checksum=path.with_suffix('.sha256')
        saved=(path.read_bytes(),checksum.read_bytes())
        try:
            for key,val in [('identity',str(uuid4())),('fixture_sha256','0'*64),('phase','fixtures_committed'),
                            ('records',json.loads(saved[0])['records'][:-1])]:
                bad=json.loads(saved[0]);bad[key]=val;write_json(path,bad)
                checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='ascii');blocked()
                if key=='phase':
                    # Commit uncertainty must not cause a second legacy Start.
                    from initialize import activate
                    try: activate(profile,state)
                    except DemoError: pass
                    else: raise DemoError('Already-started incomplete activation was adopted.')
        finally: path.write_bytes(saved[0]);checksum.write_bytes(saved[1])
        # Equivalent Decimal scales/UTC offsets are accepted; real price changes
        # are still rejected, without rounding away differences.
        from decimal import Decimal
        from datetime import datetime, timezone
        path=state/'fixtures/manifest.json';checksum=path.with_suffix('.sha256')
        saved=(path.read_bytes(),checksum.read_bytes())
        try:
            equivalent=json.loads(saved[0])
            for record in equivalent['records']:
                if record['model']=='products.productdemoprice':
                    record['fields']['base_price']=format(Decimal(record['fields']['base_price']),'.2f')
                    for field in ('created_at','updated_at'):
                        stamp=datetime.fromisoformat(record['fields'][field].replace('Z','+00:00'))
                        record['fields'][field]=stamp.astimezone(timezone(timedelta(hours=3,minutes=30))).isoformat()
            write_json(path,equivalent)
            checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='ascii')
            with deploy.maintenance(profile) as conn: init.fixture_ready(conn,profile,state)
        finally: path.write_bytes(saved[0]);checksum.write_bytes(saved[1])
        with deploy.maintenance(profile,readonly=False) as conn:
            conn.execute('UPDATE products_productdemoprice SET base_price=base_price+1 WHERE id=(SELECT min(id) FROM products_productdemoprice)')
            try: init.fixture_ready(conn,profile,state)
            except DemoError: pass
            else: raise DemoError('Real fixture price change was ignored.')
            conn.rollback()
        # Simulate an interruption after schema, before registry publication:
        # nonempty data must never be adopted as a newly initialized generation.
        path=state/'generation-state.json';saved=path.read_bytes()
        try:
            path.unlink()
            with c.connect(profile,state,c.OWNER) as conn:
                try: init.register_generation(conn,profile,state)
                except DemoError: pass
                else: raise DemoError('Populated unregistered database was adopted.')
        finally: path.write_bytes(saved)
        with deploy.maintenance(profile) as conn:
            require(deploy.public_state(conn)==before,'Negative readiness tests changed data/sequences.')
    elif action=='preservation':
        # Existing populated installation, SELECT-only path; no old reports or
        # private Python are present in this source checkout.
        from preservation import installation_preservation, record_before, verify_before
        before=installation_preservation(profile,state)
        path=state/'existing-before.json'
        operation=record_before(path,profile,before,purpose='existing-read-only',state=state)
        require(verify_before(path,profile,purpose='existing-read-only',operation=operation,state=state)==before,
                'Existing baseline verification failed.')
        require(installation_preservation(profile,state)==before,'Read-only reconciliation changed state.')
        from tests_preservation import baseline_checks
        checks=baseline_checks(profile,state,before)
        write_json(state/'preservation-results.json',dict(checks=checks,existing_read_only=True,private_artifacts=False))
    elif action=='incomplete':
        try: demo.preflight(profile,state)
        except DemoError: pass
        else: raise DemoError('Incomplete installation admitted startup.')
    else: raise DemoError('Unknown worker action.')
    from django.conf import settings
    if settings.configured:
        from django.db import connections
        connections.close_all()
    print('B9-A '+action+': PASS')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path);parser.add_argument('action',nargs='?')
    parser.add_argument('--environments',type=int,choices=[1,2],default=2)
    parser.add_argument('--clean-source',action='store_true',help='Run workers from a source-only copy, without Git/venv/private reports.')
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.action);return
    import psycopg
    from psycopg import sql
    from preservation import preservation, record_before, verify_before
    from plan import fingerprint, resolve_date
    parent=load_profile();verify_container(parent);before=preservation(parent)
    evidence=DEFAULT_STATE/'reports'/('b9b-initialization-'+uuid4().hex);evidence.mkdir()
    operation=record_before(evidence/'before.json',parent,before,purpose='initialization-tests')
    clean_database_environment()
    operator=dict(host='127.0.0.1',port=5433,dbname='postgres',user=BOOTSTRAP,
                  password=(DEFAULT_STATE/'credentials/bootstrap-password.txt').read_text().strip())
    results=[]
    for offset in range(args.environments):
        uid=str(uuid4());suffix=uid.replace('-','');name='test_stage3h3b9_'+suffix
        owner='sa_b9_owner_'+suffix;runtime='sa_b9_runtime_'+suffix;cap='sa_b9_cap_'+suffix
        state=DEFAULT_STATE/'reports'/('b9a-'+suffix);state.mkdir()
        for directory in ('credentials','run','reports'): (state/directory).mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        marker=json.dumps(dict(kind='sales-ai-isolated-demo',identity=uid),sort_keys=True)
        with psycopg.connect(**operator,autocommit=True) as control:
            require(control.execute('SELECT current_database(),current_user,inet_server_port()').fetchone()
                    ==('postgres',BOOTSTRAP,5432),'Operator endpoint differs.')
            oid=None
            try:
                for role,filename in [(owner,'owner.json'),(runtime,'runtime.json')]:
                    password=secrets.token_urlsafe(48)
                    control.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}')
                                    .format(sql.Identifier(role),sql.Literal(password)))
                    write_json(state/'credentials'/filename,dict(host='127.0.0.1',port=5433,database=name,user=role,password=password))
                control.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name),sql.Identifier(owner)))
                oid=control.execute('SELECT oid FROM pg_database WHERE datname=%s',[name]).fetchone()[0]
                control.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(name),sql.Literal(marker)))
                control.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
                control.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(name),sql.Identifier(runtime)))
                with psycopg.connect(**{**operator,'dbname':name}) as raw:
                    raw.execute(sql.SQL('ALTER SCHEMA public OWNER TO {}').format(sql.Identifier(owner)))
                    raw.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
                for filename in ('django-secret.key','control-token.key'):
                    (state/'credentials'/filename).write_text(secrets.token_urlsafe(64),encoding='utf-8')
                (state/'credentials/bootstrap-password.txt').write_text(operator['password'],encoding='utf-8')
                profile={**parent,'database':name,'database_oid':oid,'identity':uid,'owner_role':owner,'runtime_role':runtime,
                         'state_root':str(state),'application_port':port,'url':f'http://localhost:{port}',
                         'listen':f'127.0.0.1:{port}','migration_keys':[]}
                source_files={}
                worker_script=Path(__file__).resolve();worker_root=ROOT
                if args.clean_source:
                    worker_root=state/'checkout';worker_root.mkdir()
                    # Public source only. No source DB, .env, Git state, private
                    # artifacts, password hashes or existing runtime state.
                    tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
                    # Tracked static images are required by the real bootstrap's
                    # asset-availability guard, not optional test decoration.
                    allowed=[p for p in tracked if p!='db.sqlite3' and not p.startswith(('.git/','venv/'))
                             and p!='docs/checkpoints/DEMO_02_VISUAL_ASSET_SELECTION_APPROVAL.md']
                    allowed+= [p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts/demo').iterdir() if p.is_file()]
                    allowed+=['apps/core/reference_locks.py','apps/core/sql/reference_locks_v1.sql']
                    for relative in sorted(set(allowed)):
                        original=ROOT/relative;target=worker_root/relative
                        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
                        source_files[relative]=hashlib.sha256(target.read_bytes()).hexdigest()
                    worker_script=worker_root/'scripts/demo/verify_initialization_postgres.py'
                    profile['project_root']=str(worker_root)
                write_json(state/'profile.json',profile)
                config=state/'worker.json'
                write_json(config,dict(uuid=uid,profile=profile,marker=marker,date=(resolve_date()[0]+timedelta(days=offset)).isoformat(),
                    installation_root=str(ROOT),parent_identity=parent['identity'],clean_source=args.clean_source,source_files=source_files))
                steps=['migrate','incomplete','generation','incomplete','caps','incomplete','bootstrap','repeat','conflict','ready','negative','preservation']
                for index,action in enumerate(steps):
                    run=subprocess.run([sys.executable,'-B',str(worker_script),'--worker',str(config),action],
                                       cwd=worker_root,capture_output=True,text=True,timeout=90)
                    (state/f'{index:02d}-{action}.log').write_text(run.stdout+run.stderr,encoding='utf-8')
                    require(run.returncode==0,'B9-A '+action+' failed; inspect protected report '+str(state))
                    if action=='migrate':
                        config_data=read_json(config);config_data['profile']=read_json(state/'profile.json');write_json(config,config_data)
                results.append(dict(database=name,date=read_json(config)['date'],steps=len(steps),passed=True,evidence=str(state)))
                write_json(state/'results.json',results[-1])
            finally:
                if oid is not None:
                    require(control.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",[name]).fetchone()==(oid,marker),'Cleanup identity changed.')
                    require(control.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s',[name]).fetchone()[0]==0,'Test connections remain.')
                    control.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
                for role in (cap,runtime,owner):
                    if control.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[role]).fetchone():
                        control.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
                write_json(state/'cleanup.json',dict(database=name,removed=True,roles_removed=True))
    after=preservation(parent)
    require(verify_before(evidence/'before.json',parent,purpose='initialization-tests',operation=operation)==before,
            'Original initialization-test evidence changed.')
    require(before==after,'Persistent preservation changed during initialization tests.')
    write_json(evidence/'after.json',after)
    print(json.dumps(dict(environments=results,steps_passed=sum(r['steps'] for r in results),persistent_preservation=True,clean_source=args.clean_source)))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('B9-A validation stopped: '+(str(exc) if isinstance(exc,DemoError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
