{{ config(
    unique_key='tenant_id || account_id || campaign_id || adset_id || ad_id || date',
    incremental_strategy='delete+insert',
) }}

{% set ad_insights_relation = source('meta_raw', 'ad_insights') %}
{% if execute %}
    {% set ad_insights_columns = adapter.get_columns_in_relation(ad_insights_relation) %}
    {% set ad_insights_column_names = ad_insights_columns | map(attribute='name') | map('lower') | list %}
{% else %}
    {% set ad_insights_column_names = [] %}
{% endif %}
{% set has_reach = 'reach' in ad_insights_column_names %}

with source as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        cast(account_id as text) as account_id,
        cast(campaign_id as text) as campaign_id,
        cast(adset_id as text) as adset_id,
        cast(ad_id as text) as ad_id,
        cast(date_start as date) as date,
        cast(country as text) as country,
        cast(region as text) as region,
        cast(city as text) as city,
        cast(impressions as numeric) as impressions,
        {% if has_reach %}
        cast(reach as numeric) as reach_metric,
        {% else %}
        cast(0 as numeric) as reach_metric,
        {% endif %}
        cast(clicks as numeric) as clicks,
        cast(spend as numeric) as spend,
        cast(cpc as numeric) as cpc,
        cast(cpm as numeric) as cpm,
        cast(ctr as numeric) as ctr,
        actions as raw_actions
    from {{ source('meta_raw', 'ad_insights') }}
    {% if is_incremental() %}
    where date_start >= (
        select coalesce(max(date), cast('1900-01-01' as date))
        from {{ this }}
    ) - interval '30 day'
    {% endif %}
),

flattened as (
    select
        src.tenant_id,
        src.account_id,
        src.campaign_id,
        src.adset_id,
        src.ad_id,
        src.date,
        src.country,
        src.region,
        src.city,
        src.impressions,
        src.reach_metric as reach,
        src.clicks,
        src.spend,
        src.cpc,
        src.cpm,
        src.ctr,
        {{ json_array_coalesce('src.raw_actions') }} as actions,
        coalesce(
            sum(
                case
                    when {{ json_get_text('action.action_json', "'action_type'") }} = 'offsite_conversion'
                        then cast(nullif({{ json_get_text('action.action_json', "'value'") }}, '') as numeric)
                    else 0
                end
            ),
            0
        ) as conversions,
        coalesce(
            sum(
                case
                    when {{ json_get_text('action.action_json', "'action_type'") }} in ('offsite_conversion', 'purchase')
                        then cast(nullif({{ json_get_text('action.action_json', "'value'") }}, '') as numeric)
                    else 0
                end
            ),
            0
        ) as conv_value
    from source as src
    left join lateral {{ json_array_elements_subquery(json_array_coalesce('src.raw_actions')) }} as action(action_json) on true
    group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,src.raw_actions
)

select * from flattened
