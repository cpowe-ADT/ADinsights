{{ config(materialized='view', enabled=var('enable_linkedin', False)) }}

with source as (
    select *
    from {{ source('raw', 'linkedin_transparency') }}
),

cleaned as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        cast(account_id as text) as ad_account_id,
        cast(campaign_id as text) as campaign_id,
        cast(ad_creative_id as text) as ad_id,
        date(activity_date) as date_day,
        coalesce(region, 'Unknown') as region_name,
        cast(spend as numeric) as spend,
        cast(impressions as numeric) as impressions,
        cast(clicks as numeric) as clicks,
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
