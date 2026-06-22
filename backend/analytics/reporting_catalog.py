"""Governed reporting catalog and dashboard layout validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from integrations.services.metric_registry import get_reporting_metric_source_map


DASHBOARD_SCHEMA_VERSION = "dashboard.v1"
REPORT_SCHEMA_VERSION = "report.v1"

COVERAGE_POLICIES = frozenset(
    {
        "require_full_coverage",
        "render_with_warning",
        "render_snapshot_only",
        "block_if_stale",
    }
)

RELATIVE_DATE_RANGES = frozenset(
    {
        "last_7d",
        "last_28d",
        "last_30d",
        "last_90d",
        "mtd",
        "last_month",
        "this_month",
        "custom",
    }
)

TIME_DIMENSIONS = frozenset({"date", "week", "month"})
GEOGRAPHY_DIMENSIONS = frozenset({"region", "parish"})
SOURCE_LABEL_DATASETS = frozenset({"combined_paid_media", "combined_social"})
FUTURE_GATED_DATASETS = frozenset(
    {"organic_instagram", "combined_social", "ga4_web", "search_console"}
)
FUTURE_GATED_WIDGETS = frozenset({"scatter_chart"})
COVERAGE_STATUSES = frozenset(
    {
        "fresh",
        "stale",
        "partial",
        "source_disconnected",
        "missing_history",
        "not_previously_synced",
        "permission_missing",
        "unsupported_metric",
    }
)


class ReportingCatalogValidationError(ValueError):
    """Raised when a dashboard layout violates the reporting catalog."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class DatasetDefinition:
    key: str
    status: str


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    dataset: str
    widgets: frozenset[str]
    dimensions: frozenset[str]


@dataclass(frozen=True)
class DimensionDefinition:
    key: str
    datasets: frozenset[str]


@dataclass(frozen=True)
class WidgetDefinition:
    key: str
    status: str = "active_v1"


DATASETS: dict[str, DatasetDefinition] = {
    "paid_meta_ads": DatasetDefinition("paid_meta_ads", "active_v1"),
    "organic_facebook_page": DatasetDefinition("organic_facebook_page", "active_v1"),
    "content_ops": DatasetDefinition("content_ops", "active_v1"),
    "combined_paid_media": DatasetDefinition("combined_paid_media", "active_v1"),
    "csv_upload": DatasetDefinition("csv_upload", "active_v1_support"),
    "organic_instagram": DatasetDefinition("organic_instagram", "future_gated"),
    "combined_social": DatasetDefinition("combined_social", "future_gated"),
    "ga4_web": DatasetDefinition("ga4_web", "future_gated"),
    "search_console": DatasetDefinition("search_console", "future_gated"),
}


DIMENSIONS: dict[str, DimensionDefinition] = {
    "date": DimensionDefinition("date", frozenset(DATASETS)),
    "week": DimensionDefinition("week", frozenset(DATASETS)),
    "month": DimensionDefinition("month", frozenset(DATASETS)),
    "client": DimensionDefinition("client", frozenset(DATASETS)),
    "platform": DimensionDefinition(
        "platform", frozenset({"combined_paid_media", "combined_social", "csv_upload"})
    ),
    "source": DimensionDefinition("source", frozenset({"combined_paid_media", "combined_social"})),
    "ad_account": DimensionDefinition(
        "ad_account", frozenset({"paid_meta_ads", "combined_paid_media", "csv_upload"})
    ),
    "campaign": DimensionDefinition(
        "campaign", frozenset({"paid_meta_ads", "combined_paid_media", "csv_upload"})
    ),
    "adset": DimensionDefinition("adset", frozenset({"paid_meta_ads"})),
    "ad": DimensionDefinition("ad", frozenset({"paid_meta_ads"})),
    "creative": DimensionDefinition("creative", frozenset({"paid_meta_ads"})),
    "placement": DimensionDefinition("placement", frozenset({"paid_meta_ads"})),
    "region": DimensionDefinition("region", frozenset({"paid_meta_ads", "csv_upload"})),
    "parish": DimensionDefinition("parish", frozenset({"paid_meta_ads", "csv_upload"})),
    "objective": DimensionDefinition("objective", frozenset({"paid_meta_ads"})),
    "status": DimensionDefinition("status", frozenset({"paid_meta_ads", "content_ops"})),
    "page": DimensionDefinition("page", frozenset({"organic_facebook_page"})),
    "post": DimensionDefinition("post", frozenset({"organic_facebook_page", "content_ops"})),
    "content_type": DimensionDefinition(
        "content_type", frozenset({"organic_facebook_page", "content_ops"})
    ),
    "reaction_type": DimensionDefinition("reaction_type", frozenset({"organic_facebook_page"})),
    "period": DimensionDefinition("period", frozenset({"organic_facebook_page"})),
    "workspace": DimensionDefinition("workspace", frozenset({"content_ops"})),
    "channel": DimensionDefinition("channel", frozenset({"content_ops"})),
    "published_post": DimensionDefinition("published_post", frozenset({"content_ops"})),
}


WIDGETS: dict[str, WidgetDefinition] = {
    "kpi": WidgetDefinition("kpi"),
    "line_chart": WidgetDefinition("line_chart"),
    "bar_chart": WidgetDefinition("bar_chart"),
    "stacked_bar_chart": WidgetDefinition("stacked_bar_chart", "active_v1_guarded"),
    "donut_chart": WidgetDefinition("donut_chart", "active_v1_guarded"),
    "data_table": WidgetDefinition("data_table"),
    "report_section": WidgetDefinition("report_section"),
    "map": WidgetDefinition("map", "active_v1_guarded"),
    "scatter_chart": WidgetDefinition("scatter_chart", "future_gated"),
}


def _metric(
    key: str,
    dataset: str,
    *,
    widgets: set[str],
    dimensions: set[str],
) -> tuple[str, MetricDefinition]:
    return key, MetricDefinition(
        key=key,
        dataset=dataset,
        widgets=frozenset(widgets),
        dimensions=frozenset(dimensions),
    )


PAID_DIMENSIONS = {
    "date",
    "week",
    "month",
    "client",
    "ad_account",
    "campaign",
    "adset",
    "ad",
    "creative",
    "placement",
    "region",
    "parish",
    "objective",
    "status",
}
PAID_WIDGETS = {"kpi", "line_chart", "bar_chart", "stacked_bar_chart", "data_table", "map"}

ORGANIC_PAGE_DIMENSIONS = {
    "date",
    "week",
    "month",
    "client",
    "page",
    "post",
    "content_type",
    "reaction_type",
    "period",
}
ORGANIC_PAGE_WIDGETS = {"kpi", "line_chart", "bar_chart", "stacked_bar_chart", "data_table"}

CONTENT_OPS_DIMENSIONS = {
    "date",
    "week",
    "month",
    "client",
    "workspace",
    "channel",
    "content_type",
    "status",
    "post",
    "published_post",
}
CONTENT_OPS_WIDGETS = {"kpi", "line_chart", "bar_chart", "stacked_bar_chart", "data_table"}

COMBINED_PAID_DIMENSIONS = {
    "date",
    "week",
    "month",
    "client",
    "platform",
    "source",
    "ad_account",
    "campaign",
}
COMBINED_PAID_WIDGETS = {"kpi", "line_chart", "bar_chart", "stacked_bar_chart", "data_table"}


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = tuple(
    definition
    for _, definition in [
        *(
            _metric(key, "paid_meta_ads", widgets=PAID_WIDGETS, dimensions=PAID_DIMENSIONS)
            for key in (
                "spend",
                "impressions",
                "reach",
                "clicks",
                "conversions",
                "conversion_value",
                "ctr",
                "cpc",
                "cpm",
                "cpa",
                "roas",
                "frequency",
            )
        ),
        *(
            _metric(
                key,
                "organic_facebook_page",
                widgets=ORGANIC_PAGE_WIDGETS,
                dimensions=ORGANIC_PAGE_DIMENSIONS,
            )
            for key in (
                "page_reach",
                "page_impressions",
                "page_engagements",
                "page_actions",
                "page_follows",
                "page_fans",
                "page_reactions_like",
                "page_reactions_love",
                "page_reactions_wow",
                "post_impressions",
                "post_clicks",
                "post_reactions_like",
                "post_reactions_love",
            )
        ),
        _metric(
            "post_activity",
            "organic_facebook_page",
            widgets={"data_table"},
            dimensions=ORGANIC_PAGE_DIMENSIONS,
        ),
        *(
            _metric(key, "content_ops", widgets=CONTENT_OPS_WIDGETS, dimensions=CONTENT_OPS_DIMENSIONS)
            for key in (
                "content_items_created",
                "published_posts",
                "scheduled_posts",
                "approved_items",
                "content_ops_reach",
                "content_ops_engagements",
                "content_ops_impressions",
            )
        ),
        *(
            _metric(
                key,
                "combined_paid_media",
                widgets=COMBINED_PAID_WIDGETS,
                dimensions=COMBINED_PAID_DIMENSIONS,
            )
            for key in (
                "spend",
                "impressions",
                "clicks",
                "conversions",
                "conversion_value",
                "ctr",
                "cpc",
                "cpm",
                "cpa",
                "roas",
            )
        ),
        *(
            _metric(key, "csv_upload", widgets=PAID_WIDGETS, dimensions=PAID_DIMENSIONS)
            for key in ("spend", "impressions", "clicks", "conversions", "roas")
        ),
    ]
)

METRICS_BY_DATASET: dict[tuple[str, str], MetricDefinition] = {
    (definition.dataset, definition.key): definition for definition in METRIC_DEFINITIONS
}

METRICS: dict[str, MetricDefinition] = {
    f"{definition.dataset}.{definition.key}": definition for definition in METRIC_DEFINITIONS
}

DEPRECATED_OR_UNKNOWN_PAGE_METRICS = frozenset(
    {
        "page_video_views_10s",
        "page_video_views_10s_autoplayed",
        "page_video_views_10s_click_to_play",
        "page_video_views_10s_organic",
        "page_video_views_10s_paid",
        "page_video_views_10s_repeat",
        "page_video_views_10s_unique",
        "page_views_total",
        "post_video_views_10s",
        "post_video_views_10s_autoplayed",
        "post_video_views_10s_clicked_to_play",
        "post_video_views_10s_organic",
        "post_video_views_10s_paid",
        "post_video_views_10s_sound_on",
        "post_video_views_10s_unique",
    }
)


def is_dashboard_v1_layout(layout: object) -> bool:
    return isinstance(layout, Mapping) and layout.get("schema_version") == DASHBOARD_SCHEMA_VERSION


def get_reporting_catalog() -> dict[str, object]:
    """Return a serialisable view of the governed v1 catalog."""

    return {
        "schema_version": "reporting_catalog.v1",
        "dashboard_schema_version": DASHBOARD_SCHEMA_VERSION,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "datasets": [
            {
                "key": definition.key,
                "status": definition.status,
                "is_future_gated": definition.key in FUTURE_GATED_DATASETS,
            }
            for definition in sorted(DATASETS.values(), key=lambda item: item.key)
        ],
        "metrics": [
            {
                "key": definition.key,
                "dataset": definition.dataset,
                "widgets": sorted(definition.widgets),
                "dimensions": sorted(definition.dimensions),
                "is_future_gated": definition.dataset in FUTURE_GATED_DATASETS,
            }
            for definition in sorted(
                METRIC_DEFINITIONS,
                key=lambda item: (item.dataset, item.key),
            )
        ],
        "dimensions": [
            {
                "key": definition.key,
                "datasets": sorted(definition.datasets),
            }
            for definition in sorted(DIMENSIONS.values(), key=lambda item: item.key)
        ],
        "widgets": [
            {
                "key": definition.key,
                "status": definition.status,
                "is_future_gated": definition.key in FUTURE_GATED_WIDGETS,
            }
            for definition in sorted(WIDGETS.values(), key=lambda item: item.key)
        ],
        "coverage_policies": sorted(COVERAGE_POLICIES),
        "coverage_statuses": sorted(COVERAGE_STATUSES),
        "source_metric_semantics": {
            "organic_facebook_page": {
                "page": {
                    key: list(value)
                    for key, value in sorted(
                        get_reporting_metric_source_map("organic_facebook_page", level="page").items()
                    )
                },
                "post": {
                    key: list(value)
                    for key, value in sorted(
                        get_reporting_metric_source_map("organic_facebook_page", level="post").items()
                    )
                },
            },
            "content_ops": {
                key: list(value)
                for key, value in sorted(get_reporting_metric_source_map("content_ops").items())
            },
        },
        "compatibility": {
            "time_dimensions": sorted(TIME_DIMENSIONS),
            "geography_dimensions": sorted(GEOGRAPHY_DIMENSIONS),
            "source_label_datasets": sorted(SOURCE_LABEL_DATASETS),
            "future_gated_datasets": sorted(FUTURE_GATED_DATASETS),
            "future_gated_widgets": sorted(FUTURE_GATED_WIDGETS),
            "relative_date_ranges": sorted(RELATIVE_DATE_RANGES),
            "table": {"requires_row_limit": True, "max_row_limit": 500},
            "line_chart": {"requires_one_of_dimensions": sorted(TIME_DIMENSIONS)},
            "map": {"requires_one_of_dimensions": sorted(GEOGRAPHY_DIMENSIONS)},
        },
        "validation": {
            "legacy_layouts_without_schema_version": "accepted",
            "dashboard_v1_layouts": "validated",
            "report_v1_layouts": "validated",
            "deprecated_or_unknown_page_metrics": sorted(DEPRECATED_OR_UNKNOWN_PAGE_METRICS),
        },
    }


def validate_dashboard_layout(layout: object) -> dict[str, Any]:
    """Validate and return a dashboard layout JSON object.

    Layouts without ``schema_version`` are legacy saved dashboards and are
    intentionally accepted unchanged by the serializer.
    """

    if layout in (None, ""):
        return {}
    if not isinstance(layout, Mapping):
        raise ReportingCatalogValidationError(["layout must be an object."])

    candidate = dict(layout)
    schema_version = candidate.get("schema_version")
    if schema_version is None:
        return candidate
    if schema_version != DASHBOARD_SCHEMA_VERSION:
        raise ReportingCatalogValidationError(
            [f"unsupported layout schema_version '{schema_version}'."]
        )

    errors: list[str] = []
    widgets = candidate.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        errors.append("dashboard.v1 layout requires a non-empty widgets list.")
        widgets = []

    widget_ids: set[str] = set()
    for index, widget in enumerate(widgets):
        if not isinstance(widget, Mapping):
            errors.append(f"widgets[{index}] must be an object.")
            continue
        _validate_widget(index=index, widget=widget, widget_ids=widget_ids, errors=errors)

    _validate_slots(candidate.get("layout"), widget_ids=widget_ids, errors=errors)

    if errors:
        raise ReportingCatalogValidationError(errors)
    return candidate


def validate_report_layout(layout: object) -> dict[str, Any]:
    """Validate and return a report layout JSON object.

    Reports without ``schema_version`` are legacy report definitions and are
    intentionally accepted unchanged by the serializer.
    """

    if layout in (None, ""):
        return {}
    if not isinstance(layout, Mapping):
        raise ReportingCatalogValidationError(["layout must be an object."])

    candidate = dict(layout)
    schema_version = candidate.get("schema_version")
    if schema_version is None:
        return candidate
    if schema_version != REPORT_SCHEMA_VERSION:
        raise ReportingCatalogValidationError(
            [f"unsupported report layout schema_version '{schema_version}'."]
        )

    errors: list[str] = []
    widgets = candidate.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        errors.append("report.v1 layout requires a non-empty widgets list.")
        widgets = []

    widget_ids: set[str] = set()
    for index, widget in enumerate(widgets):
        if not isinstance(widget, Mapping):
            errors.append(f"widgets[{index}] must be an object.")
            continue
        _validate_widget(index=index, widget=widget, widget_ids=widget_ids, errors=errors)

    _validate_report_pages(candidate.get("pages"), widget_ids=widget_ids, errors=errors)

    if errors:
        raise ReportingCatalogValidationError(errors)
    return candidate


def validate_dashboard_widget(widget: object) -> dict[str, Any]:
    """Validate one dashboard.v1 widget config.

    Preview/render endpoints receive one widget at a time, but the catalog
    compatibility rules are intentionally shared with persisted dashboard
    validation.
    """

    if not isinstance(widget, Mapping):
        raise ReportingCatalogValidationError(["widget must be an object."])

    candidate = dict(widget)
    errors: list[str] = []
    widget_ids: set[str] = set()
    _validate_widget(index=0, widget=candidate, widget_ids=widget_ids, errors=errors)
    if errors:
        raise ReportingCatalogValidationError(errors)
    return candidate


def is_report_v1_layout(layout: object) -> bool:
    return isinstance(layout, Mapping) and layout.get("schema_version") == REPORT_SCHEMA_VERSION


def _validate_widget(
    *,
    index: int,
    widget: Mapping[str, Any],
    widget_ids: set[str],
    errors: list[str],
) -> None:
    path = f"widgets[{index}]"
    widget_id = widget.get("id")
    if not isinstance(widget_id, str) or not widget_id.strip():
        errors.append(f"{path}.id is required.")
    elif widget_id in widget_ids:
        errors.append(f"{path}.id '{widget_id}' is duplicated.")
    else:
        widget_ids.add(widget_id)

    widget_type = widget.get("type")
    if not isinstance(widget_type, str) or widget_type not in WIDGETS:
        errors.append(f"{path}.type is not a valid widget type.")
        widget_type = None
    elif widget_type in FUTURE_GATED_WIDGETS:
        errors.append(f"{path}.type '{widget_type}' is future-gated.")

    dataset = widget.get("dataset")
    if not isinstance(dataset, str) or dataset not in DATASETS:
        errors.append(f"{path}.dataset is not a valid dataset.")
        dataset = None
    elif dataset in FUTURE_GATED_DATASETS:
        errors.append(f"{path}.dataset '{dataset}' is future-gated.")

    coverage_policy = widget.get("coverage_policy")
    if coverage_policy is not None and coverage_policy not in COVERAGE_POLICIES:
        errors.append(f"{path}.coverage_policy is not valid.")

    metrics = _string_list(widget.get("metrics"))
    dimensions = _string_list(widget.get("dimensions"))

    if widget_type != "report_section" and not metrics:
        errors.append(f"{path}.metrics must include at least one metric.")
    if widget_type == "line_chart" and not (set(dimensions) & TIME_DIMENSIONS):
        errors.append(f"{path}.dimensions must include a time dimension for line_chart.")
    if widget_type == "map" and not (set(dimensions) & GEOGRAPHY_DIMENSIONS):
        errors.append(f"{path}.dimensions must include region or parish for map.")
    if widget_type == "data_table" and not _has_row_limit(widget):
        errors.append(f"{path} data_table widgets require row_limit.")

    filters = widget.get("filters")
    if widget_type != "report_section" and not _has_bounded_date_range(filters):
        errors.append(f"{path}.filters must include a bounded date range.")

    visual = widget.get("visual")
    source_labels = isinstance(visual, Mapping) and visual.get("source_labels") is True
    if dataset in SOURCE_LABEL_DATASETS and set(dimensions) & {"platform", "source"}:
        if not source_labels:
            errors.append(f"{path}.visual.source_labels must be true for source comparisons.")

    if dataset is None:
        return

    for metric in metrics:
        definition = METRICS_BY_DATASET.get((dataset, metric))
        if metric in DEPRECATED_OR_UNKNOWN_PAGE_METRICS:
            errors.append(f"{path}.metrics contains deprecated or unknown metric '{metric}'.")
        elif not any(definition.key == metric for definition in METRIC_DEFINITIONS):
            errors.append(f"{path}.metrics contains unknown metric '{metric}'.")
        elif definition is None:
            errors.append(f"{path}.metrics contains metric '{metric}' not valid for {dataset}.")
        elif widget_type and widget_type not in definition.widgets:
            errors.append(f"{path}.metrics contains metric '{metric}' not valid for {widget_type}.")

    for dimension in dimensions:
        definition = DIMENSIONS.get(dimension)
        if definition is None:
            errors.append(f"{path}.dimensions contains unknown dimension '{dimension}'.")
        elif dataset not in definition.datasets:
            errors.append(
                f"{path}.dimensions contains dimension '{dimension}' not valid for {dataset}."
            )
        elif metrics and any(
            (metric_def := METRICS_BY_DATASET.get((dataset, metric))) is not None
            and dimension not in metric_def.dimensions
            for metric in metrics
        ):
            errors.append(
                f"{path}.dimensions contains dimension '{dimension}' not valid for all metrics."
            )


def _validate_slots(layout_config: object, *, widget_ids: set[str], errors: list[str]) -> None:
    if layout_config is None:
        return
    if not isinstance(layout_config, Mapping):
        errors.append("layout.layout must be an object when provided.")
        return
    slots = layout_config.get("slots")
    if slots is None:
        return
    if not isinstance(slots, list):
        errors.append("layout.slots must be a list.")
        return
    slot_ids: set[str] = set()
    for index, slot in enumerate(slots):
        path = f"layout.slots[{index}]"
        if not isinstance(slot, Mapping):
            errors.append(f"{path} must be an object.")
            continue
        slot_id = slot.get("id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            errors.append(f"{path}.id is required.")
        elif slot_id in slot_ids:
            errors.append(f"{path}.id '{slot_id}' is duplicated.")
        else:
            slot_ids.add(slot_id)
        widget_id = slot.get("widget_id")
        if widget_id not in widget_ids:
            errors.append(f"{path}.widget_id must reference an existing widget.")
        cols = slot.get("cols")
        if not isinstance(cols, int) or cols < 1 or cols > 12:
            errors.append(f"{path}.cols must be between 1 and 12.")
        rows = slot.get("rows")
        if not isinstance(rows, int) or rows < 1 or rows > 6:
            errors.append(f"{path}.rows must be between 1 and 6.")


def _validate_report_pages(pages: object, *, widget_ids: set[str], errors: list[str]) -> None:
    if not isinstance(pages, list) or not pages:
        errors.append("report.v1 layout requires a non-empty pages list.")
        return

    page_ids: set[str] = set()
    for page_index, page in enumerate(pages):
        page_path = f"pages[{page_index}]"
        if not isinstance(page, Mapping):
            errors.append(f"{page_path} must be an object.")
            continue
        page_id = page.get("id")
        if not isinstance(page_id, str) or not page_id.strip():
            errors.append(f"{page_path}.id is required.")
        elif page_id in page_ids:
            errors.append(f"{page_path}.id '{page_id}' is duplicated.")
        else:
            page_ids.add(page_id)

        title = page.get("title")
        if title is not None and not isinstance(title, str):
            errors.append(f"{page_path}.title must be a string when provided.")

        sections = page.get("sections")
        if not isinstance(sections, list) or not sections:
            errors.append(f"{page_path}.sections must be a non-empty list.")
            continue
        section_ids: set[str] = set()
        for section_index, section in enumerate(sections):
            section_path = f"{page_path}.sections[{section_index}]"
            if not isinstance(section, Mapping):
                errors.append(f"{section_path} must be an object.")
                continue
            section_id = section.get("id")
            if not isinstance(section_id, str) or not section_id.strip():
                errors.append(f"{section_path}.id is required.")
            elif section_id in section_ids:
                errors.append(f"{section_path}.id '{section_id}' is duplicated.")
            else:
                section_ids.add(section_id)

            section_type = section.get("type")
            if section_type not in {"widget_group", "report_section"}:
                errors.append(f"{section_path}.type must be widget_group or report_section.")

            section_widget_ids = section.get("widget_ids")
            if not isinstance(section_widget_ids, list) or not section_widget_ids:
                errors.append(f"{section_path}.widget_ids must be a non-empty list.")
                continue
            for widget_id in section_widget_ids:
                if widget_id not in widget_ids:
                    errors.append(f"{section_path}.widget_ids references unknown widget '{widget_id}'.")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _has_row_limit(widget: Mapping[str, Any]) -> bool:
    candidates = [widget.get("row_limit")]
    visual = widget.get("visual")
    if isinstance(visual, Mapping):
        candidates.append(visual.get("row_limit"))
    options = widget.get("options")
    if isinstance(options, Mapping):
        candidates.append(options.get("row_limit"))
    return any(isinstance(value, int) and 1 <= value <= 500 for value in candidates)


def _has_bounded_date_range(filters: object) -> bool:
    if not isinstance(filters, Mapping):
        return False
    date_range = filters.get("date_range")
    if isinstance(date_range, str) and date_range in RELATIVE_DATE_RANGES:
        if date_range == "custom":
            return bool(filters.get("start_date") and filters.get("end_date"))
        return True
    return bool(filters.get("start_date") and filters.get("end_date"))
