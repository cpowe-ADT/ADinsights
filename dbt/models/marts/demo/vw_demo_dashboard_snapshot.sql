{{ config(materialized='view') }}

{% set window_days = var('dashboard_window_days', 30) %}

with window_bounds as (
    select
        tenant_id,
        max(date) as window_end_date,
        cast(max(date) - interval '{{ window_days }} day' as date) as window_start_date,
        max(snapshot_generated_at) as generated_at
    from {{ ref('fact_daily_campaign_metrics') }}
    group by 1
),

tenant_currency as (
    select
        tenant_id,
        coalesce(currency, 'USD') as currency
    from {{ ref('dim_tenants') }}
),

scoped_campaign as (
    select
        f.*, 
        c.campaign_name,
        c.status,
        c.objective,
        c.parish,
        c.start_date,
        c.end_date
    from {{ ref('fact_daily_campaign_metrics') }} f
    left join {{ ref('dim_campaigns') }} c
        on f.tenant_id = c.tenant_id
        and f.campaign_id = c.campaign_id
    inner join window_bounds w
        on f.tenant_id = w.tenant_id
        and f.date between w.window_start_date and w.window_end_date
),

summary as (
    select
        tenant_id,
        coalesce(sum(spend), 0) as total_spend,
        coalesce(sum(impressions), 0) as total_impressions,
        coalesce(sum(clicks), 0) as total_clicks,
        coalesce(sum(conversions), 0) as total_conversions,
        {{ metric_return_on_ad_spend('sum(revenue)', 'sum(spend)') }} as average_roas
    from scoped_campaign
    group by 1
),

trend_points as (
    select
        tenant_id,
        date as date_day,
        cast(date as text) as date,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions
    from scoped_campaign
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
        max(channel) as platform,
        coalesce(max(status), 'ACTIVE') as status,
        coalesce(nullif(max(parish), ''), 'Unknown') as parish,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(revenue)', 'sum(spend)') }} as roas,
        {{ metric_ctr('sum(clicks)', 'sum(impressions)') }} as ctr,
        coalesce({{ metric_cost_per_click('sum(spend)', 'sum(clicks)') }}, 0) as cpc,
        {{ metric_cpm('sum(spend)', 'sum(impressions)') }} as cpm,
        max(objective) as objective,
        max(start_date) as start_date,
        max(end_date) as end_date,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from scoped_campaign
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
                    "cpm": "cpm",
                    "objective": "objective",
                    "startDate": "start_date",
                    "endDate": "end_date"
                }),
                "spend desc"
            ) }},
            {{ json_empty_array() }}
        ) as rows
    from top_campaigns
    group by 1
),

creative_scoped as (
    select
        f.*, 
        cr.creative_name,
        cr.creative_type,
        c.campaign_name
    from {{ ref('fact_daily_creative_metrics') }} f
    left join {{ ref('dim_creatives') }} cr
        on f.tenant_id = cr.tenant_id
        and f.creative_id = cr.creative_id
    left join {{ ref('dim_campaigns') }} c
        on f.tenant_id = c.tenant_id
        and f.campaign_id = c.campaign_id
    inner join window_bounds w
        on f.tenant_id = w.tenant_id
        and f.date between w.window_start_date and w.window_end_date
),

creative_rollup as (
    select
        tenant_id,
        creative_id as id,
        max(creative_name) as name,
        campaign_id as campaignId,
        max(campaign_name) as campaignName,
        max(channel) as platform,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(revenue)', 'sum(spend)') }} as roas,
        {{ metric_ctr('sum(clicks)', 'sum(impressions)') }} as ctr,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from creative_scoped
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

parish_scoped as (
    select
        f.tenant_id,
        coalesce(nullif(f.parish, ''), 'Unknown') as parish,
        f.date,
        f.spend,
        f.impressions,
        f.clicks,
        f.conversions,
        f.revenue
    from {{ ref('fact_daily_parish_metrics') }} f
    inner join window_bounds w
        on f.tenant_id = w.tenant_id
        and f.date between w.window_start_date and w.window_end_date
),

parish_rollup as (
    select
        tenant_id,
        parish,
        coalesce(sum(spend), 0) as spend,
        coalesce(sum(impressions), 0) as impressions,
        coalesce(sum(clicks), 0) as clicks,
        coalesce(sum(conversions), 0) as conversions,
        {{ metric_return_on_ad_spend('sum(revenue)', 'sum(spend)') }} as roas,
        row_number() over (
            partition by tenant_id
            order by coalesce(sum(spend), 0) desc
        ) as spend_rank
    from parish_scoped
    group by 1, 2
),

top_parishes as (
    select *
    from parish_rollup
    where spend_rank <= 50
),

parish_rows_json as (
    select
        p.tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "parish": "parish",
                    "spend": "spend",
                    "impressions": "impressions",
                    "clicks": "clicks",
                    "conversions": "conversions",
                    "roas": "roas",
                    "campaignCount": "0",
                    "currency": "c.currency"
                }),
                "spend desc"
            ) }},
            {{ json_empty_array() }}
        ) as parish_metrics
    from top_parishes p
    left join tenant_currency c
        on p.tenant_id = c.tenant_id
    group by 1
),

budget_window as (
    select
        tenant_id,
        cast(date_trunc('month', window_end_date) as date) as month_start,
        cast(date_trunc('month', window_end_date) + interval '1 month - 1 day' as date) as month_end
    from window_bounds
),

budget_plans as (
    select
        b.tenant_id,
        b.campaign_id,
        b.planned_budget,
        w.month_start,
        w.month_end
    from {{ ref('plan_monthly_budgets') }} b
    inner join budget_window w
        on b.tenant_id = w.tenant_id
        and b.month = w.month_start
),

budget_spend as (
    select
        f.tenant_id,
        f.campaign_id,
        coalesce(sum(f.spend), 0) as spend_to_date
    from {{ ref('fact_daily_campaign_metrics') }} f
    inner join budget_window w
        on f.tenant_id = w.tenant_id
        and f.date between w.month_start and w.month_end
    group by 1, 2
),

budget_trailing as (
    select
        tenant_id,
        campaign_id,
        date,
        avg(spend) over (
            partition by tenant_id, campaign_id
            order by date
            rows between 6 preceding and current row
        ) as trailing_7d_avg_spend
    from {{ ref('fact_daily_campaign_metrics') }}
),

budget_latest as (
    select
        tenant_id,
        campaign_id,
        trailing_7d_avg_spend
    from (
        select
            t.*,
            row_number() over (
                partition by tenant_id, campaign_id
                order by date desc
            ) as row_num
        from budget_trailing t
    ) ranked
    where row_num = 1
),

budget_parishes as (
    select
        tenant_id,
        campaign_id,
        coalesce(
            {{ json_array_agg_ordered('parish', 'parish', true) }},
            {{ json_empty_array() }}
        ) as parishes
    from (
        select
            tenant_id,
            campaign_id,
            coalesce(nullif(parish, ''), 'Unknown') as parish
        from {{ ref('dim_campaigns') }}
    ) parishes
    group by 1, 2
),

budget_rollup as (
    select
        p.tenant_id,
        p.campaign_id,
        c.campaign_name as campaign_name,
        coalesce(bp.parishes, {{ json_empty_array() }}) as parishes,
        coalesce(s.spend_to_date, 0) as spend_to_date,
        coalesce(l.trailing_7d_avg_spend, 0) as trailing_7d_avg_spend,
        p.planned_budget,
        p.month_start,
        p.month_end
    from budget_plans p
    left join budget_spend s
        on p.tenant_id = s.tenant_id
        and p.campaign_id = s.campaign_id
    left join budget_latest l
        on p.tenant_id = l.tenant_id
        and p.campaign_id = l.campaign_id
    left join budget_parishes bp
        on p.tenant_id = bp.tenant_id
        and p.campaign_id = bp.campaign_id
    left join {{ ref('dim_campaigns') }} c
        on p.tenant_id = c.tenant_id
        and p.campaign_id = c.campaign_id
),

budget_rows as (
    select
        r.*, 
        r.trailing_7d_avg_spend * extract(day from r.month_end) as projected_spend,
        {{ metric_pacing('r.trailing_7d_avg_spend * extract(day from r.month_end)', 'r.planned_budget') }} as pacing_percent
    from budget_rollup r
),

budget_rows_json as (
    select
        tenant_id,
        coalesce(
            {{ json_array_agg_ordered(
                json_build_object({
                    "id": "campaign_id",
                    "campaignName": "campaign_name",
                    "parishes": "parishes",
                    "monthlyBudget": "planned_budget",
                    "spendToDate": "spend_to_date",
                    "projectedSpend": "projected_spend",
                    "pacingPercent": "pacing_percent",
                    "startDate": "month_start",
                    "endDate": "month_end"
                }),
                "spend_to_date desc"
            ) }},
            {{ json_empty_array() }}
        ) as budget_metrics
    from budget_rows
    group by 1
),

campaign_metrics_json as (
    select
        s.tenant_id,
        {{ json_build_object({
            "summary": json_build_object({
                "currency": "c.currency",
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
    left join tenant_currency c
        on s.tenant_id = c.tenant_id
)

select
    w.tenant_id,
    w.generated_at,
    coalesce(
        cm.campaign_metrics,
        {{ json_build_object({
            "summary": json_build_object({
                "currency": "'USD'",
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
    coalesce(bj.budget_metrics, {{ json_empty_array() }}) as budget_metrics,
    coalesce(pj.parish_metrics, {{ json_empty_array() }}) as parish_metrics
from window_bounds w
left join campaign_metrics_json cm
    on w.tenant_id = cm.tenant_id
left join creative_rows_json cj
    on w.tenant_id = cj.tenant_id
left join budget_rows_json bj
    on w.tenant_id = bj.tenant_id
left join parish_rows_json pj
    on w.tenant_id = pj.tenant_id
