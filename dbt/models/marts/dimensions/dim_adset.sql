{{ config(
    materialized='incremental',
    unique_key=['source_platform', 'ad_account_id', 'adset_id', 'valid_from'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

{% set adset_snapshots %}
    with adset_attributes as (
        select
            source_platform,
            ad_account_id,
            adset_id,
            campaign_id,
            coalesce(parish_code, 'UNK') as parish_code,
            coalesce(parish_name, region_name, 'Unknown') as parish_name,
            coalesce(region_name, 'Unknown') as region_name,
            min(date_day) over (
                partition by source_platform, ad_account_id, adset_id
            ) as first_seen_date,
            effective_from
        from {{ ref('all_ad_performance') }}
        where adset_id is not null
        {% if is_incremental() %}
            and effective_from >= (
                select coalesce(max(valid_from), '1900-01-01'::timestamp) from {{ this }}
            )
        {% endif %}
    )

    select distinct
        source_platform,
        ad_account_id,
        adset_id,
        campaign_id,
        parish_code,
        parish_name,
        region_name,
        first_seen_date,
        effective_from
    from adset_attributes
{% endset %}

{{ scd2_dimension(
    source_query=adset_snapshots,
    natural_key=['source_platform', 'ad_account_id', 'adset_id'],
    tracked_columns=['campaign_id', 'parish_code', 'parish_name', 'region_name', 'first_seen_date']
) }}
