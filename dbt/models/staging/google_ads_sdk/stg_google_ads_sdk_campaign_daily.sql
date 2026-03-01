{{ config(materialized='view', enabled=var('google_ads_ingestion_engine', 'airbyte') == 'sdk') }}

with source as (
    select *
    from {{ source('google_ads_sdk_raw', 'campaign_daily') }}
)

select
    {{ tenant_id_expr() }} as tenant_id,
    cast(customer_id as text) as ad_account_id,
    cast(campaign_id as text) as campaign_id,
    coalesce(nullif(trim(campaign_name), ''), cast(campaign_id as text)) as campaign_name,
    coalesce(nullif(trim(advertising_channel_type), ''), 'UNKNOWN') as channel_type,
    coalesce(nullif(trim(campaign_status), ''), 'UNKNOWN') as campaign_status,
    date(date_day) as date_day,
    cast(cost_micros as numeric) / 1000000.0 as spend,
    cast(impressions as numeric) as impressions,
    cast(clicks as numeric) as clicks,
    cast(conversions as numeric) as conversions,
    cast(conversions_value as numeric) as conversions_value,
    cast(coalesce(updated_at, ingested_at, current_timestamp) as timestamp) as effective_from
from source
