#!/usr/bin/env python3
"""Validate the G1 fixed SLB runtime target intake JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g1_runtime_target_intake.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
ALLOWED_G0_PROCEED_VALUES = {"yes", "approved", "approved_with_conditions", "conditional"}
ALLOWED_G0_REVIEWER_DECISIONS = {"approved", "approved_with_followups", "approved_with_conditions", "conditional"}
CONDITIONAL_G0_VALUES = {"approved_with_followups", "approved_with_conditions", "conditional"}
PLACEHOLDER_VALUES = {"", "pending", "tbd", "todo", "n/a", "unknown", "none", "<pending>"}
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
    parser = argparse.ArgumentParser(description="Validate SLB G1 runtime target intake JSON.")
    parser.add_argument("--intake-file", required=True, help="Path to filled G1 runtime intake JSON.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    intake_path = Path(args.intake_file)
    if not intake_path.is_absolute():
        intake_path = REPO_ROOT / intake_path

    errors: list[str] = []
    warnings: list[str] = []
    payload = _load_json(intake_path, errors)
    if payload:
        _validate(payload, errors=errors, warnings=warnings)

    result = {
        "schema_version": "slb_g1_runtime_target_intake_validation.v1",
        "intake_file": _display_path(intake_path),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G1 runtime target intake valid: {str(result['valid']).lower()}")
        print(f"Intake file: {result['intake_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _load_json(path: Path, errors: list[str]) -> Mapping[str, Any] | None:
    if not path.exists():
        errors.append(f"Intake file does not exist: {_display_path(path)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Intake file is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append("Intake file root must be a JSON object.")
        return None
    return payload


def _validate(payload: Mapping[str, Any], *, errors: list[str], warnings: list[str]) -> None:
    _expect(payload.get("schema_version") == REQUIRED_SCHEMA_VERSION, "Unexpected schema_version.", errors)
    _expect(str(payload.get("status") or "") == "candidate_ready_for_review", "status must be candidate_ready_for_review.", errors)
    _validate_g0(payload.get("g0_clearance"), errors)
    target = _validate_target(payload.get("target"), errors)
    _validate_comparison(payload.get("comparison"), errors)
    _validate_delivery(payload.get("delivery"), errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    _validate_evidence(payload.get("evidence"), target=target, errors=errors, warnings=warnings)
    _validate_sensitive_patterns(payload, errors)


def _validate_g0(value: Any, errors: list[str]) -> None:
    g0 = _require_mapping(value, "g0_clearance", errors)
    if not g0:
        return
    for key in ["raj_decision", "mira_decision", "can_proceed_to_g1_g11"]:
        _expect(_filled(g0.get(key)), f"g0_clearance.{key} is required.", errors)
    raj_decision = str(g0.get("raj_decision") or "").strip().lower()
    mira_decision = str(g0.get("mira_decision") or "").strip().lower()
    proceed = str(g0.get("can_proceed_to_g1_g11") or "").strip().lower()
    _expect(raj_decision in ALLOWED_G0_REVIEWER_DECISIONS, "g0_clearance.raj_decision must approve or conditionally approve evidence capture.", errors)
    _expect(mira_decision in ALLOWED_G0_REVIEWER_DECISIONS, "g0_clearance.mira_decision must approve or conditionally approve evidence capture.", errors)
    _expect(
        proceed in ALLOWED_G0_PROCEED_VALUES,
        "g0_clearance.can_proceed_to_g1_g11 must approve or conditionally approve evidence capture.",
        errors,
    )
    if proceed in {"approved_with_conditions", "conditional"} or raj_decision in CONDITIONAL_G0_VALUES or mira_decision in CONDITIONAL_G0_VALUES:
        _expect(
            _filled(g0.get("conditions")),
            "g0_clearance.conditions is required when G0 approval is conditional or has followups.",
            errors,
        )
        _expect(
            proceed in {"approved_with_conditions", "conditional"},
            "g0_clearance.can_proceed_to_g1_g11 must preserve conditional approval when reviewer decisions include conditions or followups.",
            errors,
        )


def _validate_target(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    target = _require_mapping(value, "target", errors)
    if not target:
        return None
    required = [
        "environment",
        "backend_url",
        "frontend_url",
        "safe_tenant_identifier",
        "safe_client_identifier",
        "report_definition_id",
        "currency",
        "paid_meta_account_scope",
        "organic_facebook_page_scope",
        "content_ops_workspace_scope",
    ]
    for key in required:
        _expect(_filled(target.get(key)), f"target.{key} is required.", errors)
    _expect(target.get("template_key") == EXPECTED_TEMPLATE_KEY, f"target.template_key must be {EXPECTED_TEMPLATE_KEY}.", errors)
    _expect(
        target.get("report_schema_version") == EXPECTED_REPORT_SCHEMA,
        f"target.report_schema_version must be {EXPECTED_REPORT_SCHEMA}.",
        errors,
    )
    _expect(target.get("timezone") == EXPECTED_TIMEZONE, f"target.timezone must be {EXPECTED_TIMEZONE}.", errors)
    start_date = _parse_date(str(target.get("primary_start_date") or ""), "target.primary_start_date", errors)
    end_date = _parse_date(str(target.get("primary_end_date") or ""), "target.primary_end_date", errors)
    if start_date and end_date:
        _expect(start_date <= end_date, "target.primary_start_date must be on or before primary_end_date.", errors)
    return target


def _validate_comparison(value: Any, errors: list[str]) -> None:
    comparison = _require_mapping(value, "comparison", errors)
    if not comparison:
        return
    for key in ["dashthis_source_comparison_owner", "dashthis_source_evidence_location"]:
        _expect(_filled(comparison.get(key)), f"comparison.{key} is required.", errors)
    _expect(
        comparison.get("tolerances_confirmed") is True,
        "comparison.tolerances_confirmed must be true before G1 can pass.",
        errors,
    )


def _validate_delivery(value: Any, errors: list[str]) -> None:
    delivery = _require_mapping(value, "delivery", errors)
    if not delivery:
        return
    _expect(delivery.get("scheduled_delivery_mode") == "dry_run_only", "delivery.scheduled_delivery_mode must be dry_run_only.", errors)
    _expect(_filled(delivery.get("recipient_assumption")), "delivery.recipient_assumption is required.", errors)
    _expect(delivery.get("dashthis_active") is True, "delivery.dashthis_active must be true.", errors)


def _validate_guardrails(value: Any, errors: list[str]) -> None:
    guardrails = _require_mapping(value, "guardrails", errors)
    if not guardrails:
        return
    _expect(
        guardrails.get("instagram_decision") == "deferred_in_v1",
        "guardrails.instagram_decision must be deferred_in_v1.",
        errors,
    )
    _expect(guardrails.get("stored_aggregate_only") is True, "guardrails.stored_aggregate_only must be true.", errors)
    _expect(
        guardrails.get("no_live_provider_calls_at_render_export_time") is True,
        "guardrails.no_live_provider_calls_at_render_export_time must be true.",
        errors,
    )


def _validate_evidence(
    value: Any,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    evidence = _require_mapping(value, "evidence", errors)
    if not evidence:
        return
    _expect(
        _filled(evidence.get("slb_report_target_intake_output")),
        "evidence.slb_report_target_intake_output is required.",
        errors,
    )
    target_output = _load_target_intake_output(evidence.get("slb_report_target_intake_output"), errors)
    if target_output and target:
        _validate_target_intake_output(target_output, target=target, errors=errors)
    if not _filled(evidence.get("operator_notes")):
        warnings.append("evidence.operator_notes is empty.")


def _load_target_intake_output(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    if not _filled(value):
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        errors.append(f"evidence.slb_report_target_intake_output path does not exist: {_display_path(path)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"evidence.slb_report_target_intake_output is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append("evidence.slb_report_target_intake_output root must be a JSON object.")
        return None
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Sensitive or user-level pattern detected in target intake output: {pattern.pattern}")
    return payload


def _validate_target_intake_output(output: Mapping[str, Any], *, target: Mapping[str, Any], errors: list[str]) -> None:
    _expect(output.get("schema_version") == "slb_target_intake.v1", "target intake output schema_version must be slb_target_intake.v1.", errors)
    _expect(
        output.get("status") == "candidate_ready_for_operator_confirmation",
        "target intake output status must be candidate_ready_for_operator_confirmation.",
        errors,
    )
    report = _require_mapping(output.get("report"), "target intake output.report", errors)
    if report:
        _expect(str(report.get("id") or "") == str(target.get("report_definition_id") or ""), "target intake output report.id must match target.report_definition_id.", errors)
        _expect(report.get("schema_version") == EXPECTED_REPORT_SCHEMA, f"target intake output report.schema_version must be {EXPECTED_REPORT_SCHEMA}.", errors)
        _expect(report.get("template_key") == EXPECTED_TEMPLATE_KEY, f"target intake output report.template_key must be {EXPECTED_TEMPLATE_KEY}.", errors)
    datasets = _require_mapping(output.get("datasets"), "target intake output.datasets", errors)
    if datasets:
        required_present = set(_as_str_list(datasets.get("required_active_v1_present")))
        missing_required = _as_str_list(datasets.get("missing_required_active_v1"))
        _expect(
            {"paid_meta_ads", "organic_facebook_page", "content_ops"} <= required_present,
            "target intake output must include paid_meta_ads, organic_facebook_page, and content_ops.",
            errors,
        )
        _expect(not missing_required, "target intake output must not list missing required active v1 datasets.", errors)
    pages = _require_mapping(output.get("pages"), "target intake output.pages", errors)
    if pages:
        _expect(pages.get("required_slb_pages_present") is True, "target intake output must confirm required SLB pages are present.", errors)
    guardrails = _require_mapping(output.get("guardrails"), "target intake output.guardrails", errors)
    if guardrails:
        _expect(guardrails.get("report_v1") is True, "target intake output guardrails.report_v1 must be true.", errors)
        _expect(guardrails.get("slb_template") is True, "target intake output guardrails.slb_template must be true.", errors)
        _expect(guardrails.get("instagram_deferred") is True, "target intake output guardrails.instagram_deferred must be true.", errors)
        _expect(
            guardrails.get("no_sensitive_patterns_detected") is True,
            "target intake output guardrails.no_sensitive_patterns_detected must be true.",
            errors,
        )
    source_scope = _require_mapping(output.get("source_scope_presence"), "target intake output.source_scope_presence", errors)
    if source_scope:
        for key in ["account_id_present", "page_id_present", "workspace_id_present"]:
            _expect(source_scope.get(key) is True, f"target intake output source_scope_presence.{key} must be true.", errors)
    _validate_target_intake_date_range(output.get("date_range"), target=target, errors=errors)


def _validate_target_intake_date_range(value: Any, *, target: Mapping[str, Any], errors: list[str]) -> None:
    date_range = _require_mapping(value, "target intake output.date_range", errors)
    if not date_range:
        return
    report_filter = date_range.get("report_filter") if isinstance(date_range.get("report_filter"), Mapping) else {}
    if report_filter:
        start_date = str(report_filter.get("start_date") or "")
        end_date = str(report_filter.get("end_date") or "")
        if _filled(start_date):
            _expect(start_date == str(target.get("primary_start_date") or ""), "target intake output report_filter.start_date must match target.primary_start_date.", errors)
        if _filled(end_date):
            _expect(end_date == str(target.get("primary_end_date") or ""), "target intake output report_filter.end_date must match target.primary_end_date.", errors)


def _as_str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _validate_sensitive_patterns(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Sensitive or user-level pattern detected: {pattern.pattern}")


def _require_mapping(value: Any, field: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field} must be an object.")
        return None
    return value


def _filled(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized not in PLACEHOLDER_VALUES


def _parse_date(value: str, field: str, errors: list[str]) -> date | None:
    if not _filled(value):
        errors.append(f"{field} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be YYYY-MM-DD.")
        return None


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
