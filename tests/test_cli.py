import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

from blue_jackal import cli, demo, runner


class CLITests(unittest.TestCase):
    def test_entire_command_workflow_and_stable_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'trial'
            def call(*args):
                output=io.StringIO()
                with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                    result=cli.main(['--root',str(root),*args])
                self.assertEqual(result,0,output.getvalue())
                return output.getvalue()
            call('init')
            call('run','--','demo')
            folder,baseline=runner.find_record(root)
            self.assertEqual(baseline['work'],'PASS')
            receipt=(folder/'run.json').read_bytes()
            one=call('inspect',baseline['id'],'--html')
            two=call('inspect',baseline['id'],'--html')
            self.assertEqual(one,two)
            self.assertEqual(receipt,(folder/'run.json').read_bytes())
            call('crash',baseline['id'])
            _,matrix=runner.find_record(root)
            (root/'agent-policy.txt').write_text(demo.REPAIRED_POLICY,encoding='utf-8')
            call('verify','--against',matrix['id'])
            _,comparison=runner.find_record(root)
            self.assertTrue(comparison['repair_verified'])
            call('export',comparison['id'])
            self.assertTrue((root/'.blue-jackal'/'exports'/comparison['id']/'manifest.json').exists())

    def test_unsupported_agent_and_empty_init_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--root',temp,'run','--','unknown']),2)
                self.assertEqual(cli.main(['--root',temp,'init']),0)
                self.assertEqual(cli.main(['--root',temp,'init']),2)


if __name__=='__main__': unittest.main()
