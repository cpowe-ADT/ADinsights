{% set using_duckdb = target.type == 'duckdb' %}
{{ config(
    materialized='table' if using_duckdb else 'incremental',
    enabled=var('enable_ga4', false),
    unique_key=['tenant_id', 'date_day', 'property_id', 'channel_group', 'country', 'city', 'campaign_name'],
    incremental_strategy='merge' if not using_duckdb else none,
    on_schema_change='sync_all_columns'
) }}

with base as (
    select
        tenant_id,
        date_day,
        property_id,
        channel_group,
        country,
        city,
        campaign_name,
        sessions,
        engaged_sessions,
        conversions,
        purchase_revenue,
        engagement_rate,
        conversion_rate,
        currency_code
    from {{ ref('stg_ga4_reports') }}
    {% if is_incremental() %}
      where date_day >= (select coalesce(max(date_day), '1900-01-01') from {{ this }})
    {% endif %}
)

select
    tenant_id,
    date_day,
    property_id,
    channel_group,
    country,
    city,
    campaign_name,
    sum(sessions) as sessions,
    sum(engaged_sessions) as engaged_sessions,
    sum(conversions) as conversions,
    sum(purchase_revenue) as purchase_revenue,
    {{ metric_conversion_rate('sum(engaged_sessions)', 'sum(sessions)') }} as engagement_rate,
    {{ metric_conversion_rate('sum(conversions)', 'sum(sessions)') }} as conversion_rate,
    max(currency_code) as currency_code
from base
group by 1, 2, 3, 4, 5, 6, 7
