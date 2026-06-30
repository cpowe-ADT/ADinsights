#!/usr/bin/env python3
"""Validate the SLB DashThis cancellation-readiness status manifest."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
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
DOCTOR_SCRIPT = REPO_ROOT / "scripts" / "slb_cancellation_readiness_doctor.py"
G1_DRAFT_HELPER_SCRIPT = REPO_ROOT / "scripts" / "slb_g1_intake_draft.py"
G1_INTAKE_VALIDATOR_SCRIPT = REPO_ROOT / "scripts" / "validate_slb_g1_runtime_target_intake.py"
G11_TEMPLATE_REFERENCE_FIELDS = {
    "g1_intake_file": None,
    "g1_intake_valid": False,
    "g2_g9_run_file": None,
    "g2_g9_run_valid": False,
    "g10_review_file": None,
    "g10_review_valid": False,
}
G12_TEMPLATE_REFERENCE_FIELDS = {
    "status_manifest_file": None,
    "status_manifest_valid": False,
    "g1_intake_file": None,
    "g1_intake_valid": False,
    "g2_g9_run_file": None,
    "g2_g9_run_valid": False,
    "g10_review_file": None,
    "g10_review_valid": False,
    "g11_window_file": None,
    "g11_window_valid": False,
}

EXPECTED_GOAL_IDS = [f"G{index}" for index in range(13)]
EXPECTED_BLOCKER_IDS = [f"BLK-{index:03d}" for index in range(1, 12)]
EXPECTED_OBJECTIVE_IDS = [
    "SLB-001",
    "SLB-002",
    "SLB-003",
    "SLB-004",
    "RPT-001",
    "META-001",
    "META-002",
    "UX-001",
    "OPS-001",
]
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
ALLOWED_OBJECTIVE_STATUSES = ALLOWED_GOAL_STATUSES | {"not_mapped", "unknown"}
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
    _validate_doctor_objective_map(status_path, errors)
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
        "g1_intake_draft_helper",
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
    intake_draft_helper = str(next_execution.get("g1_intake_draft_helper") or "")
    if intake_draft_helper:
        _expect(
            "scripts/slb_g1_intake_draft.py" in intake_draft_helper,
            "next_execution.g1_intake_draft_helper must reference scripts/slb_g1_intake_draft.py.",
            errors,
        )
        _expect(
            G1_DRAFT_HELPER_SCRIPT.exists(),
            "G1 intake draft helper script does not exist: scripts/slb_g1_intake_draft.py.",
            errors,
        )
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
            "--intake-file" in run_validator,
            "next_execution.g2_g9_run_validator must include --intake-file for the approved G1 intake.",
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
            "--g2-g9-run-file" in adversarial_validator,
            "next_execution.g10_adversarial_validator must include --g2-g9-run-file for the validated G2-G9 run.",
            errors,
        )
        _expect(
            "--intake-file" in adversarial_validator,
            "next_execution.g10_adversarial_validator must include --intake-file for the approved G1 intake.",
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
            "--g10-review-file" in hardening_validator,
            "next_execution.g11_hardening_validator must include --g10-review-file for the validated G10 review.",
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
        for required_arg in ["--status-manifest-file", "--g11-window-file"]:
            _expect(
                required_arg in recommendation_validator,
                f"next_execution.g12_recommendation_validator must include {required_arg}.",
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
        for required_arg in [
            "--status-manifest-file",
            "--g1-intake-file",
            "--g2-g9-run-file",
            "--g10-review-file",
            "--g11-window-file",
            "--g12-recommendation-file",
        ]:
            _expect(
                required_arg in chain_validator,
                f"next_execution.evidence_chain_validator must include {required_arg}.",
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
    _validate_downstream_template_references(next_execution, errors)
    _validate_valid_examples(next_execution, errors)
    _validate_g1_draft_helper_example(next_execution, errors)


def _validate_downstream_template_references(
    next_execution: Mapping[str, Any], errors: list[str]
) -> None:
    for manifest_key, expected_fields in [
        ("g11_hardening_template", G11_TEMPLATE_REFERENCE_FIELDS),
        ("g12_recommendation_template", G12_TEMPLATE_REFERENCE_FIELDS),
    ]:
        raw_path = str(next_execution.get(manifest_key) or "").strip()
        if not raw_path:
            continue
        path = _resolve_repo_path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        payload = _load_json_mapping(path, f"next_execution.{manifest_key}", errors)
        if not payload:
            continue
        references = _as_mapping(payload.get("references"))
        if not references:
            errors.append(f"next_execution.{manifest_key}.references must be an object.")
            continue
        for field, expected_value in expected_fields.items():
            _expect(
                field in references,
                f"next_execution.{manifest_key}.references.{field} is required.",
                errors,
            )
            if expected_value is not None and field in references:
                _expect(
                    references.get(field) == expected_value,
                    f"next_execution.{manifest_key}.references.{field} must default to {str(expected_value).lower()}.",
                    errors,
                )


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


def _validate_g1_draft_helper_example(next_execution: Mapping[str, Any], errors: list[str]) -> None:
    g1_example = str(next_execution.get("g1_valid_example") or "").strip()
    if not g1_example or not G1_DRAFT_HELPER_SCRIPT.exists():
        return
    g1_path = _resolve_repo_path(g1_example)
    if not g1_path.exists():
        return
    g1_payload = _load_json_mapping(g1_path, "G1 valid example", errors)
    if not g1_payload:
        return

    target = _as_mapping(g1_payload.get("target"))
    comparison = _as_mapping(g1_payload.get("comparison"))
    delivery = _as_mapping(g1_payload.get("delivery"))
    g0_clearance = _as_mapping(g1_payload.get("g0_clearance"))
    evidence = _as_mapping(g1_payload.get("evidence"))
    target_output_raw = str(evidence.get("slb_report_target_intake_output") or "").strip()
    if not target_output_raw:
        errors.append("G1 draft helper example cannot run without evidence.slb_report_target_intake_output.")
        return
    target_output_path = _resolve_repo_path(target_output_raw)
    if not target_output_path.exists():
        errors.append(f"G1 draft helper target-intake output path does not exist: {target_output_raw}.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        draft_output_path = Path(temp_dir) / "g1-draft-from-status-validator.json"
        helper_args = [
            str(G1_DRAFT_HELPER_SCRIPT),
            "--target-intake-output",
            str(target_output_path),
            "--output",
            str(draft_output_path),
        ]
        _add_optional_arg(helper_args, "--environment", target.get("environment"))
        _add_optional_arg(helper_args, "--backend-url", target.get("backend_url"))
        _add_optional_arg(helper_args, "--frontend-url", target.get("frontend_url"))
        _add_optional_arg(helper_args, "--safe-tenant-identifier", target.get("safe_tenant_identifier"))
        _add_optional_arg(helper_args, "--safe-client-identifier", target.get("safe_client_identifier"))
        _add_optional_arg(helper_args, "--currency", target.get("currency"))
        _add_optional_arg(helper_args, "--paid-meta-account-scope", target.get("paid_meta_account_scope"))
        _add_optional_arg(helper_args, "--organic-facebook-page-scope", target.get("organic_facebook_page_scope"))
        _add_optional_arg(helper_args, "--content-ops-workspace-scope", target.get("content_ops_workspace_scope"))
        _add_optional_arg(helper_args, "--comparison-owner", comparison.get("dashthis_source_comparison_owner"))
        _add_optional_arg(
            helper_args,
            "--comparison-evidence-location",
            comparison.get("dashthis_source_evidence_location"),
        )
        if comparison.get("tolerances_confirmed") is True:
            helper_args.append("--tolerances-confirmed")
        _add_optional_arg(helper_args, "--recipient-assumption", delivery.get("recipient_assumption"))
        _add_optional_arg(helper_args, "--operator-notes", evidence.get("operator_notes"))
        _add_optional_arg(helper_args, "--g0-raj-decision", g0_clearance.get("raj_decision"))
        _add_optional_arg(helper_args, "--g0-mira-decision", g0_clearance.get("mira_decision"))
        _add_optional_arg(helper_args, "--g0-can-proceed-to-g1-g11", g0_clearance.get("can_proceed_to_g1_g11"))
        _add_optional_arg(helper_args, "--g0-conditions", g0_clearance.get("conditions"))

        completed = subprocess.run(
            [sys.executable, *helper_args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            details = _json_validator_error_summary(completed.stdout) or completed.stderr.strip() or completed.stdout.strip()
            errors.append(f"G1 draft helper example failed validation: {details}")
            return

        result_payload = _parse_json_output(completed.stdout, "G1 draft helper example result", errors)
        if not isinstance(result_payload, Mapping):
            return
        _expect(
            result_payload.get("schema_version") == "slb_g1_intake_draft_result.v1",
            "G1 draft helper example result has an unexpected schema_version.",
            errors,
        )
        _expect(result_payload.get("valid") is True, "G1 draft helper example result must be valid.", errors)
        _expect(
            result_payload.get("candidate_ready_for_review") is False,
            "G1 draft helper example must not mark drafts candidate_ready_for_review.",
            errors,
        )
        _expect(result_payload.get("pending_fields") == [], "G1 draft helper example must fill all example fields.", errors)
        _expect(
            result_payload.get("false_confirmation_fields") == [],
            "G1 draft helper example must not leave false confirmation fields when example values confirm them.",
            errors,
        )
        if not draft_output_path.exists():
            errors.append("G1 draft helper example did not write draft output.")
            return

        draft = _load_json_mapping(draft_output_path, "G1 draft helper example output", errors)
        if not draft:
            return
        _expect(
            draft.get("schema_version") == "slb_g1_runtime_target_intake.v1",
            "G1 draft helper example output has an unexpected schema_version.",
            errors,
        )
        _expect(
            draft.get("status") == "pending_operator_input",
            "G1 draft helper example output must stay pending_operator_input.",
            errors,
        )
        draft_target = _as_mapping(draft.get("target"))
        for key in [
            "report_definition_id",
            "template_key",
            "report_schema_version",
            "primary_start_date",
            "primary_end_date",
        ]:
            _expect(
                draft_target.get(key) == target.get(key),
                f"G1 draft helper example output target.{key} drifted from the checked-in valid example.",
                errors,
            )
        draft_evidence = _as_mapping(draft.get("evidence"))
        _expect(
            draft_evidence.get("slb_report_target_intake_output") == target_output_raw,
            "G1 draft helper example output must preserve the target-intake evidence path.",
            errors,
        )

        validator_result = subprocess.run(
            [
                sys.executable,
                str(G1_INTAKE_VALIDATOR_SCRIPT),
                "--intake-file",
                str(draft_output_path),
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if validator_result.returncode == 0:
            errors.append("G1 draft helper example unexpectedly passed the final G1 validator before operator promotion.")
            return
        validator_payload = _parse_json_output(
            validator_result.stdout,
            "G1 draft helper example final-validator result",
            errors,
        )
        if isinstance(validator_payload, Mapping):
            _expect(
                validator_payload.get("errors") == ["status must be candidate_ready_for_review."],
                "G1 draft helper example final-validator errors must be limited to operator status promotion.",
                errors,
            )


def _validate_doctor_objective_map(status_path: Path, errors: list[str]) -> None:
    if not DOCTOR_SCRIPT.exists():
        errors.append(f"SLB readiness doctor script does not exist: {_display_path(DOCTOR_SCRIPT)}.")
        return
    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "--status-file",
            str(status_path),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip()
        errors.append(f"SLB readiness doctor failed for status manifest: {details}")
        return
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"SLB readiness doctor did not emit valid JSON: {exc}")
        return
    if not isinstance(payload, Mapping):
        errors.append("SLB readiness doctor JSON root must be an object.")
        return
    product_capability = payload.get("product_capability_assessment")
    if not isinstance(product_capability, Mapping):
        errors.append("SLB readiness doctor must emit product_capability_assessment.")
    else:
        _expect(
            product_capability.get("schema_version")
            == "slb_product_capability_assessment.v1",
            "SLB readiness doctor product_capability_assessment has unsupported schema_version.",
            errors,
        )
        _expect(
            product_capability.get("external_inputs_are_product_blockers") is False,
            "SLB readiness doctor must not classify external comparison/release inputs as product blockers.",
            errors,
        )
        _expect(
            "invented values"
            in str(product_capability.get("no_fake_data_rule") or "").lower(),
            "SLB readiness doctor product_capability_assessment must preserve the no-fake-data rule.",
            errors,
        )
        counts = product_capability.get("counts")
        _expect(
            isinstance(counts, Mapping)
            and isinstance(counts.get("product_capability_blockers"), int)
            and isinstance(counts.get("comparison_or_release_inputs"), int),
            "SLB readiness doctor product_capability_assessment must include blocker counts.",
            errors,
        )
        _expect(
            isinstance(product_capability.get("lanes"), Mapping),
            "SLB readiness doctor product_capability_assessment must include blocker lanes.",
            errors,
        )
    fixed_target = payload.get("fixed_target_prerequisite")
    if not isinstance(fixed_target, Mapping) or fixed_target.get("id") != "G1":
        errors.append("SLB readiness doctor must emit fixed_target_prerequisite for G1.")
    fixed_target_passed = isinstance(fixed_target, Mapping) and fixed_target.get("status") == "passed"
    g1_intake = payload.get("g1_intake_requirements")
    if not isinstance(g1_intake, Mapping):
        errors.append("SLB readiness doctor must emit g1_intake_requirements.")
    else:
        _expect(
            g1_intake.get("template_exists") is True,
            "SLB readiness doctor g1_intake_requirements must point to an existing template.",
            errors,
        )
        _expect(
            isinstance(g1_intake.get("pending_fields"), list)
            and "target.report_definition_id" in g1_intake.get("pending_fields", []),
            "SLB readiness doctor g1_intake_requirements must list pending target.report_definition_id.",
            errors,
        )
        _expect(
            isinstance(g1_intake.get("false_confirmation_fields"), list)
            and "comparison.tolerances_confirmed" in g1_intake.get("false_confirmation_fields", []),
            "SLB readiness doctor g1_intake_requirements must list false comparison.tolerances_confirmed.",
            errors,
        )
    objective_rows = payload.get("objective_progress")
    if not isinstance(objective_rows, list):
        errors.append("SLB readiness doctor must emit objective_progress as a list.")
        return
    objective_ids: list[str] = []
    for index, row in enumerate(objective_rows):
        if not isinstance(row, Mapping):
            errors.append(f"SLB readiness doctor objective_progress[{index}] must be an object.")
            continue
        objective_id = str(row.get("id") or "")
        objective_ids.append(objective_id)
        _expect(
            str(row.get("status") or "") in ALLOWED_OBJECTIVE_STATUSES,
            f"SLB readiness doctor objective {objective_id} has unsupported status.",
            errors,
        )
        _expect(
            isinstance(row.get("readiness_goals"), list) and bool(row.get("readiness_goals")),
            f"SLB readiness doctor objective {objective_id} must list readiness_goals.",
            errors,
        )
        fixed_target_gate = row.get("fixed_target_prerequisite")
        if not isinstance(fixed_target_gate, Mapping):
            errors.append(f"SLB readiness doctor objective {objective_id} must emit fixed_target_prerequisite.")
        else:
            _expect(
                fixed_target_gate.get("required") is True,
                f"SLB readiness doctor objective {objective_id} fixed_target_prerequisite.required must be true.",
                errors,
            )
            _expect(
                fixed_target_gate.get("satisfied") is fixed_target_passed,
                f"SLB readiness doctor objective {objective_id} fixed_target_prerequisite.satisfied must match G1 status.",
                errors,
            )
            gate_goal = fixed_target_gate.get("goal")
            _expect(
                isinstance(gate_goal, Mapping) and gate_goal.get("id") == "G1",
                f"SLB readiness doctor objective {objective_id} fixed_target_prerequisite.goal must summarize G1.",
                errors,
            )
        _expect(
            row.get("can_start_fixed_target_evidence") is fixed_target_passed,
            f"SLB readiness doctor objective {objective_id} can_start_fixed_target_evidence must match G1 status.",
            errors,
        )
        _expect(
            bool(str(row.get("note") or "").strip()),
            f"SLB readiness doctor objective {objective_id} note is required.",
            errors,
        )
    _expect(
        objective_ids == EXPECTED_OBJECTIVE_IDS,
        "SLB readiness doctor objective_progress must list active objectives in order: "
        f"{', '.join(EXPECTED_OBJECTIVE_IDS)}.",
        errors,
    )
    _expect(len(objective_ids) == len(set(objective_ids)), "SLB readiness doctor objective_progress contains duplicate ids.", errors)


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


def _load_json_mapping(path: Path, label: str, errors: list[str]) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append(f"{label} root must be a JSON object.")
        return None
    return payload


def _parse_json_output(output: str, label: str, errors: list[str]) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} did not emit valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append(f"{label} JSON root must be an object.")
        return None
    return payload


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


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _add_optional_arg(args: list[str], flag: str, value: Any) -> None:
    if value is None:
        return
    normalized = str(value).strip()
    if normalized:
        args.extend([flag, normalized])


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


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
