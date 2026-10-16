"""Fresh-install prerequisites and read-only readiness; no automatic recovery."""
from datetime import date, datetime, timezone
from decimal import Decimal
from collections import Counter
import json

from common import OWNER, require, read_json, verify_connection, migration_fingerprint

FRAMEWORK = {'django_migrations', 'django_content_type', 'auth_permission'}
FIXTURE_TABLES = {'auth_user','visits_salesperson','customers_customergrade',
    'products_brand','products_category','products_product','inventory_inventory',
    'products_productdemoprice','customers_customer','customers_customer360',
    'visits_customerassignment','visits_visit','recommendations_customerrecommendation'}


def schema_ready(conn, profile):
    verify_connection(conn, profile, conn.info.user)
    require(conn.info.host == '127.0.0.1' and conn.info.port == 5433, 'Initialization endpoint mismatch.')
    require(migration_fingerprint() == (50, profile['migration_fingerprint']), 'Migration source drift.')
    rows = [list(r) for r in conn.execute('SELECT app,name FROM public.django_migrations ORDER BY app,name')]
    require(rows == profile['migration_keys'] and len(rows) == 50, 'Initialization requires the complete reviewed schema.')
    require(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0] == 40,
            'Unexpected public schema tables.')
    owners = conn.execute("SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','S')").fetchall()
    require(owners == [(OWNER,)], 'Unexpected Demo table/sequence owner.')
    require(conn.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='public'").fetchone()
            == (OWNER,), 'Unexpected Demo public schema owner.')


def empty_baseline(conn):
    from psycopg import sql
    tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")]
    require(len(tables) == 40 and FRAMEWORK <= set(tables), 'Unexpected initialization schema.')
    for name in tables:
        if name not in FRAMEWORK:
            require(conn.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0] == 0,
                    'Unregistered existing Demo rows; initialization refused: '+name)


def generation_ready(profile, state):
    from generation import validate_registry
    return validate_registry(read_json(state/'generation-state.json'), profile, read_json(state/'profile.json'))


def register_generation(conn, profile, state):
    """Explicit provisioning/recovery only. Never adopt a populated unregistered DB."""
    schema_ready(conn, profile)
    path = state/'generation-state.json'
    if path.exists():
        generation_ready(profile, state)
        return 'NO_OP'
    empty_baseline(conn)
    require(not (state/'fixtures/manifest.json').exists() and not (state/'credentials/test-accounts.json').exists(),
            'Unregistered fixture/account files require inspection.')
    from generation import initial_registry
    # Exclusive creation: a concurrent operator cannot overwrite a registry.
    # An interrupted/invalid file remains fail-closed for explicit inspection.
    with path.open('x',encoding='utf-8') as stream:
        json.dump(initial_registry(profile),stream,sort_keys=True,indent=2)
        stream.write('\n')
    return 'CREATED'


def fixture_ready(conn, profile, state, *, phase='complete'):
    """Bind the local manifest to versioned source and recorded live identities.

    Compare only fixture-owned fields, preserving later Visit/request history.
    No password rehash, login, sequence calls or ORM write side effects.
    """
    from bootstrap import definition, digest, VERSION
    from plan import checked_json, CUSTOMERS
    from psycopg import sql
    from django.core.serializers.json import DjangoJSONEncoder
    conn.execute("SET LOCAL TIME ZONE 'UTC'")
    generation_ready(profile,state)
    path=state/'fixtures/manifest.json'
    require(path.is_file() and path.with_suffix('.sha256').is_file(), 'Demo fixtures are not initialized.')
    manifest = checked_json(path)
    require(manifest.get('identity') == profile['identity'] and manifest.get('version') == VERSION
            and manifest.get('phase') == phase, 'Missing, foreign or incomplete Demo fixtures.')
    expected = definition(date.fromisoformat(manifest['preparation_date']))
    require(manifest.get('fixture') == json.loads(json.dumps(expected))
            and manifest.get('fixture_sha256') == digest(expected), 'Fixture source/date checksum mismatch.')
    require(set(manifest.get('visits',{})) == set(CUSTOMERS), 'Fixture Visit ownership mismatch.')
    records = manifest.get('records',[])
    require(records and {r['model'].replace('.','_') for r in records} == FIXTURE_TABLES,
            'Fixture model ownership set differs.')
    counts={'auth.user':3,'visits.salesperson':1,'customers.customergrade':3,
        'products.brand':len({p['brand'] for p in expected['products']}),
        'products.category':len({p['category'] for p in expected['products']}),
        'products.product':14,'inventory.inventory':13,'products.productdemoprice':14,
        'customers.customer':5,'customers.customer360':5,'visits.customerassignment':5,
        'visits.visit':5,'recommendations.customerrecommendation':15}
    require(Counter(r['model'] for r in records)==counts,'Incomplete fixture ownership manifest.')
    products={r['pk']:r['fields']['product_code'] for r in records if r['model']=='products.product'}
    require(set(products.values())==set(expected['prices']['prices']), 'Fixture product-code ownership mismatch.')
    require({r['fields']['customer_code'] for r in records if r['model']=='customers.customer'}==set(CUSTOMERS),
            'Fixture customer-code ownership mismatch.')
    price_products=[]
    for record in records:
        if record['model']=='products.productdemoprice':
            fields=record['fields'];code=products.get(fields['product_id']);price_products.append(code)
            require(code in expected['prices']['prices'] and
                    Decimal(str(fields['base_price']))==Decimal(expected['prices']['prices'][code]) and
                    all(fields[k]==expected['prices'][k] for k in ('currency','source','source_version')),
                    'Fixture price/source differs from approved dataset.')
    require(len(set(price_products))==14,'Duplicate fixture price ownership.')
    seen = set()
    for record in records:
        table = record['model'].replace('.','_')
        identity = (table,record['pk'])
        require(identity not in seen and type(record['pk']) is int and record['pk']>0, 'Duplicate/invalid fixture identity.')
        seen.add(identity)
        fields = record['fields']
        require(fields and 'password' not in fields and 'last_login' not in fields, 'Invalid fixture field contract.')
        names = list(fields)
        row = conn.execute(sql.SQL('SELECT {} FROM public.{} WHERE id=%s').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.Identifier(table)),[record['pk']]).fetchone()
        require(row is not None, 'Recorded fixture row is missing: '+table)
        actual,expected_fields={},dict(fields)
        for name,value in zip(names,row):
            if isinstance(value,Decimal):
                actual[name]=format(value.normalize(),'f')
                expected_fields[name]=format(Decimal(str(fields[name])).normalize(),'f')
            elif isinstance(value,datetime):
                saved=datetime.fromisoformat(fields[name].replace('Z','+00:00'))
                require(saved.utcoffset() is not None and value.utcoffset() is not None,'Naive fixture timestamp.')
                actual[name]=value.astimezone(timezone.utc)
                expected_fields[name]=saved.astimezone(timezone.utc)
            else:
                actual[name]=value
        actual = json.loads(json.dumps(actual,cls=DjangoJSONEncoder))
        expected_fields=json.loads(json.dumps(expected_fields,cls=DjangoJSONEncoder))
        require(actual == expected_fields, 'Recorded fixture fields changed: '+table)
    for code, visit in manifest['visits'].items():
        require(('visits_visit',visit['id']) in seen and conn.execute(
            'SELECT c.customer_code FROM visits_visit v JOIN customers_customer c ON c.id=v.customer_id WHERE v.id=%s',
            [visit['id']]).fetchone() == (code,), 'Fixture Visit/customer binding differs.')
    return manifest


def installation_state(conn, profile, state):
    """Capabilities can precede fixtures only on an exact empty initial baseline."""
    schema_ready(conn,profile)
    generation_ready(profile,state)
    if (state/'fixtures/manifest.json').exists():
        fixture_ready(conn,profile,state)
        return 'PREPARED'
    require(not (state/'credentials/test-accounts.json').exists(), 'Orphaned TEST credentials require inspection.')
    empty_baseline(conn)
    return 'EMPTY'
