"""Summarize a candidate SLB report target for G1 intake."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from analytics.models import ReportDefinition
from analytics.reporting_catalog import (
    REPORT_SCHEMA_VERSION,
    ReportingCatalogValidationError,
    validate_report_layout,
)
from analytics.reporting_templates import SLB_MONTHLY_TEMPLATE_KEY


SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"bearer\s+[a-z0-9._~+/=-]{20,}",
        r"access_token",
        r"refresh_token",
        r"client_secret",
        r"page_token",
        r"private key",
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        r"raw_payload",
        r"\buser_id\b",
        r"\bprofile_id\b",
        r"\bviewer_id\b",
        r"\bactor_id\b",
    ]
]


class Command(BaseCommand):
    help = "Produce a redacted G1 intake summary for a candidate SLB report.v1 target."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True)

    def handle(self, *args, **options):
        report = ReportDefinition.all_objects.filter(id=options["report_id"]).first()
        if report is None:
            raise CommandError("Report not found.")

        try:
            layout = validate_report_layout(report.layout)
            validation_errors: list[str] = []
        except ReportingCatalogValidationError as exc:
            layout = report.layout if isinstance(report.layout, Mapping) else {}
            validation_errors = exc.errors

        summary = build_target_intake_summary(report=report, layout=layout, validation_errors=validation_errors)
        self.stdout.write(json.dumps(summary, indent=2, sort_keys=True, default=str))


def build_target_intake_summary(
    *,
    report: ReportDefinition,
    layout: Mapping[str, Any],
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    validation_errors = validation_errors or []
    filters = report.filters if isinstance(report.filters, Mapping) else {}
    layout_filters = _layout_filter_summary(layout)
    datasets = _dataset_summary(layout)
    page_ids = _page_ids(layout)
    serialized = json.dumps({"filters": filters, "layout": layout}, sort_keys=True, default=str)
    return {
        "schema_version": "slb_target_intake.v1",
        "status": _status(layout=layout, validation_errors=validation_errors, datasets=datasets),
        "report": {
            "id": str(report.id),
            "tenant_id": str(report.tenant_id),
            "is_active": bool(report.is_active),
            "schema_version": str(layout.get("schema_version") or ""),
            "template_key": str(layout.get("template_key") or filters.get("template_key") or ""),
            "catalog_schema_version": str(layout.get("catalog_schema_version") or ""),
        },
        "date_range": {
            "report_filter": _safe_date_range(filters),
            "layout_filters": layout_filters,
        },
        "source_scope_presence": {
            "client_id_present": _present(filters.get("client_id")),
            "account_id_present": _present(filters.get("account_id")),
            "page_id_present": _present(filters.get("page_id")),
            "workspace_id_present": _present(filters.get("workspace_id")),
            "delivery_recipient_count": _safe_len(report.delivery_emails),
        },
        "datasets": datasets,
        "pages": {
            "count": len(page_ids),
            "ids": page_ids,
            "required_slb_pages_present": _required_pages_present(page_ids),
        },
        "widgets": _widget_summary(layout),
        "schedule": {
            "schedule_enabled": bool(report.schedule_enabled),
            "schedule_cron_present": _present(report.schedule_cron),
            "last_scheduled_at": report.last_scheduled_at.isoformat() if report.last_scheduled_at else None,
        },
        "guardrails": {
            "report_v1": layout.get("schema_version") == REPORT_SCHEMA_VERSION,
            "slb_template": (layout.get("template_key") or filters.get("template_key")) == SLB_MONTHLY_TEMPLATE_KEY,
            "instagram_deferred": "organic_instagram" not in datasets["active"],
            "no_sensitive_patterns_detected": not any(pattern.search(serialized) for pattern in SENSITIVE_PATTERNS),
            "no_live_provider_check": "not_applicable_offline_metadata_only",
        },
        "validation_errors": validation_errors,
        "operator_fields_still_required": [
            "target_environment",
            "backend_url",
            "frontend_url",
            "safe_tenant_identifier",
            "safe_client_identifier",
            "primary_date_range_confirmation",
            "timezone",
            "currency",
            "paid_meta_account_scope",
            "organic_facebook_page_scope",
            "content_ops_workspace_scope",
            "dashthis_source_comparison_owner",
            "dashthis_source_evidence_location",
            "recipient_assumption",
            "dashthis_active_confirmation",
            "raj_mira_g0_clearance",
        ],
    }


def _status(*, layout: Mapping[str, Any], validation_errors: list[str], datasets: Mapping[str, Any]) -> str:
    if validation_errors:
        return "invalid_report_layout"
    if layout.get("schema_version") != REPORT_SCHEMA_VERSION:
        return "not_report_v1"
    if layout.get("template_key") != SLB_MONTHLY_TEMPLATE_KEY:
        return "not_slb_template"
    if "organic_instagram" in datasets["active"]:
        return "instagram_not_deferred"
    return "candidate_ready_for_operator_confirmation"


def _dataset_summary(layout: Mapping[str, Any]) -> dict[str, Any]:
    active: set[str] = set()
    by_widget: list[dict[str, str]] = []
    for widget in layout.get("widgets", []):
        if not isinstance(widget, Mapping):
            continue
        dataset = str(widget.get("dataset") or "")
        widget_type = str(widget.get("type") or "")
        widget_id = str(widget.get("id") or "")
        if dataset and widget_type != "report_section":
            active.add(dataset)
        if dataset:
            by_widget.append({"widget_id": widget_id, "type": widget_type, "dataset": dataset})
    return {
        "active": sorted(active),
        "required_active_v1_present": sorted({"paid_meta_ads", "organic_facebook_page", "content_ops"} & active),
        "missing_required_active_v1": sorted({"paid_meta_ads", "organic_facebook_page", "content_ops"} - active),
        "by_widget": by_widget,
    }


def _page_ids(layout: Mapping[str, Any]) -> list[str]:
    return [str(page.get("id") or "") for page in layout.get("pages", []) if isinstance(page, Mapping)]


def _required_pages_present(page_ids: list[str]) -> bool:
    required = {
        "cover",
        "executive_summary",
        "paid_meta_ads",
        "organic_facebook",
        "top_posts",
        "content_activity",
        "recommendations",
        "appendix",
    }
    return required <= set(page_ids)


def _widget_summary(layout: Mapping[str, Any]) -> dict[str, Any]:
    widgets = [widget for widget in layout.get("widgets", []) if isinstance(widget, Mapping)]
    by_type: dict[str, int] = {}
    for widget in widgets:
        widget_type = str(widget.get("type") or "unknown")
        by_type[widget_type] = by_type.get(widget_type, 0) + 1
    return {"count": len(widgets), "by_type": by_type}


def _layout_filter_summary(layout: Mapping[str, Any]) -> list[dict[str, str]]:
    filters = []
    for widget in layout.get("widgets", []):
        if not isinstance(widget, Mapping):
            continue
        widget_filters = widget.get("filters") if isinstance(widget.get("filters"), Mapping) else {}
        filters.append(
            {
                "widget_id": str(widget.get("id") or ""),
                "date_range": str(widget_filters.get("date_range") or ""),
                "start_date": str(widget_filters.get("start_date") or ""),
                "end_date": str(widget_filters.get("end_date") or ""),
            }
        )
    return filters


def _safe_date_range(filters: Mapping[str, Any]) -> dict[str, str]:
    return {
        "date_range": str(filters.get("date_range") or ""),
        "start_date": str(filters.get("start_date") or ""),
        "end_date": str(filters.get("end_date") or ""),
    }


def _present(value: object) -> bool:
    return bool(str(value or "").strip())


def _safe_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0
