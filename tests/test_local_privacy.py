from pathlib import Path
import subprocess
import tempfile
import unittest
from blue_jackal.runner import new_folder


class LocalPrivacyTests(unittest.TestCase):
    def test_run_directory_is_git_ignored_without_parent_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            folder = new_folder(root)
            record = folder/'private.txt'
            record.write_text('fixture only')
            result = subprocess.run(['git','-C',str(root),'check-ignore',str(record)],capture_output=True)
            self.assertEqual(result.returncode,0)
            new_folder(root)
            self.assertEqual((root/'.blue-jackal/.gitignore').read_text(),'*\n')
