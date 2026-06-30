"""Report.v1 preview assembly over governed widget preview data."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from typing import Any, Mapping

from django.core.cache import cache
from django.utils import timezone

from analytics.models import AdAccount, ReportDefinition, SavedReportLayout

from .reporting_catalog import (
    REPORT_SCHEMA_VERSION,
    ReportingCatalogValidationError,
    is_report_v1_layout,
    validate_dashboard_widget,
    validate_report_layout,
)
from .reporting_preview import ReportingWidgetPreviewError, build_widget_preview
from .reporting_source_health import build_reporting_source_health
from .reporting_templates import SLB_MONTHLY_TEMPLATE_KEY, get_template_export_policy


REPORT_EXPORT_BLOCKING_COVERAGE_STATUSES = {
    "missing_history",
    "not_previously_synced",
    "permission_missing",
    "unsupported_metric",
}

REPORT_LAYOUT_DEFAULT_COLS = 12
REPORT_LAYOUT_DEFAULT_ROW_HEIGHT = 64
REPORT_PREVIEW_CACHE_TTL_SECONDS = 60
NON_METRIC_ROW_KEYS = frozenset(
    {
        "ad",
        "ad_account",
        "adset",
        "campaign",
        "channel",
        "client",
        "content",
        "content_type",
        "creative",
        "date",
        "label",
        "month",
        "objective",
        "page",
        "parish",
        "period",
        "permalink",
        "placement",
        "platform",
        "post",
        "published_post",
        "reaction_type",
        "region",
        "source",
        "status",
        "week",
        "workspace",
    }
)


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
        raise ReportingReportPreviewError(
            ["report preview is only available for report.v1 layouts."]
        )

    context = _preview_context(report=report, payload=payload)
    cache_key = _report_preview_cache_key(report=report, context=context)
    cached_payload = cache.get(cache_key)
    if isinstance(cached_payload, Mapping):
        return deepcopy(dict(cached_payload))

    preview_payload = _build_report_preview_payload(
        report=report,
        layout=layout,
        context=context,
    )
    cache.set(cache_key, deepcopy(preview_payload), timeout=REPORT_PREVIEW_CACHE_TTL_SECONDS)
    return preview_payload


def _build_report_preview_payload(
    *,
    report: ReportDefinition,
    layout: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    widgets = [
        widget for widget in layout.get("widgets", []) if isinstance(widget, Mapping)
    ]
    widgets_by_id = {str(widget.get("id")): dict(widget) for widget in widgets}
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
                    reason = str(
                        preview.get("error")
                        or preview.get("widget_id")
                        or "widget blocked"
                    )
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
    blocking_reasons.extend(_coverage_blocking_reasons(coverage_summary, layout=layout))
    blocking_reasons = sorted(set(blocking_reasons))
    export_ready = not blocking_reasons
    preview_payload = {
        "report": {
            "id": str(report.id),
            "name": report.name,
            "template_key": str(
                layout.get("template_key") or report.filters.get("template_key") or ""
            ),
            "schema_version": REPORT_SCHEMA_VERSION,
            "catalog_schema_version": str(
                layout.get("catalog_schema_version") or "reporting_catalog.v1"
            ),
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


def _report_preview_cache_key(
    *, report: ReportDefinition, context: Mapping[str, Any]
) -> str:
    updated_at = report.updated_at.isoformat() if report.updated_at else ""
    payload = {
        "tenant_id": str(report.tenant_id),
        "report_id": str(report.id),
        "updated_at": updated_at,
        "context": context,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"analytics:report_preview:{digest}"


def build_report_export_metadata(
    *,
    report: ReportDefinition,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = build_report_snapshot(report=report, payload=payload)
    return build_report_export_metadata_from_snapshot(snapshot)


def build_saved_report_layout_snapshot(
    *,
    report: ReportDefinition,
    requested_by=None,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return the latest tenant-safe saved grid layout for this report export."""

    target_config_id = f"report-{report.id}"
    queryset = SavedReportLayout.objects.filter(
        tenant_id=report.tenant_id,
        config__id=target_config_id,
    )
    selected = None
    source = "shared_saved_layout"
    user_id = getattr(requested_by, "id", None)
    if user_id:
        selected = (
            queryset.filter(created_by_id=user_id)
            .order_by("-updated_at", "name")
            .first()
        )
        if selected is not None:
            source = "requester_saved_layout"
    if selected is None:
        selected = (
            queryset.filter(is_shared=True).order_by("-updated_at", "name").first()
        )
    if selected is None or not isinstance(selected.config, Mapping):
        return None
    config = deepcopy(selected.config)
    governed_widget_append_count = 0
    generated_config = _report_snapshot_to_layout_config(report=report, snapshot=snapshot)
    if generated_config is not None:
        config, governed_widget_append_count = _append_missing_governed_widgets(
            saved_config=config,
            generated_config=generated_config,
        )
    return {
        "schema_version": "report_layout_snapshot.v1",
        "source": source,
        "saved_layout_id": str(selected.id),
        "config_id": target_config_id,
        "name": selected.name,
        "is_shared": bool(selected.is_shared),
        "updated_at": selected.updated_at.isoformat() if selected.updated_at else None,
        "governed_widget_append_count": governed_widget_append_count,
        "config": config,
    }


def _report_snapshot_to_layout_config(
    *,
    report: ReportDefinition,
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(snapshot, Mapping):
        return None

    cursor_y = 1
    kpi_x = 1
    widgets: list[dict[str, Any]] = []

    def flush_kpi_row() -> None:
        nonlocal cursor_y, kpi_x
        if kpi_x != 1:
            cursor_y += 2
            kpi_x = 1

    def place(widget: Mapping[str, Any]) -> None:
        nonlocal cursor_y, kpi_x
        layout_widget = dict(widget)
        widget_type = str(layout_widget.get("type") or "")
        if widget_type == "kpi":
            if kpi_x > REPORT_LAYOUT_DEFAULT_COLS - 2:
                flush_kpi_row()
            layout_widget.update({"x": kpi_x, "y": cursor_y})
            widgets.append(layout_widget)
            kpi_x += 3
            if kpi_x > REPORT_LAYOUT_DEFAULT_COLS:
                flush_kpi_row()
            return

        flush_kpi_row()
        layout_widget.update({"x": 1, "y": cursor_y})
        widgets.append(layout_widget)
        cursor_y += _grid_int(layout_widget.get("h"), 2)

    for page in snapshot.get("pages") if isinstance(snapshot.get("pages"), list) else []:
        if not isinstance(page, Mapping):
            continue
        sections = page.get("sections") if isinstance(page.get("sections"), list) else []
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            preview_widgets = (
                section.get("widgets")
                if isinstance(section.get("widgets"), list)
                else []
            )
            for preview_widget in preview_widgets:
                if not isinstance(preview_widget, Mapping):
                    continue
                for layout_widget in _layout_widgets_from_preview_widget(
                    preview_widget
                ):
                    place(layout_widget)

    flush_kpi_row()
    if not widgets:
        widgets = [
            {
                "id": "empty-report-note",
                "type": "note",
                "title": "No renderable widgets",
                "x": 1,
                "y": 1,
                "w": 12,
                "h": 2,
                "options": {
                    "text": (
                        "The governed report preview returned no renderable widgets "
                        "for this range."
                    ),
                },
            }
        ]

    return {
        "id": f"report-{report.id}",
        "title": f"{report.name} layout",
        "cols": REPORT_LAYOUT_DEFAULT_COLS,
        "rowHeight": REPORT_LAYOUT_DEFAULT_ROW_HEIGHT,
        "widgets": widgets,
    }


def _layout_widgets_from_preview_widget(
    widget: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if str(widget.get("status") or "") in {"blocked", "error"}:
        return [_blocked_layout_note(widget)]

    widget_type = str(widget.get("type") or "")
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    if widget_type == "report_section":
        body = str(data.get("body") or "")
        if not body:
            body = f"{_layout_title_from_widget(widget)}{_coverage_text(widget)}".strip()
        return [
            {
                "id": _widget_id(widget),
                "type": "note",
                "title": _layout_title_from_widget(widget),
                "w": 12,
                "h": 2,
                "source": _source_from_preview_widget(widget),
                "options": {"text": body},
            }
        ]

    if widget_type == "kpi":
        metrics = data.get("metrics") if isinstance(data.get("metrics"), list) else []
        output = []
        for metric in metrics:
            if not isinstance(metric, Mapping):
                continue
            key = str(metric.get("key") or metric.get("label") or _widget_id(widget))
            output.append(
                {
                    "id": f"{_widget_id(widget)}-{key}",
                    "type": "kpi",
                    "title": str(metric.get("label") or _label_from_key(key)),
                    "w": 3,
                    "h": 2,
                    "data": _number_value(metric.get("value")),
                    "source": _source_from_preview_widget(widget, [key]),
                    "options": {
                        "format": _metric_format(key),
                        "currency": "JMD",
                    },
                }
            )
        return output

    if widget_type == "line_chart":
        rows = _rows_from_widget(widget)
        x_key = str(data.get("x") or "date")
        metric_keys = _metric_keys_from_widget(widget, x_key=x_key)
        return [
            {
                "id": _widget_id(widget),
                "type": "line",
                "title": _layout_title_from_widget(widget),
                "w": 12,
                "h": 4,
                "data": [
                    {
                        "date": str(row.get(x_key) or row.get("date") or ""),
                        **{
                            key: _number_value(row.get(key))
                            for key in metric_keys
                        },
                    }
                    for row in rows
                ],
                "source": _source_from_preview_widget(widget, metric_keys),
                "options": {
                    "height": 220,
                    "series": [
                        {"key": key, "label": _label_from_key(key)}
                        for key in metric_keys
                    ],
                    "yFormat": (
                        "currency"
                        if _metric_format(metric_keys[0] if metric_keys else "")
                        == "currency"
                        else "number"
                    ),
                    "currency": "JMD",
                },
            }
        ]

    if widget_type in {"bar_chart", "stacked_bar_chart"}:
        rows = _rows_from_widget(widget)
        x_key = str(data.get("x") or "label")
        metric_keys = _metric_keys_from_widget(widget, x_key=x_key)
        metric_key = metric_keys[0] if metric_keys else "value"
        bar_rows = []
        for row in rows:
            value = _number_value(row.get(metric_key))
            if value is None:
                continue
            bar_rows.append(
                {
                    "label": str(row.get(x_key) or row.get("label") or "Unspecified"),
                    "value": value,
                }
            )
        return [
            {
                "id": _widget_id(widget),
                "type": "bar",
                "title": _layout_title_from_widget(widget),
                "w": 12,
                "h": 4,
                "source": _source_from_preview_widget(widget, [metric_key]),
                "data": bar_rows,
                "options": {
                    "height": 220,
                    "currency": (
                        "JMD" if _metric_format(metric_key) == "currency" else None
                    ),
                },
            }
        ]

    if widget_type == "data_table":
        rows = _rows_from_widget(widget)
        return [
            {
                "id": _widget_id(widget),
                "type": "table",
                "title": _layout_title_from_widget(widget),
                "w": 12,
                "h": 4,
                "data": [_json_safe_value(row) for row in rows],
                "source": _source_from_preview_widget(
                    widget, _metric_keys_from_widget(widget, x_key="date")
                ),
                "options": {"columns": _columns_from_widget(widget)},
            }
        ]

    blocked_widget = dict(widget)
    blocked_widget["error"] = f"Unsupported governed widget type: {widget_type}"
    return [_blocked_layout_note(blocked_widget)]


def _append_missing_governed_widgets(
    *,
    saved_config: Mapping[str, Any],
    generated_config: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    config = deepcopy(dict(saved_config))
    saved_widgets = (
        list(config.get("widgets")) if isinstance(config.get("widgets"), list) else None
    )
    generated_widgets = (
        generated_config.get("widgets")
        if isinstance(generated_config.get("widgets"), list)
        else []
    )
    if saved_widgets is None or not generated_widgets:
        return config, 0

    existing_ids = {
        str(widget.get("id"))
        for widget in saved_widgets
        if isinstance(widget, Mapping) and widget.get("id") is not None
    }
    existing_signatures = {
        signature
        for widget in saved_widgets
        if isinstance(widget, Mapping)
        for signature in [_widget_source_signature(widget)]
        if signature
    }
    missing_widgets = []
    for widget in generated_widgets:
        if not isinstance(widget, Mapping):
            continue
        widget_id = str(widget.get("id") or "")
        if widget_id and widget_id in existing_ids:
            continue
        signature = _widget_source_signature(widget)
        if signature and signature in existing_signatures:
            continue
        missing_widgets.append(deepcopy(dict(widget)))

    if not missing_widgets:
        return config, 0

    current_bottom_y = 0
    for widget in saved_widgets:
        if not isinstance(widget, Mapping):
            continue
        current_bottom_y = max(
            current_bottom_y,
            _grid_int(widget.get("y"), 1) + _grid_int(widget.get("h"), 1) - 1,
        )
    min_generated_y = min(_grid_int(widget.get("y"), 1) for widget in missing_widgets)
    y_offset = current_bottom_y + 1 - min_generated_y
    for widget in missing_widgets:
        widget["y"] = _grid_int(widget.get("y"), 1) + y_offset

    config["widgets"] = saved_widgets + missing_widgets
    return config, len(missing_widgets)


def _blocked_layout_note(widget: Mapping[str, Any]) -> dict[str, Any]:
    warnings = widget.get("warnings") if isinstance(widget.get("warnings"), list) else []
    reason = str(widget.get("error") or (warnings[0] if warnings else "")).strip()
    if not reason:
        reason = "This governed widget is not renderable."
    return {
        "id": f"{_widget_id(widget)}-note",
        "type": "note",
        "title": _layout_title_from_widget(widget),
        "w": 12,
        "h": 2,
        "source": _source_from_preview_widget(widget),
        "options": {
            "text": f"{reason}{_coverage_text(widget)}".strip(),
        },
    }


def _widget_source_signature(widget: Mapping[str, Any]) -> str | None:
    source = widget.get("source") if isinstance(widget.get("source"), Mapping) else None
    if source is None:
        return None
    dataset = str(source.get("dataset") or "")
    raw_metrics = source.get("metrics") if isinstance(source.get("metrics"), list) else []
    metrics = sorted(str(metric) for metric in raw_metrics if str(metric))
    widget_type = str(widget.get("type") or "")
    if metrics:
        return f"{widget_type}|{dataset}|metrics:{','.join(metrics)}"
    source_widget_id = source.get("widgetId") or source.get("widget_id")
    if source_widget_id:
        return f"{widget_type}|{dataset}|widget:{source_widget_id}"
    return None


def _source_from_preview_widget(
    widget: Mapping[str, Any],
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "dataset": str(widget.get("dataset") or ""),
        "widgetId": _widget_id(widget),
        "metrics": metrics or [],
    }


def _columns_from_widget(widget: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _rows_from_widget(widget)
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    raw_columns = data.get("columns") if isinstance(data.get("columns"), list) else []
    keys = [str(key) for key in raw_columns if str(key)]
    if not keys and rows:
        keys = [str(key) for key in rows[0].keys()]
    return [
        {
            "key": key,
            "header": _label_from_key(key),
            "align": (
                "right"
                if any(_number_value(row.get(key)) is not None for row in rows)
                else "left"
            ),
        }
        for key in keys
    ]


def _metric_keys_from_rows(rows: list[Mapping[str, Any]], x_key: str) -> list[str]:
    first = rows[0] if rows else None
    if not isinstance(first, Mapping):
        return []
    return [str(key) for key in first.keys() if key not in {x_key, "date"}]


def _metric_keys_from_widget(widget: Mapping[str, Any], *, x_key: str) -> list[str]:
    declared = _declared_keys(widget, "metrics")
    if declared:
        return declared
    return [
        key
        for key in _metric_keys_from_rows(_rows_from_widget(widget), x_key)
        if key not in NON_METRIC_ROW_KEYS
    ]


def _declared_keys(widget: Mapping[str, Any], key: str) -> list[str]:
    values = widget.get(key)
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value)]


def _rows_from_widget(widget: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    return [row for row in rows if isinstance(row, Mapping)]


def _coverage_text(widget: Mapping[str, Any]) -> str:
    coverage = (
        widget.get("coverage") if isinstance(widget.get("coverage"), Mapping) else {}
    )
    note = str(coverage.get("coverage_note") or "").strip()
    return f"\n\n{note}" if note else ""


def _layout_title_from_widget(widget: Mapping[str, Any]) -> str:
    data = widget.get("data") if isinstance(widget.get("data"), Mapping) else {}
    title = str(data.get("title") or "").strip()
    if title:
        return title
    return _label_from_key(_widget_id(widget))


def _widget_id(widget: Mapping[str, Any]) -> str:
    return str(widget.get("widget_id") or widget.get("id") or "")


def _metric_format(metric: str) -> str:
    if metric in {"spend", "cpc", "cpm", "cpa", "conversion_value"}:
        return "currency"
    if metric in {"ctr", "roas", "frequency"}:
        return "rate"
    return "number"


def _label_from_key(key: str) -> str:
    return str(key).replace("_", " ").title().strip()


def _number_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = Decimal(value.strip())
        except Exception:
            return None
        if not parsed.is_finite():
            return None
        return int(parsed) if parsed == parsed.to_integral_value() else float(parsed)
    return None


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, Decimal):
        return _number_value(value)
    return value


def _grid_int(value: Any, fallback: int) -> int:
    number = _number_value(value)
    if number is None:
        return fallback
    return max(1, int(round(number)))


def build_report_export_metadata_from_snapshot(
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
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
        "warnings": snapshot["warnings"],
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

    context = _preview_context(report=report, payload=payload or {})
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
    coverage_summary = (
        snapshot.get("coverage_summary") if isinstance(snapshot, Mapping) else {}
    )
    for dataset in (coverage_summary or {}).get("datasets", []):
        if not isinstance(dataset, Mapping):
            continue
        statuses = (
            dataset.get("statuses")
            if isinstance(dataset.get("statuses"), Mapping)
            else {}
        )
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
                "source_label": dataset.get("source_label")
                or str(dataset.get("dataset") or ""),
                "last_successful_sync_at": dataset.get("last_successful_sync_at"),
                "notes": [str(note) for note in dataset.get("notes", [])],
                "coverage_gap": (
                    dataset.get("coverage_gap")
                    if isinstance(dataset.get("coverage_gap"), Mapping)
                    else {}
                ),
                "recommended_next_action": _recommended_next_action(primary_status),
            }
        )

    export_history = []
    for job in report.export_jobs.filter(tenant_id=report.tenant_id).order_by(
        "-created_at"
    )[:10]:
        metadata = job.metadata if isinstance(job.metadata, Mapping) else {}
        report_preview = (
            metadata.get("report_preview")
            if isinstance(metadata.get("report_preview"), Mapping)
            else {}
        )
        delivery_status = (
            metadata.get("delivery_status")
            if isinstance(metadata.get("delivery_status"), Mapping)
            else {}
        )
        export_history.append(
            {
                "id": str(job.id),
                "format": job.export_format,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "preview_hash": metadata.get("preview_hash")
                or report_preview.get("preview_hash"),
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
        "source_health": build_reporting_source_health(
            tenant=report.tenant,
            report_context=context,
        ),
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


def _preview_context(
    *, report: ReportDefinition, payload: Mapping[str, Any]
) -> dict[str, Any]:
    filters = report.filters if isinstance(report.filters, Mapping) else {}
    layout = report.layout if isinstance(report.layout, Mapping) else {}
    date_range = {
        "date_range": payload.get("date_range")
        or filters.get("date_range")
        or "last_month",
        "start_date": payload.get("start_date") or filters.get("start_date") or "",
        "end_date": payload.get("end_date") or filters.get("end_date") or "",
    }
    return {
        "date_range": date_range,
        "template_key": str(
            payload.get("template_key")
            or filters.get("template_key")
            or layout.get("template_key")
            or ""
        ).strip(),
        "client_id": str(
            payload.get("client_id") or filters.get("client_id") or ""
        ).strip(),
        "account_id": str(
            payload.get("account_id") or filters.get("account_id") or ""
        ).strip(),
        "page_id": str(payload.get("page_id") or filters.get("page_id") or "").strip(),
    }


def _preview_report_widget(
    *, tenant, widget: dict[str, Any], context: Mapping[str, Any]
) -> dict[str, Any]:
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
            "metrics": [],
            "dimensions": [],
            "data": {
                "kind": "report_section",
                "title": (widget.get("visual") or {}).get("title")
                if isinstance(widget.get("visual"), Mapping)
                else "",
                "body": (widget.get("visual") or {}).get("body")
                if isinstance(widget.get("visual"), Mapping)
                else "",
            },
            "coverage": _section_coverage(widget),
            "warnings": [],
        }

    if _slb_paid_widget_requires_scope(tenant=tenant, widget=widget, context=context):
        return _error_widget(
            widget=widget,
            errors=[
                "SLB paid Meta widgets require account_id or client_id scope before preview/export."
            ],
            status="blocked",
        )

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


def _slb_paid_widget_requires_scope(
    *, tenant, widget: Mapping[str, Any], context: Mapping[str, Any]
) -> bool:
    if str(context.get("template_key") or "") != SLB_MONTHLY_TEMPLATE_KEY:
        return False
    if str(widget.get("dataset") or "") != "paid_meta_ads":
        return False
    filters = (
        widget.get("filters") if isinstance(widget.get("filters"), Mapping) else {}
    )
    missing_scope = not any(
        str(value or "").strip()
        for value in (
            context.get("account_id"),
            context.get("client_id"),
            filters.get("account_id"),
            filters.get("client_id"),
        )
    )
    if not missing_scope:
        return False
    return AdAccount.all_objects.filter(tenant=tenant).count() > 1


def _error_widget(
    *, widget: Mapping[str, Any], errors: list[str], status: str
) -> dict[str, Any]:
    return {
        "widget_id": str(widget.get("id") or ""),
        "dataset": str(widget.get("dataset") or ""),
        "type": str(widget.get("type") or ""),
        "status": status,
        "metrics": _declared_keys(widget, "metrics"),
        "dimensions": _declared_keys(widget, "dimensions"),
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
        target["row_count"] = int(target.get("row_count") or 0) + int(
            coverage.get("row_count") or 0
        )
        target["covered_start_date"] = _min_date(
            target.get("covered_start_date"), coverage.get("covered_start_date")
        )
        target["covered_end_date"] = _max_date(
            target.get("covered_end_date"), coverage.get("covered_end_date")
        )
        target["last_successful_sync_at"] = _max_date(
            target.get("last_successful_sync_at"),
            coverage.get("last_successful_sync_at"),
        )
        note = str(coverage.get("coverage_note") or "").strip()
        if note and note not in target["notes"]:
            target["notes"].append(note)
        coverage_gap = coverage.get("coverage_gap")
        if isinstance(coverage_gap, Mapping) and not isinstance(
            target.get("coverage_gap"), Mapping
        ):
            target["coverage_gap"] = dict(coverage_gap)
    return {
        "by_status": by_status,
        "datasets": sorted(datasets.values(), key=lambda item: item["dataset"]),
    }


def _coverage_blocking_reasons(
    coverage_summary: Mapping[str, Any],
    *,
    layout: Mapping[str, Any],
) -> list[str]:
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
        warning_only_statuses = _warning_only_coverage_statuses(
            layout=layout, dataset=dataset_name
        )
        for status in sorted(REPORT_EXPORT_BLOCKING_COVERAGE_STATUSES):
            if status in warning_only_statuses:
                continue
            count = int(statuses.get(status) or 0)
            if count <= 0:
                continue
            reasons.append(
                f"{dataset_name} has {count} widget(s) with blocking coverage_status {status}."
            )
    return reasons


def _warning_only_coverage_statuses(
    *, layout: Mapping[str, Any], dataset: str
) -> set[str]:
    template_key = str(layout.get("template_key") or "")
    policy = layout.get("export_policy")
    if not isinstance(policy, Mapping):
        policy = get_template_export_policy(template_key)
    warning_only = policy.get("warning_only_coverage_statuses")
    if not isinstance(warning_only, Mapping):
        return set()
    statuses = warning_only.get(dataset)
    if not isinstance(statuses, list):
        return set()
    return {str(status) for status in statuses if isinstance(status, str)}


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
