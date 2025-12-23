{{ config(
    unique_key='tenant_id || customer_id || campaign_id || ad_group_id || ad_id || date',
    incremental_strategy='delete+insert',
) }}

with source as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        customer_id::text as customer_id,
        campaign_id::text as campaign_id,
        ad_group_id::text as ad_group_id,
        ad_id::text as ad_id,
        segments_date::date as date,
        metrics_impressions::numeric as impressions,
        metrics_clicks::numeric as clicks,
        metrics_conversions::numeric as conversions,
        metrics_conversions_value::numeric as conversion_value,
        metrics_cost_micros::numeric / 1000000 as spend,
        metrics_average_cpc::numeric as average_cpc,
        metrics_average_cpm::numeric as average_cpm
    from {{ source('google_ads_raw', 'campaign_daily') }}
    {% if is_incremental() %}
    where segments_date >= (select coalesce(max(date), '1900-01-01'::date) from {{ this }}) - interval '30 day'
    {% endif %}
)

select
    *,
    {{ safe_divide('clicks', 'impressions') }} as ctr,
    {{ safe_divide('spend', 'clicks') }} as cpc,
    {{ safe_divide('spend', 'impressions') }} * 1000 as cpm
from source
