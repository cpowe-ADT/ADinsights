{% set adset_snapshots %}
    select
        source_platform,
        ad_account_id,
        coalesce(adset_id, campaign_id) as adset_id,
        coalesce(parish_code, 'UNK') as parish_code,
        coalesce(parish_name, region_name, 'Unknown') as geography_label,
        effective_from
    from {{ ref('all_ad_performance') }}
    where coalesce(adset_id, campaign_id) is not null
    group by 1,2,3,4,5,6
{% endset %}

{{ scd2_dimension(adset_snapshots, ['source_platform', 'ad_account_id', 'adset_id'], ['parish_code', 'geography_label']) }}
