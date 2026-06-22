#!/usr/bin/env python3
"""Report the next actionable SLB DashThis cancellation-readiness step."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS_FILE = (
    REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-slb-cancellation-readiness-status.json"
)
UNRESOLVED_BLOCKER_STATUSES = {"open", "waiting_external", "evidence_needed"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print the next actionable SLB DashThis cancellation-readiness step."
    )
    parser.add_argument(
        "--status-file",
        default=str(DEFAULT_STATUS_FILE),
        help="Path to the SLB cancellation-readiness status manifest.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    status_path = Path(args.status_file)
    if not status_path.is_absolute():
        status_path = REPO_ROOT / status_path

    errors: list[str] = []
    payload = _load_status(status_path, errors)
    result = _build_result(payload, status_path, errors)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 1 if errors else 0


def _build_result(
    payload: Mapping[str, Any] | None,
    status_path: Path,
    errors: list[str],
) -> dict[str, Any]:
    if not payload:
        return {
            "schema_version": "slb_cancellation_readiness_doctor.v1",
            "status_file": _display_path(status_path),
            "valid_input": False,
            "errors": errors,
        }

    goals = _as_list(payload.get("sub_goals"))
    blockers = _as_list(payload.get("active_blockers"))
    next_execution = payload.get("next_execution") if isinstance(payload.get("next_execution"), Mapping) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), Mapping) else {}
    blocker_by_id = {
        str(blocker.get("id") or ""): blocker
        for blocker in blockers
        if isinstance(blocker, Mapping)
    }
    next_goal = _first_unpassed_goal(goals)
    next_blockers = _blockers_for_goal(next_goal, blocker_by_id)
    unresolved_blockers = [
        _summarize_blocker(blocker)
        for blocker in blockers
        if isinstance(blocker, Mapping)
        and str(blocker.get("status") or "") in UNRESOLVED_BLOCKER_STATUSES
    ]

    return {
        "schema_version": "slb_cancellation_readiness_doctor.v1",
        "status_file": _display_path(status_path),
        "valid_input": not errors,
        "decision": {
            "implementation_readiness": decision.get("implementation_readiness"),
            "cancellation_review_readiness": decision.get("cancellation_review_readiness"),
            "dashthis_cancellation": decision.get("dashthis_cancellation"),
            "reason": decision.get("reason"),
        },
        "guardrails": payload.get("guardrails", {}),
        "next_goal": _summarize_goal(next_goal),
        "next_blockers": next_blockers,
        "unresolved_blocker_count": len(unresolved_blockers),
        "unresolved_blockers": unresolved_blockers,
        "recommended_action": _recommended_action(next_goal, next_blockers, next_execution),
        "commands": _recommended_commands(next_goal, next_execution),
        "required_update_paths": payload.get("required_updates_when_status_changes", []),
        "errors": errors,
    }


def _first_unpassed_goal(goals: list[Any]) -> Mapping[str, Any] | None:
    for goal in goals:
        if isinstance(goal, Mapping) and str(goal.get("status") or "") != "passed":
            return goal
    return None


def _blockers_for_goal(
    goal: Mapping[str, Any] | None,
    blocker_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not goal:
        return []
    blocked_by = goal.get("blocked_by")
    if not isinstance(blocked_by, list):
        return []
    rows: list[dict[str, Any]] = []
    for blocker_id in blocked_by:
        blocker = blocker_by_id.get(str(blocker_id))
        if blocker:
            rows.append(_summarize_blocker(blocker))
    return rows


def _summarize_goal(goal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not goal:
        return None
    return {
        "id": goal.get("id"),
        "name": goal.get("name"),
        "status": goal.get("status"),
        "primary_evidence": goal.get("primary_evidence"),
        "blocked_by": goal.get("blocked_by", []),
    }


def _summarize_blocker(blocker: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": blocker.get("id"),
        "status": blocker.get("status"),
        "owner_route": blocker.get("owner_route", []),
        "unblock_action": blocker.get("unblock_action"),
    }


def _recommended_action(
    goal: Mapping[str, Any] | None,
    blockers: list[dict[str, Any]],
    next_execution: Mapping[str, Any],
) -> str:
    if not goal:
        return "All sub-goals are passed; write or validate the final G12 recommendation before any DashThis action."
    goal_id = str(goal.get("id") or "")
    if goal_id == "G0":
        return "Fill the G0 Raj/Mira review decision JSON, validate it, then update BLK-001 and the status manifest only if Raj/Mira approve or waive the blocker."
    if goal_id == "G1":
        return "Fill the G1 runtime target intake JSON, validate it, then run the combined G0/G1 handoff validator before starting G2-G11 evidence capture."
    if blockers:
        return str(blockers[0].get("unblock_action") or next_execution.get("preferred_next_action") or "")
    return str(next_execution.get("preferred_next_action") or "Continue with the next unpassed sub-goal.")


def _recommended_commands(goal: Mapping[str, Any] | None, next_execution: Mapping[str, Any]) -> list[str]:
    commands = [
        str(next_execution.get("status_validator") or "python3 scripts/validate_slb_cancellation_readiness_status.py")
    ]
    goal_id = str((goal or {}).get("id") or "")
    if goal_id == "G0":
        commands.extend(
            [
                str(next_execution.get("g0_review_validator") or ""),
                str(next_execution.get("g0_g1_handoff_validator") or ""),
            ]
        )
    elif goal_id == "G1":
        commands.extend(
            [
                str(next_execution.get("g1_intake_validator") or ""),
                str(next_execution.get("g0_g1_handoff_validator") or ""),
            ]
        )
    else:
        for key in [
            "g2_g9_run_validator",
            "g10_adversarial_validator",
            "g11_hardening_validator",
            "g12_recommendation_validator",
        ]:
            command = str(next_execution.get(key) or "")
            if command:
                commands.append(command)
    return [command for command in commands if command]


def _print_text(result: Mapping[str, Any]) -> None:
    print("SLB cancellation-readiness doctor")
    print(f"Status file: {result.get('status_file')}")
    if result.get("errors"):
        print("Errors:")
        for error in result["errors"]:
            print(f"- {error}")
        return
    decision = result.get("decision") if isinstance(result.get("decision"), Mapping) else {}
    print(f"Cancellation review readiness: {decision.get('cancellation_review_readiness')}")
    print(f"DashThis cancellation: {decision.get('dashthis_cancellation')}")
    next_goal = result.get("next_goal")
    if isinstance(next_goal, Mapping):
        print(f"Next goal: {next_goal.get('id')} - {next_goal.get('name')} ({next_goal.get('status')})")
        print(f"Primary evidence: {next_goal.get('primary_evidence')}")
    print(f"Unresolved blockers: {result.get('unresolved_blocker_count')}")
    for blocker in result.get("next_blockers", []):
        print(f"- {blocker.get('id')} [{blocker.get('status')}]: {blocker.get('unblock_action')}")
        owners = blocker.get("owner_route") or []
        if owners:
            print(f"  Owners: {', '.join(str(owner) for owner in owners)}")
    print(f"Recommended action: {result.get('recommended_action')}")
    print("Commands:")
    for command in result.get("commands", []):
        print(f"- {command}")


def _load_status(path: Path, errors: list[str]) -> Mapping[str, Any] | None:
    if not path.exists():
        errors.append(f"Status file does not exist: {_display_path(path)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Status file is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append("Status file root must be a JSON object.")
        return None
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
