{{ config(
    materialized='incremental',
    unique_key=['date_day', 'source_platform', 'ad_account_id', 'campaign_id'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

with aggregated as (
    select
        f.date_day,
        f.source_platform,
        f.ad_account_id,
        f.campaign_id,
        sum(f.spend) as spend,
        sum(f.impressions) as impressions,
        sum(f.clicks) as clicks,
        sum(f.conversions) as conversions
    from {{ ref('fct_ad_performance') }} f
    where f.campaign_id is not null
    {% if is_incremental() %}
      and f.date_day >= (
          select coalesce(max(date_day), '1900-01-01') from {{ this }}
      )
    {% endif %}
    group by 1, 2, 3, 4
),

enriched as (
    select
        a.date_day,
        a.source_platform,
        a.ad_account_id,
        a.campaign_id,
        coalesce(dc.campaign_name, a.campaign_id::text) as campaign_name,
        a.spend,
        a.impressions,
        a.clicks,
        a.conversions,
        {{ metric_ctr('a.clicks', 'a.impressions') }} as ctr,
        {{ metric_conversion_rate('a.conversions', 'a.clicks') }} as conversion_rate,
        {{ metric_cost_per_click('a.spend', 'a.clicks') }} as cost_per_click,
        {{ metric_cost_per_conversion('a.spend', 'a.conversions') }} as cost_per_conversion,
        {{ metric_cpm('a.spend', 'a.impressions') }} as cpm,
        dc.parish_code,
        dc.parish_name,
        dc.region_name,
        dc.first_seen_date
    from aggregated a
    left join {{ ref('dim_campaign') }} dc
        on a.source_platform = dc.source_platform
        and a.ad_account_id = dc.ad_account_id
        and a.campaign_id = dc.campaign_id
        and a.date_day between dc.valid_from and dc.valid_to
)

select *
from enriched
