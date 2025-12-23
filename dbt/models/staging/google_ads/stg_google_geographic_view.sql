{{ config(unique_key='tenant_id || customer_id || date || geo_target_id', incremental_strategy='delete+insert') }}

select
    {{ tenant_id_expr() }} as tenant_id,
    customer_id::text as customer_id,
    segments_date::date as date,
    geo_target_id::text as geo_target_id,
    geo_target_country::text as country,
    geo_target_state::text as region,
    geo_target_city_name::text as city,
    metrics_impressions::numeric as impressions,
    metrics_clicks::numeric as clicks,
    metrics_cost_micros::numeric / 1000000 as spend
from {{ source('google_ads_raw', 'geographic_view') }}
