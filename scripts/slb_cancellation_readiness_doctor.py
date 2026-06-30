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
PLACEHOLDER_VALUES = {"", "pending", "tbd", "todo", "n/a", "unknown", "none", "<pending>"}
PRODUCT_CAPABILITY_SCHEMA_VERSION = "slb_product_capability_assessment.v1"

BLOCKER_CAPABILITY_LANES = {
    "BLK-001": {
        "lane": "confidence_review",
        "product_blocker": True,
        "note": "Architecture/scope review must clear before relying on the product evidence path.",
    },
    "BLK-002": {
        "lane": "target_selection_input",
        "product_blocker": False,
        "note": "Needed to bind evidence to a concrete SLB target; not evidence of a product defect.",
    },
    "BLK-003": {
        "lane": "runtime_release_input",
        "product_blocker": False,
        "note": "Needed for production-readiness evidence; not required to prove the local report system works.",
    },
    "BLK-004": {
        "lane": "source_comparison_input",
        "product_blocker": False,
        "note": "Needed for DashThis/source parity; missing values must stay missing rather than invented.",
    },
    "BLK-005": {
        "lane": "internal_product_evidence",
        "product_blocker": True,
        "note": "Run preview, diagnostics, coverage, and history proof over stored data.",
    },
    "BLK-006": {
        "lane": "internal_product_evidence",
        "product_blocker": True,
        "note": "Prove render/export paths produce non-empty CSV/PDF/PNG artifacts.",
    },
    "BLK-007": {
        "lane": "internal_product_evidence",
        "product_blocker": True,
        "note": "Prove scheduled dry-run and support diagnostics without client delivery.",
    },
    "BLK-008": {
        "lane": "internal_product_evidence",
        "product_blocker": True,
        "note": "Prove tenant isolation, audit, quota, and aggregate-only safety controls.",
    },
    "BLK-009": {
        "lane": "confidence_review",
        "product_blocker": True,
        "note": "Run adversarial review after product evidence exists.",
    },
    "BLK-010": {
        "lane": "confidence_review",
        "product_blocker": True,
        "note": "Run the hardening window after adversarial blockers are cleared.",
    },
    "BLK-011": {
        "lane": "decision_control",
        "product_blocker": False,
        "note": "Final keep/cancel recommendation; should follow product confidence evidence.",
    },
}

OBJECTIVE_MAPPINGS = [
    {
        "id": "SLB-001",
        "title": "Truthful organic metrics without read_insights",
        "goal_ids": ["G2", "G4", "G5", "G8"],
        "note": "Prove available Page follows plus post engagement render/export with reach/impressions notes.",
    },
    {
        "id": "SLB-002",
        "title": "Paid May coverage",
        "goal_ids": ["G2", "G3", "G6"],
        "note": "Prove selected-account May coverage, warning-only treatment, or approved import/backfill evidence.",
    },
    {
        "id": "SLB-003",
        "title": "Export with warnings",
        "goal_ids": ["G4", "G5", "G7"],
        "note": "Prove same fixed target can generate non-empty CSV/PDF/PNG and scheduled dry-run evidence.",
    },
    {
        "id": "SLB-004",
        "title": "Parity worksheet with real source values",
        "goal_ids": ["G6"],
        "note": "Requires real DashThis/source values; missing values must remain missing, never invented.",
    },
    {
        "id": "RPT-001",
        "title": "Governed report builder",
        "goal_ids": ["G4", "G5", "G9"],
        "note": "Prove report.v1 builder/render/export paths use governed stored report data and remain tenant-safe.",
    },
    {
        "id": "META-001",
        "title": "Metric availability states",
        "goal_ids": ["G2", "G8", "G9"],
        "note": "Prove availability states distinguish available, callable-no-data, permission-gated, and unsupported.",
    },
    {
        "id": "META-002",
        "title": "Organic fallback import",
        "goal_ids": ["G2", "G6", "G9"],
        "note": "Prove approved aggregate manual organic imports can feed reporting without live provider calls.",
    },
    {
        "id": "UX-001",
        "title": "Client-facing SLB report polish",
        "goal_ids": ["G4", "G5", "G8"],
        "note": "Prove client report render/export keeps diagnostics and operator controls collapsed.",
    },
    {
        "id": "OPS-001",
        "title": "Finish G1-G12 evidence after product/data works",
        "goal_ids": [f"G{index}" for index in range(1, 13)],
        "note": "Do not mark cancellation-review readiness until fixed target, parity, hardening, and G12 pass.",
    },
]


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
    goal_by_id = {
        str(goal.get("id") or ""): goal
        for goal in goals
        if isinstance(goal, Mapping)
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
        "fixed_target_prerequisite": _summarize_goal(goal_by_id.get("G1")),
        "g1_intake_requirements": _g1_intake_requirements(next_execution),
        "objective_progress": _objective_progress(goal_by_id, blocker_by_id),
        "product_capability_assessment": _product_capability_assessment(
            unresolved_blockers
        ),
        "recommended_action": _recommended_action(next_goal, next_blockers, next_execution),
        "local_progress_action": str(next_execution.get("next_without_external_input") or ""),
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
    classification = BLOCKER_CAPABILITY_LANES.get(str(blocker.get("id") or ""), {})
    return {
        "id": blocker.get("id"),
        "status": blocker.get("status"),
        "owner_route": blocker.get("owner_route", []),
        "unblock_action": blocker.get("unblock_action"),
        "capability_lane": classification.get("lane", "unclassified"),
        "product_blocker": bool(classification.get("product_blocker", True)),
        "capability_note": classification.get("note", ""),
    }


def _product_capability_assessment(
    unresolved_blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    product_blockers = [
        blocker for blocker in unresolved_blockers if blocker.get("product_blocker") is True
    ]
    input_blockers = [
        blocker for blocker in unresolved_blockers if blocker.get("product_blocker") is False
    ]
    lanes: dict[str, list[dict[str, Any]]] = {}
    for blocker in unresolved_blockers:
        lane = str(blocker.get("capability_lane") or "unclassified")
        lanes.setdefault(lane, []).append(blocker)

    if product_blockers:
        status = "needs_internal_product_evidence"
        interpretation = (
            "The reporting system is not yet confidence-ready because internal "
            "coverage, render/export, diagnostics, safety, review, or hardening "
            "evidence is still pending."
        )
    elif input_blockers:
        status = "product_capable_pending_comparison_or_release_inputs"
        interpretation = (
            "No current unresolved blocker is classified as a product-capability "
            "defect; remaining inputs affect parity, release evidence, or the final "
            "business cancellation decision."
        )
    else:
        status = "product_confidence_ready"
        interpretation = (
            "No unresolved blocker remains in the product-capability or comparison "
            "lanes. Validate the final recommendation before taking DashThis action."
        )

    next_internal_actions = [
        str(blocker.get("unblock_action") or "")
        for blocker in product_blockers
        if str(blocker.get("unblock_action") or "")
    ]
    return {
        "schema_version": PRODUCT_CAPABILITY_SCHEMA_VERSION,
        "status": status,
        "interpretation": interpretation,
        "external_inputs_are_product_blockers": False,
        "no_fake_data_rule": (
            "Missing DashThis/source values can block a parity or cancellation claim, "
            "but they must not be replaced with invented values."
        ),
        "counts": {
            "unresolved_total": len(unresolved_blockers),
            "product_capability_blockers": len(product_blockers),
            "comparison_or_release_inputs": len(input_blockers),
        },
        "lanes": lanes,
        "next_internal_actions": next_internal_actions,
    }


def _objective_progress(
    goal_by_id: Mapping[str, Mapping[str, Any]],
    blocker_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fixed_target_goal = goal_by_id.get("G1")
    fixed_target_gate = _fixed_target_prerequisite(fixed_target_goal)
    for objective in OBJECTIVE_MAPPINGS:
        goal_ids = [str(goal_id) for goal_id in objective["goal_ids"]]
        goals = [goal_by_id[goal_id] for goal_id in goal_ids if goal_id in goal_by_id]
        blockers = _unique_blockers_for_goals(goals, blocker_by_id)
        rows.append(
            {
                "id": objective["id"],
                "title": objective["title"],
                "status": _objective_status(goals, blockers),
                "can_start_fixed_target_evidence": fixed_target_gate["satisfied"],
                "fixed_target_prerequisite": fixed_target_gate,
                "readiness_goals": [_summarize_goal(goal) for goal in goals],
                "blockers": [_summarize_blocker(blocker) for blocker in blockers],
                "note": objective["note"],
            }
        )
    return rows


def _fixed_target_prerequisite(goal: Mapping[str, Any] | None) -> dict[str, Any]:
    summarized_goal = _summarize_goal(goal)
    status = str((summarized_goal or {}).get("status") or "")
    return {
        "required": True,
        "satisfied": status == "passed",
        "goal": summarized_goal,
        "note": (
            "G2-G12 evidence must use the approved fixed SLB report/date range. "
            "Do not claim objective evidence readiness until G1 is passed."
        ),
    }


def _unique_blockers_for_goals(
    goals: list[Mapping[str, Any]],
    blocker_by_id: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    blockers: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for goal in goals:
        for blocker_id in _as_list(goal.get("blocked_by")):
            key = str(blocker_id)
            blocker = blocker_by_id.get(key)
            if blocker and key not in seen:
                blockers.append(blocker)
                seen.add(key)
    return blockers


def _objective_status(
    goals: list[Mapping[str, Any]],
    blockers: list[Mapping[str, Any]],
) -> str:
    if not goals:
        return "not_mapped"
    unresolved_blocker_statuses = {
        str(blocker.get("status") or "")
        for blocker in blockers
        if str(blocker.get("status") or "") in UNRESOLVED_BLOCKER_STATUSES
    }
    if "waiting_external" in unresolved_blocker_statuses or "open" in unresolved_blocker_statuses:
        return "blocked_external"
    if "evidence_needed" in unresolved_blocker_statuses:
        return "evidence_pending"

    statuses = {str(goal.get("status") or "") for goal in goals}
    if statuses == {"passed"}:
        return "passed"
    if "blocked_external" in statuses:
        return "blocked_external"
    if "evidence_pending" in statuses:
        return "evidence_pending"
    if "not_started" in statuses:
        return "not_started"
    if "review_pending" in statuses:
        return "review_pending"
    if "failed_or_blocked" in statuses:
        return "failed_or_blocked"
    return sorted(statuses)[0] if statuses else "unknown"


def _g1_intake_requirements(next_execution: Mapping[str, Any]) -> dict[str, Any]:
    template_value = str(next_execution.get("g1_intake_template") or "").strip()
    summary: dict[str, Any] = {
        "template_path": template_value,
        "template_exists": False,
        "template_status": None,
        "pending_fields": [],
        "false_confirmation_fields": [],
    }
    if not template_value:
        return summary
    template_path = Path(template_value)
    if not template_path.is_absolute():
        template_path = REPO_ROOT / template_path
    summary["template_path"] = _display_path(template_path)
    if not template_path.exists():
        return summary
    summary["template_exists"] = True
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        summary["template_error"] = f"invalid JSON: {exc}"
        return summary
    if not isinstance(template, Mapping):
        summary["template_error"] = "root is not a JSON object"
        return summary
    summary["template_status"] = template.get("status")
    pending_fields: list[str] = []
    false_confirmation_fields: list[str] = []
    _collect_g1_template_fields(
        value=template,
        path="",
        pending_fields=pending_fields,
        false_confirmation_fields=false_confirmation_fields,
    )
    summary["pending_fields"] = pending_fields
    summary["false_confirmation_fields"] = false_confirmation_fields
    return summary


def _collect_g1_template_fields(
    *,
    value: Any,
    path: str,
    pending_fields: list[str],
    false_confirmation_fields: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _collect_g1_template_fields(
                value=child,
                path=child_path,
                pending_fields=pending_fields,
                false_confirmation_fields=false_confirmation_fields,
            )
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            _collect_g1_template_fields(
                value=child,
                path=child_path,
                pending_fields=pending_fields,
                false_confirmation_fields=false_confirmation_fields,
            )
        return
    if isinstance(value, str) and _is_placeholder(value):
        pending_fields.append(path)
        return
    if value is False:
        false_confirmation_fields.append(path)


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


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
                str(next_execution.get("g1_intake_draft_helper") or ""),
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
    product_capability = result.get("product_capability_assessment")
    if isinstance(product_capability, Mapping):
        print(f"Product capability status: {product_capability.get('status')}")
        print(f"Product capability note: {product_capability.get('interpretation')}")
        counts = product_capability.get("counts")
        if isinstance(counts, Mapping):
            print(
                "Product blockers: "
                f"{counts.get('product_capability_blockers')} internal, "
                f"{counts.get('comparison_or_release_inputs')} comparison/release inputs"
            )
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
    local_progress_action = str(result.get("local_progress_action") or "")
    if local_progress_action:
        print(f"Local progress while waiting: {local_progress_action}")
    fixed_target = result.get("fixed_target_prerequisite")
    if isinstance(fixed_target, Mapping):
        print(
            "Fixed-target prerequisite: "
            f"{fixed_target.get('id')} ({fixed_target.get('status')})"
        )
    g1_intake = result.get("g1_intake_requirements")
    if isinstance(g1_intake, Mapping) and g1_intake.get("template_path"):
        pending_fields = _as_list(g1_intake.get("pending_fields"))
        false_confirmation_fields = _as_list(g1_intake.get("false_confirmation_fields"))
        print(f"G1 intake template: {g1_intake.get('template_path')}")
        print(f"G1 pending fields: {len(pending_fields)}")
        for field in pending_fields:
            print(f"- {field}")
        if false_confirmation_fields:
            print("G1 false confirmations:")
            for field in false_confirmation_fields:
                print(f"- {field}")
    objective_rows = _as_list(result.get("objective_progress"))
    if objective_rows:
        print("Objective map:")
        for row in objective_rows:
            if not isinstance(row, Mapping):
                continue
            goals = [
                f"{goal.get('id')}={goal.get('status')}"
                for goal in _as_list(row.get("readiness_goals"))
                if isinstance(goal, Mapping)
            ]
            blockers = [
                f"{blocker.get('id')}={blocker.get('status')}"
                for blocker in _as_list(row.get("blockers"))
                if isinstance(blocker, Mapping)
            ]
            fixed_target = row.get("fixed_target_prerequisite")
            fixed_target_status = None
            if isinstance(fixed_target, Mapping):
                fixed_target_goal = fixed_target.get("goal")
                if isinstance(fixed_target_goal, Mapping):
                    fixed_target_status = fixed_target_goal.get("status")
            gate_detail = (
                [f"G1_prereq={fixed_target_status}"]
                if fixed_target_status is not None
                else []
            )
            details = ", ".join(gate_detail + goals + blockers)
            print(f"- {row.get('id')} [{row.get('status')}]: {details}")
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
