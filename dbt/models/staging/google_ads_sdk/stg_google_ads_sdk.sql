{{ config(materialized='view', enabled=var('google_ads_ingestion_engine', 'airbyte') == 'sdk') }}

with source as (
    select *
    from {{ source('google_ads_sdk_raw', 'ad_group_ad_daily') }}
),

cleaned as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        cast(s.customer_id as text) as ad_account_id,
        cast(s.campaign_id as text) as campaign_id,
        coalesce(nullif(trim(s.campaign_name), ''), cast(s.campaign_id as text)) as campaign_name,
        cast(s.ad_group_id as text) as adset_id,
        cast(s.ad_id as text) as ad_id,
        coalesce(nullif(trim(s.ad_name), ''), cast(s.ad_id as text)) as ad_name,
        date(s.date_day) as date_day,
        'Unknown' as region_name,
        cast(s.cost_micros as numeric) / 1000000.0 as spend,
        cast(s.impressions as numeric) as impressions,
        cast(s.clicks as numeric) as clicks,
        cast(s.conversions as numeric) as conversions,
        cast(coalesce(s.updated_at, s.ingested_at, current_timestamp) as timestamp) as effective_from
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
