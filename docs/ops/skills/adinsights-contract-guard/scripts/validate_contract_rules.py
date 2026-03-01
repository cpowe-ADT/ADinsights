#!/usr/bin/env python3
"""Validate contract-rules.yaml structure and values."""

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
    "ci_strict_fail_statuses",
    "contract_statuses",
    "surface_patterns",
    "surface_keywords",
    "breaking_change_keywords",
    "breaking_change_path_patterns",
    "doc_requirements_by_surface",
    "tests_by_surface",
    "base_required_reviewers",
    "breaking_change_reviewers",
    "next_action_templates",
}

REQUIRED_STATUSES = {
    "PASS_NO_CONTRACT_CHANGE",
    "WARN_POSSIBLE_CONTRACT_CHANGE",
    "ESCALATE_CONTRACT_CHANGE_REQUIRES_DOCS",
    "ESCALATE_BREAKING_CHANGE",
}

REQUIRED_STRICT_LEVELS = {"breaking_only", "breaking_or_missing_docs"}


def default_rules_path() -> Path:
    root = Path(__file__).resolve().parents[5]
    return (
        root
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-contract-guard"
        / "references"
        / "contract-rules.yaml"
    )


def signal_patterns_path_for_rules(rules_path: Path) -> Path:
    return rules_path.parent / "contract-signal-patterns.yaml"


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

    if rules.get("skill") != "adinsights-contract-guard":
        errors.append("`skill` must equal 'adinsights-contract-guard'.")

    packet_schema_version = str(rules.get("packet_schema_version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", packet_schema_version):
        errors.append("`packet_schema_version` must be semver-like (for example 1.0.0).")

    statuses = rules.get("contract_statuses")
    if not isinstance(statuses, list) or set(statuses) != REQUIRED_STATUSES:
        errors.append("`contract_statuses` must include exactly the required status set.")

    strict_levels = rules.get("ci_strict_fail_statuses")
    if not isinstance(strict_levels, dict):
        errors.append("`ci_strict_fail_statuses` must be a mapping.")
    else:
        if set(strict_levels.keys()) != REQUIRED_STRICT_LEVELS:
            errors.append(
                "`ci_strict_fail_statuses` must include exactly "
                + f"{sorted(REQUIRED_STRICT_LEVELS)}."
            )
        for level, level_statuses in strict_levels.items():
            if not isinstance(level_statuses, list) or not level_statuses:
                errors.append(f"ci_strict_fail_statuses.{level} must be a non-empty list.")
                continue
            invalid = sorted(set(str(v) for v in level_statuses) - REQUIRED_STATUSES)
            if invalid:
                errors.append(
                    f"ci_strict_fail_statuses.{level} contains invalid status(es): {', '.join(invalid)}."
                )

    surface_patterns = rules.get("surface_patterns")
    if not isinstance(surface_patterns, dict) or not surface_patterns:
        errors.append("`surface_patterns` must be a non-empty mapping.")
    else:
        for surface, patterns in surface_patterns.items():
            if not isinstance(patterns, list) or not patterns:
                errors.append(f"surface_patterns.{surface} must be a non-empty list.")
            else:
                for pattern in patterns:
                    try:
                        re.compile(str(pattern))
                    except re.error as err:
                        errors.append(f"Invalid regex pattern '{pattern}' for {surface}: {err}")

    for key in ("surface_keywords", "doc_requirements_by_surface", "tests_by_surface"):
        value = rules.get(key)
        if not isinstance(value, dict) or not value:
            errors.append(f"`{key}` must be a non-empty mapping.")

    for key in ("breaking_change_keywords", "breaking_change_path_patterns"):
        value = rules.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"`{key}` must be a non-empty list.")

    for key in ("base_required_reviewers", "breaking_change_reviewers"):
        value = rules.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"`{key}` must be a non-empty list.")

    next_actions = rules.get("next_action_templates")
    if not isinstance(next_actions, dict):
        errors.append("`next_action_templates` must be a mapping.")
    else:
        for status in REQUIRED_STATUSES:
            actions = next_actions.get(status)
            if not isinstance(actions, list) or not actions:
                errors.append(f"next_action_templates.{status} must be a non-empty list.")

    signal_patterns_path = signal_patterns_path_for_rules(path)
    if not signal_patterns_path.exists():
        errors.append(f"Missing shared signal patterns file: {signal_patterns_path}")
    else:
        signal_patterns = yaml.safe_load(signal_patterns_path.read_text()) or {}
        if not isinstance(signal_patterns, dict):
            errors.append("contract-signal-patterns.yaml must be a mapping.")
        else:
            path_patterns = signal_patterns.get("path_patterns")
            keywords = signal_patterns.get("keywords")
            if not isinstance(path_patterns, list) or not path_patterns:
                errors.append("contract-signal-patterns.yaml.path_patterns must be a non-empty list.")
            else:
                for pattern in path_patterns:
                    try:
                        re.compile(str(pattern))
                    except re.error as err:
                        errors.append(f"Invalid signal path regex pattern '{pattern}': {err}")
            if not isinstance(keywords, list) or not keywords:
                errors.append("contract-signal-patterns.yaml.keywords must be a non-empty list.")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print("[OK] Contract rules valid and complete.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate contract-rules.yaml")
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return validate_rules(args.rules)


if __name__ == "__main__":
    sys.exit(main())
