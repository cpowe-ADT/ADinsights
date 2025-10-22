{{ config(materialized='table') }}

{% set campaign_source %}
    select
        {{ tenant_id_expr() }} as tenant_id,
        source_platform,
        ad_account_id,
        campaign_id,
        coalesce(campaign_name, campaign_id::text) as campaign_name,
        coalesce(parish_code, 'UNK') as parish_code,
        coalesce(parish_name, region_name, 'Unknown') as parish_name,
        coalesce(region_name, 'Unknown') as region_name,
        effective_from
    from {{ ref('all_ad_performance') }}
    where campaign_id is not null
{% endset %}

with scd2 as (
    {{ scd2_dimension(
        source_query=campaign_source,
        natural_key=['tenant_id', 'source_platform', 'ad_account_id', 'campaign_id'],
        tracked_columns=['campaign_name', 'parish_code', 'parish_name', 'region_name'],
        valid_from_column='dbt_valid_from',
        valid_to_column='dbt_valid_to',
        is_current_column='is_current'
    ) }}
), final as (
    select
        s.*, 
        min(s.dbt_valid_from) over (
            partition by tenant_id, source_platform, ad_account_id, campaign_id
        ) as first_seen_at
    from scd2 s
)

select * from final
