{% macro backend_raw_fixture_sql(fixture) %}
    {% set backend_raw_schema = env_var('BACKEND_RAW_SCHEMA', 'public') %}
    {% set backend_database = target.get('dbname') or target.get('database') %}
    {% set raw_performance_relation = adapter.get_relation(
        database=backend_database,
        schema=backend_raw_schema,
        identifier='analytics_rawperformancerecord'
    ) %}
    {% set adset_relation = adapter.get_relation(
        database=backend_database,
        schema=backend_raw_schema,
        identifier='analytics_adset'
    ) %}
    {% set ad_relation = adapter.get_relation(
        database=backend_database,
        schema=backend_raw_schema,
        identifier='analytics_ad'
    ) %}
    {% set campaign_relation = adapter.get_relation(
        database=backend_database,
        schema=backend_raw_schema,
        identifier='analytics_campaign'
    ) %}
    {% set account_relation = adapter.get_relation(
        database=backend_database,
        schema=backend_raw_schema,
        identifier='analytics_adaccount'
    ) %}

    {% if raw_performance_relation is none %}
        {{ return(none) }}
    {% endif %}

    {% set tenant_scope = var('tenant_id', '') %}
    {% set tenant_filter = "" %}
    {% if tenant_scope and tenant_scope != 'tenant_demo' %}
        {% set tenant_filter = " and r.tenant_id::text = '" ~ tenant_scope ~ "'" %}
    {% endif %}

    {% if fixture.schema == var('raw_schema', 'raw') and fixture.identifier == 'meta_ads_insights' %}
        {% set sql %}
            select
                r.tenant_id::text as tenant_id,
                coalesce(
                    nullif(raw_payload->>'ad_account_id', ''),
                    ac.account_id,
                    ac.external_id,
                    c.account_external_id,
                    'unknown-meta'
                ) as ad_account_id,
                coalesce(nullif(raw_payload->>'campaign_id', ''), r.campaign_id::text, r.external_id) as campaign_id,
                coalesce(
                    nullif(raw_payload->>'campaign_name', ''),
                    c.name,
                    c.external_id,
                    r.campaign_id::text,
                    r.external_id
                ) as campaign_name,
                coalesce(nullif(raw_payload->>'adset_id', ''), r.adset_id::text, r.external_id) as adset_id,
                coalesce(nullif(raw_payload->>'ad_id', ''), r.ad_id::text, r.external_id) as ad_id,
                coalesce(
                    nullif(raw_payload->>'ad_name', ''),
                    ad.name,
                    ad.external_id,
                    r.ad_id::text,
                    r.external_id
                ) as ad_name,
                r.date as date_start,
                coalesce(
                    nullif(raw_payload->>'region', ''),
                    nullif(raw_payload->>'geo_target_region', ''),
                    'Unknown'
                ) as region,
                r.spend,
                r.impressions,
                r.reach,
                r.clicks,
                r.conversions,
                coalesce(r.updated_at, r.ingested_at, current_timestamp) as updated_time,
                coalesce(r.updated_at, r.ingested_at, current_timestamp) as _airbyte_emitted_at,
                r.id::text as _airbyte_raw_id
            from {{ raw_performance_relation }} r
            left join {{ campaign_relation }} c
                on r.campaign_id = c.id
            left join {{ ad_relation }} ad
                on r.ad_id = ad.id
            left join {{ account_relation }} ac
                on r.ad_account_id = ac.id or c.ad_account_id = ac.id
            where r.source = 'meta'
              and r.level = 'ad'
              {{ tenant_filter }}
        {% endset %}
        {{ return(sql) }}
    {% endif %}

    {% if fixture.schema == var('raw_schema', 'raw') and fixture.identifier == 'google_ads_insights' %}
        {% set sql %}
            select
                r.tenant_id::text as tenant_id,
                coalesce(
                    nullif(raw_payload->>'customer_id', ''),
                    ac.account_id,
                    ac.external_id,
                    c.account_external_id,
                    'unknown-google'
                ) as customer_id,
                coalesce(nullif(raw_payload->>'campaign_id', ''), r.campaign_id::text, r.external_id) as campaign_id,
                coalesce(
                    nullif(raw_payload->>'campaign_name', ''),
                    c.name,
                    c.external_id,
                    r.campaign_id::text,
                    r.external_id
                ) as campaign_name,
                coalesce(
                    nullif(raw_payload->>'ad_group_id', ''),
                    r.adset_id::text,
                    r.external_id
                ) as ad_group_id,
                coalesce(nullif(raw_payload->>'criterion_id', ''), r.ad_id::text, r.external_id) as criterion_id,
                coalesce(
                    nullif(raw_payload->>'ad_name', ''),
                    ad.name,
                    ad.external_id,
                    r.ad_id::text,
                    r.external_id
                ) as ad_name,
                r.date as date_day,
                coalesce(
                    nullif(raw_payload->>'geo_target_region', ''),
                    nullif(raw_payload->>'region', ''),
                    'Unknown'
                ) as geo_target_region,
                r.spend * 1000000.0 as cost_micros,
                r.impressions,
                r.clicks,
                r.conversions,
                coalesce(r.updated_at, r.ingested_at, current_timestamp) as _airbyte_emitted_at,
                r.id::text as _airbyte_raw_id
            from {{ raw_performance_relation }} r
            left join {{ campaign_relation }} c
                on r.campaign_id = c.id
            left join {{ ad_relation }} ad
                on r.ad_id = ad.id
            left join {{ account_relation }} ac
                on r.ad_account_id = ac.id or c.ad_account_id = ac.id
            where r.source = 'google'
              and r.level = 'ad'
              {{ tenant_filter }}
        {% endset %}
        {{ return(sql) }}
    {% endif %}

    {% if fixture.schema == var('raw_meta_schema', 'raw_meta') and fixture.identifier == 'adsets' and adset_relation is not none %}
        {% set sql %}
            select
                a.tenant_id::text as tenant_id,
                a.id::text as id,
                a.campaign_id::text as campaign_id,
                coalesce(ac.account_id, ac.external_id, c.account_external_id, 'unknown-meta') as account_id,
                a.name,
                a.status,
                a.daily_budget,
                a.created_at as created_time,
                a.updated_at as updated_time
            from {{ adset_relation }} a
            left join {{ campaign_relation }} c
                on a.campaign_id = c.id
            left join {{ account_relation }} ac
                on c.ad_account_id = ac.id
            where 1 = 1
              {% if tenant_scope and tenant_scope != 'tenant_demo' %}
              and a.tenant_id::text = '{{ tenant_scope }}'
              {% endif %}
        {% endset %}
        {{ return(sql) }}
    {% endif %}

    {{ return(none) }}
{% endmacro %}
