{{ config(materialized='view') }}

with account_daily as (
    select
        tenant_id,
        date_day,
        source_platform,
        ad_account_id,
        sum(spend) as spend,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(conversions) as conversions,
        sum(reported_conversions) as reported_conversions
    from {{ ref('fact_performance') }}
    group by 1,2,3,4
),

windowed as (
    select
        ad.tenant_id,
        ad.date_day,
        ad.source_platform,
        ad.ad_account_id,
        ad.spend,
        ad.impressions,
        ad.clicks,
        ad.conversions,
        ad.reported_conversions,
        sum(ad.spend) over (
            partition by ad.tenant_id, ad.source_platform, ad.ad_account_id
            order by ad.date_day
            rows between unbounded preceding and current row
        ) as cumulative_spend,
        avg(ad.spend) over (
            partition by ad.tenant_id, ad.source_platform, ad.ad_account_id
            order by ad.date_day
            rows between 6 preceding and current row
        ) as trailing_7d_avg_spend,
        {{ metric_ctr('ad.clicks', 'ad.impressions') }} as ctr,
        {{ metric_conversion_rate('ad.conversions', 'ad.clicks') }} as conversion_rate,
        {{ metric_cost_per_conversion('ad.spend', 'ad.conversions') }} as cost_per_conversion,
        {{ metric_return_on_ad_spend('ad.conversions', 'ad.spend') }} as roas,
        {{ metric_cpm('ad.spend', 'ad.impressions') }} as cpm
    from account_daily ad
)

select * from windowed
