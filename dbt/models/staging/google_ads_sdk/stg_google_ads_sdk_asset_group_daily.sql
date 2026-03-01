{{ config(materialized='view', enabled=var('google_ads_ingestion_engine', 'airbyte') == 'sdk') }}

with source as (
    select *
    from {{ source('google_ads_sdk_raw', 'asset_group_daily') }}
)

select
    {{ tenant_id_expr() }} as tenant_id,
    cast(customer_id as text) as ad_account_id,
    cast(campaign_id as text) as campaign_id,
    cast(asset_group_id as text) as asset_group_id,
    asset_group_name,
    asset_group_status,
    date(date_day) as date_day,
    cast(cost_micros as numeric) / 1000000.0 as spend,
    cast(impressions as numeric) as impressions,
    cast(clicks as numeric) as clicks,
    cast(conversions as numeric) as conversions,
    cast(conversions_value as numeric) as conversions_value,
    cast(coalesce(updated_at, ingested_at, current_timestamp) as timestamp) as effective_from
from source
