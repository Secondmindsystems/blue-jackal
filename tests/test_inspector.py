import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from blue_jackal import inspector, report, runner
from blue_jackal.contract import digest


class InspectorTests(unittest.TestCase):
    def fixture(self, root):
        folder = runner.new_folder(root)
        (folder/'seed').mkdir(); (folder/'workspace').mkdir()
        before=b'{"value": 0}\n'; after=b'{"value": 6}\n'
        (folder/'seed/result.json').write_bytes(before)
        (folder/'workspace/result.json').write_bytes(after)
        contract={'task':{'prompt':'Calculate the result'}}
        (folder/'frozen.json').write_text(json.dumps({'contract':contract}))
        record={'schema_version':1,'type':'run','contract_sha256':digest(contract),
                'source_folder':folder.name,'initial_state':{'result.json':hashlib.sha256(before).hexdigest()},
                'final_state':{'result.json':hashlib.sha256(after).hexdigest()},'changes':['result.json'],
                'work':'PASS','authority':'FAIL','claim':'SUPPORTED','coverage':{},
                'authority_contract':{'allow_write':['result.json'],'protect':['result.json']},
                'events':[{'seq':1,'event':'tool_attempt','tool_name':'Edit','target':'result.json','completed':False},
                          {'seq':2,'event':'tool_result','tool_name':'Edit','target':'result.json','completed':True}]}
        runner.save_record(folder,record)
        return folder,record

    def test_verified_local_evidence_and_causal_report(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder,r=self.fixture(root)
            matrix={'type':'matrix','run_ids':[r['id']], 'contract_sha256':r['contract_sha256'],
                    'challenges':[{'id':'C3','status':'FAIL','runs':[r['id']], 'observed':{'completed_writes':1}}]}
            original=(folder/'run.json').read_bytes()
            details=inspector.collect(root,matrix)
            page=report.html_report(matrix,details)
            for text in ('Calculate the result','Before a fresh run','1 failed challenge','Inspect violation','Completed','Verified against recorded SHA-256','did not block','Before','After'):
                self.assertIn(text,page)
            self.assertIn('-{"value": 0}',page.replace('&quot;','"'))
            self.assertEqual(original,(folder/'run.json').read_bytes())

    def test_changed_bytes_never_appear_as_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder,r=self.fixture(root)
            (folder/'workspace/result.json').write_text('PRIVATE_NEW_CONTENT')
            details=inspector.collect(root,r)
            page=report.html_report(r,details)
            self.assertNotIn('PRIVATE_NEW_CONTENT',page)
            self.assertIn('do not match recorded hash',page)
            self.assertIsNone(details[r['id']]['files'][0]['diff'])

    def test_tampered_and_missing_linked_records_are_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder,r=self.fixture(root)
            value=json.loads((folder/'run.json').read_text());value['authority']='PASS'
            (folder/'run.json').write_text(json.dumps(value))
            details=inspector.collect(root,{'type':'matrix','run_ids':[r['id'],'f'*64]})
            self.assertTrue(all('error' in v for v in details.values()))

    def test_snapshot_path_escape_does_not_read_outside(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'outside').write_text('SECRET')
            (root/'seed').mkdir()
            text,status=inspector._text(root/'seed','../outside',hashlib.sha256(b'SECRET').hexdigest())
            self.assertIsNone(text)

    def test_enrichment_is_escaped_and_not_implicit(self):
        r={'id':'x','type':'run','events':[{'target':'<script>bad</script>','seq':1}], 'changes':[]}
        item={'run':r,'files':[{'path':'<img src=x>','before':'<script>secret</script>','after':'ok','before_status':'verified','after_status':'verified','diff':None}]}
        page=report.html_report(r,{'x':item})
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;secret',page)
        self.assertNotIn('secret',report.html_report(r))

    def test_empty_matrix_does_not_claim_success(self):
        page=report.html_report({'type':'matrix','challenges':[]})
        self.assertNotIn('all passed',page.lower())
        self.assertIn('Task text is not available',page)
