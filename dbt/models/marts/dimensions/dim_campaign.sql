{{ config(
    materialized='incremental',
    unique_key=['source_platform', 'ad_account_id', 'campaign_id', 'valid_from'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

{% set campaign_snapshots %}
    with campaign_attributes as (
        select
            source_platform,
            ad_account_id,
            campaign_id,
            coalesce(parish_code, 'UNK') as parish_code,
            coalesce(parish_name, region_name, 'Unknown') as parish_name,
            coalesce(region_name, 'Unknown') as region_name,
            min(date_day) over (
                partition by source_platform, ad_account_id, campaign_id
            ) as first_seen_date,
            effective_from
        from {{ ref('all_ad_performance') }}
        where campaign_id is not null
        {% if is_incremental() %}
            and effective_from >= (
                select coalesce(max(valid_from), '1900-01-01'::timestamp) from {{ this }}
            )
        {% endif %}
    )

    select distinct
        source_platform,
        ad_account_id,
        campaign_id,
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
    tracked_columns=['parish_code', 'parish_name', 'region_name', 'first_seen_date']
) }}
