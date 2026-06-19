"""Report.v1 preview assembly over governed widget preview data."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from django.utils import timezone

from analytics.models import ReportDefinition

from .reporting_catalog import (
    REPORT_SCHEMA_VERSION,
    ReportingCatalogValidationError,
    is_report_v1_layout,
    validate_dashboard_widget,
    validate_report_layout,
)
from .reporting_preview import ReportingWidgetPreviewError, build_widget_preview
from .reporting_source_health import build_reporting_source_health


REPORT_EXPORT_BLOCKING_COVERAGE_STATUSES = {
    "missing_history",
    "not_previously_synced",
    "permission_missing",
    "unsupported_metric",
}


class ReportingReportPreviewError(ValueError):
    """Safe API-facing report preview error."""

    def __init__(self, errors: list[str], *, status_code: int = 400) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
        self.status_code = status_code


class ReportingReportExportBlocked(ReportingReportPreviewError):
    """Raised when report.v1 coverage blocks export generation."""


def build_report_preview(
    *,
    report: ReportDefinition,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a report.v1 preview payload without live provider calls."""

    payload = payload or {}
    try:
        layout = validate_report_layout(report.layout)
    except ReportingCatalogValidationError as exc:
        raise ReportingReportPreviewError(exc.errors) from exc

    if not is_report_v1_layout(layout):
        raise ReportingReportPreviewError(["report preview is only available for report.v1 layouts."])

    widgets = [widget for widget in layout.get("widgets", []) if isinstance(widget, Mapping)]
    widgets_by_id = {str(widget.get("id")): dict(widget) for widget in widgets}
    context = _preview_context(report=report, payload=payload)
    rendered_pages: list[dict[str, Any]] = []
    rendered_widgets: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    for page in layout.get("pages", []):
        if not isinstance(page, Mapping):
            continue
        rendered_sections: list[dict[str, Any]] = []
        for section in page.get("sections", []):
            if not isinstance(section, Mapping):
                continue
            section_widgets = []
            for widget_id in section.get("widget_ids", []):
                widget = widgets_by_id.get(str(widget_id))
                if widget is None:
                    continue
                preview = _preview_report_widget(
                    tenant=report.tenant,
                    widget=widget,
                    context=context,
                )
                section_widgets.append(preview)
                rendered_widgets.append(preview)
                warnings.extend(str(item) for item in preview.get("warnings", []))
                if preview.get("status") in {"blocked", "error"}:
                    reason = str(preview.get("error") or preview.get("widget_id") or "widget blocked")
                    blocking_reasons.append(reason)
            rendered_sections.append(
                {
                    "id": str(section.get("id") or ""),
                    "type": str(section.get("type") or "widget_group"),
                    "widgets": section_widgets,
                }
            )
        rendered_pages.append(
            {
                "id": str(page.get("id") or ""),
                "title": str(page.get("title") or ""),
                "sections": rendered_sections,
            }
        )

    coverage_summary = _coverage_summary(rendered_widgets)
    blocking_reasons.extend(_coverage_blocking_reasons(coverage_summary))
    blocking_reasons = sorted(set(blocking_reasons))
    export_ready = not blocking_reasons
    preview_payload = {
        "report": {
            "id": str(report.id),
            "name": report.name,
            "template_key": str(layout.get("template_key") or report.filters.get("template_key") or ""),
            "schema_version": REPORT_SCHEMA_VERSION,
            "catalog_schema_version": str(layout.get("catalog_schema_version") or "reporting_catalog.v1"),
        },
        "generated_at": timezone.now().isoformat(),
        "date_range": context["date_range"],
        "pages": rendered_pages,
        "coverage_summary": coverage_summary,
        "warnings": sorted(set(warnings)),
        "blocking_reasons": blocking_reasons,
        "export_ready": export_ready,
    }
    preview_payload["preview_hash"] = _preview_hash(preview_payload)
    return preview_payload


def build_report_export_metadata(*, report: ReportDefinition) -> dict[str, Any]:
    snapshot = build_report_snapshot(report=report)
    if not snapshot.get("export_ready"):
        reasons = [str(reason) for reason in snapshot.get("blocking_reasons", [])]
        raise ReportingReportExportBlocked(
            reasons or ["report.v1 export is blocked by coverage or validation."]
        )
    return {
        "report_schema_version": snapshot["report"]["schema_version"],
        "template_key": snapshot["report"]["template_key"],
        "catalog_schema_version": snapshot["report"]["catalog_schema_version"],
        "generated_at": snapshot["generated_at"],
        "date_range": snapshot["date_range"],
        "coverage_summary": snapshot["coverage_summary"],
        "blocking_reasons": snapshot["blocking_reasons"],
        "preview_hash": snapshot["preview_hash"],
        "export_ready": snapshot["export_ready"],
        "report_snapshot": snapshot,
        "delivery_status": {
            "mode": "manual_export",
            "status": "queued",
            "sanitized": True,
        },
    }


def build_report_snapshot(
    *,
    report: ReportDefinition,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the durable report.v1 render snapshot stored with exports."""

    preview = build_report_preview(report=report, payload=payload)
    return {
        "report": preview["report"],
        "generated_at": preview["generated_at"],
        "date_range": preview["date_range"],
        "pages": preview["pages"],
        "coverage_summary": preview["coverage_summary"],
        "warnings": preview["warnings"],
        "blocking_reasons": preview["blocking_reasons"],
        "export_ready": preview["export_ready"],
        "preview_hash": preview["preview_hash"],
    }


def build_report_diagnostics(
    *,
    report: ReportDefinition,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build tenant-scoped support diagnostics without raw provider/user data."""

    try:
        snapshot = build_report_snapshot(report=report, payload=payload)
        preview_error = None
    except ReportingReportPreviewError as exc:
        snapshot = {}
        preview_error = {
            "status": "validation_failed",
            "errors": exc.errors,
        }

    datasets = []
    coverage_summary = snapshot.get("coverage_summary") if isinstance(snapshot, Mapping) else {}
    for dataset in (coverage_summary or {}).get("datasets", []):
        if not isinstance(dataset, Mapping):
            continue
        statuses = dataset.get("statuses") if isinstance(dataset.get("statuses"), Mapping) else {}
        primary_status = _primary_status(statuses)
        datasets.append(
            {
                "dataset": str(dataset.get("dataset") or ""),
                "coverage_status": primary_status,
                "freshness_status": primary_status,
                "retained_range": {
                    "start_date": dataset.get("covered_start_date"),
                    "end_date": dataset.get("covered_end_date"),
                },
                "row_count": int(dataset.get("row_count") or 0),
                "source_label": dataset.get("source_label") or str(dataset.get("dataset") or ""),
                "last_successful_sync_at": dataset.get("last_successful_sync_at"),
                "notes": [str(note) for note in dataset.get("notes", [])],
                "recommended_next_action": _recommended_next_action(primary_status),
            }
        )

    export_history = []
    for job in report.export_jobs.filter(tenant_id=report.tenant_id).order_by("-created_at")[:10]:
        metadata = job.metadata if isinstance(job.metadata, Mapping) else {}
        report_preview = metadata.get("report_preview") if isinstance(metadata.get("report_preview"), Mapping) else {}
        delivery_status = (
            metadata.get("delivery_status") if isinstance(metadata.get("delivery_status"), Mapping) else {}
        )
        export_history.append(
            {
                "id": str(job.id),
                "format": job.export_format,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "preview_hash": metadata.get("preview_hash") or report_preview.get("preview_hash"),
                "delivery_status": delivery_status.get("status") or "",
                "blocking_reasons": (
                    metadata.get("blocking_reasons")
                    or report_preview.get("blocking_reasons")
                    or []
                ),
            }
        )

    return {
        "report": {
            "id": str(report.id),
            "name": report.name,
            "schema_version": (
                snapshot.get("report", {}).get("schema_version")
                if isinstance(snapshot.get("report"), Mapping)
                else ""
            ),
            "template_key": (
                snapshot.get("report", {}).get("template_key")
                if isinstance(snapshot.get("report"), Mapping)
                else ""
            ),
        },
        "generated_at": timezone.now().isoformat(),
        "date_range": snapshot.get("date_range") if snapshot else {},
        "datasets": datasets,
        "coverage_summary": coverage_summary or {},
        "blocking_reasons": snapshot.get("blocking_reasons", []) if snapshot else [],
        "export_ready": bool(snapshot.get("export_ready")) if snapshot else False,
        "preview_hash": snapshot.get("preview_hash") if snapshot else "",
        "preview_error": preview_error,
        "export_history": export_history,
        "source_health": build_reporting_source_health(tenant=report.tenant),
    }


def _primary_status(statuses: Mapping[str, Any]) -> str:
    if not statuses:
        return "missing_history"
    priority = [
        "permission_missing",
        "unsupported_metric",
        "source_disconnected",
        "missing_history",
        "not_previously_synced",
        "partial",
        "stale",
        "fresh",
    ]
    for status in priority:
        if int(statuses.get(status) or 0) > 0:
            return status
    return str(next(iter(statuses.keys())))


def _recommended_next_action(status: str) -> str:
    return {
        "fresh": "No action required.",
        "stale": "Check the last successful sync and rerun the stored-data sync if needed.",
        "partial": "Review retained history before approving export or scheduled delivery.",
        "source_disconnected": "Reconnect the source; retained history can still support limited reporting.",
        "missing_history": "Confirm backfill or upload fallback before exporting a client-ready report.",
        "not_previously_synced": "Complete the first sync before using this section in report exports.",
        "permission_missing": "Review source permissions and page/account access.",
        "unsupported_metric": "Remove the unsupported metric or add it to the governed catalog after review.",
    }.get(status, "Review dataset coverage and source configuration.")


def _preview_context(*, report: ReportDefinition, payload: Mapping[str, Any]) -> dict[str, Any]:
    filters = report.filters if isinstance(report.filters, Mapping) else {}
    date_range = {
        "date_range": payload.get("date_range") or filters.get("date_range") or "last_month",
        "start_date": payload.get("start_date") or filters.get("start_date") or "",
        "end_date": payload.get("end_date") or filters.get("end_date") or "",
    }
    return {
        "date_range": date_range,
        "client_id": str(payload.get("client_id") or filters.get("client_id") or "").strip(),
        "account_id": str(payload.get("account_id") or filters.get("account_id") or "").strip(),
        "page_id": str(payload.get("page_id") or filters.get("page_id") or "").strip(),
    }


def _preview_report_widget(*, tenant, widget: dict[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    if widget.get("type") == "report_section":
        try:
            widget = validate_dashboard_widget(widget)
        except ReportingCatalogValidationError as exc:
            return _error_widget(widget=widget, errors=exc.errors, status="error")
        return {
            "widget_id": widget["id"],
            "dataset": widget.get("dataset", "content_ops"),
            "type": "report_section",
            "status": "rendered",
            "data": {
                "kind": "report_section",
                "title": (widget.get("visual") or {}).get("title") if isinstance(widget.get("visual"), Mapping) else "",
                "body": (widget.get("visual") or {}).get("body") if isinstance(widget.get("visual"), Mapping) else "",
            },
            "coverage": _section_coverage(widget),
            "warnings": [],
        }

    try:
        preview = build_widget_preview(
            tenant=tenant,
            payload={
                "widget": widget,
                "date_range": context.get("date_range"),
                "client_id": context.get("client_id"),
                "account_id": context.get("account_id"),
                "page_id": context.get("page_id"),
            },
        )
    except ReportingWidgetPreviewError as exc:
        return _error_widget(
            widget=widget,
            errors=exc.errors,
            status="blocked" if exc.status_code == 409 else "error",
        )

    return {
        **preview,
        "status": "rendered",
    }


def _error_widget(*, widget: Mapping[str, Any], errors: list[str], status: str) -> dict[str, Any]:
    return {
        "widget_id": str(widget.get("id") or ""),
        "dataset": str(widget.get("dataset") or ""),
        "type": str(widget.get("type") or ""),
        "status": status,
        "data": {},
        "coverage": None,
        "warnings": errors,
        "error": "; ".join(errors),
    }


def _section_coverage(widget: Mapping[str, Any]) -> dict[str, Any]:
    today = timezone.localdate().isoformat()
    title = ""
    visual = widget.get("visual")
    if isinstance(visual, Mapping):
        title = str(visual.get("title") or "Report narrative section")
    return {
        "dataset": str(widget.get("dataset") or "content_ops"),
        "requested_start_date": today,
        "requested_end_date": today,
        "covered_start_date": today,
        "covered_end_date": today,
        "coverage_status": "fresh",
        "history_status": "available",
        "freshness_status": "fresh",
        "last_successful_sync_at": None,
        "row_count": 1,
        "source_label": title or "Report narrative section",
        "coverage_note": f"{title or 'Report narrative section'} is manually authored.",
    }


def _coverage_summary(widgets: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    datasets: dict[str, dict[str, Any]] = {}
    for widget in widgets:
        if widget.get("type") == "report_section":
            continue
        coverage = widget.get("coverage")
        if not isinstance(coverage, Mapping):
            continue
        status = str(coverage.get("coverage_status") or "unsupported_metric")
        by_status[status] = by_status.get(status, 0) + 1
        dataset = str(coverage.get("dataset") or widget.get("dataset") or "")
        if not dataset:
            continue
        target = datasets.setdefault(
            dataset,
            {
                "dataset": dataset,
                "statuses": {},
                "row_count": 0,
                "covered_start_date": None,
                "covered_end_date": None,
                "last_successful_sync_at": None,
                "source_label": coverage.get("source_label"),
                "notes": [],
            },
        )
        target["statuses"][status] = target["statuses"].get(status, 0) + 1
        target["row_count"] = int(target.get("row_count") or 0) + int(coverage.get("row_count") or 0)
        target["covered_start_date"] = _min_date(target.get("covered_start_date"), coverage.get("covered_start_date"))
        target["covered_end_date"] = _max_date(target.get("covered_end_date"), coverage.get("covered_end_date"))
        target["last_successful_sync_at"] = _max_date(
            target.get("last_successful_sync_at"),
            coverage.get("last_successful_sync_at"),
        )
        note = str(coverage.get("coverage_note") or "").strip()
        if note and note not in target["notes"]:
            target["notes"].append(note)
    return {
        "by_status": by_status,
        "datasets": sorted(datasets.values(), key=lambda item: item["dataset"]),
    }


def _coverage_blocking_reasons(coverage_summary: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    datasets = coverage_summary.get("datasets")
    if not isinstance(datasets, list):
        return reasons

    for dataset in datasets:
        if not isinstance(dataset, Mapping):
            continue
        statuses = dataset.get("statuses")
        if not isinstance(statuses, Mapping):
            continue
        dataset_name = str(dataset.get("dataset") or "unknown_dataset")
        for status in sorted(REPORT_EXPORT_BLOCKING_COVERAGE_STATUSES):
            count = int(statuses.get(status) or 0)
            if count <= 0:
                continue
            reasons.append(
                f"{dataset_name} has {count} widget(s) with blocking coverage_status {status}."
            )
    return reasons


def _min_date(current: object, candidate: object) -> str | None:
    current_value = str(current) if current else ""
    candidate_value = str(candidate) if candidate else ""
    if not current_value:
        return candidate_value or None
    if not candidate_value:
        return current_value
    return min(current_value, candidate_value)


def _max_date(current: object, candidate: object) -> str | None:
    current_value = str(current) if current else ""
    candidate_value = str(candidate) if candidate else ""
    if not current_value:
        return candidate_value or None
    if not candidate_value:
        return current_value
    return max(current_value, candidate_value)


def _preview_hash(preview_payload: Mapping[str, Any]) -> str:
    stable_payload = {
        key: value
        for key, value in preview_payload.items()
        if key not in {"generated_at", "preview_hash"}
    }
    raw = json.dumps(stable_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
