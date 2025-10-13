{% set enable_linkedin = var('enable_linkedin', False) %}
{% set enable_tiktok = var('enable_tiktok', False) %}

{% set meta_columns = adapter.get_columns_in_relation(ref('stg_meta_ads')) %}
{% set meta_column_names = meta_columns | map(attribute='name') | map('lower') | list %}
{% set meta_has_campaign_name = 'campaign_name' in meta_column_names %}

{% set google_columns = adapter.get_columns_in_relation(ref('stg_google_ads')) %}
{% set google_column_names = google_columns | map(attribute='name') | map('lower') | list %}
{% set google_has_campaign_name = 'campaign_name' in google_column_names %}

with meta as (
    select
        'meta_ads' as source_platform,
        ad_account_id,
        campaign_id,
        {% if meta_has_campaign_name %}
        coalesce(nullif(campaign_name, ''), campaign_id) as campaign_name,
        {% else %}
        campaign_id as campaign_name,
        {% endif %}
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
        {% if google_has_campaign_name %}
        coalesce(nullif(campaign_name, ''), campaign_id) as campaign_name,
        {% else %}
        campaign_id as campaign_name,
        {% endif %}
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
{% if enable_linkedin %}
{% set linkedin_columns = adapter.get_columns_in_relation(ref('stg_linkedin_transparency')) %}
{% set linkedin_column_names = linkedin_columns | map(attribute='name') | map('lower') | list %}
{% set linkedin_has_campaign_name = 'campaign_name' in linkedin_column_names %}
,
linkedin as (
    select
        'linkedin' as source_platform,
        ad_account_id,
        campaign_id,
        {% if linkedin_has_campaign_name %}
        coalesce(nullif(campaign_name, ''), campaign_id) as campaign_name,
        {% else %}
        campaign_id as campaign_name,
        {% endif %}
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
{% if enable_tiktok %}
{% set tiktok_columns = adapter.get_columns_in_relation(ref('stg_tiktok_transparency')) %}
{% set tiktok_column_names = tiktok_columns | map(attribute='name') | map('lower') | list %}
{% set tiktok_has_campaign_name = 'campaign_name' in tiktok_column_names %}
,
tiktok as (
    select
        'tiktok' as source_platform,
        ad_account_id,
        campaign_id,
        {% if tiktok_has_campaign_name %}
        coalesce(nullif(campaign_name, ''), campaign_id) as campaign_name,
        {% else %}
        campaign_id as campaign_name,
        {% endif %}
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
