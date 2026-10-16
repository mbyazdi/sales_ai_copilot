"""Explicit B7 maintenance only. No startup installation or automatic repair.

python -B scripts/demo/deploy_lock_capabilities.py preflight
python -B scripts/demo/deploy_lock_capabilities.py install --approve-reference-locks-v1
python -B scripts/demo/deploy_lock_capabilities.py recheck
The install command pauses only the identity-verified Demo listener. Restart is
separate after validation; interruption always requires journal inspection.
"""
import argparse
import hashlib
import json
import subprocess
from uuid import uuid4

from common import *
from lock_capabilities import PERSISTENT_OWNER, SOURCE, VERSION, _create, source_sha, validate_runtime

def maintenance(profile, *, readonly=True):
    import psycopg
    clean_database_environment()
    conn = psycopg.connect(host='127.0.0.1', port=5433, dbname=DATABASE, user=BOOTSTRAP,
        password=(DEFAULT_STATE / 'credentials/bootstrap-password.txt').read_text(encoding='utf-8').strip(),
        connect_timeout=5, application_name='sales-ai-b7-explicit-maintenance',
        options='-c default_transaction_read_only=' + ('on' if readonly else 'off') +
                ' -c statement_timeout=30000 -c lock_timeout=5000')
    try:
        require(conn.info.host == '127.0.0.1' and conn.info.port == 5433, 'Maintenance endpoint mismatch.')
        verify_connection(conn, profile, BOOTSTRAP)
        return conn
    except BaseException:
        conn.close()
        raise


def public_grants(conn, *, exclude_owner=None):
    """All public relation/column ACLs, including grantors and grant options."""
    query = """SELECT c.relname,a.attname,x.grantor,x.grantee,x.privilege_type,x.is_grantable
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
        CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname='public'
        UNION ALL SELECT c.relname,NULL,x.grantor,x.grantee,x.privilege_type,x.is_grantable
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(c.relacl) x WHERE n.nspname='public'
        ORDER BY 1,2,3,4,5"""
    oid = conn.execute('SELECT oid FROM pg_roles WHERE rolname=%s', [exclude_owner]).fetchone() if exclude_owner else None
    return [list(r) for r in conn.execute(query).fetchall() if not oid or r[3] != oid[0]]


def public_state(conn):
    """Full operator-visible row/sequence evidence; SELECTs only, no row export."""
    from psycopg import sql
    conn.execute("SET LOCAL TIME ZONE 'UTC'")
    tables = {}
    for name, in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1").fetchall():
        rows = conn.execute(sql.SQL('SELECT row_to_json(t)::text FROM public.{} t ORDER BY row_to_json(t)::text')
                            .format(sql.Identifier(name))).fetchall()
        tables[name] = dict(count=len(rows),sha256=hashlib.sha256('\n'.join(r[0] for r in rows).encode()).hexdigest())
    sequences = {}
    for name, in conn.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY 1").fetchall():
        sequences[name] = list(conn.execute(sql.SQL('SELECT last_value,is_called FROM public.{}')
                                            .format(sql.Identifier(name))).fetchone())
    return dict(tables=tables,sequences=sequences)


def isolated_preflight(profile):
    from initialization import installation_state
    verify_container(profile)
    require(migration_fingerprint() == (50, profile['migration_fingerprint']), 'Migration source changed.')
    source_sha()
    with maintenance(profile) as conn:
        conn.rollback()
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        mode = installation_state(conn,profile,DEFAULT_STATE)
        data = public_state(conn)
        roles = conn.execute('SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls '
                             'FROM pg_roles WHERE rolname=ANY(%s) ORDER BY 1', [[OWNER,RUNTIME,BOOTSTRAP]]).fetchall()
        require(len(roles) == 3, 'Demo operator/owner/runtime roles are incomplete.')
        owner = conn.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='public'").fetchone()
        require(owner == (OWNER,), 'Public schema ownership changed.')
        active = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                              "AND pid<>pg_backend_pid() AND xact_start IS NOT NULL").fetchone()[0]
        require(active == 0, 'Active Demo transaction: installation refused.')
    return dict(data=data,mode=mode,roles=roles,source_sha256=source_sha())


def fresh_preservation(profile):
    # Compatibility name used by the original fresh-install integration tests.
    from preservation import installation_preservation
    return installation_preservation(profile, DEFAULT_STATE)


ROLLBACK = """Recovery is manual and requires explicit approval; never rerun blindly.
Pause the verified Demo app; verify container/endpoint/database/OID/marker/generation
and compare this journal, protected registry, SQL body fingerprint and dependencies.
If reverting only this deployment, DROP the two exact sales_ai_locks functions
(no CASCADE), then DROP the empty sales_ai_locks schema; REVOKE only this new
owner's SELECT(columns)/UPDATE(id) grants on the five listed reference tables and
USAGE on public. DROP sales_ai_demo_lock_owner only after proving no dependencies
elsewhere. Archive the capability registry. Do not restore data or reset sequences.
The new launcher deliberately remains blocked without capabilities; restoring old
launcher behavior requires separate review. No automatic DDL rollback/retry follows
an uncertain commit. Installation and registry publication are separate steps.
"""


def run(command, approved=False):
    profile = load_profile()
    preflight = isolated_preflight(profile)
    registry = DEFAULT_STATE / 'lock-capabilities.json'
    with maintenance(profile) as conn:
        exists = conn.execute("SELECT to_regnamespace('sales_ai_locks')").fetchone()[0] is not None
        role_exists = conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', [PERSISTENT_OWNER]).fetchone() is not None
    if exists or role_exists or registry.exists():
        require(exists and role_exists and registry.exists(), 'Partial installation; inspect recovery journal. No repair attempted.')
        with connect(profile, DEFAULT_STATE) as conn:
            value = validate_runtime(conn, profile, DEFAULT_STATE)
        print(json.dumps(dict(status='READ_ONLY_VERIFIED_NO_OP', version=value['version'], sha256=value['sha256'])))
        return
    require(command != 'recheck', 'Capabilities are not installed.')
    if command == 'preflight':
        print(json.dumps(dict(status='READY_FOR_EXPLICIT_INSTALL', version=VERSION, sha256=source_sha(), migrations=50)))
        return
    require(approved, 'Explicit --approve-reference-locks-v1 is required.')
    # Both modes validate authoritative initialization state, never old reports.
    # Full public row/sequence coverage is required even on a first installation.
    from preservation import installation_preservation, record_before, verify_before
    preservation = lambda value: installation_preservation(value, DEFAULT_STATE)
    from demo import health, port_free
    try:
        listener = health(profile)
    except DemoError:
        port_free()  # No listener is fine; an unknown/occupied port fails closed.
        listener = None
    evidence = DEFAULT_STATE / 'reports' / ('b7-' + uuid4().hex)
    evidence.mkdir()
    before = preservation(profile)
    operation = record_before(evidence/'before.json',profile,before,
                              purpose='reference-lock-install',state=DEFAULT_STATE)
    write_json(evidence / 'preflight.json', preflight)
    write_json(evidence / 'listener-before.json', listener)
    (evidence / 'rollback-plan.txt').write_text(ROLLBACK, encoding='utf-8')
    (evidence / 'reference_locks_v1.sql').write_text(SOURCE.read_text(encoding='utf-8'), encoding='utf-8')
    journal = dict(version=1,identity=profile['identity'],database=DATABASE,database_oid=profile['database_oid'],
                   capability_version=VERSION,sha256=source_sha(),phase='RECOVERY_RECORDED',multi_step_atomic=False)
    write_json(evidence / 'journal.json', journal)
    if listener is not None:
        subprocess.run([sys.executable,'-B',str(ROOT / 'scripts/demo/demo.py'),'stop'],check=True,cwd=ROOT)
    port_free()
    journal['phase'] = 'VERIFIED_APP_STOPPED'
    write_json(evidence / 'journal.json', journal)
    require(isolated_preflight(profile)['data']==preflight['data'], 'Demo state drifted during maintenance.')
    from psycopg import sql
    with maintenance(profile, readonly=False) as conn:
        require(conn.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                             'AND pid<>pg_backend_pid()').fetchone()[0] == 0, 'Other Demo connections remain; no DDL applied.')
        grants = public_grants(conn)
        full_before = public_state(conn)
        write_json(evidence / 'operator-data-before.json', full_before)
        write_json(evidence / 'public-grants-before.json', grants)
        require(conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[PERSISTENT_OWNER]).fetchone() is None,
                'Capability owner appeared during maintenance.')
        conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS')
                     .format(sql.Identifier(PERSISTENT_OWNER)))
        snapshot = _create(conn, owner=PERSISTENT_OWNER)
        require(public_grants(conn, exclude_owner=PERSISTENT_OWNER) == grants, 'Existing public ACLs changed; rolling back DDL.')
        # Compare every public row and sequence inside the DDL transaction.
        full_after = public_state(conn)
        require(full_after == full_before, 'Public data changed; rolling back DDL.')
        write_json(evidence / 'operator-data-after.json', full_after)
    journal['phase'] = 'DDL_COMMITTED'
    write_json(evidence / 'journal.json', journal)
    write_json(registry, dict(identity=profile['identity'],database=DATABASE,database_oid=profile['database_oid'],snapshot=snapshot))
    registry.with_suffix('.sha256').write_text(hashlib.sha256(registry.read_bytes()).hexdigest()+'\n',encoding='ascii')
    journal['phase'] = 'REGISTRY_PUBLISHED_APP_STOPPED'
    write_json(evidence / 'journal.json', journal)
    with connect(profile, DEFAULT_STATE) as conn:
        require(validate_runtime(conn,profile,DEFAULT_STATE) == snapshot, 'Post-commit runtime recheck failed.')
    after = preservation(profile)
    write_json(evidence / 'after-install.json', after)
    require(verify_before(evidence/'before.json',profile,purpose='reference-lock-install',
                         operation=operation,state=DEFAULT_STATE)==before,'Original deployment evidence changed.')
    require(before == after, 'Preservation changed; app remains stopped. Inspect recovery evidence.')
    journal['phase'] = 'INSTALL_VERIFIED_APP_STOPPED'
    write_json(evidence / 'journal.json', journal)
    print(json.dumps(dict(status=journal['phase'], evidence=str(evidence),version=VERSION,sha256=source_sha())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['preflight','install','recheck'])
    parser.add_argument('--approve-reference-locks-v1',action='store_true')
    args = parser.parse_args()
    try:
        run(args.command,args.approve_reference_locks_v1)
    except Exception as exc:
        print('B7 stopped: ' + (str(exc) if isinstance(exc,DemoError) else type(exc).__name__) +
              '; inspect protected journal before any retry.',file=sys.stderr)
        sys.exit(1)
