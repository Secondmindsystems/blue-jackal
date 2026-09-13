import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from blue_jackal.export import export_run
from blue_jackal.report import html_report, terminal


def sample():
    return {
        "schema_version": 1, "id": "a" * 64, "agent_kind": "synthetic",
        "contract_sha256": "b" * 64, "seed_sha256": "c" * 64,
        "work": "PASS", "authority": "PASS", "claim": "UNSUPPORTED",
        "disposition": "ACCEPTABLE_WORK", "claim_integrity": "FAIL",
        "coverage": {"writes": True}, "changes": ["result.json"], "violations": [],
        "oracle_results": [{"argv": ["python", "oracle.py"], "exit_code": 0, "stdout": "OK", "stderr": "", "status": "PASS"}],
        "events": [{"seq": 1, "event": "write", "target": "result.json", "completed": True}],
        "claims": [{"text": "DONE AND UNIVERSALLY RELIABLE", "kind": "extra"}],
        "limitations": ["Only direct tools are observed."], "created_at": "2026-09-07T00:00:00Z",
    }


class ReportTests(unittest.TestCase):
    def test_local_html_redacts_absolute_host_paths_but_keeps_file_identity(self):
        record = sample()
        record['oracle_results'] = [{
            'argv': ['/Users/alice/blue-jackal/.venv/bin/python',
                     '/private/var/folders/run/oracle/accept.py',
                     r'C:\\Users\\alice\\run\\workspace\\result.json'],
            'stdout': 'verified /Users/alice/blue-jackal/result.json',
            'stderr': 'workspace /Users/alice',
            'status': 'PASS',
        }]
        page = html_report(record)
        self.assertNotIn('/Users/alice', page)
        self.assertNotIn('[local-path]/alice', page)
        self.assertNotIn('/private/var', page)
        self.assertNotIn(r'C:\\Users\\alice', page)
        self.assertIn('[local-path]/python', page)
        self.assertIn('[local-path]/accept.py', page)
        self.assertIn('[local-path]/result.json', page)

    def test_axes_remain_independent(self):
        record = sample()
        out = terminal(record)
        self.assertIn("PASS", out)
        self.assertIn("UNSUPPORTED", out)
        self.assertIn("ACCEPTABLE_WORK", out)
        self.assertNotIn("NOT_DONE", out)
        self.assertLessEqual(len(out.splitlines()), 40)
        page = html_report(record)
        for field in ("WORK", "AUTHORITY", "CLAIM", "CLAIM INTEGRITY"):
            self.assertIn(field, page)

    def test_arbitrary_fields_are_html_escaped(self):
        record = sample()
        attack = '<script>alert("x")</script><img src="https://evil.test/x">'
        record["claims"][0]["text"] = attack
        record["id"] = attack
        page = html_report(record)
        self.assertNotIn("<script>", page)
        self.assertNotIn('<img src="https://evil.test', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("script-src 'none'", page)
        self.assertIn("<details", page)

    def test_no_remote_assets_or_active_javascript(self):
        page = html_report(sample())
        self.assertNotIn("<script", page)
        self.assertNotIn("<link", page)
        self.assertNotIn("@import", page)
        self.assertNotIn("url(", page)
        self.assertIn("prefers-color-scheme:dark", page)

    def test_terminal_rejects_control_spoofing(self):
        record = sample()
        record["id"] = "\x1b[31mEVIL\nFAKE PASS\x00"
        out = terminal(record)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x00", out)
        self.assertNotIn("\nFAKE", out)

    def test_matrix_exposes_five_failure_facts(self):
        record = {"type": "matrix", "id": "d" * 64, "challenges": [
            {"id": f"C{i}", "title": "Example", "status": "FAIL", "what_changed": "Factor changed",
             "observed": "Write before read", "required": "Read current input", "actual": "Wrong result",
             "reason": "Missing input observation", "runs": ["a" * 64]} for i in range(1, 5)]}
        self.assertLessEqual(len(terminal(record).splitlines()), 40)
        page = html_report(record)
        for text in ("Factor changed", "Write before read", "Read current input", "Wrong result", "Missing input observation"):
            self.assertIn(text, page)

    def test_comparison_preserves_regressions_and_both_matrices(self):
        record = {"type": "comparison", "repair_verified": False, "original_id": "a" * 64,
                  "repaired_id": "b" * 64, "fixed_failures": ["C2"], "new_failures": ["C3"],
                  "unchanged_failures": ["C4"], "regressions": ["C3"],
                  "original_matrix": {"type": "matrix", "id": "c" * 64},
                  "repaired_matrix": {"type": "matrix", "id": "d" * 64}}
        self.assertIn("REPAIR VERIFIED    NO", terminal(record))
        page = html_report(record)
        for text in ("Regressions", "Original Matrix", "Repaired Matrix", "C2", "C3", "C4"):
            self.assertIn(text, page)


class ExportTests(unittest.TestCase):
    def export(self, record):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "bundle"
        result = export_run(record, destination)
        return destination, result, json.loads((destination / "receipt.json").read_text(encoding="utf-8"))

    def test_allowlist_omits_raw_data_and_paths(self):
        record = sample()
        record["prompt"] = "secret-private-prompt"
        record["changes"] = ["C:\\Users\\SomePerson\\PrivateProject\\secret.txt"]
        record["oracle_results"][0]["stdout"] = "sk-private-key-123"
        record["events"][0]["target"] = "/home/private-user/key.txt"
        destination, result, clean = self.export(record)
        for path in destination.iterdir():
            text = path.read_text(encoding="utf-8")
            for secret in ("secret-private-prompt", "SomePerson", "PrivateProject", "sk-private-key-123", "private-user", "DONE AND UNIVERSALLY RELIABLE"):
                self.assertNotIn(secret, text)
        self.assertEqual(clean["work"], "PASS")
        self.assertEqual(clean["claim"], "UNSUPPORTED")
        self.assertNotIn("changes", clean)
        self.assertNotIn("argv", clean["oracle_results"][0])
        self.assertFalse(result["complete_reproduction_bundle"])
        self.assertTrue(any(item["field"] == "record.events[0].target" for item in result["rejected"]))

    def test_malicious_unknown_keys_do_not_leak_through_rejections(self):
        record = sample()
        record["secret-key-in-dictionary-name"] = "ignored"
        record["events"][0]["sk-private-field-name"] = "ignored"
        destination, result, _ = self.export(record)
        all_text = "".join(p.read_text(encoding="utf-8") for p in destination.iterdir()) + json.dumps(result["rejected"])
        self.assertNotIn("secret-key-in-dictionary-name", all_text)
        self.assertNotIn("sk-private-field-name", all_text)

    def test_enum_and_identity_values_are_validated(self):
        record = sample()
        record["id"] = "sk-fake-secret"
        record["work"] = "PASS /home/user"
        record["agent_kind"] = "machine-private-identifier"
        _, result, clean = self.export(record)
        for key in ("id", "work", "agent_kind"):
            self.assertNotIn(key, clean)
        self.assertTrue(any(item["reason"] == "invalid_sha256" for item in result["rejected"]))

    def test_manifests_match_exact_bytes_and_exports_are_stable(self):
        first, _, _ = self.export(sample())
        second, _, _ = self.export(sample())
        for name in ("receipt.json", "report.html", "manifest.json"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
        for name, entry in manifest["files"].items():
            data = (first / name).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["bytes"], len(data))

    def test_does_not_overwrite_existing_export(self):
        destination, _, _ = self.export(sample())
        before = (destination / "receipt.json").read_bytes()
        with self.assertRaises(FileExistsError):
            export_run({"work": "FAIL"}, destination)
        self.assertEqual(before, (destination / "receipt.json").read_bytes())

    def test_does_not_use_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.export(sample())

    def test_rejects_unc_destination(self):
        with self.assertRaises(ValueError):
            export_run(sample(), Path("//server/share/export"))

    def test_matrix_and_comparison_export(self):
        matrix = {"schema_version": 1, "type": "matrix", "id": "d" * 64,
                  "challenges": [{"id": "C2", "status": "FAIL", "title": "private-title", "runs": ["a" * 64]}]}
        _, _, clean = self.export(matrix)
        self.assertEqual(clean["challenges"][0], {"id": "C2", "status": "FAIL", "runs": ["a" * 64]})
        comparison = {"type": "comparison", "original_id": "a" * 64, "repaired_id": "b" * 64,
                      "repair_verified": False, "regressions": ["C3", "secret-item"], "original_matrix": matrix}
        _, _, clean = self.export(comparison)
        self.assertEqual(clean["regressions"], ["C3"])
        self.assertEqual(clean["original_matrix"]["type"], "matrix")
        self.assertFalse(clean["repair_verified"])


if __name__ == "__main__":
    unittest.main()
