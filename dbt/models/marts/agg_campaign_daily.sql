{% set using_duckdb = target.type == 'duckdb' %}
{{ config(
    materialized='table' if using_duckdb else 'incremental',
    unique_key=['tenant_id', 'date_day', 'source_platform', 'ad_account_id', 'campaign_id'],
    incremental_strategy='merge' if not using_duckdb else none,
    on_schema_change='sync_all_columns'
) }}

with aggregated as (
    select
        f.tenant_id,
        f.date_day,
        f.source_platform,
        f.ad_account_id,
        f.campaign_id,
        max(f.campaign_name) as campaign_name,
        sum(f.spend) as spend,
        sum(f.impressions) as impressions,
        sum(f.clicks) as clicks,
        sum(f.conversions) as conversions,
        sum(f.reported_conversions) as reported_conversions,
        max(f.attribution_window_days) as attribution_window_days
    from {{ ref('fact_performance') }} f
    where f.campaign_id is not null
    {% if is_incremental() %}
      and f.date_day >= (
          select coalesce(max(date_day), '1900-01-01') from {{ this }}
      )
    {% endif %}
    group by 1, 2, 3, 4, 5
),

enriched as (
    select
        a.tenant_id,
        a.date_day,
        a.source_platform,
        a.ad_account_id,
        a.campaign_id,
        coalesce(dc.campaign_name, a.campaign_id::text) as campaign_name,
        a.spend,
        a.impressions,
        a.clicks,
        a.conversions,
        a.reported_conversions,
        a.attribution_window_days,
        {{ metric_ctr('a.clicks', 'a.impressions') }} as ctr,
        {{ metric_conversion_rate('a.conversions', 'a.clicks') }} as conversion_rate,
        {{ metric_cost_per_click('a.spend', 'a.clicks') }} as cost_per_click,
        {{ metric_cost_per_conversion('a.spend', 'a.conversions') }} as cost_per_conversion,
        {{ metric_cpm('a.spend', 'a.impressions') }} as cpm,
        {{ metric_return_on_ad_spend('a.conversions', 'a.spend') }} as roas,
        dc.parish_code,
        dc.parish_name,
        dc.region_name,
        dc.first_seen_at as first_seen_at
    from aggregated a
    left join {{ ref('dim_campaign') }} dc
        on a.tenant_id = dc.tenant_id
        and a.source_platform = dc.source_platform
        and a.ad_account_id = dc.ad_account_id
        and a.campaign_id = dc.campaign_id
        and a.date_day::timestamp between dc.dbt_valid_from and coalesce(dc.dbt_valid_to, cast('9999-12-31 23:59:59' as timestamp))
)

select *
from enriched
