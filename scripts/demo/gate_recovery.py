"""Operator-confirmed gate-only recovery. Disposable implementation; no CLI/deployment.

No Prepare Day journal, business writes, PID-based takeover or automatic repair.
Missing/changed evidence and uncertain outcomes leave PENDING for owner review.
"""
import hashlib
import hmac
import json
import re
from pathlib import Path
from uuid import UUID

from django.conf import settings

from scripts.demo.maintenance_gate import KEY, OWNER_KEY, TABLE, VERSION, inspect, require
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def key():
    try:
        value=(Path(settings.DEMO_GENERATION_CONFIG['state'])/'credentials/control-token.key').read_bytes().strip()
    except (OSError,KeyError):
        value=b''
    require(len(value)>=48,'Protected recovery signing key is unavailable.')
    return value


def seal(payload):
    return dict(payload=payload,signature=hmac.new(key(),b'demo-gate-recovery-v2\0'+canonical(payload),hashlib.sha256).hexdigest())


def verify(envelope):
    require(isinstance(envelope,dict) and isinstance(envelope.get('payload'),dict),'Missing recovery evidence.')
    expected=seal(envelope['payload'])
    require(hmac.compare_digest(str(envelope.get('signature','')),expected['signature']),'Recovery evidence signature mismatch.')
    return envelope['payload']


def binding(profile, *, purpose='GATE_ONLY_NO_BUSINESS_WRITES'):
    # Bind code as well as identity; a changed implementation needs explicit review.
    source={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('maintenance_gate.py','gate_recovery.py')}
    return dict(version=VERSION,database=profile['database'],oid=profile['database_oid'],
        generation=profile['identity'],host=profile['host'],port=profile['database_port'],
        container_id=profile['container_id'],owner=profile['owner_role'],runtime=profile['runtime_role'],
        source=source,purpose=purpose)


def business_digest(raw):
    # Full rows + operator-visible sequence high-water state, never row export.
    # Conservative announcement baseline: if admitted work subsequently changes
    # it, abandoned-operation recovery REFUSES rather than adopting new evidence.
    from deploy_lock_capabilities import public_state
    return sha(public_state(raw))


def record_operation(raw,profile,operation,pid,*,purpose='GATE_ONLY_NO_BUSINESS_WRITES'):
    from psycopg.types.json import Jsonb
    payload=dict(binding=binding(profile,purpose=purpose),operation=str(operation),backend_pid=pid,
                 business_sha=business_digest(raw))
    envelope=seal(payload)
    raw.execute('INSERT INTO sales_ai_demo_control.operations(operation,envelope) VALUES(%s,%s)',
                [operation,Jsonb(envelope)])
    return sha(envelope)


def verify_operation(raw,profile,operation,expected_sha=None,*,purpose='GATE_ONLY_NO_BUSINESS_WRITES'):
    row=raw.execute('SELECT envelope FROM sales_ai_demo_control.operations WHERE operation=%s',[operation]).fetchone()
    require(row is not None,'Durable operation evidence is missing; no reconstructed baseline accepted.')
    envelope=row[0];payload=verify(envelope)
    require(payload.get('binding')==binding(profile,purpose=purpose) and payload.get('operation')==str(operation),
            'Recovery database/generation/owner/source identity mismatch.')
    digest=sha(envelope)
    if expected_sha is not None:require(digest==expected_sha,'Approved operation evidence changed.')
    return payload,digest


def record_result(raw,profile,operation,*,kind,business_sha,recovery_uuid=None,evidence_sha=None,purpose='GATE_ONLY_NO_BUSINESS_WRITES'):
    from psycopg.types.json import Jsonb
    payload=dict(binding=binding(profile,purpose=purpose),operation=str(operation),kind=kind,
        recovery_uuid=str(recovery_uuid) if recovery_uuid else None,business_sha=business_sha,
        evidence_sha=evidence_sha,actor=profile['owner_role'])
    raw.execute('INSERT INTO sales_ai_demo_control.results(operation,recovery_uuid,envelope) VALUES(%s,%s,%s)',
                [operation,recovery_uuid,Jsonb(seal(payload))])
    return payload


def confirmation(profile,operation,evidence_sha):
    return f"RECOVER DEMO GATE {profile['database']} OID {profile['database_oid']} GENERATION {profile['identity']} OP {operation} EVIDENCE {evidence_sha}"


def recover_disposable(raw,profile,*,operation,recovery_uuid,evidence_sha,confirm,_before_commit=None):
    """No persistent entry point. Caller must supply the exact approved evidence.

    Both locks, audit INSERT and conditional release are one DB transaction.
    A live owner retains OWNER_KEY even while idle/timed out/before exclusivity.
    Exclusive KEY proves admitted requests and maintenance transactions drained.
    """
    require(profile['database'].startswith('test_stage3h3b3_') and
            profile.get('gate_test_marker')=='sales-ai-demo-b3-disposable:'+profile['identity'],
            'Recovery is approved for verified disposable databases only.')
    operation,recovery_uuid=UUID(str(operation)),UUID(str(recovery_uuid))
    require(isinstance(evidence_sha,str) and re.fullmatch('[0-9a-f]{64}',evidence_sha),
            'Exact approved evidence SHA256 is required.')
    require(confirm==confirmation(profile,operation,evidence_sha),'Explicit exact recovery confirmation required.')
    require(raw.info.transaction_status==0,'Recovery requires an idle verified owner connection.')
    from scripts.demo.generation import active_generation
    require(active_generation()==profile['identity'],'Recovery generation is not active/verified.')
    with raw.transaction(),raw.cursor() as cursor:
        inspect(cursor,profile,profile['owner_role'])
        # Exclusive owner lease prevents the old owner and other recoveries from
        # proceeding; nonblocking attempts never terminate anyone or take over.
        cursor.execute('SELECT pg_try_advisory_xact_lock(%s,%s)',OWNER_KEY)
        require(cursor.fetchone()[0],'Owner/recovery is live; recovery rejected.')
        cursor.execute('SELECT pg_try_advisory_xact_lock(%s,%s)',KEY)
        require(cursor.fetchone()[0],'Protected requests/maintenance still active; recovery rejected.')
        state=inspect(cursor,profile,profile['owner_role'])
        from scripts.demo.prepare_day import is_preparation
        require(not is_preparation(raw,operation),'Prepare Day requires journal reconciliation, not gate-only recovery.')
        require(active_generation()==profile['identity'],'Generation changed while acquiring recovery.')
        evidence,digest=verify_operation(raw,profile,operation,evidence_sha)
        prior=raw.execute('SELECT envelope FROM sales_ai_demo_control.results WHERE operation=%s OR recovery_uuid=%s',
                          [operation,recovery_uuid]).fetchall()
        if prior:
            require(len(prior)==1,'Ambiguous recovery history.')
            result=verify(prior[0][0])
            require(result.get('binding')==binding(profile) and result.get('operation')==str(operation)
                    and result.get('kind')=='RECOVERED' and result.get('recovery_uuid')==str(recovery_uuid)
                    and result.get('evidence_sha')==digest,'Recovery command conflicts with existing result.')
            require(state==('ACTIVE',None,None),'Replay cannot unlock a subsequent operation.')
            return result
        require(state==('PENDING',operation,evidence['backend_pid']),'Pending ownership does not match approved evidence.')
        row=raw.execute('SELECT evidence_sha FROM '+TABLE+' WHERE singleton FOR UPDATE').fetchone()
        require(row==(digest,),'Pending evidence identity mismatch.')
        before=business_digest(raw)
        require(before==evidence['business_sha'],'Protected data/sequence baseline changed; outcome requires independent review.')
        result=record_result(raw,profile,operation,kind='RECOVERED',business_sha=before,
                             recovery_uuid=recovery_uuid,evidence_sha=digest)
        cursor.execute('UPDATE '+TABLE+" SET phase='ACTIVE',operation=NULL,backend_pid=NULL,evidence_sha=NULL "
                       "WHERE singleton AND phase='PENDING' AND operation=%s AND evidence_sha=%s",
                       [operation,digest])
        require(cursor.rowcount==1,'Recovery CAS failed.')
        require(business_digest(raw)==before,'Recovery changed protected data; rollback.')
        if _before_commit is not None:_before_commit()
        require(active_generation()==profile['identity'],'Generation changed before recovery commit.')
        return result
