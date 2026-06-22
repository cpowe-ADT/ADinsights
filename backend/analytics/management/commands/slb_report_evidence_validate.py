"""Validate offline SLB cancellation-readiness evidence artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError


REQUIRED_DATASETS = {"paid_meta_ads", "organic_facebook_page", "content_ops"}
REQUIRED_PAGE_IDS = {
    "cover",
    "executive_summary",
    "paid_meta_ads",
    "organic_facebook",
    "top_posts",
    "content_activity",
    "recommendations",
    "appendix",
}
DEFAULT_REQUIRED_FORMATS = {"csv", "pdf", "png"}
ALLOWED_PARITY_RESULTS = {
    "pass",
    "fail",
    "blocked_missing_dashthis_value",
    "blocked_missing_source_value",
    "blocked_metric_semantics",
}
BLOCKING_COVERAGE_STATUSES = {
    "permission_missing",
    "unsupported_metric",
    "missing_history",
    "not_previously_synced",
}
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


class Command(BaseCommand):
    help = "Validate offline SLB evidence-bundle and parity-comparison artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--evidence-bundle", required=True)
        parser.add_argument("--parity-comparison", required=False)
        parser.add_argument("--expected-start-date", required=False, default="")
        parser.add_argument("--expected-end-date", required=False, default="")
        parser.add_argument(
            "--required-export-format",
            action="append",
            dest="required_export_formats",
            default=None,
            choices=["csv", "pdf", "png"],
        )
        parser.add_argument("--format", choices=["json", "markdown"], default="json")

    def handle(self, *args, **options):
        bundle = _load_json_file(options["evidence_bundle"], expected="evidence bundle")
        parity = (
            _load_json_file(options["parity_comparison"], expected="parity comparison")
            if options.get("parity_comparison")
            else None
        )
        result = validate_evidence(
            bundle=bundle,
            parity=parity,
            expected_start_date=options.get("expected_start_date") or "",
            expected_end_date=options.get("expected_end_date") or "",
            required_export_formats=set(options.get("required_export_formats") or DEFAULT_REQUIRED_FORMATS),
        )
        if options["format"] == "markdown":
            self.stdout.write(_markdown(result))
        else:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))


def validate_evidence(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    expected_start_date: str = "",
    expected_end_date: str = "",
    required_export_formats: set[str] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []
    required_export_formats = required_export_formats or DEFAULT_REQUIRED_FORMATS

    _check_bundle_schema(bundle, blockers, checks)
    _check_date_range(
        bundle=bundle,
        parity=parity,
        expected_start_date=expected_start_date,
        expected_end_date=expected_end_date,
        blockers=blockers,
        checks=checks,
    )
    _check_datasets(bundle, blockers, warnings, checks)
    _check_source_health(bundle, blockers, checks)
    _check_rendering(bundle, blockers, checks)
    _check_exports(bundle, required_export_formats, blockers, checks)
    _check_parity(bundle, parity, blockers, checks)
    _check_instagram_deferred(bundle, blockers, checks)
    _check_sensitive_payloads(bundle=bundle, parity=parity, blockers=blockers, checks=checks)

    return {
        "schema_version": "slb_evidence_validation.v1",
        "evidence": _evidence_identity(bundle=bundle, parity=parity),
        "readiness_status": "blocked" if blockers else "warning" if warnings else "pass",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def _load_json_file(path: str, *, expected: str) -> Any:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CommandError(f"{expected} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"{expected} file is not valid JSON: {path}") from exc


def _evidence_identity(*, bundle: Mapping[str, Any], parity: Mapping[str, Any] | None) -> dict[str, Any]:
    parity_payload = parity or {}
    return {
        "report": bundle.get("report") if isinstance(bundle.get("report"), Mapping) else {},
        "date_range": bundle.get("date_range") if isinstance(bundle.get("date_range"), Mapping) else {},
        "preview_hash": str(bundle.get("preview_hash") or ""),
        "parity_preview_hash": str(parity_payload.get("preview_hash") or ""),
    }


def _check_bundle_schema(bundle: Mapping[str, Any], blockers: list[dict[str, str]], checks: list[dict[str, str]]) -> None:
    if bundle.get("schema_version") != "slb_evidence_bundle.v1":
        blockers.append(_finding("bundle_schema", "Evidence bundle schema_version must be slb_evidence_bundle.v1."))
        return
    checks.append(_passed("bundle_schema", "Evidence bundle schema is recognized."))


def _check_date_range(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    expected_start_date: str,
    expected_end_date: str,
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    date_range = bundle.get("date_range") if isinstance(bundle.get("date_range"), Mapping) else {}
    if date_range.get("date_range") != "custom":
        blockers.append(_finding("date_range", "Evidence bundle must use a bounded custom date range."))
    start_date = str(date_range.get("start_date") or "")
    end_date = str(date_range.get("end_date") or "")
    if not start_date or not end_date:
        blockers.append(_finding("date_range", "Evidence bundle start_date and end_date are required."))
    if expected_start_date and start_date != expected_start_date:
        blockers.append(_finding("date_range", "Evidence bundle start_date does not match expected G1 start date."))
    if expected_end_date and end_date != expected_end_date:
        blockers.append(_finding("date_range", "Evidence bundle end_date does not match expected G1 end date."))
    if parity is not None:
        parity_range = parity.get("date_range") if isinstance(parity.get("date_range"), Mapping) else {}
        if parity_range != date_range:
            blockers.append(_finding("date_range", "Parity comparison date_range does not match evidence bundle."))
    checks.append(_passed("date_range", "Date-range consistency check completed."))


def _check_datasets(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    coverage_summary = bundle.get("coverage_summary") if isinstance(bundle.get("coverage_summary"), Mapping) else {}
    datasets = coverage_summary.get("datasets") if isinstance(coverage_summary.get("datasets"), list) else []
    by_dataset = {
        str(row.get("dataset") or ""): row
        for row in datasets
        if isinstance(row, Mapping) and row.get("dataset")
    }
    missing = REQUIRED_DATASETS - set(by_dataset)
    if missing:
        blockers.append(_finding("coverage_datasets", f"Missing required datasets: {', '.join(sorted(missing))}."))
    for dataset, row in by_dataset.items():
        statuses = row.get("statuses") if isinstance(row.get("statuses"), Mapping) else {}
        blocking_statuses = sorted(set(statuses) & BLOCKING_COVERAGE_STATUSES)
        if blocking_statuses:
            blockers.append(
                _finding(
                    "coverage_status",
                    f"{dataset} has cancellation-blocking coverage statuses: {', '.join(blocking_statuses)}.",
                )
            )
        if "partial" in statuses or "stale" in statuses or "source_disconnected" in statuses:
            warnings.append(
                _finding(
                    "coverage_status",
                    f"{dataset} has warning coverage statuses that require reviewer explanation.",
                )
            )
        if int(row.get("row_count") or 0) <= 0:
            blockers.append(_finding("coverage_row_count", f"{dataset} has no aggregate rows."))
    checks.append(_passed("coverage_datasets", "Required dataset coverage check completed."))


def _check_source_health(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    diagnostics = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), Mapping) else {}
    source_health = (
        diagnostics.get("source_health")
        if isinstance(diagnostics.get("source_health"), Mapping)
        else {}
    )
    if source_health.get("schema_version") != "slb_source_health.v1":
        blockers.append(
            _finding("source_health", "Diagnostics source_health schema_version must be slb_source_health.v1.")
        )
        return
    if source_health.get("stored_aggregate_only") is not True:
        blockers.append(_finding("source_health", "source_health must confirm stored_aggregate_only."))
    if source_health.get("no_live_provider_calls") is not True:
        blockers.append(_finding("source_health", "source_health must confirm no_live_provider_calls."))

    for key in ["meta_credentials", "meta_page_connection", "meta_airbyte", "stored_assets", "stored_rows"]:
        if not isinstance(source_health.get(key), Mapping):
            blockers.append(_finding("source_health", f"source_health.{key} is required."))

    stored_rows = source_health.get("stored_rows") if isinstance(source_health.get("stored_rows"), Mapping) else {}
    for key in ["paid_meta_ads", "organic_facebook_page", "organic_facebook_posts", "content_ops"]:
        row = stored_rows.get(key) if isinstance(stored_rows.get(key), Mapping) else {}
        if "row_count" not in row:
            blockers.append(_finding("source_health", f"source_health.stored_rows.{key}.row_count is required."))

    actions = source_health.get("recommended_next_actions")
    if not isinstance(actions, list) or not actions:
        blockers.append(_finding("source_health", "source_health.recommended_next_actions must be non-empty."))

    checks.append(_passed("source_health", "Diagnostics source-health support proof check completed."))


def _check_rendering(bundle: Mapping[str, Any], blockers: list[dict[str, str]], checks: list[dict[str, str]]) -> None:
    rendering = bundle.get("rendering") if isinstance(bundle.get("rendering"), Mapping) else {}
    pages = rendering.get("pages") if isinstance(rendering.get("pages"), list) else []
    page_ids = {str(page.get("id") or "") for page in pages if isinstance(page, Mapping)}
    missing = REQUIRED_PAGE_IDS - page_ids
    if missing:
        blockers.append(_finding("rendering_pages", f"Missing required report pages: {', '.join(sorted(missing))}."))
    if int(rendering.get("widget_count") or 0) <= 0:
        blockers.append(_finding("rendering_widgets", "Rendering summary has no widgets."))
    checks.append(_passed("rendering", "Report rendering summary check completed."))


def _check_exports(
    bundle: Mapping[str, Any],
    required_formats: set[str],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    exports = bundle.get("exports") if isinstance(bundle.get("exports"), list) else []
    completed_by_format = {}
    dry_run_rendered = False
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    if not bundle_hash:
        blockers.append(_finding("preview_hash", "Evidence bundle preview_hash is required for export reproducibility."))
    for row in exports:
        if not isinstance(row, Mapping):
            continue
        export_format = str(row.get("format") or "")
        preview_hash = str(row.get("preview_hash") or "").strip()
        snapshot_preview_hash = str(row.get("snapshot_preview_hash") or "").strip()
        completed_non_empty = (
            row.get("status") == "completed"
            and row.get("artifact_present") is True
            and int(row.get("artifact_size_bytes") or 0) > 0
        )
        hash_reproducible = True
        if completed_non_empty:
            if not preview_hash:
                blockers.append(_finding("export_hash", f"{export_format} export preview_hash is required."))
                hash_reproducible = False
            elif bundle_hash and preview_hash != bundle_hash:
                blockers.append(_finding("export_hash", f"{export_format} export preview_hash differs from bundle."))
                hash_reproducible = False
            if not snapshot_preview_hash:
                blockers.append(_finding("export_hash", f"{export_format} export snapshot_preview_hash is required."))
                hash_reproducible = False
            elif bundle_hash and snapshot_preview_hash != bundle_hash:
                blockers.append(_finding("export_hash", f"{export_format} snapshot_preview_hash differs from bundle."))
                hash_reproducible = False
        else:
            if bundle_hash and preview_hash and preview_hash != bundle_hash:
                blockers.append(_finding("export_hash", f"{export_format} export preview_hash differs from bundle."))
            if bundle_hash and snapshot_preview_hash and snapshot_preview_hash != bundle_hash:
                blockers.append(_finding("export_hash", f"{export_format} snapshot_preview_hash differs from bundle."))
        if (
            completed_non_empty
            and hash_reproducible
        ):
            completed_by_format[export_format] = row
        delivery_status = row.get("delivery_status") if isinstance(row.get("delivery_status"), Mapping) else {}
        if delivery_status.get("mode") == "dry_run" and delivery_status.get("status") == "rendered":
            dry_run_rendered = True
    missing_formats = required_formats - set(completed_by_format)
    if missing_formats:
        blockers.append(
            _finding(
                "exports",
                f"Missing completed non-empty exports for: {', '.join(sorted(missing_formats))}.",
            )
        )
    if not dry_run_rendered:
        blockers.append(_finding("scheduled_dry_run", "No rendered scheduled dry-run evidence found."))
    checks.append(_passed("exports", "Export and scheduled dry-run evidence check completed."))


def _check_parity(
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    if parity is None:
        blockers.append(_finding("parity", "Parity comparison artifact is required."))
        return
    if parity.get("schema_version") != "slb_parity_comparison.v1":
        blockers.append(_finding("parity_schema", "Parity comparison schema_version must be slb_parity_comparison.v1."))
    bundle_report = bundle.get("report") if isinstance(bundle.get("report"), Mapping) else {}
    parity_report = parity.get("report") if isinstance(parity.get("report"), Mapping) else {}
    _check_parity_report_identity(bundle_report, parity_report, blockers)
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    parity_hash = str(parity.get("preview_hash") or "").strip()
    if not parity_hash:
        blockers.append(_finding("parity_hash", "Parity comparison preview_hash is required."))
    elif bundle_hash and parity_hash != bundle_hash:
        blockers.append(_finding("parity_hash", "Parity comparison preview_hash does not match evidence bundle."))
    rows = parity.get("rows") if isinstance(parity.get("rows"), list) else []
    declared_row_count = _int_value(parity.get("row_count"))
    actual_row_count = len([row for row in rows if isinstance(row, Mapping)])
    if declared_row_count <= 0:
        blockers.append(_finding("parity_rows", "Parity comparison has no rows."))
    elif declared_row_count != actual_row_count:
        blockers.append(_finding("parity_rows", "Parity comparison row_count does not match rows length."))
    summary = parity.get("result_summary") if isinstance(parity.get("result_summary"), Mapping) else {}
    declared_summary = {str(key): _int_value(value) for key, value in summary.items()}
    actual_summary: dict[str, int] = {}
    unsupported_results: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        result = str(row.get("result") or "").strip()
        if result:
            actual_summary[result] = actual_summary.get(result, 0) + 1
            if result not in ALLOWED_PARITY_RESULTS:
                unsupported_results.add(result)
        if result == "pass":
            _validate_pass_parity_row(index, row, blockers)
    if unsupported_results:
        blockers.append(
            _finding(
                "parity_results",
                f"Parity has unsupported result labels: {', '.join(sorted(unsupported_results))}.",
            )
        )
    if actual_summary and declared_summary != actual_summary:
        blockers.append(_finding("parity_results", "Parity result_summary does not match row results."))
    if declared_summary.get("pass", 0) <= 0:
        blockers.append(_finding("parity_results", "Parity comparison must include at least one passing row."))
    blocked_or_failed = {
        key: value
        for key, value in declared_summary.items()
        if (str(key).startswith("blocked_") or key == "fail") and value > 0
    }
    if blocked_or_failed:
        blockers.append(_finding("parity_results", f"Parity has unresolved rows: {blocked_or_failed}."))
    checks.append(_passed("parity", "Parity comparison check completed."))


def _validate_pass_parity_row(index: int, row: Mapping[str, Any], blockers: list[dict[str, str]]) -> None:
    for key in ["dataset", "widget_id", "metric", "label"]:
        if not str(row.get(key) or "").strip():
            blockers.append(_finding("parity_pass_row", f"Parity pass row {index} is missing {key}."))
    for key in ["adinsights_value", "source_value", "absolute_delta"]:
        if row.get(key) is None:
            blockers.append(_finding("parity_pass_row", f"Parity pass row {index} is missing {key}."))
    has_tolerance = (
        row.get("accepted_tolerance_percent") is not None
        or row.get("accepted_tolerance_absolute") is not None
    )
    if not has_tolerance:
        blockers.append(_finding("parity_pass_row", f"Parity pass row {index} is missing accepted tolerance."))
    if not str(row.get("explanation") or "").strip():
        blockers.append(_finding("parity_pass_row", f"Parity pass row {index} is missing explanation."))


def _check_parity_report_identity(
    bundle_report: Mapping[str, Any],
    parity_report: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    bundle_report_id = str(bundle_report.get("id") or "").strip()
    parity_report_id = str(parity_report.get("id") or "").strip()
    bundle_template_key = str(bundle_report.get("template_key") or "").strip()
    parity_template_key = str(parity_report.get("template_key") or "").strip()
    if not bundle_report_id:
        blockers.append(_finding("report_identity", "Evidence bundle report.id is required."))
    if not parity_report_id:
        blockers.append(_finding("report_identity", "Parity comparison report.id is required."))
    elif bundle_report_id and parity_report_id != bundle_report_id:
        blockers.append(_finding("report_identity", "Parity comparison report.id does not match evidence bundle."))
    if not bundle_template_key:
        blockers.append(_finding("report_identity", "Evidence bundle report.template_key is required."))
    if not parity_template_key:
        blockers.append(_finding("report_identity", "Parity comparison report.template_key is required."))
    elif bundle_template_key and parity_template_key != bundle_template_key:
        blockers.append(
            _finding("report_identity", "Parity comparison report.template_key does not match evidence bundle.")
        )


def _check_instagram_deferred(bundle: Mapping[str, Any], blockers: list[dict[str, str]], checks: list[dict[str, str]]) -> None:
    serialized = json.dumps(bundle, sort_keys=True, default=str).lower()
    if "organic_instagram" in serialized or "instagram" in serialized:
        blockers.append(_finding("instagram", "Instagram appears in v1 evidence and must remain deferred."))
    else:
        checks.append(_passed("instagram", "Instagram is absent from v1 evidence bundle."))


def _check_sensitive_payloads(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    serialized = json.dumps({"bundle": bundle, "parity": parity or {}}, sort_keys=True, default=str)
    matches = sorted({pattern.pattern for pattern in SENSITIVE_PATTERNS if pattern.search(serialized)})
    if matches:
        blockers.append(_finding("sensitive_payload", f"Sensitive pattern(s) found in evidence artifacts: {len(matches)}."))
    else:
        checks.append(_passed("sensitive_payload", "No high-signal sensitive patterns found in evidence artifacts."))


def _finding(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _passed(code: str, message: str) -> dict[str, str]:
    return {"code": code, "status": "pass", "message": message}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SLB Evidence Validation",
        "",
        f"- Readiness status: `{result.get('readiness_status')}`",
        f"- Blockers: `{result.get('blocker_count')}`",
        f"- Warnings: `{result.get('warning_count')}`",
        "",
        "## Blockers",
        "",
    ]
    for finding in result.get("blockers", []):
        if isinstance(finding, Mapping):
            lines.append(f"- `{finding.get('code')}`: {finding.get('message')}")
    if not result.get("blockers"):
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    for finding in result.get("warnings", []):
        if isinstance(finding, Mapping):
            lines.append(f"- `{finding.get('code')}`: {finding.get('message')}")
    if not result.get("warnings"):
        lines.append("- None")
    return "\n".join(lines)
