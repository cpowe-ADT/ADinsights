{% set using_duckdb = target.type == 'duckdb' %}
{% set fact_incremental_strategy = 'merge' if not using_duckdb else none %}
{{ config(
    materialized='table' if using_duckdb else 'incremental',
    unique_key=[
        'tenant_id',
        'date_day',
        'source_platform',
        'ad_account_id',
        'campaign_id',
        'adset_id_key',
        'ad_id_key'
    ],
    incremental_strategy=fact_incremental_strategy,
    on_schema_change='sync_all_columns'
) }}

with base as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        date_day,
        source_platform,
        ad_account_id,
        campaign_id,
        campaign_name,
        adset_id,
        ad_id,
        ad_name,
        coalesce(adset_id, 'NO_ADSET') as adset_id_key,
        coalesce(ad_id, 'NO_AD') as ad_id_key,
        coalesce(parish_code, 'UNK') as parish_code,
        coalesce(parish_name, region_name, 'Unknown') as parish_name,
        coalesce(region_name, 'Unknown') as region_name,
        spend,
        impressions,
        clicks,
        conversions,
        effective_from
    from {{ ref('all_ad_performance') }}
    {% if is_incremental() %}
    where {{ tenant_id_expr('tenant_id') }} = {{ tenant_id_expr() }}
      and date_day >= (
        select coalesce(max(date_day), '1900-01-01'::date)
        from {{ this }}
        where tenant_id = {{ tenant_id_expr() }}
    )
    {% endif %}
), normalized as (
    select
        b.*,
        {{ attribution_window_days_expr('b.source_platform') }} as attribution_window_days,
        {{ normalize_attribution_metric('b.conversions', 'b.source_platform') }} as conversions_aligned
    from base b
)

select
    n.tenant_id,
    n.date_day,
    n.source_platform,
    n.ad_account_id,
    n.campaign_id,
    n.campaign_name,
    n.adset_id,
    n.ad_id,
    n.ad_name,
    n.adset_id_key,
    n.ad_id_key,
    n.parish_code,
    n.parish_name,
    n.region_name,
    n.spend,
    n.impressions,
    n.clicks,
    n.conversions as reported_conversions,
    n.conversions_aligned as conversions,
    {{ metric_ctr('n.clicks', 'n.impressions') }} as ctr,
    {{ metric_conversion_rate('n.conversions_aligned', 'n.clicks') }} as conversion_rate,
    {{ metric_cost_per_click('n.spend', 'n.clicks') }} as cost_per_click,
    {{ metric_cost_per_conversion('n.spend', 'n.conversions_aligned') }} as cost_per_conversion,
    {{ metric_cpm('n.spend', 'n.impressions') }} as cpm,
    {{ metric_return_on_ad_spend('n.conversions_aligned', 'n.spend') }} as roas,
    n.attribution_window_days,
    n.effective_from
from normalized n
