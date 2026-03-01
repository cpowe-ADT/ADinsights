{{ config(materialized='table') }}

with source as (
    select
        tenant_id,
        date,
        account_id as ad_account_id,
        campaign_id,
        adset_id,
        ad_id,
        coalesce(impressions, 0) as impressions,
        coalesce(reach, 0) as reach,
        coalesce(clicks, 0) as clicks,
        coalesce(spend, 0) as spend,
        coalesce(cpc, 0) as cpc,
        coalesce(cpm, 0) as cpm,
        coalesce(conversions, 0) as conversions
    from {{ ref('stg_meta_insights') }}
)

select
    tenant_id,
    date,
    ad_account_id,
    campaign_id,
    adset_id,
    ad_id,
    sum(impressions) as impressions,
    sum(reach) as reach,
    sum(clicks) as clicks,
    sum(spend) as spend,
    sum(conversions) as conversions,
    case when sum(clicks) > 0 then sum(spend) / sum(clicks) else 0 end as blended_cpc,
    case when sum(impressions) > 0 then (sum(spend) * 1000.0) / sum(impressions) else 0 end as blended_cpm
from source
group by 1,2,3,4,5,6
