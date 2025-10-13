{% macro apply_ci_fixtures() %}
    {% set env_flag = env_var('CI_USE_SEEDS', '') | lower %}
    {% set should_force = env_flag in ['1', 'true', 'yes', 'on'] %}

    {% set raw_schema = var('raw_schema', 'raw') %}
    {% set raw_google_ads_schema = var('raw_google_ads_schema', 'raw_google_ads') %}
    {% set raw_meta_schema = var('raw_meta_schema', 'raw_meta') %}
    {% set seed_schema = var('ci_seed_schema', target.schema) %}
    {% set seed_database = target.database %}

    {% if target.type == 'duckdb' %}
        {% set json_macro %}
            create or replace macro jsonb_array_elements(input_json) as table(
                select value::json from json_each(coalesce(input_json, '[]'))
            )
        {% endset %}
        {% do run_query(json_macro) %}
        {% do log('Ensured duckdb compatibility macro jsonb_array_elements is available for CI.', info=True) %}
    {% endif %}

    {% set fixtures = [
        {'schema': raw_schema, 'identifier': 'google_ads_insights', 'seed_identifier': 'raw__google_ads_insights'},
        {'schema': raw_schema, 'identifier': 'meta_ads_insights', 'seed_identifier': 'raw__meta_ads_insights'},
        {'schema': raw_schema, 'identifier': 'linkedin_transparency', 'seed_identifier': 'raw__linkedin_transparency'},
        {'schema': raw_schema, 'identifier': 'tiktok_transparency', 'seed_identifier': 'raw__tiktok_transparency'},
        {'schema': raw_google_ads_schema, 'identifier': 'campaign_daily', 'seed_identifier': 'raw_google_ads__campaign_daily'},
        {'schema': raw_google_ads_schema, 'identifier': 'geographic_view', 'seed_identifier': 'raw_google_ads__geographic_view'},
        {'schema': raw_meta_schema, 'identifier': 'ad_insights', 'seed_identifier': 'raw_meta__ad_insights'},
        {'schema': raw_meta_schema, 'identifier': 'campaigns', 'seed_identifier': 'raw_meta__campaigns'},
        {'schema': raw_meta_schema, 'identifier': 'ads', 'seed_identifier': 'raw_meta__ads'},
        {'schema': raw_meta_schema, 'identifier': 'adsets', 'seed_identifier': 'raw_meta__adsets'}
    ] %}

    {% for fixture in fixtures %}
        {% set seed_relation = adapter.get_relation(
            database=seed_database,
            schema=seed_schema,
            identifier=fixture.seed_identifier
        ) %}

        {% if not seed_relation %}
            {% do log('Skipping CI fixture view for ' ~ fixture.identifier ~ ' because seed relation was not found.', info=True) %}
            {% continue %}
        {% endif %}

        {% set target_relation = api.Relation.create(
            database=seed_database,
            schema=fixture.schema,
            identifier=fixture.identifier,
            type='view'
        ) %}
        {% do adapter.create_schema(target_relation) %}

        {% set existing_relation = adapter.get_relation(
            database=seed_database,
            schema=fixture.schema,
            identifier=fixture.identifier
        ) %}

        {% if existing_relation and not should_force %}
            {% do log('Found existing relation for ' ~ target_relation ~ '; leaving it untouched.', info=True) %}
            {% continue %}
        {% endif %}

        {% if existing_relation %}
            {% do adapter.drop_relation(existing_relation) %}
        {% endif %}

        {% set statement %}
            create view {{ target_relation }} as
            select * from {{ seed_relation }}
        {% endset %}

        {% do run_query(statement) %}
        {% if should_force %}
            {% do log('Created CI fixture view for ' ~ target_relation ~ ' (forced by CI_USE_SEEDS).', info=True) %}
        {% else %}
            {% do log('Created CI fixture view for ' ~ target_relation ~ ' because no existing relation was found.', info=True) %}
        {% endif %}
    {% endfor %}

    {% if should_force %}
        {% do log('CI_USE_SEEDS enabled; fixture views forced to seed data.', info=True) %}
    {% else %}
        {% do log('CI_USE_SEEDS unset; fixture views only created when missing.', info=True) %}
    {% endif %}
{% endmacro %}
