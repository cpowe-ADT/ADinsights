#!/usr/bin/env python3
"""Validate a fixed-range SLB G2-G9 evidence run before G10 starts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g2_g9_evidence_run.v1"
G1_SCHEMA_VERSION = "slb_g1_runtime_target_intake.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
REQUIRED_DATASETS = ["paid_meta_ads", "organic_facebook_page", "content_ops"]
REQUIRED_SECTIONS = [
    "cover",
    "executive_summary",
    "paid_meta_ads",
    "organic_facebook_page",
    "top_posts",
    "content_ops",
    "recommendations",
    "appendix_data_notes",
]
REQUIRED_EXPORT_FORMATS = ["csv", "pdf", "png"]
PASS_STATUSES = {"pass", "passed", "ok", "green", "success"}
ALLOWED_PREFLIGHT_BLOCKS = {"gate_block", "blocked_architecture_scope", "esc_arch_risk"}
PLACEHOLDER_VALUES = {"", "pending", "tbd", "todo", "n/a", "unknown", "none", "<pending>"}
EVIDENCE_ROOT = Path("docs/project/evidence/dashthis-replacement")
EVIDENCE_FILE_SUFFIXES = {
    "preview": {".json"},
    "diagnostics": {".json"},
    "history_probe": {".json"},
    "evidence_bundle": {".json"},
    "evidence_validation": {".json"},
    "parity_output": {".json", ".md", ".txt"},
    "parity_comparison": {".json", ".md", ".csv"},
    "report_ui_screenshot": {".png", ".jpg", ".jpeg"},
    "dashboard_ui_screenshot": {".png", ".jpg", ".jpeg"},
    "scheduled_dry_run": {".json"},
    "redaction_scan": {".md", ".txt", ".log"},
    "gate_output": {".json", ".md", ".txt", ".log"},
}
OPTIONAL_NOT_IN_SCOPE_EVIDENCE_FILES = {"dashboard_ui_screenshot"}
TEXT_EVIDENCE_SUFFIXES = {".json", ".md", ".txt", ".log", ".csv"}
BLOCKING_COVERAGE_STATES = {
    "missing_history",
    "not_previously_synced",
    "permission_missing",
    "unsupported_metric",
    "unsupported",
    "blocked",
}
REVIEW_NOTE_COVERAGE_STATES = {"stale", "partial", "source_disconnected", "source_disconnected_with_history"}
FULL_RANGE_COVERAGE_STATES = {"fresh", "stale", "source_disconnected_with_history"}
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
    parser = argparse.ArgumentParser(description="Validate a filled SLB G2-G9 evidence run JSON.")
    parser.add_argument("--run-file", required=True, help="Path to the filled G2-G9 evidence run JSON.")
    parser.add_argument(
        "--intake-file",
        help="Optional filled G1 runtime target intake JSON. When provided, target fields must match.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    run_path = _resolve_path(args.run_file)
    intake_path = _resolve_path(args.intake_file) if args.intake_file else None

    errors: list[str] = []
    warnings: list[str] = []
    run_payload = _load_json(run_path, "Run file", errors)
    intake_payload = _load_json(intake_path, "G1 intake file", errors) if intake_path else None
    if run_payload:
        _validate_run(run_payload, intake_payload=intake_payload, errors=errors, warnings=warnings)

    result = {
        "schema_version": "slb_g2_g9_evidence_run_validation.v1",
        "run_file": _display_path(run_path),
        "intake_file": _display_path(intake_path) if intake_path else None,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G2-G9 evidence run valid: {str(result['valid']).lower()}")
        print(f"Run file: {result['run_file']}")
        if result["intake_file"]:
            print(f"G1 intake file: {result['intake_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_run(
    payload: Mapping[str, Any],
    *,
    intake_payload: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(payload.get("schema_version") == REQUIRED_SCHEMA_VERSION, "Unexpected schema_version.", errors)
    _expect(str(payload.get("status") or "") == "ready_for_g10_review", "status must be ready_for_g10_review.", errors)
    _validate_references(payload.get("references"), errors)
    target = _validate_target(payload.get("target"), errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    _validate_evidence_files(payload.get("evidence_files"), errors)
    _validate_offline_evidence_validation(payload.get("evidence_files"), target=target, errors=errors)
    _validate_coverage(payload.get("coverage"), target=target, errors=errors, warnings=warnings)
    _validate_rendering(payload.get("rendering"), errors)
    _validate_exports(payload.get("exports"), errors)
    _validate_parity(payload.get("parity"), errors)
    _validate_delivery(payload.get("delivery"), errors)
    _validate_safety(payload.get("safety"), errors)
    _validate_gates(payload.get("gates"), errors)
    _validate_reviewer_route(payload.get("reviewer_route"), errors)
    if intake_payload and target:
        _validate_intake_match(target, intake_payload, errors)
    _validate_sensitive_patterns(payload, errors)


def _validate_references(value: Any, errors: list[str]) -> None:
    references = _require_mapping(value, "references", errors)
    if not references:
        return
    for key in ["g1_intake_file", "evidence_run_id", "run_timestamp", "operator"]:
        _expect(_filled(references.get(key)), f"references.{key} is required.", errors)
    _expect(references.get("g0_can_proceed") is True, "references.g0_can_proceed must be true.", errors)


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
        "primary_start_date",
        "primary_end_date",
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
    start = _parse_date(str(target.get("primary_start_date") or ""), "target.primary_start_date", errors)
    end = _parse_date(str(target.get("primary_end_date") or ""), "target.primary_end_date", errors)
    if start and end:
        _expect(start <= end, "target.primary_start_date must be on or before primary_end_date.", errors)
    return target


def _validate_guardrails(value: Any, errors: list[str]) -> None:
    guardrails = _require_mapping(value, "guardrails", errors)
    if not guardrails:
        return
    expected_true = [
        "instagram_deferred",
        "dashthis_active",
        "stored_aggregate_only",
        "no_live_provider_calls_at_render_export_time",
    ]
    for key in expected_true:
        _expect(guardrails.get(key) is True, f"guardrails.{key} must be true.", errors)


def _validate_evidence_files(value: Any, errors: list[str]) -> None:
    evidence_files = _require_mapping(value, "evidence_files", errors)
    if not evidence_files:
        return
    required = [
        "preview",
        "diagnostics",
        "history_probe",
        "evidence_bundle",
        "evidence_validation",
        "parity_output",
        "parity_comparison",
        "report_ui_screenshot",
        "scheduled_dry_run",
        "redaction_scan",
        "gate_output",
    ]
    for key in required:
        _validate_evidence_file_path(key, evidence_files.get(key), errors)
    optional = evidence_files.get("dashboard_ui_screenshot")
    if _filled(optional) and str(optional).strip().lower() != "not_in_scope":
        _validate_evidence_file_path("dashboard_ui_screenshot", optional, errors)


def _validate_evidence_file_path(key: str, value: Any, errors: list[str]) -> None:
    if not _filled(value):
        _expect(key in OPTIONAL_NOT_IN_SCOPE_EVIDENCE_FILES, f"evidence_files.{key} is required.", errors)
        return
    raw_path = str(value).strip()
    if raw_path.lower() == "not_in_scope":
        _expect(
            key in OPTIONAL_NOT_IN_SCOPE_EVIDENCE_FILES,
            f"evidence_files.{key} cannot be not_in_scope.",
            errors,
        )
        return
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"evidence_files.{key} must be a repo-relative path under {EVIDENCE_ROOT}.")
        return
    if path.parts[: len(EVIDENCE_ROOT.parts)] != EVIDENCE_ROOT.parts:
        errors.append(f"evidence_files.{key} must be under {EVIDENCE_ROOT}.")
        return
    allowed_suffixes = EVIDENCE_FILE_SUFFIXES.get(key)
    suffix = path.suffix.lower()
    if allowed_suffixes and suffix not in allowed_suffixes:
        errors.append(f"evidence_files.{key} must use one of: {', '.join(sorted(allowed_suffixes))}.")
    resolved = REPO_ROOT / path
    if not resolved.exists():
        errors.append(f"evidence_files.{key} does not exist: {_display_path(resolved)}")
        return
    if not resolved.is_file():
        errors.append(f"evidence_files.{key} must be a file: {_display_path(resolved)}")
        return
    if resolved.stat().st_size <= 0:
        errors.append(f"evidence_files.{key} must be non-empty: {_display_path(resolved)}")
        return
    if suffix in TEXT_EVIDENCE_SUFFIXES:
        _validate_text_evidence_file(key, resolved, suffix, errors)


def _validate_offline_evidence_validation(
    value: Any,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    evidence_files = _require_mapping(value, "evidence_files", errors)
    if not evidence_files:
        return
    raw_path = str(evidence_files.get("evidence_validation") or "").strip()
    if not _filled(raw_path):
        return
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return
    resolved = REPO_ROOT / path
    if not resolved.exists() or not resolved.is_file() or resolved.suffix.lower() != ".json":
        return
    payload = _load_json(resolved, "Evidence validation file", errors)
    if not payload:
        return
    _expect(
        payload.get("schema_version") == "slb_evidence_validation.v1",
        "evidence_files.evidence_validation schema_version must be slb_evidence_validation.v1.",
        errors,
    )
    _expect(
        payload.get("readiness_status") == "pass",
        "evidence_files.evidence_validation readiness_status must be pass.",
        errors,
    )
    _expect(
        int(payload.get("blocker_count") or 0) == 0,
        "evidence_files.evidence_validation blocker_count must be zero.",
        errors,
    )
    if target:
        _validate_offline_evidence_identity(payload.get("evidence"), target=target, errors=errors)


def _validate_offline_evidence_identity(
    value: Any,
    *,
    target: Mapping[str, Any],
    errors: list[str],
) -> None:
    evidence = _require_mapping(value, "evidence_files.evidence_validation.evidence", errors)
    if not evidence:
        return
    report = _require_mapping(evidence.get("report"), "evidence_files.evidence_validation.evidence.report", errors)
    date_range = _require_mapping(evidence.get("date_range"), "evidence_files.evidence_validation.evidence.date_range", errors)
    if report:
        _expect(
            str(report.get("id") or "") == str(target.get("report_definition_id") or ""),
            "evidence_files.evidence_validation report.id must match target.report_definition_id.",
            errors,
        )
        _expect(
            str(report.get("template_key") or "") == str(target.get("template_key") or ""),
            "evidence_files.evidence_validation report.template_key must match target.template_key.",
            errors,
        )
    if date_range:
        _expect(
            str(date_range.get("date_range") or "") == "custom",
            "evidence_files.evidence_validation date_range must be custom.",
            errors,
        )
        _expect(
            str(date_range.get("start_date") or "") == str(target.get("primary_start_date") or ""),
            "evidence_files.evidence_validation start_date must match target.primary_start_date.",
            errors,
        )
        _expect(
            str(date_range.get("end_date") or "") == str(target.get("primary_end_date") or ""),
            "evidence_files.evidence_validation end_date must match target.primary_end_date.",
            errors,
        )
    _expect(
        _filled(evidence.get("preview_hash")),
        "evidence_files.evidence_validation preview_hash is required.",
        errors,
    )
    _expect(
        str(evidence.get("preview_hash") or "") == str(evidence.get("parity_preview_hash") or ""),
        "evidence_files.evidence_validation preview_hash must match parity_preview_hash.",
        errors,
    )


def _validate_text_evidence_file(key: str, path: Path, suffix: str, errors: list[str]) -> None:
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
            errors.append(f"Sensitive or user-level pattern detected in evidence_files.{key}: {pattern.pattern}")


def _validate_coverage(
    value: Any,
    *,
    target: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    coverage = _require_mapping(value, "coverage", errors)
    if not coverage:
        return
    datasets = _require_mapping(coverage.get("datasets"), "coverage.datasets", errors)
    if not datasets:
        return
    target_start = None
    target_end = None
    if target:
        target_start = _parse_date(str(target.get("primary_start_date") or ""), "target.primary_start_date", errors)
        target_end = _parse_date(str(target.get("primary_end_date") or ""), "target.primary_end_date", errors)
    for dataset in REQUIRED_DATASETS:
        row = _require_mapping(datasets.get(dataset), f"coverage.datasets.{dataset}", errors)
        if not row:
            continue
        state = str(row.get("status") or "").strip().lower()
        _expect(_filled(state), f"coverage.datasets.{dataset}.status is required.", errors)
        if state in BLOCKING_COVERAGE_STATES:
            errors.append(f"coverage.datasets.{dataset}.status blocks G10: {state}.")
        elif state in REVIEW_NOTE_COVERAGE_STATES:
            warnings.append(f"coverage.datasets.{dataset}.status needs explicit reviewer note: {state}.")
            _expect(_filled(row.get("reviewer_note")), f"coverage.datasets.{dataset}.reviewer_note is required for {state} coverage.", errors)
        row_count = row.get("row_count")
        _expect(isinstance(row_count, int) and row_count >= 0, f"coverage.datasets.{dataset}.row_count must be a non-negative integer.", errors)
        _expect(_filled(row.get("reviewer")), f"coverage.datasets.{dataset}.reviewer is required.", errors)
        covered_start = None
        covered_end = None
        if state not in BLOCKING_COVERAGE_STATES:
            covered_start = _parse_date(str(row.get("covered_start_date") or ""), f"coverage.datasets.{dataset}.covered_start_date", errors)
            covered_end = _parse_date(str(row.get("covered_end_date") or ""), f"coverage.datasets.{dataset}.covered_end_date", errors)
            if covered_start and covered_end:
                _expect(covered_start <= covered_end, f"coverage.datasets.{dataset}.covered_start_date must be on or before covered_end_date.", errors)
        if state in FULL_RANGE_COVERAGE_STATES and target_start and target_end and covered_start and covered_end:
            _expect(
                covered_start <= target_start,
                f"coverage.datasets.{dataset}.covered_start_date must cover the target start date for {state} coverage.",
                errors,
            )
            _expect(
                covered_end >= target_end,
                f"coverage.datasets.{dataset}.covered_end_date must cover the target end date for {state} coverage.",
                errors,
            )
    _expect(
        coverage.get("monthly_and_90_day_history_proven") is True,
        "coverage.monthly_and_90_day_history_proven must be true.",
        errors,
    )


def _validate_rendering(value: Any, errors: list[str]) -> None:
    rendering = _require_mapping(value, "rendering", errors)
    if not rendering:
        return
    _expect(rendering.get("report_v1_pages_rendered") is True, "rendering.report_v1_pages_rendered must be true.", errors)
    _expect(
        rendering.get("dashboard_v1_rendered_or_not_in_scope") is True,
        "rendering.dashboard_v1_rendered_or_not_in_scope must be true.",
        errors,
    )
    sections = _require_mapping(rendering.get("required_sections_present"), "rendering.required_sections_present", errors)
    if sections:
        for section in REQUIRED_SECTIONS:
            _expect(sections.get(section) is True, f"rendering.required_sections_present.{section} must be true.", errors)
    _expect(rendering.get("coverage_notes_visible") is True, "rendering.coverage_notes_visible must be true.", errors)


def _validate_exports(value: Any, errors: list[str]) -> None:
    exports = _require_mapping(value, "exports", errors)
    if not exports:
        return
    for export_format in REQUIRED_EXPORT_FORMATS:
        row = _require_mapping(exports.get(export_format), f"exports.{export_format}", errors)
        if not row:
            continue
        _expect(_filled(row.get("job_id")), f"exports.{export_format}.job_id is required.", errors)
        _expect(str(row.get("status") or "").strip().lower() in {"completed", "rendered"}, f"exports.{export_format}.status must be completed/rendered.", errors)
        _expect(_positive_int(row.get("byte_count")), f"exports.{export_format}.byte_count must be greater than zero.", errors)
        preview_hash = str(row.get("preview_hash") or "")
        snapshot_hash = str(row.get("snapshot_preview_hash") or "")
        _expect(_filled(preview_hash), f"exports.{export_format}.preview_hash is required.", errors)
        _expect(_filled(snapshot_hash), f"exports.{export_format}.snapshot_preview_hash is required.", errors)
        if _filled(preview_hash) and _filled(snapshot_hash):
            _expect(preview_hash == snapshot_hash, f"exports.{export_format} preview_hash must match snapshot_preview_hash.", errors)


def _validate_parity(value: Any, errors: list[str]) -> None:
    parity = _require_mapping(value, "parity", errors)
    if not parity:
        return
    _expect(parity.get("comparison_values_attached") is True, "parity.comparison_values_attached must be true.", errors)
    counts = _require_mapping(parity.get("result_counts"), "parity.result_counts", errors)
    if counts:
        _expect(_positive_int(counts.get("pass")), "parity.result_counts.pass must be greater than zero.", errors)
        _expect(int(counts.get("fail") or 0) == 0, "parity.result_counts.fail must be zero before G10.", errors)
        _expect(int(counts.get("blocked") or 0) == 0, "parity.result_counts.blocked must be zero before G10.", errors)
    _expect(parity.get("non_pass_rows_resolved") is True, "parity.non_pass_rows_resolved must be true.", errors)
    _expect(_filled(parity.get("reviewer")), "parity.reviewer is required.", errors)


def _validate_delivery(value: Any, errors: list[str]) -> None:
    delivery = _require_mapping(value, "delivery", errors)
    if not delivery:
        return
    _expect(
        str(delivery.get("scheduled_dry_run_status") or "").strip().lower() == "rendered",
        "delivery.scheduled_dry_run_status must be rendered.",
        errors,
    )
    _expect(delivery.get("delivery_mode") == "dry_run", "delivery.delivery_mode must be dry_run.", errors)
    _expect(delivery.get("no_client_email_sent") is True, "delivery.no_client_email_sent must be true.", errors)
    _expect(delivery.get("sanitized_status_recorded") is True, "delivery.sanitized_status_recorded must be true.", errors)


def _validate_safety(value: Any, errors: list[str]) -> None:
    safety = _require_mapping(value, "safety", errors)
    if not safety:
        return
    for key in [
        "diagnostics_support_proof_captured",
        "permissions_matrix_passed",
        "tenant_isolation_passed",
        "audit_events_verified",
        "quota_controls_verified",
        "aggregate_only_verified",
        "redaction_scan_passed",
    ]:
        _expect(safety.get(key) is True, f"safety.{key} must be true.", errors)


def _validate_gates(value: Any, errors: list[str]) -> None:
    gates = _require_mapping(value, "gates", errors)
    if not gates:
        return
    for key in [
        "backend_lint",
        "backend_test",
        "frontend_guardrails",
        "frontend_lint",
        "frontend_test",
        "frontend_build",
        "dev_healthcheck",
    ]:
        _expect(str(gates.get(key) or "").strip().lower() in PASS_STATUSES, f"gates.{key} must pass.", errors)
    preflight = str(gates.get("adinsights_preflight_status") or "").strip().lower()
    _expect(preflight in PASS_STATUSES or preflight in ALLOWED_PREFLIGHT_BLOCKS, "gates.adinsights_preflight_status must pass or be accepted GATE_BLOCK.", errors)
    if preflight in ALLOWED_PREFLIGHT_BLOCKS:
        _expect(
            gates.get("adinsights_preflight_block_accepted_by_g0") is True,
            "gates.adinsights_preflight_block_accepted_by_g0 must be true for blocked preflight.",
            errors,
        )


def _validate_reviewer_route(value: Any, errors: list[str]) -> None:
    route = _require_mapping(value, "reviewer_route", errors)
    if not route:
        return
    for key in ["sofia", "andre", "lina_or_joel", "omar_or_hannah", "raj_mira"]:
        _expect(_filled(route.get(key)), f"reviewer_route.{key} is required.", errors)


def _validate_intake_match(target: Mapping[str, Any], intake_payload: Mapping[str, Any], errors: list[str]) -> None:
    _expect(intake_payload.get("schema_version") == G1_SCHEMA_VERSION, "G1 intake schema_version is invalid.", errors)
    intake_target = _require_mapping(intake_payload.get("target"), "G1 intake target", errors)
    if not intake_target:
        return
    for key in [
        "environment",
        "backend_url",
        "frontend_url",
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
            str(target.get(key) or "") == str(intake_target.get(key) or ""),
            f"target.{key} must match G1 intake target.{key}.",
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


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and value > 0


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
