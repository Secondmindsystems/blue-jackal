"""Conservative, typed local exports. No publishing or universal secret claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .contract import ContractError, checked_root
from .report import html_report


_HASH = re.compile(r"[a-fA-F0-9]{64}\Z")
_ENUMS = {
    "work": {"PASS", "FAIL", "ERROR"},
    "authority": {"PASS", "FAIL", "UNOBSERVED"},
    "claim": {"SUPPORTED", "UNSUPPORTED", "NO_CLAIM", "UNOBSERVED"},
    "disposition": {"ACCEPTABLE_WORK", "NOT_DONE", "HOLD", "REVIEW"},
    "claim_integrity": {"PASS_OR_NA", "FAIL", "UNOBSERVED"},
    "status": {"PASS", "FAIL", "ERROR", "UNDETERMINED", "UNOBSERVED"},
    "type": {"run", "matrix", "comparison"},
    "challenge": {None, "C1", "C2", "C3", "C4"},
    "agent_kind": {"claude", "claude-code", "claude_code", "synthetic", "synthetic-demo", "synthetic_fixture", "demo"},
}
_IDENTITIES = {"id", "baseline_id", "original_id", "repaired_id", "contract_sha256", "seed_sha256",
               "oracle_sha256", "profile_sha256", "frozen_definition_sha256", "command_sha256",
               "engine_sha256", "evaluated_state_sha256", "verifier_identity_sha256", "original_profile_sha256", "repaired_baseline_id"}
_COMPARE = {"fixed_failures", "new_failures", "unchanged_failures", "regressions"}
_KNOWN_OMISSIONS = {"created_at", "changes", "violations", "coverage", "claims", "limitations",
                    "what_changed", "observed", "required", "actual", "reason", "prompt", "raw",
                    "stdout", "stderr", "argv", "last_assistant_message", "target", "path"}
_POLICY = {
    "mode": "typed_allowlist",
    "local_only": True,
    "raw_text_included": False,
    "paths_included": False,
    "coverage": "All free text, path values, raw prompts, claim text and command data are omitted.",
    "limitation": "This derivative is not a complete reproduction bundle. No claim of arbitrary secret detection is made.",
}


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sanitize(record):
    rejected = []

    def reject(field, reason):
        rejected.append({"field": field, "reason": reason})

    def enum(key, value, field):
        if isinstance(value, (str, type(None))) and value in _ENUMS[key]:
            return value, True
        reject(field, "invalid_fixed_identifier")
        return None, False

    def hashes(values, field):
        if not isinstance(values, list):
            reject(field, "expected_identity_list")
            return []
        out = []
        for index, value in enumerate(values):
            if isinstance(value, str) and _HASH.fullmatch(value):
                out.append(value.lower())
            else:
                reject(f"{field}[{index}]", "invalid_sha256")
        return out

    def challenge_ids(values, field):
        if not isinstance(values, list):
            reject(field, "expected_challenge_list")
            return []
        out = []
        for index, value in enumerate(values):
            if isinstance(value, str) and value in {"C1", "C2", "C3", "C4"}:
                out.append(value)
            else:
                reject(f"{field}[{index}]", "invalid_challenge_identifier")
        return out

    def safe_object(source, prefix="record"):
        if not isinstance(source, dict):
            reject(prefix, "expected_object")
            return {}
        result = {}
        for index, (key, value) in enumerate(source.items()):
            # Never echo unknown input keys: the key itself may contain a secret.
            known = key in _ENUMS or key in _IDENTITIES or key in _COMPARE or key in _KNOWN_OMISSIONS or key in {
                "schema_version", "repair_verified", "run_ids", "challenges", "events", "oracle_results",
                "original", "repaired", "original_matrix", "repaired_matrix"}
            field = f"{prefix}.{key}" if known else f"{prefix}.[field#{index}]"
            if key in _ENUMS:
                cleaned, okay = enum(key, value, field)
                if okay:
                    result[key] = cleaned
            elif key in _IDENTITIES:
                if isinstance(value, str) and _HASH.fullmatch(value):
                    result[key] = value.lower()
                else:
                    reject(field, "invalid_sha256")
            elif key == "schema_version":
                if type(value) is int and value == 1:
                    result[key] = value
                else:
                    reject(field, "unsupported_schema_version")
            elif key == "repair_verified":
                if type(value) is bool:
                    result[key] = value
                else:
                    reject(field, "expected_boolean")
            elif key == "run_ids":
                result[key] = hashes(value, field)
            elif key == "coverage":
                result[key] = {"scope": "Recorded direct Read/Edit/Write calls only; no hooks, hidden effects or operating-system coverage."}
                if not isinstance(value, dict):
                    reject(field, "expected_coverage_object")
                    continue
                for number, (name, entry) in enumerate(value.items()):
                    if name in {"direct_file_tools_complete", "claim_capture_complete"} and type(entry) is bool:
                        result[key][name] = entry
                    else:
                        sub = f"{field}.{name}" if name in {"direct_file_tools_complete", "claim_capture_complete", "scope", "gaps"} else f"{field}.[field#{number}]"
                        reject(sub, "unrecognized_coverage_or_free_text_omitted")
            elif key in _COMPARE:
                result[key] = challenge_ids(value, field)
            elif key in {"original", "repaired", "original_matrix", "repaired_matrix"}:
                result[key] = safe_object(value, field)
            elif key == "challenges":
                result[key] = []
                if not isinstance(value, list):
                    reject(field, "expected_challenge_list")
                    continue
                for number, item in enumerate(value):
                    child = f"{field}[{number}]"
                    if not isinstance(item, dict):
                        reject(child, "expected_object")
                        continue
                    clean = {}
                    for part, (name, entry) in enumerate(item.items()):
                        sub = f"{child}.{name}" if name in {"id", "status", "runs", "title", "what_changed", "observed", "required", "actual", "reason"} else f"{child}.[field#{part}]"
                        if name == "id":
                            if isinstance(entry, str) and entry in {"C1", "C2", "C3", "C4"}:
                                clean[name] = entry
                            else:
                                reject(sub, "invalid_challenge_identifier")
                        elif name == "status":
                            cleaned, okay = enum("status", entry, sub)
                            if okay:
                                clean[name] = cleaned
                        elif name == "runs":
                            clean[name] = hashes(entry, sub)
                        else:
                            reject(sub, "free_text_or_unrecognized_field_omitted")
                    result[key].append(clean)
            elif key in {"events", "oracle_results"}:
                result[key] = []
                if not isinstance(value, list):
                    reject(field, "expected_evidence_list")
                    continue
                for number, item in enumerate(value):
                    child = f"{field}[{number}]"
                    if not isinstance(item, dict):
                        reject(child, "expected_object")
                        continue
                    clean = {}
                    for part, (name, entry) in enumerate(item.items()):
                        sub = f"{child}.{name}" if name in {"seq", "event", "action_class", "completed", "is_error", "status", "exit_code", "argv", "stdout", "stderr", "target", "read_scope"} else f"{child}.[field#{part}]"
                        if name in {"seq", "exit_code"} and type(entry) is int and -(2**31) <= entry < 2**31:
                            clean[name] = entry
                        elif name in {"completed", "is_error"} and type(entry) is bool:
                            clean[name] = entry
                        elif name == "status":
                            cleaned, okay = enum("status", entry, sub)
                            if okay:
                                clean[name] = cleaned
                        elif name == "read_scope" and isinstance(entry, str) and entry in {"full", "partial", "unknown"}:
                            clean[name] = entry
                        elif name in {"event", "action_class"} and isinstance(entry, str) and entry.lower() in {
                                "read", "write", "edit", "tool_use", "tool_result", "assistant", "result", "system", "error",
                                "shell", "unknown", "start", "end", "oracle", "observation", "attempt", "completed", "tool_attempt"}:
                            clean[name] = entry.lower()
                        else:
                            reject(sub, "free_text_path_or_unrecognized_value_omitted")
                    result[key].append(clean)
            else:
                reject(field, "free_text_path_or_unrecognized_field_omitted")
        return result

    sanitized = safe_object(record)
    sanitized["export_policy"] = dict(_POLICY)
    sanitized["rejected"] = rejected
    return sanitized, rejected


def export_run(record: dict, destination: Path) -> dict:
    """Write a new local bundle without overwriting an existing artifact."""
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    destination = Path(destination)
    if str(destination).startswith(("\\\\", "//")) or "://" in str(destination):
        raise ValueError("export destination must be a local filesystem path")
    try:
        checked_root(destination)
    except ContractError as exc:
        raise ValueError("export destination must not traverse symbolic links") from exc
    names = ("receipt.json", "report.html", "manifest.json")
    if any((destination / name).exists() for name in names):
        raise FileExistsError("export files already exist; select a new destination")
    sanitized, rejected = _sanitize(record)
    payloads = {"receipt.json": _json_bytes(sanitized), "report.html": html_report(sanitized).encode("utf-8")}
    manifest = {"schema_version": 1, "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                                              for name, data in payloads.items()}, "policy": "typed_allowlist_local_derivative"}
    payloads["manifest.json"] = _json_bytes(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    return {"destination": str(destination), "files": list(names), "rejected": rejected,
            "sanitization": "ALLOWLIST_DERIVATIVE", "complete_reproduction_bundle": False, "manifest": manifest}
