#!/usr/bin/env python3
"""Validate SLB G10 adversarial review evidence before G11 hardening."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g10_adversarial_review.v1"
G2_G9_SCHEMA_VERSION = "slb_g2_g9_evidence_run.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TIMEZONE = "America/Jamaica"
REQUIRED_ATTACKS = [
    "date_range_timezone",
    "tenant_scope",
    "client_account_page_scope",
    "stale_freshness",
    "partial_coverage",
    "missing_history",
    "source_disconnected",
    "unsupported_instagram",
    "user_level_data",
    "empty_artifacts",
    "artifact_safety",
    "csv_formula_safety",
    "delivery_failure",
    "quota_bypass",
    "audit_gap",
    "rollback_gap",
]
PASS_OUTCOMES = {"pass", "fixed", "accepted_risk", "waived", "not_applicable"}
BLOCKING_OUTCOMES = {"pending", "open", "failed", "blocked", "runtime_pending", "review_pending"}
ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "blocker"}
PLACEHOLDER_VALUES = {"", "pending", "tbd", "todo", "n/a", "unknown", "none", "<pending>"}
EVIDENCE_ROOT = Path("docs/project/evidence/dashthis-replacement")
EVIDENCE_LINK_SUFFIXES = {".md", ".json", ".txt", ".log", ".csv", ".png", ".jpg", ".jpeg", ".pdf"}
TEXT_EVIDENCE_SUFFIXES = {".md", ".json", ".txt", ".log", ".csv"}
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
    parser = argparse.ArgumentParser(description="Validate a filled SLB G10 adversarial review JSON.")
    parser.add_argument("--review-file", required=True, help="Path to filled G10 adversarial review JSON.")
    parser.add_argument(
        "--g2-g9-run-file",
        help="Optional filled G2-G9 evidence run JSON. When provided, target fields must match.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    review_path = _resolve_path(args.review_file)
    run_path = _resolve_path(args.g2_g9_run_file) if args.g2_g9_run_file else None

    errors: list[str] = []
    warnings: list[str] = []
    review_payload = _load_json(review_path, "Review file", errors)
    run_payload = _load_json(run_path, "G2-G9 run file", errors) if run_path else None
    if review_payload:
        _validate_review(review_payload, run_payload=run_payload, errors=errors, warnings=warnings)

    result = {
        "schema_version": "slb_g10_adversarial_review_validation.v1",
        "review_file": _display_path(review_path),
        "g2_g9_run_file": _display_path(run_path) if run_path else None,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G10 adversarial review valid: {str(result['valid']).lower()}")
        print(f"Review file: {result['review_file']}")
        if result["g2_g9_run_file"]:
            print(f"G2-G9 run file: {result['g2_g9_run_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_review(
    payload: Mapping[str, Any],
    *,
    run_payload: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    _expect(payload.get("schema_version") == REQUIRED_SCHEMA_VERSION, "Unexpected schema_version.", errors)
    _expect(str(payload.get("status") or "") == "ready_for_g11_hardening", "status must be ready_for_g11_hardening.", errors)
    _validate_references(payload.get("references"), errors)
    target = _validate_target(payload.get("target"), errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    _validate_attack_reviews(payload.get("attack_reviews"), errors, warnings)
    _validate_final_checks(payload.get("final_checks"), errors)
    _validate_reviewer_route(payload.get("reviewer_route"), errors)
    if run_payload and target:
        _validate_g2_g9_match(target, run_payload, errors)
    _validate_sensitive_patterns(payload, errors)


def _validate_references(value: Any, errors: list[str]) -> None:
    references = _require_mapping(value, "references", errors)
    if not references:
        return
    for key in ["g2_g9_run_file", "review_id", "review_timestamp", "operator"]:
        _expect(_filled(references.get(key)), f"references.{key} is required.", errors)
    _expect(references.get("g2_g9_run_valid") is True, "references.g2_g9_run_valid must be true.", errors)


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
    for key in [
        "instagram_deferred",
        "dashthis_active",
        "stored_aggregate_only",
        "no_live_provider_calls_at_render_export_time",
    ]:
        _expect(guardrails.get(key) is True, f"guardrails.{key} must be true.", errors)


def _validate_attack_reviews(value: Any, errors: list[str], warnings: list[str]) -> None:
    reviews = _require_mapping(value, "attack_reviews", errors)
    if not reviews:
        return
    seen = list(reviews)
    _expect(seen == REQUIRED_ATTACKS, "attack_reviews must contain exactly the required adversarial checks in order.", errors)
    for attack in REQUIRED_ATTACKS:
        row = _require_mapping(reviews.get(attack), f"attack_reviews.{attack}", errors)
        if not row:
            continue
        outcome = str(row.get("outcome") or "").strip().lower()
        severity = str(row.get("severity") or "").strip().lower()
        _expect(outcome in PASS_OUTCOMES, f"attack_reviews.{attack}.outcome must be closed before G11.", errors)
        if outcome in BLOCKING_OUTCOMES:
            errors.append(f"attack_reviews.{attack}.outcome blocks G11: {outcome}.")
        _expect(severity in ALLOWED_SEVERITIES, f"attack_reviews.{attack}.severity is unsupported.", errors)
        for key in ["evidence", "resolution", "reviewer"]:
            _expect(_filled(row.get(key)), f"attack_reviews.{attack}.{key} is required.", errors)
        if _filled(row.get("evidence")):
            _validate_evidence_link(attack, str(row.get("evidence") or ""), errors)
        if severity in {"high", "blocker"} and outcome not in {"fixed", "accepted_risk", "waived"}:
            errors.append(
                f"attack_reviews.{attack} severity {severity} requires outcome fixed, accepted_risk, or waived."
            )
        if outcome in {"accepted_risk", "waived"}:
            approval = _require_mapping(row.get("approval"), f"attack_reviews.{attack}.approval", errors)
            if approval:
                for key in ["risk_owner", "accepted_by", "expires_or_review_by", "rationale"]:
                    _expect(_filled(approval.get(key)), f"attack_reviews.{attack}.approval.{key} is required for {outcome}.", errors)
                approvers = approval.get("accepted_by")
                if isinstance(approvers, list):
                    normalized = {str(approver).strip().lower() for approver in approvers}
                    _expect({"raj", "mira"}.issubset(normalized), f"attack_reviews.{attack}.approval.accepted_by must include Raj and Mira for {outcome}.", errors)
                else:
                    normalized_text = str(approvers or "").lower()
                    _expect(
                        "raj" in normalized_text and "mira" in normalized_text,
                        f"attack_reviews.{attack}.approval.accepted_by must include Raj and Mira for {outcome}.",
                        errors,
                    )
            warnings.append(f"attack_reviews.{attack} has {outcome}; confirm the approval metadata is reflected in the G12 recommendation.")


def _validate_evidence_link(attack: str, value: str, errors: list[str]) -> None:
    path = Path(value.strip())
    field = f"attack_reviews.{attack}.evidence"
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field} must be a repo-relative path under {EVIDENCE_ROOT}.")
        return
    if path.parts[: len(EVIDENCE_ROOT.parts)] != EVIDENCE_ROOT.parts:
        errors.append(f"{field} must be under {EVIDENCE_ROOT}.")
        return
    suffix = path.suffix.lower()
    if suffix not in EVIDENCE_LINK_SUFFIXES:
        errors.append(f"{field} must use one of: {', '.join(sorted(EVIDENCE_LINK_SUFFIXES))}.")
    resolved = REPO_ROOT / path
    if not resolved.exists():
        errors.append(f"{field} does not exist: {_display_path(resolved)}")
        return
    if not resolved.is_file():
        errors.append(f"{field} must be a file: {_display_path(resolved)}")
        return
    if resolved.stat().st_size <= 0:
        errors.append(f"{field} must be non-empty: {_display_path(resolved)}")
        return
    if suffix in TEXT_EVIDENCE_SUFFIXES:
        _validate_text_evidence_file(field, resolved, suffix, errors)


def _validate_text_evidence_file(field: str, path: Path, suffix: str, errors: list[str]) -> None:
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
            errors.append(f"Sensitive or user-level pattern detected in {field}: {pattern.pattern}")


def _validate_final_checks(value: Any, errors: list[str]) -> None:
    checks = _require_mapping(value, "final_checks", errors)
    if not checks:
        return
    for key in [
        "all_attack_reviews_closed",
        "no_unresolved_blocker_or_high",
        "no_unsupported_instagram_claim",
        "no_hidden_stale_partial_missing_history",
        "no_user_level_secret_or_raw_provider_data",
        "rollback_path_confirmed",
        "dashthis_still_active",
        "raj_mira_acceptance",
    ]:
        _expect(checks.get(key) is True, f"final_checks.{key} must be true.", errors)


def _validate_reviewer_route(value: Any, errors: list[str]) -> None:
    route = _require_mapping(value, "reviewer_route", errors)
    if not route:
        return
    for key in ["raj", "mira", "sofia", "andre", "lina_or_joel", "omar_or_hannah"]:
        _expect(_filled(route.get(key)), f"reviewer_route.{key} is required.", errors)


def _validate_g2_g9_match(target: Mapping[str, Any], run_payload: Mapping[str, Any], errors: list[str]) -> None:
    _expect(run_payload.get("schema_version") == G2_G9_SCHEMA_VERSION, "G2-G9 run schema_version is invalid.", errors)
    _expect(str(run_payload.get("status") or "") == "ready_for_g10_review", "G2-G9 run status must be ready_for_g10_review.", errors)
    references = _require_mapping(run_payload.get("references"), "G2-G9 run references", errors)
    if references:
        _expect(references.get("g0_can_proceed") is True, "G2-G9 run references.g0_can_proceed must be true.", errors)
    run_target = _require_mapping(run_payload.get("target"), "G2-G9 run target", errors)
    if not run_target:
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
            str(target.get(key) or "") == str(run_target.get(key) or ""),
            f"target.{key} must match G2-G9 run target.{key}.",
            errors,
        )
    _validate_g2_g9_evidence_validation(run_payload.get("evidence_files"), target=target, errors=errors)


def _validate_g2_g9_evidence_validation(
    value: Any,
    *,
    target: Mapping[str, Any],
    errors: list[str],
) -> None:
    evidence_files = _require_mapping(value, "G2-G9 run evidence_files", errors)
    if not evidence_files:
        return
    raw_path = str(evidence_files.get("evidence_validation") or "").strip()
    _expect(_filled(raw_path), "G2-G9 run evidence_files.evidence_validation is required.", errors)
    if not _filled(raw_path):
        return
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        errors.append("G2-G9 run evidence_files.evidence_validation must be a repo-relative path.")
        return
    resolved = REPO_ROOT / path
    payload = _load_json(resolved, "G2-G9 evidence validation file", errors)
    if not payload:
        return
    _expect(
        payload.get("schema_version") == "slb_evidence_validation.v1",
        "G2-G9 evidence validation schema_version must be slb_evidence_validation.v1.",
        errors,
    )
    _expect(
        payload.get("readiness_status") == "pass",
        "G2-G9 evidence validation readiness_status must be pass.",
        errors,
    )
    _expect(int(payload.get("blocker_count") or 0) == 0, "G2-G9 evidence validation blocker_count must be zero.", errors)
    evidence = _require_mapping(payload.get("evidence"), "G2-G9 evidence validation evidence", errors)
    if not evidence:
        return
    report = _require_mapping(evidence.get("report"), "G2-G9 evidence validation evidence.report", errors)
    date_range = _require_mapping(evidence.get("date_range"), "G2-G9 evidence validation evidence.date_range", errors)
    if report:
        _expect(
            str(report.get("id") or "") == str(target.get("report_definition_id") or ""),
            "G2-G9 evidence validation report.id must match target.report_definition_id.",
            errors,
        )
        _expect(
            str(report.get("template_key") or "") == str(target.get("template_key") or ""),
            "G2-G9 evidence validation report.template_key must match target.template_key.",
            errors,
        )
    if date_range:
        _expect(
            str(date_range.get("start_date") or "") == str(target.get("primary_start_date") or ""),
            "G2-G9 evidence validation start_date must match target.primary_start_date.",
            errors,
        )
        _expect(
            str(date_range.get("end_date") or "") == str(target.get("primary_end_date") or ""),
            "G2-G9 evidence validation end_date must match target.primary_end_date.",
            errors,
        )
    _expect(_filled(evidence.get("preview_hash")), "G2-G9 evidence validation preview_hash is required.", errors)
    _expect(
        str(evidence.get("preview_hash") or "") == str(evidence.get("parity_preview_hash") or ""),
        "G2-G9 evidence validation preview_hash must match parity_preview_hash.",
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
