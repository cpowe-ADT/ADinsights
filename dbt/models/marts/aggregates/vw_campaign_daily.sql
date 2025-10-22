{{ config(
    materialized='incremental',
    unique_key=['date_day', 'source_platform', 'ad_account_id', 'campaign_id'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

{% set lookback_days = 7 %}

with campaign_daily as (
    select
        date_day,
        source_platform,
        ad_account_id,
        campaign_id,
        max(campaign_name) as campaign_name,
        sum(spend) as spend,
        sum(impressions) as impressions,
        sum(clicks) as clicks,
        sum(conversions) as conversions
    from {{ ref('fct_ad_performance') }}
    where campaign_id is not null
    {% if is_incremental() %}
        and date_day >= (
            select coalesce(
                max(date_day) - interval '{{ lookback_days }} day',
                cast('1900-01-01' as date)
            )
            from {{ this }}
        )
    {% endif %}
    group by 1, 2, 3, 4
),

enriched as (
    select
        cd.date_day,
        cd.source_platform,
        cd.ad_account_id,
        cd.campaign_id,
        coalesce(d.campaign_name, cd.campaign_name, cd.campaign_id::text) as campaign_name,
        cd.spend,
        cd.impressions,
        cd.clicks,
        cd.conversions,
        {{ metric_ctr('cd.clicks', 'cd.impressions') }} as ctr,
        {{ metric_conversion_rate('cd.conversions', 'cd.clicks') }} as conversion_rate,
        {{ metric_cost_per_click('cd.spend', 'cd.clicks') }} as cost_per_click,
        {{ metric_cost_per_conversion('cd.spend', 'cd.conversions') }} as cost_per_conversion,
        {{ metric_cpm('cd.spend', 'cd.impressions') }} as cpm,
        {{ metric_return_on_ad_spend('cd.conversions', 'cd.spend') }} as roas,
        d.parish_code,
        d.parish_name,
        d.region_name,
        d.first_seen_date
    from campaign_daily cd
    left join {{ ref('dim_campaign') }} d
        on cd.source_platform = d.source_platform
        and cd.ad_account_id = d.ad_account_id
        and cd.campaign_id = d.campaign_id
        and cd.date_day between cast(d.valid_from as date) and cast(d.valid_to as date)
)

select *
from enriched
