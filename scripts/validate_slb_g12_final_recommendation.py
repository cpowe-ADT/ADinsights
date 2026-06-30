#!/usr/bin/env python3
"""Validate SLB G12 final DashThis keep/cancel recommendation evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g12_final_recommendation.v1"
STATUS_MANIFEST_SCHEMA = "slb_cancellation_readiness_status.v1"
G11_SCHEMA_VERSION = "slb_g11_hardening_window.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
EXPECTED_GOAL_IDS = [f"G{index}" for index in range(12)]
G6_PARITY_VALIDATION_SCHEMA = "slb_evidence_validation.v1"
G6_READY_READINESS_STATUSES = {"pass", "warning"}
ALLOWED_RECOMMENDATIONS = {
    "keep_dashthis_active",
    "cancellation_review_ready",
    "cancel_dashthis_recommended",
    "cancel_dashthis_not_recommended",
}
ALLOWED_DASHTHIS_ACTIONS = {
    "keep_active",
    "keep_active_until_cancellation_date",
    "cancel_after_acceptance",
}
APPROVED_REVIEW_VALUES = {
    "approved",
    "accepted",
    "approved_with_conditions",
    "accepted_with_conditions",
    "pass",
    "passed",
}
NON_BLOCKING_REVIEW_VALUES = APPROVED_REVIEW_VALUES | {"waived", "not_required"}
CANCEL_BUSINESS_OWNER_VALUES = {"approved_cancel", "accepted_cancel", "approved"}
KEEP_BUSINESS_OWNER_VALUES = {"approved_keep", "accepted_keep", "approved", "accepted"}
PLACEHOLDER_VALUES = {
    "",
    "pending",
    "tbd",
    "todo",
    "n/a",
    "unknown",
    "none",
    "<pending>",
    "yyyy-mm-dd",
}
EVIDENCE_ROOT = Path("docs/project/evidence/dashthis-replacement")
EVIDENCE_LINK_SUFFIXES = {
    ".md",
    ".json",
    ".csv",
    ".txt",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
}
TEXT_EVIDENCE_SUFFIXES = {".md", ".json", ".csv", ".txt", ".log"}
SENSITIVE_PATTERNS = [
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a filled SLB G12 final recommendation JSON."
    )
    parser.add_argument(
        "--recommendation-file",
        required=True,
        help="Path to filled G12 recommendation JSON.",
    )
    parser.add_argument(
        "--status-manifest-file",
        help="Optional SLB cancellation-readiness status manifest. G0-G11 must be passed when provided.",
    )
    parser.add_argument(
        "--g11-window-file",
        help="Optional filled G11 hardening-window JSON. When provided, target fields must match.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    recommendation_path = _resolve_path(args.recommendation_file)
    status_manifest_path = (
        _resolve_path(args.status_manifest_file) if args.status_manifest_file else None
    )
    window_path = _resolve_path(args.g11_window_file) if args.g11_window_file else None

    errors: list[str] = []
    warnings: list[str] = []
    recommendation_payload = _load_json(
        recommendation_path, "Recommendation file", errors
    )
    status_manifest = (
        _load_json(status_manifest_path, "Status manifest file", errors)
        if status_manifest_path
        else None
    )
    window_payload = (
        _load_json(window_path, "G11 window file", errors) if window_path else None
    )
    if recommendation_payload:
        _validate_recommendation(
            recommendation_payload,
            status_manifest=status_manifest,
            window_payload=window_payload,
            errors=errors,
            warnings=warnings,
        )

    result = {
        "schema_version": "slb_g12_final_recommendation_validation.v1",
        "recommendation_file": _display_path(recommendation_path),
        "status_manifest_file": _display_path(status_manifest_path)
        if status_manifest_path
        else None,
        "g11_window_file": _display_path(window_path) if window_path else None,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G12 final recommendation valid: {str(result['valid']).lower()}")
        print(f"Recommendation file: {result['recommendation_file']}")
        if result["status_manifest_file"]:
            print(f"Status manifest file: {result['status_manifest_file']}")
        if result["g11_window_file"]:
            print(f"G11 window file: {result['g11_window_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_recommendation(
    payload: Mapping[str, Any],
    *,
    status_manifest: Mapping[str, Any] | None,
    window_payload: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(
        payload.get("schema_version") == REQUIRED_SCHEMA_VERSION,
        "Unexpected schema_version.",
        errors,
    )
    _expect(
        str(payload.get("status") or "") == "final_decision_recorded",
        "status must be final_decision_recorded.",
        errors,
    )
    references = _validate_references(payload.get("references"), errors)
    target = _validate_target(payload.get("target"), errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    recommendation = _validate_decision(payload.get("decision"), errors)
    _validate_evidence_rollup(
        payload.get("evidence_rollup"), target=target, errors=errors
    )
    _validate_cancellation_scope(
        payload.get("cancellation_scope"), recommendation, errors, warnings
    )
    _validate_final_acceptance(payload.get("final_acceptance"), errors)
    _validate_rollback_monitoring(payload.get("rollback_monitoring"), errors)
    _validate_reviewer_signoffs(
        payload.get("reviewer_signoffs"), recommendation, errors
    )
    _validate_decision_change_log(
        payload.get("decision_change_log"), recommendation, errors
    )
    if status_manifest:
        _validate_status_manifest(status_manifest, errors)
    if window_payload and target:
        _validate_g11_match(target, references, window_payload, errors)
    _validate_sensitive_patterns(payload, errors)


def _validate_references(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    references = _require_mapping(value, "references", errors)
    if not references:
        return None
    for key in [
        "status_manifest_file",
        "g1_intake_file",
        "g2_g9_run_file",
        "g10_review_file",
        "g11_window_file",
        "decision_id",
        "decision_timestamp",
        "operator",
    ]:
        _expect(_filled(references.get(key)), f"references.{key} is required.", errors)
    for key in [
        "status_manifest_valid",
        "g1_intake_valid",
        "g2_g9_run_valid",
        "g10_review_valid",
        "g11_window_valid",
    ]:
        _expect(
            references.get(key) is True,
            f"references.{key} must be true.",
            errors,
        )
    return references


def _validate_target(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    target = _require_mapping(value, "target", errors)
    if not target:
        return None
    required = [
        "environment",
        "safe_tenant_identifier",
        "safe_client_identifier",
        "report_definition_id",
        "primary_start_date",
        "primary_end_date",
    ]
    for key in required:
        _expect(_filled(target.get(key)), f"target.{key} is required.", errors)
    _expect(
        target.get("template_key") == EXPECTED_TEMPLATE_KEY,
        f"target.template_key must be {EXPECTED_TEMPLATE_KEY}.",
        errors,
    )
    _expect(
        target.get("report_schema_version") == EXPECTED_REPORT_SCHEMA,
        f"target.report_schema_version must be {EXPECTED_REPORT_SCHEMA}.",
        errors,
    )
    _expect(
        target.get("timezone") == EXPECTED_TIMEZONE,
        f"target.timezone must be {EXPECTED_TIMEZONE}.",
        errors,
    )
    start = _parse_date(
        str(target.get("primary_start_date") or ""), "target.primary_start_date", errors
    )
    end = _parse_date(
        str(target.get("primary_end_date") or ""), "target.primary_end_date", errors
    )
    if start and end:
        _expect(
            start <= end,
            "target.primary_start_date must be on or before primary_end_date.",
            errors,
        )
    return target


def _validate_guardrails(value: Any, errors: list[str]) -> None:
    guardrails = _require_mapping(value, "guardrails", errors)
    if not guardrails:
        return
    for key in [
        "instagram_deferred",
        "stored_aggregate_only",
        "no_live_provider_calls_at_render_export_time",
        "dashthis_active_until_decision",
    ]:
        _expect(guardrails.get(key) is True, f"guardrails.{key} must be true.", errors)


def _validate_decision(value: Any, errors: list[str]) -> str | None:
    decision = _require_mapping(value, "decision", errors)
    if not decision:
        return None
    recommendation = str(decision.get("recommendation") or "").strip()
    _expect(
        recommendation in ALLOWED_RECOMMENDATIONS,
        "decision.recommendation is unsupported.",
        errors,
    )
    _expect(_filled(decision.get("reason")), "decision.reason is required.", errors)
    _expect(
        decision.get("business_owner_acceptance") is True,
        "decision.business_owner_acceptance must be true.",
        errors,
    )
    dashthis_action = str(decision.get("dashthis_action") or "").strip()
    _expect(
        dashthis_action in ALLOWED_DASHTHIS_ACTIONS,
        "decision.dashthis_action is unsupported.",
        errors,
    )
    effective_date = _parse_date(
        str(decision.get("effective_date") or ""), "decision.effective_date", errors
    )
    if recommendation == "cancel_dashthis_recommended":
        _expect(
            dashthis_action == "cancel_after_acceptance",
            "decision.dashthis_action must be cancel_after_acceptance when cancellation is recommended.",
            errors,
        )
        cancellation_date = _parse_date(
            str(decision.get("dashthis_cancellation_date") or ""),
            "decision.dashthis_cancellation_date",
            errors,
        )
        if effective_date and cancellation_date:
            _expect(
                cancellation_date >= effective_date,
                "decision.dashthis_cancellation_date must be on or after decision.effective_date.",
                errors,
            )
    if recommendation in {"keep_dashthis_active", "cancel_dashthis_not_recommended"}:
        _expect(
            dashthis_action == "keep_active",
            "decision.dashthis_action must be keep_active when cancellation is not recommended.",
            errors,
        )
        _expect(
            not _filled(decision.get("dashthis_cancellation_date")),
            "decision.dashthis_cancellation_date must be empty when cancellation is not recommended.",
            errors,
        )
    return recommendation


def _validate_evidence_rollup(
    value: Any,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    rollup = _require_mapping(value, "evidence_rollup", errors)
    if not rollup:
        return
    _expect(
        list(rollup) == EXPECTED_GOAL_IDS,
        "evidence_rollup must contain G0 through G11 in order.",
        errors,
    )
    for goal_id in EXPECTED_GOAL_IDS:
        row = _require_mapping(
            rollup.get(goal_id), f"evidence_rollup.{goal_id}", errors
        )
        if not row:
            continue
        _expect(
            str(row.get("status") or "") == "passed",
            f"evidence_rollup.{goal_id}.status must be passed.",
            errors,
        )
        _expect(
            _filled(row.get("evidence_link")),
            f"evidence_rollup.{goal_id}.evidence_link is required.",
            errors,
        )
        evidence_path: Path | None = None
        if _filled(row.get("evidence_link")):
            evidence_path = _validate_evidence_link(
                goal_id, str(row.get("evidence_link") or ""), errors
            )
        if goal_id == "G6" and evidence_path:
            _validate_g6_parity_validation_evidence(
                evidence_path, target=target, errors=errors
            )
        approval = _normalized(row.get("reviewer_approval"))
        _expect(
            _filled(approval),
            f"evidence_rollup.{goal_id}.reviewer_approval is required.",
            errors,
        )
        if _filled(approval):
            _expect(
                approval in NON_BLOCKING_REVIEW_VALUES,
                f"evidence_rollup.{goal_id}.reviewer_approval must be an approved, accepted, waived, or not_required value.",
                errors,
            )


def _validate_evidence_link(goal_id: str, value: str, errors: list[str]) -> Path | None:
    path = Path(value.strip())
    field = f"evidence_rollup.{goal_id}.evidence_link"
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field} must be a repo-relative path under {EVIDENCE_ROOT}.")
        return None
    if path.parts[: len(EVIDENCE_ROOT.parts)] != EVIDENCE_ROOT.parts:
        errors.append(f"{field} must be under {EVIDENCE_ROOT}.")
        return None
    suffix = path.suffix.lower()
    if suffix not in EVIDENCE_LINK_SUFFIXES:
        errors.append(
            f"{field} must use one of: {', '.join(sorted(EVIDENCE_LINK_SUFFIXES))}."
        )
    resolved = REPO_ROOT / path
    if not resolved.exists():
        errors.append(f"{field} does not exist: {_display_path(resolved)}")
        return None
    if not resolved.is_file():
        errors.append(f"{field} must be a file: {_display_path(resolved)}")
        return None
    if resolved.stat().st_size <= 0:
        errors.append(f"{field} must be non-empty: {_display_path(resolved)}")
        return None
    if suffix in TEXT_EVIDENCE_SUFFIXES:
        _validate_text_evidence_file(field, resolved, suffix, errors)
    return resolved


def _validate_g6_parity_validation_evidence(
    path: Path,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    field = "evidence_rollup.G6.evidence_link"
    if path.suffix.lower() != ".json":
        errors.append(
            f"{field} must point to {G6_PARITY_VALIDATION_SCHEMA} JSON from slb_report_evidence_validate."
        )
        return
    payload = _load_json(path, field, errors)
    if not payload:
        return
    _expect(
        payload.get("schema_version") == G6_PARITY_VALIDATION_SCHEMA,
        f"{field}.schema_version must be {G6_PARITY_VALIDATION_SCHEMA}.",
        errors,
    )
    _expect(
        str(payload.get("readiness_status") or "") in G6_READY_READINESS_STATUSES,
        f"{field}.readiness_status must be pass or warning.",
        errors,
    )
    _expect(
        payload.get("blocker_count") == 0, f"{field}.blocker_count must be 0.", errors
    )
    _expect(payload.get("blockers") == [], f"{field}.blockers must be empty.", errors)

    unresolved = _require_mapping(
        payload.get("unresolved_parity"), f"{field}.unresolved_parity", errors
    )
    if unresolved:
        _expect(
            unresolved.get("row_count") == 0,
            f"{field}.unresolved_parity.row_count must be 0.",
            errors,
        )
        _expect(
            unresolved.get("rows") == [],
            f"{field}.unresolved_parity.rows must be empty.",
            errors,
        )

    source_inventory = _require_mapping(
        payload.get("source_value_inventory"), f"{field}.source_value_inventory", errors
    )
    if source_inventory:
        _expect(
            source_inventory.get("missing_source_value_count") == 0,
            f"{field}.source_value_inventory.missing_source_value_count must be 0.",
            errors,
        )
        _expect(
            source_inventory.get("missing_source_values") == [],
            f"{field}.source_value_inventory.missing_source_values must be empty.",
            errors,
        )
        _expect(
            source_inventory.get("unmatched_source_value_count") == 0,
            f"{field}.source_value_inventory.unmatched_source_value_count must be 0.",
            errors,
        )
        _expect(
            source_inventory.get("unmatched_source_values") == [],
            f"{field}.source_value_inventory.unmatched_source_values must be empty.",
            errors,
        )

    completion = _require_mapping(
        payload.get("parity_completion_requirements"),
        f"{field}.parity_completion_requirements",
        errors,
    )
    if completion:
        _expect(
            completion.get("ready_for_final_parity") is True,
            f"{field}.parity_completion_requirements.ready_for_final_parity must be true.",
            errors,
        )
        _expect(
            completion.get("requirement_count") == 0,
            f"{field}.parity_completion_requirements.requirement_count must be 0.",
            errors,
        )
        _expect(
            completion.get("requirements") == [],
            f"{field}.parity_completion_requirements.requirements must be empty.",
            errors,
        )

    _validate_blocking_next_actions(
        payload.get("blocking_next_actions"), f"{field}.blocking_next_actions", errors
    )

    _validate_g6_evidence_identity(
        payload.get("evidence"), target=target, field=field, errors=errors
    )


def _validate_blocking_next_actions(
    value: Any, field: str, errors: list[str]
) -> None:
    actions = _require_mapping(value, field, errors)
    if not actions:
        return
    _expect(
        actions.get("action_count") == 0,
        f"{field}.action_count must be 0.",
        errors,
    )
    _expect(
        actions.get("ready_to_run_action_count") == 0,
        f"{field}.ready_to_run_action_count must be 0.",
        errors,
    )
    _expect(
        actions.get("blocked_prerequisite_count") == 0,
        f"{field}.blocked_prerequisite_count must be 0.",
        errors,
    )
    _expect(actions.get("actions") == [], f"{field}.actions must be empty.", errors)


def _validate_g6_evidence_identity(
    value: Any,
    *,
    target: Mapping[str, Any] | None,
    field: str,
    errors: list[str],
) -> None:
    evidence = _require_mapping(value, f"{field}.evidence", errors)
    if not evidence:
        return
    report = _require_mapping(
        evidence.get("report"), f"{field}.evidence.report", errors
    )
    date_range = _require_mapping(
        evidence.get("date_range"), f"{field}.evidence.date_range", errors
    )
    if target and report:
        _expect(
            str(report.get("id") or "")
            == str(target.get("report_definition_id") or ""),
            f"{field}.evidence.report.id must match target.report_definition_id.",
            errors,
        )
        _expect(
            report.get("template_key") == target.get("template_key"),
            f"{field}.evidence.report.template_key must match target.template_key.",
            errors,
        )
        _expect(
            report.get("schema_version") == target.get("report_schema_version"),
            f"{field}.evidence.report.schema_version must match target.report_schema_version.",
            errors,
        )
    if target and date_range:
        _expect(
            date_range.get("start_date") == target.get("primary_start_date"),
            f"{field}.evidence.date_range.start_date must match target.primary_start_date.",
            errors,
        )
        _expect(
            date_range.get("end_date") == target.get("primary_end_date"),
            f"{field}.evidence.date_range.end_date must match target.primary_end_date.",
            errors,
        )
    preview_hash = str(evidence.get("preview_hash") or "")
    parity_preview_hash = str(evidence.get("parity_preview_hash") or "")
    _expect(
        _filled(preview_hash), f"{field}.evidence.preview_hash is required.", errors
    )
    _expect(
        preview_hash == parity_preview_hash,
        f"{field}.evidence.parity_preview_hash must match evidence.preview_hash.",
        errors,
    )


def _validate_text_evidence_file(
    field: str, path: Path, suffix: str, errors: list[str]
) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{field} must be UTF-8 text: {_display_path(path)}")
        return
    if suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            errors.append(f"{field} is not valid JSON: {exc}")
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            errors.append(
                f"Sensitive or user-level pattern detected in {field}: {pattern.pattern}"
            )


def _validate_cancellation_scope(
    value: Any,
    recommendation: str | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    scope = _require_mapping(value, "cancellation_scope", errors)
    if not scope:
        return
    _expect(
        scope.get("included_datasets")
        == ["paid_meta_ads", "organic_facebook_page", "content_ops"],
        "cancellation_scope.included_datasets must be paid_meta_ads, organic_facebook_page, content_ops.",
        errors,
    )
    _expect(
        scope.get("excluded_datasets") == ["organic_instagram"],
        "cancellation_scope.excluded_datasets must defer organic_instagram.",
        errors,
    )
    _expect(
        scope.get("render_source") == "stored_aggregate_adinsights_data_only",
        "cancellation_scope.render_source must be stored_aggregate_adinsights_data_only.",
        errors,
    )
    _expect(
        scope.get("live_provider_calls_at_render_export_time") == "forbidden",
        "cancellation_scope.live_provider_calls_at_render_export_time must be forbidden.",
        errors,
    )
    if recommendation == "cancel_dashthis_recommended":
        _expect(
            scope.get("official_fallback")
            in {
                "dashthis_active_until_cancellation_date",
                "exported_dashthis_historical_packet",
            },
            "cancellation_scope.official_fallback must name the fallback through cancellation.",
            errors,
        )
    elif scope.get("official_fallback") != "dashthis_active_until_decision":
        warnings.append(
            "cancellation_scope.official_fallback differs from dashthis_active_until_decision."
        )


def _validate_final_acceptance(value: Any, errors: list[str]) -> None:
    checks = _require_mapping(value, "final_acceptance", errors)
    if not checks:
        return
    for key in [
        "g0_g11_passed",
        "fixed_target_locked",
        "all_required_sections_rendered",
        "csv_pdf_png_reproducible",
        "no_secrets_raw_user_data",
        "parity_complete",
        "scheduled_dry_run_safe",
        "diagnostics_support_ready",
        "safety_controls_passed",
        "adversarial_no_blocker",
        "hardening_completed_without_reset",
        "rollback_monitoring_documented",
    ]:
        _expect(
            checks.get(key) is True, f"final_acceptance.{key} must be true.", errors
        )


def _validate_rollback_monitoring(value: Any, errors: list[str]) -> None:
    plan = _require_mapping(value, "rollback_monitoring", errors)
    if not plan:
        return
    for key in [
        "support_owner",
        "escalation_owner",
        "monitoring_owner",
        "rollback_path",
        "reversal_triggers",
        "client_communication",
    ]:
        _expect(
            _filled(plan.get(key)), f"rollback_monitoring.{key} is required.", errors
        )


def _validate_reviewer_signoffs(
    value: Any, recommendation: str | None, errors: list[str]
) -> None:
    signoffs = _require_mapping(value, "reviewer_signoffs", errors)
    if not signoffs:
        return
    for key in [
        "raj",
        "mira",
        "sofia",
        "andre",
        "lina_or_joel",
        "omar",
        "hannah",
        "nina",
        "business_owner",
    ]:
        normalized = _normalized(signoffs.get(key))
        _expect(_filled(normalized), f"reviewer_signoffs.{key} is required.", errors)
        if key != "business_owner" and _filled(normalized):
            _expect(
                normalized in NON_BLOCKING_REVIEW_VALUES,
                f"reviewer_signoffs.{key} must be an approved, accepted, waived, or not_required value.",
                errors,
            )
    if recommendation == "cancel_dashthis_recommended":
        _expect(
            _normalized(signoffs.get("business_owner")) in CANCEL_BUSINESS_OWNER_VALUES,
            "reviewer_signoffs.business_owner must approve cancellation when cancellation is recommended.",
            errors,
        )
    elif recommendation in {
        "keep_dashthis_active",
        "cancel_dashthis_not_recommended",
        "cancellation_review_ready",
    }:
        _expect(
            _normalized(signoffs.get("business_owner"))
            in KEEP_BUSINESS_OWNER_VALUES | CANCEL_BUSINESS_OWNER_VALUES,
            "reviewer_signoffs.business_owner must approve or accept the final recommendation.",
            errors,
        )


def _validate_decision_change_log(
    value: Any, recommendation: str | None, errors: list[str]
) -> None:
    if not isinstance(value, list) or not value:
        errors.append("decision_change_log must be a non-empty list.")
        return
    last = value[-1]
    row = _require_mapping(last, "decision_change_log[-1]", errors)
    if not row:
        return
    _expect(
        _filled(row.get("timestamp")),
        "decision_change_log[-1].timestamp is required.",
        errors,
    )
    _expect(
        row.get("recommendation") == recommendation,
        "decision_change_log[-1].recommendation must match decision.recommendation.",
        errors,
    )
    _expect(
        _filled(row.get("reason")),
        "decision_change_log[-1].reason is required.",
        errors,
    )
    _expect(
        _filled(row.get("approver_or_owner")),
        "decision_change_log[-1].approver_or_owner is required.",
        errors,
    )


def _validate_status_manifest(payload: Mapping[str, Any], errors: list[str]) -> None:
    _expect(
        payload.get("schema_version") == STATUS_MANIFEST_SCHEMA,
        "Status manifest schema_version is invalid.",
        errors,
    )
    goals = payload.get("sub_goals")
    if not isinstance(goals, list):
        errors.append("Status manifest sub_goals must be a list.")
        return
    statuses = {
        str(goal.get("id") or ""): str(goal.get("status") or "")
        for goal in goals
        if isinstance(goal, Mapping)
    }
    for goal_id in EXPECTED_GOAL_IDS:
        _expect(
            statuses.get(goal_id) == "passed",
            f"Status manifest {goal_id} must be passed before G12.",
            errors,
        )


def _validate_g11_match(
    target: Mapping[str, Any],
    references: Mapping[str, Any] | None,
    window_payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    _expect(
        window_payload.get("schema_version") == G11_SCHEMA_VERSION,
        "G11 window schema_version is invalid.",
        errors,
    )
    _expect(
        str(window_payload.get("status") or "") == "ready_for_g12_recommendation",
        "G11 window status must be ready_for_g12_recommendation.",
        errors,
    )
    window_target = _require_mapping(
        window_payload.get("target"), "G11 window target", errors
    )
    window_references = _require_mapping(
        window_payload.get("references"), "G11 window references", errors
    )
    if window_references:
        for key in ["g1_intake_file", "g2_g9_run_file", "g10_review_file"]:
            _expect(
                _filled(window_references.get(key)),
                f"G11 window references.{key} is required.",
                errors,
            )
        for key in ["g1_intake_valid", "g2_g9_run_valid", "g10_review_valid"]:
            _expect(
                window_references.get(key) is True,
                f"G11 window references.{key} must be true.",
                errors,
            )
        if references:
            for key in ["g1_intake_file", "g2_g9_run_file", "g10_review_file"]:
                _expect(
                    str(references.get(key) or "")
                    == str(window_references.get(key) or ""),
                    f"references.{key} must match G11 window references.{key}.",
                    errors,
                )
    if not window_target:
        return
    for key in [
        "environment",
        "safe_tenant_identifier",
        "safe_client_identifier",
        "report_definition_id",
        "template_key",
        "report_schema_version",
        "primary_start_date",
        "primary_end_date",
        "timezone",
    ]:
        _expect(
            str(target.get(key) or "") == str(window_target.get(key) or ""),
            f"target.{key} must match G11 window target.{key}.",
            errors,
        )


def _validate_sensitive_patterns(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(
                f"Sensitive or user-level pattern detected: {pattern.pattern}"
            )


def _load_json(
    path: Path | None, label: str, errors: list[str]
) -> Mapping[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        errors.append(f"{label} does not exist: {_display_path(path)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append(f"{label} root must be a JSON object.")
        return None
    return payload


def _require_mapping(
    value: Any, field: str, errors: list[str]
) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field} must be an object.")
        return None
    return value


def _filled(value: Any) -> bool:
    return _normalized(value) not in PLACEHOLDER_VALUES


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_date(value: str, field: str, errors: list[str]) -> date | None:
    if not _filled(value):
        errors.append(f"{field} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be YYYY-MM-DD.")
        return None


def _resolve_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
