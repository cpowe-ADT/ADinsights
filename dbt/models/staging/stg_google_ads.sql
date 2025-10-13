{{ config(materialized='view') }}

with source as (
    select *
    from {{ source('raw', 'google_ads_insights') }}
),

cleaned as (
    select
        cast(s.customer_id as text) as ad_account_id,
        cast(s.campaign_id as text) as campaign_id,
        coalesce(nullif(trim(s.campaign_name), ''), cast(s.campaign_id as text)) as campaign_name,
        cast(s.ad_group_id as text) as adset_id,
        cast(s.criterion_id as text) as ad_id,
        coalesce(nullif(trim(s.ad_name), ''), cast(s.criterion_id as text)) as ad_name,
        date(s.date_day) as date_day,
        coalesce(s.geo_target_region, 'Unknown') as region_name,
        s.cost_micros / 1000000.0 as spend,
        cast(s.impressions as numeric) as impressions,
        cast(s.clicks as numeric) as clicks,
        cast(s.conversions as numeric) as conversions,
        cast(coalesce(s._airbyte_emitted_at, current_timestamp) as timestamp) as effective_from
    from source as s
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
