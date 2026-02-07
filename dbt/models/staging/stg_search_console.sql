{{ config(materialized='view', enabled=var('enable_search_console', false)) }}

with source as (
    select *
    from {{ source('raw', 'search_console_performance') }}
),

cleaned as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        date(s.date_day) as date_day,
        coalesce(nullif(trim(s.site_url), ''), 'unknown') as site_url,
        coalesce(nullif(trim(s.country), ''), 'Unknown') as country,
        coalesce(nullif(trim(s.device), ''), 'Unknown') as device,
        coalesce(nullif(trim(s.query), ''), '(not set)') as query,
        coalesce(nullif(trim(s.page), ''), '(not set)') as page,
        cast(s.clicks as numeric) as clicks,
        cast(s.impressions as numeric) as impressions,
        cast(s.ctr as numeric) as ctr,
        cast(s.position as numeric) as position,
        cast(coalesce(s._airbyte_emitted_at, current_timestamp) as timestamp) as effective_from,
        s._airbyte_raw_id
    from source as s
)

select
    tenant_id,
    date_day,
    site_url,
    country,
    device,
    query,
    page,
    clicks,
    impressions,
    coalesce(ctr, {{ metric_ctr('clicks', 'impressions') }}) as ctr,
    position,
    effective_from,
    _airbyte_raw_id
from cleaned
