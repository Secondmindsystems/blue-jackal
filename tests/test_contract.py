import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from blue_jackal.contract import (ContractError, _stable_platform_root_alias, allowed, beneath,
                                  canonical, load, matches, relative, snapshot)
from blue_jackal.demo import CONTRACT


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / '.blue-jackal.toml'

    def parse(self, text=CONTRACT):
        self.config.write_text(text, encoding='utf-8')
        return load(self.config)

    def test_demo_contract_is_complete(self):
        data = self.parse()
        self.assertTrue(data['verify']['commands'])
        self.assertEqual(data['authority']['allow_shell'], [])
        self.assertEqual(data['claim']['done_patterns'], ['^DONE$'])

    def test_rejects_traversal_and_platform_aliases(self):
        cases = ['', '/outside', '../outside', 'x/../y', 'x\\y', 'C:/x', 'x//y',
                 'x/', 'NUL', 'con.txt', 'x/a.', 'x/a ', 'x\nPASS', '.hidden', 'x/a:b', 'x/<bad>']
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ContractError):
                relative(value)

    def test_globs_are_explicit_and_protection_wins(self):
        self.assertEqual(relative('src/**', pattern=True), 'src/**')
        with self.assertRaises(ContractError): relative('src/*')
        auth = {'allow_write': ['src/**'], 'protect': ['src/private/**']}
        self.assertTrue(matches('SRC/file.py', ['src/**']))
        self.assertTrue(allowed('src/file.py', auth))
        self.assertFalse(allowed('src/private/token.py', auth))

    def test_missing_snapshot_is_not_an_empty_valid_fixture(self):
        with self.assertRaises(ContractError): snapshot(self.root / 'absent')

    def test_snapshot_hashes_contents_and_rejects_hidden_files(self):
        (self.root / 'a.txt').write_text('first', encoding='utf-8')
        before = snapshot(self.root)
        (self.root / 'a.txt').write_text('second', encoding='utf-8')
        self.assertNotEqual(before, snapshot(self.root))
        (self.root / '.hidden').write_text('value', encoding='utf-8')
        with self.assertRaises(ContractError): snapshot(self.root)

    def test_snapshot_file_budget(self):
        for number in range(201):
            (self.root / f'{number}.txt').write_text('x', encoding='utf-8')
        with self.assertRaises(ContractError): snapshot(self.root)

    def test_linked_roots_and_children_are_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'value.txt').write_text('x', encoding='utf-8')
        link = self.root / 'alias'
        try: link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError): self.skipTest('Host does not permit creating test symlinks')
        with self.assertRaises(ContractError): snapshot(link)
        with self.assertRaises(ContractError): beneath(self.root, 'alias/value.txt')

    def test_platform_root_alias_requires_root_owned_top_level_immutable_link(self):
        info = type('Info', (), {'st_mode': 0o120777, 'st_uid': 0})()
        parent = type('Parent', (), {'st_mode': 0o40755, 'st_uid': 0})()
        alias = Path('/system-alias')
        canonical = Path('/canonical-root') if Path('/canonical-root').is_absolute() else Path('C:/canonical-root')
        with patch('pathlib.Path.resolve', return_value=canonical), \
             patch('pathlib.Path.lstat', return_value=parent):
            self.assertTrue(_stable_platform_root_alias(alias, info))
            info.st_uid = 501
            self.assertFalse(_stable_platform_root_alias(alias, info))
            info.st_uid = 0
            self.assertFalse(_stable_platform_root_alias(Path('/tmp/user-alias'), info))

    def test_unknown_sections_and_challenge_fields_are_rejected(self):
        for text in (CONTRACT + '\n[unexpected]\nx=1\n',
                     CONTRACT.replace('observe_path = "input.json"', 'unknown = "input.json"')):
            with self.subTest(text=text[-80:]), self.assertRaises(ContractError): self.parse(text)

    def test_empty_or_unsealed_oracle_is_rejected(self):
        for text in (CONTRACT.replace('commands = [["{python}", "{oracle}/accept.py", "{workspace}"]]', 'commands = []'),
                     CONTRACT.replace('files = ["accept.py"]', 'files = []'),
                     CONTRACT.replace('"{oracle}/accept.py"', '"unsealed.py"')):
            with self.assertRaises(ContractError): self.parse(text)

    def test_shell_authority_timeout_and_unanchored_claims_are_rejected(self):
        changes = [('allow_shell = []', 'allow_shell = ["anything"]'),
                   ('timeout_seconds = 30', 'timeout_seconds = 0'),
                   ('timeout_seconds = 30', 'timeout_seconds = true'),
                   ('"^DONE$"', '"DONE"')]
        for old, new in changes:
            with self.subTest(old=old), self.assertRaises(ContractError): self.parse(CONTRACT.replace(old, new))

    def test_invalid_utf8_is_a_contract_error(self):
        self.config.write_bytes(b'\xff\xfeinvalid')
        with self.assertRaises(ContractError): load(self.config)

    def test_canonical_identity_is_order_stable_and_finite(self):
        self.assertEqual(canonical({'b': 2, 'a': 1}), canonical({'a': 1, 'b': 2}))
        with self.assertRaises(ValueError): canonical({'value': float('nan')})


if __name__ == '__main__':
    unittest.main()
