{{ config(
    unique_key="date_day || '|' || source_platform || '|' || ad_account_id || '|' || campaign_id || '|' || coalesce(adset_id, 'NO_ADSET') || '|' || coalesce(ad_id, 'NO_AD')",
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
) }}

with base as (
    select
        date_day,
        source_platform,
        ad_account_id,
        campaign_id,
        campaign_name,
        adset_id,
        ad_id,
        parish_code,
        parish_name,
        spend,
        impressions,
        clicks,
        conversions,
        effective_from
    from {{ ref('all_ad_performance') }}
    {% if is_incremental() %}
    where date_day >= (select coalesce(max(date_day), '1900-01-01') from {{ this }})
    {% endif %}
),

enriched as (
    select
        b.*, 
        {{ metric_ctr('b.clicks', 'b.impressions') }} as ctr,
        {{ metric_conversion_rate('b.conversions', 'b.clicks') }} as conversion_rate,
        {{ metric_cost_per_conversion('b.spend', 'b.conversions') }} as cost_per_conversion,
        {{ metric_return_on_ad_spend('b.conversions', 'b.spend') }} as roas
    from base b
)

select * from enriched
