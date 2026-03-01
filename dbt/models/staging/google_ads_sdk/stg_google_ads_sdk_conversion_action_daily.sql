{{ config(materialized='view', enabled=var('google_ads_ingestion_engine', 'airbyte') == 'sdk') }}

with source as (
    select *
    from {{ source('google_ads_sdk_raw', 'conversion_action_daily') }}
)

select
    {{ tenant_id_expr() }} as tenant_id,
    cast(customer_id as text) as ad_account_id,
    cast(conversion_action_id as text) as conversion_action_id,
    conversion_action_name,
    conversion_action_type,
    date(date_day) as date_day,
    cast(conversions as numeric) as conversions,
    cast(all_conversions as numeric) as all_conversions,
    cast(conversions_value as numeric) as conversions_value,
    cast(coalesce(updated_at, ingested_at, current_timestamp) as timestamp) as effective_from
from source
