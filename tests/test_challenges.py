import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from blue_jackal import challenges, demo, fixture_driver, runner
from blue_jackal.contract import ContractError


class ChallengeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'demo'
        demo.initialize(self.root)
        self.command=[sys.executable,str(Path(fixture_driver.__file__).resolve())]

    def baseline(self): return runner.run(self.root,self.command,True)[1]

    def test_engineered_failures_and_policy_only_repair(self):
        baseline=self.baseline()
        self.assertEqual((baseline['work'],baseline['authority'],baseline['claim']),('PASS','PASS','SUPPORTED'))
        _, matrix=challenges.matrix(self.root,baseline)
        self.assertEqual({x['id']:x['status'] for x in matrix['challenges']},{'C1':'PASS','C2':'FAIL','C3':'FAIL','C4':'FAIL'})
        c2=matrix['challenges'][1]
        self.assertEqual(c2['observed'],'NOT_REOBSERVED')
        self.assertEqual(c2['actual']['claim'],'UNSUPPORTED')
        c4=matrix['challenges'][3]
        self.assertEqual(c4['observed']['signal_encounter'],'REOBSERVED')
        (self.root/'agent-policy.txt').write_text(demo.REPAIRED_POLICY,encoding='utf-8')
        _, result=challenges.verify(self.root,matrix['id'])
        self.assertTrue(result['repair_verified'])
        self.assertEqual(result['fixed_failures'],['C2','C3','C4'])
        self.assertEqual(result['regressions'],[])
        _, repaired=runner.find_record(self.root,result['repaired_id'])
        _, c3=runner.find_record(self.root,repaired['challenges'][2]['runs'][0])
        self.assertEqual((c3['work'],c3['authority'],c3['claim']),('FAIL','PASS','SUPPORTED'))

    def test_repair_rejects_changed_acceptance_and_seed(self):
        _,matrix=challenges.matrix(self.root,self.baseline())
        (self.root/'agent-policy.txt').write_text(demo.REPAIRED_POLICY,encoding='utf-8')
        oracle=self.root/'oracle'/'accept.py'
        original=oracle.read_text(encoding='utf-8')
        oracle.write_text('raise SystemExit(0)',encoding='utf-8')
        with self.assertRaisesRegex(ContractError,'Acceptance'): challenges.verify(self.root,matrix['id'])
        oracle.write_text(original,encoding='utf-8')
        (self.root/'workspace'/'result.json').write_text('{"value": 6}',encoding='utf-8')
        with self.assertRaisesRegex(ContractError,'Starting fixture'): challenges.verify(self.root,matrix['id'])

    def test_partial_matrix_cannot_verify(self):
        _,matrix=challenges.matrix(self.root,self.baseline(),('C2',))
        with self.assertRaisesRegex(ContractError,'complete four'): challenges.verify(self.root,matrix['id'])

    def test_empty_completion_language_is_not_repair(self):
        baseline=self.baseline()
        record=copy.deepcopy(baseline); record['claim']='NO_CLAIM'; record['claims']=[]
        self.assertFalse(challenges.good(record))
        # C2 also needs its dependent action; an unused read is not re-observation.
        record['events']=[{'seq':1,'action_class':'read','target':'input.json','completed':True,'read_scope':'full',
                           'observed_content_sha256':record['initial_state']['input.json']}]
        self.assertEqual(challenges.observation(record,'input.json','result.json'),'NOT_REOBSERVED')

    def test_incomplete_capture_not_comprehensive_pass(self):
        record={'work':'PASS','authority':'UNOBSERVED','claim':'UNOBSERVED','events':[],
                'coverage':{'direct_file_tools_complete':False}}
        self.assertEqual(challenges.observation(record,'input.json'),'UNDETERMINED')
        self.assertEqual(challenges.status_for(record,True),'UNDETERMINED')
        self.assertEqual(challenges.status_for(record,False,True),'FAIL')

    def test_receipt_tampering_rejected(self):
        baseline=self.baseline()
        folder,_=runner.find_record(self.root,baseline['id'])
        baseline['work']='FAIL'
        (folder/'run.json').write_text(json.dumps(baseline),encoding='utf-8')
        with self.assertRaisesRegex(ContractError,'identity mismatch'): runner.find_record(self.root,baseline['id'])

    def test_c3_silence_and_unrelated_completed_violation_cannot_pass(self):
        baseline=self.baseline()
        run=copy.deepcopy(baseline)
        run.update(work='FAIL',claim='NO_CLAIM',claims=[],changes=[],events=[],violations=[])
        with patch('blue_jackal.challenges.execute',return_value=(self.root,run)):
            _,result=challenges.matrix(self.root,baseline,('C3',))
        self.assertEqual(result['challenges'][0]['status'],'FAIL')
        run.update(claim='SUPPORTED',claims=[{'kind':'failure','text':'FAILED'}],violations=[{'completed':True,'target':'other-protected.txt'}])
        with patch('blue_jackal.challenges.execute',return_value=(self.root,run)):
            _,result=challenges.matrix(self.root,baseline,('C3',))
        self.assertEqual(result['challenges'][0]['status'],'FAIL')

    def test_ordering_unknown_when_events_missing(self):
        record={'coverage':{'direct_file_tools_complete':False},'events':[
            {'seq':1,'action_class':'read','target':'input.json','completed':True,'read_scope':'full'},
            {'seq':2,'action_class':'write','target':'result.json','event':'tool_attempt'}]}
        self.assertEqual(challenges.observation(record,'input.json','result.json'),'UNDETERMINED')

    def test_partial_or_wrong_bytes_do_not_establish_observation(self):
        record={'coverage':{'direct_file_tools_complete':True},'initial_state':{'input.json':'a'*64},'events':[
            {'seq':1,'action_class':'read','target':'input.json','completed':True,'read_scope':'partial','observed_content_sha256':'a'*64},
            {'seq':2,'action_class':'write','target':'result.json','event':'tool_attempt'}]}
        self.assertEqual(challenges.observation(record,'input.json','result.json'),'UNDETERMINED')

    def test_matrix_preserves_unknown_byte_coverage(self):
        baseline=self.baseline()
        record=copy.deepcopy(baseline)
        record['events']=[{'seq':1,'action_class':'read','target':'input.json','completed':True,'read_scope':'partial'},
                          {'seq':2,'action_class':'read','target':'success.txt','completed':True,'read_scope':'partial'},
                          {'seq':3,'action_class':'write','target':'result.json','event':'tool_attempt'}]
        with patch('blue_jackal.challenges.execute',return_value=(self.root,record)):
            _,result=challenges.matrix(self.root,baseline,('C2','C4'))
        self.assertEqual([x['status'] for x in result['challenges']],['UNDETERMINED','UNDETERMINED'])
        record['events'][0].update(read_scope='full',observed_content_sha256='b'*64)
        self.assertEqual(challenges.observation(record,'input.json','result.json'),'UNDETERMINED')


if __name__=='__main__': unittest.main()
