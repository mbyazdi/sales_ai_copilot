"""Explicit B7 runtime validation: outer rollback and explicit IDs, no nextval."""
from uuid import uuid4

from common import *


def main():
    from deploy_lock_capabilities import isolated_preflight, maintenance, public_state
    from lock_capabilities import validate_runtime, TABLES
    from preservation import preservation, record_before, verify_before
    profile = load_profile()
    isolated_preflight(profile)
    before = preservation(profile)
    report = DEFAULT_STATE / 'reports' / ('b7-runtime-' + uuid4().hex)
    report.mkdir()
    operation = record_before(report/'before.json',profile,before,purpose='deployed-lock-probes')
    with maintenance(profile) as raw:
        full_before = public_state(raw)
    write_json(report / 'operator-data-before.json', full_before)
    with connect(profile, DEFAULT_STATE) as raw:
        snapshot = validate_runtime(raw, profile, DEFAULT_STATE)
    configure_django(profile, DEFAULT_STATE)
    check_schema(profile)
    from django.core.management import call_command
    call_command('makemigrations', check=True, dry_run=True, verbosity=1)
    from django.db import DatabaseError, connection, connections, transaction
    from apps.visits.models import Visit
    from apps.recommendations.models import CustomerRecommendation
    from lock_rollback_probe import exercise
    visit = Visit.objects.select_related('customer','salesperson__user').get(customer__customer_code='C0005',status='IN_PROGRESS')
    recommendation = CustomerRecommendation.objects.filter(customer=visit.customer,is_active=True).order_by('rank','pk').first()
    require(recommendation is not None, 'No saved recommendation for rollback validation.')
    evidence = exercise(visit.salesperson.user, visit, recommendation)
    denied = []
    from provision import APPEND_ONLY
    from psycopg import sql
    statements = [(f'UPDATE {table}', sql.SQL('UPDATE public.{} SET id=id WHERE false').format(sql.Identifier(table)))
                  for table in (*TABLES,'products_productdemoprice',*sorted(APPEND_ONLY))]
    statements += [(f'DELETE {table}', sql.SQL('DELETE FROM public.{} WHERE false').format(sql.Identifier(table)))
                   for table in sorted(APPEND_ONLY)]
    statements += [('DDL',sql.SQL('CREATE TABLE public.b7_forbidden_probe(id bigint)')),
                   ('role assumption',sql.SQL('SET ROLE sales_ai_demo_lock_owner'))]
    with transaction.atomic():
        for label, statement in statements:
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(statement)
            except DatabaseError as error:
                require(getattr(error.__cause__,'sqlstate',None) == '42501', 'Unexpected denial type: '+label)
                denied.append(label)
            else:
                transaction.set_rollback(True)
                raise DemoError('Unexpected runtime permission: '+label)
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL search_path=pg_temp,public')
            cursor.execute('SELECT sales_ai_locks.lock_feedback_references(%s,%s)',[visit.customer_id,recommendation.pk])
            cursor.execute('SELECT sales_ai_locks.lock_submission_references(%s,%s::bigint[])',[visit.customer_id,[recommendation.product_id]])
            cursor.execute('SELECT current_user')
            require(cursor.fetchone() == (RUNTIME,), 'Capability leaked privileged role.')
            # Independent maintenance writer confirms locks really survive function return.
            with connect(profile, DEFAULT_STATE, role=OWNER, readonly=False) as contender:
                try:
                    contender.execute('SELECT id FROM public.products_product WHERE id=%s FOR UPDATE NOWAIT',[recommendation.product_id])
                except Exception as error:
                    require(getattr(error,'sqlstate',None) == '55P03', 'Unexpected lock contention error.')
                    contender.rollback()
                else:
                    raise DemoError('Reference lock was not retained by runtime transaction.')
        transaction.set_rollback(True)
    # Owner has no EXECUTE despite owning the public reference tables.
    with connect(profile, DEFAULT_STATE, role=OWNER, readonly=False) as raw:
        try:
            raw.execute('SELECT sales_ai_locks.lock_feedback_references(%s,%s)',[visit.customer_id,recommendation.pk])
        except Exception as error:
            require(getattr(error,'sqlstate',None) == '42501', 'Unexpected unauthorized EXECUTE error.')
            raw.rollback()
            denied.append('unauthorized owner EXECUTE')
        else:
            raw.rollback()
            raise DemoError('Unauthorized EXECUTE unexpectedly allowed.')
    connections.close_all()
    after = preservation(profile)
    with maintenance(profile) as raw:
        full_after = public_state(raw)
    write_json(report / 'operator-data-after.json', full_after)
    require(full_before == full_after, 'Operator-visible rows/sequences differ after rollback probes.')
    write_json(report / 'after.json', after)
    require(verify_before(report/'before.json',profile,purpose='deployed-lock-probes',operation=operation)==before,
            'Original deployed-lock verification evidence changed.')
    require(before == after, 'Preservation differs after rollback probes; stop and inspect reports.')
    write_json(report / 'result.json', dict(version=snapshot['version'],sha256=snapshot['sha256'],
               rollback_services=evidence,denied=denied,locks_retained=True,preservation_identical=True,
               explicit_ids=True,sequence_resets=False))
    print('B7 runtime rollback/security verification passed; all table digests and sequences unchanged.')
    print('Evidence: '+str(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('B7 runtime verification stopped: '+(str(exc) if isinstance(exc,DemoError) else type(exc).__name__),file=sys.stderr)
        sys.exit(1)
