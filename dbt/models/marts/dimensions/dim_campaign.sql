{{ config(
    materialized='incremental',
    unique_key=['source_platform', 'ad_account_id', 'campaign_id', 'valid_from'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

{% set campaign_snapshots %}
    with campaign_metadata as (
        select distinct
            'meta_ads' as source_platform,
            account_id as ad_account_id,
            campaign_id,
            name as campaign_name
        from {{ ref('stg_meta_campaigns') }}

        union all

        select distinct
            'google_ads' as source_platform,
            customer_id as ad_account_id,
            campaign_id,
            null as campaign_name
        from {{ ref('stg_google_campaign_daily') }}
    ),

    campaign_attributes as (
        select
            a.source_platform,
            a.ad_account_id,
            a.campaign_id,
            coalesce(cm.campaign_name, a.campaign_id::text) as campaign_name,
            coalesce(a.parish_code, 'UNK') as parish_code,
            coalesce(a.parish_name, a.region_name, 'Unknown') as parish_name,
            coalesce(a.region_name, 'Unknown') as region_name,
            min(a.date_day) over (
                partition by a.source_platform, a.ad_account_id, a.campaign_id
            ) as first_seen_date,
            a.effective_from
        from {{ ref('all_ad_performance') }} a
        left join campaign_metadata cm
            on a.source_platform = cm.source_platform
            and a.ad_account_id = cm.ad_account_id
            and a.campaign_id = cm.campaign_id
        where a.campaign_id is not null
        {% if is_incremental() %}
            and a.effective_from >= (
                select coalesce(max(valid_from), '1900-01-01'::timestamp) from {{ this }}
            )
        {% endif %}
    )

    select distinct
        source_platform,
        ad_account_id,
        campaign_id,
        campaign_name,
        parish_code,
        parish_name,
        region_name,
        first_seen_date,
        effective_from
    from campaign_attributes
{% endset %}

{{ scd2_dimension(
    source_query=campaign_snapshots,
    natural_key=['source_platform', 'ad_account_id', 'campaign_id'],
    tracked_columns=['campaign_name', 'parish_code', 'parish_name', 'region_name', 'first_seen_date']
) }}
