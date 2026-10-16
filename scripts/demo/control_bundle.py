"""Read-only Gate V2 + Prepare Day V1 catalog contract, never a schema installer.

The checked-in contract describes the reviewed disposable installers, not a
baseline inferred from the target being inspected. OIDs are resolved afresh;
qualified names, definitions and ACLs must match before serving traffic.
"""
import hashlib
import json
from pathlib import Path

from scripts.demo.maintenance_gate import inspect as inspect_admission, require
from scripts.demo import maintenance_gate, gate_recovery, prepare_day

VERSION = 'H4_CONTROL_SCHEMA_V2_PREPARE_DAY_V1'
SCHEMA = 'sales_ai_demo_control'
TABLES = ('admission', 'operations', 'preparation_recoveries', 'prepared_days', 'results')
CONTRACT_PATH = Path(__file__).with_name('control_bundle_v1.json')
LOADED_CONTRACT_SHA256 = hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding='utf-8-sig'))
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
# Loaded evidence cannot bless changed source files underneath a running worker.
LOADED_SOURCES = {Path(module.__file__).name: module.LOADED_SOURCE_SHA256
                  for module in (maintenance_gate, gate_recovery, prepare_day)}


def catalog(cursor):
    """Canonical, non-secret structure. No journal data or target-derived trust."""
    cursor.execute("SELECT c.relname,c.relkind,c.relpersistence,c.relrowsecurity,c.relforcerowsecurity,"
        "c.relreplident FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=%s ORDER BY c.relname", [SCHEMA])
    relations = cursor.fetchall()
    cursor.execute("SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,"
        "pg_get_expr(d.adbin,d.adrelid),a.attidentity,a.attgenerated,a.attisdropped "
        "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum "
        "WHERE n.nspname=%s AND c.relkind='r' AND a.attnum>0 ORDER BY c.relname,a.attnum", [SCHEMA])
    columns = cursor.fetchall()
    cursor.execute("SELECT t.relname,c.conname,c.contype,pg_get_constraintdef(c.oid),"
        "c.convalidated,c.condeferrable,c.condeferred FROM pg_constraint c "
        "JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname=%s ORDER BY t.relname,c.conname", [SCHEMA])
    constraints = cursor.fetchall()
    cursor.execute("SELECT t.relname,c.relname,pg_get_indexdef(i.indexrelid),i.indisvalid,i.indisready "
        "FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_class c ON c.oid=i.indexrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s ORDER BY t.relname,c.relname", [SCHEMA])
    indexes = cursor.fetchall()
    cursor.execute("SELECT (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND NOT t.tgisinternal),"
        "(SELECT count(*) FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s),"
        "(SELECT count(*) FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s),"
        "(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s)", [SCHEMA]*4)
    extras = cursor.fetchone()
    return json.loads(json.dumps(dict(version=VERSION, relations=relations, columns=columns,
                                     constraints=constraints, indexes=indexes, extras=extras)))


def inspect(cursor, profile, role, *, serving=False):
    """SELECT-only; operator may inspect PENDING, normal startup may not serve it.

    Caller controls its read-only transaction. No current catalog state is ever
    adopted or repaired. Database/endpoint/role/marker and singleton generation
    validation are shared with request admission. Private tables stay unreadable.
    """
    status = inspect_admission(cursor, profile, role)
    require(all(hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() == value
                for name, value in {**LOADED_SOURCES, 'control_bundle.py': LOADED_SOURCE_SHA256}.items()),
            'Control bundle loaded source differs from disk; restart compatible workers explicitly.')
    require(hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest() == LOADED_CONTRACT_SHA256,
            'Control bundle contract changed underneath worker.')
    require(catalog(cursor) == CONTRACT, 'Missing/incompatible control bundle schema, constraints or indexes.')
    runtime, owner = profile['runtime_role'], profile['owner_role']
    cursor.execute("SELECT pg_get_userbyid(nspowner),has_schema_privilege(%s,oid,'USAGE'),"
        "has_schema_privilege(%s,oid,'CREATE') FROM pg_namespace WHERE nspname=%s", [runtime,runtime,SCHEMA])
    require(cursor.fetchone() == (owner,True,False), 'Unsafe control bundle schema ownership/runtime grants.')
    # Exact ACL grantees, including grant options. No PUBLIC, inherited or stray
    # principal may acquire private journal access through an unnoticed grant.
    cursor.execute("SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,"
        "a.privilege_type,a.is_grantable FROM pg_namespace n,"
        "LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname=%s", [SCHEMA])
    require(set(cursor.fetchall()) == {(owner,'USAGE',False),(owner,'CREATE',False),(runtime,'USAGE',False)},
            'Unsafe control bundle schema ACL.')
    cursor.execute("SELECT c.relname,pg_get_userbyid(c.relowner),"
        "CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,a.privilege_type,a.is_grantable "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,"
        "LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
        "WHERE n.nspname=%s AND c.relkind='r'", [SCHEMA])
    allowed = {(table,owner,owner,priv,False) for table in TABLES
               for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN')}
    allowed.add(('admission',owner,runtime,'SELECT',False))
    require(set(cursor.fetchall()) == allowed, 'Unsafe control bundle ownership/table runtime grants.')
    cursor.execute("SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND cardinality(a.attacl)>0", [SCHEMA])
    require(cursor.fetchone() == (0,), 'Unsafe control bundle column runtime grants.')
    for table in TABLES:
        cursor.execute("SELECT has_table_privilege(%s,%s,'SELECT'),"
            "has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'),"
            "has_any_column_privilege(%s,%s,'INSERT,UPDATE,REFERENCES')",
            [runtime,f'{SCHEMA}.{table}']*3)
        require(cursor.fetchone() == (table=='admission',False,False), 'Unsafe effective control bundle runtime grants.')
    cursor.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', [runtime])
    require(cursor.fetchone() == (False,)*5, 'Elevated control runtime role.')
    cursor.execute('SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=%s', [runtime])
    require(cursor.fetchone() == (0,), 'Unexpected runtime role membership.')
    require(not serving or status == ('ACTIVE',None,None), 'Maintenance PENDING; normal startup refused.')
    return dict(version=VERSION, phase=status[0], serving_ready=status==('ACTIVE',None,None),
                contract_sha256=LOADED_CONTRACT_SHA256)
