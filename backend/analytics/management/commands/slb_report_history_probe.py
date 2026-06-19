"""Probe primary and retained-history coverage for an SLB report."""

from __future__ import annotations

import json
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from analytics.models import ReportDefinition
from analytics.reporting_report_preview import (
    ReportingReportPreviewError,
    build_report_diagnostics,
    build_report_preview,
)
from analytics.reporting_source_health import build_reporting_source_health


REQUIRED_DATASETS = ("paid_meta_ads", "organic_facebook_page", "content_ops")
BLOCKING_STATUSES = {
    "permission_missing",
    "unsupported_metric",
    "missing_history",
    "not_previously_synced",
}
WARNING_STATUSES = {"partial", "stale", "source_disconnected"}


class Command(BaseCommand):
    help = "Build a redacted monthly and 90-day retained-history probe for an SLB report."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True)
        parser.add_argument("--primary-start-date", required=True)
        parser.add_argument("--primary-end-date", required=True)
        parser.add_argument("--history-start-date", required=True)
        parser.add_argument("--history-end-date", required=True)

    def handle(self, *args, **options):
        report = (
            ReportDefinition.all_objects.select_related("tenant")
            .filter(id=options["report_id"])
            .first()
        )
        if report is None:
            raise CommandError("Report not found.")

        with tenant_context(str(report.tenant_id)):
            try:
                primary = _probe(
                    report=report,
                    label="primary_month",
                    start_date=options["primary_start_date"],
                    end_date=options["primary_end_date"],
                )
                history = _probe(
                    report=report,
                    label="retained_90_day",
                    start_date=options["history_start_date"],
                    end_date=options["history_end_date"],
                )
            except ReportingReportPreviewError as exc:
                raise CommandError("; ".join(exc.errors)) from exc

            result = {
                "schema_version": "slb_history_probe.v1",
                "report": {
                    "id": str(report.id),
                    "tenant_id": str(report.tenant_id),
                    "template_key": str(report.layout.get("template_key") if isinstance(report.layout, Mapping) else ""),
                },
                "probes": {
                    "primary_month": primary,
                    "retained_90_day": history,
                },
                "dataset_matrix": _dataset_matrix(primary=primary, history=history),
                "source_health": build_reporting_source_health(tenant=report.tenant),
            }
            log_audit_event(
                tenant=report.tenant,
                user=None,
                action="report_history_probe_generated",
                resource_type="report_definition",
                resource_id=report.id,
                metadata={
                    "redacted": True,
                    "primary_start_date": options["primary_start_date"],
                    "primary_end_date": options["primary_end_date"],
                    "history_start_date": options["history_start_date"],
                    "history_end_date": options["history_end_date"],
                },
            )

        self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))


def _probe(*, report: ReportDefinition, label: str, start_date: str, end_date: str) -> dict[str, Any]:
    payload = {"date_range": "custom", "start_date": start_date, "end_date": end_date}
    preview = build_report_preview(report=report, payload=payload)
    diagnostics = build_report_diagnostics(report=report, payload=payload)
    datasets = {
        str(row.get("dataset") or ""): _diagnostic_dataset_summary(row)
        for row in diagnostics.get("datasets", [])
        if isinstance(row, Mapping) and row.get("dataset")
    }
    return {
        "label": label,
        "date_range": preview["date_range"],
        "preview_hash": preview["preview_hash"],
        "export_ready": preview["export_ready"],
        "coverage_summary": preview["coverage_summary"],
        "blocking_reasons": preview["blocking_reasons"],
        "warnings": preview["warnings"],
        "datasets": datasets,
    }


def _diagnostic_dataset_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": str(row.get("coverage_status") or ""),
        "freshness_status": str(row.get("freshness_status") or ""),
        "retained_range": row.get("retained_range") if isinstance(row.get("retained_range"), Mapping) else {},
        "row_count": int(row.get("row_count") or 0),
        "source_label": str(row.get("source_label") or ""),
        "last_successful_sync_at": row.get("last_successful_sync_at"),
        "recommended_next_action": str(row.get("recommended_next_action") or ""),
    }


def _dataset_matrix(*, primary: Mapping[str, Any], history: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    primary_datasets = primary.get("datasets") if isinstance(primary.get("datasets"), Mapping) else {}
    history_datasets = history.get("datasets") if isinstance(history.get("datasets"), Mapping) else {}
    for dataset in REQUIRED_DATASETS:
        primary_row = primary_datasets.get(dataset) if isinstance(primary_datasets.get(dataset), Mapping) else {}
        history_row = history_datasets.get(dataset) if isinstance(history_datasets.get(dataset), Mapping) else {}
        rows.append(
            {
                "dataset": dataset,
                "primary_status": str(primary_row.get("coverage_status") or "missing_history"),
                "primary_row_count": int(primary_row.get("row_count") or 0),
                "primary_retained_range": primary_row.get("retained_range") or {},
                "history_status": str(history_row.get("coverage_status") or "missing_history"),
                "history_row_count": int(history_row.get("row_count") or 0),
                "history_retained_range": history_row.get("retained_range") or {},
                "decision": _decision(primary_row=primary_row, history_row=history_row),
            }
        )
    return rows


def _decision(*, primary_row: Mapping[str, Any], history_row: Mapping[str, Any]) -> str:
    statuses = {
        str(primary_row.get("coverage_status") or "missing_history"),
        str(history_row.get("coverage_status") or "missing_history"),
    }
    if statuses & BLOCKING_STATUSES:
        return "blocked_retained_history"
    if int(primary_row.get("row_count") or 0) <= 0 or int(history_row.get("row_count") or 0) <= 0:
        return "blocked_no_aggregate_rows"
    if statuses & WARNING_STATUSES:
        return "review_required"
    return "ready_for_review"
