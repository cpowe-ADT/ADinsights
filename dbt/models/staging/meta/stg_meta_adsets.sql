{{ config(unique_key=['tenant_id', 'adset_id'], incremental_strategy='delete+insert') }}

{% set backend_raw_schema = env_var('BACKEND_RAW_SCHEMA', 'public') %}

{% if execute %}
    {% set campaign_exists_sql %}
        select 1
        from information_schema.tables
        where table_schema = '{{ backend_raw_schema }}'
          and table_name = 'analytics_campaign'
        limit 1
    {% endset %}
    {% set account_exists_sql %}
        select 1
        from information_schema.tables
        where table_schema = '{{ backend_raw_schema }}'
          and table_name = 'analytics_adaccount'
        limit 1
    {% endset %}
    {% set backend_campaign_exists = (run_query(campaign_exists_sql).rows | length) > 0 %}
    {% set backend_account_exists = (run_query(account_exists_sql).rows | length) > 0 %}
    {% set adset_columns = adapter.get_columns_in_relation(source('meta_raw', 'adsets')) %}
    {% set adset_column_names = adset_columns | map(attribute='name') | map('lower') | list %}
{% else %}
    {% set backend_campaign_exists = false %}
    {% set backend_account_exists = false %}
    {% set adset_column_names = [] %}
{% endif %}
{% set has_tenant_id = 'tenant_id' in adset_column_names %}

select
    {% if has_tenant_id %}
    {{ tenant_id_expr('s.tenant_id::text') }} as tenant_id,
    {% else %}
    {{ tenant_id_expr() }} as tenant_id,
    {% endif %}
    s.id::text as adset_id,
    coalesce(c.external_id::text, s.campaign_id::text) as campaign_id,
    coalesce(
        {% if backend_account_exists %}
        nullif(ac.account_id::text, ''),
        nullif(ac.external_id::text, ''),
        {% endif %}
        nullif(s.account_id::text, ''),
        c.account_external_id::text
    ) as ad_account_id,
    s.name,
    s.status,
    s.daily_budget::numeric as daily_budget,
    s.created_time::timestamp as created_time,
    s.updated_time::timestamp as updated_time
from {{ source('meta_raw', 'adsets') }} s
{% if backend_campaign_exists %}
left join {{ backend_raw_schema }}.analytics_campaign c
    on s.campaign_id::text = c.id::text
{% else %}
left join (
    select
        null::text as id,
        null::text as external_id,
        null::text as account_external_id,
        null::uuid as ad_account_id
    where false
) c on false
{% endif %}
{% if backend_account_exists %}
left join {{ backend_raw_schema }}.analytics_adaccount ac
    on c.ad_account_id = ac.id
{% endif %}
