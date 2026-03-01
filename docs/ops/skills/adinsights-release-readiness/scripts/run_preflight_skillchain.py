#!/usr/bin/env python3
"""One-command ADinsights skills preflight: router -> scope -> contract -> release."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py
    return Path(__file__).resolve().parents[5]


def script_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "router": repo_root / "docs" / "ops" / "skills" / "adinsights-persona-router" / "scripts" / "persona_router.py",
        "scope": repo_root / "docs" / "ops" / "skills" / "adinsights-scope-gatekeeper" / "scripts" / "evaluate_scope.py",
        "contract": repo_root / "docs" / "ops" / "skills" / "adinsights-contract-guard" / "scripts" / "evaluate_contract.py",
        "release": repo_root / "docs" / "ops" / "skills" / "adinsights-release-readiness" / "scripts" / "evaluate_release_readiness.py",
    }


def run_json_script(script: Path, args: list[str], cwd: Path) -> dict[str, Any]:
    cmd = [sys.executable, str(script), *args, "--format", "json"]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse JSON from {script}.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object JSON from {script}, got {type(data).__name__}.")

    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ADinsights skills preflight chain")
    parser.add_argument("--prompt", required=True, help="Prompt/context for preflight routing and readiness")
    parser.add_argument("--path", action="append", default=[], help="Explicit path hint (repeatable)")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path (repeatable)")
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Pass through git changed-files discovery to child evaluators",
    )
    parser.add_argument("--router-mode", choices=["resolve", "preflight"], default="preflight")
    parser.add_argument("--run-checks", action="store_true", help="Enable release-readiness optional command checks")
    parser.add_argument(
        "--contract-on-signal-only",
        action="store_true",
        help="Only run contract-guard if router/scope signal recommends it",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional directory to persist packet JSON files")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    return parser.parse_args()


def packet_to_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    packets = result.get("packets", {})

    lines: list[str] = []
    lines.append("## ADinsights Preflight Skillchain")
    lines.append(f"- Router action: `{summary.get('router_action')}`")
    lines.append(f"- Scope status: `{summary.get('scope_status')}`")
    lines.append(f"- Contract status: `{summary.get('contract_status')}`")
    lines.append(f"- Release status: `{summary.get('release_status')}`")
    lines.append(f"- Contract executed: `{summary.get('contract_executed')}`")
    lines.append(f"- Output directory: `{result.get('output_dir')}`")

    release_packet = packets.get("release", {})
    lines.append("\n### Release Blocking Issues")
    blocking = release_packet.get("blocking_issues", []) if isinstance(release_packet, dict) else []
    if blocking:
        for issue in blocking:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    lines.append("\n### Release Warnings")
    warnings = release_packet.get("warnings", []) if isinstance(release_packet, dict) else []
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo_root = default_repo_root()
    scripts = script_paths(repo_root)

    router_scope_args: list[str] = []
    contract_changed_file_args: list[str] = []
    for path in args.path:
        router_scope_args.extend(["--path", str(path)])
        contract_changed_file_args.extend(["--changed-file", str(path)])
    for path in args.changed_file:
        router_scope_args.extend(["--changed-file", str(path)])
        contract_changed_file_args.extend(["--changed-file", str(path)])
    if args.changed_files_from_git:
        router_scope_args.append("--changed-files-from-git")
        contract_changed_file_args.append("--changed-files-from-git")

    router_args = ["--prompt", args.prompt, "--mode", args.router_mode, *router_scope_args]
    router_packet = run_json_script(scripts["router"], router_args, repo_root)

    scope_args = ["--prompt", args.prompt, *router_scope_args]
    scope_packet = run_json_script(scripts["scope"], scope_args, repo_root)

    run_contract = True
    if args.contract_on_signal_only:
        router_downstream = router_packet.get("downstream_recommendations", {})
        scope_handoff = scope_packet.get("handoff_recommendations", {})
        run_contract = bool(router_downstream.get("invoke_contract_guard") or scope_handoff.get("invoke_contract_guard"))

    contract_packet: dict[str, Any]
    if run_contract:
        with tempfile.TemporaryDirectory(prefix="adinsights-preflight-contract-") as temp_contract_dir:
            router_packet_path = Path(temp_contract_dir) / "router-packet.json"
            scope_packet_path = Path(temp_contract_dir) / "scope-packet.json"
            write_json(router_packet_path, router_packet)
            write_json(scope_packet_path, scope_packet)

            contract_args = [
                "--prompt",
                args.prompt,
                *contract_changed_file_args,
                "--router-packet",
                str(router_packet_path),
                "--scope-packet",
                str(scope_packet_path),
            ]
            contract_packet = run_json_script(scripts["contract"], contract_args, repo_root)
    else:
        contract_packet = {
            "schema_version": "1.0.0",
            "contract_status": "PASS_NO_CONTRACT_CHANGE",
            "breaking_change_detected": False,
            "contract_surfaces_touched": [],
            "required_docs_updates": [],
            "required_reviewers": [],
            "required_tests": [],
            "rationale": ["Contract guard skipped because no contract signal was raised."],
            "evidence": [],
            "next_actions": ["No contract-specific follow-up required."],
            "advisory_only": True,
            "signals": {"skipped": True},
        }

    output_dir: Path
    temp_output_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.output_dir:
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_output_dir = tempfile.TemporaryDirectory(prefix="adinsights-preflight-output-")
        output_dir = Path(temp_output_dir.name)

    router_packet_path = output_dir / "router-packet.json"
    scope_packet_path = output_dir / "scope-packet.json"
    contract_packet_path = output_dir / "contract-packet.json"
    release_packet_path = output_dir / "release-packet.json"

    write_json(router_packet_path, router_packet)
    write_json(scope_packet_path, scope_packet)
    write_json(contract_packet_path, contract_packet)

    release_args = [
        "--prompt",
        args.prompt,
        "--router-packet",
        str(router_packet_path),
        "--scope-packet",
        str(scope_packet_path),
        "--contract-packet",
        str(contract_packet_path),
    ]
    if args.run_checks:
        release_args.append("--run-checks")
    if args.changed_files_from_git:
        release_args.append("--changed-files-from-git")

    release_packet = run_json_script(scripts["release"], release_args, repo_root)
    write_json(release_packet_path, release_packet)

    result = {
        "schema_version": "1.0.0",
        "pipeline": "adinsights-preflight-skillchain",
        "output_dir": str(output_dir),
        "packets": {
            "router": router_packet,
            "scope": scope_packet,
            "contract": contract_packet,
            "release": release_packet,
        },
        "summary": {
            "router_action": router_packet.get("action"),
            "scope_status": scope_packet.get("scope_status"),
            "contract_status": contract_packet.get("contract_status"),
            "release_status": release_packet.get("release_status"),
            "contract_executed": run_contract,
        },
    }

    if args.format == "markdown":
        print(packet_to_markdown(result))
    else:
        print(json.dumps(result, indent=2))

    if temp_output_dir is not None:
        temp_output_dir.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
