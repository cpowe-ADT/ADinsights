#!/usr/bin/env python3
"""Validate the SLB DashThis cancellation-readiness status manifest."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
DEFAULT_GOAL_DOC = DEFAULT_STATUS_FILE.with_name("2026-06-16-slb-cancellation-readiness-goals.md")
DEFAULT_BLOCKER_REGISTER = DEFAULT_STATUS_FILE.with_name(
    "2026-06-16-slb-cancellation-readiness-blocker-register.md"
)

EXPECTED_GOAL_IDS = [f"G{index}" for index in range(13)]
EXPECTED_BLOCKER_IDS = [f"BLK-{index:03d}" for index in range(1, 12)]
ALLOWED_GOAL_STATUSES = {
    "not_started",
    "implemented_path",
    "evidence_pending",
    "blocked_external",
    "review_pending",
    "passed",
    "failed_or_blocked",
}
ALLOWED_BLOCKER_STATUSES = {
    "open",
    "waiting_external",
    "evidence_needed",
    "resolved",
    "waived",
}
ALLOWED_READINESS_VALUES = {"partial", "no_go", "ready", "passed"}
ALLOWED_CANCELLATION_VALUES = {"no_go", "cancel", "keep"}
STRICT_SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"bearer\s+[a-z0-9._~+/=-]{20,}",
        r"access_token",
        r"refresh_token",
        r"client_secret",
        r"page_token",
        r"private key",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bAIza[0-9A-Za-z_-]{20,}\b",
        r"\bya29\.[0-9A-Za-z_-]+",
        r"\bEAAG[0-9A-Za-z]+",
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        r"\buser_id\b",
        r"\bprofile_id\b",
        r"\bviewer_id\b",
        r"\bactor_id\b",
        r"raw_payload",
        r"raw-provider-payload",
    ]
]
DOC_SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"bearer\s+[a-z0-9._~+/=-]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bAIza[0-9A-Za-z_-]{20,}\b",
        r"\bya29\.[0-9A-Za-z_-]+",
        r"\bEAAG[0-9A-Za-z]+",
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        r"\buser_id\b",
        r"\bprofile_id\b",
        r"\bviewer_id\b",
        r"\bactor_id\b",
        r"raw_payload",
        r"raw-provider-payload",
    ]
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the ADinsights SLB DashThis cancellation-readiness status manifest."
    )
    parser.add_argument(
        "--status-file",
        default=str(DEFAULT_STATUS_FILE),
        help="Path to the readiness status JSON manifest.",
    )
    parser.add_argument(
        "--goal-doc",
        default=str(DEFAULT_GOAL_DOC),
        help="Path to the human-readable G0-G12 goal controller.",
    )
    parser.add_argument(
        "--blocker-register",
        default=str(DEFAULT_BLOCKER_REGISTER),
        help="Path to the human-readable active blocker register.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    status_path = Path(args.status_file)
    if not status_path.is_absolute():
        status_path = REPO_ROOT / status_path
    goal_doc_path = Path(args.goal_doc)
    if not goal_doc_path.is_absolute():
        goal_doc_path = REPO_ROOT / goal_doc_path
    blocker_register_path = Path(args.blocker_register)
    if not blocker_register_path.is_absolute():
        blocker_register_path = REPO_ROOT / blocker_register_path

    errors: list[str] = []
    warnings: list[str] = []
    data = _load_status(status_path, errors)
    if data:
        _validate_status(
            data=data,
            status_path=status_path,
            goal_doc_path=goal_doc_path,
            blocker_register_path=blocker_register_path,
            errors=errors,
            warnings=warnings,
        )

    result = {
        "schema_version": "slb_cancellation_readiness_status_validation.v1",
        "status_file": str(status_path.relative_to(REPO_ROOT) if status_path.is_relative_to(REPO_ROOT) else status_path),
        "goal_doc": str(goal_doc_path.relative_to(REPO_ROOT) if goal_doc_path.is_relative_to(REPO_ROOT) else goal_doc_path),
        "blocker_register": str(
            blocker_register_path.relative_to(REPO_ROOT)
            if blocker_register_path.is_relative_to(REPO_ROOT)
            else blocker_register_path
        ),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB cancellation-readiness status valid: {str(result['valid']).lower()}")
        print(f"Status file: {result['status_file']}")
        print(f"Goal doc: {result['goal_doc']}")
        print(f"Blocker register: {result['blocker_register']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


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


def _validate_status(
    *,
    data: Mapping[str, Any],
    status_path: Path,
    goal_doc_path: Path,
    blocker_register_path: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(data.get("schema_version") == "slb_cancellation_readiness_status.v1", "Unexpected schema_version.", errors)
    _expect(data.get("timezone") == "America/Jamaica", "timezone must be America/Jamaica.", errors)
    _validate_decision(data, errors)
    _validate_guardrails(data, errors)

    blockers = _as_list(data.get("active_blockers"))
    blocker_ids = _validate_blockers(blockers, errors)
    blocker_statuses = _blocker_status_map(blockers)
    goals = _as_list(data.get("sub_goals"))
    goal_statuses = _validate_goals(goals, blocker_ids, errors)
    _validate_goal_blocker_consistency(goals=goals, blocker_statuses=blocker_statuses, errors=errors)
    _validate_readiness_claims(data, goal_statuses, blockers, errors)
    _validate_next_execution(data, errors)
    _validate_required_update_paths(data, errors)
    _validate_primary_evidence_paths(goals, status_path, errors, warnings)
    _validate_goal_doc_statuses(goal_doc_path=goal_doc_path, goal_statuses=goal_statuses, errors=errors)
    _validate_blocker_register_statuses(
        blocker_register_path=blocker_register_path,
        blockers=blockers,
        errors=errors,
    )
    _validate_json_hygiene("status manifest", data, errors)
    _validate_text_file_hygiene("goal doc", goal_doc_path, errors)
    _validate_text_file_hygiene("blocker register", blocker_register_path, errors)


def _validate_decision(data: Mapping[str, Any], errors: list[str]) -> None:
    decision = data.get("decision")
    if not isinstance(decision, Mapping):
        errors.append("decision must be an object.")
        return
    implementation = str(decision.get("implementation_readiness") or "")
    cancellation_review = str(decision.get("cancellation_review_readiness") or "")
    cancellation = str(decision.get("dashthis_cancellation") or "")
    _expect(implementation in ALLOWED_READINESS_VALUES, "implementation_readiness has an unsupported value.", errors)
    _expect(
        cancellation_review in ALLOWED_READINESS_VALUES,
        "cancellation_review_readiness has an unsupported value.",
        errors,
    )
    _expect(cancellation in ALLOWED_CANCELLATION_VALUES, "dashthis_cancellation has an unsupported value.", errors)
    _expect(bool(str(decision.get("reason") or "").strip()), "decision.reason is required.", errors)


def _validate_guardrails(data: Mapping[str, Any], errors: list[str]) -> None:
    guardrails = data.get("guardrails")
    if not isinstance(guardrails, Mapping):
        errors.append("guardrails must be an object.")
        return
    expected = {
        "instagram_v1": "deferred",
        "render_export_data_source": "stored_aggregate_adinsights_data_only",
        "live_provider_calls_at_render_export_time": "forbidden",
        "dashthis_status": "keep_active_until_evidence_passes",
    }
    for key, value in expected.items():
        _expect(guardrails.get(key) == value, f"guardrails.{key} must be {value}.", errors)


def _validate_blockers(blockers: list[Any], errors: list[str]) -> set[str]:
    ids: list[str] = []
    for index, blocker in enumerate(blockers):
        if not isinstance(blocker, Mapping):
            errors.append(f"active_blockers[{index}] must be an object.")
            continue
        blocker_id = str(blocker.get("id") or "")
        ids.append(blocker_id)
        _expect(blocker_id in EXPECTED_BLOCKER_IDS, f"Unexpected blocker id: {blocker_id}.", errors)
        _expect(
            str(blocker.get("status") or "") in ALLOWED_BLOCKER_STATUSES,
            f"{blocker_id} has an unsupported status.",
            errors,
        )
        _expect(isinstance(blocker.get("owner_route"), list) and bool(blocker.get("owner_route")), f"{blocker_id} owner_route is required.", errors)
        _expect(bool(str(blocker.get("unblock_action") or "").strip()), f"{blocker_id} unblock_action is required.", errors)
    _expect(ids == EXPECTED_BLOCKER_IDS, "active_blockers must list BLK-001 through BLK-011 in order.", errors)
    _expect(len(ids) == len(set(ids)), "active_blockers contains duplicate ids.", errors)
    return set(ids)


def _validate_goals(goals: list[Any], blocker_ids: set[str], errors: list[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    ids: list[str] = []
    for index, goal in enumerate(goals):
        if not isinstance(goal, Mapping):
            errors.append(f"sub_goals[{index}] must be an object.")
            continue
        goal_id = str(goal.get("id") or "")
        status = str(goal.get("status") or "")
        ids.append(goal_id)
        statuses[goal_id] = status
        _expect(goal_id in EXPECTED_GOAL_IDS, f"Unexpected sub-goal id: {goal_id}.", errors)
        _expect(status in ALLOWED_GOAL_STATUSES, f"{goal_id} has an unsupported status.", errors)
        _expect(bool(str(goal.get("name") or "").strip()), f"{goal_id} name is required.", errors)
        blocked_by = goal.get("blocked_by")
        _expect(isinstance(blocked_by, list), f"{goal_id} blocked_by must be a list.", errors)
        if isinstance(blocked_by, list):
            for blocker_id in blocked_by:
                _expect(str(blocker_id) in blocker_ids, f"{goal_id} references unknown blocker {blocker_id}.", errors)
        _expect(bool(str(goal.get("primary_evidence") or "").strip()), f"{goal_id} primary_evidence is required.", errors)
    _expect(ids == EXPECTED_GOAL_IDS, "sub_goals must list G0 through G12 in order.", errors)
    _expect(len(ids) == len(set(ids)), "sub_goals contains duplicate ids.", errors)
    return statuses


def _validate_readiness_claims(
    data: Mapping[str, Any],
    goal_statuses: Mapping[str, str],
    blockers: list[Any],
    errors: list[str],
) -> None:
    decision = data.get("decision") if isinstance(data.get("decision"), Mapping) else {}
    cancellation_review = str(decision.get("cancellation_review_readiness") or "")
    cancellation = str(decision.get("dashthis_cancellation") or "")
    unresolved_blockers = [
        str(blocker.get("id") or "")
        for blocker in blockers
        if isinstance(blocker, Mapping) and str(blocker.get("status") or "") not in {"resolved", "waived"}
    ]
    if cancellation_review != "no_go":
        not_passed = [goal_id for goal_id in EXPECTED_GOAL_IDS[:12] if goal_statuses.get(goal_id) != "passed"]
        if not_passed:
            errors.append(
                "cancellation_review_readiness cannot move beyond no_go until G0-G11 are passed; "
                f"not passed: {', '.join(not_passed)}."
            )
        unresolved_review_blockers = [
            blocker_id
            for blocker_id in unresolved_blockers
            if blocker_id != "BLK-011"
        ]
        if unresolved_review_blockers:
            errors.append(
                "cancellation_review_readiness cannot move beyond no_go while G0-G11 blockers remain unresolved: "
                f"{', '.join(unresolved_review_blockers)}."
            )
    if cancellation != "no_go":
        not_passed = [goal_id for goal_id in EXPECTED_GOAL_IDS if goal_statuses.get(goal_id) != "passed"]
        if not_passed:
            errors.append(
                "dashthis_cancellation cannot move beyond no_go until G0-G12 are passed; "
                f"not passed: {', '.join(not_passed)}."
            )
        if unresolved_blockers:
            errors.append(
                "dashthis_cancellation cannot move beyond no_go while unresolved blockers remain: "
                f"{', '.join(unresolved_blockers)}."
            )


def _validate_goal_blocker_consistency(
    *,
    goals: list[Any],
    blocker_statuses: Mapping[str, str],
    errors: list[str],
) -> None:
    unresolved_statuses = {"open", "waiting_external", "evidence_needed"}
    for goal in goals:
        if not isinstance(goal, Mapping) or goal.get("status") != "passed":
            continue
        goal_id = str(goal.get("id") or "")
        blockers = goal.get("blocked_by")
        if not isinstance(blockers, list):
            continue
        unresolved = [
            str(blocker_id)
            for blocker_id in blockers
            if blocker_statuses.get(str(blocker_id)) in unresolved_statuses
        ]
        if unresolved:
            errors.append(
                f"{goal_id} cannot be passed while linked blockers remain unresolved: {', '.join(unresolved)}."
            )


def _validate_next_execution(data: Mapping[str, Any], errors: list[str]) -> None:
    next_execution = data.get("next_execution")
    if not isinstance(next_execution, Mapping):
        errors.append("next_execution must be an object.")
        return
    for key in [
        "preferred_next_action",
        "next_without_external_input",
        "g0_g1_external_handoff",
        "g0_review_template",
        "g0_review_validator",
        "examples_readme",
        "g0_valid_example",
        "g1_valid_example",
        "g1_intake_template",
        "g1_intake_validator",
        "g0_g1_handoff_validator",
        "g2_g9_run_template",
        "g2_g9_run_validator",
        "g10_adversarial_template",
        "g10_adversarial_validator",
        "g11_hardening_template",
        "g11_hardening_validator",
        "g12_recommendation_template",
        "g12_recommendation_validator",
        "g12_approval_signoff_preflight",
        "evidence_chain_validator",
        "status_validator",
        "status_validator_preflight",
        "single_run_controller",
        "offline_validator",
    ]:
        _expect(bool(str(next_execution.get(key) or "").strip()), f"next_execution.{key} is required.", errors)
    review_validator = str(next_execution.get("g0_review_validator") or "")
    if review_validator:
        _expect(
            "scripts/validate_slb_g0_raj_mira_review.py" in review_validator,
            "next_execution.g0_review_validator must reference scripts/validate_slb_g0_raj_mira_review.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g0_raj_mira_review.py").exists(),
            "G0 Raj/Mira review validator script does not exist: scripts/validate_slb_g0_raj_mira_review.py.",
            errors,
        )
    intake_validator = str(next_execution.get("g1_intake_validator") or "")
    if intake_validator:
        _expect(
            "scripts/validate_slb_g1_runtime_target_intake.py" in intake_validator,
            "next_execution.g1_intake_validator must reference scripts/validate_slb_g1_runtime_target_intake.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g1_runtime_target_intake.py").exists(),
            "G1 intake validator script does not exist: scripts/validate_slb_g1_runtime_target_intake.py.",
            errors,
        )
    handoff_validator = str(next_execution.get("g0_g1_handoff_validator") or "")
    if handoff_validator:
        _expect(
            "scripts/validate_slb_g0_g1_handoff.py" in handoff_validator,
            "next_execution.g0_g1_handoff_validator must reference scripts/validate_slb_g0_g1_handoff.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g0_g1_handoff.py").exists(),
            "G0/G1 handoff validator script does not exist: scripts/validate_slb_g0_g1_handoff.py.",
            errors,
        )
    run_validator = str(next_execution.get("g2_g9_run_validator") or "")
    if run_validator:
        _expect(
            "scripts/validate_slb_g2_g9_evidence_run.py" in run_validator,
            "next_execution.g2_g9_run_validator must reference scripts/validate_slb_g2_g9_evidence_run.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g2_g9_evidence_run.py").exists(),
            "G2-G9 evidence run validator script does not exist: scripts/validate_slb_g2_g9_evidence_run.py.",
            errors,
        )
    adversarial_validator = str(next_execution.get("g10_adversarial_validator") or "")
    if adversarial_validator:
        _expect(
            "scripts/validate_slb_g10_adversarial_review.py" in adversarial_validator,
            "next_execution.g10_adversarial_validator must reference scripts/validate_slb_g10_adversarial_review.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g10_adversarial_review.py").exists(),
            "G10 adversarial review validator script does not exist: scripts/validate_slb_g10_adversarial_review.py.",
            errors,
        )
    hardening_validator = str(next_execution.get("g11_hardening_validator") or "")
    if hardening_validator:
        _expect(
            "scripts/validate_slb_g11_hardening_window.py" in hardening_validator,
            "next_execution.g11_hardening_validator must reference scripts/validate_slb_g11_hardening_window.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g11_hardening_window.py").exists(),
            "G11 hardening window validator script does not exist: scripts/validate_slb_g11_hardening_window.py.",
            errors,
        )
    recommendation_validator = str(next_execution.get("g12_recommendation_validator") or "")
    if recommendation_validator:
        _expect(
            "scripts/validate_slb_g12_final_recommendation.py" in recommendation_validator,
            "next_execution.g12_recommendation_validator must reference scripts/validate_slb_g12_final_recommendation.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_g12_final_recommendation.py").exists(),
            "G12 final recommendation validator script does not exist: scripts/validate_slb_g12_final_recommendation.py.",
            errors,
        )
    validator = str(next_execution.get("status_validator") or "")
    if validator:
        _expect(
            "scripts/validate_slb_cancellation_readiness_status.py" in validator,
            "next_execution.status_validator must reference scripts/validate_slb_cancellation_readiness_status.py.",
            errors,
        )
    chain_validator = str(next_execution.get("evidence_chain_validator") or "")
    if chain_validator:
        _expect(
            "scripts/validate_slb_evidence_chain.py" in chain_validator,
            "next_execution.evidence_chain_validator must reference scripts/validate_slb_evidence_chain.py.",
            errors,
        )
        _expect(
            (REPO_ROOT / "scripts" / "validate_slb_evidence_chain.py").exists(),
            "Evidence chain validator script does not exist: scripts/validate_slb_evidence_chain.py.",
            errors,
        )
    for key in [
        "g0_g1_external_handoff",
        "g0_review_template",
        "examples_readme",
        "g0_valid_example",
        "g1_valid_example",
        "g1_intake_template",
        "g2_g9_run_template",
        "g10_adversarial_template",
        "g11_hardening_template",
        "g12_recommendation_template",
        "g12_approval_signoff_preflight",
        "single_run_controller",
        "status_validator_preflight",
    ]:
        raw_path = str(next_execution.get(key) or "").rstrip("/")
        if raw_path:
            _expect((REPO_ROOT / raw_path).exists(), f"next_execution.{key} path does not exist: {raw_path}.", errors)
    _validate_valid_examples(next_execution, errors)


def _validate_valid_examples(next_execution: Mapping[str, Any], errors: list[str]) -> None:
    g0_example = str(next_execution.get("g0_valid_example") or "").strip()
    g1_example = str(next_execution.get("g1_valid_example") or "").strip()
    if not g0_example or not g1_example:
        return
    g0_path = REPO_ROOT / g0_example
    g1_path = REPO_ROOT / g1_example
    if not g0_path.exists() or not g1_path.exists():
        return
    _run_json_validator(
        label="G0 valid example",
        args=[
            str(REPO_ROOT / "scripts" / "validate_slb_g0_raj_mira_review.py"),
            "--review-file",
            str(g0_path),
            "--format",
            "json",
        ],
        errors=errors,
    )
    _run_json_validator(
        label="G1 valid example",
        args=[
            str(REPO_ROOT / "scripts" / "validate_slb_g1_runtime_target_intake.py"),
            "--intake-file",
            str(g1_path),
            "--format",
            "json",
        ],
        errors=errors,
    )
    _run_json_validator(
        label="G0/G1 valid example handoff",
        args=[
            str(REPO_ROOT / "scripts" / "validate_slb_g0_g1_handoff.py"),
            "--g0-review-file",
            str(g0_path),
            "--g1-intake-file",
            str(g1_path),
            "--format",
            "json",
        ],
        errors=errors,
    )
    _run_json_validator(
        label="G0/G1 valid example chain",
        args=[
            str(REPO_ROOT / "scripts" / "validate_slb_evidence_chain.py"),
            "--g0-review-file",
            str(g0_path),
            "--g1-intake-file",
            str(g1_path),
            "--format",
            "json",
        ],
        errors=errors,
    )


def _run_json_validator(*, label: str, args: list[str], errors: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return
    details = _json_validator_error_summary(completed.stdout) or completed.stderr.strip() or completed.stdout.strip()
    errors.append(f"{label} failed validation: {details}")


def _json_validator_error_summary(output: str) -> str:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, Mapping):
        return ""
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return ""
    return "; ".join(str(error) for error in errors[:3])


def _validate_required_update_paths(data: Mapping[str, Any], errors: list[str]) -> None:
    paths = data.get("required_updates_when_status_changes")
    if not isinstance(paths, list) or not paths:
        errors.append("required_updates_when_status_changes must be a non-empty list.")
        return
    for raw_path in paths:
        path = REPO_ROOT / str(raw_path)
        _expect(path.exists(), f"Required update path does not exist: {raw_path}.", errors)


def _validate_primary_evidence_paths(
    goals: list[Any],
    status_path: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    for goal in goals:
        if not isinstance(goal, Mapping):
            continue
        evidence = str(goal.get("primary_evidence") or "")
        if not evidence:
            continue
        path = REPO_ROOT / evidence
        if not path.exists():
            errors.append(f"{goal.get('id')} primary_evidence path does not exist: {evidence}.")
        if path == status_path:
            warnings.append(f"{goal.get('id')} primary_evidence points at the status manifest itself.")


def _validate_goal_doc_statuses(
    *,
    goal_doc_path: Path,
    goal_statuses: Mapping[str, str],
    errors: list[str],
) -> None:
    rows = _extract_markdown_status_table(goal_doc_path, id_pattern=r"G\d+")
    if not rows:
        errors.append(f"Could not extract G0-G12 status rows from {_display_path(goal_doc_path)}.")
        return
    ids = sorted(rows, key=_goal_sort_key)
    _expect(ids == EXPECTED_GOAL_IDS, "Goal doc must list G0 through G12 in its sub-goal status table.", errors)
    for goal_id in EXPECTED_GOAL_IDS:
        doc_status = rows.get(goal_id)
        manifest_status = goal_statuses.get(goal_id)
        _expect(
            doc_status == manifest_status,
            f"{goal_id} status mismatch: manifest={manifest_status}, goal_doc={doc_status}.",
            errors,
        )


def _validate_blocker_register_statuses(
    *,
    blocker_register_path: Path,
    blockers: list[Any],
    errors: list[str],
) -> None:
    rows = _extract_markdown_status_table(blocker_register_path, id_pattern=r"BLK-\d{3}")
    if not rows:
        errors.append(f"Could not extract BLK-001 through BLK-011 rows from {_display_path(blocker_register_path)}.")
        return
    manifest_statuses = {
        str(blocker.get("id") or ""): str(blocker.get("status") or "")
        for blocker in blockers
        if isinstance(blocker, Mapping)
    }
    ids = sorted(rows)
    _expect(ids == EXPECTED_BLOCKER_IDS, "Blocker register must list BLK-001 through BLK-011.", errors)
    for blocker_id in EXPECTED_BLOCKER_IDS:
        doc_status = rows.get(blocker_id)
        manifest_status = manifest_statuses.get(blocker_id)
        _expect(
            doc_status == manifest_status,
            f"{blocker_id} status mismatch: manifest={manifest_status}, blocker_register={doc_status}.",
            errors,
        )


def _validate_json_hygiene(label: str, payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in STRICT_SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Sensitive or user-level pattern detected in {label}: {pattern.pattern}")


def _validate_text_file_hygiene(label: str, path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    for pattern in DOC_SENSITIVE_PATTERNS:
        if pattern.search(content):
            errors.append(f"Sensitive or user-level pattern detected in {label}: {pattern.pattern}")


def _blocker_status_map(blockers: list[Any]) -> dict[str, str]:
    return {
        str(blocker.get("id") or ""): str(blocker.get("status") or "")
        for blocker in blockers
        if isinstance(blocker, Mapping)
    }


def _extract_markdown_status_table(path: Path, *, id_pattern: str) -> dict[str, str]:
    if not path.exists():
        return {}
    rows: dict[str, str] = {}
    row_pattern = re.compile(rf"^\|\s*({id_pattern})\s*\|")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not row_pattern.match(line):
            continue
        cells = [_clean_markdown_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        rows[cells[0]] = cells[2]
    return rows


def _clean_markdown_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def _goal_sort_key(goal_id: str) -> int:
    try:
        return int(goal_id.removeprefix("G"))
    except ValueError:
        return 999


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
