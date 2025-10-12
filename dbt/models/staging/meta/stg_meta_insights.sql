{{ config(
    unique_key='account_id || campaign_id || adset_id || ad_id || date',
    incremental_strategy='delete+insert',
) }}

with source as (
    select
        account_id::text as account_id,
        campaign_id::text as campaign_id,
        adset_id::text as adset_id,
        ad_id::text as ad_id,
        date_start::date as date,
        country::text as country,
        region::text as region,
        city::text as city,
        impressions::numeric as impressions,
        clicks::numeric as clicks,
        spend::numeric as spend,
        cpc::numeric as cpc,
        cpm::numeric as cpm,
        ctr::numeric as ctr,
        actions
    from {{ source('meta_raw', 'ad_insights') }}
    {% if is_incremental() %}
    where date_start >= (select coalesce(max(date), '1900-01-01'::date) from {{ this }}) - interval '30 day'
    {% endif %}
),

flattened as (
    select
        account_id,
        campaign_id,
        adset_id,
        ad_id,
        date,
        country,
        region,
        city,
        impressions,
        clicks,
        spend,
        cpc,
        cpm,
        ctr,
        coalesce(sum((action ->> 'value')::numeric) filter (where action ->> 'action_type' = 'offsite_conversion'), 0) as conversions,
        coalesce(sum((action ->> 'value')::numeric) filter (where action ->> 'action_type' in ('offsite_conversion', 'purchase')), 0) as conv_value
    from source
    left join lateral jsonb_array_elements(coalesce(actions::jsonb, '[]'::jsonb)) as action on true
    group by 1,2,3,4,5,6,7,8,9,10,11,12,13
)

select * from flattened
