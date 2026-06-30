#!/usr/bin/env python3
"""Validate SLB G11 hardening-window evidence before G12 recommendation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g11_hardening_window.v1"
G10_SCHEMA_VERSION = "slb_g10_adversarial_review.v1"
FINAL_EVIDENCE_VALIDATION_SCHEMA = "slb_evidence_validation.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
REQUIRED_EXPORT_FORMATS = ["csv", "pdf", "png"]
REQUIRED_CHECKPOINTS = ["start", "midpoint_1", "end"]
CHECKPOINT_PASS_STATUSES = {"pass", "passed", "ok", "ready", "success", "rendered"}
FINAL_EVIDENCE_READY_STATUSES = {"pass", "warning"}
DRY_RUN_PASS_STATUSES = CHECKPOINT_PASS_STATUSES | {
    "dry_run_passed",
    "dry_run_rendered",
}
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
EVIDENCE_FILE_SUFFIXES = {
    "start_checkpoint": {".json", ".md", ".txt"},
    "midpoint_1_checkpoint": {".json", ".md", ".txt"},
    "midpoint_2_checkpoint": {".json", ".md", ".txt"},
    "end_checkpoint": {".json", ".md", ".txt"},
    "final_evidence_validation": {".json", ".md", ".txt", ".log"},
    "final_redaction_scan": {".md", ".txt", ".log"},
    "export_snapshot_summary": {".json", ".md"},
}
TEXT_EVIDENCE_SUFFIXES = {".json", ".md", ".txt", ".log"}
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
        description="Validate a filled SLB G11 hardening-window JSON."
    )
    parser.add_argument(
        "--window-file", required=True, help="Path to filled G11 hardening-window JSON."
    )
    parser.add_argument(
        "--g10-review-file",
        help="Optional filled G10 adversarial review JSON. When provided, target fields must match.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    window_path = _resolve_path(args.window_file)
    review_path = _resolve_path(args.g10_review_file) if args.g10_review_file else None

    errors: list[str] = []
    warnings: list[str] = []
    window_payload = _load_json(window_path, "Window file", errors)
    review_payload = (
        _load_json(review_path, "G10 review file", errors) if review_path else None
    )
    if window_payload:
        _validate_window(
            window_payload,
            review_payload=review_payload,
            errors=errors,
            warnings=warnings,
        )

    result = {
        "schema_version": "slb_g11_hardening_window_validation.v1",
        "window_file": _display_path(window_path),
        "g10_review_file": _display_path(review_path) if review_path else None,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G11 hardening window valid: {str(result['valid']).lower()}")
        print(f"Window file: {result['window_file']}")
        if result["g10_review_file"]:
            print(f"G10 review file: {result['g10_review_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_window(
    payload: Mapping[str, Any],
    *,
    review_payload: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(
        payload.get("schema_version") == REQUIRED_SCHEMA_VERSION,
        "Unexpected schema_version.",
        errors,
    )
    _expect(
        str(payload.get("status") or "") == "ready_for_g12_recommendation",
        "status must be ready_for_g12_recommendation.",
        errors,
    )
    references = _validate_references(payload.get("references"), errors)
    target = _validate_target(payload.get("target"), errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    window_info = _validate_window_metadata(payload.get("window"), errors)
    _validate_checkpoints(
        payload.get("checkpoints"), window_info=window_info, errors=errors
    )
    _validate_evidence_files(
        payload.get("evidence_files"),
        window_info=window_info,
        target=target,
        errors=errors,
    )
    _validate_exports(payload.get("export_reproducibility"), errors)
    _validate_final_checks(payload.get("final_checks"), errors)
    _validate_reviewer_route(payload.get("reviewer_route"), errors)
    if review_payload and target:
        _validate_g10_match(target, references, review_payload, errors, warnings)
    _validate_sensitive_patterns(payload, errors)


def _validate_references(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    references = _require_mapping(value, "references", errors)
    if not references:
        return None
    for key in [
        "g1_intake_file",
        "g2_g9_run_file",
        "g10_review_file",
        "window_id",
        "operator",
    ]:
        _expect(_filled(references.get(key)), f"references.{key} is required.", errors)
    for key in [
        "g1_intake_valid",
        "g2_g9_run_valid",
        "g10_review_valid",
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
        "dashthis_active_during_window",
        "stored_aggregate_only",
        "no_live_provider_calls_at_render_export_time",
    ]:
        _expect(guardrails.get(key) is True, f"guardrails.{key} must be true.", errors)


def _validate_window_metadata(value: Any, errors: list[str]) -> dict[str, Any]:
    window = _require_mapping(value, "window", errors)
    if not window:
        return {}
    length = window.get("length_hours")
    _expect(isinstance(length, int), "window.length_hours must be an integer.", errors)
    if isinstance(length, int):
        _expect(
            24 <= length <= 48, "window.length_hours must be between 24 and 48.", errors
        )
    start_timestamp = _parse_datetime(
        str(window.get("start_timestamp") or ""), "window.start_timestamp", errors
    )
    end_timestamp = _parse_datetime(
        str(window.get("end_timestamp") or ""), "window.end_timestamp", errors
    )
    if start_timestamp and end_timestamp:
        _expect(
            start_timestamp <= end_timestamp,
            "window.start_timestamp must be on or before end_timestamp.",
            errors,
        )
        if isinstance(length, int):
            actual_hours = (end_timestamp - start_timestamp).total_seconds() / 3600
            _expect(
                actual_hours >= length,
                "window.end_timestamp must be at least window.length_hours after start_timestamp.",
                errors,
            )
    _expect(
        window.get("reset_occurred") is False,
        "window.reset_occurred must be false.",
        errors,
    )
    _expect(
        not _filled(window.get("reset_reason")),
        "window.reset_reason must be empty when no reset occurred.",
        errors,
    )
    _expect(
        str(window.get("evidence_validation_final_status") or "").strip().lower()
        in CHECKPOINT_PASS_STATUSES,
        "window.evidence_validation_final_status must be pass.",
        errors,
    )
    _expect(
        window.get("redaction_scan_passed") is True,
        "window.redaction_scan_passed must be true.",
        errors,
    )
    return {
        "length_hours": length if isinstance(length, int) else None,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
    }


def _validate_checkpoints(
    value: Any, *, window_info: Mapping[str, Any], errors: list[str]
) -> None:
    checkpoints = _require_mapping(value, "checkpoints", errors)
    if not checkpoints:
        return
    length_hours = (
        window_info.get("length_hours") if isinstance(window_info, Mapping) else None
    )
    required = list(REQUIRED_CHECKPOINTS)
    if length_hours and length_hours > 24:
        required.insert(2, "midpoint_2")
    previous_timestamp = (
        window_info.get("start_timestamp") if isinstance(window_info, Mapping) else None
    )
    for checkpoint in required:
        row = _require_mapping(
            checkpoints.get(checkpoint), f"checkpoints.{checkpoint}", errors
        )
        if row:
            current_timestamp = _validate_checkpoint_row(row, checkpoint, errors)
            if current_timestamp and previous_timestamp:
                _expect(
                    current_timestamp >= previous_timestamp,
                    f"checkpoints.{checkpoint}.timestamp must be on or after the previous checkpoint.",
                    errors,
                )
            if current_timestamp:
                previous_timestamp = current_timestamp
    end_timestamp = (
        window_info.get("end_timestamp") if isinstance(window_info, Mapping) else None
    )
    if previous_timestamp and end_timestamp:
        _expect(
            previous_timestamp <= end_timestamp,
            "Final checkpoint timestamp must be on or before window.end_timestamp.",
            errors,
        )


def _validate_checkpoint_row(
    row: Mapping[str, Any], checkpoint: str, errors: list[str]
) -> datetime | None:
    timestamp = _parse_datetime(
        str(row.get("timestamp") or ""), f"checkpoints.{checkpoint}.timestamp", errors
    )
    _expect(
        str(row.get("preview_status") or "").strip().lower()
        in CHECKPOINT_PASS_STATUSES,
        f"checkpoints.{checkpoint}.preview_status must be pass.",
        errors,
    )
    _expect(
        str(row.get("diagnostics_status") or "").strip().lower()
        in CHECKPOINT_PASS_STATUSES,
        f"checkpoints.{checkpoint}.diagnostics_status must be pass.",
        errors,
    )
    _expect(
        str(row.get("export_status") or "").strip().lower() in CHECKPOINT_PASS_STATUSES,
        f"checkpoints.{checkpoint}.export_status must be pass.",
        errors,
    )
    _expect(
        str(row.get("scheduled_dry_run_status") or "").strip().lower()
        in DRY_RUN_PASS_STATUSES,
        f"checkpoints.{checkpoint}.scheduled_dry_run_status must be pass.",
        errors,
    )
    _expect(
        str(row.get("evidence_validation_status") or "").strip().lower()
        in CHECKPOINT_PASS_STATUSES,
        f"checkpoints.{checkpoint}.evidence_validation_status must be pass.",
        errors,
    )
    _expect(
        row.get("redaction_scan_passed") is True,
        f"checkpoints.{checkpoint}.redaction_scan_passed must be true.",
        errors,
    )
    _expect(
        _filled(row.get("reviewer_note")),
        f"checkpoints.{checkpoint}.reviewer_note is required.",
        errors,
    )
    return timestamp


def _validate_evidence_files(
    value: Any,
    *,
    window_info: Mapping[str, Any],
    target: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    evidence_files = _require_mapping(value, "evidence_files", errors)
    if not evidence_files:
        return
    length_hours = (
        window_info.get("length_hours") if isinstance(window_info, Mapping) else None
    )
    required = [
        "start_checkpoint",
        "midpoint_1_checkpoint",
        "end_checkpoint",
        "final_evidence_validation",
        "final_redaction_scan",
        "export_snapshot_summary",
    ]
    if length_hours and length_hours > 24:
        required.insert(2, "midpoint_2_checkpoint")
    for key in required:
        resolved = _validate_evidence_file_path(key, evidence_files.get(key), errors)
        if key == "final_evidence_validation" and resolved:
            _validate_final_evidence_validation(resolved, target=target, errors=errors)
    optional = evidence_files.get("midpoint_2_checkpoint")
    if (
        not (length_hours and length_hours > 24)
        and _filled(optional)
        and str(optional).strip().lower() != "not_required_for_24h"
    ):
        _validate_evidence_file_path("midpoint_2_checkpoint", optional, errors)


def _validate_evidence_file_path(
    key: str, value: Any, errors: list[str]
) -> Path | None:
    if not _filled(value):
        errors.append(f"evidence_files.{key} is required.")
        return None
    raw_path = str(value).strip()
    if raw_path.lower() == "not_required_for_24h":
        errors.append(f"evidence_files.{key} cannot be not_required_for_24h.")
        return None
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        errors.append(
            f"evidence_files.{key} must be a repo-relative path under {EVIDENCE_ROOT}."
        )
        return None
    if path.parts[: len(EVIDENCE_ROOT.parts)] != EVIDENCE_ROOT.parts:
        errors.append(f"evidence_files.{key} must be under {EVIDENCE_ROOT}.")
        return None
    allowed_suffixes = EVIDENCE_FILE_SUFFIXES.get(key)
    suffix = path.suffix.lower()
    if allowed_suffixes and suffix not in allowed_suffixes:
        errors.append(
            f"evidence_files.{key} must use one of: {', '.join(sorted(allowed_suffixes))}."
        )
    resolved = REPO_ROOT / path
    if not resolved.exists():
        errors.append(f"evidence_files.{key} does not exist: {_display_path(resolved)}")
        return None
    if not resolved.is_file():
        errors.append(f"evidence_files.{key} must be a file: {_display_path(resolved)}")
        return None
    if resolved.stat().st_size <= 0:
        errors.append(
            f"evidence_files.{key} must be non-empty: {_display_path(resolved)}"
        )
        return None
    if suffix in TEXT_EVIDENCE_SUFFIXES:
        _validate_text_evidence_file(key, resolved, suffix, errors)
    return resolved


def _validate_final_evidence_validation(
    path: Path,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    field = "evidence_files.final_evidence_validation"
    if path.suffix.lower() != ".json":
        errors.append(
            f"{field} must point to {FINAL_EVIDENCE_VALIDATION_SCHEMA} JSON from slb_report_evidence_validate."
        )
        return
    payload = _load_json(path, field, errors)
    if not payload:
        return
    _expect(
        payload.get("schema_version") == FINAL_EVIDENCE_VALIDATION_SCHEMA,
        f"{field}.schema_version must be {FINAL_EVIDENCE_VALIDATION_SCHEMA}.",
        errors,
    )
    _expect(
        str(payload.get("readiness_status") or "") in FINAL_EVIDENCE_READY_STATUSES,
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

    _validate_final_evidence_identity(
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


def _validate_final_evidence_identity(
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
    key: str, path: Path, suffix: str, errors: list[str]
) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"evidence_files.{key} must be UTF-8 text: {_display_path(path)}")
        return
    if suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            errors.append(f"evidence_files.{key} is not valid JSON: {exc}")
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            errors.append(
                f"Sensitive or user-level pattern detected in evidence_files.{key}: {pattern.pattern}"
            )


def _validate_exports(value: Any, errors: list[str]) -> None:
    exports = _require_mapping(value, "export_reproducibility", errors)
    if not exports:
        return
    _expect(
        list(exports) == REQUIRED_EXPORT_FORMATS,
        "export_reproducibility must contain csv, pdf, and png in order.",
        errors,
    )
    for export_format in REQUIRED_EXPORT_FORMATS:
        row = _require_mapping(
            exports.get(export_format),
            f"export_reproducibility.{export_format}",
            errors,
        )
        if not row:
            continue
        _expect(
            _filled(row.get("job_id")),
            f"export_reproducibility.{export_format}.job_id is required.",
            errors,
        )
        byte_count = row.get("byte_count")
        _expect(
            isinstance(byte_count, int) and byte_count > 0,
            f"export_reproducibility.{export_format}.byte_count must be greater than zero.",
            errors,
        )
        _expect(
            _filled(row.get("preview_hash")),
            f"export_reproducibility.{export_format}.preview_hash is required.",
            errors,
        )
        _expect(
            str(row.get("preview_hash") or "")
            == str(row.get("snapshot_preview_hash") or ""),
            f"export_reproducibility.{export_format}.preview_hash must match snapshot_preview_hash.",
            errors,
        )


def _validate_final_checks(value: Any, errors: list[str]) -> None:
    checks = _require_mapping(value, "final_checks", errors)
    if not checks:
        return
    for key in [
        "no_reset_conditions",
        "no_unresolved_blocker_or_high",
        "dashthis_still_active",
        "rollback_path_available",
        "monitoring_owner_named",
        "support_owner_named",
        "raj_mira_acceptance",
    ]:
        _expect(checks.get(key) is True, f"final_checks.{key} must be true.", errors)


def _validate_reviewer_route(value: Any, errors: list[str]) -> None:
    route = _require_mapping(value, "reviewer_route", errors)
    if not route:
        return
    for key in ["raj", "mira", "omar", "hannah"]:
        _expect(_filled(route.get(key)), f"reviewer_route.{key} is required.", errors)


def _validate_g10_match(
    target: Mapping[str, Any],
    references: Mapping[str, Any] | None,
    review_payload: Mapping[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(
        review_payload.get("schema_version") == G10_SCHEMA_VERSION,
        "G10 review schema_version is invalid.",
        errors,
    )
    _expect(
        str(review_payload.get("status") or "") == "ready_for_g11_hardening",
        "G10 review status must be ready_for_g11_hardening.",
        errors,
    )
    review_target = _require_mapping(
        review_payload.get("target"), "G10 review target", errors
    )
    review_references = _require_mapping(
        review_payload.get("references"), "G10 review references", errors
    )
    if review_references:
        for key in ["g1_intake_file", "g2_g9_run_file"]:
            _expect(
                _filled(review_references.get(key)),
                f"G10 review references.{key} is required.",
                errors,
            )
        for key in ["g1_intake_valid", "g2_g9_run_valid"]:
            _expect(
                review_references.get(key) is True,
                f"G10 review references.{key} must be true.",
                errors,
            )
        if references:
            for key in ["g1_intake_file", "g2_g9_run_file"]:
                _expect(
                    str(references.get(key) or "")
                    == str(review_references.get(key) or ""),
                    f"references.{key} must match G10 review references.{key}.",
                    errors,
                )
    if not review_target:
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
            str(target.get(key) or "") == str(review_target.get(key) or ""),
            f"target.{key} must match G10 review target.{key}.",
            errors,
        )
    final_checks = review_payload.get("final_checks")
    if (
        isinstance(final_checks, Mapping)
        and final_checks.get("raj_mira_acceptance") is not True
    ):
        warnings.append("G10 review final_checks.raj_mira_acceptance is not true.")


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


def _parse_datetime(value: str, field: str, errors: list[str]) -> datetime | None:
    if not _filled(value):
        errors.append(f"{field} is required.")
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{field} must be an ISO-8601 timestamp.")
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
