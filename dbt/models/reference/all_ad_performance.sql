{% set enable_linkedin = var('enable_linkedin', False) %}
{% set enable_tiktok = var('enable_tiktok', False) %}

with meta as (
    select
        'meta_ads' as source_platform,
        ad_account_id,
        campaign_id,
        adset_id,
        ad_id,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        clicks,
        conversions,
        effective_from
    from {{ ref('stg_meta_ads') }}
),

google as (
    select
        'google_ads' as source_platform,
        ad_account_id,
        campaign_id,
        adset_id,
        ad_id,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        clicks,
        conversions,
        effective_from
    from {{ ref('stg_google_ads') }}
)
{% if enable_linkedin %},
linkedin as (
    select
        'linkedin' as source_platform,
        ad_account_id,
        campaign_id,
        null as adset_id,
        ad_id,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        clicks,
        null as conversions,
        effective_from
    from {{ ref('stg_linkedin_transparency') }}
)
{% endif %}
{% if enable_tiktok %},
tiktok as (
    select
        'tiktok' as source_platform,
        ad_account_id,
        campaign_id,
        adset_id,
        ad_id,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        clicks,
        null as conversions,
        effective_from
    from {{ ref('stg_tiktok_transparency') }}
)
{% endif %}

select * from meta
union all
select * from google
{% if enable_linkedin %}
union all
select * from linkedin
{% endif %}
{% if enable_tiktok %}
union all
select * from tiktok
{% endif %}
