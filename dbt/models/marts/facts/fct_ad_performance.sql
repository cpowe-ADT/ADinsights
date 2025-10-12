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
        case when impressions > 0 then clicks / impressions::numeric else 0 end as ctr,
        case when clicks > 0 then conversions / clicks::numeric else 0 end as conversion_rate,
        case when conversions > 0 then spend / conversions::numeric else null end as cost_per_conversion
    from base b
)

select * from enriched
