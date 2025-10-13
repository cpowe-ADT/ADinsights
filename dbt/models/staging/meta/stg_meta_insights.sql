{{ config(
    unique_key='account_id || campaign_id || adset_id || ad_id || date',
    incremental_strategy='delete+insert',
) }}

{% set json_type = 'jsonb' if target.type in ['postgres', 'redshift'] else 'json' %}

with source as (
    select
        cast(account_id as text) as account_id,
        cast(campaign_id as text) as campaign_id,
        cast(adset_id as text) as adset_id,
        cast(ad_id as text) as ad_id,
        cast(date_start as date) as date,
        cast(country as text) as country,
        cast(region as text) as region,
        cast(city as text) as city,
        cast(impressions as numeric) as impressions,
        cast(clicks as numeric) as clicks,
        cast(spend as numeric) as spend,
        cast(cpc as numeric) as cpc,
        cast(cpm as numeric) as cpm,
        cast(ctr as numeric) as ctr,
        actions
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
        s.account_id,
        s.campaign_id,
        s.adset_id,
        s.ad_id,
        s.date,
        s.country,
        s.region,
        s.city,
        s.impressions,
        s.clicks,
        s.spend,
        s.cpc,
        s.cpm,
        s.ctr,
        coalesce(
            sum(cast({{ json_get_text('action.action_json', "'value'") }} as numeric))
            filter (
                where {{ json_get_text('action.action_json', "'action_type'") }} = 'offsite_conversion'
            ),
            0
        ) as conversions,
        coalesce(
            sum(cast({{ json_get_text('action.action_json', "'value'") }} as numeric))
            filter (
                where {{ json_get_text('action.action_json', "'action_type'") }} in ('offsite_conversion', 'purchase')
            ),
            0
        ) as conv_value
    from source as s
    left join lateral {{ json_array_elements_subquery(json_array_coalesce('s.actions')) }} as action(action_json) on true
    group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14
)

select * from flattened
