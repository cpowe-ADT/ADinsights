#!/usr/bin/env python3
"""Validate that filled SLB G0 and G1 evidence agree before fixed-target proof starts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
G0_SCHEMA_VERSION = "slb_g0_raj_mira_review.v1"
G1_SCHEMA_VERSION = "slb_g1_runtime_target_intake.v1"
G0_APPROVED_STATUSES = {"approved_for_g1", "approved_with_followups"}
G0_PROCEED_VALUES = {"proceed_to_g1", "proceed_to_g1_with_followups"}
G1_APPROVED_VALUES = {"yes", "approved", "approved_with_conditions", "conditional"}
G1_CLEAN_APPROVAL_VALUES = {"approved"}
G1_CONDITIONAL_APPROVAL_VALUES = {"approved_with_followups", "approved_with_conditions", "conditional"}
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
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
    parser = argparse.ArgumentParser(description="Validate filled SLB G0 and G1 handoff JSON artifacts together.")
    parser.add_argument("--g0-review-file", required=True, help="Path to filled G0 Raj/Mira review decision JSON.")
    parser.add_argument("--g1-intake-file", required=True, help="Path to filled G1 runtime target intake JSON.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    g0_path = _resolve_path(args.g0_review_file)
    g1_path = _resolve_path(args.g1_intake_file)

    errors: list[str] = []
    warnings: list[str] = []
    g0_payload = _load_json(g0_path, "G0 review file", errors)
    g1_payload = _load_json(g1_path, "G1 intake file", errors)
    if g0_payload and g1_payload:
        _validate_handoff(g0_payload, g1_payload, errors=errors, warnings=warnings)

    result = {
        "schema_version": "slb_g0_g1_handoff_validation.v1",
        "g0_review_file": _display_path(g0_path),
        "g1_intake_file": _display_path(g1_path),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G0/G1 handoff valid: {str(result['valid']).lower()}")
        print(f"G0 review file: {result['g0_review_file']}")
        print(f"G1 intake file: {result['g1_intake_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_handoff(
    g0_payload: Mapping[str, Any],
    g1_payload: Mapping[str, Any],
    *,
    errors: list[str],
    warnings: list[str],
) -> None:
    _validate_g0_ready(g0_payload, errors)
    _validate_g1_ready(g1_payload, errors, warnings)
    _validate_approval_consistency(g0_payload, g1_payload, errors, warnings)
    _validate_shared_guardrails(g0_payload, g1_payload, errors)
    _validate_sensitive_patterns({"g0": g0_payload, "g1": g1_payload}, errors)


def _validate_g0_ready(payload: Mapping[str, Any], errors: list[str]) -> None:
    _expect(payload.get("schema_version") == G0_SCHEMA_VERSION, "G0 schema_version is invalid.", errors)
    status = str(payload.get("status") or "").strip()
    _expect(status in G0_APPROVED_STATUSES, "G0 status must approve G1 evidence capture.", errors)
    decision = _require_mapping(payload.get("decision"), "G0 decision", errors)
    if not decision:
        return
    _expect(
        str(decision.get("g1_g11_evidence_capture") or "").strip() in G0_PROCEED_VALUES,
        "G0 decision.g1_g11_evidence_capture must proceed to G1.",
        errors,
    )
    _expect(decision.get("dashthis_cancellation") == "no_go", "G0 decision.dashthis_cancellation must remain no_go.", errors)
    for key in ["scope_classification", "architecture_classification", "reason"]:
        _expect(_filled(decision.get(key)), f"G0 decision.{key} is required.", errors)
    reviewers = _require_mapping(payload.get("reviewers"), "G0 reviewers", errors)
    if reviewers:
        for reviewer in ["raj", "mira"]:
            row = _require_mapping(reviewers.get(reviewer), f"G0 reviewers.{reviewer}", errors)
            if row:
                _expect(str(row.get("decision") or "").strip() in G0_APPROVED_STATUSES, f"G0 reviewers.{reviewer}.decision must approve G1.", errors)


def _validate_g1_ready(payload: Mapping[str, Any], errors: list[str], warnings: list[str]) -> None:
    _expect(payload.get("schema_version") == G1_SCHEMA_VERSION, "G1 schema_version is invalid.", errors)
    _expect(str(payload.get("status") or "") == "candidate_ready_for_review", "G1 status must be candidate_ready_for_review.", errors)
    g0_clearance = _require_mapping(payload.get("g0_clearance"), "G1 g0_clearance", errors)
    if g0_clearance:
        for key in ["raj_decision", "mira_decision", "can_proceed_to_g1_g11"]:
            _expect(_filled(g0_clearance.get(key)), f"G1 g0_clearance.{key} is required.", errors)
        _expect(
            str(g0_clearance.get("can_proceed_to_g1_g11") or "").strip().lower() in G1_APPROVED_VALUES,
            "G1 g0_clearance.can_proceed_to_g1_g11 must approve evidence capture.",
            errors,
        )
        if not _filled(g0_clearance.get("conditions")):
            warnings.append("G1 g0_clearance.conditions is empty.")
    target = _require_mapping(payload.get("target"), "G1 target", errors)
    if target:
        _expect(target.get("template_key") == EXPECTED_TEMPLATE_KEY, f"G1 target.template_key must be {EXPECTED_TEMPLATE_KEY}.", errors)
        _expect(target.get("report_schema_version") == EXPECTED_REPORT_SCHEMA, f"G1 target.report_schema_version must be {EXPECTED_REPORT_SCHEMA}.", errors)
        _expect(target.get("timezone") == EXPECTED_TIMEZONE, f"G1 target.timezone must be {EXPECTED_TIMEZONE}.", errors)
        for key in [
            "environment",
            "backend_url",
            "frontend_url",
            "safe_tenant_identifier",
            "safe_client_identifier",
            "report_definition_id",
            "primary_start_date",
            "primary_end_date",
            "currency",
            "paid_meta_account_scope",
            "organic_facebook_page_scope",
            "content_ops_workspace_scope",
        ]:
            _expect(_filled(target.get(key)), f"G1 target.{key} is required.", errors)
        start_date = _parse_date(str(target.get("primary_start_date") or ""), "G1 target.primary_start_date", errors)
        end_date = _parse_date(str(target.get("primary_end_date") or ""), "G1 target.primary_end_date", errors)
        if start_date and end_date:
            _expect(start_date <= end_date, "G1 target.primary_start_date must be on or before primary_end_date.", errors)
    comparison = _require_mapping(payload.get("comparison"), "G1 comparison", errors)
    if comparison:
        for key in ["dashthis_source_comparison_owner", "dashthis_source_evidence_location"]:
            _expect(_filled(comparison.get(key)), f"G1 comparison.{key} is required.", errors)
        _expect(comparison.get("tolerances_confirmed") is True, "G1 comparison.tolerances_confirmed must be true.", errors)
    delivery = _require_mapping(payload.get("delivery"), "G1 delivery", errors)
    if delivery:
        _expect(delivery.get("scheduled_delivery_mode") == "dry_run_only", "G1 delivery.scheduled_delivery_mode must be dry_run_only.", errors)
        _expect(delivery.get("dashthis_active") is True, "G1 delivery.dashthis_active must be true.", errors)
    evidence = _require_mapping(payload.get("evidence"), "G1 evidence", errors)
    if evidence:
        _expect(_filled(evidence.get("slb_report_target_intake_output")), "G1 evidence.slb_report_target_intake_output is required.", errors)


def _validate_approval_consistency(
    g0_payload: Mapping[str, Any],
    g1_payload: Mapping[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    g0_status = str(g0_payload.get("status") or "").strip()
    g0_decision = g0_payload.get("decision") if isinstance(g0_payload.get("decision"), Mapping) else {}
    evidence_capture = str(g0_decision.get("g1_g11_evidence_capture") or "").strip()
    g0_reviewers = g0_payload.get("reviewers") if isinstance(g0_payload.get("reviewers"), Mapping) else {}
    g1_clearance = g1_payload.get("g0_clearance") if isinstance(g1_payload.get("g0_clearance"), Mapping) else {}
    g1_proceed = str(g1_clearance.get("can_proceed_to_g1_g11") or "").strip().lower()
    _expect(
        (g0_status, evidence_capture, g1_proceed)
        in {
            ("approved_for_g1", "proceed_to_g1", "approved"),
            ("approved_for_g1", "proceed_to_g1", "yes"),
            ("approved_with_followups", "proceed_to_g1_with_followups", "approved_with_conditions"),
            ("approved_with_followups", "proceed_to_g1_with_followups", "conditional"),
        },
        "G0 approval path and G1 g0_clearance.can_proceed_to_g1_g11 are inconsistent.",
        errors,
    )
    for reviewer in ["raj", "mira"]:
        g0_reviewer = g0_reviewers.get(reviewer) if isinstance(g0_reviewers.get(reviewer), Mapping) else {}
        g0_reviewer_decision = str(g0_reviewer.get("decision") or "").strip()
        g1_reviewer_decision = str(g1_clearance.get(f"{reviewer}_decision") or "").strip().lower()
        if g0_reviewer_decision == "approved_for_g1":
            _expect(
                g1_reviewer_decision in G1_CLEAN_APPROVAL_VALUES,
                f"G1 g0_clearance.{reviewer}_decision must preserve clean G0 approval.",
                errors,
            )
        elif g0_reviewer_decision == "approved_with_followups":
            _expect(
                g1_reviewer_decision in G1_CONDITIONAL_APPROVAL_VALUES,
                f"G1 g0_clearance.{reviewer}_decision must preserve G0 followup approval.",
                errors,
            )
    required_followups = g0_payload.get("required_followups")
    if g0_status == "approved_with_followups":
        _expect(isinstance(required_followups, list) and bool(required_followups), "G0 approved_with_followups requires required_followups.", errors)
        _expect(_filled(g1_clearance.get("conditions")), "G1 g0_clearance.conditions must summarize G0 followups.", errors)
    elif _filled(g1_clearance.get("conditions")) and str(g1_clearance.get("conditions")).strip().lower() not in {"none", "no conditions"}:
        warnings.append("G1 g0_clearance.conditions is filled even though G0 has no followups.")


def _validate_shared_guardrails(g0_payload: Mapping[str, Any], g1_payload: Mapping[str, Any], errors: list[str]) -> None:
    g0_guardrails = _require_mapping(g0_payload.get("guardrails"), "G0 guardrails", errors)
    g1_guardrails = _require_mapping(g1_payload.get("guardrails"), "G1 guardrails", errors)
    if g0_guardrails:
        for key in [
            "instagram_deferred",
            "stored_aggregate_only",
            "no_live_provider_calls_at_render_export_time",
            "dashthis_active_until_g12",
        ]:
            _expect(g0_guardrails.get(key) is True, f"G0 guardrails.{key} must be true.", errors)
    if g1_guardrails:
        _expect(g1_guardrails.get("instagram_decision") == "deferred_in_v1", "G1 guardrails.instagram_decision must be deferred_in_v1.", errors)
        _expect(g1_guardrails.get("stored_aggregate_only") is True, "G1 guardrails.stored_aggregate_only must be true.", errors)
        _expect(
            g1_guardrails.get("no_live_provider_calls_at_render_export_time") is True,
            "G1 guardrails.no_live_provider_calls_at_render_export_time must be true.",
            errors,
        )


def _validate_sensitive_patterns(payload: Mapping[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Sensitive or user-level pattern detected: {pattern.pattern}")


def _load_json(path: Path | None, label: str, errors: list[str]) -> Mapping[str, Any] | None:
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
