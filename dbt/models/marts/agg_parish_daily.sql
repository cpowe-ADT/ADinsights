{% set using_duckdb = target.type == 'duckdb' %}
{{ config(
    materialized='table' if using_duckdb else 'incremental',
    unique_key=['tenant_id', 'date_day', 'parish_code'],
    incremental_strategy='merge' if not using_duckdb else none,
    on_schema_change='sync_all_columns'
) }}

with aggregated as (
    select
        f.tenant_id,
        f.date_day,
        coalesce(f.parish_code, 'UNK') as parish_code,
        sum(f.spend) as spend,
        sum(f.impressions) as impressions,
        sum(f.clicks) as clicks,
        sum(f.conversions) as conversions,
        sum(f.reported_conversions) as reported_conversions,
        count(distinct f.campaign_id) as campaign_count
    from {{ ref('fact_performance') }} f
    {% if is_incremental() %}
      where f.date_day >= (
          select coalesce(max(date_day), '1900-01-01') from {{ this }}
      )
    {% endif %}
    group by 1, 2, 3
),

enriched as (
    select
        a.tenant_id,
        a.date_day,
        a.parish_code,
        coalesce(dg.parish_name, 'Unknown') as parish_name,
        coalesce(dg.region_name, 'Unknown') as region_name,
        a.spend,
        a.impressions,
        a.clicks,
        a.conversions,
        a.reported_conversions,
        a.campaign_count,
        {{ metric_ctr('a.clicks', 'a.impressions') }} as ctr,
        {{ metric_conversion_rate('a.conversions', 'a.clicks') }} as conversion_rate,
        {{ metric_cost_per_click('a.spend', 'a.clicks') }} as cost_per_click,
        {{ metric_cost_per_conversion('a.spend', 'a.conversions') }} as cost_per_conversion,
        {{ metric_cpm('a.spend', 'a.impressions') }} as cpm,
        {{ metric_return_on_ad_spend('a.conversions', 'a.spend') }} as roas
    from aggregated a
    left join {{ ref('dim_geo') }} dg
        on a.tenant_id = dg.tenant_id
        and a.parish_code = dg.parish_code
)

select *
from enriched
