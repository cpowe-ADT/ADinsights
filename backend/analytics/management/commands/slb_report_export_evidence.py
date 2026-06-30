"""Generate fixed-range SLB export jobs for evidence collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from analytics.models import ReportDefinition, ReportExportJob
from analytics.reporting_delivery import create_scheduled_report_dry_run
from analytics.reporting_evidence_availability import (
    build_report_data_availability_evidence_summary,
)
from analytics.reporting_report_preview import (
    ReportingReportPreviewError,
    build_report_export_metadata_from_snapshot,
    build_report_snapshot,
    build_saved_report_layout_snapshot,
)
from analytics.tasks import run_report_export_job


DEFAULT_EXPORT_FORMATS = (
    ReportExportJob.FORMAT_CSV,
    ReportExportJob.FORMAT_PDF,
    ReportExportJob.FORMAT_PNG,
)


class Command(BaseCommand):
    help = "Create fixed-target SLB CSV/PDF/PNG exports and scheduled dry-run evidence."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)
        parser.add_argument(
            "--format",
            action="append",
            dest="formats",
            choices=[
                ReportExportJob.FORMAT_CSV,
                ReportExportJob.FORMAT_PDF,
                ReportExportJob.FORMAT_PNG,
            ],
            default=None,
            help="Export format to generate. Repeat to limit the default csv/pdf/png set.",
        )
        parser.add_argument(
            "--scheduled-dry-run-format",
            choices=[
                ReportExportJob.FORMAT_CSV,
                ReportExportJob.FORMAT_PDF,
                ReportExportJob.FORMAT_PNG,
            ],
            default=ReportExportJob.FORMAT_PDF,
        )
        parser.add_argument(
            "--skip-scheduled-dry-run",
            action="store_true",
            help="Generate only manual export jobs. G5/G2-G9 evidence normally requires the dry-run.",
        )

    def handle(self, *args, **options):
        report = (
            ReportDefinition.all_objects.select_related("tenant")
            .filter(id=options["report_id"])
            .first()
        )
        if report is None:
            raise CommandError("Report not found.")

        formats = tuple(dict.fromkeys(options.get("formats") or DEFAULT_EXPORT_FORMATS))
        payload = {
            "date_range": "custom",
            "start_date": options["start_date"],
            "end_date": options["end_date"],
        }

        with tenant_context(str(report.tenant_id)):
            try:
                snapshot = build_report_snapshot(report=report, payload=payload)
            except ReportingReportPreviewError as exc:
                raise CommandError("; ".join(exc.errors)) from exc

            data_availability = build_report_data_availability_evidence_summary(
                report=report,
                payload=payload,
            )
            if not snapshot.get("export_ready"):
                scheduled_dry_run = None
                if not options["skip_scheduled_dry_run"]:
                    scheduled_dry_run = _create_blocked_scheduled_dry_run(
                        report=report,
                        export_format=options["scheduled_dry_run_format"],
                        payload=payload,
                    )
                evidence = _blocked_evidence(
                    report=report,
                    snapshot=snapshot,
                    formats=formats,
                    scheduled_dry_run=scheduled_dry_run,
                    data_availability=data_availability,
                )
                log_audit_event(
                    tenant=report.tenant,
                    user=None,
                    action="report_export_evidence_blocked",
                    resource_type="report_definition",
                    resource_id=report.id,
                    metadata={
                        "redacted": True,
                        "formats": sorted(formats),
                        "scheduled_dry_run": scheduled_dry_run is not None,
                        "start_date": options["start_date"],
                        "end_date": options["end_date"],
                        "preview_hash": evidence["preview_hash"],
                        "blocking_reason_count": len(evidence["blocking_reasons"]),
                    },
                )
                self.stdout.write(
                    json.dumps(evidence, indent=2, sort_keys=True, default=str)
                )
                raise CommandError(
                    "SLB export evidence blocked by coverage; see JSON summary."
                )

            report_preview = build_report_export_metadata_from_snapshot(snapshot)
            exports = {
                export_format: _create_and_run_export(
                    report=report,
                    export_format=export_format,
                    report_preview=report_preview,
                )
                for export_format in formats
            }

            scheduled_dry_run = None
            if not options["skip_scheduled_dry_run"]:
                scheduled_dry_run = _create_and_run_scheduled_dry_run(
                    report=report,
                    export_format=options["scheduled_dry_run_format"],
                    payload=payload,
                )

            evidence = {
                "schema_version": "slb_export_evidence_run.v1",
                "report": {
                    "id": str(report.id),
                    "tenant_id": str(report.tenant_id),
                    "template_key": report_preview.get("template_key") or "",
                    "schema_version": report_preview.get("report_schema_version") or "",
                },
                "date_range": report_preview.get("date_range") or payload,
                "preview_hash": report_preview.get("preview_hash") or "",
                "export_ready": True,
                "coverage_summary": report_preview.get("coverage_summary") or {},
                "data_availability": dict(data_availability),
                "blocking_reasons": [
                    str(reason) for reason in report_preview.get("blocking_reasons", [])
                ],
                "warnings": [
                    str(warning) for warning in report_preview.get("warnings", [])
                ],
                "exports": exports,
                "scheduled_dry_run": scheduled_dry_run,
                "delivery": _delivery_summary(scheduled_dry_run),
            }

            log_audit_event(
                tenant=report.tenant,
                user=None,
                action="report_export_evidence_generated",
                resource_type="report_definition",
                resource_id=report.id,
                metadata={
                    "redacted": True,
                    "formats": sorted(formats),
                    "scheduled_dry_run": scheduled_dry_run is not None,
                    "start_date": options["start_date"],
                    "end_date": options["end_date"],
                    "preview_hash": evidence["preview_hash"],
                },
            )

        self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True, default=str))


def _create_blocked_scheduled_dry_run(
    *,
    report: ReportDefinition,
    export_format: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    job = create_scheduled_report_dry_run(
        report=report,
        requested_by=None,
        export_format=export_format,
        payload=dict(payload),
    )
    job.refresh_from_db()
    evidence = _job_evidence(job)
    delivery_status = (
        evidence.get("delivery_status")
        if isinstance(evidence.get("delivery_status"), Mapping)
        else {}
    )
    if delivery_status.get("status") != "blocked_by_coverage":
        raise CommandError(
            "Blocked export evidence did not record a blocked scheduled dry-run."
        )
    return evidence


def _create_and_run_export(
    *,
    report: ReportDefinition,
    export_format: str,
    report_preview: Mapping[str, Any],
) -> dict[str, Any]:
    report_layout = build_saved_report_layout_snapshot(
        report=report,
        requested_by=None,
        snapshot=report_preview.get("report_snapshot"),
    )
    metadata: dict[str, Any] = {"report_preview": dict(report_preview)}
    if report_layout is not None:
        metadata["report_layout"] = report_layout
    job = ReportExportJob.objects.create(
        tenant=report.tenant,
        report=report,
        requested_by=None,
        export_format=export_format,
        status=ReportExportJob.STATUS_QUEUED,
        metadata=metadata,
    )
    result = run_report_export_job.run(str(job.id))
    job.refresh_from_db()
    if job.status != ReportExportJob.STATUS_COMPLETED:
        raise CommandError(
            f"{export_format} export failed with status {job.status}: {job.error_message or result}"
        )
    evidence = _job_evidence(job)
    if evidence["byte_count"] <= 0:
        raise CommandError(
            f"{export_format} export completed without a non-empty artifact."
        )
    return evidence


def _create_and_run_scheduled_dry_run(
    *,
    report: ReportDefinition,
    export_format: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    job = create_scheduled_report_dry_run(
        report=report,
        requested_by=None,
        export_format=export_format,
        payload=dict(payload),
    )
    if job.status != ReportExportJob.STATUS_QUEUED:
        raise CommandError(
            f"Scheduled dry-run did not queue: {job.error_message or job.status}"
        )
    result = run_report_export_job.run(str(job.id))
    job.refresh_from_db()
    if job.status != ReportExportJob.STATUS_COMPLETED:
        raise CommandError(
            f"Scheduled dry-run failed with status {job.status}: {job.error_message or result}"
        )
    evidence = _job_evidence(job)
    delivery_status = (
        evidence.get("delivery_status")
        if isinstance(evidence.get("delivery_status"), Mapping)
        else {}
    )
    if delivery_status.get("status") != "rendered":
        raise CommandError(
            "Scheduled dry-run completed without rendered delivery status."
        )
    return evidence


def _blocked_evidence(
    *,
    report: ReportDefinition,
    snapshot: Mapping[str, Any],
    formats: tuple[str, ...],
    scheduled_dry_run: Mapping[str, Any] | None,
    data_availability: Mapping[str, Any],
) -> dict[str, Any]:
    report_payload = (
        snapshot.get("report") if isinstance(snapshot.get("report"), Mapping) else {}
    )
    preview_hash = str(snapshot.get("preview_hash") or "")
    return {
        "schema_version": "slb_export_evidence_run.v1",
        "status": "blocked_by_coverage",
        "report": {
            "id": str(report.id),
            "tenant_id": str(report.tenant_id),
            "template_key": report_payload.get("template_key") or "",
            "schema_version": report_payload.get("schema_version") or "",
        },
        "date_range": snapshot.get("date_range") or {},
        "preview_hash": preview_hash,
        "export_ready": False,
        "coverage_summary": snapshot.get("coverage_summary") or {},
        "data_availability": dict(data_availability),
        "blocking_reasons": [
            str(reason) for reason in snapshot.get("blocking_reasons", [])
        ],
        "warnings": [str(warning) for warning in snapshot.get("warnings", [])],
        "exports": {
            export_format: {
                "job_id": "",
                "format": export_format,
                "status": "blocked_by_coverage",
                "artifact_path": "",
                "byte_count": 0,
                "preview_hash": preview_hash,
                "snapshot_preview_hash": preview_hash,
                "source": "report_v1_snapshot",
                "row_count": 0,
                "delivery_status": {},
                "completed_at": None,
            }
            for export_format in formats
        },
        "scheduled_dry_run": scheduled_dry_run,
        "delivery": _delivery_summary(scheduled_dry_run),
    }


def _job_evidence(job: ReportExportJob) -> dict[str, Any]:
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
    artifact = _artifact_file_path(job.artifact_path) if job.artifact_path else None
    byte_count = (
        artifact.stat().st_size
        if artifact is not None and artifact.exists() and artifact.is_file()
        else 0
    )
    return {
        "job_id": str(job.id),
        "format": job.export_format,
        "status": job.status,
        "artifact_path": job.artifact_path,
        "byte_count": byte_count,
        "preview_hash": metadata.get("preview_hash")
        or report_preview.get("preview_hash")
        or "",
        "snapshot_preview_hash": report_snapshot.get("preview_hash") or "",
        "source": metadata.get("source") or "",
        "row_count": int(metadata.get("row_count") or 0),
        "report_layout_source": str(metadata.get("report_layout_source") or ""),
        "report_layout_governed_widget_append_count": _report_layout_append_count(
            metadata.get("report_layout")
        ),
        "delivery_status": _safe_delivery_status(metadata.get("delivery_status")),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


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
    allowed = {"mode", "status", "sanitized", "error_type", "rendered_at"}
    return {str(key): value.get(key) for key in allowed if key in value}


def _delivery_summary(scheduled_dry_run: Mapping[str, Any] | None) -> dict[str, Any]:
    if not scheduled_dry_run:
        return {
            "scheduled_dry_run_status": "skipped",
            "scheduled_dry_run_job_id": "",
            "sanitized": True,
        }
    delivery_status = (
        scheduled_dry_run.get("delivery_status")
        if isinstance(scheduled_dry_run.get("delivery_status"), Mapping)
        else {}
    )
    return {
        "scheduled_dry_run_status": str(
            delivery_status.get("status") or scheduled_dry_run.get("status") or ""
        ),
        "scheduled_dry_run_job_id": str(scheduled_dry_run.get("job_id") or ""),
        "scheduled_dry_run_format": str(scheduled_dry_run.get("format") or ""),
        "sanitized": delivery_status.get("sanitized") is True,
    }
