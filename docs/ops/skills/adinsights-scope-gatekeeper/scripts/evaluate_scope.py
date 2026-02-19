#!/usr/bin/env python3
"""Evaluate ADinsights scope and escalation risk (advisory-first)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc

DEFAULT_PACKET_SCHEMA_VERSION = "1.1.0"


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-scope-gatekeeper/scripts/evaluate_scope.py
    return Path(__file__).resolve().parents[5]


def default_rules_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-scope-gatekeeper"
        / "references"
        / "scope-rules.yaml"
    )


def default_contract_signal_patterns_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-contract-guard"
        / "references"
        / "contract-signal-patterns.yaml"
    )


def load_rules(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("scope-rules.yaml must be a mapping")
    return data


def load_contract_signal_patterns(path: Path, fallback_patterns: list[str]) -> tuple[list[str], list[str]]:
    fallback_keywords: list[str] = []
    if not path.exists():
        return fallback_patterns, fallback_keywords

    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        return fallback_patterns, fallback_keywords

    path_patterns = data.get("path_patterns")
    keyword_patterns = data.get("keywords")
    if not isinstance(path_patterns, list) or not path_patterns:
        return fallback_patterns, fallback_keywords
    if not isinstance(keyword_patterns, list):
        keyword_patterns = []

    return [str(pattern) for pattern in path_patterns], [str(keyword) for keyword in keyword_patterns]


def discover_changed_files_from_git(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    changed: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        path_part = line[3:] if len(line) > 3 else ""
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip()
        if path_part:
            changed.append(path_part)
    return changed


def normalize_path(path: str, repo_root: Path) -> str:
    cleaned = path.strip().replace("\\", "/")
    if not cleaned:
        return cleaned

    repo_root_str = str(repo_root).replace("\\", "/")
    if cleaned.startswith(repo_root_str):
        cleaned = cleaned[len(repo_root_str) :].lstrip("/")

    cleaned = cleaned.lstrip("./")
    return cleaned


def extract_prompt_paths(prompt: str) -> list[str]:
    pattern = r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+/?"
    return sorted({match.group(0) for match in re.finditer(pattern, prompt)})


def detect_bucket(path: str, rules: dict[str, Any]) -> str | None:
    lower = path.lower()

    alias_map = rules.get("bucket_aliases", {})
    for prefix, bucket in alias_map.items():
        prefix_s = str(prefix).lower()
        if lower.startswith(prefix_s):
            return str(bucket)

    if not lower:
        return None

    top_level = lower.split("/", 1)[0]
    known = set(rules.get("known_top_level_buckets", []))
    if top_level in known:
        return top_level

    return None


def pattern_matches(path: str, pattern: str) -> bool:
    lower_path = path.lower()
    lower_pattern = pattern.lower()

    # Treat patterns with regex markers as regex; otherwise use substring match.
    regex_markers = [".*", "\\", "[", "]", "(", ")", "{", "}", "+", "?", "^", "$", "|"]
    if any(marker in pattern for marker in regex_markers):
        return re.search(pattern, path) is not None

    return lower_pattern in lower_path


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def packet_evidence_item(evidence_type: str, value: str, strength: float, source: str) -> dict[str, Any]:
    return {
        "type": evidence_type,
        "value": value,
        "strength": round(max(0.0, min(1.0, strength)), 4),
        "source": source,
    }


def choose_scope_status(
    has_paths: bool,
    touched_buckets: list[str],
    arch_risk: bool,
) -> str:
    if not has_paths:
        return "WARN_UNCLEAR_SCOPE"
    if arch_risk:
        return "ESCALATE_ARCH_RISK"
    if len(touched_buckets) > 1:
        return "ESCALATE_CROSS_SCOPE"
    return "PASS_SINGLE_SCOPE"


def required_reviewers(
    status: str,
    touched_buckets: list[str],
    contract_risk_signal: bool,
    rules: dict[str, Any],
) -> list[str]:
    reviewers: list[str] = []
    contract_defaults = rules.get("contract_signal_defaults", {})
    contract_reviewer = str(contract_defaults.get("reviewer", "Raj"))

    if status == "ESCALATE_CROSS_SCOPE":
        reviewers.append("Raj")
    elif status == "ESCALATE_ARCH_RISK":
        reviewers.extend(["Raj", "Mira"])
    elif status == "ESCALATE_CONTRACT_RISK":
        reviewers.append(contract_reviewer)

    if contract_risk_signal:
        reviewers.append(contract_reviewer)

    owner_map = rules.get("bucket_owner_personas", {})
    if status.startswith("ESCALATE"):
        for bucket in touched_buckets:
            owner = owner_map.get(bucket)
            if owner:
                reviewers.append(str(owner))

    return dedupe(reviewers)


def required_tests_by_folder(touched_buckets: list[str], rules: dict[str, Any]) -> dict[str, list[str]]:
    test_map = rules.get("bucket_required_tests", {})
    output: dict[str, list[str]] = {}
    for bucket in touched_buckets:
        tests = test_map.get(bucket, [])
        output[bucket] = [str(t) for t in tests]
    return output


def required_docs_updates(
    status: str,
    touched_buckets: list[str],
) -> list[str]:
    if status == "WARN_UNCLEAR_SCOPE":
        return []

    if "docs" in touched_buckets:
        return [
            "docs/ops/doc-index.md",
            "docs/ops/agent-activity-log.md",
        ]
    return []


def recommended_next_action(status: str, touched_buckets: list[str], contract_risk_signal: bool) -> str:
    if status == "PASS_SINGLE_SCOPE":
        bucket = touched_buckets[0] if touched_buckets else "target"
        if contract_risk_signal:
            return (
                f"Proceed within `{bucket}` scope, but run contract guard before merge "
                "to validate API/data contract impacts."
            )
        return (
            f"Proceed within `{bucket}` scope, run canonical tests for that folder, "
            "and keep changes single-folder unless new evidence appears."
        )
    if status == "WARN_UNCLEAR_SCOPE":
        return (
            "Provide explicit file paths or changed files so scope can be evaluated reliably "
            "before implementation planning."
        )
    if status == "ESCALATE_CROSS_SCOPE":
        return (
            "Either split work into single-folder PR slices or route to Raj for cross-stream coordination."
        )
    if status == "ESCALATE_CONTRACT_RISK":
        return "Run contract guard and route to Raj for cross-stream contract review."
    return (
        "Route to Raj + Mira before implementation and capture architecture rationale/rollback notes."
    )


def evaluate_scope(
    prompt: str,
    explicit_paths: list[str],
    changed_files: list[str],
    use_git_changed_files: bool,
    rules_path: Path,
) -> dict[str, Any]:
    repo_root = default_repo_root()
    rules = load_rules(rules_path)

    prompt_paths = extract_prompt_paths(prompt)

    evidence_source = "prompt_paths"
    evidence_paths: list[str] = []

    if use_git_changed_files and changed_files:
        evidence_source = "git_changed_files"
        evidence_paths = list(changed_files)
    elif explicit_paths:
        evidence_source = "explicit_paths"
        evidence_paths = list(explicit_paths)
    elif prompt_paths:
        evidence_source = "prompt_paths"
        evidence_paths = list(prompt_paths)

    normalized_paths = dedupe(
        [normalize_path(path, repo_root) for path in evidence_paths if normalize_path(path, repo_root)]
    )

    touched_buckets = dedupe(
        [bucket for bucket in (detect_bucket(path, rules) for path in normalized_paths) if bucket]
    )

    arch_patterns = [str(p) for p in rules.get("architecture_sensitive_patterns", [])]
    contract_patterns, contract_keywords = load_contract_signal_patterns(
        default_contract_signal_patterns_path(),
        [str(p) for p in rules.get("contract_risk_patterns", [])],
    )

    arch_hits = [
        path
        for path in normalized_paths
        if any(pattern_matches(path, pattern) for pattern in arch_patterns)
    ]
    contract_hits = [
        path
        for path in normalized_paths
        if any(pattern_matches(path, pattern) for pattern in contract_patterns)
    ]
    prompt_lower = prompt.lower()
    contract_keyword_hits = [
        keyword for keyword in contract_keywords if keyword.lower() in prompt_lower
    ]

    contract_risk_signal = bool(contract_hits or contract_keyword_hits)
    contract_risk_reasons = [
        f"Matched contract-risk pattern on '{path}'." for path in contract_hits
    ]
    contract_risk_reasons.extend(
        f"Matched contract-risk keyword '{keyword}' in prompt." for keyword in contract_keyword_hits
    )

    status = choose_scope_status(
        has_paths=bool(normalized_paths),
        touched_buckets=touched_buckets,
        arch_risk=bool(arch_hits),
    )

    reviewers = required_reviewers(status, touched_buckets, contract_risk_signal, rules)
    tests = required_tests_by_folder(touched_buckets, rules)
    docs = required_docs_updates(status, touched_buckets)

    rationale = [
        f"Evidence source: {evidence_source}.",
        f"Detected {len(normalized_paths)} path(s): {', '.join(normalized_paths) if normalized_paths else 'none'}.",
        f"Touched top-level folders: {', '.join(touched_buckets) if touched_buckets else 'none'}.",
    ]
    if arch_hits:
        rationale.append(
            "Architecture-sensitive paths detected: " + ", ".join(arch_hits)
        )
    if contract_risk_signal:
        rationale.append("Contract-risk signal detected: " + ", ".join(contract_hits))

    packet_schema_version = str(rules.get("packet_schema_version", DEFAULT_PACKET_SCHEMA_VERSION))
    invoke_contract_guard = contract_risk_signal
    invoke_release_readiness = (
        status in {"ESCALATE_CROSS_SCOPE", "ESCALATE_ARCH_RISK", "ESCALATE_CONTRACT_RISK"}
        or contract_risk_signal
    )

    evidence: list[dict[str, Any]] = []
    for path in normalized_paths:
        evidence.append(
            packet_evidence_item("scope_path", path, 0.8, evidence_source)
        )
    for path in arch_hits:
        evidence.append(
            packet_evidence_item("architecture_sensitive_match", path, 1.0, "rules")
        )
    for path in contract_hits:
        evidence.append(
            packet_evidence_item("contract_risk_match", path, 0.9, "rules")
        )

    return {
        "schema_version": packet_schema_version,
        "scope_status": status,
        "touched_top_level_folders": touched_buckets,
        "required_reviewers": reviewers,
        "required_tests_by_folder": tests,
        "required_docs_updates": docs,
        "recommended_next_action": recommended_next_action(status, touched_buckets, contract_risk_signal),
        "rationale": rationale,
        "advisory_only": True,
        "evidence_source": evidence_source,
        "evidence_paths": normalized_paths,
        "evidence": evidence,
        "contract_risk_signal": contract_risk_signal,
        "contract_risk_reasons": contract_risk_reasons,
        "handoff_recommendations": {
            "invoke_contract_guard": invoke_contract_guard,
            "invoke_release_readiness": invoke_release_readiness,
        },
        "signals": {
            "prompt_paths": prompt_paths,
            "explicit_paths": explicit_paths,
            "changed_files": changed_files,
            "used_git_changed_files": use_git_changed_files,
            "architecture_hits": arch_hits,
            "contract_hits": contract_hits,
            "contract_keyword_hits": contract_keyword_hits,
        },
    }


def packet_to_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Scope Gatekeeper Advisory Packet")
    lines.append(f"- Schema version: `{packet.get('schema_version', 'unknown')}`")
    lines.append(f"- Status: `{packet['scope_status']}`")
    lines.append(f"- Advisory-only: `{packet['advisory_only']}`")
    lines.append(f"- Contract risk signal: `{packet.get('contract_risk_signal')}`")
    lines.append(f"- Evidence source: `{packet['evidence_source']}`")
    lines.append(
        "- Touched folders: `"
        + (", ".join(packet.get("touched_top_level_folders", [])) or "none")
        + "`"
    )
    lines.append(
        "- Required reviewers: `"
        + (", ".join(packet.get("required_reviewers", [])) or "none")
        + "`"
    )
    handoff = packet.get("handoff_recommendations", {})
    lines.append(
        f"- Invoke contract guard: `{handoff.get('invoke_contract_guard')}`"
    )
    lines.append(
        f"- Invoke release readiness: `{handoff.get('invoke_release_readiness')}`"
    )

    lines.append("\n### Required Tests By Folder")
    tests = packet.get("required_tests_by_folder", {})
    if tests:
        for folder, commands in tests.items():
            lines.append(f"- `{folder}`")
            for command in commands:
                lines.append(f"  - `{command}`")
    else:
        lines.append("- None")

    lines.append("\n### Required Docs Updates")
    docs = packet.get("required_docs_updates", [])
    if docs:
        for doc in docs:
            lines.append(f"- `{doc}`")
    else:
        lines.append("- None")

    lines.append("\n### Recommended Next Action")
    lines.append(f"- {packet.get('recommended_next_action', '')}")

    lines.append("\n### Rationale")
    for item in packet.get("rationale", []):
        lines.append(f"- {item}")

    lines.append("\n### Contract Risk Reasons")
    reasons = packet.get("contract_risk_reasons", [])
    if reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- None")

    lines.append("\n### Evidence")
    evidence = packet.get("evidence", [])
    if evidence:
        for item in evidence:
            lines.append(
                "- "
                f"`{item.get('type')}` "
                f"`{item.get('value')}` "
                f"(strength={item.get('strength')}, source={item.get('source')})"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADinsights scope gatekeeper")
    parser.add_argument("--prompt", required=True, help="Prompt text for scope analysis")
    parser.add_argument("--path", action="append", default=[], help="Explicit path hint (repeatable)")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path (repeatable)")
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Use changed files discovered via git status if available",
    )
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = default_repo_root()

    changed_files = list(args.changed_file)
    if args.changed_files_from_git:
        changed_files.extend(discover_changed_files_from_git(repo_root))

    packet = evaluate_scope(
        prompt=args.prompt,
        explicit_paths=list(args.path) + list(args.changed_file),
        changed_files=dedupe(changed_files),
        use_git_changed_files=args.changed_files_from_git,
        rules_path=args.rules,
    )

    if args.format == "markdown":
        print(packet_to_markdown(packet))
    else:
        print(json.dumps(packet, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
