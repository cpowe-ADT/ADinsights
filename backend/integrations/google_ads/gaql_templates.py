from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class GaqlTemplate:
    key: str
    title: str
    description: str
    query: str


GAQL_TEMPLATES: dict[str, GaqlTemplate] = {
    "campaign_daily_performance": GaqlTemplate(
        key="campaign_daily_performance",
        title="Campaign Daily Performance",
        description="Daily campaign-level metrics used by top-line dashboard widgets.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "customer.currency_code, "
            "campaign.id, "
            "campaign.name, "
            "campaign.status, "
            "campaign.advertising_channel_type, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM campaign "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "ad_group_ad_daily_performance": GaqlTemplate(
        key="ad_group_ad_daily_performance",
        title="Ad Group Ad Daily Performance",
        description="Creative-level daily metrics for creative scorecards and drilldowns.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "campaign.id, "
            "campaign.name, "
            "ad_group.id, "
            "ad_group.name, "
            "ad_group_ad.ad.id, "
            "ad_group_ad.ad.name, "
            "ad_group_ad.status, "
            "ad_group_ad.policy_summary.approval_status, "
            "ad_group_ad.policy_summary.review_status, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM ad_group_ad "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "geographic_daily_performance": GaqlTemplate(
        key="geographic_daily_performance",
        title="Geographic Daily Performance",
        description="Geo rollups powering parish/region maps and location drilldowns.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "campaign.id, "
            "campaign.name, "
            "segments.geo_target_region, "
            "segments.geo_target_city, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM geographic_view "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "keyword_daily_performance": GaqlTemplate(
        key="keyword_daily_performance",
        title="Keyword Daily Performance",
        description="Keyword-level daily metrics used for keyword performance diagnostics.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "customer.currency_code, "
            "campaign.id, "
            "ad_group.id, "
            "ad_group_criterion.criterion_id, "
            "ad_group_criterion.status, "
            "ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type, "
            "ad_group_criterion.quality_info.quality_score, "
            "ad_group_criterion.quality_info.ad_relevance, "
            "ad_group_criterion.quality_info.expected_clickthrough_rate, "
            "ad_group_criterion.quality_info.landing_page_experience, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM keyword_view "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "search_term_daily_performance": GaqlTemplate(
        key="search_term_daily_performance",
        title="Search Term Daily Performance",
        description="Search term daily performance for query mining and negatives workflows.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "customer.currency_code, "
            "campaign.id, "
            "ad_group.id, "
            "ad_group_criterion.criterion_id, "
            "search_term_view.search_term, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM search_term_view "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "asset_group_daily_performance": GaqlTemplate(
        key="asset_group_daily_performance",
        title="Asset Group Daily Performance",
        description="Performance Max asset group daily metrics.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "customer.currency_code, "
            "campaign.id, "
            "campaign.advertising_channel_type, "
            "asset_group.id, "
            "asset_group.name, "
            "asset_group.status, "
            "metrics.impressions, "
            "metrics.clicks, "
            "metrics.conversions, "
            "metrics.conversions_value, "
            "metrics.cost_micros "
            "FROM asset_group "
            "WHERE campaign.advertising_channel_type = PERFORMANCE_MAX "
            "AND segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "conversion_action_daily_performance": GaqlTemplate(
        key="conversion_action_daily_performance",
        title="Conversion Action Daily Performance",
        description="Conversion action daily totals for attribution views.",
        query=(
            "SELECT "
            "segments.date, "
            "customer.id, "
            "conversion_action.id, "
            "conversion_action.name, "
            "conversion_action.type, "
            "metrics.conversions, "
            "metrics.all_conversions, "
            "metrics.conversions_value "
            "FROM conversion_action "
            "WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        ),
    ),
    "change_event_incremental": GaqlTemplate(
        key="change_event_incremental",
        title="Change Event Incremental",
        description="Incremental account change history query for governance timelines.",
        query=(
            "SELECT "
            "change_event.change_date_time, "
            "change_event.user_email, "
            "change_event.client_type, "
            "change_event.change_resource_type, "
            "change_event.resource_change_operation, "
            "change_event.campaign, "
            "change_event.ad_group, "
            "change_event.ad, "
            "change_event.changed_fields "
            "FROM change_event "
            "WHERE change_event.change_date_time >= '{start_datetime}' "
            "AND change_event.change_date_time < '{end_datetime}'"
        ),
    ),
    "recommendations_inventory": GaqlTemplate(
        key="recommendations_inventory",
        title="Recommendations Inventory",
        description="Recommendation inventory for opportunity tracking.",
        query=(
            "SELECT "
            "customer.id, "
            "recommendation.type, "
            "recommendation.resource_name, "
            "recommendation.campaign, "
            "recommendation.ad_group, "
            "recommendation.dismissed, "
            "recommendation.impact, "
            "recommendation.primary_status "
            "FROM recommendation"
        ),
    ),
    "accessible_customers": GaqlTemplate(
        key="accessible_customers",
        title="Accessible Customers",
        description="Accessible account discovery under manager credentials.",
        query=(
            "SELECT "
            "customer_client.id, "
            "customer_client.descriptive_name, "
            "customer_client.currency_code, "
            "customer_client.time_zone, "
            "customer_client.status, "
            "customer_client.manager "
            "FROM customer_client "
            "WHERE customer_client.level <= 1"
        ),
    ),
}


def get_gaql_template(key: str) -> GaqlTemplate:
    if key not in GAQL_TEMPLATES:
        raise KeyError(f"Unknown GAQL template: {key}")
    return GAQL_TEMPLATES[key]


def _format_template_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def render_gaql_template(key: str, **params: object) -> str:
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if isinstance(start_date, date) and isinstance(end_date, date) and start_date > end_date:
        raise ValueError("start_date must be less than or equal to end_date.")
    start_datetime = params.get("start_datetime")
    end_datetime = params.get("end_datetime")
    if (
        isinstance(start_datetime, datetime)
        and isinstance(end_datetime, datetime)
        and start_datetime > end_datetime
    ):
        raise ValueError("start_datetime must be less than or equal to end_datetime.")
    template = get_gaql_template(key)
    formatted = {name: _format_template_value(value) for name, value in params.items()}
    return template.query.format(**formatted)
