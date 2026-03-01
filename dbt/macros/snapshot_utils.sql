{% macro reset_snapshot_if_missing_tenant(snapshot_relation) %}
    {% if execute %}
        {% set existing_relation = adapter.get_relation(
            database=snapshot_relation.database,
            schema=snapshot_relation.schema,
            identifier=snapshot_relation.identifier
        ) %}

        {% if existing_relation %}
            {% set existing_columns = adapter.get_columns_in_relation(existing_relation) %}
            {% set column_names = existing_columns | map(attribute='name') | map('lower') | list %}
            {% if 'tenant_id' not in column_names %}
                {% do log(
                    'Dropping legacy snapshot relation without tenant_id: ' ~ existing_relation,
                    info=True
                ) %}
                {% do adapter.drop_relation(existing_relation) %}
            {% endif %}
        {% endif %}
    {% endif %}

    select 1
{% endmacro %}
