#!/usr/bin/env python3
"""Golden tests for ADinsights release readiness evaluator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc

import evaluate_release_readiness


def base_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def check_case(packet: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "release_status" in expect and packet.get("release_status") != expect["release_status"]:
        errors.append(
            f"Expected release_status={expect['release_status']}, got {packet.get('release_status')}"
        )

    if "required_approvers_contains" in expect:
        required = set(expect["required_approvers_contains"])
        actual = set(packet.get("required_approvers", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected approvers {sorted(required)} to be subset of {sorted(actual)}"
            )

    if "pending_items_contains" in expect:
        required = set(expect["pending_items_contains"])
        actual = set(packet.get("pending_items", []))
        if not required.issubset(actual):
            errors.append(
                f"Expected pending_items {sorted(required)} to be subset of {sorted(actual)}"
            )

    if packet.get("schema_version") != "1.1.0":
        errors.append(f"Expected schema_version=1.1.0, got {packet.get('schema_version')}")

    if not isinstance(packet.get("gate_results"), dict):
        errors.append("Expected gate_results to be an object.")

    return errors


def main() -> int:
    rules_path = base_dir() / "references" / "release-gates.yaml"
    cases_path = base_dir() / "references" / "release-golden-cases.yaml"
    schema_path = base_dir() / "references" / "release-decision.schema.json"

    cases_doc = load_yaml(cases_path)
    cases = cases_doc.get("cases", [])
    if not isinstance(cases, list) or not cases:
        print("[ERROR] No cases found in release-golden-cases.yaml")
        return 1

    schema = json.loads(schema_path.read_text())
    required_keys = set(schema.get("required", []))

    failures = 0

    for case in cases:
        name = case.get("name", "unnamed")
        input_data = case.get("input", {})
        expect = case.get("expect", {})

        packet = evaluate_release_readiness.evaluate_release_readiness(
            prompt=str(input_data.get("prompt", "")),
            router_packet=input_data.get("router_packet") if isinstance(input_data.get("router_packet"), dict) else {},
            scope_packet=input_data.get("scope_packet") if isinstance(input_data.get("scope_packet"), dict) else {},
            contract_packet=input_data.get("contract_packet") if isinstance(input_data.get("contract_packet"), dict) else {},
            changed_files=[str(path) for path in input_data.get("changed_files", [])],
            run_checks=bool(input_data.get("run_checks", False)),
            rules_path=rules_path,
            artifact_presence_override=input_data.get("artifact_presence_override") if isinstance(input_data.get("artifact_presence_override"), dict) else None,
            forced_check_results=input_data.get("forced_check_results") if isinstance(input_data.get("forced_check_results"), list) else None,
        )

        errors = check_case(packet, expect)

        missing_required = sorted(required_keys - set(packet.keys()))
        if missing_required:
            errors.append("Missing required keys: " + ", ".join(missing_required))

        if errors:
            failures += 1
            print(f"[FAIL] {name}")
            for err in errors:
                print(f"  - {err}")
            print("  Packet:")
            print(json.dumps(packet, indent=2))
        else:
            print(f"[PASS] {name}")

    if failures:
        print(f"\n[ERROR] {failures} release golden case(s) failed.")
        return 1

    print(f"\n[OK] {len(cases)} release golden cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
