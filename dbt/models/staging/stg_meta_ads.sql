{{ config(materialized='view') }}

{% set meta_ads_relation = source('raw', 'meta_ads_insights') %}
{% if execute %}
    {% set meta_ads_columns = adapter.get_columns_in_relation(meta_ads_relation) %}
    {% set meta_ads_column_names = meta_ads_columns | map(attribute='name') | map('lower') | list %}
{% else %}
    {% set meta_ads_column_names = [] %}
{% endif %}
{% set has_reach = 'reach' in meta_ads_column_names %}
{% set has_tenant_id = 'tenant_id' in meta_ads_column_names %}

with source as (
    select *
    from {{ source('raw', 'meta_ads_insights') }}
),

cleaned as (
    select
        {% if has_tenant_id %}
        {{ tenant_id_expr('cast(s.tenant_id as text)') }} as tenant_id,
        {% else %}
        {{ tenant_id_expr() }} as tenant_id,
        {% endif %}
        cast(s.ad_account_id as text) as ad_account_id,
        cast(s.campaign_id as text) as campaign_id,
        coalesce(nullif(trim(s.campaign_name), ''), cast(s.campaign_id as text)) as campaign_name,
        cast(s.adset_id as text) as adset_id,
        cast(s.ad_id as text) as ad_id,
        coalesce(nullif(trim(s.ad_name), ''), cast(s.ad_id as text)) as ad_name,
        date(s.date_start) as date_day,
        coalesce(s.region, 'Unknown') as region_name,
        cast(s.spend as numeric) as spend,
        cast(s.impressions as numeric) as impressions,
        {% if has_reach %}
        cast(coalesce(s.reach, 0) as numeric) as reach,
        {% else %}
        cast(0 as numeric) as reach,
        {% endif %}
        cast(s.clicks as numeric) as clicks,
        cast(s.conversions as numeric) as conversions,
        cast(coalesce(s.updated_time, s._airbyte_emitted_at) as timestamp) as effective_from,
        s._airbyte_raw_id
    from source as s
),

final as (
    select
        c.*,
        g.parish_name,
        g.parish_code,
        g.latitude,
        g.longitude
    from cleaned c
    left join {{ ref('geo_parish_lookup') }} g
        on lower(c.region_name) = lower(g.region_name)
)

select * from final
