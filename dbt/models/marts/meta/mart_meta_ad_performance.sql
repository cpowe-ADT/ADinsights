{{ config(materialized='view') }}

select
    tenant_id,
    ad_account_id,
    campaign_id,
    adset_id,
    ad_id,
    min(date) as first_seen_date,
    max(date) as last_seen_date,
    sum(impressions) as impressions,
    sum(reach) as reach,
    sum(clicks) as clicks,
    sum(spend) as spend,
    sum(conversions) as conversions,
    case when sum(clicks) > 0 then sum(spend) / sum(clicks) else 0 end as cpc,
    case when sum(impressions) > 0 then (sum(spend) * 1000.0) / sum(impressions) else 0 end as cpm
from {{ ref('mart_meta_daily_performance') }}
where ad_id is not null
group by 1,2,3,4,5
