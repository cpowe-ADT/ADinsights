#!/usr/bin/env python3
"""Backward-compatible smoke resolver that wraps persona_router.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import persona_router


def default_catalog_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "references"
        / "persona-catalog.yaml"
    )


def legacy_resolved_by(value: str) -> str:
    if value == "explicit_stream":
        return "stream_or_workstream_id"
    return value


def packet_to_legacy(packet: dict) -> dict:
    selected = packet.get("selected_persona")
    backup = packet.get("backup_persona")

    touched_streams = packet.get("touched_streams", [])
    stream = touched_streams[0] if touched_streams else None

    return {
        "input": packet.get("input_prompt"),
        "resolved_by": legacy_resolved_by(packet.get("resolved_by", "ask_user_for_clarification")),
        "stream": stream,
        "cross_stream": packet.get("conflict_flags", {}).get("cross_stream", False),
        "primary_persona": selected,
        "backup_persona": backup,
        "reason": " ".join(packet.get("rationale", [])) if packet.get("rationale") else "",
        "escalation": packet.get("escalation_decision", {}).get("required_reviewers", []),
        "action": packet.get("action"),
        "confidence": packet.get("confidence"),
        "invoke_scope_gatekeeper": packet.get("invoke_scope_gatekeeper"),
        "invoke_contract_guard": packet.get("downstream_recommendations", {}).get("invoke_contract_guard"),
        "invoke_release_readiness": packet.get("downstream_recommendations", {}).get("invoke_release_readiness"),
        "conflict_flags": packet.get("conflict_flags"),
        "recommended_report_template": packet.get("recommended_report_template"),
        "clarifying_question": packet.get("clarifying_question"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test persona resolution priority for adinsights-persona-router."
    )
    parser.add_argument(
        "prompt",
        nargs="+",
        help="Prompt text to resolve. Pass quoted text.",
    )
    parser.add_argument(
        "--mode",
        choices=["resolve", "preflight"],
        default="resolve",
        help="Routing mode.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path hint (repeatable).",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file hint (repeatable).",
    )
    parser.add_argument(
        "--changed-files-from-git",
        action="store_true",
        help="Include changed files discovered via git status.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=default_catalog_path(),
        help="Path to persona-catalog.yaml.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print("Prompt cannot be empty.", file=sys.stderr)
        return 1

    changed_files = list(args.changed_file)
    if args.changed_files_from_git:
        changed_files.extend(persona_router.discover_changed_files_from_git(persona_router.default_repo_root()))

    packet = persona_router.build_decision_packet(
        prompt=prompt,
        mode=args.mode,
        explicit_paths=list(args.path),
        changed_files=persona_router.merge_unique(changed_files),
        use_git_changed_files=args.changed_files_from_git,
        catalog_path=args.catalog,
    )

    output = packet_to_legacy(packet)
    print(json.dumps(output, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
