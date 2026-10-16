"""B2 real-process recovery tests. Only the guarded disposable runner may invoke."""
from uuid import uuid4

from tests_maintenance_gate import MaintenanceTests


class RecoveryTests(MaintenanceTests):
    def evidence(self,mode='pending-only'):
        owner=self.child(mode)
        record=owner.read();self.assertEqual(record['phase'],'PENDING')
        if mode=='exclusive':self.assertEqual(owner.read()['phase'],'EXCLUSIVE')
        return owner,record

    def arguments(self,evidence,recovery_uuid=None,profile=None):
        from scripts.demo.gate_recovery import confirmation
        from uuid import UUID
        operation=UUID(evidence['operation'])
        return dict(operation=operation,recovery_uuid=recovery_uuid or uuid4(),evidence_sha=evidence['evidence_sha'],
                    confirm=confirmation(profile or self.profile,operation,evidence['evidence_sha']))

    def recover(self,evidence,**changes):
        from scripts.demo.gate_recovery import recover_disposable
        args=self.arguments(evidence);args.update(changes)
        with self.raw() as raw:return recover_disposable(raw,self.profile,**args)

    def digest(self):
        from scripts.demo.gate_recovery import business_digest
        with self.raw() as raw:return business_digest(raw)

    def test_60_live_owner_before_and_after_exclusivity_refuses_recovery(self):
        from scripts.demo.maintenance_gate import GateRefused
        for mode in ('pending-only','exclusive'):
            owner,evidence=self.evidence(mode)
            with self.assertRaisesRegex(GateRefused,'live'):self.recover(evidence)
            if mode=='exclusive':owner.send('finish');owner.wait()
            else:
                owner.close();self.recover(evidence)

    def test_61_owner_death_before_and_after_exclusive_exact_recovery_and_replay(self):
        for mode in ('pending-only','exclusive'):
            before=self.digest()
            owner,evidence=self.evidence(mode);owner.close()
            command=uuid4()
            first=self.recover(evidence,recovery_uuid=command)
            self.assertEqual(first['kind'],'RECOVERED')
            self.assertEqual(first,self.recover(evidence,recovery_uuid=command))
            self.assertEqual(self.digest(),before)
            from scripts.demo.maintenance_gate import GateRefused
            with self.assertRaisesRegex(GateRefused,'conflict'):self.recover(evidence)

    def test_62_active_request_prevents_recovery_until_rollback(self):
        from scripts.demo.maintenance_gate import GateRefused
        before=self.digest();key='rec-'+uuid4().hex;self.keys.append(key)
        reader=self.child('shared',key=key);self.assertEqual(reader.read()['phase'],'ADMITTED')
        owner,evidence=self.evidence();owner.close()
        with self.assertRaisesRegex(GateRefused,'still active'):self.recover(evidence)
        reader.send('rollback');reader.wait()
        self.recover(evidence);self.assertEqual(before,self.digest())

    def test_63_changed_data_or_sequence_baseline_is_never_adopted(self):
        from scripts.demo.maintenance_gate import GateRefused
        owner,evidence=self.evidence();owner.close()
        with self.raw() as raw:
            raw.execute('UPDATE auth_user SET last_login=CURRENT_TIMESTAMP WHERE id=%s',[self.user.pk])
        changed=self.digest()
        with self.assertRaisesRegex(GateRefused,'baseline changed'):self.recover(evidence)
        self.assertEqual(changed,self.digest())
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone(),('PENDING',))

    def test_64_missing_or_tampered_evidence_fails_closed(self):
        from scripts.demo.maintenance_gate import GateRefused
        from psycopg.types.json import Jsonb
        owner,evidence=self.evidence();owner.close()
        with self.raw() as raw:
            original=raw.execute('SELECT envelope FROM sales_ai_demo_control.operations WHERE operation=%s',[evidence['operation']]).fetchone()[0]
            raw.execute('UPDATE sales_ai_demo_control.operations SET envelope=%s WHERE operation=%s',
                        [Jsonb({**original,'signature':'tampered'}),evidence['operation']])
        with self.assertRaisesRegex(GateRefused,'signature'):self.recover(evidence)
        with self.raw() as raw:raw.execute('DELETE FROM sales_ai_demo_control.operations WHERE operation=%s',[evidence['operation']])
        with self.assertRaisesRegex(GateRefused,'missing'):self.recover(evidence)

    def test_65_wrong_confirmation_generation_database_or_evidence_rejected(self):
        from scripts.demo.maintenance_gate import GateRefused
        from scripts.demo.gate_recovery import recover_disposable
        owner,evidence=self.evidence();owner.close()
        for changes in ({'confirm':'yes'},{'evidence_sha':'0'*64},{'evidence_sha':None}):
            with self.subTest(changes=changes),self.assertRaises(GateRefused):self.recover(evidence,**changes)
        for profile in ({**self.profile,'database_oid':self.profile['database_oid']+1},
                        {**self.profile,'identity':str(uuid4())},
                        {**self.profile,'database':'sales_ai_db'}):
            with self.raw() as raw,self.assertRaises(GateRefused):
                recover_disposable(raw,profile,**self.arguments(evidence,profile=profile))

    def test_66_competing_recovery_processes_and_interrupted_commit(self):
        owner,evidence=self.evidence();owner.close();before=self.digest()
        args=self.arguments(evidence)
        wire={k:str(v) for k,v in args.items()}
        first=self.child('recovery',**wire,pause=True)
        self.assertEqual(first.read()['phase'],'RECOVERY_UNCOMMITTED')
        second=self.child('recovery',**wire)
        self.assertEqual(second.read()['phase'],'REFUSED');second.wait()
        # A fresh app process sees old committed PENDING, not uncommitted ACTIVE.
        app=self.child('http',mode_name='new')
        self.assertEqual(app.read(),{'phase':'LOGIN_BLOCKED','status':503});app.wait()
        first.close()
        with self.raw() as raw:
            self.assertEqual(raw.execute('SELECT phase FROM sales_ai_demo_control.admission').fetchone(),('PENDING',))
            self.assertEqual(raw.execute('SELECT count(*) FROM sales_ai_demo_control.results WHERE operation=%s',[args['operation']]).fetchone(),(0,))
        self.assertEqual(before,self.digest())
        retry=self.child('recovery',**wire)
        self.assertEqual(retry.read()['phase'],'RECOVERED');retry.wait()
        self.assertEqual(before,self.digest())

    def test_67_pending_survives_new_workers_and_clean_release_is_audited(self):
        owner,evidence=self.evidence('exclusive');before=self.digest()
        for _ in range(2):
            app=self.child('http',mode_name='new')
            self.assertEqual(app.read(),{'phase':'LOGIN_BLOCKED','status':503});app.wait()
        owner.send('finish');owner.wait()
        self.assertEqual(before,self.digest())
        with self.raw() as raw:
            envelope=raw.execute('SELECT envelope FROM sales_ai_demo_control.results WHERE operation=%s',[evidence['operation']]).fetchone()[0]
            from scripts.demo.gate_recovery import verify
            self.assertEqual(verify(envelope)['kind'],'RELEASED')

    def test_68_drain_timeout_live_owner_rejected_then_explicit_abandoned_recovery(self):
        import psycopg
        from scripts.demo.maintenance_gate import ExclusiveGate,GateRefused
        key='rec-'+uuid4().hex;self.keys.append(key)
        reader=self.child('shared',key=key);self.assertEqual(reader.read()['phase'],'ADMITTED')
        raw=self.raw()
        gate=ExclusiveGate(raw,self.profile,uuid4());gate.announce()
        evidence=dict(operation=str(gate.operation),evidence_sha=raw.execute('SELECT evidence_sha FROM sales_ai_demo_control.admission').fetchone()[0]);raw.rollback()
        raw.execute("SET lock_timeout='100ms'");raw.commit()
        try:
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                with gate.exclusive():self.fail('Not drained')
            with self.assertRaisesRegex(GateRefused,'live'):self.recover(evidence)
        finally:raw.close()
        reader.send('rollback');reader.wait()
        self.recover(evidence)

    def test_69_recovery_result_and_operation_history_not_runtime_writable(self):
        import psycopg
        owner,evidence=self.evidence();owner.close();self.recover(evidence)
        for table in ('operations','results'):
            for verb in ('UPDATE','DELETE'):
                statement=f'UPDATE sales_ai_demo_control.{table} SET envelope=\'{{}}\'' if verb=='UPDATE' else f'DELETE FROM sales_ai_demo_control.{table}'
                with self.raw(self.profile['runtime_role']) as raw,self.assertRaises(psycopg.errors.InsufficientPrivilege):raw.execute(statement)

    def test_70_readonly_readiness_and_loaded_worker_signature(self):
        from scripts.demo.gate_readiness import worker_matches,worker_signature
        from scripts.demo.maintenance_gate import verify_ready
        from unittest.mock import patch
        with self.raw(self.profile['runtime_role']) as raw:
            raw.execute('SET TRANSACTION READ ONLY');verify_ready(raw,self.profile)
        expected=worker_signature()
        self.assertTrue(worker_matches({'maintenance_gate':expected}))
        self.assertFalse(worker_matches({}))
        self.assertFalse(worker_matches({'maintenance_gate':{**expected,'version':'DEMO_MAINTENANCE_V1'}}))
        # Health uses loaded bytes, never blesses a changed file on disk.
        with patch('pathlib.Path.read_bytes',side_effect=AssertionError('Must not recompute loaded evidence')):
            self.assertEqual(worker_signature(),expected)

    def test_71_gate_only_maintenance_business_change_rolls_back_and_can_be_reviewed(self):
        from scripts.demo.maintenance_gate import ExclusiveGate,GateRefused
        before=self.digest();raw=self.raw()
        gate=ExclusiveGate(raw,self.profile,uuid4());gate.announce()
        evidence=dict(operation=str(gate.operation),evidence_sha=raw.execute('SELECT evidence_sha FROM sales_ai_demo_control.admission').fetchone()[0]);raw.rollback()
        try:
            with self.assertRaisesRegex(GateRefused,'changed protected data'):
                with gate.exclusive() as cursor:
                    cursor.execute('UPDATE auth_user SET first_name=%s WHERE id=%s',['not-permitted-gate-work',self.user.pk])
        finally:raw.close()
        self.assertEqual(before,self.digest())
        self.recover(evidence);self.assertEqual(before,self.digest())

    def test_72_missing_signing_key_and_stale_source_evidence_refuse_release(self):
        from scripts.demo import gate_recovery
        from scripts.demo.maintenance_gate import GateRefused
        from unittest.mock import patch
        owner,evidence=self.evidence();owner.close()
        signing=self.state_dir/'credentials/control-token.key'
        saved=signing.read_bytes()
        try:
            signing.write_bytes(b'invalid-disposable-test-key')
            with self.assertRaisesRegex(GateRefused,'key is unavailable'):self.recover(evidence)
        finally:signing.write_bytes(saved)
        original=gate_recovery.binding(self.profile)
        with patch.object(gate_recovery,'binding',return_value={**original,'source':{'stale':'0'*64}}):
            with self.assertRaisesRegex(GateRefused,'identity mismatch'):self.recover(evidence)
        self.recover(evidence)
