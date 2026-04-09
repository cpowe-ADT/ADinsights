{% set enable_linkedin = var('enable_linkedin', False) %}
{% set enable_tiktok = var('enable_tiktok', False) %}

{% set meta_columns = adapter.get_columns_in_relation(ref('stg_meta_ads')) %}
{% set meta_column_names = meta_columns | map(attribute='name') | map('lower') | list %}
{% set meta_has_campaign_name = 'campaign_name' in meta_column_names %}
{% set meta_has_ad_name = 'ad_name' in meta_column_names %}

{% set google_columns = adapter.get_columns_in_relation(ref('stg_google_ads')) %}
{% set google_column_names = google_columns | map(attribute='name') | map('lower') | list %}
{% set google_has_campaign_name = 'campaign_name' in google_column_names %}
{% set google_has_ad_name = 'ad_name' in google_column_names %}

with meta_campaigns as (
    select
        tenant_id,
        campaign_id,
        account_id,
        coalesce(nullif(trim(effective_status), ''), nullif(trim(status), ''), 'Unknown') as status,
        coalesce(nullif(trim(objective), ''), 'Unknown') as objective
    from {{ ref('stg_meta_campaigns') }}
),

meta as (
    select
        m.tenant_id,
        'meta_ads' as source_platform,
        m.ad_account_id,
        m.campaign_id,
        {% if meta_has_campaign_name %}
        coalesce(nullif(m.campaign_name, ''), m.campaign_id) as campaign_name,
        {% else %}
        m.campaign_id as campaign_name,
        {% endif %}
        m.adset_id,
        m.ad_id,
        {% if meta_has_ad_name %}
        coalesce(nullif(m.ad_name, ''), m.ad_id) as ad_name,
        {% else %}
        m.ad_id as ad_name,
        {% endif %}
        m.date_day,
        m.region_name,
        m.parish_name,
        m.parish_code,
        m.spend,
        m.impressions,
        m.reach,
        m.clicks,
        m.conversions,
        coalesce(mc.status, 'Unknown') as status,
        coalesce(mc.objective, 'Unknown') as objective,
        m.effective_from
    from {{ ref('stg_meta_ads') }} m
    left join meta_campaigns mc
        on m.tenant_id = mc.tenant_id
        and m.campaign_id = mc.campaign_id
        and m.ad_account_id = mc.account_id
),

google as (
    select
        tenant_id,
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
        {% if google_has_ad_name %}
        coalesce(nullif(ad_name, ''), ad_id) as ad_name,
        {% else %}
        ad_id as ad_name,
        {% endif %}
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        cast(0 as numeric) as reach,
        clicks,
        conversions,
        'Unknown' as status,
        'Unknown' as objective,
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
        tenant_id,
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
        ad_id as ad_name,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        cast(0 as numeric) as reach,
        clicks,
        null as conversions,
        'Unknown' as status,
        'Unknown' as objective,
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
        tenant_id,
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
        ad_id as ad_name,
        date_day,
        region_name,
        parish_name,
        parish_code,
        spend,
        impressions,
        cast(0 as numeric) as reach,
        clicks,
        null as conversions,
        'Unknown' as status,
        'Unknown' as objective,
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
