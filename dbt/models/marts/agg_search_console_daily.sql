{% set using_duckdb = target.type == 'duckdb' %}
{{ config(
    materialized='table' if using_duckdb else 'incremental',
    enabled=var('enable_search_console', false),
    unique_key=['tenant_id', 'date_day', 'site_url', 'country', 'device', 'query', 'page'],
    incremental_strategy='merge' if not using_duckdb else none,
    on_schema_change='sync_all_columns'
) }}

with base as (
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
        ctr,
        position
    from {{ ref('stg_search_console') }}
    {% if is_incremental() %}
      where date_day >= (select coalesce(max(date_day), '1900-01-01') from {{ this }})
    {% endif %}
)

select
    tenant_id,
    date_day,
    site_url,
    country,
    device,
    query,
    page,
    sum(clicks) as clicks,
    sum(impressions) as impressions,
    {{ metric_ctr('sum(clicks)', 'sum(impressions)') }} as ctr,
    avg(position) as position
from base
group by 1, 2, 3, 4, 5, 6, 7
