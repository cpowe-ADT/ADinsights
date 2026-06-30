"""Reusable governed reporting templates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


SLB_MONTHLY_TEMPLATE_KEY = "slb_monthly_social_report"
SLB_EXPORT_WARNING_ONLY_COVERAGE_STATUSES: dict[str, tuple[str, ...]] = {
    "paid_meta_ads": ("partial", "missing_history", "not_previously_synced"),
    "organic_facebook_page": ("missing_history", "not_previously_synced"),
    "organic_facebook_posts": ("missing_history", "not_previously_synced"),
    "content_ops": ("missing_history", "not_previously_synced"),
}


@dataclass(frozen=True)
class ReportTemplateDefinition:
    template_key: str
    label: str
    version: str
    supported_datasets: tuple[str, ...]
    required_sources: tuple[str, ...]
    builder: Callable[..., dict[str, Any]]
    eligibility: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_key": self.template_key,
            "label": self.label,
            "version": self.version,
            "supported_datasets": list(self.supported_datasets),
            "required_sources": list(self.required_sources),
            "export_policy": get_template_export_policy(self.template_key),
            "eligibility": dict(self.eligibility),
        }


def build_slb_monthly_report_layout(
    *,
    date_range: str = "last_month",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    filters: dict[str, Any] = {"date_range": date_range}
    if date_range == "custom":
        filters.update({"start_date": start_date, "end_date": end_date})

    widgets = [
        _report_section("cover_period", "Cover and reporting period"),
        _kpi("paid_summary", "paid_meta_ads", ["spend", "reach", "clicks"], filters),
        _line("paid_spend_trend", "paid_meta_ads", ["spend"], filters),
        _table(
            "paid_campaign_table",
            "paid_meta_ads",
            ["campaign"],
            ["spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm", "conversions"],
            filters,
        ),
        _kpi(
            "organic_page_summary",
            "organic_facebook_page",
            ["page_follows"],
            filters,
        ),
        _kpi(
            "organic_post_engagement_summary",
            "organic_facebook_page",
            ["post_reactions", "post_comments", "post_shares"],
            filters,
        ),
        _line(
            "organic_engagement_trend",
            "organic_facebook_page",
            ["post_reactions", "post_comments", "post_shares"],
            filters,
        ),
        _report_section(
            "organic_reach_impressions_note",
            "Reach and impressions availability",
            (
                "Organic Facebook reach and impressions are unavailable in ADinsights until Meta "
                "approves the required insights access. This report uses Page follows plus post "
                "reactions, comments, and shares from the approved engagement edge path instead."
            ),
        ),
        _table(
            "top_posts_table",
            "organic_facebook_page",
            ["post"],
            ["post_reactions", "post_comments", "post_shares"],
            filters,
        ),
        _kpi(
            "content_activity_summary",
            "content_ops",
            ["published_posts", "content_items_created"],
            filters,
        ),
        _report_section("recommendations", "Recommendations and next actions"),
        _report_section("appendix_data_notes", "Appendix and data notes"),
    ]

    return {
        "schema_version": "report.v1",
        "template_key": SLB_MONTHLY_TEMPLATE_KEY,
        "catalog_schema_version": "reporting_catalog.v1",
        "export_policy": get_template_export_policy(SLB_MONTHLY_TEMPLATE_KEY),
        "pages": [
            _page("cover", "Cover and period", ["cover_period"]),
            _page(
                "executive_summary",
                "Executive summary",
                ["paid_summary", "organic_page_summary", "organic_post_engagement_summary"],
            ),
            _page(
                "paid_meta_ads",
                "Paid Meta Ads performance",
                ["paid_spend_trend", "paid_campaign_table"],
            ),
            _page(
                "organic_facebook",
                "Organic Facebook/Page performance",
                ["organic_engagement_trend", "organic_reach_impressions_note"],
            ),
            _page("top_posts", "Top posts", ["top_posts_table"]),
            _page("content_activity", "Content activity/work completed", ["content_activity_summary"]),
            _page("recommendations", "Recommendations and next actions", ["recommendations"]),
            _page("appendix", "Appendix/data notes", ["appendix_data_notes"]),
        ],
        "widgets": widgets,
    }


REPORT_TEMPLATE_REGISTRY: dict[str, ReportTemplateDefinition] = {
    SLB_MONTHLY_TEMPLATE_KEY: ReportTemplateDefinition(
        template_key=SLB_MONTHLY_TEMPLATE_KEY,
        label="SLB monthly social report",
        version="1",
        supported_datasets=("paid_meta_ads", "organic_facebook_page", "content_ops"),
        required_sources=("meta_marketing_credential", "facebook_page", "content_ops_workspace"),
        builder=build_slb_monthly_report_layout,
        eligibility={
            "instagram": "deferred_v1",
            "requires_stored_aggregate_data": True,
            "allows_live_provider_calls_at_render_time": False,
        },
    )
}


def get_template_export_policy(template_key: str) -> dict[str, Any]:
    if template_key != SLB_MONTHLY_TEMPLATE_KEY:
        return {"warning_only_coverage_statuses": {}}
    return {
        "warning_only_coverage_statuses": {
            dataset: list(statuses)
            for dataset, statuses in SLB_EXPORT_WARNING_ONLY_COVERAGE_STATUSES.items()
        },
        "notes": [
            "SLB monthly reports may export missing/partial stored-data sections as explicit "
            "warnings when no permission, unsupported-metric, or unscoped paid-account blocker "
            "is present. Missing metrics remain no-data values; unrelated paid account rows must "
            "not be substituted."
        ],
    }


def get_report_template_registry() -> list[dict[str, Any]]:
    return [
        definition.as_dict()
        for definition in sorted(REPORT_TEMPLATE_REGISTRY.values(), key=lambda item: item.template_key)
    ]


def get_report_template_definition(template_key: str) -> ReportTemplateDefinition | None:
    return REPORT_TEMPLATE_REGISTRY.get(template_key)


def build_report_layout_from_template(
    *,
    template_key: str,
    date_range: str = "last_month",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    definition = get_report_template_definition(template_key)
    if definition is None:
        raise KeyError(template_key)
    return definition.builder(
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
    )


def _page(page_id: str, title: str, widget_ids: list[str]) -> dict[str, Any]:
    return {
        "id": page_id,
        "title": title,
        "sections": [{"id": f"{page_id}_widgets", "type": "widget_group", "widget_ids": widget_ids}],
    }


def _kpi(widget_id: str, dataset: str, metrics: list[str], filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "kpi",
        "dataset": dataset,
        "metrics": metrics,
        "dimensions": [],
        "filters": dict(filters),
        "coverage_policy": "render_with_warning",
        "visual": {"title": widget_id.replace("_", " ").title(), "source_labels": True},
    }


def _line(widget_id: str, dataset: str, metrics: list[str], filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "line_chart",
        "dataset": dataset,
        "metrics": metrics,
        "dimensions": ["date"],
        "filters": dict(filters),
        "coverage_policy": "render_with_warning",
        "visual": {"title": widget_id.replace("_", " ").title(), "source_labels": True},
    }


def _table(
    widget_id: str,
    dataset: str,
    dimensions: list[str],
    metrics: list[str],
    filters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "data_table",
        "dataset": dataset,
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": dict(filters),
        "coverage_policy": "render_with_warning",
        "visual": {
            "title": widget_id.replace("_", " ").title(),
            "source_labels": True,
            "row_limit": 25,
        },
    }


def _report_section(widget_id: str, title: str, body: str = "") -> dict[str, Any]:
    return {
        "id": widget_id,
        "type": "report_section",
        "dataset": "content_ops",
        "metrics": [],
        "dimensions": [],
        "filters": {"date_range": "last_month"},
        "coverage_policy": "render_with_warning",
        "visual": {"title": title, "body": body, "source_labels": True},
    }
