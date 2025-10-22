{{ config(
    materialized='incremental',
    unique_key=['date_day', 'source_platform', 'ad_account_id'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

{% set lookback_days = 7 %}

with base_account_daily as (
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
    {% if is_incremental() %}
    where date_day >= (
        select coalesce(max(date_day), cast('1900-01-01' as date))
        from {{ this }}
    ) - interval '{{ lookback_days }} day'
    {% endif %}
    group by 1,2,3,4
)
{% if is_incremental() %}
, historical_account_daily as (
    select
        existing.tenant_id,
        existing.date_day,
        existing.source_platform,
        existing.ad_account_id,
        existing.spend,
        existing.impressions,
        existing.clicks,
        existing.conversions,
        existing.reported_conversions
    from {{ this }} existing
    left join base_account_daily latest
        on existing.tenant_id = latest.tenant_id
        and existing.source_platform = latest.source_platform
        and existing.ad_account_id = latest.ad_account_id
        and existing.date_day = latest.date_day
    where latest.date_day is null
)
, account_daily as (
    select * from base_account_daily
    union all
    select * from historical_account_daily
)
{% else %}
, account_daily as (
    select * from base_account_daily
)
{% endif %}
,

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
        ) as trailing_7d_avg_spend
    from account_daily ad
),

enriched as (
    select
        w.date_day,
        w.source_platform,
        w.ad_account_id,
        w.spend,
        w.impressions,
        w.clicks,
        w.conversions,
        w.cumulative_spend,
        w.trailing_7d_avg_spend,
        {{ metric_ctr('w.clicks', 'w.impressions') }} as ctr,
        {{ metric_conversion_rate('w.conversions', 'w.clicks') }} as conversion_rate,
        {{ metric_cost_per_click('w.spend', 'w.clicks') }} as cost_per_click,
        {{ metric_cost_per_conversion('w.spend', 'w.conversions') }} as cost_per_conversion,
        {{ metric_return_on_ad_spend('w.conversions', 'w.spend') }} as roas,
        {{ metric_cpm('w.spend', 'w.impressions') }} as cpm,
        {{ metric_pacing('w.spend', 'w.trailing_7d_avg_spend') }} as pacing_vs_7d_avg
    from windowed w
)

select *
from enriched
