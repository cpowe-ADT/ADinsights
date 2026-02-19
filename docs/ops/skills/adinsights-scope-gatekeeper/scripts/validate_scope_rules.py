#!/usr/bin/env python3
"""Validate scope-rules.yaml structure and references."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc


REQUIRED_KEYS = {
    "skill",
    "version",
    "mode",
    "packet_schema_version",
    "evidence_precedence",
    "supported_scope_statuses",
    "known_top_level_buckets",
    "bucket_owner_personas",
    "bucket_required_tests",
    "architecture_sensitive_patterns",
    "contract_risk_patterns",
    "contract_signal_defaults",
}
REQUIRED_STATUSES = {
    "PASS_SINGLE_SCOPE",
    "WARN_UNCLEAR_SCOPE",
    "ESCALATE_CROSS_SCOPE",
    "ESCALATE_ARCH_RISK",
    "ESCALATE_CONTRACT_RISK",
}


def default_rules_path() -> Path:
    root = Path(__file__).resolve().parents[5]
    return (
        root
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-scope-gatekeeper"
        / "references"
        / "scope-rules.yaml"
    )


def validate_rules(path: Path) -> int:
    errors: list[str] = []

    if not path.exists():
        print(f"[ERROR] Rules file not found: {path}")
        return 1

    rules = yaml.safe_load(path.read_text()) or {}
    if not isinstance(rules, dict):
        print("[ERROR] Rules file must be a YAML mapping.")
        return 1

    missing = sorted(REQUIRED_KEYS - set(rules.keys()))
    if missing:
        errors.append("Missing required key(s): " + ", ".join(missing))

    if rules.get("skill") != "adinsights-scope-gatekeeper":
        errors.append("`skill` must equal 'adinsights-scope-gatekeeper'.")

    if rules.get("mode") != "advisory-first":
        errors.append("`mode` must equal 'advisory-first'.")

    packet_schema_version = str(rules.get("packet_schema_version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", packet_schema_version):
        errors.append("`packet_schema_version` must be semver-like (for example 1.1.0).")

    precedence = rules.get("evidence_precedence")
    if not isinstance(precedence, list) or precedence != [
        "git_changed_files",
        "explicit_paths",
        "prompt_paths",
    ]:
        errors.append(
            "`evidence_precedence` must be exactly ['git_changed_files', 'explicit_paths', 'prompt_paths']."
        )

    statuses = rules.get("supported_scope_statuses")
    if not isinstance(statuses, list) or sorted(statuses) != sorted(REQUIRED_STATUSES):
        errors.append(
            "`supported_scope_statuses` must include exactly "
            + f"{sorted(REQUIRED_STATUSES)}."
        )

    known_buckets = rules.get("known_top_level_buckets")
    if not isinstance(known_buckets, list) or not known_buckets:
        errors.append("`known_top_level_buckets` must be a non-empty list.")
        known_buckets = []

    owner_map = rules.get("bucket_owner_personas")
    if not isinstance(owner_map, dict):
        errors.append("`bucket_owner_personas` must be a mapping.")
        owner_map = {}

    test_map = rules.get("bucket_required_tests")
    if not isinstance(test_map, dict):
        errors.append("`bucket_required_tests` must be a mapping.")
        test_map = {}

    for bucket in known_buckets:
        if bucket not in owner_map:
            errors.append(f"Bucket '{bucket}' missing owner mapping.")
        if bucket not in test_map:
            errors.append(f"Bucket '{bucket}' missing required test mapping.")
        else:
            tests = test_map[bucket]
            if not isinstance(tests, list) or not tests:
                errors.append(f"Bucket '{bucket}' must define a non-empty test list.")

    arch_patterns = rules.get("architecture_sensitive_patterns", [])
    if not isinstance(arch_patterns, list) or not arch_patterns:
        errors.append("`architecture_sensitive_patterns` must be a non-empty list.")

    contract_patterns = rules.get("contract_risk_patterns", [])
    if not isinstance(contract_patterns, list) or not contract_patterns:
        errors.append("`contract_risk_patterns` must be a non-empty list.")
    else:
        for pattern in contract_patterns:
            try:
                re.compile(str(pattern))
            except re.error as err:
                errors.append(f"Invalid contract regex pattern '{pattern}': {err}")

    contract_defaults = rules.get("contract_signal_defaults")
    if not isinstance(contract_defaults, dict):
        errors.append("`contract_signal_defaults` must be a mapping.")
    else:
        reviewer = str(contract_defaults.get("reviewer", "")).strip()
        if not reviewer:
            errors.append("contract_signal_defaults.reviewer must be a non-empty string.")
        invoke_contract_guard = contract_defaults.get("invoke_contract_guard")
        if not isinstance(invoke_contract_guard, bool):
            errors.append("contract_signal_defaults.invoke_contract_guard must be boolean.")

    if errors:
        for err in errors:
            print(f"[ERROR] {err}")
        return 1

    print(
        f"[OK] Scope rules valid with {len(known_buckets)} buckets and required status set {sorted(REQUIRED_STATUSES)}."
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate scope-rules.yaml")
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return validate_rules(args.rules)


if __name__ == "__main__":
    sys.exit(main())
