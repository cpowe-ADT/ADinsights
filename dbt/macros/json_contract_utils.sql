{% macro json_contract_missing_keys_condition(object_expr, required_keys) %}
    {% if required_keys %}
    exists (
        select 1
        from unnest(array[
            {% for key in required_keys %}
            '{{ key }}'{% if not loop.last %}, {% endif %}
            {% endfor %}
        ]) as required_key
        where not (({{ object_expr }}) ? required_key)
    )
    {% else %}
    false
    {% endif %}
{% endmacro %}

{% macro json_contract_array_missing_keys_condition(array_expr, required_keys) %}
    {% if required_keys %}
    exists (
        select 1
        from jsonb_array_elements(({{ array_expr }})) as element
        cross join unnest(array[
            {% for key in required_keys %}
            '{{ key }}'{% if not loop.last %}, {% endif %}
            {% endfor %}
        ]) as required_key
        where not (element ? required_key)
    )
    {% else %}
    false
    {% endif %}
{% endmacro %}

{% macro json_contract_array_invalid_types_condition(array_expr, keys, expected_type='number') %}
    {% if keys %}
    exists (
        select 1
        from jsonb_array_elements(({{ array_expr }})) as element
        cross join unnest(array[
            {% for key in keys %}
            '{{ key }}'{% if not loop.last %}, {% endif %}
            {% endfor %}
        ]) as key_name
        where element ? key_name
          and jsonb_typeof(element -> key_name) not in ('{{ expected_type }}', 'null')
    )
    {% else %}
    false
    {% endif %}
{% endmacro %}

{% macro json_contract_array_elements_invalid_type_condition(array_expr, expected_type) %}
    exists (
        select 1
        from jsonb_array_elements(({{ array_expr }})) as element
        where jsonb_typeof(element) != '{{ expected_type }}'
    )
{% endmacro %}
