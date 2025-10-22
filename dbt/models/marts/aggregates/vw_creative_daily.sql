{{ config(materialized='view') }}

with creative_daily as (
    select
        tenant_id,
        date_day,
        source_platform,
        ad_account_id,
        ad_id,
        adset_id,
        campaign_id,
        max(ad_name) as ad_name,
        sum(spend) as spend,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(conversions) as conversions,
        sum(reported_conversions) as reported_conversions
    from {{ ref('fact_performance') }}
    group by 1,2,3,4,5,6,7
),

enriched as (
    select
        cd.tenant_id,
        cd.date_day,
        cd.source_platform,
        cd.ad_account_id,
        cd.ad_id,
        cd.adset_id,
        cd.campaign_id,
        cd.ad_name,
        cd.spend,
        cd.impressions,
        cd.clicks,
        cd.conversions,
        cd.reported_conversions,
        {{ metric_ctr('cd.clicks', 'cd.impressions') }} as ctr,
        {{ metric_conversion_rate('cd.conversions', 'cd.clicks') }} as conversion_rate,
        {{ metric_cost_per_conversion('cd.spend', 'cd.conversions') }} as cost_per_conversion,
        {{ metric_cost_per_click('cd.spend', 'cd.clicks') }} as cost_per_click,
        {{ metric_return_on_ad_spend('cd.conversions', 'cd.spend') }} as roas,
        {{ metric_cpm('cd.spend', 'cd.impressions') }} as cpm,
        d.parish_code,
        d.parish_name,
        d.region_name,
        d.first_seen_at
    from creative_daily cd
    left join {{ ref('dim_ad') }} d
        on cd.tenant_id = d.tenant_id
        and cd.source_platform = d.source_platform
        and cd.ad_account_id = d.ad_account_id
        and cd.ad_id = d.ad_id
        and cd.date_day::timestamp between d.dbt_valid_from and coalesce(d.dbt_valid_to, cast('9999-12-31 23:59:59' as timestamp))
)

select * from enriched
