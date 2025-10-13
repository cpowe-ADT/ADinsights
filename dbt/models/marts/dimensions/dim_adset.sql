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
    ),

    new_snapshots as (
        select distinct
            source_platform,
            ad_account_id,
            adset_id,
            campaign_id,
            parish_code,
            parish_name,
            region_name,
            first_seen_date,
            effective_from,
            1 as snapshot_sort_key
        from adset_attributes
    )

    {% if is_incremental() %}
    , latest_existing as (
        select
            existing.source_platform,
            existing.ad_account_id,
            existing.adset_id,
            existing.campaign_id,
            existing.parish_code,
            existing.parish_name,
            existing.region_name,
            existing.first_seen_date,
            existing.valid_from as effective_from,
            0 as snapshot_sort_key
        from {{ this }} as existing
        inner join (
            select distinct source_platform, ad_account_id, adset_id
            from new_snapshots
        ) as changed_keys
            on existing.source_platform = changed_keys.source_platform
            and existing.ad_account_id = changed_keys.ad_account_id
            and existing.adset_id = changed_keys.adset_id
        where existing.is_current
    )

    select * from latest_existing
    union all
    select * from new_snapshots
    {% else %}
    select * from new_snapshots
    {% endif %}
{% endset %}

{{ scd2_dimension(
    source_query=adset_snapshots,
    natural_key=['source_platform', 'ad_account_id', 'adset_id'],
    tracked_columns=['campaign_id', 'parish_code', 'parish_name', 'region_name', 'first_seen_date'],
    order_by_columns=['snapshot_sort_key']
) }}
