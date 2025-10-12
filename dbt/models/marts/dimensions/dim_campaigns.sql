{% set campaign_snapshots %}
    select
        source_platform,
        ad_account_id,
        campaign_id,
        coalesce(parish_code, 'UNK') as parish_code,
        coalesce(parish_name, region_name, 'Unknown') as geography_label,
        min(date_day) as first_seen_date,
        effective_from
    from {{ ref('all_ad_performance') }}
    group by 1,2,3,4,5,7
{% endset %}

{{ scd2_dimension(campaign_snapshots, ['source_platform', 'ad_account_id', 'campaign_id'], ['parish_code', 'geography_label', 'first_seen_date']) }}
