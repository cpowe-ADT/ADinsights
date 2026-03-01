#!/usr/bin/env python3
"""Evaluate ADinsights release readiness from upstream decision packets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-release-readiness/scripts/evaluate_release_readiness.py
    return Path(__file__).resolve().parents[5]


def default_rules_path() -> Path:
    return (
        default_repo_root()
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-release-readiness"
        / "references"
        / "release-gates.yaml"
    )


def load_rules(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("release-gates.yaml must be a mapping")
    return data


def load_json_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
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


def gate_entry(status: str, rationale: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "rationale": rationale,
        "evidence": evidence or [],
    }


def run_optional_checks(
    checks: list[dict[str, Any]],
    repo_root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in checks:
        cmd = str(check.get("command", "")).strip()
        if not cmd:
            continue
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        results.append(
            {
                "id": str(check.get("id", "unknown")),
                "command": cmd,
                "gate_dimension": str(check.get("gate_dimension", "test_coverage")),
                "block_on_failure": bool(check.get("block_on_failure", False)),
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "output": output.strip()[:1200],
            }
        )
    return results


def evaluate_release_readiness(
    prompt: str,
    router_packet: dict[str, Any],
    scope_packet: dict[str, Any],
    contract_packet: dict[str, Any],
    changed_files: list[str],
    run_checks: bool,
    rules_path: Path,
    artifact_presence_override: dict[str, bool] | None = None,
    forced_check_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo_root = default_repo_root()
    rules = load_rules(rules_path)

    artifact_presence_override = artifact_presence_override or {}

    gate_results: dict[str, dict[str, Any]] = {}
    blocking_issues: list[str] = []
    warnings: list[str] = []
    pending_items: list[str] = []
    required_approvers: list[str] = []
    evidence: list[dict[str, Any]] = []

    scope_status = str(scope_packet.get("scope_status", ""))
    block_scope = set(str(v) for v in rules.get("scope_control", {}).get("block_scope_statuses", []))
    warn_scope = set(str(v) for v in rules.get("scope_control", {}).get("warn_scope_statuses", []))

    if scope_status in block_scope:
        gate_results["scope_control"] = gate_entry(
            "BLOCK",
            f"Scope status '{scope_status}' is blocking for release.",
            [scope_status],
        )
        blocking_issues.append("Scope control gate blocked by architecture-level scope risk.")
    elif scope_status in warn_scope:
        gate_results["scope_control"] = gate_entry(
            "WARN",
            f"Scope status '{scope_status}' requires escalation/clarification.",
            [scope_status],
        )
        warnings.append("Scope control requires escalation or clarification before release.")
    elif scope_status:
        gate_results["scope_control"] = gate_entry(
            "PASS",
            f"Scope status '{scope_status}' is acceptable.",
            [scope_status],
        )
    else:
        gate_results["scope_control"] = gate_entry("WARN", "Scope packet missing; cannot verify scope controls.")
        warnings.append("Missing scope packet evidence.")

    required_approvers.extend(str(r) for r in scope_packet.get("required_reviewers", []))

    contract_status = str(contract_packet.get("contract_status", ""))
    block_contract = set(str(v) for v in rules.get("contract_integrity", {}).get("block_contract_statuses", []))
    warn_contract = set(str(v) for v in rules.get("contract_integrity", {}).get("warn_contract_statuses", []))

    if contract_status in block_contract:
        gate_results["contract_integrity"] = gate_entry(
            "BLOCK",
            f"Contract status '{contract_status}' is blocking.",
            [contract_status],
        )
        blocking_issues.append("Contract integrity blocked by breaking contract change.")
    elif contract_status in warn_contract:
        gate_results["contract_integrity"] = gate_entry(
            "WARN",
            f"Contract status '{contract_status}' requires follow-up.",
            [contract_status],
        )
        warnings.append("Contract integrity requires follow-up before release.")
    elif contract_status:
        gate_results["contract_integrity"] = gate_entry(
            "PASS",
            f"Contract status '{contract_status}' is acceptable.",
            [contract_status],
        )
    else:
        gate_results["contract_integrity"] = gate_entry(
            "WARN", "Contract packet missing; cannot verify contract integrity."
        )
        warnings.append("Missing contract packet evidence.")

    required_approvers.extend(str(r) for r in contract_packet.get("required_reviewers", []))

    required_tests: list[str] = []
    for commands in scope_packet.get("required_tests_by_folder", {}).values():
        if isinstance(commands, list):
            required_tests.extend(str(command) for command in commands)
    required_tests.extend(str(cmd) for cmd in contract_packet.get("required_tests", []))
    required_tests = dedupe(required_tests)

    if required_tests:
        gate_results["test_coverage"] = gate_entry(
            "INFO",
            "Required tests identified; pending explicit execution/verification.",
            required_tests,
        )
        pending_items.append("Run and verify required tests before release.")
    else:
        gate_results["test_coverage"] = gate_entry("PASS", "No additional required tests surfaced by packets.")

    risky_prompt_terms = ["pii", "secret", "token", "password", "credential"]
    lower_prompt = prompt.lower()
    security_hits = [term for term in risky_prompt_terms if term in lower_prompt]
    risky_paths = [path for path in changed_files if ".env" in path.lower() or "secret" in path.lower()]

    if security_hits or risky_paths:
        gate_results["security_pii_secrets"] = gate_entry(
            "WARN",
            "Prompt/paths include security-sensitive signals; verify secrets/PII handling.",
            security_hits + risky_paths,
        )
        warnings.append("Security/PII gate requires verification due to sensitive signals.")
    else:
        gate_results["security_pii_secrets"] = gate_entry("PASS", "No security-sensitive prompt/path signals detected.")

    required_artifacts = [str(path) for path in rules.get("required_artifacts", [])]
    missing_artifacts: list[str] = []
    for artifact in required_artifacts:
        if artifact in artifact_presence_override:
            present = bool(artifact_presence_override[artifact])
        else:
            present = (repo_root / artifact).exists()
        if not present:
            missing_artifacts.append(artifact)

    if missing_artifacts:
        gate_results["runbook_ops_readiness"] = gate_entry(
            "WARN",
            "Missing required release runbook artifacts.",
            missing_artifacts,
        )
        warnings.append("Missing required release artifacts.")
    else:
        gate_results["runbook_ops_readiness"] = gate_entry("PASS", "Required runbook artifacts are present.")

    required_docs_updates = dedupe(
        [str(v) for v in contract_packet.get("required_docs_updates", [])]
        + [str(v) for v in scope_packet.get("required_docs_updates", [])]
    )
    changed_file_set = set(changed_files)
    provided_docs_updates = [doc for doc in required_docs_updates if doc in changed_file_set]
    missing_docs_updates = [doc for doc in required_docs_updates if doc not in changed_file_set]
    if required_docs_updates:
        if missing_docs_updates:
            gate_results["documentation_completeness"] = gate_entry(
                "INFO",
                "Documentation updates are required before release.",
                missing_docs_updates,
            )
            pending_items.append("Complete required documentation updates before release.")
        else:
            gate_results["documentation_completeness"] = gate_entry(
                "PASS",
                "All required documentation updates are present in current change evidence.",
                provided_docs_updates,
            )
    else:
        gate_results["documentation_completeness"] = gate_entry(
            "PASS",
            "No pending required documentation updates from scope/contract packets.",
        )

    if (default_repo_root() / "docs/runbooks/deployment.md").exists():
        gate_results["rollout_rollback_plan"] = gate_entry(
            "PASS",
            "Deployment runbook exists for rollout/rollback planning.",
            ["docs/runbooks/deployment.md"],
        )
    else:
        gate_results["rollout_rollback_plan"] = gate_entry(
            "WARN",
            "Deployment runbook missing for rollback planning.",
        )
        warnings.append("Rollout/rollback plan evidence missing.")

    check_results: list[dict[str, Any]] = []
    if run_checks:
        if forced_check_results is not None:
            check_results = forced_check_results
        else:
            check_results = run_optional_checks(
                [dict(item) for item in rules.get("optional_checks", [])],
                default_repo_root(),
            )

        for check in check_results:
            check_id = str(check.get("id", "unknown"))
            gate_dimension = str(check.get("gate_dimension", "test_coverage"))
            ok = bool(check.get("ok", False))
            if ok:
                evidence.append(packet_evidence_item("optional_check_pass", check_id, 1.0, "run_checks"))
                continue

            evidence.append(packet_evidence_item("optional_check_fail", check_id, 1.0, "run_checks"))
            message = f"Optional check '{check_id}' failed (exit={check.get('exit_code')})."
            if bool(check.get("block_on_failure", False)):
                gate_results[gate_dimension] = gate_entry(
                    "BLOCK",
                    message,
                    [str(check.get("command", ""))],
                )
                blocking_issues.append(message)
            else:
                if gate_dimension not in gate_results or gate_results[gate_dimension].get("status") in {"PASS", "INFO"}:
                    gate_results[gate_dimension] = gate_entry(
                        "WARN",
                        message,
                        [str(check.get("command", ""))],
                    )
                warnings.append(message)

    # Ensure observability gate exists even when no checks run.
    if "observability" not in gate_results:
        gate_results["observability"] = gate_entry(
            "PASS",
            "Observability gate not explicitly blocked by packet/check evidence.",
        )

    dimension_statuses = [entry.get("status") for entry in gate_results.values()]
    if "BLOCK" in dimension_statuses:
        release_status = "GATE_BLOCK"
    elif "WARN" in dimension_statuses:
        release_status = "GATE_WARN"
    else:
        release_status = "GATE_PASS"

    next_action_map = rules.get("next_action_templates", {})
    recommended_next_action = str(next_action_map.get(release_status, "Review gate details and proceed accordingly."))

    required_approvers = dedupe(required_approvers)
    if release_status == "GATE_BLOCK" and not required_approvers:
        required_approvers = ["Raj", "Mira"]

    evidence.extend(
        packet_evidence_item("scope_status", scope_status or "missing", 0.9, "scope_packet")
        for _ in [0]
    )
    evidence.extend(
        packet_evidence_item("contract_status", contract_status or "missing", 0.9, "contract_packet")
        for _ in [0]
    )

    executive_summary = (
        f"Release status {release_status}. "
        f"Blocking issues: {len(blocking_issues)}. "
        f"Warnings: {len(warnings)}. "
        f"Pending items: {len(pending_items)}."
    )

    return {
        "schema_version": str(rules.get("packet_schema_version", "1.1.0")),
        "release_status": release_status,
        "gate_results": gate_results,
        "blocking_issues": dedupe(blocking_issues),
        "warnings": dedupe(warnings),
        "pending_items": dedupe(pending_items),
        "required_approvers": required_approvers,
        "required_artifacts": required_artifacts,
        "recommended_next_action": recommended_next_action,
        "evidence": evidence,
        "executive_summary": executive_summary,
        "advisory_only": True,
        "signals": {
            "run_checks": run_checks,
            "check_results": check_results,
            "router_packet_present": bool(router_packet),
            "scope_packet_present": bool(scope_packet),
            "contract_packet_present": bool(contract_packet),
            "changed_files": changed_files,
        },
    }


def packet_to_markdown(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Release Readiness Decision Packet")
    lines.append(f"- Schema version: `{packet.get('schema_version', 'unknown')}`")
    lines.append(f"- Release status: `{packet.get('release_status')}`")
    lines.append(f"- Advisory-only: `{packet.get('advisory_only')}`")

    lines.append("\n### Gate Results")
    for gate, result in packet.get("gate_results", {}).items():
        lines.append(
            f"- `{gate}`: `{result.get('status')}` - {result.get('rationale', '')}"
        )

    lines.append("\n### Blocking Issues")
    blocks = packet.get("blocking_issues", [])
    if blocks:
        for issue in blocks:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    lines.append("\n### Warnings")
    warns = packet.get("warnings", [])
    if warns:
        for warn in warns:
            lines.append(f"- {warn}")
    else:
        lines.append("- None")

    lines.append("\n### Pending Items")
    pending = packet.get("pending_items", [])
    if pending:
        for item in pending:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    lines.append("\n### Required Approvers")
    approvers = packet.get("required_approvers", [])
    if approvers:
        for approver in approvers:
            lines.append(f"- `{approver}`")
    else:
        lines.append("- None")

    lines.append("\n### Required Artifacts")
    for artifact in packet.get("required_artifacts", []):
        lines.append(f"- `{artifact}`")

    lines.append("\n### Recommended Next Action")
    lines.append(f"- {packet.get('recommended_next_action', '')}")

    lines.append("\n### Executive Summary")
    lines.append(f"- {packet.get('executive_summary', '')}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADinsights release readiness evaluator")
    parser.add_argument("--prompt", required=True, help="Prompt text for release readiness context")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--router-packet", type=Path, default=None)
    parser.add_argument("--scope-packet", type=Path, default=None)
    parser.add_argument("--contract-packet", type=Path, default=None)
    parser.add_argument("--run-checks", action="store_true", help="Execute optional readiness commands")
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Include changed files discovered via git status",
    )
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    changed_files: list[str] = []
    if args.changed_files_from_git:
        changed_files = discover_changed_files_from_git(default_repo_root())

    packet = evaluate_release_readiness(
        prompt=args.prompt,
        router_packet=load_json_file(args.router_packet),
        scope_packet=load_json_file(args.scope_packet),
        contract_packet=load_json_file(args.contract_packet),
        changed_files=changed_files,
        run_checks=args.run_checks,
        rules_path=args.rules,
    )

    if args.format == "markdown":
        print(packet_to_markdown(packet))
    else:
        print(json.dumps(packet, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
