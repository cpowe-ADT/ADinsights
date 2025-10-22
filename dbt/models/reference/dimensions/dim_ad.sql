{{ config(materialized='table') }}

{% set ad_source %}
    select
        {{ tenant_id_expr() }} as tenant_id,
        source_platform,
        ad_account_id,
        ad_id,
        adset_id,
        campaign_id,
        coalesce(ad_name, ad_id::text) as ad_name,
        coalesce(parish_code, 'UNK') as parish_code,
        coalesce(parish_name, region_name, 'Unknown') as parish_name,
        coalesce(region_name, 'Unknown') as region_name,
        effective_from
    from {{ ref('all_ad_performance') }}
    where ad_id is not null
{% endset %}

with scd2 as (
    {{ scd2_dimension(
        source_query=ad_source,
        natural_key=['tenant_id', 'source_platform', 'ad_account_id', 'ad_id'],
        tracked_columns=['adset_id', 'campaign_id', 'ad_name', 'parish_code', 'parish_name', 'region_name'],
        valid_from_column='dbt_valid_from',
        valid_to_column='dbt_valid_to',
        is_current_column='is_current'
    ) }}
), final as (
    select
        s.*, 
        min(s.dbt_valid_from) over (
            partition by tenant_id, source_platform, ad_account_id, ad_id
        ) as first_seen_at
    from scd2 s
)

select * from final
