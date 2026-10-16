"""Exact, versioned lock capabilities. Startup validates; never installs/repairs."""
import hashlib
import json
import re

from common import BOOTSTRAP, ROOT, RUNTIME, require

VERSION = "REFERENCE_LOCKS_V1"
APPROVED_SHA256 = "7f4a013f7b58f4560a803c086645ad196fe68466a6d3a1b887f8f4e8188a32f1"
PERSISTENT_OWNER = "sales_ai_demo_lock_owner"
SOURCE = ROOT / "apps/core/sql/reference_locks_v1.sql"
TABLES = ("customers_customer", "customers_customergrade", "products_product",
          "inventory_inventory", "recommendations_customerrecommendation")
READ_COLUMNS = {
    "customers_customer": ("id", "grade_id"),
    "customers_customergrade": ("id",),
    "products_product": ("id",),
    "inventory_inventory": ("id", "product_id"),
    "recommendations_customerrecommendation": ("id", "customer_id", "product_id"),
}
SIGNATURES = ("lock_feedback_references(bigint,bigint)", "lock_submission_references(bigint,bigint[])")


def source_sha():
    value = hashlib.sha256(SOURCE.read_text(encoding="utf-8").encode()).hexdigest()
    require(value == APPROVED_SHA256, "Capability SQL differs from the owner-approved B6 source.")
    return value


def inspect(conn, *, owner, runtime=None):
    """SELECT-only exact security/body validation, usable by real runtime credentials."""
    source_sha()
    runtime = runtime or RUNTIME
    roles = conn.execute("SELECT rolname,oid,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit "
                         "FROM pg_roles WHERE rolname IN (%s,%s) ORDER BY rolname", [owner, runtime]).fetchall()
    by_role = {r[0]: r for r in roles}
    require(owner in by_role and runtime in by_role, "Capability/runtime role is missing.")
    require(by_role[owner][2:] == (False,) * 7, "Unsafe capability owner flags.")
    require(by_role[runtime][2:] == (True,) + (False,) * 6, "Unsafe runtime role flags.")
    owner_oid, runtime_oid = by_role[owner][1], by_role[runtime][1]
    require(conn.execute("SELECT count(*) FROM pg_auth_members WHERE roleid=%s OR member=ANY(%s)",
                         [owner_oid, [owner_oid, runtime_oid]]).fetchone()[0] == 0, "Unexpected role membership.")
    schema = conn.execute("SELECT oid,nspowner FROM pg_namespace WHERE nspname='sales_ai_locks'").fetchone()
    require(schema is not None and schema[1] == owner_oid, "Missing capability schema or wrong owner.")
    schema_acl = conn.execute("SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_namespace n "
        "CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a "
        "WHERE n.oid=%s ORDER BY 1,2", [schema[0]]).fetchall()
    require(all(g in {owner_oid, runtime_oid} and (g != runtime_oid or (p == 'USAGE' and not grantable))
                for g,p,grantable in schema_acl), "Unexpected capability schema grants.")
    require(conn.execute("SELECT has_schema_privilege(%s,'sales_ai_locks','USAGE'),"
        "has_schema_privilege(%s,'sales_ai_locks','CREATE')", [runtime, runtime]).fetchone() == (True, False),
        "Runtime schema privileges differ.")
    require(conn.execute("SELECT count(*) FROM pg_class WHERE relnamespace=%s", [schema[0]]).fetchone()[0] == 0,
            "Unexpected relations in capability schema.")
    functions = conn.execute("SELECT p.oid,p.proname,p.proowner,p.proargtypes::oid[],p.proargnames,p.prorettype,"
        "p.prosecdef,p.provolatile,p.proparallel,p.proconfig,p.prosrc,obj_description(p.oid,'pg_proc'),"
        "l.lanname,p.prokind,p.proisstrict,p.proleakproof,p.pronargdefaults "
        "FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.pronamespace=%s ORDER BY p.proname", [schema[0]]).fetchall()
    bodies = re.findall(r'AS \$body\$(.*?)\$body\$;', SOURCE.read_text(encoding='utf-8'), re.S)
    names = ['lock_feedback_references','lock_submission_references']
    require(len(functions) == 2 and len(bodies) == 2, "Unexpected capability functions.")
    function_state = []
    for index, row in enumerate(functions):
        oid,name,actual_owner,args,argnames,result,definer,volatility,parallel,config,body,version,language,kind,strict,leakproof,defaults = row
        require(name == names[index] and actual_owner == owner_oid and args == ([20,20] if index == 0 else [20,1016])
                and argnames == (['customer_id','recommendation_id'] if index == 0 else ['customer_id','product_ids'])
                and (result,definer,volatility,parallel,version,language,kind,strict,leakproof,defaults)
                    == (2278,True,'v','u',VERSION,'plpgsql','f',False,False,0)
                and set(config or []) == {'search_path=pg_catalog, pg_temp','row_security=on'}
                and body == bodies[index], "Capability body/signature/security differs from B6.")
        acl = conn.execute("SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_proc p "
            "CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
            "WHERE p.oid=%s ORDER BY 1,2", [oid]).fetchall()
        require(all(g in {owner_oid,runtime_oid} and p == 'EXECUTE' and (g != runtime_oid or not grantable)
                    for g,p,grantable in acl), "Unexpected function EXECUTE grants.")
        require(conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')", [runtime,oid]).fetchone()[0],
                "Runtime EXECUTE is missing.")
        function_state.append(dict(oid=oid,name=name,body_sha256=hashlib.sha256(body.encode()).hexdigest(),acl=acl))
    columns = []
    for table in TABLES:
        rows = conn.execute("SELECT a.attname,has_column_privilege(%s,c.oid,a.attnum,'SELECT'),"
            "has_column_privilege(%s,c.oid,a.attnum,'UPDATE'),has_any_column_privilege(%s,c.oid,'UPDATE'),c.relowner "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid "
            "WHERE n.nspname='public' AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
            [owner,owner,runtime,table]).fetchall()
        require({r[0] for r in rows if r[1]} == set(READ_COLUMNS[table]) and {r[0] for r in rows if r[2]} == {'id'}
                and all(not r[3] and r[4] != owner_oid for r in rows), "Reference column protection differs.")
        require(conn.execute("SELECT has_table_privilege(%s,%s,'INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
                             [owner,table]).fetchone()[0] is False, "Capability owner has unnecessary table privileges.")
        columns.append(dict(table=table,select=list(READ_COLUMNS[table]),update=['id']))
    require(conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                         "WHERE n.nspname='public' AND c.relowner=%s", [owner_oid]).fetchone()[0] == 0,
            "Capability owner owns public relations.")
    result = dict(version=VERSION,sha256=source_sha(),owner=owner,schema='sales_ai_locks',schema_oid=schema[0],
                  owner_oid=owner_oid,runtime_oid=runtime_oid,schema_acl=schema_acl,functions=function_state,columns=columns)
    return json.loads(json.dumps(result))


def _create(conn, *, owner):
    """Caller must verify exact target and role before this private DDL helper."""
    from psycopg import sql
    flags = conn.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                         "FROM pg_roles WHERE rolname=%s", [owner]).fetchone()
    require(flags == (False,) * 6, "Unsafe capability owner flags.")
    require(conn.execute("SELECT count(*) FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=%s) "
        "OR member=(SELECT oid FROM pg_roles WHERE rolname=%s)", [owner, owner]).fetchone()[0] == 0,
        "Capability owner must have no role memberships in either direction.")
    require(conn.execute("SELECT to_regnamespace('sales_ai_locks')").fetchone()[0] is None,
            "Capability schema already exists; never overwrite an uncertain installation.")
    conn.execute(sql.SQL("CREATE SCHEMA sales_ai_locks AUTHORIZATION {}").format(sql.Identifier(owner)))
    conn.execute("REVOKE ALL ON SCHEMA sales_ai_locks FROM PUBLIC")
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(owner)))
    for table in TABLES:
        conn.execute(sql.SQL("GRANT SELECT({}),UPDATE(id) ON TABLE public.{} TO {}")
                     .format(sql.SQL(',').join(map(sql.Identifier, READ_COLUMNS[table])), sql.Identifier(table), sql.Identifier(owner)))
    # Caller supplies one transaction: no PUBLIC-executable installation window.
    source = SOURCE.read_text(encoding="utf-8")
    conn.execute(source)
    for signature in SIGNATURES:
        conn.execute(sql.SQL("ALTER FUNCTION sales_ai_locks.{} OWNER TO {}")
                     .format(sql.SQL(signature), sql.Identifier(owner)))
        conn.execute(sql.SQL("GRANT EXECUTE ON FUNCTION sales_ai_locks.{} TO {}")
                     .format(sql.SQL(signature), sql.Identifier(RUNTIME)))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA sales_ai_locks TO {}").format(sql.Identifier(RUNTIME)))
    return inspect(conn, owner=owner)


def install(conn, *, database, oid, marker, owner):
    require(database.startswith("test_stage3h3b3_") and marker.startswith("sales-ai-demo-b3-disposable:")
            and owner.startswith("sa_lock_b6_") and len(owner) <= 63, "Only verified disposable installation is supported.")
    require(not conn.autocommit, "Capability installation requires one enclosing transaction.")
    actual = conn.execute("SELECT current_database(),current_user,d.oid,shobj_description(d.oid,'pg_database'),"
        "inet_server_port() FROM pg_database d WHERE datname=current_database()").fetchone()
    require(actual == (database, BOOTSTRAP, oid, marker,5432) and conn.info.host == '127.0.0.1' and conn.info.port == 5433,
            "Disposable installer identity mismatch.")
    source_sha()
    if conn.execute("SELECT to_regnamespace('sales_ai_locks')").fetchone()[0] is not None:
        return inspect(conn, owner=owner)
    return _create(conn, owner=owner)


def validate_runtime(conn, profile, state, *, owner=PERSISTENT_OWNER):
    """Read-only startup/new-connection fence; never installs or repairs objects."""
    from pathlib import Path
    from common import read_json
    path = Path(state) / 'lock-capabilities.json'
    manifest = read_json(path)
    require(path.with_suffix('.sha256').is_file(), "Capability registry checksum is missing.")
    require(path.with_suffix('.sha256').read_text(encoding='ascii').strip() == hashlib.sha256(path.read_bytes()).hexdigest(),
            "Capability registry checksum mismatch.")
    require(manifest.get('identity') == profile['identity'] and manifest.get('database_oid') == profile['database_oid']
            and manifest.get('database') == profile['database'], "Capability registry identity mismatch.")
    actual = inspect(conn, owner=owner, runtime=profile['runtime_role'])
    require(actual == manifest.get('snapshot'), "Capability objects/owner/grants differ from protected registry.")
    return actual
