"""Read-only Demo gate deployment inspection. Never install/recover/start/stop."""
import argparse
import json
from pathlib import Path

from common import DEFAULT_STATE, connect, load_profile, verify_container, read_json
from scripts.demo.maintenance_gate import VERSION
from scripts.demo.control_bundle import inspect


def worker_signature():
    from scripts.demo import maintenance_gate,gate_recovery,control_bundle
    return dict(version=VERSION,source={'maintenance_gate.py':maintenance_gate.LOADED_SOURCE_SHA256,
                'gate_recovery.py':gate_recovery.LOADED_SOURCE_SHA256,
                'control_bundle.py':control_bundle.LOADED_SOURCE_SHA256,
                'prepare_day.py':control_bundle.LOADED_SOURCES['prepare_day.py']},
                bundle=control_bundle.VERSION,contract_sha256=control_bundle.LOADED_CONTRACT_SHA256)


def worker_matches(listener):
    # Identifies the one inspected listener, NEVER attests to all other workers.
    return isinstance(listener,dict) and listener.get('maintenance_gate')==worker_signature()


def assess(state=DEFAULT_STATE):
    from generation import validate_registry
    from initialization import schema_ready, fixture_ready
    from lock_capabilities import validate_runtime
    from demo import health
    profile=load_profile(state);verify_container(profile)
    validate_registry(read_json(state/'generation-state.json'),profile,read_json(state/'profile.json'))
    result=dict(database=profile['database'],endpoint='127.0.0.1:5433',generation=profile['identity'],
        expected_gate=worker_signature(),database_ready=False,listener_ready=False,
        all_workers_verified=False,execution_authorized=False,persistent_recovery_available=False,reasons=[])
    with connect(profile,state,readonly=True) as raw:
        schema_ready(raw,profile);fixture_ready(raw,profile,state);validate_runtime(raw,profile,state)
        try:
            with raw.cursor() as cursor:status=inspect(cursor,profile,profile['runtime_role'])
            result['database_ready']=status['serving_ready']
            result['control_bundle']=status
            result['gate_state']=status['phase']
            if not result['database_ready']:result['reasons'].append('PENDING_REQUIRES_EXPLICIT_RECOVERY_REVIEW')
        except Exception as exc:
            result['gate_state']='MISSING_OR_INCOMPATIBLE'
            result['reasons'].append('GATE_READINESS_'+type(exc).__name__)
    try:
        listener=health(profile)
        result['listener_ready']=worker_matches(listener)
        result['listener_pid']=listener['pid']
        if not result['listener_ready']:result['reasons'].append('LISTENER_GATE_VERSION_UNPROVEN')
    except Exception as exc:result['reasons'].append('LISTENER_READINESS_'+type(exc).__name__)
    result['reasons'].append('SEPARATE_DEPLOYMENT_APPROVAL_AND_COMPLETE_WORKER_INVENTORY_REQUIRED')
    result['status']='READ_ONLY_REVIEW_ONLY' if result['database_ready'] and result['listener_ready'] else 'NO_GO'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root',type=Path,default=DEFAULT_STATE)
    args=parser.parse_args()
    result=assess(args.state_root)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 2 if result['status']=='NO_GO' else 0


if __name__=='__main__':raise SystemExit(main())
