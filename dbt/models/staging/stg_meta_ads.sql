{{ config(materialized='view') }}

with source as (
    select *
    from {{ source('raw', 'meta_ads_insights') }}
),

cleaned as (
    select
        cast(ad_account_id as text) as ad_account_id,
        cast(campaign_id as text) as campaign_id,
        cast(adset_id as text) as adset_id,
        cast(ad_id as text) as ad_id,
        date(date_start) as date_day,
        coalesce(region, 'Unknown') as region_name,
        cast(spend as numeric) as spend,
        cast(impressions as numeric) as impressions,
        cast(clicks as numeric) as clicks,
        cast(conversions as numeric) as conversions,
        cast(coalesce(updated_time, _airbyte_emitted_at) as timestamp) as effective_from,
        _airbyte_raw_id
    from source
),

final as (
    select
        c.*,
        g.parish_name,
        g.parish_code,
        g.latitude,
        g.longitude
    from cleaned c
    left join {{ ref('geo_parish_lookup') }} g
        on lower(c.region_name) = lower(g.region_name)
)

select * from final
