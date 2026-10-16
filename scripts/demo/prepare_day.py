"""Signed Prepare Day protocol. Executable ONLY in verified disposable PostgreSQL.

The DB journal is authoritative. Filesystem publication is a verifiable copy,
never the source of command success, registration or permission to release a gate.
"""
from datetime import date
import hashlib
import hmac
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from django.conf import settings
from psycopg.types.json import Jsonb

from scripts.demo.maintenance_gate import ExclusiveGate, KEY, OWNER_KEY, TABLE, inspect, require
from scripts.demo.gate_recovery import canonical, sha
from plan import CUSTOMERS, prepare_day, resolve_date

JOURNAL = 'sales_ai_demo_control.prepared_days'
FORMAT = 'PREPARE_DAY_V1'
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def is_preparation(raw,operation):
    if raw.execute('SELECT to_regclass(%s)',[JOURNAL]).fetchone()[0] is None:return False
    return raw.execute('SELECT 1 FROM '+JOURNAL+' WHERE operation=%s',[operation]).fetchone() is not None


def binding(profile):
    from scripts.demo.gate_recovery import binding as gate_binding
    return {**gate_binding(profile),'purpose':FORMAT,'prepare_source':{
        name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('prepare_day.py','plan.py','initialization.py','bootstrap.py','lock_capabilities.py')}}


def sign(payload,state):
    secret=(state/'credentials/control-token.key').read_bytes().strip()
    require(len(secret)>=48,'Preparation signing key unavailable.')
    return dict(payload=payload,signature=hmac.new(secret,b'prepare-day-v1\0'+canonical(payload),hashlib.sha256).hexdigest())


def verify(envelope,state):
    require(isinstance(envelope,dict) and isinstance(envelope.get('payload'),dict),'Missing signed preparation evidence.')
    require(hmac.compare_digest(str(envelope.get('signature','')),sign(envelope['payload'],state)['signature']),
            'Preparation signature mismatch.')
    return envelope['payload']


def context(raw,profile,state):
    from common import DEFAULT_STATE,verify_container,migration_fingerprint,read_json
    from generation import validate_registry
    from initialization import fixture_ready
    from lock_capabilities import validate_runtime
    require(profile['database'].startswith('test_stage3h3b3_') and
            profile.get('gate_test_marker')=='sales-ai-demo-b3-disposable:'+profile['identity'],
            'Prepare Day writes/validation require the exact disposable identity.')
    cluster=read_json(DEFAULT_STATE/'profile.json')
    require(cluster.get('database')=='sales_ai_demo_db' and cluster.get('owner_role')=='sales_ai_demo_owner'
            and cluster.get('runtime_role')=='sales_ai_demo_runtime','Protected Demo cluster profile mismatch.')
    verify_container(cluster)
    require(all(profile[k]==cluster[k] for k in ('host','database_port','container','container_id','image_id','volume')),
            'Disposable container/endpoint identity mismatch.')
    require(Path(state).resolve()==Path(settings.DEMO_GENERATION_CONFIG['state']).resolve(),'Preparation state root mismatch.')
    validate_registry(read_json(state/'generation-state.json'),profile,read_json(state/'profile.json'))
    from scripts.demo.control_bundle import inspect as inspect_bundle
    with raw.cursor() as cursor:inspect_bundle(cursor,profile,profile['owner_role'])
    migrations=[list(r) for r in raw.execute('SELECT app,name FROM django_migrations ORDER BY app,name')]
    require(migrations==profile['migration_keys'] and migration_fingerprint()==(50,profile['migration_fingerprint']),
            'Preparation migration drift.')
    validate_runtime(raw,profile,state,owner=profile['capability_owner'])
    return fixture_ready(raw,profile,state)


def install_disposable(raw,profile):
    from scripts.demo.maintenance_gate import identity
    require(profile['database'].startswith('test_stage3h3b3_') and
            profile.get('gate_test_marker')=='sales-ai-demo-b3-disposable:'+profile['identity'],'Disposable journal installer only.')
    with raw.cursor() as cursor:identity(cursor,profile,profile['owner_role'])
    raw.execute('CREATE TABLE '+JOURNAL+' (operation uuid PRIMARY KEY REFERENCES sales_ai_demo_control.operations(operation),'
        'intent_sha text NOT NULL,generation uuid NOT NULL,target_date date NOT NULL,salesperson_id bigint NOT NULL,'
        "state text NOT NULL CHECK(state IN ('PREPARING','ALLOCATED','COMMITTED')),"
        'plan jsonb NOT NULL,allocation jsonb,result jsonb,owns_day boolean NOT NULL DEFAULT FALSE,'
        "CHECK ((state='PREPARING' AND allocation IS NULL AND result IS NULL AND NOT owns_day) OR "
        "(state='ALLOCATED' AND allocation IS NOT NULL AND result IS NULL AND NOT owns_day) OR "
        "(state='COMMITTED' AND allocation IS NOT NULL AND result IS NOT NULL)))")
    raw.execute('CREATE UNIQUE INDEX prepared_day_identity ON '+JOURNAL+
                '(generation,target_date,salesperson_id) WHERE owns_day')
    raw.execute('CREATE TABLE sales_ai_demo_control.preparation_recoveries('
                'id uuid PRIMARY KEY,operation uuid NOT NULL REFERENCES '+JOURNAL+'(operation),envelope jsonb NOT NULL)')


def snapshot(raw):
    from deploy_lock_capabilities import public_state
    actor=raw.execute("SELECT s.id FROM visits_salesperson s JOIN auth_user u ON u.id=s.user_id "
        "WHERE s.employee_code='SP001' AND s.is_active AND u.is_active AND NOT u.is_staff").fetchall()
    require(len(actor)==1,'Synthetic owning salesperson unavailable.')
    actor=actor[0][0]
    customers={r[0]:dict(id=r[1],active=r[2],assigned=r[3]) for r in raw.execute(
        'SELECT c.customer_code,c.id,c.is_active,EXISTS(SELECT 1 FROM visits_customerassignment a '
        'WHERE a.customer_id=c.id AND a.salesperson_id=%s AND a.is_active) FROM customers_customer c',[actor])}
    visits=[dict(id=r[0],customer=r[1],salesperson_id=r[2],date=r[3].isoformat(),status=r[4],
                 request=None if r[5] is None else dict(id=r[5],status=r[6],revision=r[7]))
        for r in raw.execute('SELECT v.id,c.customer_code,v.salesperson_id,v.visit_date,v.status,r.id,r.status,r.revision '
            'FROM visits_visit v JOIN customers_customer c ON c.id=v.customer_id '
            'LEFT JOIN sales_requests_salesrequest r ON r.visit_id=v.id ORDER BY v.id')]
    return dict(salesperson_id=actor,customers=customers,visits=visits,business=public_state(raw))


def registration(raw,profile,state,manifest,target,actor):
    result={c:v['id'] for c,v in manifest['visits'].items()} if manifest['preparation_date']==target else {}
    rows=raw.execute('SELECT result FROM '+JOURNAL+" WHERE generation=%s AND target_date=%s AND salesperson_id=%s AND owns_day AND state='COMMITTED'",
                     [profile['identity'],target,actor]).fetchall()
    require(len(rows)<=1,'Ambiguous prepared-day registration.')
    if rows:
        saved=verify(rows[0][0],state)
        require(saved['binding']==binding(profile),'Prepared-day source/identity mismatch.')
        require(not result or result==saved['visits'],'Conflicting initial/day registrations.')
        result=saved['visits']
    return result


def make_plan(raw,profile,state,target,*,now=None):
    state=Path(state);parsed,today=resolve_date(target,now() if callable(now) else now)
    require(parsed.isoformat()==target,'Target must be an ISO date.')
    manifest=context(raw,profile,state)
    observed=snapshot(raw)
    registered=registration(raw,profile,state,manifest,target,observed['salesperson_id'])
    assessment=prepare_day(observed,manifest,parsed,today,registered)
    payload=dict(format=FORMAT,binding=binding(profile),target=target,today=today.isoformat(),
        fixture_sha=hashlib.sha256((state/'fixtures/manifest.json').read_bytes()).hexdigest(),
        observed=observed,assessment=assessment)
    return {**sign(payload,state),'fingerprint':sha(payload)}


def validate_plan(envelope,profile,state):
    payload=verify(envelope,state)
    require(payload['format']==FORMAT and payload['binding']==binding(profile) and envelope.get('fingerprint')==sha(payload),
            'Stale/mismatched signed plan fingerprint.')
    return payload


def confirmation(profile,operation,fingerprint,*,recover=False):
    return f"{'RECOVER' if recover else 'PREPARE'} DEMO DAY {profile['database']} OID {profile['database_oid']} GENERATION {profile['identity']} OP {operation} PLAN {fingerprint}"


def record_intent(raw,profile,operation,plan):
    state=Path(settings.DEMO_GENERATION_CONFIG['state'])
    payload=validate_plan(plan,profile,state)
    require(payload['assessment']['status'] in ('READY_FOR_APPROVAL','NO_OP'),'Entire preparation batch blocked.')
    raw.execute('INSERT INTO '+JOURNAL+'(operation,intent_sha,generation,target_date,salesperson_id,state,plan) '
        "VALUES(%s,%s,%s,%s,%s,'PREPARING',%s)",[operation,plan['fingerprint'],profile['identity'],payload['target'],
        payload['observed']['salesperson_id'],Jsonb(plan)])


def journal(raw,profile,state,operation,plan):
    row=raw.execute('SELECT state,plan,allocation,result FROM '+JOURNAL+' WHERE operation=%s',[operation]).fetchone()
    require(row is not None,'Preparation journal missing; no adoption/reconstruction.')
    require(row[1]==plan,'Operation UUID has a different preparation intent.')
    validate_plan(row[1],profile,state)
    metadata=raw.execute('SELECT intent_sha,generation,target_date,salesperson_id FROM '+JOURNAL+' WHERE operation=%s',[operation]).fetchone()
    require(metadata==(plan['fingerprint'],UUID(profile['identity']),date.fromisoformat(plan['payload']['target']),
                       plan['payload']['observed']['salesperson_id']),'Journal metadata tampered.')
    return row


def check_rows(raw,expected,inserted,*,sequences):
    from deploy_lock_capabilities import public_state
    actual=public_state(raw)
    require(actual['sequences']==sequences,'Unexpected sequence state; no reset or inferred ownership.')
    for table,saved in expected['tables'].items():
        if table=='visits_visit':
            rows=raw.execute('SELECT row_to_json(t)::text FROM public.visits_visit t WHERE NOT(id=ANY(%s)) '
                             'ORDER BY row_to_json(t)::text',[list(inserted)]).fetchall()
            remaining=dict(count=len(rows),sha256=hashlib.sha256('\n'.join(r[0] for r in rows).encode()).hexdigest())
            require(remaining==saved and actual['tables'][table]['count']==saved['count']+len(inserted),
                    'Existing Visits changed or unexpected Visit insert.')
        else:require(actual['tables'][table]==saved,'Unexpected public-table change: '+table)
    require(set(actual['tables'])==set(expected['tables']),'Public schema changed.')
    return actual


def revalidate(raw,profile,state,payload,allocation,now):
    manifest=context(raw,profile,state)
    _,today=resolve_date(payload['target'],now() if callable(now) else now)
    require(today.isoformat()==payload['today'] and date.fromisoformat(payload['target'])>=today,'Tehran day changed; renewed plan required.')
    require(hashlib.sha256((state/'fixtures/manifest.json').read_bytes()).hexdigest()==payload['fixture_sha'],'Fixture manifest changed.')
    actor=payload['observed']['salesperson_id']
    raw.execute('SELECT id FROM visits_salesperson WHERE id=%s ORDER BY id FOR UPDATE',[actor]).fetchall()
    ids=sorted(payload['observed']['customers'][c]['id'] for c in CUSTOMERS)
    raw.execute('SELECT id FROM customers_customer WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[ids]).fetchall()
    raw.execute('SELECT id FROM visits_customerassignment WHERE salesperson_id=%s AND customer_id=ANY(%s) ORDER BY id FOR UPDATE',[actor,ids]).fetchall()
    raw.execute('SELECT id FROM visits_visit WHERE salesperson_id=%s AND customer_id=ANY(%s) ORDER BY id FOR UPDATE',[actor,ids]).fetchall()
    check_rows(raw,payload['observed']['business'],[],sequences=allocation['sequences'] if allocation else payload['observed']['business']['sequences'])
    live=snapshot(raw)
    require({k:v for k,v in live.items() if k!='business'}=={k:v for k,v in payload['observed'].items() if k!='business'},
            'Visit/request/assignment context changed.')
    registered=registration(raw,profile,state,manifest,payload['target'],actor)
    require(prepare_day(live,manifest,date.fromisoformat(payload['target']),today,registered)==payload['assessment'],
            'Preparation policy/proposed write set changed.')


def recovery_head(raw,profile,state,operation,plan):
    """Prove one complete signed ownership chain; missing/forked claims fail closed."""
    from scripts.demo.gate_recovery import verify_operation
    original,head=verify_operation(raw,profile,operation,purpose=FORMAT)
    pid=original['backend_pid'];claims={}
    for pk,envelope in raw.execute('SELECT id,envelope FROM sales_ai_demo_control.preparation_recoveries WHERE operation=%s',[operation]):
        claim=verify(envelope,state)
        require(claim.get('binding')==binding(profile) and claim.get('operation')==str(operation)
                and claim.get('plan')==plan['fingerprint'] and claim.get('claim_uuid')==str(pk),
                'Recovery claim identity mismatch.')
        previous=claim.get('previous_claim')
        require(previous not in claims,'Forked recovery evidence.')
        claims[previous]=(claim,sha(envelope))
    count=0
    while head in claims:
        claim,digest=claims[head]
        require(claim['previous_pid']==pid and type(claim['claimed_pid']) is int and claim['claimed_pid']>0,
                'Recovery ownership chain mismatch.')
        pid=claim['claimed_pid'];head=digest;count+=1
        require(count<=len(claims),'Cyclic recovery evidence.')
    require(count==len(claims),'Missing/orphaned recovery evidence.')
    return head,pid


def claim_recovery(raw,profile,state,operation,plan):
    """Explicit manual continuation, never gate-only recovery or PID takeover."""
    from generation import active_generation
    from scripts.demo.gate_recovery import verify_operation
    with raw.transaction(),raw.cursor() as cursor:
        inspect(cursor,profile,profile['owner_role'])
        cursor.execute('SELECT pg_try_advisory_lock(%s,%s)',OWNER_KEY)
        require(cursor.fetchone()[0],'Preparation owner/recovery still live.')
    try:
        with raw.transaction(),raw.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s,%s)',KEY)
            pending=inspect(cursor,profile,profile['owner_role'])
            require(pending[0]=='PENDING' and pending[1]==operation,'No matching abandoned preparation.')
            require(active_generation()==profile['identity'],'Recovery generation mismatch.')
            cursor.execute('SELECT evidence_sha FROM '+TABLE+' WHERE singleton');evidence=cursor.fetchone()[0]
            verify_operation(raw,profile,operation,evidence,purpose=FORMAT)
            journal(raw,profile,state,operation,plan)
            previous,owner_pid=recovery_head(raw,profile,state,operation,plan)
            require(owner_pid==pending[2],'Pending owner has no signed claim; no PID-based takeover.')
            cursor.execute('SELECT pg_backend_pid()');pid=cursor.fetchone()[0]
            claim_uuid=uuid4()
            envelope=sign(dict(operation=str(operation),plan=plan['fingerprint'],binding=binding(profile),
                               claim_uuid=str(claim_uuid),previous_claim=previous,previous_pid=pending[2],claimed_pid=pid),state)
            cursor.execute('INSERT INTO sales_ai_demo_control.preparation_recoveries VALUES(%s,%s,%s)',[claim_uuid,operation,Jsonb(envelope)])
            cursor.execute('UPDATE '+TABLE+' SET backend_pid=%s WHERE singleton AND operation=%s AND backend_pid=%s',[pid,operation,pending[2]])
            require(cursor.rowcount==1,'Preparation recovery ownership conflict.')
        gate=ExclusiveGate(raw,profile,operation);gate.pid=pid
        return gate
    except BaseException:raw.close();raise


def publish(raw,profile,state,operation,plan,*,hook=lambda phase:None):
    phase,_,_,envelope=journal(raw,profile,state,operation,plan)
    require(phase=='COMMITTED' and envelope is not None,'No committed preparation result to publish.')
    saved=verify(envelope,state)
    require(saved['binding']==binding(profile) and saved['operation']==str(operation)
            and saved['intent']==plan['fingerprint'],'Committed result identity mismatch.')
    require(recovery_head(raw,profile,state,operation,plan)[0]==saved['recovery_head'],
            'Committed recovery evidence changed/missing.')
    from scripts.demo.gate_recovery import verify_operation,verify as gate_verify
    verify_operation(raw,profile,operation,saved['gate_evidence'],purpose=FORMAT)
    audit=raw.execute('SELECT envelope FROM sales_ai_demo_control.results WHERE operation=%s',[operation]).fetchone()
    require(audit is not None,'Committed gate result missing.')
    audit=gate_verify(audit[0])
    from scripts.demo.gate_recovery import binding as gate_binding
    require(audit['binding']==gate_binding(profile,purpose=FORMAT) and audit['evidence_sha']==saved['gate_evidence']
            and audit['operation']==str(operation) and audit['kind']=='PREPARED_DAY' and audit['business_sha']==saved['after_sha'],
            'Committed gate result does not reconcile.')
    for code,pk in saved['visits'].items():
        row=raw.execute('SELECT c.customer_code,v.salesperson_id,v.visit_date FROM visits_visit v '
            'JOIN customers_customer c ON c.id=v.customer_id WHERE v.id=%s',[pk]).fetchone()
        require(row==(code,saved['salesperson_id'],date.fromisoformat(saved['target'])),'Prepared Visit lineage changed.')
    directory=state/'fixtures/prepared-days';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(str(operation)+'.json');data=canonical(envelope)+b'\n'
    if path.exists():require(path.read_bytes()==data,'Published preparation evidence tampered; never overwrite.')
    else:
        temporary=directory/(str(operation)+'.'+uuid4().hex+'.tmp')
        with temporary.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        hook('publication_temporary')
        try:os.link(temporary,path)  # Exclusive atomic publication; never clobber another file.
        except FileExistsError:require(path.read_bytes()==data,'Competing publication differs; never overwrite.')
        temporary.unlink()
    return saved


def execute_disposable(raw,profile,state,*,target,plan,operation,confirm,recover=False,now=None,hook=lambda phase:None):
    """One explicit command/connection. No network retry and no persistent target."""
    try:
        state=Path(state);operation=UUID(str(operation));payload=validate_plan(plan,profile,state)
        require(target==payload['target'] and confirm==confirmation(profile,operation,plan['fingerprint'],recover=recover),
                'Exact target/operation/plan confirmation required.')
        with raw.transaction():
            context(raw,profile,state)
            row=raw.execute('SELECT state FROM '+JOURNAL+' WHERE operation=%s',[operation]).fetchone()
            require(row is not None or raw.execute('SELECT 1 FROM sales_ai_demo_control.operations WHERE operation=%s',[operation]).fetchone() is None,
                    'Preparation journal missing or UUID used by another operation.')
            if row and row[0]=='COMMITTED':return publish(raw,profile,state,operation,plan,hook=hook)
        require(raw.info.transaction_status==0,'Preparation requires an idle connection.')
        gate=claim_recovery(raw,profile,state,operation,plan) if recover else ExclusiveGate(raw,profile,operation)
        if not recover:gate.announce(prepare_plan=plan)
        hook('announced')
        with gate._drained():
            phase,_,allocation,_=journal(raw,profile,state,operation,plan)
            require(recovery_head(raw,profile,state,operation,plan)[1]==gate.pid,'Unsigned preparation owner.')
            allocation=verify(allocation,state) if allocation else None
            revalidate(raw,profile,state,payload,allocation,now)
            if phase=='PREPARING':
                sequence=raw.execute("SELECT pg_get_serial_sequence('visits_visit','id')").fetchone()[0]
                require(raw.execute("SELECT increment_by,cache_size,cycle FROM pg_sequences WHERE schemaname='public' "
                    "AND sequencename=%s",[sequence.split('.')[-1]]).fetchone()==(1,1,False),'Unsupported Visit sequence policy.')
                ids={c['customer_code']:raw.execute('SELECT nextval(%s::regclass)',[sequence]).fetchone()[0]
                     for c in payload['assessment']['visits'] if c['action']=='WOULD_INSERT'}
                hook('reserved')
                from deploy_lock_capabilities import public_state
                allocation=dict(operation=str(operation),intent=plan['fingerprint'],ids=ids,sequences=public_state(raw)['sequences'])
                changed=raw.execute('UPDATE '+JOURNAL+" SET state='ALLOCATED',allocation=%s WHERE operation=%s AND state='PREPARING'",
                                    [Jsonb(sign(allocation,state)),operation])
                require(changed.rowcount==1,'Allocation CAS failed.')
                require(raw.execute('SELECT count(*) FROM visits_visit WHERE id=ANY(%s)',[list(ids.values())]).fetchone()[0]==0,'Allocated ID collision.')
            else:require(phase=='ALLOCATED','Invalid preparation journal phase.')
        hook('allocated')
        with gate._drained() as cursor:
            _,_,signed_allocation,_=journal(raw,profile,state,operation,plan)
            head,owner_pid=recovery_head(raw,profile,state,operation,plan)
            require(owner_pid==gate.pid,'Unsigned preparation owner.')
            allocation=verify(signed_allocation,state)
            require(allocation['operation']==str(operation) and allocation['intent']==plan['fingerprint'],'Allocation identity mismatch.')
            revalidate(raw,profile,state,payload,allocation,now)
            ids=allocation['ids'];actor=payload['observed']['salesperson_id'];visits={}
            for item in payload['assessment']['visits']:
                code=item['customer_code'];customer=payload['observed']['customers'][code]['id']
                if item['action']=='WOULD_INSERT':
                    cursor.execute("INSERT INTO visits_visit(id,salesperson_id,customer_id,visit_date,status,customer_request,"
                        "customer_feedback,competitor_information,notes,order_created,order_amount,follow_up_required,follow_up_date,created_at,updated_at) "
                        "VALUES(%s,%s,%s,%s,'PLANNED','','','',%s,FALSE,0,FALSE,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                        [ids[code],actor,customer,target,FORMAT+' / '+str(operation)])
                    visits[code]=ids[code];hook('inserted')
                else:
                    require(item['action']=='KEEP_EXISTING','Blocked or consumed scenario.')
                    visits[code]=item['existing_visit_ids'][0]
            final=check_rows(raw,payload['observed']['business'],ids.values(),sequences=allocation['sequences'])
            cursor.execute('SELECT evidence_sha FROM '+TABLE+' WHERE singleton');evidence=cursor.fetchone()[0]
            result=dict(format=FORMAT,binding=binding(profile),operation=str(operation),intent=plan['fingerprint'],
                target=target,salesperson_id=actor,visits=visits,inserted_ids=list(ids.values()),prepared_status='PLANNED',
                before_sha=sha(payload['observed']['business']),after_sha=sha(final),sequences=allocation['sequences'],gate_evidence=evidence,
                recovery_head=head)
            changed=raw.execute('UPDATE '+JOURNAL+" SET state='COMMITTED',result=%s,owns_day=%s WHERE operation=%s AND state='ALLOCATED'",
                                [Jsonb(sign(result,state)),bool(ids),operation])
            require(changed.rowcount==1,'Preparation result CAS failed.')
            from scripts.demo.gate_recovery import record_result
            record_result(raw,profile,operation,kind='PREPARED_DAY',business_sha=sha(final),evidence_sha=evidence,purpose=FORMAT)
            cursor.execute('UPDATE '+TABLE+" SET phase='ACTIVE',operation=NULL,backend_pid=NULL,evidence_sha=NULL "
                           "WHERE singleton AND operation=%s AND backend_pid=%s",[operation,gate.pid])
            require(cursor.rowcount==1,'Preparation release ownership conflict.')
            hook('before_commit')
            from scripts.demo.generation import active_generation
            require(active_generation()==profile['identity'],'Generation changed before preparation commit.')
            _,today=resolve_date(target,now() if callable(now) else now)
            require(today.isoformat()==payload['today'],'Tehran midnight changed before commit; renewed review required.')
        hook('after_commit')
        with raw.transaction():return publish(raw,profile,state,operation,plan,hook=hook)
    finally:raw.close()  # Retained lifetime lease ends only at verified commit or disconnect.
