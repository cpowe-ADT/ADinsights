#!/usr/bin/env python3
"""Validate SLB G0 Raj/Mira architecture and scope review evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_VERSION = "slb_g0_raj_mira_review.v1"
ALLOWED_REVIEW_STATUSES = {"approved_for_g1", "approved_with_followups", "blocked_pending_changes"}
ALLOWED_SCOPE_CLASSIFICATIONS = {"accepted_cross_stream_scope", "accepted_with_followups", "blocked_pending_split"}
ALLOWED_ARCHITECTURE_CLASSIFICATIONS = {
    "accepted_architecture",
    "accepted_with_followups",
    "blocked_pending_architecture_changes",
}
ALLOWED_EVIDENCE_CAPTURE = {"proceed_to_g1", "proceed_to_g1_with_followups", "blocked_before_g1"}
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
    parser = argparse.ArgumentParser(description="Validate a filled SLB G0 Raj/Mira review decision JSON.")
    parser.add_argument("--review-file", required=True, help="Path to filled G0 Raj/Mira review decision JSON.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    review_path = _resolve_path(args.review_file)

    errors: list[str] = []
    warnings: list[str] = []
    payload = _load_json(review_path, "Review file", errors)
    if payload:
        _validate_review(payload, errors=errors, warnings=warnings)

    result = {
        "schema_version": "slb_g0_raj_mira_review_validation.v1",
        "review_file": _display_path(review_path),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"SLB G0 Raj/Mira review valid: {str(result['valid']).lower()}")
        print(f"Review file: {result['review_file']}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_review(payload: Mapping[str, Any], *, errors: list[str], warnings: list[str]) -> None:
    _expect(payload.get("schema_version") == REQUIRED_SCHEMA_VERSION, "Unexpected schema_version.", errors)
    status = str(payload.get("status") or "").strip()
    _expect(status in ALLOWED_REVIEW_STATUSES, "status must be approved_for_g1, approved_with_followups, or blocked_pending_changes.", errors)
    references = _validate_references(payload.get("references"), errors)
    decision = _validate_decision(payload.get("decision"), errors)
    _validate_status_decision_consistency(status, decision, errors)
    _validate_reviewers(payload.get("reviewers"), status, errors)
    _validate_guardrails(payload.get("guardrails"), errors)
    preflight = _validate_preflight_interpretation(payload.get("preflight_interpretation"), errors)
    _validate_preflight_packet_consistency(references, preflight, errors)
    _validate_followups(payload.get("required_followups"), decision, errors, warnings)
    _validate_reviewer_route(payload.get("reviewer_route_confirmed"), errors)
    _validate_decision_log(payload.get("decision_log"), errors)
    _validate_sensitive_patterns(payload, errors)


def _validate_references(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    references = _require_mapping(value, "references", errors)
    if not references:
        return None
    for key in [
        "review_packet",
        "preflight_packet",
        "checked_preflight_packet",
        "decision_id",
        "decision_timestamp",
        "operator",
    ]:
        _expect(_filled(references.get(key)), f"references.{key} is required.", errors)
    for key in ["review_packet", "preflight_packet", "checked_preflight_packet"]:
        raw_path = str(references.get(key) or "").rstrip("/")
        if raw_path and not raw_path.startswith("<"):
            _expect((REPO_ROOT / raw_path).exists(), f"references.{key} path does not exist: {raw_path}.", errors)
    decision_id = str(references.get("decision_id") or "").strip()
    _expect(
        bool(re.fullmatch(r"slb-g0-[a-z0-9][a-z0-9._-]{5,80}", decision_id)),
        "references.decision_id must be a stable slug beginning with slb-g0-.",
        errors,
    )
    _expect(
        _parse_timestamp(str(references.get("decision_timestamp") or "")) is not None,
        "references.decision_timestamp must be an ISO-8601 timestamp with timezone.",
        errors,
    )
    return references


def _validate_decision(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    decision = _require_mapping(value, "decision", errors)
    if not decision:
        return None
    scope = str(decision.get("scope_classification") or "").strip()
    architecture = str(decision.get("architecture_classification") or "").strip()
    evidence_capture = str(decision.get("g1_g11_evidence_capture") or "").strip()
    _expect(scope in ALLOWED_SCOPE_CLASSIFICATIONS, "decision.scope_classification is unsupported.", errors)
    _expect(architecture in ALLOWED_ARCHITECTURE_CLASSIFICATIONS, "decision.architecture_classification is unsupported.", errors)
    _expect(evidence_capture in ALLOWED_EVIDENCE_CAPTURE, "decision.g1_g11_evidence_capture is unsupported.", errors)
    _expect(decision.get("dashthis_cancellation") == "no_go", "decision.dashthis_cancellation must remain no_go.", errors)
    _expect(_filled(decision.get("reason")), "decision.reason is required.", errors)
    if evidence_capture in {"proceed_to_g1", "proceed_to_g1_with_followups"}:
        _expect(
            scope in {"accepted_cross_stream_scope", "accepted_with_followups"},
            "decision.scope_classification must accept scope before proceeding to G1.",
            errors,
        )
        _expect(
            architecture in {"accepted_architecture", "accepted_with_followups"},
            "decision.architecture_classification must accept architecture before proceeding to G1.",
            errors,
        )
    return decision


def _validate_status_decision_consistency(
    status: str,
    decision: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    if not decision:
        return
    scope = str(decision.get("scope_classification") or "").strip()
    architecture = str(decision.get("architecture_classification") or "").strip()
    evidence_capture = str(decision.get("g1_g11_evidence_capture") or "").strip()
    if status == "approved_for_g1":
        _expect(evidence_capture == "proceed_to_g1", "status approved_for_g1 requires decision.g1_g11_evidence_capture proceed_to_g1.", errors)
        _expect(scope == "accepted_cross_stream_scope", "status approved_for_g1 requires clean scope acceptance.", errors)
        _expect(architecture == "accepted_architecture", "status approved_for_g1 requires clean architecture acceptance.", errors)
    elif status == "approved_with_followups":
        _expect(
            evidence_capture == "proceed_to_g1_with_followups",
            "status approved_with_followups requires decision.g1_g11_evidence_capture proceed_to_g1_with_followups.",
            errors,
        )
        _expect(
            scope in {"accepted_cross_stream_scope", "accepted_with_followups"},
            "status approved_with_followups requires accepted scope.",
            errors,
        )
        _expect(
            architecture in {"accepted_architecture", "accepted_with_followups"},
            "status approved_with_followups requires accepted architecture.",
            errors,
        )
    elif status == "blocked_pending_changes":
        _expect(evidence_capture == "blocked_before_g1", "status blocked_pending_changes requires decision.g1_g11_evidence_capture blocked_before_g1.", errors)
        _expect(
            scope == "blocked_pending_split" or architecture == "blocked_pending_architecture_changes",
            "status blocked_pending_changes requires at least one blocked scope or architecture classification.",
            errors,
        )


def _validate_reviewers(value: Any, status: str, errors: list[str]) -> None:
    reviewers = _require_mapping(value, "reviewers", errors)
    if not reviewers:
        return
    decisions: list[str] = []
    for reviewer in ["raj", "mira"]:
        row = _require_mapping(reviewers.get(reviewer), f"reviewers.{reviewer}", errors)
        if not row:
            continue
        decision = str(row.get("decision") or "").strip()
        decisions.append(decision)
        _expect(decision in ALLOWED_REVIEW_STATUSES, f"reviewers.{reviewer}.decision is unsupported.", errors)
        _expect(_filled(row.get("name_or_handle")), f"reviewers.{reviewer}.name_or_handle is required.", errors)
        _expect(_filled(row.get("notes")), f"reviewers.{reviewer}.notes is required.", errors)
        if status == "approved_for_g1":
            _expect(
                decision == "approved_for_g1",
                f"reviewers.{reviewer}.decision must be approved_for_g1 when status is approved_for_g1.",
                errors,
            )
        if status in {"approved_for_g1", "approved_with_followups"}:
            _expect(
                decision in {"approved_for_g1", "approved_with_followups"},
                f"reviewers.{reviewer}.decision must approve G1 when status approves G1.",
                errors,
            )
    if status == "approved_with_followups":
        _expect(
            "approved_with_followups" in decisions,
            "status approved_with_followups requires at least one reviewer decision approved_with_followups.",
            errors,
        )
    if status == "blocked_pending_changes":
        _expect(
            "blocked_pending_changes" in decisions,
            "status blocked_pending_changes requires at least one reviewer decision blocked_pending_changes.",
            errors,
        )


def _validate_guardrails(value: Any, errors: list[str]) -> None:
    guardrails = _require_mapping(value, "guardrails", errors)
    if not guardrails:
        return
    for key in [
        "instagram_deferred",
        "stored_aggregate_only",
        "no_live_provider_calls_at_render_export_time",
        "tenant_isolation_required",
        "aggregate_only_no_user_level_metrics",
        "dashthis_active_until_g12",
    ]:
        _expect(guardrails.get(key) is True, f"guardrails.{key} must be true.", errors)


def _validate_preflight_interpretation(value: Any, errors: list[str]) -> Mapping[str, Any] | None:
    preflight = _require_mapping(value, "preflight_interpretation", errors)
    if not preflight:
        return None
    _expect(preflight.get("scope_status") == "ESCALATE_ARCH_RISK", "preflight_interpretation.scope_status must be ESCALATE_ARCH_RISK.", errors)
    _expect(
        preflight.get("contract_status") == "WARN_POSSIBLE_CONTRACT_CHANGE",
        "preflight_interpretation.contract_status must be WARN_POSSIBLE_CONTRACT_CHANGE.",
        errors,
    )
    _expect(preflight.get("release_status") == "GATE_BLOCK", "preflight_interpretation.release_status must be GATE_BLOCK.", errors)
    _expect(
        preflight.get("classified_as_architecture_review_not_runtime_failure") is True,
        "preflight_interpretation.classified_as_architecture_review_not_runtime_failure must be true.",
        errors,
    )
    for key in ["contract_warning_route", "security_pii_warning_route"]:
        _expect(_filled(preflight.get(key)), f"preflight_interpretation.{key} is required.", errors)
    return preflight


def _validate_preflight_packet_consistency(
    references: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    if not references or not preflight:
        return
    for key in ["preflight_packet", "checked_preflight_packet"]:
        raw_path = str(references.get(key) or "").rstrip("/")
        if not raw_path or raw_path.startswith("<"):
            continue
        packet_dir = _resolve_path(raw_path)
        if packet_dir is None or not packet_dir.exists():
            continue
        _validate_preflight_packet_dir(packet_dir, key, preflight, errors)


def _validate_preflight_packet_dir(
    packet_dir: Path,
    reference_key: str,
    expected: Mapping[str, Any],
    errors: list[str],
) -> None:
    scope_packet = _load_packet_json(packet_dir / "scope-packet.json", f"references.{reference_key}/scope-packet.json", errors)
    contract_packet = _load_packet_json(packet_dir / "contract-packet.json", f"references.{reference_key}/contract-packet.json", errors)
    release_packet = _load_packet_json(packet_dir / "release-packet.json", f"references.{reference_key}/release-packet.json", errors)
    if scope_packet:
        _expect(
            scope_packet.get("scope_status") == expected.get("scope_status"),
            f"references.{reference_key} scope-packet scope_status does not match preflight_interpretation.scope_status.",
            errors,
        )
    if contract_packet:
        _expect(
            contract_packet.get("contract_status") == expected.get("contract_status"),
            f"references.{reference_key} contract-packet contract_status does not match preflight_interpretation.contract_status.",
            errors,
        )
    if release_packet:
        _expect(
            release_packet.get("release_status") == expected.get("release_status"),
            f"references.{reference_key} release-packet release_status does not match preflight_interpretation.release_status.",
            errors,
        )


def _load_packet_json(path: Path, label: str, errors: list[str]) -> Mapping[str, Any] | None:
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


def _validate_followups(
    value: Any,
    decision: Mapping[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append("required_followups must be a list.")
        return
    evidence_capture = str((decision or {}).get("g1_g11_evidence_capture") or "")
    if evidence_capture == "proceed_to_g1_with_followups":
        _expect(bool(value), "required_followups must list followups when proceeding with followups.", errors)
    if evidence_capture == "blocked_before_g1":
        _expect(bool(value), "required_followups must list blocking changes when G0 blocks before G1.", errors)
        _expect(
            any(isinstance(row, Mapping) and row.get("required_before_g1") is True for row in value),
            "blocked_before_g1 requires at least one followup required_before_g1.",
            errors,
        )
    for index, row_value in enumerate(value):
        row = _require_mapping(row_value, f"required_followups[{index}]", errors)
        if not row:
            continue
        if str(row.get("id") or "").strip().lower() in PLACEHOLDER_VALUES and len(value) == 1:
            if evidence_capture == "proceed_to_g1_with_followups":
                errors.append("required_followups must include real followup rows when proceeding with followups.")
            else:
                warnings.append("required_followups contains only the template placeholder row.")
            continue
        _expect(_filled(row.get("id")), f"required_followups[{index}].id is required.", errors)
        _expect(
            isinstance(row.get("owner_route"), list) and bool(row.get("owner_route")),
            f"required_followups[{index}].owner_route is required.",
            errors,
        )
        for owner_index, owner in enumerate(row.get("owner_route") or []):
            _expect(_filled(owner), f"required_followups[{index}].owner_route[{owner_index}] is required.", errors)
        _expect(isinstance(row.get("required_before_g1"), bool), f"required_followups[{index}].required_before_g1 must be boolean.", errors)
        _expect(isinstance(row.get("required_before_g12"), bool), f"required_followups[{index}].required_before_g12 must be boolean.", errors)
        if row.get("required_before_g1") is False and row.get("required_before_g12") is False:
            errors.append(f"required_followups[{index}] must be required before G1 or before G12.")
        _expect(_filled(row.get("description")), f"required_followups[{index}].description is required.", errors)


def _validate_reviewer_route(value: Any, errors: list[str]) -> None:
    route = _require_mapping(value, "reviewer_route_confirmed", errors)
    if not route:
        return
    for key in [
        "sofia",
        "andre",
        "lina_or_joel",
        "omar_or_hannah",
        "nina_if_sensitive",
        "priya_martin_if_retention_gap",
        "raj_mira_for_g12",
    ]:
        _expect(route.get(key) is True, f"reviewer_route_confirmed.{key} must be true.", errors)


def _validate_decision_log(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("decision_log must be a non-empty list.")
        return
    timestamps: list[datetime] = []
    for index, row_value in enumerate(value):
        row = _require_mapping(row_value, f"decision_log[{index}]", errors)
        if not row:
            continue
        for key in ["timestamp", "actor", "summary"]:
            _expect(_filled(row.get(key)), f"decision_log[{index}].{key} is required.", errors)
        parsed = _parse_timestamp(str(row.get("timestamp") or ""))
        _expect(parsed is not None, f"decision_log[{index}].timestamp must be an ISO-8601 timestamp with timezone.", errors)
        if parsed is not None:
            timestamps.append(parsed)
    if len(timestamps) > 1:
        ordered = all(previous <= current for previous, current in zip(timestamps, timestamps[1:]))
        _expect(ordered, "decision_log timestamps must be in ascending order.", errors)


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


def _parse_timestamp(value: str) -> datetime | None:
    if not _filled(value):
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


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
