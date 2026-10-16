"""SELECT-only preservation evidence; no imports from private reports or artifacts.

Evidence starts a NEW operation, never reconstructs a missing historical baseline.
Signed before-state files are recovery records, not fixture initialization records.
"""
import argparse
import hashlib
import hmac
import json
import subprocess
from uuid import uuid4

from common import *

PRODUCTION_ENV = Path(r'D:\docker\sales-ai-postgres\runtime-credentials\sales_ai_runtime.env')
FORMAT = 'DEMO_PRESERVATION_V1'


def production_connection():
    """Independent, runtime-only, read-only audit connection; never operator auth."""
    import psycopg
    clean_database_environment()
    values = {}
    for line in PRODUCTION_ENV.read_text(encoding='utf-8-sig').splitlines():
        key, sep, value = line.partition('=')
        if sep and not key.lstrip().startswith('#'):
            require(key.strip() not in values, 'Duplicate production audit environment key.')
            values[key.strip()] = value.strip().strip('\"\'')
    for key, expected in dict(POSTGRES_DB='sales_ai_db', POSTGRES_USER='sales_ai_runtime',
                              POSTGRES_HOST='127.0.0.1', POSTGRES_PORT='5432').items():
        require(key not in values or values[key] == expected, 'Production audit credential identity mismatch.')
    require(bool(values.get('POSTGRES_PASSWORD')), 'Read-only production audit credential is missing.')
    conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='sales_ai_db', user='sales_ai_runtime',
        password=values['POSTGRES_PASSWORD'], connect_timeout=5, application_name='sales-ai-preservation-read-only',
        options='-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=5000')
    try:
        require(conn.info.host == '127.0.0.1' and conn.info.port == 5432, 'Production audit endpoint mismatch.')
        identity = conn.execute("SELECT current_database(),current_user,current_setting('server_encoding'),"
            "pg_get_userbyid(datdba),current_setting('transaction_read_only') FROM pg_database WHERE datname=current_database()").fetchone()
        require(identity == ('sales_ai_db', 'sales_ai_runtime', 'UTF8', 'sales_ai_user', 'on'),
                'Production audit identity/read-only mode mismatch.')
        conn.rollback()
        return conn
    except BaseException:
        conn.close()
        raise


def production_metadata(conn):
    """Reviewed metadata SELECTs formerly hidden in an ignored provisioning script.

    pg_sequences deliberately reports NULL where runtime lacks sequence visibility;
    this does not claim operator-level sequence coverage or acquire new privileges.
    """
    return dict(
        sequences=conn.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename").fetchall(),
        owners=conn.execute("SELECT relname,relkind,pg_get_userbyid(relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname='public' AND relkind IN ('r','S','i') ORDER BY relname").fetchall(),
        constraints=conn.execute("SELECT c.conname,pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                                 "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' ORDER BY c.conname").fetchall(),
        owner_flags=conn.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='sales_ai_user'").fetchone(),
        owner_database_privileges=conn.execute("SELECT has_database_privilege('sales_ai_user',current_database(),'CONNECT'),"
            "has_database_privilege('sales_ai_user',current_database(),'CREATE'),has_database_privilege('sales_ai_user',current_database(),'TEMPORARY')").fetchone())


def file_hashes(paths):
    """Every declared file is required, including on recovery; absence is NOT skipped."""
    result = {}
    for path in sorted(set(Path(p).resolve() for p in paths)):
        require(path.is_file() and not path.is_symlink(), 'Required preservation file missing/unsafe: ' + str(path))
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    require(bool(result), 'Empty preservation file set is not evidence.')
    return result


def installation_files(state, *, prepared):
    paths = [state/'profile.json', state/'generation-state.json']
    paths += [state/'credentials'/name for name in
              ('owner.json','runtime.json','bootstrap-password.txt','django-secret.key','control-token.key')]
    if prepared:
        paths += [state/'fixtures/manifest.json',state/'fixtures/manifest.sha256',state/'credentials/test-accounts.json']
    # Protect additional CURRENT configured credentials, without historical reports.
    paths += list((state/'credentials').glob('*'))
    return paths


def installation_preservation(profile, state=DEFAULT_STATE):
    """Fresh/prepared capability deployment: exact live identity and full Demo state.

    Fresh uses verified empty-schema + explicit generation registration. Prepared
    requires the authoritative fixture manifest checked against current rows.
    Neither mode needs production access or a previous run's private reports.
    Capability registry/owner grants are the explicitly expected deployment output;
    the installer's separate ACL/body checks validate them, not this data baseline.
    """
    from initialization import installation_state
    from deploy_lock_capabilities import maintenance, public_state
    with maintenance(profile) as conn:
        conn.rollback()
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        mode = installation_state(conn, profile, state)
        data = public_state(conn)
    return dict(mode=mode, data=data, files=file_hashes(installation_files(state, prepared=mode=='PREPARED')))


def preservation(profile):
    """Current-operation existing-install protection, including production and Git.

    Private preview credentials that currently exist are discovered as FILES ONLY;
    no Python, report, snapshot or fixture is loaded from venv.
    """
    from plan import inventory
    from apps.core.reconciliation import canonical_data_state
    with connect(profile, DEFAULT_STATE) as conn:
        conn.rollback()
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        demo = inventory(conn, profile)
    with production_connection() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        production = canonical_data_state(conn, production_metadata)
        # Pin this operation's actual DB identity as well as all canonical row data.
        production['identity'] = conn.execute("SELECT oid,current_setting('server_version_num'),inet_server_addr()::text,"
            "inet_server_port() FROM pg_database WHERE datname=current_database()").fetchone()
    paths = installation_files(DEFAULT_STATE, prepared=True) + [ROOT/'db.sqlite3']
    paths += [DEFAULT_STATE/'lock-capabilities.json',DEFAULT_STATE/'lock-capabilities.sha256']
    paths += list((ROOT/'venv').glob('*/credentials.json'))
    unrelated = ROOT/'docs/checkpoints/DEMO_02_VISUAL_ASSET_SELECTION_APPROVAL.md'
    if unrelated.exists():
        paths.append(unrelated)  # Untracked planning is protected when present, never a prerequisite.
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    return json.loads(json.dumps(dict(demo=demo,production=production,files=file_hashes(paths),
        head=git('rev-parse','HEAD'),stash=git('stash','list','--format=%H'),
        staged=git('diff','--cached','--name-only')), default=str))


def context(profile, state, purpose):
    from generation import validate_registry
    from lock_capabilities import source_sha
    validate_profile(profile, state)
    registry = read_json(state/'generation-state.json')
    validate_registry(registry, profile, read_json(state/'profile.json'))
    require(registry['phase'] == 'ACTIVE', 'Preservation requires an active, unambiguous generation.')
    require(isinstance(purpose, str) and bool(purpose.strip()), 'An explicit operation purpose is required.')
    return dict(identity=profile['identity'], database=profile['database'], database_oid=profile['database_oid'],
        endpoint=[profile['host'],profile['database_port']],runtime=profile['runtime_role'],generation=registry,
        migrations=migration_fingerprint(),sql_sha256=source_sha(),purpose=purpose,
        tooling=file_hashes([Path(__file__),ROOT/'scripts/demo/initialization.py',ROOT/'scripts/demo/deploy_lock_capabilities.py']))


def signed_bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()


def key(state):
    value = (state/'credentials/control-token.key').read_bytes().strip()
    require(len(value)>=48, 'Protected preservation signing key is missing/invalid.')
    return value


def record_before(path, profile, snapshot, *, purpose, state=DEFAULT_STATE):
    """Exclusive creation. Never replace/rebase an uncertain operation's evidence."""
    value = dict(format=FORMAT, operation=str(uuid4()),context=context(profile,state,purpose),snapshot=snapshot)
    value = json.loads(json.dumps(value,default=str))
    envelope = dict(payload=value,signature=hmac.new(key(state),signed_bytes(value),hashlib.sha256).hexdigest())
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(envelope,stream,indent=2,sort_keys=True)
    return value['operation']


def verify_before(path, profile, *, purpose, operation, state=DEFAULT_STATE):
    """Missing/tampered/foreign evidence always stops; never captures a replacement."""
    require(Path(path).is_file(), 'Before-state evidence is missing. Stop this operation; inspect its journal. '
            'Only independently approved new work may capture a NEW baseline; historical preservation cannot be reconstructed.')
    envelope = read_json(path)
    value = envelope.get('payload',{})
    require(hmac.compare_digest(str(envelope.get('signature','')),
        hmac.new(key(state),signed_bytes(value),hashlib.sha256).hexdigest()), 'Before-state signature mismatch; no recovery assumed.')
    expected = json.loads(json.dumps(context(profile,state,purpose),default=str))
    require(value.get('format') == FORMAT and value.get('operation') == operation
        and value.get('context') == expected, 'Before-state operation/identity/generation/source mismatch.')
    snapshot = value.get('snapshot')
    require(isinstance(snapshot,dict) and bool(snapshot.get('files')), 'Incomplete preservation baseline.')
    require(file_hashes(snapshot['files']) == snapshot['files'], 'Protected files changed since before-state capture.')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['capture','verify'])
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--purpose',required=True)
    parser.add_argument('--operation',help='Exact operation UUID returned by capture; required for verify.')
    args = parser.parse_args()
    profile = load_profile();verify_container(profile)
    if args.command == 'capture':
        # Explicit NEW operation only; does not attest to any earlier deployment.
        operation = record_before(args.baseline,profile,preservation(profile),purpose=args.purpose)
        print(json.dumps(dict(status='NEW_OPERATION_RECORDED',operation=operation)))
    else:
        require(bool(args.operation), 'Verification requires the original operation UUID.')
        before = verify_before(args.baseline,profile,purpose=args.purpose,operation=args.operation)
        require(before == preservation(profile), 'Current state differs from original operation evidence; STOP.')
        print('READ_ONLY_PRESERVATION_VERIFIED')


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('Preservation stopped: '+(str(exc) if isinstance(exc,DemoError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
