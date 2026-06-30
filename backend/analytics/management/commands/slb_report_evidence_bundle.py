"""Generate a sanitized fixed-range SLB report evidence bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from analytics.models import ReportDefinition
from analytics.reporting_evidence_availability import (
    build_report_data_availability_evidence_summary,
)
from analytics.reporting_report_preview import (
    ReportingReportPreviewError,
    build_report_diagnostics,
    build_report_preview,
)

from .slb_report_parity_evidence import _evidence_rows


class Command(BaseCommand):
    help = "Render one aggregate-only SLB evidence bundle for fixed-target readiness review."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)

    def handle(self, *args, **options):
        report = (
            ReportDefinition.all_objects.select_related("tenant")
            .filter(id=options["report_id"])
            .first()
        )
        if report is None:
            raise CommandError("Report not found.")

        preview_payload = {
            "date_range": "custom",
            "start_date": options["start_date"],
            "end_date": options["end_date"],
        }
        with tenant_context(str(report.tenant_id)):
            try:
                preview = build_report_preview(report=report, payload=preview_payload)
                diagnostics = build_report_diagnostics(
                    report=report, payload=preview_payload
                )
            except ReportingReportPreviewError as exc:
                raise CommandError("; ".join(exc.errors)) from exc

            bundle = {
                "schema_version": "slb_evidence_bundle.v1",
                "report": preview["report"],
                "tenant_id": str(report.tenant_id),
                "date_range": preview["date_range"],
                "preview_hash": preview["preview_hash"],
                "export_ready": preview["export_ready"],
                "coverage_summary": preview["coverage_summary"],
                "data_availability": build_report_data_availability_evidence_summary(
                    report=report,
                    payload=preview_payload,
                ),
                "blocking_reasons": preview["blocking_reasons"],
                "warnings": preview["warnings"],
                "rendering": _rendering_summary(preview, report.layout),
                "diagnostics": _diagnostics_summary(diagnostics),
                "exports": _export_summary(report),
                "parity_rows": _evidence_rows(preview),
            }
            log_audit_event(
                tenant=report.tenant,
                user=None,
                action="report_evidence_bundle_generated",
                resource_type="report_definition",
                resource_id=report.id,
                metadata={
                    "redacted": True,
                    "start_date": options["start_date"],
                    "end_date": options["end_date"],
                    "preview_hash": preview["preview_hash"],
                    "parity_row_count": len(bundle["parity_rows"]),
                },
            )

        self.stdout.write(json.dumps(bundle, indent=2, sort_keys=True, default=str))


def _rendering_summary(
    preview: Mapping[str, Any],
    layout: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    layout_widgets = _layout_widgets_by_id(layout)
    pages = []
    widgets = []
    widget_count = 0
    for page in preview.get("pages", []):
        if not isinstance(page, Mapping):
            continue
        section_count = 0
        page_widget_count = 0
        statuses: dict[str, int] = {}
        for section in page.get("sections", []):
            if not isinstance(section, Mapping):
                continue
            section_count += 1
            for widget in section.get("widgets", []):
                if not isinstance(widget, Mapping):
                    continue
                page_widget_count += 1
                widget_count += 1
                status = str(widget.get("status") or "unknown")
                statuses[status] = statuses.get(status, 0) + 1
                widget_id = str(widget.get("widget_id") or "")
                widgets.append(
                    _rendered_widget_inventory(
                        page=page,
                        section=section,
                        widget=widget,
                        declared_widget=layout_widgets.get(widget_id),
                    )
                )
        pages.append(
            {
                "id": str(page.get("id") or ""),
                "title": str(page.get("title") or ""),
                "section_count": section_count,
                "widget_count": page_widget_count,
                "statuses": statuses,
            }
        )
    return {
        "page_count": len(pages),
        "widget_count": widget_count,
        "pages": pages,
        "widgets": widgets,
    }


def _layout_widgets_by_id(
    layout: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(layout, Mapping):
        return {}
    widgets = layout.get("widgets")
    if not isinstance(widgets, list):
        return {}
    return {
        str(widget.get("id") or ""): widget
        for widget in widgets
        if isinstance(widget, Mapping) and str(widget.get("id") or "")
    }


def _rendered_widget_inventory(
    *,
    page: Mapping[str, Any],
    section: Mapping[str, Any],
    widget: Mapping[str, Any],
    declared_widget: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    coverage = (
        widget.get("coverage") if isinstance(widget.get("coverage"), Mapping) else {}
    )
    warnings = widget.get("warnings") if isinstance(widget.get("warnings"), list) else []
    inventory = {
        "page_id": str(page.get("id") or ""),
        "section_id": str(section.get("id") or ""),
        "widget_id": str(widget.get("widget_id") or ""),
        "dataset": str(widget.get("dataset") or coverage.get("dataset") or ""),
        "type": str(widget.get("type") or ""),
        "status": str(widget.get("status") or "unknown"),
        "declared_metrics": _declared_list(declared_widget, "metrics"),
        "declared_dimensions": _declared_list(declared_widget, "dimensions"),
        "data_kind": str(data.get("kind") or ""),
        "coverage_status": str(coverage.get("coverage_status") or ""),
        "coverage_row_count": int(coverage.get("row_count") or 0),
        "source_label": str(coverage.get("source_label") or ""),
        "coverage_note_present": bool(str(coverage.get("coverage_note") or "").strip()),
        "warning_count": len(warnings),
    }
    if str(widget.get("type") or "") == "report_section":
        body = str(data.get("body") or "")
        inventory["note"] = {
            "title": str(data.get("title") or ""),
            "body_present": bool(body.strip()),
            "mentions_reach_impressions_unavailable": _mentions_reach_impressions_unavailable(
                body
            ),
        }
    return inventory


def _declared_list(
    widget: Mapping[str, Any] | None,
    key: str,
) -> list[str]:
    if not isinstance(widget, Mapping):
        return []
    value = widget.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _mentions_reach_impressions_unavailable(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return all(
        phrase in normalized
        for phrase in ("reach", "impressions", "unavailable", "meta")
    )


def _diagnostics_summary(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": diagnostics.get("generated_at"),
        "date_range": diagnostics.get("date_range") or {},
        "datasets": diagnostics.get("datasets") or [],
        "blocking_reasons": diagnostics.get("blocking_reasons") or [],
        "export_ready": bool(diagnostics.get("export_ready")),
        "preview_hash": diagnostics.get("preview_hash") or "",
        "preview_error": diagnostics.get("preview_error"),
        "source_health": diagnostics.get("source_health") or {},
        "export_history": diagnostics.get("export_history") or [],
    }


def _export_summary(report: ReportDefinition) -> list[dict[str, Any]]:
    rows = []
    for job in report.export_jobs.filter(tenant_id=report.tenant_id).order_by(
        "-created_at"
    )[:20]:
        metadata = job.metadata if isinstance(job.metadata, Mapping) else {}
        report_preview = (
            metadata.get("report_preview")
            if isinstance(metadata.get("report_preview"), Mapping)
            else {}
        )
        report_snapshot = (
            report_preview.get("report_snapshot")
            if isinstance(report_preview.get("report_snapshot"), Mapping)
            else {}
        )
        artifact_exists = False
        artifact_size = None
        artifact_path = ""
        if job.artifact_path:
            artifact_path = str(job.artifact_path)
            artifact = _artifact_file_path(job.artifact_path)
            if artifact.exists() and artifact.is_file():
                artifact_exists = True
                artifact_size = artifact.stat().st_size
        rows.append(
            {
                "id": str(job.id),
                "format": job.export_format,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "artifact_path": artifact_path,
                "artifact_present": artifact_exists,
                "artifact_size_bytes": artifact_size,
                "source": metadata.get("source") or "",
                "row_count": metadata.get("row_count"),
                "preview_hash": metadata.get("preview_hash")
                or report_preview.get("preview_hash"),
                "snapshot_preview_hash": report_snapshot.get("preview_hash"),
                "report_layout_source": str(
                    metadata.get("report_layout_source") or ""
                ),
                "report_layout_governed_widget_append_count": _report_layout_append_count(
                    metadata.get("report_layout")
                ),
                "delivery_status": _safe_delivery_status(
                    metadata.get("delivery_status")
                ),
                "blocking_reasons": (
                    metadata.get("blocking_reasons")
                    or report_preview.get("blocking_reasons")
                    or []
                ),
            }
        )
    return rows


def _report_layout_append_count(value: object) -> int | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return int(value.get("governed_widget_append_count") or 0)
    except (TypeError, ValueError):
        return 0


def _artifact_file_path(artifact_path: str) -> Path:
    path = Path(artifact_path)
    if artifact_path.startswith("/exports/"):
        return Path(settings.REPORT_EXPORT_ARTIFACT_ROOT) / artifact_path.lstrip("/")
    return path


def _safe_delivery_status(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {"mode", "status", "sanitized", "error_type"}
    return {str(key): value.get(key) for key in allowed if key in value}
