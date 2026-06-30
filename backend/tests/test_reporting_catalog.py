from __future__ import annotations

from copy import deepcopy

import pytest

from analytics.reporting_catalog import (
    DASHBOARD_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    ReportingCatalogValidationError,
    get_reporting_catalog,
    validate_dashboard_layout,
    validate_report_layout,
)


def valid_dashboard_v1_layout() -> dict:
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "layout": {
            "columns": 12,
            "slots": [
                {
                    "id": "slot_spend_trend",
                    "widget_id": "spend_trend",
                    "cols": 8,
                    "rows": 2,
                }
            ],
        },
        "widgets": [
            {
                "id": "spend_trend",
                "type": "line_chart",
                "dataset": "paid_meta_ads",
                "metrics": ["spend"],
                "dimensions": ["date"],
                "filters": {"date_range": "last_90d"},
                "coverage_policy": "render_with_warning",
                "visual": {"title": "Spend trend", "source_labels": True},
            }
        ],
    }


def assert_layout_error(layout: dict, expected: str) -> None:
    with pytest.raises(ReportingCatalogValidationError) as exc_info:
        validate_dashboard_layout(layout)
    assert expected in " ".join(exc_info.value.errors)


def test_validate_dashboard_layout_accepts_legacy_layout_without_schema_version():
    legacy = {"routeKind": "campaigns", "widgets": ["kpis", "trend"]}

    assert validate_dashboard_layout(legacy) == legacy


def test_validate_dashboard_layout_accepts_valid_dashboard_v1():
    layout = valid_dashboard_v1_layout()

    assert validate_dashboard_layout(layout) == layout


def test_get_reporting_catalog_exposes_builder_metadata():
    catalog = get_reporting_catalog()

    assert catalog["schema_version"] == "reporting_catalog.v1"
    assert catalog["dashboard_schema_version"] == DASHBOARD_SCHEMA_VERSION
    assert catalog["report_schema_version"] == REPORT_SCHEMA_VERSION
    assert {"datasets", "metrics", "dimensions", "widgets", "compatibility"} <= set(catalog)
    assert any(dataset["key"] == "paid_meta_ads" for dataset in catalog["datasets"])
    assert any(
        metric["dataset"] == "paid_meta_ads" and metric["key"] == "spend"
        for metric in catalog["metrics"]
    )
    assert any(widget["key"] == "data_table" for widget in catalog["widgets"])
    assert catalog["compatibility"]["table"]["requires_row_limit"] is True
    assert "render_with_warning" in catalog["coverage_policies"]


def test_validate_dashboard_layout_rejects_unknown_dataset():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["dataset"] = "unknown_dataset"

    assert_layout_error(layout, "dataset is not a valid dataset")


def test_validate_dashboard_layout_rejects_metric_not_valid_for_dataset():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["dataset"] = "organic_facebook_page"
    layout["widgets"][0]["metrics"] = ["spend"]

    assert_layout_error(layout, "metric 'spend' not valid for organic_facebook_page")


def test_validate_dashboard_layout_rejects_dimension_not_valid_for_dataset():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["dataset"] = "organic_facebook_page"
    layout["widgets"][0]["metrics"] = ["page_engagements"]
    layout["widgets"][0]["dimensions"] = ["campaign"]

    assert_layout_error(layout, "dimension 'campaign' not valid for organic_facebook_page")


def test_validate_dashboard_layout_rejects_invalid_widget_type():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["type"] = "heatmap"

    assert_layout_error(layout, "type is not a valid widget type")


def test_validate_dashboard_layout_rejects_table_without_row_limit():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0].update(
        {
            "type": "data_table",
            "dimensions": ["campaign"],
            "visual": {"title": "Campaign table", "source_labels": True},
        }
    )

    assert_layout_error(layout, "data_table widgets require row_limit")


def test_validate_dashboard_layout_rejects_missing_source_labels_for_combined_source_dimension():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0].update(
        {
            "type": "bar_chart",
            "dataset": "combined_paid_media",
            "metrics": ["spend"],
            "dimensions": ["platform"],
            "visual": {"title": "Paid platform split"},
        }
    )

    assert_layout_error(layout, "visual.source_labels must be true")


def test_validate_dashboard_layout_rejects_deprecated_or_unknown_page_metric():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0].update(
        {
            "dataset": "organic_facebook_page",
            "metrics": ["page_video_views_10s"],
            "dimensions": ["date"],
        }
    )

    assert_layout_error(layout, "deprecated or unknown metric 'page_video_views_10s'")


def test_validate_dashboard_layout_rejects_invalid_coverage_policy():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["coverage_policy"] = "hope_for_the_best"

    assert_layout_error(layout, "coverage_policy is not valid")


def test_validate_dashboard_layout_rejects_unbounded_date_range():
    layout = valid_dashboard_v1_layout()
    layout["widgets"][0]["filters"] = {"client_id": "client-1"}

    assert_layout_error(layout, "filters must include a bounded date range")


def test_validate_dashboard_layout_rejects_malformed_slot_widget_reference():
    layout = valid_dashboard_v1_layout()
    layout["layout"]["slots"][0]["widget_id"] = "missing_widget"

    assert_layout_error(layout, "widget_id must reference an existing widget")


def test_validate_dashboard_layout_rejects_unsupported_schema_version():
    layout = deepcopy(valid_dashboard_v1_layout())
    layout["schema_version"] = "dashboard.v99"

    assert_layout_error(layout, "unsupported layout schema_version")


def valid_report_v1_layout() -> dict:
    widget = valid_dashboard_v1_layout()["widgets"][0]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "template_key": "slb_monthly_social_report",
        "catalog_schema_version": "reporting_catalog.v1",
        "pages": [
            {
                "id": "paid_meta_ads",
                "title": "Paid Meta Ads performance",
                "sections": [
                    {
                        "id": "paid_widgets",
                        "type": "widget_group",
                        "widget_ids": [widget["id"]],
                    }
                ],
            }
        ],
        "widgets": [widget],
    }


def assert_report_layout_error(layout: dict, expected: str) -> None:
    with pytest.raises(ReportingCatalogValidationError) as exc_info:
        validate_report_layout(layout)
    assert expected in " ".join(exc_info.value.errors)


def test_validate_report_layout_accepts_legacy_layout_without_schema_version():
    legacy = {"sections": ["summary"], "format": "pdf"}

    assert validate_report_layout(legacy) == legacy


def test_validate_report_layout_accepts_valid_report_v1():
    layout = valid_report_v1_layout()

    assert validate_report_layout(layout) == layout


def test_validate_report_layout_rejects_unknown_widget_reference():
    layout = valid_report_v1_layout()
    layout["pages"][0]["sections"][0]["widget_ids"] = ["missing_widget"]

    assert_report_layout_error(layout, "references unknown widget 'missing_widget'")


def test_validate_report_layout_rejects_invalid_widget_config():
    layout = valid_report_v1_layout()
    layout["widgets"][0]["coverage_policy"] = "hope_for_the_best"

    assert_report_layout_error(layout, "coverage_policy is not valid")


def test_validate_report_layout_rejects_unsupported_schema_version():
    layout = valid_report_v1_layout()
    layout["schema_version"] = "report.v99"

    assert_report_layout_error(layout, "unsupported report layout schema_version")
