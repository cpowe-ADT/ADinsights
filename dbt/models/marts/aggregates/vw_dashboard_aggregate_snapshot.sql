{{ config(materialized='view') }}

{% set currency_code = var('currency_code', 'USD') %}
{% set window_days = var('dashboard_window_days', 30) %}
{% set currency_literal = "'" ~ currency_code ~ "'" %}

with window_bounds as (
    select
        tenant_id,
        max(date_day) as window_end_date,
        cast(max(date_day) - interval '{{ window_days }} day' as date) as window_start_date,
        max(effective_from) as generated_at
    from {{ ref('fact_performance') }}
    group by 1
),

scoped as (
    select f.*
    from {{ ref('fact_performance') }} f
    inner join window_bounds w
        on f.tenant_id = w.tenant_id
        and f.date_day between w.window_start_date and w.window_end_date
),

summary as (
    select
        tenant_id,
        coalesce(sum(spend), 0) as total_spend,
        coalesce(sum(impressions), 0) as total_impressions,
        coalesce(sum(clicks), 0) as total_clicks,
        coalesce(sum(conversions), 0) as total_conversions,
        {{ metric_return_on_ad_spend('sum(conversions)', 'sum(spend)') }} as average_roas
    from scoped
    group by 1
),

trend_points as (
    select
        tenant_id,
        date_day,
        cast(date_day as text) as date,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions
    from scoped
    group by 1, 2, 3
),

trend_json as (
    select
        tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "date": "date",
                    "spend": "spend",
                    "conversions": "conversions",
                    "clicks": "clicks",
                    "impressions": "impressions"
                }),
                "date_day"
            ) }},
            {{ json_empty_array() }}
        ) as trend
    from trend_points
    group by 1
),

campaign_rollup as (
    select
        tenant_id,
        campaign_id as id,
        max(campaign_name) as name,
        case max(source_platform)
            when 'meta_ads' then 'Meta'
            when 'google_ads' then 'Google'
            when 'linkedin' then 'LinkedIn'
            when 'tiktok' then 'TikTok'
            else max(source_platform)
        end as platform,
        'ACTIVE' as status,
        coalesce(max(parish_name), 'Unknown') as parish,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(conversions)', 'sum(spend)') }} as roas,
        {{ metric_ctr('sum(clicks)', 'sum(impressions)') }} as ctr,
        coalesce({{ metric_cost_per_click('sum(spend)', 'sum(clicks)') }}, 0) as cpc,
        {{ metric_cpm('sum(spend)', 'sum(impressions)') }} as cpm,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from scoped
    where campaign_id is not null
    group by 1, 2
),

top_campaigns as (
    select *
    from campaign_rollup
    where spend_rank <= 50
),

campaign_rows_json as (
    select
        tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "id": "id",
                    "name": "name",
                    "platform": "platform",
                    "status": "status",
                    "parish": "parish",
                    "spend": "spend",
                    "impressions": "impressions",
                    "clicks": "clicks",
                    "conversions": "conversions",
                    "roas": "roas",
                    "ctr": "ctr",
                    "cpc": "cpc",
                    "cpm": "cpm"
                }),
                "spend desc"
            ) }},
            {{ json_empty_array() }}
        ) as rows
    from top_campaigns
    group by 1
),

creative_rollup as (
    select
        tenant_id,
        ad_id as id,
        max(ad_name) as name,
        campaign_id as campaignId,
        max(campaign_name) as campaignName,
        case max(source_platform)
            when 'meta_ads' then 'Meta'
            when 'google_ads' then 'Google'
            when 'linkedin' then 'LinkedIn'
            when 'tiktok' then 'TikTok'
            else max(source_platform)
        end as platform,
        coalesce(max(parish_name), 'Unknown') as parish,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(conversions)', 'sum(spend)') }} as roas,
        {{ metric_ctr('sum(clicks)', 'sum(impressions)') }} as ctr,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from scoped
    where ad_id is not null
      and campaign_id is not null
    group by 1, 2, 4
),

top_creatives as (
    select *
    from creative_rollup
    where spend_rank <= 50
),

creative_rows_json as (
    select
        tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "id": "id",
                    "name": "name",
                    "campaignId": "campaignId",
                    "campaignName": "campaignName",
                    "platform": "platform",
                    "parish": "parish",
                    "spend": "spend",
                    "impressions": "impressions",
                    "clicks": "clicks",
                    "conversions": "conversions",
                    "roas": "roas",
                    "ctr": "ctr"
                }),
                "spend desc"
            ) }},
            {{ json_empty_array() }}
        ) as creative_metrics
    from top_creatives
    group by 1
),

parish_rollup as (
    select
        tenant_id,
        coalesce(parish_name, 'Unknown') as parish,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(conversions)', 'sum(spend)') }} as roas,
        coalesce(count(distinct campaign_id), 0) as campaignCount,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from scoped
    group by 1, 2
),

top_parishes as (
    select *
    from parish_rollup
    where spend_rank <= 50
),

parish_rows_json as (
    select
        tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "parish": "parish",
                    "spend": "spend",
                    "impressions": "impressions",
                    "clicks": "clicks",
                    "conversions": "conversions",
                    "roas": "roas",
                    "campaignCount": "campaignCount",
                    "currency": currency_literal
                }),
                "spend desc"
            ) }},
            {{ json_empty_array() }}
        ) as parish_metrics
    from top_parishes
    group by 1
),

campaign_metrics_json as (
    select
        s.tenant_id,
        {{ json_build_object({
            "summary": json_build_object({
                "currency": currency_literal,
                "totalSpend": "s.total_spend",
                "totalImpressions": "s.total_impressions",
                "totalClicks": "s.total_clicks",
                "totalConversions": "s.total_conversions",
                "averageRoas": "s.average_roas"
            }),
            "trend": "t.trend",
            "rows": "r.rows"
        }) }} as campaign_metrics
    from summary s
    left join trend_json t
        on s.tenant_id = t.tenant_id
    left join campaign_rows_json r
        on s.tenant_id = r.tenant_id
)

select
    w.tenant_id,
    w.generated_at,
    coalesce(
        cm.campaign_metrics,
        {{ json_build_object({
            "summary": json_build_object({
                "currency": currency_literal,
                "totalSpend": "0",
                "totalImpressions": "0",
                "totalClicks": "0",
                "totalConversions": "0",
                "averageRoas": "0"
            }),
            "trend": json_empty_array(),
            "rows": json_empty_array()
        }) }}
    ) as campaign_metrics,
    coalesce(cj.creative_metrics, {{ json_empty_array() }}) as creative_metrics,
    {{ json_empty_array() }} as budget_metrics,
    coalesce(pj.parish_metrics, {{ json_empty_array() }}) as parish_metrics
from window_bounds w
left join campaign_metrics_json cm
    on w.tenant_id = cm.tenant_id
left join creative_rows_json cj
    on w.tenant_id = cj.tenant_id
left join parish_rows_json pj
    on w.tenant_id = pj.tenant_id
