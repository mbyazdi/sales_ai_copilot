"""Explicit fresh-generation registration / one-shot authorized C0005 activation.

Not a reset, promotion, date-preparation or ordinary startup command.
"""
import argparse
import re

from common import *


def activate(profile, state):
    from initialization import fixture_ready, schema_ready
    from lock_capabilities import validate_runtime
    with connect(profile,state) as raw:
        schema_ready(raw,profile)
        validate_runtime(raw,profile,state)
        manifest=fixture_ready(raw,profile,state,phase='fixtures_committed')
    configure_django(profile,state)
    check_schema(profile)
    from django.db import connection, transaction
    from django.test import Client
    from apps.visits.models import Visit
    account=read_json(state/'credentials/test-accounts.json')
    require(account.get('identity') == profile['identity'], 'Activation credential identity mismatch.')
    account=account['accounts']['salesperson']
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)',[89005433])
        visit=Visit.objects.select_for_update().get(pk=manifest['visits']['C0005']['id'])
        require(visit.status == 'PLANNED', 'Partial/uncertain activation; inspect instead of repeating Start.')
        client=Client(enforce_csrf_checks=True, HTTP_HOST=f"localhost:{profile['application_port']}")
        page=client.get('/accounts/login/')
        proof=re.search(rb'data-demo-proof="([^"]+)"',page.content)
        require(page.status_code == 200 and proof is not None, 'Activation login/proof unavailable.')
        client.defaults.update(HTTP_X_DEMO_GENERATION_PROOF=proof.group(1).decode(),HTTP_ORIGIN=profile['url'])
        login=client.post('/accounts/login/',dict(username=account['username'],password=account['password'],
            csrfmiddlewaretoken=client.cookies['csrftoken'].value))
        require(login.status_code == 302 and client.session.get('_auth_user_id') == str(visit.salesperson.user_id),
                'Activation requires the normal owning TEST login.')
        response=client.post(f'/api/visits/v1/visits/{visit.pk}/start/',b'{}',content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        require(response.status_code == 200, 'Authorized initial C0005 Start failed; activation rolled back.')
        result=response.json()
        require(result['visit']['id']==visit.pk and result['visit']['status']=='IN_PROGRESS', 'Unexpected Start result.')
        session_key=client.session.session_key
        logout=client.post('/accounts/logout/',HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        from django.contrib.sessions.models import Session
        require(logout.status_code==302 and not Session.objects.filter(session_key=session_key).exists(),
                'Activation logout failed.')
    # DB and filesystem publication are not atomic. Interruption here blocks
    # ordinary startup and retries; no inferred success or automatic adoption.
    from bootstrap import publish_manifest
    manifest.update(phase='complete',authorized_start=result)
    publish_manifest(manifest)
    print('Initial C0005 activated through normal runtime login/CSRF/Start/logout; fixtures complete.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['generation','activate'])
    parser.add_argument('--confirm-database',required=True,choices=[DATABASE])
    args=parser.parse_args()
    profile=load_profile();verify_container(profile)
    if args.command=='generation':
        from initialization import register_generation
        with connect(profile,DEFAULT_STATE,OWNER) as raw:
            print('Initial generation registration: '+register_generation(raw,profile,DEFAULT_STATE))
    else:
        activate(profile,DEFAULT_STATE)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Initialization stopped: '+(str(exc) if isinstance(exc,DemoError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
