{{ config(materialized='view') }}

with account_daily as (
    select
        date_day,
        source_platform,
        ad_account_id,
        sum(spend) as spend,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(conversions) as conversions
    from {{ ref('fct_ad_performance') }}
    group by 1,2,3
),

windowed as (
    select
        ad.date_day,
        ad.source_platform,
        ad.ad_account_id,
        ad.spend,
        ad.impressions,
        ad.clicks,
        ad.conversions,
        sum(ad.spend) over (
            partition by ad.source_platform, ad.ad_account_id
            order by ad.date_day
            rows between unbounded preceding and current row
        ) as cumulative_spend,
        avg(ad.spend) over (
            partition by ad.source_platform, ad.ad_account_id
            order by ad.date_day
            rows between 6 preceding and current row
        ) as trailing_7d_avg_spend,
        {{ metric_ctr('ad.clicks', 'ad.impressions') }} as ctr,
        {{ metric_conversion_rate('ad.conversions', 'ad.clicks') }} as conversion_rate,
        {{ metric_cost_per_conversion('ad.spend', 'ad.conversions') }} as cost_per_conversion,
        {{ metric_cpm('ad.spend', 'ad.impressions') }} as cpm
    from account_daily ad
)

select * from windowed
