#!/usr/bin/env python3
"""Golden tests for ADinsights scope gatekeeper."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc

import evaluate_scope


def base_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def check_case(packet: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "scope_status" in expect and packet.get("scope_status") != expect["scope_status"]:
        errors.append(
            f"Expected scope_status={expect['scope_status']}, got {packet.get('scope_status')}"
        )

    if "touched_top_level_folders_exact" in expect:
        expected = expect["touched_top_level_folders_exact"]
        actual = packet.get("touched_top_level_folders")
        if actual != expected:
            errors.append(f"Expected touched folders {expected}, got {actual}")

    if "required_reviewers_exact" in expect:
        expected = expect["required_reviewers_exact"]
        actual = packet.get("required_reviewers")
        if actual != expected:
            errors.append(f"Expected reviewers {expected}, got {actual}")

    if "required_reviewers_contains" in expect:
        required = set(expect["required_reviewers_contains"])
        actual = set(packet.get("required_reviewers", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected reviewers {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "required_docs_updates_exact" in expect:
        expected = expect["required_docs_updates_exact"]
        actual = packet.get("required_docs_updates")
        if actual != expected:
            errors.append(f"Expected required_docs_updates {expected}, got {actual}")

    if "required_docs_updates_contains" in expect:
        required = set(expect["required_docs_updates_contains"])
        actual = set(packet.get("required_docs_updates", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected required_docs_updates {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "contract_risk_signal" in expect:
        actual = packet.get("contract_risk_signal")
        if actual != expect["contract_risk_signal"]:
            errors.append(
                f"Expected contract_risk_signal={expect['contract_risk_signal']}, got {actual}"
            )

    if "invoke_contract_guard" in expect:
        actual = packet.get("handoff_recommendations", {}).get("invoke_contract_guard")
        if actual != expect["invoke_contract_guard"]:
            errors.append(
                f"Expected invoke_contract_guard={expect['invoke_contract_guard']}, got {actual}"
            )

    if "invoke_release_readiness" in expect:
        actual = packet.get("handoff_recommendations", {}).get("invoke_release_readiness")
        if actual != expect["invoke_release_readiness"]:
            errors.append(
                f"Expected invoke_release_readiness={expect['invoke_release_readiness']}, got {actual}"
            )

    if packet.get("schema_version") != "1.1.0":
        errors.append(f"Expected schema_version=1.1.0, got {packet.get('schema_version')}")

    return errors


def main() -> int:
    rules_path = base_dir() / "references" / "scope-rules.yaml"
    cases_path = base_dir() / "references" / "scope-golden-cases.yaml"

    cases_doc = load_yaml(cases_path)
    cases = cases_doc.get("cases", [])

    if not isinstance(cases, list) or not cases:
        print("[ERROR] No cases found in scope-golden-cases.yaml")
        return 1

    failures = 0

    for case in cases:
        name = case.get("name", "unnamed")
        input_data = case.get("input", {})
        expect = case.get("expect", {})

        packet = evaluate_scope.evaluate_scope(
            prompt=str(input_data.get("prompt", "")),
            explicit_paths=[str(p) for p in input_data.get("paths", [])],
            changed_files=[str(p) for p in input_data.get("changed_files", [])],
            use_git_changed_files=False,
            rules_path=rules_path,
        )

        errors = check_case(packet, expect)
        if errors:
            failures += 1
            print(f"[FAIL] {name}")
            for err in errors:
                print(f"  - {err}")
            print(f"  Packet: {packet}")
        else:
            print(f"[PASS] {name}")

    if failures:
        print(f"\n[ERROR] {failures} scope golden case(s) failed.")
        return 1

    print(f"\n[OK] {len(cases)} scope golden cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
