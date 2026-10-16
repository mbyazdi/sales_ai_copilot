"""B6 disposable PostgreSQL tests: real runtime logins, SQL and competing writers."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from threading import Event
import time
from uuid import uuid4

from common import BOOTSTRAP, OWNER, RUNTIME
from tests_generation_postgres import LiveGenerationTests


class CapabilitySecurityTests(LiveGenerationTests):
    def denied(self, statement, params=None, code="42501"):
        from django.db import DatabaseError, connection, transaction
        with self.assertRaises(DatabaseError) as error:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(statement, params)
        self.assertEqual(error.exception.__cause__.sqlstate, code)

    def test_20_owner_search_path_and_exact_grants(self):
        from django.db import connection
        from lock_capabilities import TABLES, READ_COLUMNS
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            self.assertEqual(cursor.fetchone()[0], RUNTIME)
            cursor.execute("SELECT pg_get_userbyid(proowner),prosecdef,provolatile,proparallel,proconfig,"
                "obj_description(p.oid,'pg_proc') FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='sales_ai_locks' ORDER BY proname")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)
            for owner, definer, volatility, parallel, config, version in rows:
                self.assertEqual((owner, definer, volatility, parallel, version),
                                 (self.capability_owner, True, 'v', 'u', 'REFERENCE_LOCKS_V1'))
                self.assertEqual(set(config), {'search_path=pg_catalog, pg_temp', 'row_security=on'})
            cursor.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
                "WHERE n.nspname='sales_ai_locks' AND a.grantee=0 AND a.privilege_type='EXECUTE'")
            self.assertEqual(cursor.fetchone()[0], 0)
            cursor.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                           "FROM pg_roles WHERE rolname=%s", [self.capability_owner])
            self.assertEqual(cursor.fetchone(), (False,) * 6)
            cursor.execute("SELECT count(*) FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=%s) "
                           "OR member=(SELECT oid FROM pg_roles WHERE rolname=%s)", [self.capability_owner] * 2)
            self.assertEqual(cursor.fetchone()[0], 0)
            for table in TABLES:
                cursor.execute("SELECT has_any_column_privilege(current_user,%s,'UPDATE'),"
                               "has_column_privilege(%s,%s,'id','UPDATE')", [table, self.capability_owner, table])
                self.assertEqual(cursor.fetchone(), (False, True))
                cursor.execute("SELECT a.attname,has_column_privilege(%s,c.oid,a.attnum,'SELECT'),"
                    "has_column_privilege(%s,c.oid,a.attnum,'UPDATE') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='public' AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped",
                    [self.capability_owner, self.capability_owner, table])
                columns = cursor.fetchall()
                self.assertEqual({n for n, readable, _ in columns if readable}, set(READ_COLUMNS[table]))
                self.assertEqual({n for n, _, writable in columns if writable}, {'id'})
            # A hostile caller search_path and shadow relations must not influence either function.
            cursor.execute("SET LOCAL search_path=b6_hostile,public,pg_temp")
            cursor.execute("SELECT sales_ai_locks.lock_feedback_references(%s,%s)", [self.customer.pk, self.recs[0].pk])
            cursor.execute("SELECT sales_ai_locks.lock_submission_references(%s,%s::bigint[])", [self.customer.pk, [self.products[0].pk]])
            cursor.execute("SELECT current_user")
            self.assertEqual(cursor.fetchone()[0], RUNTIME)
            cursor.execute("SET LOCAL search_path=public")

    def test_21_runtime_reference_dml_append_only_ddl_and_role_assumption_denied(self):
        from lock_capabilities import TABLES
        from provision import APPEND_ONLY
        before = self.state()
        for table in TABLES:
            self.denied(f"UPDATE public.{table} SET id=id+100000 WHERE id=1")
            self.denied(f"DELETE FROM public.{table} WHERE FALSE")
        self.denied("UPDATE products_productdemoprice SET base_price=0 WHERE FALSE")
        for table in sorted(APPEND_ONLY):
            self.denied(f"UPDATE public.{table} SET id=id WHERE FALSE")
            self.denied(f"DELETE FROM public.{table} WHERE FALSE")
        self.denied("CREATE TABLE public.b6_forbidden(id int)")
        self.denied("CREATE TABLE sales_ai_locks.b6_forbidden(id int)")
        self.denied("CREATE TEMP TABLE b6_forbidden(id int)")
        self.denied(f"SET LOCAL ROLE {self.capability_owner}")
        self.assertEqual(self.state(), before)
        with self.probe(OWNER) as unauthorized:
            import psycopg
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                unauthorized.execute("SELECT sales_ai_locks.lock_feedback_references(%s,%s)", [self.customer.pk, self.recs[0].pk])

    def test_22_invalid_sql_and_adapter_inputs_fail_without_effects(self):
        from apps.core.reference_locks import lock_feedback_references, lock_submission_references
        from django.core.exceptions import ValidationError
        before = self.state()
        for customer, recommendation in ((None, 1), (1, None), (0, 1), (1, -1)):
            self.denied("SELECT sales_ai_locks.lock_feedback_references(%s::bigint,%s::bigint)",
                        [customer, recommendation], "22023")
        for products in (None, [None], [0], [-1], [1] * 51, [[1, 2]]):
            self.denied("SELECT sales_ai_locks.lock_submission_references(%s::bigint,%s::bigint[])",
                        [self.customer.pk, products], "22023")
        for value in (True, 0, -1, '1', None, 1.5):
            with self.assertRaises(ValidationError): lock_feedback_references(value, self.recs[0].pk)
            with self.assertRaises(ValidationError): lock_submission_references(self.customer.pk, [value])
        with self.assertRaises(ValidationError): lock_submission_references(self.customer.pk, [1] * 51)
        self.assertEqual(self.state(), before)

    def test_23_quoted_rounding_missing_prices_unknown_stock_and_replay_unchanged(self):
        # All commercial perturbations occur in this rollback-only disposable transaction.
        from django.db import connection
        from apps.sales_requests.models import SalesRequest
        with self.probe(BOOTSTRAP) as writer:
            # Grade/price fixture changes are independently committed before API reads.
            writer.execute("UPDATE customers_customergrade SET code='A' WHERE id=%s", [self.grade.pk])
            writer.execute("UPDATE products_productdemoprice SET base_price=105 WHERE product_id=%s", [self.products[0].pk])
        try:
            response = self.add(self.add_command(quantity=3))
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['saved_totals'], dict(base='315', discount='30', final='285'))
            # Other products exercise truthfully distinct price/stock states.
            quote = self.client.get(f"/api/sales-requests/v1/visits/{self.visit.pk}/basket/quote/",
                dict(customer_code=self.customer.customer_code, product_id=self.products[5].pk, quantity=1)).json()
            self.assertIn('INVENTORY_UNKNOWN', [i['reason_code'] for i in quote['items']])
            quote = self.client.get(f"/api/sales-requests/v1/visits/{self.visit.pk}/basket/quote/",
                dict(customer_code=self.customer.customer_code, product_id=self.products[4].pk, quantity=1)).json()
            self.assertIn('OUT_OF_STOCK', [i['reason_code'] for i in quote['items']])
            self.assertEqual(SalesRequest.objects.get().revision, 1)
        finally:
            with self.probe(BOOTSTRAP) as writer:
                writer.execute("UPDATE customers_customergrade SET code='C' WHERE id=%s", [self.grade.pk])
                writer.execute("UPDATE products_productdemoprice SET base_price=123 WHERE product_id=%s", [self.products[0].pk])


class CapabilityConcurrencyTests(LiveGenerationTests):
    """Committed disposable fixtures permit real independent HTTP transactions."""
    def setUp(self):
        from django.db import connection
        from apps.visits.models import Visit
        self.assertEqual(connection.settings_dict['NAME'], self.test_profile['database'])
        self.assertTrue(connection.get_autocommit())
        from psycopg import sql
        with self.probe(BOOTSTRAP) as owner:
            columns = [r[0] for r in owner.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='visits_visit' AND column_name<>'id' ORDER BY ordinal_position")]
            fields = sql.SQL(',').join(map(sql.Identifier, columns))
            pk = owner.execute(sql.SQL("INSERT INTO public.visits_visit ({}) SELECT {} FROM public.visits_visit WHERE id=%s RETURNING id")
                .format(fields, fields), [type(self).visit.pk]).fetchone()[0]
        self.visit = Visit.objects.get(pk=pk)
        self.client = self.login(self.user)

    def async_request(self, callback, ready):
        from django.db import connection, connections
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid(),current_user')
                ready.pid, role = cursor.fetchone()
                self.assertEqual(role, RUNTIME)
            ready.set()
            return callback()
        finally:
            connections.close_all()

    def wait_blocked(self, ready, blocker_pid):
        self.assertTrue(ready.wait(5), 'Independent writer did not start')
        deadline = time.monotonic() + 4
        with self.probe(BOOTSTRAP) as observer:
            while time.monotonic() < deadline:
                row = observer.execute("SELECT %s=ANY(pg_blocking_pids(%s))", [blocker_pid, ready.pid]).fetchone()
                if row and row[0]: return
                time.sleep(.01)
        self.fail('Expected real PostgreSQL lock wait was not observed')

    def submit_command(self):
        response = self.client.get(f"/api/sales-requests/v1/visits/{self.visit.pk}/review/",
            dict(customer_code=self.customer.customer_code))
        self.assertEqual(response.status_code, 200)
        review = response.json()
        self.assertTrue(review['can_submit'])
        return dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()), catalog_context=self.context(),
            expected_request_revision=review['request']['revision'], accepted_review_fingerprint=review['review_fingerprint'])

    def test_30_reference_locks_retained_until_commit_and_rollback(self):
        cases = [
            ('feedback', 'recommendations_customerrecommendation', 'is_active', self.recs[0].pk),
            ('feedback', 'products_product', 'is_active', self.products[0].pk),
            ('submission', 'customers_customer', 'is_active', self.customer.pk),
            ('submission', 'customers_customergrade', 'is_active', self.grade.pk),
            ('submission', 'products_product', 'is_active', self.products[0].pk),
            ('submission', 'inventory_inventory', 'available_quantity', self.products[0].inventory.pk),
        ]
        for mode in ('commit', 'rollback'):
            for operation, table, column, pk in cases:
                with self.subTest(mode=mode, table=table), self.probe() as holder:
                    if operation == 'feedback':
                        holder.execute('SELECT sales_ai_locks.lock_feedback_references(%s,%s)', [self.customer.pk, self.recs[0].pk])
                    else:
                        holder.execute('SELECT sales_ai_locks.lock_submission_references(%s,%s::bigint[])', [self.customer.pk, [self.products[0].pk]])
                    holder_pid = holder.execute('SELECT pg_backend_pid()').fetchone()[0]
                    ready = Event()
                    def competing_write():
                        with self.probe(BOOTSTRAP) as writer:
                            ready.pid = writer.execute('SELECT pg_backend_pid()').fetchone()[0]
                            ready.set()
                            expression = f'NOT {column}' if column == 'is_active' else f'{column}+1'
                            count = writer.execute(f'UPDATE public.{table} SET {column}={expression} WHERE id=%s', [pk]).rowcount
                            writer.rollback()
                            return count
                    with ThreadPoolExecutor(1) as pool:
                        future = pool.submit(competing_write)
                        try: self.wait_blocked(ready, holder_pid)
                        finally: getattr(holder, mode)()
                        self.assertEqual(future.result(8), 1)

    def test_31_feedback_rereads_after_recommendation_or_product_deactivation(self):
        from apps.recommendations.models import RecommendationFeedbackEvent
        for table, pk in (('recommendations_customerrecommendation', self.recs[0].pk), ('products_product', self.products[0].pk)):
            token = self.context()
            command = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()),
                recommendation_id=self.recs[0].pk, action='LATER', catalog_context=token)
            path = f'/api/recommendations/v1/visits/{self.visit.pk}/feedback/'
            try:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET is_active=FALSE WHERE id=%s', [pk])
                    pid = writer.execute('SELECT pg_backend_pid()').fetchone()[0]
                    ready = Event()
                    with ThreadPoolExecutor(1) as pool:
                        future = pool.submit(self.async_request, lambda: self.send(path, command), ready)
                        try: self.wait_blocked(ready, pid)
                        finally: writer.commit()
                        response = future.result(8)
                        self.assertEqual(response.status_code, 409)
                        self.assertEqual(response.json()['code'], 'CATALOG_CONTEXT_UNAVAILABLE')
            finally:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET is_active=TRUE WHERE id=%s', [pk])
        self.assertFalse(RecommendationFeedbackEvent.objects.filter(visit=self.visit).exists())

    def test_32_submit_rereads_customer_grade_and_stock_after_waiting(self):
        from apps.sales_requests.models import SalesRequest
        self.assertEqual(self.add().status_code, 201)
        path = f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/'
        cases = [('customers_customer', 'grade_id', None, self.customer.pk, self.grade.pk, 'PRICE_CHANGED'),
                 ('customers_customergrade', 'code', 'B', self.grade.pk, 'C', 'PRICE_CHANGED'),
                 ('inventory_inventory', 'available_quantity', 0, self.products[0].inventory.pk, 10, 'OUT_OF_STOCK')]
        for table, column, value, pk, old, expected in cases:
            command = self.submit_command()
            try:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET {column}=%s WHERE id=%s', [value, pk])
                    pid = writer.execute('SELECT pg_backend_pid()').fetchone()[0]
                    ready = Event()
                    with ThreadPoolExecutor(1) as pool:
                        future = pool.submit(self.async_request, lambda: self.send(path, command), ready)
                        try: self.wait_blocked(ready, pid)
                        finally: writer.commit()
                        response = future.result(8)
                        self.assertEqual((response.status_code, response.json()['code']), (409, expected))
                request = SalesRequest.objects.get(visit=self.visit)
                self.assertEqual((request.status, request.revision), ('DRAFT', 1))
                self.assertIsNone(request.submission_key)
            finally:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET {column}=%s WHERE id=%s', [old, pk])

    def test_33_submit_vs_basket_edit_and_completion(self):
        from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestAcknowledgement
        from threading import Barrier
        self.assertEqual(self.add().status_code, 201)
        submit = self.submit_command()
        edit = self.add_command(quantity=2); edit.pop('product_id')
        line = SalesRequestLine.objects.get(sales_request__visit=self.visit, is_selected=True)
        second_client = self.login(self.user)
        gate = Barrier(2)
        def request(path, command, method, client):
            from django.db import connections
            try:
                gate.wait(5)
                return self.send(path, command, method, client=client)
            finally: connections.close_all()
        submit_path = f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/'
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(request, submit_path, submit, 'post', self.client)
            b = pool.submit(request, f'/api/sales-requests/v1/requests/{line.sales_request_id}/lines/{line.pk}/', edit, 'patch', second_client)
            results = [a.result(12), b.result(12)]
        self.assertEqual(sum(r.status_code in (200, 201) for r in results), 1)
        self.assertEqual(sum(r.status_code == 409 for r in results), 1)
        # If edit won, obtain a fresh review before racing completion.
        request_row = SalesRequest.objects.get(visit=self.visit)
        if request_row.status == 'DRAFT': submit = self.submit_command()
        finish = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()))
        gate = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(request, submit_path, submit, 'post', self.client)
            b = pool.submit(request, f'/api/visits/v1/visits/{self.visit.pk}/completion/', finish, 'post', second_client)
            submitted, finished = a.result(12), b.result(12)
        self.assertEqual(finished.status_code, 200)
        self.assertIn(submitted.status_code, (201, 409))
        request_row.refresh_from_db()
        self.assertEqual(SalesRequestAcknowledgement.objects.filter(sales_request=request_row).count(), int(request_row.status == 'SUBMITTED'))

    def test_34_adapter_requires_transaction_and_missing_function_rolls_back(self):
        from apps.core.reference_locks import lock_feedback_references
        from django.db.transaction import TransactionManagementError
        from django.db import DatabaseError
        with self.assertRaises(TransactionManagementError): lock_feedback_references(self.customer.pk, self.recs[0].pk)
        # Rename a function only in this disposable DB; production/Demo never touched.
        signature = 'sales_ai_locks.lock_submission_references(bigint,bigint[])'
        with self.probe(BOOTSTRAP) as owner:
            owner.execute(f'ALTER FUNCTION {signature} RENAME TO submission_held')
        try:
            self.assertEqual(self.add().status_code, 201)
            before = self.state()
            with self.assertRaises(DatabaseError):
                self.send(f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/', self.submit_command())
            self.assertEqual(self.state(), before)
        finally:
            with self.probe(BOOTSTRAP) as owner:
                owner.execute('ALTER FUNCTION sales_ai_locks.submission_held(bigint,bigint[]) RENAME TO lock_submission_references')
        with self.probe(BOOTSTRAP) as owner:
            owner.execute('ALTER FUNCTION sales_ai_locks.lock_feedback_references(bigint,bigint) RENAME TO feedback_held')
        try:
            before = self.state()
            with self.assertRaises(DatabaseError):
                self.send(f'/api/recommendations/v1/visits/{self.visit.pk}/feedback/',
                    dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()),
                         recommendation_id=self.recs[1].pk, action='LATER', catalog_context=self.context(), expected_request_revision=1))
            self.assertEqual(self.state(), before)
        finally:
            with self.probe(BOOTSTRAP) as owner:
                owner.execute('ALTER FUNCTION sales_ai_locks.feedback_held(bigint,bigint) RENAME TO lock_feedback_references')

    def test_35_explicit_reference_lock_order_and_sorted_product_inventory_ids(self):
        import psycopg
        low, high = sorted(p.pk for p in (self.products[0], self.products[3]))
        cases = [
            # blocker, already locked row, row not reached yet, capability
            ('products_product', self.products[0].pk,
             'recommendations_customerrecommendation', self.recs[0].pk, None, None, 'feedback'),
            ('customers_customergrade', self.grade.pk,
             'customers_customer', self.customer.pk, 'products_product', low, 'submission'),
            ('products_product', high,
             'products_product', low, 'inventory_inventory', self.products[0].inventory.pk, 'submission'),
            ('inventory_inventory', self.products[3].inventory.pk,
             'inventory_inventory', self.products[0].inventory.pk, None, None, 'submission'),
        ]
        for blocker_table, blocker_pk, earlier_table, earlier_pk, later_table, later_pk, operation in cases:
            with self.subTest(stage=blocker_table, operation=operation), self.probe(BOOTSTRAP) as blocker:
                blocker.execute(f'SELECT id FROM public.{blocker_table} WHERE id=%s FOR UPDATE', [blocker_pk])
                blocker_pid = blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
                ready = Event()
                def acquire():
                    with self.probe() as holder:
                        ready.pid = holder.execute('SELECT pg_backend_pid()').fetchone()[0]
                        ready.set()
                        if operation == 'feedback':
                            holder.execute('SELECT sales_ai_locks.lock_feedback_references(%s,%s)', [self.customer.pk, self.recs[0].pk])
                        else:
                            # Reverse and duplicate input; sorting is server-side.
                            holder.execute('SELECT sales_ai_locks.lock_submission_references(%s,%s::bigint[])', [self.customer.pk, [high, low, high]])
                        holder.rollback()
                with ThreadPoolExecutor(1) as pool:
                    future = pool.submit(acquire)
                    try:
                        self.wait_blocked(ready, blocker_pid)
                        with self.probe(BOOTSTRAP) as checker:
                            with self.assertRaises(psycopg.errors.LockNotAvailable):
                                checker.execute(f'SELECT id FROM public.{earlier_table} WHERE id=%s FOR UPDATE NOWAIT', [earlier_pk])
                            checker.rollback()
                            if later_table:
                                self.assertIsNotNone(checker.execute(f'SELECT id FROM public.{later_table} WHERE id=%s FOR UPDATE NOWAIT', [later_pk]).fetchone())
                                checker.rollback()
                    finally: blocker.rollback()
                    future.result(8)

    def test_36_changed_and_missing_price_or_insufficient_stock_preserve_draft(self):
        from apps.sales_requests.models import SalesRequest
        self.assertEqual(self.add(self.add_command(quantity=3)).status_code, 201)
        path = f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/'
        command = self.submit_command()
        cases = [('products_productdemoprice', 'base_price', 200, 123, 'PRICE_CHANGED'),
                 ('products_productdemoprice', 'base_price', Decimal('0.5'), 123, 'PRICE_CONFIGURATION_ERROR'),
                 ('inventory_inventory', 'available_quantity', 4, 10, 'INSUFFICIENT_STOCK')]
        for table, column, value, old, expected in cases:
            try:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET {column}=%s WHERE product_id=%s', [value, self.products[0].pk])
                before = self.state()
                response = self.send(path, command)
                self.assertEqual((response.status_code, response.json()['code']), (409, expected))
                self.assertEqual(self.state(), before)
            finally:
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(f'UPDATE public.{table} SET {column}=%s WHERE product_id=%s', [old, self.products[0].pk])
        # Missing data is not zero; restore exact controlled fixture rows afterward.
        for statement, expected in (
            ('DELETE FROM public.products_productdemoprice WHERE product_id=%s', 'PRICE_UNAVAILABLE'),
            ('DELETE FROM public.inventory_inventory WHERE product_id=%s', 'INVENTORY_UNKNOWN'),
        ):
            # Use this disposable DB's operator to remove a controlled fixture and restore it afterward.
            with self.probe(BOOTSTRAP) as writer:
                table = 'products_productdemoprice' if 'productdemoprice' in statement else 'inventory_inventory'
                columns = [r[0] for r in writer.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                                                       "AND table_name=%s ORDER BY ordinal_position", [table])]
                row = writer.execute(f'SELECT * FROM public.{table} WHERE product_id=%s', [self.products[0].pk]).fetchone()
                writer.execute(statement, [self.products[0].pk]); writer.commit()
            try:
                before = self.state()
                response = self.send(path, command)
                self.assertEqual((response.status_code, response.json()['code']), (409, expected))
                self.assertEqual(self.state(), before)
            finally:
                from psycopg import sql
                with self.probe(BOOTSTRAP) as writer:
                    writer.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(sql.Identifier(table),
                        sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns)), row)
        request = SalesRequest.objects.get(visit=self.visit)
        self.assertEqual((request.status, request.revision), ('DRAFT', 1))

    def test_37_concurrent_duplicate_and_conflicting_submission_commands(self):
        from django.core import signing
        from django.db import connections
        from apps.recommendations.catalog_context import CONTEXT_SALT
        from apps.sales_requests.models import SalesRequest
        from threading import Barrier
        self.assertEqual(self.add().status_code, 201)
        command = self.submit_command()
        second = self.login(self.user)
        path = f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/'
        gate = Barrier(2)
        def submit(client):
            try:
                gate.wait(5)
                return self.send(path, command, client=client)
            finally: connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(submit, self.client), pool.submit(submit, second)
            first, replay = a.result(12), b.result(12)
        self.assertEqual((first.status_code, replay.status_code), (201, 201))
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(sorted([first['Idempotent-Replayed'], replay['Idempotent-Replayed']]), ['false', 'true'])
        self.assertEqual(SalesRequest.objects.filter(visit=self.visit).count(), 1)
        self.assertEqual(SalesRequest.objects.get(visit=self.visit).revision, 2)
        changed = {**command, 'catalog_context': signing.dumps(signing.loads(command['catalog_context'], salt=CONTEXT_SALT), salt=CONTEXT_SALT, compress=False)}
        self.assertNotEqual(changed['catalog_context'], command['catalog_context'])
        response = self.send(path, changed)
        self.assertEqual((response.status_code, response.json()['code']), (409, 'COMMAND_CONFLICT'))
        # Exact committed recovery does not need the reference functions at all.
        with self.probe(BOOTSTRAP) as owner:
            owner.execute('ALTER FUNCTION sales_ai_locks.lock_submission_references(bigint,bigint[]) RENAME TO submission_held')
        try:
            before = self.state()
            self.assertEqual(self.send(path, command).json(), first.json())
            self.assertEqual(self.state(), before)
        finally:
            with self.probe(BOOTSTRAP) as owner:
                owner.execute('ALTER FUNCTION sales_ai_locks.submission_held(bigint,bigint[]) RENAME TO lock_submission_references')

    def test_38_lock_timeout_rolls_back_without_receipt_or_automatic_retry(self):
        from django.db import DatabaseError, connection
        from apps.recommendations.models import RecommendationFeedbackEvent
        command = dict(customer_code=self.customer.customer_code, command_uuid=str(uuid4()),
            recommendation_id=self.recs[0].pk, action='LATER', catalog_context=self.context())
        path = f'/api/recommendations/v1/visits/{self.visit.pk}/feedback/'
        with connection.cursor() as cursor:
            cursor.execute('SHOW lock_timeout'); old_timeout = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('lock_timeout','100ms',false)")
        try:
            with self.probe(BOOTSTRAP) as blocker:
                blocker.execute('SELECT id FROM recommendations_customerrecommendation WHERE id=%s FOR UPDATE', [self.recs[0].pk])
                before = self.state()
                with self.assertRaises(DatabaseError) as error:
                    self.send(path, command)
                self.assertEqual(error.exception.__cause__.sqlstate, '55P03')
                self.assertEqual(self.state(), before)
                self.assertFalse(RecommendationFeedbackEvent.objects.filter(visit=self.visit).exists())
                blocker.rollback()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('lock_timeout',%s,false)", [old_timeout])
        # Only an explicit caller retry after the failure may create the event.
        self.assertEqual(self.send(path, command).status_code, 201)
        self.assertEqual(RecommendationFeedbackEvent.objects.filter(visit=self.visit).count(), 1)

    def test_39_concurrent_same_uuid_different_valid_intents_conflict(self):
        from django.core import signing
        from django.db import connections
        from apps.recommendations.catalog_context import CONTEXT_SALT
        from apps.sales_requests.models import SalesRequest
        from threading import Barrier
        self.assertEqual(self.add().status_code, 201)
        command = self.submit_command()
        changed = {**command, 'catalog_context': signing.dumps(signing.loads(command['catalog_context'], salt=CONTEXT_SALT), salt=CONTEXT_SALT, compress=False)}
        self.assertNotEqual(command['catalog_context'], changed['catalog_context'])
        second = self.login(self.user)
        gate = Barrier(2)
        def submit(client, body):
            try:
                gate.wait(5)
                return self.send(f'/api/sales-requests/v1/visits/{self.visit.pk}/submit/', body, client=client)
            finally: connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(submit, self.client, command), pool.submit(submit, second, changed)
            results = [a.result(12), b.result(12)]
        self.assertEqual(sorted(r.status_code for r in results), [201, 409])
        self.assertEqual(next(r for r in results if r.status_code == 409).json()['code'], 'COMMAND_CONFLICT')
        self.assertEqual(SalesRequest.objects.get(visit=self.visit).revision, 2)
