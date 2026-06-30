"""Generate ADinsights-side SLB parity evidence rows for a fixed date range."""

from __future__ import annotations

import json
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from analytics.models import ReportDefinition
from analytics.reporting_report_preview import (
    ReportingReportPreviewError,
    build_report_preview,
)

_NO_DATA_COVERAGE_STATUSES = {"missing_history", "not_previously_synced"}


class Command(BaseCommand):
    help = "Render aggregate-only SLB report parity evidence rows for manual DashThis comparison."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)
        parser.add_argument("--format", choices=["json", "markdown"], default="json")

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
                preview = build_report_preview(
                    report=report,
                    payload={
                        "date_range": "custom",
                        "start_date": options["start_date"],
                        "end_date": options["end_date"],
                    },
                )
            except ReportingReportPreviewError as exc:
                raise CommandError("; ".join(exc.errors)) from exc

            evidence = {
                "report_id": str(report.id),
                "tenant_id": str(report.tenant_id),
                "date_range": {
                    "start_date": options["start_date"],
                    "end_date": options["end_date"],
                },
                "preview_hash": preview["preview_hash"],
                "export_ready": preview["export_ready"],
                "coverage_summary": preview["coverage_summary"],
                "rows": _evidence_rows(preview),
            }
            log_audit_event(
                tenant=report.tenant,
                user=None,
                action="report_parity_evidence_generated",
                resource_type="report_definition",
                resource_id=report.id,
                metadata={
                    "redacted": True,
                    "start_date": options["start_date"],
                    "end_date": options["end_date"],
                    "preview_hash": preview["preview_hash"],
                    "row_count": len(evidence["rows"]),
                },
            )

        if options["format"] == "markdown":
            self.stdout.write(_markdown(evidence))
        else:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True, default=str))


def _evidence_rows(preview: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in preview.get("pages", []):
        if not isinstance(page, Mapping):
            continue
        for section in page.get("sections", []):
            if not isinstance(section, Mapping):
                continue
            for widget in section.get("widgets", []):
                if not isinstance(widget, Mapping):
                    continue
                rows.extend(_widget_rows(page=page, section=section, widget=widget))
    return rows


def _widget_rows(
    *,
    page: Mapping[str, Any],
    section: Mapping[str, Any],
    widget: Mapping[str, Any],
) -> list[dict[str, Any]]:
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    coverage = widget.get("coverage") if isinstance(widget.get("coverage"), Mapping) else {}
    base = {
        "page_id": str(page.get("id") or ""),
        "section_id": str(section.get("id") or ""),
        "widget_id": str(widget.get("widget_id") or ""),
        "dataset": str(widget.get("dataset") or ""),
        "coverage_status": str(coverage.get("coverage_status") or widget.get("status") or ""),
        "source_label": str(coverage.get("source_label") or ""),
        "dashthis_value": None,
        "absolute_delta": None,
        "percentage_delta": None,
        "accepted_tolerance": None,
        "result": "blocked_missing_dashthis_value",
        "explanation": "",
    }
    no_data_coverage = base["coverage_status"] in _NO_DATA_COVERAGE_STATUSES
    kind = str(data.get("kind") or "")
    if kind == "kpi":
        return [
            {
                **base,
                "metric": str(metric.get("key") or ""),
                "label": str(metric.get("label") or metric.get("key") or ""),
                "adinsights_value": _evidence_value(
                    metric.get("value"), no_data_coverage=no_data_coverage
                ),
            }
            for metric in data.get("metrics", [])
            if isinstance(metric, Mapping)
        ]
    if kind in {"table", "bar", "timeseries"}:
        output = []
        for row in data.get("rows", [])[:50]:
            if not isinstance(row, Mapping):
                continue
            metrics = [
                key
                for key, value in row.items()
                if isinstance(value, (int, float)) and key not in {"date"}
            ]
            for metric in metrics:
                output.append(
                    {
                        **base,
                        "metric": metric,
                        "label": str(
                            row.get("name")
                            or row.get("campaign")
                            or row.get("date")
                            or metric
                        ),
                        "adinsights_value": _evidence_value(
                            row.get(metric), no_data_coverage=no_data_coverage
                        ),
                    }
                )
        return output
    return []


def _evidence_value(value: object, *, no_data_coverage: bool) -> object:
    if no_data_coverage:
        return None
    return value


def _markdown(evidence: Mapping[str, Any]) -> str:
    lines = [
        "# SLB Parity Evidence",
        "",
        f"- Report ID: `{evidence['report_id']}`",
        f"- Date range: `{evidence['date_range']['start_date']}` to `{evidence['date_range']['end_date']}`",
        f"- Preview hash: `{evidence['preview_hash']}`",
        f"- Export ready: `{evidence['export_ready']}`",
        "",
        "| Dataset | Metric | Label | ADinsights | DashThis | Delta | % Delta | Tolerance | Result |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in evidence["rows"]:
        lines.append(
            "| {dataset} | {metric} | {label} | {value} |  |  |  |  | blocked_missing_dashthis_value |".format(
                dataset=row["dataset"],
                metric=row["metric"],
                label=str(row["label"]).replace("|", "\\|"),
                value=row["adinsights_value"],
            )
        )
    return "\n".join(lines)
