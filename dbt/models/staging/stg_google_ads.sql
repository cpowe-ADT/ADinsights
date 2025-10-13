{{ config(materialized='view') }}

with source as (
    select *
    from {{ source('raw', 'google_ads_insights') }}
),

cleaned as (
    select
        cast(customer_id as text) as ad_account_id,
        cast(campaign_id as text) as campaign_id,
        coalesce(nullif(trim(campaign_name), ''), cast(campaign_id as text)) as campaign_name,
        cast(ad_group_id as text) as adset_id,
        cast(criterion_id as text) as ad_id,
        coalesce(nullif(trim(ad_name), ''), cast(criterion_id as text)) as ad_name,
        date(date_day) as date_day,
        coalesce(geo_target_region, 'Unknown') as region_name,
        cost_micros / 1000000.0 as spend,
        cast(impressions as numeric) as impressions,
        cast(clicks as numeric) as clicks,
        cast(conversions as numeric) as conversions,
        cast(coalesce(_airbyte_emitted_at, current_timestamp) as timestamp) as effective_from
    from source
)

select
    c.*,
    g.parish_name,
    g.parish_code,
    g.latitude,
    g.longitude
from cleaned c
left join {{ ref('geo_parish_lookup') }} g
    on lower(c.region_name) = lower(g.region_name)
