{{ config(materialized='view', enabled=var('enable_tiktok', False)) }}

-- Canonical TikTok Ads daily performance (connector output) normalized to the
-- shared fact grain. Separate from stg_tiktok_transparency by design (DD-1
-- Option A): only this performance model feeds the combined fact.

with source as (
    select *
    from {{ source('raw', 'tiktok_ads_performance') }}
),

cleaned as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        cast(account_id as text) as ad_account_id,
        cast(campaign_id as text) as campaign_id,
        cast(ad_group_id as text) as adset_id,
        cast(ad_id as text) as ad_id,
        date(date) as date_day,
        coalesce(region, 'Unknown') as region_name,
        cast(spend as numeric) as spend,
        cast(impressions as numeric) as impressions,
        cast(clicks as numeric) as clicks,
        cast(conversions as numeric) as conversions,
        cast(coalesce(_airbyte_emitted_at, current_timestamp) as timestamp) as effective_from
    from source
),

-- A region (e.g. "Corporate Area") can map to multiple parishes in the lookup.
-- Collapse to one parish per region so the geo join never fans out the grain.
geo as (
    select region_name, parish_name, parish_code, latitude, longitude
    from (
        select
            *,
            row_number() over (partition by lower(region_name) order by parish_code) as _rn
        from {{ ref('geo_parish_lookup') }}
    )
    where _rn = 1
)

select
    c.*,
    g.parish_name,
    g.parish_code,
    g.latitude,
    g.longitude
from cleaned c
left join geo g
    on lower(c.region_name) = lower(g.region_name)
