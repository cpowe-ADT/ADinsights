#!/usr/bin/env python3
"""Draft G1 runtime target intake JSON from redacted target-intake output."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json"
EXPECTED_TARGET_SCHEMA = "slb_target_intake.v1"
EXPECTED_TARGET_STATUS = "candidate_ready_for_operator_confirmation"
EXPECTED_REPORT_SCHEMA = "report.v1"
EXPECTED_TEMPLATE_KEY = "slb_monthly_social_report"
PENDING_STATUS = "pending_operator_input"
RESULT_SCHEMA_VERSION = "slb_g1_intake_draft_result.v1"
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
    parser = argparse.ArgumentParser(
        description=(
            "Draft the G1 runtime target intake JSON from a redacted "
            "slb_target_intake.v1 output. Unknown operator-owned fields stay Pending."
        )
    )
    parser.add_argument("--target-intake-output", required=True, help="Path to redacted slb_target_intake.v1 JSON.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to G1 intake template JSON.")
    parser.add_argument("--output", help="Optional path to write the draft JSON. Defaults to stdout.")

    parser.add_argument("--environment")
    parser.add_argument("--backend-url")
    parser.add_argument("--frontend-url")
    parser.add_argument("--safe-tenant-identifier")
    parser.add_argument("--safe-client-identifier")
    parser.add_argument("--currency")
    parser.add_argument("--paid-meta-account-scope")
    parser.add_argument("--organic-facebook-page-scope")
    parser.add_argument("--content-ops-workspace-scope")

    parser.add_argument("--comparison-owner")
    parser.add_argument("--comparison-evidence-location")
    parser.add_argument("--tolerances-confirmed", action="store_true")

    parser.add_argument("--recipient-assumption")
    parser.add_argument("--operator-notes")

    parser.add_argument("--g0-raj-decision")
    parser.add_argument("--g0-mira-decision")
    parser.add_argument("--g0-can-proceed-to-g1-g11")
    parser.add_argument("--g0-conditions")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors: list[str] = []

    template_path = _resolve_path(args.template)
    target_output_path = _resolve_path(args.target_intake_output)
    template = _load_json(template_path, "template", errors)
    target_output = _load_json(target_output_path, "target-intake output", errors)

    draft: Mapping[str, Any] | None = None
    if template and target_output:
        _validate_target_output(target_output, errors)
        if not errors:
            draft = _build_draft(
                template=template,
                target_output=target_output,
                target_output_path=target_output_path,
                args=args,
            )
            _validate_no_sensitive_values(draft, errors, label="draft")

    if errors:
        print(
            json.dumps(
                {
                    "schema_version": RESULT_SCHEMA_VERSION,
                    "valid": False,
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    assert draft is not None
    summary = _draft_summary(draft)
    serialized = json.dumps(draft, indent=2) + "\n"
    if args.output:
        output_path = _resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
        print(
            json.dumps(
                {
                    "schema_version": RESULT_SCHEMA_VERSION,
                    "valid": True,
                    "output_file": _display_path(output_path),
                    **summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(serialized, end="")
    return 0


def _build_draft(
    *,
    template: Mapping[str, Any],
    target_output: Mapping[str, Any],
    target_output_path: Path,
    args: argparse.Namespace,
) -> Mapping[str, Any]:
    draft = copy.deepcopy(dict(template))
    draft["status"] = PENDING_STATUS

    report = _as_mapping(target_output.get("report"))
    report_filter = _as_mapping(_as_mapping(target_output.get("date_range")).get("report_filter"))

    target = _ensure_mapping(draft, "target")
    target["report_definition_id"] = str(report["id"])
    target["template_key"] = str(report.get("template_key") or EXPECTED_TEMPLATE_KEY)
    target["report_schema_version"] = str(report.get("schema_version") or EXPECTED_REPORT_SCHEMA)
    target["primary_start_date"] = str(report_filter["start_date"])
    target["primary_end_date"] = str(report_filter["end_date"])

    _copy_arg(args, target, "environment", "environment")
    _copy_arg(args, target, "backend_url", "backend_url")
    _copy_arg(args, target, "frontend_url", "frontend_url")
    _copy_arg(args, target, "safe_tenant_identifier", "safe_tenant_identifier")
    _copy_arg(args, target, "safe_client_identifier", "safe_client_identifier")
    _copy_arg(args, target, "currency", "currency")
    _copy_arg(args, target, "paid_meta_account_scope", "paid_meta_account_scope")
    _copy_arg(args, target, "organic_facebook_page_scope", "organic_facebook_page_scope")
    _copy_arg(args, target, "content_ops_workspace_scope", "content_ops_workspace_scope")

    comparison = _ensure_mapping(draft, "comparison")
    _copy_arg(args, comparison, "comparison_owner", "dashthis_source_comparison_owner")
    _copy_arg(args, comparison, "comparison_evidence_location", "dashthis_source_evidence_location")
    if args.tolerances_confirmed:
        comparison["tolerances_confirmed"] = True

    delivery = _ensure_mapping(draft, "delivery")
    _copy_arg(args, delivery, "recipient_assumption", "recipient_assumption")

    g0 = _ensure_mapping(draft, "g0_clearance")
    _copy_arg(args, g0, "g0_raj_decision", "raj_decision")
    _copy_arg(args, g0, "g0_mira_decision", "mira_decision")
    _copy_arg(args, g0, "g0_can_proceed_to_g1_g11", "can_proceed_to_g1_g11")
    _copy_arg(args, g0, "g0_conditions", "conditions")

    evidence = _ensure_mapping(draft, "evidence")
    evidence["slb_report_target_intake_output"] = _display_path(target_output_path)
    _copy_arg(args, evidence, "operator_notes", "operator_notes")
    return draft


def _validate_target_output(payload: Mapping[str, Any], errors: list[str]) -> None:
    _expect(payload.get("schema_version") == EXPECTED_TARGET_SCHEMA, f"target-intake output schema_version must be {EXPECTED_TARGET_SCHEMA}.", errors)
    _expect(payload.get("status") == EXPECTED_TARGET_STATUS, f"target-intake output status must be {EXPECTED_TARGET_STATUS}.", errors)

    report = _require_mapping(payload.get("report"), "target-intake output.report", errors)
    if report:
        _expect(_filled(report.get("id")), "target-intake output.report.id is required.", errors)
        _expect(report.get("schema_version") == EXPECTED_REPORT_SCHEMA, f"target-intake output.report.schema_version must be {EXPECTED_REPORT_SCHEMA}.", errors)
        _expect(report.get("template_key") == EXPECTED_TEMPLATE_KEY, f"target-intake output.report.template_key must be {EXPECTED_TEMPLATE_KEY}.", errors)

    date_range = _require_mapping(payload.get("date_range"), "target-intake output.date_range", errors)
    report_filter = _require_mapping(date_range.get("report_filter") if date_range else None, "target-intake output.date_range.report_filter", errors)
    if report_filter:
        _expect(_filled(report_filter.get("start_date")), "target-intake output.date_range.report_filter.start_date is required.", errors)
        _expect(_filled(report_filter.get("end_date")), "target-intake output.date_range.report_filter.end_date is required.", errors)

    _validate_no_sensitive_values(payload, errors, label="target-intake output")


def _draft_summary(draft: Mapping[str, Any]) -> dict[str, Any]:
    pending_fields: list[str] = []
    false_confirmation_fields: list[str] = []
    _collect_draft_fields(draft, path="", pending_fields=pending_fields, false_confirmation_fields=false_confirmation_fields)
    return {
        "draft_status": draft.get("status"),
        "candidate_ready_for_review": False,
        "pending_fields": pending_fields,
        "pending_field_count": len(pending_fields),
        "false_confirmation_fields": false_confirmation_fields,
        "false_confirmation_count": len(false_confirmation_fields),
        "next_required_actions": [
            "Review every pending field and replace placeholders with approved safe values.",
            "Record G0 Raj/Mira clearance and preserve conditional followups when present.",
            "Confirm DashThis/source tolerances only after real source evidence is available.",
            "Set status to candidate_ready_for_review only after operator review is complete.",
            "Run scripts/validate_slb_g1_runtime_target_intake.py against the reviewed intake.",
        ],
    }


def _collect_draft_fields(
    value: Any,
    *,
    path: str,
    pending_fields: list[str],
    false_confirmation_fields: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _collect_draft_fields(
                item,
                path=child_path,
                pending_fields=pending_fields,
                false_confirmation_fields=false_confirmation_fields,
            )
        return
    if value is False and path.endswith(("confirmed", "active", "proceed_to_g1_g11")):
        false_confirmation_fields.append(path)
    elif _is_placeholder(value):
        pending_fields.append(path)


def _load_json(path: Path, label: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not path.exists():
        errors.append(f"{label} file does not exist: {_display_path(path)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label} file is not valid JSON: {exc}")
        return None
    if not isinstance(payload, Mapping):
        errors.append(f"{label} root must be a JSON object.")
        return None
    return payload


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    value = {}
    parent[key] = value
    return value


def _require_mapping(value: Any, field: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{field} must be an object.")
        return None
    return value


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _copy_arg(args: argparse.Namespace, target: dict[str, Any], attr: str, key: str) -> None:
    value = getattr(args, attr)
    if value is not None:
        target[key] = value


def _filled(value: Any) -> bool:
    return bool(str(value or "").strip())


def _is_placeholder(value: Any) -> bool:
    normalized = "" if value is None else str(value).strip().lower()
    return normalized in PLACEHOLDER_VALUES


def _validate_no_sensitive_values(payload: Mapping[str, Any], errors: list[str], *, label: str) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Sensitive or user-level pattern detected in {label}: {pattern.pattern}")


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
