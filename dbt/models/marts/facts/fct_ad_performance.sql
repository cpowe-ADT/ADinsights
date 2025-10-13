{{ config(
    unique_key=['date_day', 'source_platform', 'campaign_id', 'ad_account_id'],
    incremental_strategy='merge'
) }}

with base as (
    select
        date_day,
        source_platform,
        ad_account_id,
        campaign_id,
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
        {{ metric_cost_per_conversion('b.spend', 'b.conversions') }} as cost_per_conversion
    from base b
)

select * from enriched
