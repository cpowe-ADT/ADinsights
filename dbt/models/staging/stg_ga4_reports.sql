{{ config(materialized='view', enabled=var('enable_ga4', false)) }}

with source as (
    select *
    from {{ source('raw', 'ga4_reports') }}
),

cleaned as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        date(s.date_day) as date_day,
        cast(s.property_id as text) as property_id,
        coalesce(nullif(trim(s.session_default_channel_group), ''), 'Unknown') as channel_group,
        coalesce(nullif(trim(s.country), ''), 'Unknown') as country,
        coalesce(nullif(trim(s.city), ''), 'Unknown') as city,
        coalesce(nullif(trim(s.campaign_name), ''), 'Unassigned') as campaign_name,
        cast(s.sessions as numeric) as sessions,
        cast(s.engaged_sessions as numeric) as engaged_sessions,
        cast(s.conversions as numeric) as conversions,
        cast(s.purchase_revenue as numeric) as purchase_revenue,
        coalesce(nullif(trim(s.currency_code), ''), 'USD') as currency_code,
        cast(coalesce(s._airbyte_emitted_at, current_timestamp) as timestamp) as effective_from,
        s._airbyte_raw_id
    from source as s
)

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
    {{ metric_conversion_rate('engaged_sessions', 'sessions') }} as engagement_rate,
    {{ metric_conversion_rate('conversions', 'sessions') }} as conversion_rate,
    currency_code,
    effective_from,
    _airbyte_raw_id
from cleaned
