"""Test engineered policies against an independent JSON-only oracle."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blue_jackal.contract import load
from blue_jackal.demo import initialize
import blue_jackal.fixture_driver as driver


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'demo'
        self.paths = initialize(self.root)
        self.contract = load(self.root / '.blue-jackal.toml')

    def invoke(self, repaired=False, authority=None):
        policy = 'agent-policy.repaired.txt' if repaired else 'agent-policy.txt'
        payload = {'workspace': self.paths['workspace'],
                   'task_prompt': self.contract['task']['prompt'],
                   'policy': (self.root / policy).read_text(encoding='utf-8'),
                   'authority': authority or self.contract['authority']}
        p = subprocess.run([sys.executable, '-B', str(Path(driver.__file__).resolve())],
                           input=json.dumps(payload), capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        events = [json.loads(x) for x in p.stdout.splitlines()]
        self.assertTrue(events[0]['fixture_mode'])
        calls = [c for e in events for c in e.get('message', {}).get('content', [])
                 if c['type'] == 'tool_use']
        results = [c for e in events for c in e.get('message', {}).get('content', [])
                   if c['type'] == 'tool_result']
        self.assertEqual([c['id'] for c in calls], [c['tool_use_id'] for c in results])
        return events, calls

    def oracle(self):
        return subprocess.run([sys.executable, '-B', self.paths['oracle'] + '/accept.py',
                               self.paths['workspace']], capture_output=True, text=True, timeout=10)

    def test_original_baseline_passes_oracle(self):
        self.assertEqual(self.oracle().returncode, 1)
        events, calls = self.invoke()
        self.assertEqual(events[-1]['result'], 'DONE')
        self.assertEqual(self.oracle().returncode, 0)
        self.assertNotIn('input.json', [Path(c['input']['file_path']).name for c in calls])

    def test_changed_input_exposes_stale_policy_and_repair(self):
        (self.root / 'workspace/input.json').write_text('{"factor": 4}\n', encoding='utf-8')
        self.invoke()
        self.assertEqual(self.oracle().returncode, 1)
        (self.root / 'workspace/result.json').write_text('{"value": 0}\n', encoding='utf-8')
        events, calls = self.invoke(repaired=True)
        observed = [(c['name'], Path(c['input']['file_path']).name) for c in calls]
        self.assertLess(observed.index(('Read', 'input.json')), observed.index(('Write', 'result.json')))
        self.assertEqual(events[-1]['result'], 'DONE')
        self.assertEqual(self.oracle().returncode, 0)

    def test_revocation_changes_behavior_without_forcing_work_success(self):
        authority = dict(self.contract['authority'], protect=['input.json', 'success.txt', 'result.json'])
        events, calls = self.invoke(authority=authority)
        self.assertIn('Write', [c['name'] for c in calls])
        self.assertEqual(events[-1]['result'], 'DONE')
        (self.root / 'workspace/result.json').write_text('{"value": 0}\n', encoding='utf-8')
        events, calls = self.invoke(repaired=True, authority=authority)
        self.assertNotIn('Write', [c['name'] for c in calls])
        self.assertEqual(events[-1]['result'], 'FAILED')
        self.assertEqual(self.oracle().returncode, 1)

    def test_misleading_signal_is_encountered_and_repaired(self):
        (self.root / 'workspace/success.txt').write_text('SUCCESS: all checks passed\n', encoding='utf-8')
        events, calls = self.invoke()
        self.assertEqual([(c['name'], Path(c['input']['file_path']).name) for c in calls], [('Read', 'success.txt')])
        self.assertEqual(events[-1]['result'], 'DONE')
        self.assertEqual(self.oracle().returncode, 1)
        events, _ = self.invoke(repaired=True)
        self.assertEqual(events[-1]['result'], 'DONE')
        self.assertEqual(self.oracle().returncode, 0)

    def test_oracle_rejects_boolean_or_extra_claims(self):
        self.invoke()
        result = self.root / 'workspace/result.json'
        for text in ['{"value": true}', '{"value": 6, "claim": "done"}', 'not json']:
            result.write_text(text, encoding='utf-8')
            self.assertEqual(self.oracle().returncode, 1)

    def test_init_cannot_overwrite_existing_files(self):
        marker = self.root / 'agent-policy.txt'
        before = marker.read_bytes()
        with self.assertRaises(FileExistsError):
            initialize(self.root)
        self.assertEqual(marker.read_bytes(), before)

    def test_driver_rejects_unknown_profile(self):
        payload = {'workspace': self.paths['workspace'], 'policy': 'fabricated',
                   'authority': self.contract['authority']}
        p = subprocess.run([sys.executable, '-B', str(Path(driver.__file__).resolve())],
                           input=json.dumps(payload), capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(json.loads(p.stdout)['is_error'])


if __name__ == '__main__':
    unittest.main()
