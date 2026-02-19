#!/usr/bin/env python3
"""Evaluate ADinsights API/data/integration contract risk."""

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


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-contract-guard/scripts/evaluate_contract.py
    return Path(__file__).resolve().parents[5]


def default_rules_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-contract-guard"
        / "references"
        / "contract-rules.yaml"
    )


def load_rules(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("contract-rules.yaml must be a mapping")
    return data


def load_json_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


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


def extract_prompt_paths(prompt: str) -> list[str]:
    pattern = r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]*)+/?"
    return sorted({match.group(0) for match in re.finditer(pattern, prompt)})


def normalize_path(path: str, repo_root: Path) -> str:
    cleaned = path.strip().replace("\\", "/")
    if not cleaned:
        return cleaned

    repo_root_str = str(repo_root).replace("\\", "/")
    if cleaned.startswith(repo_root_str):
        cleaned = cleaned[len(repo_root_str) :].lstrip("/")

    return cleaned.lstrip("./")


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
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


def strict_fail_statuses(rules: dict[str, Any], strict_level: str) -> list[str]:
    configured = rules.get("ci_strict_fail_statuses", {})
    if isinstance(configured, dict):
        statuses = configured.get(strict_level)
        if isinstance(statuses, list) and statuses:
            return [str(status) for status in statuses]

    if strict_level == "breaking_or_missing_docs":
        return ["ESCALATE_BREAKING_CHANGE", "ESCALATE_CONTRACT_CHANGE_REQUIRES_DOCS"]
    return ["ESCALATE_BREAKING_CHANGE"]


def ci_strict_evaluation(
    rules: dict[str, Any],
    contract_status: str,
    ci_strict_enabled: bool,
    ci_strict_level: str,
) -> dict[str, Any]:
    fail_statuses = set(strict_fail_statuses(rules, ci_strict_level))
    would_fail_ci = ci_strict_enabled and contract_status in fail_statuses
    return {
        "enabled": ci_strict_enabled,
        "strict_level": ci_strict_level,
        "would_fail_ci": would_fail_ci,
    }


def pattern_matches(path: str, pattern: str) -> bool:
    regex_markers = [".*", "\\", "[", "]", "(", ")", "{", "}", "+", "?", "^", "$", "|"]
    if any(marker in pattern for marker in regex_markers):
        return re.search(pattern, path, flags=re.IGNORECASE) is not None
    return pattern.lower() in path.lower()


def gather_packet_paths(router_packet: dict[str, Any], scope_packet: dict[str, Any]) -> list[str]:
    router_signals = router_packet.get("signals", {}) if isinstance(router_packet, dict) else {}
    scope_signals = scope_packet.get("signals", {}) if isinstance(scope_packet, dict) else {}

    candidates: list[str] = []
    candidates.extend(str(p) for p in router_signals.get("explicit_paths", []) if p)
    candidates.extend(str(p) for p in router_signals.get("changed_files", []) if p)
    candidates.extend(str(p) for p in router_signals.get("prompt_paths", []) if p)
    candidates.extend(str(p) for p in scope_packet.get("evidence_paths", []) if p)
    candidates.extend(str(p) for p in scope_signals.get("changed_files", []) if p)
    return dedupe(candidates)


def classify_contract_surfaces(
    prompt: str,
    normalized_paths: list[str],
    rules: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    surface_patterns = rules.get("surface_patterns", {})
    surface_keywords = rules.get("surface_keywords", {})

    touched: list[str] = []
    rationale: list[str] = []
    evidence: list[dict[str, Any]] = []

    lower_prompt = prompt.lower()

    for surface, patterns in surface_patterns.items():
        hits: list[str] = []
        for path in normalized_paths:
            if any(pattern_matches(path, str(pattern)) for pattern in patterns):
                hits.append(path)
                evidence.append(packet_evidence_item("surface_path_match", f"{surface}:{path}", 0.9, "paths"))

        keyword_hits: list[str] = []
        for keyword in surface_keywords.get(surface, []):
            kw = str(keyword).strip().lower()
            if kw and kw in lower_prompt:
                keyword_hits.append(kw)
                evidence.append(packet_evidence_item("surface_keyword_match", f"{surface}:{kw}", 0.7, "prompt"))

        if hits or keyword_hits:
            touched.append(str(surface))
            if hits:
                rationale.append(f"Surface '{surface}' matched paths: {', '.join(dedupe(hits))}.")
            if keyword_hits:
                rationale.append(
                    f"Surface '{surface}' matched prompt keywords: {', '.join(dedupe(keyword_hits))}."
                )

    return dedupe(touched), rationale, evidence


def detect_breaking_change(prompt: str, normalized_paths: list[str], rules: dict[str, Any]) -> tuple[bool, list[str]]:
    lower_prompt = prompt.lower()
    reasons: list[str] = []
    destructive_intent_keywords = ("remove", "drop", "rename", "deprecate", "breaking", "incompatible")
    destructive_intent_present = any(keyword in lower_prompt for keyword in destructive_intent_keywords)

    for keyword in rules.get("breaking_change_keywords", []):
        key = str(keyword).strip().lower()
        if key and key in lower_prompt:
            reasons.append(f"Prompt contains breaking-change keyword '{key}'.")

    if destructive_intent_present:
        for path in normalized_paths:
            for pattern in rules.get("breaking_change_path_patterns", []):
                if pattern_matches(path, str(pattern)):
                    reasons.append(f"Path '{path}' matched breaking-change pattern '{pattern}'.")

    return bool(reasons), dedupe(reasons)


def evaluate_contract(
    prompt: str,
    explicit_paths: list[str],
    changed_files: list[str],
    use_git_changed_files: bool,
    rules_path: Path,
    router_packet: dict[str, Any] | None = None,
    scope_packet: dict[str, Any] | None = None,
    ci_strict_enabled: bool = False,
    ci_strict_level: str = "breaking_only",
) -> dict[str, Any]:
    repo_root = default_repo_root()
    rules = load_rules(rules_path)

    router_packet = router_packet or {}
    scope_packet = scope_packet or {}

    prompt_paths = extract_prompt_paths(prompt)
    packet_paths = gather_packet_paths(router_packet, scope_packet)

    evidence_source = "prompt_paths"
    evidence_paths: list[str] = []

    if use_git_changed_files and changed_files:
        evidence_source = "git_changed_files"
        evidence_paths = list(changed_files)
    elif explicit_paths:
        evidence_source = "explicit_paths"
        evidence_paths = list(explicit_paths)
    elif packet_paths:
        evidence_source = "packet_paths"
        evidence_paths = list(packet_paths)
    elif prompt_paths:
        evidence_source = "prompt_paths"
        evidence_paths = list(prompt_paths)

    normalized_paths = dedupe(
        [normalize_path(path, repo_root) for path in evidence_paths if normalize_path(path, repo_root)]
    )

    surfaces, surface_rationale, evidence = classify_contract_surfaces(prompt, normalized_paths, rules)
    breaking_change_detected, breaking_reasons = detect_breaking_change(prompt, normalized_paths, rules)

    required_docs: list[str] = []
    for surface in surfaces:
        required_docs.extend(str(path) for path in rules.get("doc_requirements_by_surface", {}).get(surface, []))
    required_docs = dedupe(required_docs)

    missing_docs = [doc for doc in required_docs if doc not in normalized_paths]

    required_tests: list[str] = []
    for surface in surfaces:
        required_tests.extend(str(cmd) for cmd in rules.get("tests_by_surface", {}).get(surface, []))
    required_tests = dedupe(required_tests)

    if not surfaces:
        contract_status = "PASS_NO_CONTRACT_CHANGE"
    elif breaking_change_detected:
        contract_status = "ESCALATE_BREAKING_CHANGE"
    elif missing_docs:
        contract_status = "ESCALATE_CONTRACT_CHANGE_REQUIRES_DOCS"
    else:
        contract_status = "WARN_POSSIBLE_CONTRACT_CHANGE"

    reviewers = [str(r) for r in rules.get("base_required_reviewers", [])]
    if contract_status == "ESCALATE_BREAKING_CHANGE":
        reviewers.extend(str(r) for r in rules.get("breaking_change_reviewers", []))
    reviewers.extend(str(r) for r in scope_packet.get("required_reviewers", []))
    required_reviewers = dedupe(reviewers)

    rationale: list[str] = []
    rationale.append(f"Evidence source: {evidence_source}.")
    rationale.append(f"Detected {len(normalized_paths)} path(s): {', '.join(normalized_paths) if normalized_paths else 'none'}.")
    rationale.extend(surface_rationale)
    rationale.extend(breaking_reasons)
    if missing_docs:
        rationale.append("Missing required contract docs updates: " + ", ".join(missing_docs) + ".")

    next_actions = [
        str(v)
        for v in rules.get("next_action_templates", {}).get(contract_status, [])
    ]
    if missing_docs:
        next_actions.append("Add contract documentation updates to this change set before merge.")
    next_actions = dedupe(next_actions)

    evidence.extend(
        packet_evidence_item("input_path", path, 0.8, evidence_source)
        for path in normalized_paths
    )

    if breaking_reasons:
        evidence.extend(
            packet_evidence_item("breaking_signal", reason, 1.0, "analysis")
            for reason in breaking_reasons
        )

    strict_eval = ci_strict_evaluation(
        rules=rules,
        contract_status=contract_status,
        ci_strict_enabled=ci_strict_enabled,
        ci_strict_level=ci_strict_level,
    )

    return {
        "schema_version": str(rules.get("packet_schema_version", "1.0.0")),
        "contract_status": contract_status,
        "breaking_change_detected": breaking_change_detected,
        "contract_surfaces_touched": surfaces,
        "required_docs_updates": missing_docs,
        "required_reviewers": required_reviewers,
        "required_tests": required_tests,
        "rationale": dedupe(rationale),
        "evidence": evidence,
        "next_actions": next_actions,
        "ci_strict_evaluation": strict_eval,
        "advisory_only": True,
        "signals": {
            "prompt_paths": prompt_paths,
            "packet_paths": packet_paths,
            "explicit_paths": explicit_paths,
            "changed_files": changed_files,
            "used_git_changed_files": use_git_changed_files,
            "evidence_source": evidence_source,
        },
    }


def packet_to_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Contract Guard Decision Packet")
    lines.append(f"- Schema version: `{packet.get('schema_version', 'unknown')}`")
    lines.append(f"- Contract status: `{packet.get('contract_status')}`")
    lines.append(f"- Breaking change: `{packet.get('breaking_change_detected')}`")
    lines.append(
        "- Surfaces touched: `"
        + (", ".join(packet.get("contract_surfaces_touched", [])) or "none")
        + "`"
    )
    lines.append(
        "- Required reviewers: `"
        + (", ".join(packet.get("required_reviewers", [])) or "none")
        + "`"
    )
    strict_eval = packet.get("ci_strict_evaluation", {})
    lines.append(f"- CI strict enabled: `{strict_eval.get('enabled')}`")
    lines.append(f"- CI strict level: `{strict_eval.get('strict_level')}`")
    lines.append(f"- CI would fail: `{strict_eval.get('would_fail_ci')}`")

    lines.append("\n### Required Docs Updates")
    docs = packet.get("required_docs_updates", [])
    if docs:
        for doc in docs:
            lines.append(f"- `{doc}`")
    else:
        lines.append("- None")

    lines.append("\n### Required Tests")
    tests = packet.get("required_tests", [])
    if tests:
        for test_cmd in tests:
            lines.append(f"- `{test_cmd}`")
    else:
        lines.append("- None")

    lines.append("\n### Next Actions")
    for action in packet.get("next_actions", []):
        lines.append(f"- {action}")

    lines.append("\n### Rationale")
    for reason in packet.get("rationale", []):
        lines.append(f"- {reason}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADinsights contract guard")
    parser.add_argument("--prompt", required=True, help="Prompt text for contract analysis")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path (repeatable)")
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Use changed files discovered via git status if available",
    )
    parser.add_argument("--router-packet", type=Path, default=None)
    parser.add_argument("--scope-packet", type=Path, default=None)
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--ci-strict", action="store_true", help="Return non-zero on breaking contract status")
    parser.add_argument(
        "--ci-strict-level",
        choices=["breaking_only", "breaking_or_missing_docs"],
        default=None,
        help=(
            "CI strictness level. "
            "`breaking_only` fails on breaking contract changes only; "
            "`breaking_or_missing_docs` fails on breaking changes and missing required contract docs."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = default_repo_root()

    changed_files = list(args.changed_file)
    if args.changed_files_from_git:
        changed_files.extend(discover_changed_files_from_git(repo_root))

    router_packet = load_json_file(args.router_packet)
    scope_packet = load_json_file(args.scope_packet)

    ci_strict_enabled = bool(args.ci_strict or args.ci_strict_level)
    ci_strict_level = str(args.ci_strict_level or "breaking_only")

    packet = evaluate_contract(
        prompt=args.prompt,
        explicit_paths=list(args.changed_file),
        changed_files=dedupe(changed_files),
        use_git_changed_files=args.changed_files_from_git,
        rules_path=args.rules,
        router_packet=router_packet,
        scope_packet=scope_packet,
        ci_strict_enabled=ci_strict_enabled,
        ci_strict_level=ci_strict_level,
    )

    if args.format == "markdown":
        print(packet_to_markdown(packet))
    else:
        print(json.dumps(packet, indent=2))

    strict_eval = packet.get("ci_strict_evaluation", {})
    if bool(strict_eval.get("enabled")) and bool(strict_eval.get("would_fail_ci")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
