"""Scheduled report delivery helpers for report.v1 dry-run evidence."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from analytics.models import ReportDefinition, ReportExportJob

from .reporting_report_preview import (
    ReportingReportExportBlocked,
    build_report_export_metadata_from_snapshot,
    build_report_snapshot,
    build_saved_report_layout_snapshot,
)


def create_scheduled_report_dry_run(
    *,
    report: ReportDefinition,
    requested_by=None,
    export_format: str = ReportExportJob.FORMAT_PDF,
    payload: dict[str, Any] | None = None,
) -> ReportExportJob:
    """Create a sanitized scheduled-delivery dry-run export job."""

    now = timezone.now()
    snapshot = build_report_snapshot(report=report, payload=payload)
    try:
        report_preview = build_report_export_metadata_from_snapshot(snapshot)
    except ReportingReportExportBlocked as exc:
        job = ReportExportJob.objects.create(
            tenant=report.tenant,
            report=report,
            requested_by=requested_by,
            export_format=export_format,
            status=ReportExportJob.STATUS_FAILED,
            error_message="Scheduled dry-run blocked by coverage.",
            completed_at=now,
            metadata={
                "delivery_status": {
                    "mode": "dry_run",
                    "status": "blocked_by_coverage",
                    "sanitized": True,
                },
                "blocking_reasons": exc.errors,
                "coverage_summary": snapshot.get("coverage_summary") or {},
                "date_range": snapshot.get("date_range") or {},
                "preview_hash": snapshot.get("preview_hash") or "",
                "report": snapshot.get("report") or {},
                "report_id": str(report.id),
            },
        )
        _touch_scheduled_at(report=report, timestamp=now)
        return job

    metadata: dict[str, Any] = {
        "report_preview": {
            **report_preview,
            "delivery_status": {
                "mode": "dry_run",
                "status": "queued",
                "sanitized": True,
            },
        },
        "delivery_status": {
            "mode": "dry_run",
            "status": "queued",
            "sanitized": True,
        },
        "preview_hash": report_preview["preview_hash"],
        "coverage_summary": report_preview["coverage_summary"],
        "blocking_reasons": report_preview["blocking_reasons"],
    }
    report_layout = build_saved_report_layout_snapshot(
        report=report,
        requested_by=requested_by,
        snapshot=snapshot,
    )
    if report_layout is not None:
        metadata["report_layout"] = report_layout
    job = ReportExportJob.objects.create(
        tenant=report.tenant,
        report=report,
        requested_by=requested_by,
        export_format=export_format,
        status=ReportExportJob.STATUS_QUEUED,
        metadata=metadata,
    )
    _touch_scheduled_at(report=report, timestamp=now)
    return job


def _touch_scheduled_at(*, report: ReportDefinition, timestamp) -> None:
    report.last_scheduled_at = timestamp
    report.save(update_fields=["last_scheduled_at", "updated_at"])
