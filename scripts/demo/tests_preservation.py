"""Focused evidence tests; no DB writes. Also reused in disposable initialization."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from common import *
import preservation as evidence


def baseline_checks(profile,state,snapshot):
    """Exercise recovery without historical artifacts or touching database rows."""
    checks=[]
    with tempfile.TemporaryDirectory(dir=state) as directory:
        directory=Path(directory);path=directory/'before.json';purpose='evidence-regression'
        operation=evidence.record_before(path,profile,snapshot,purpose=purpose,state=state)
        saved=path.read_bytes()
        def verify(**kw):
            return evidence.verify_before(path,profile,purpose=kw.get('purpose',purpose),
                                          operation=kw.get('operation',operation),state=state)
        def denied(label,fn):
            try: fn()
            except (DemoError,ValueError,FileExistsError): checks.append(label)
            else: raise AssertionError('Unsafe baseline accepted: '+label)
        require(verify()==json.loads(json.dumps(snapshot,default=str)),'Canonical baseline replay differs.')
        checks.append('valid-current-evidence')
        denied('exclusive-no-rebase',lambda:evidence.record_before(path,profile,snapshot,purpose=purpose,state=state))
        path.unlink();denied('missing-baseline',verify)
        path.write_text('{');denied('invalid-json',verify)
        path.write_bytes(saved)
        value=json.loads(saved);value['payload']['snapshot']['files']={}
        write_json(path,value);denied('tampered-payload',verify)
        # An attacker recomputing a public checksum cannot forge the HMAC.
        value['signature']=hashlib.sha256(evidence.signed_bytes(value['payload'])).hexdigest()
        write_json(path,value);denied('public-checksum-not-authorization',verify)
        path.write_bytes(saved)
        denied('different-operation',lambda:verify(operation=str(uuid4())))
        denied('different-purpose',lambda:verify(purpose='foreign-operation'))
        # Even correctly signed, foreign identity/endpoint/source is refused.
        for field,wrong in [('database_oid',0),('endpoint',['127.0.0.1',5432]),('identity',str(uuid4())),
                            ('sql_sha256','0'*64),('generation',{})]:
            value=json.loads(saved);value['payload']['context'][field]=wrong
            value['signature']=hmac.new(evidence.key(state),evidence.signed_bytes(value['payload']),hashlib.sha256).hexdigest()
            write_json(path,value);denied('foreign-'+field,verify)
        path.write_bytes(saved)
        # A newly captured file is a required part of the operation thereafter.
        protected=directory/'required.txt';protected.write_text('before')
        extra={**snapshot,'files':{**snapshot['files'],**evidence.file_hashes([protected])}}
        other=directory/'files.json'
        other_id=evidence.record_before(other,profile,extra,purpose=purpose,state=state)
        check_files=lambda:evidence.verify_before(other,profile,purpose=purpose,operation=other_id,state=state)
        protected.write_text('changed');denied('changed-required-file',check_files)
        protected.unlink();denied('missing-required-file',check_files)
        require(path.read_bytes()==saved,'Original valid evidence was not retained.')
    return checks


class PreservationTests(unittest.TestCase):
    def test_missing_tampered_foreign_evidence_fails_closed(self):
        from generation import initial_registry
        with tempfile.TemporaryDirectory() as name:
            state=Path(name);(state/'credentials').mkdir()
            (state/'credentials/control-token.key').write_text(secrets.token_urlsafe(64))
            profile=dict(version=1,ready=True,database=DATABASE,host='127.0.0.1',database_port=5433,
                container=CONTAINER,volume=VOLUME,runtime_role=RUNTIME,owner_role=OWNER,
                application_port=APP_PORT,url=f'http://localhost:{APP_PORT}',listen=f'127.0.0.1:{APP_PORT}',
                project_root=str(ROOT),state_root=str(state),identity=str(uuid4()),database_oid=123,
                container_id='test-container-only',migration_fingerprint=migration_fingerprint()[1])
            write_json(state/'profile.json',profile);write_json(state/'generation-state.json',initial_registry(profile))
            snapshot=dict(files=evidence.file_hashes([state/'profile.json']),data={'rows':{'count':0}})
            self.assertEqual(len(baseline_checks(profile,state,snapshot)),15)

    def test_metadata_queries_are_select_only(self):
        class ReadOnlySpy:
            def execute(self,query):
                if not query.startswith('SELECT '): raise AssertionError('Not SELECT-only')
                return self
            def fetchall(self): return []
            def fetchone(self): return ()
        self.assertEqual(set(evidence.production_metadata(ReadOnlySpy())),
                         {'sequences','owners','constraints','owner_flags','owner_database_privileges'})

    def test_wrong_production_credentials_refused_before_connection(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'runtime.env'
            for text in ['POSTGRES_DB=sales_ai_demo_db','POSTGRES_PORT=5433',
                         'POSTGRES_USER=sales_ai_user','POSTGRES_PASSWORD=x\nPOSTGRES_PASSWORD=y']:
                path.write_text(text)
                with self.subTest(text=text),patch.object(evidence,'PRODUCTION_ENV',path),patch('psycopg.connect') as connect:
                    with self.assertRaises(DemoError): evidence.production_connection()
                    connect.assert_not_called()

    def test_explicit_file_set_cannot_be_empty_or_skip_missing(self):
        with self.assertRaises(DemoError): evidence.file_hashes([])
        with tempfile.TemporaryDirectory() as name,self.assertRaises(DemoError):
            evidence.file_hashes([Path(name)/'missing'])


if __name__=='__main__': unittest.main(verbosity=2)
