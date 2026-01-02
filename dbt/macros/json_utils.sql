{% macro json_array_elements_subquery(json_expr) %}
  {{ adapter.dispatch('json_array_elements_subquery', 'adinsights')(json_expr) }}
{% endmacro %}

{% macro default__json_array_elements_subquery(json_expr) %}
  jsonb_array_elements({{ json_expr }})
{% endmacro %}

{% macro duckdb__json_array_elements_subquery(json_expr) %}
  (
      select value as action_json
      from json_each({{ json_expr }})
  )
{% endmacro %}

{% macro json_array_coalesce(column_expr) %}
  {{ adapter.dispatch('json_array_coalesce', 'adinsights')(column_expr) }}
{% endmacro %}

{% macro default__json_array_coalesce(column_expr) %}
  {% set expr = column_expr | replace("'", "") %}
  coalesce({{ expr }}::jsonb, '[]'::jsonb)
{% endmacro %}

{% macro duckdb__json_array_coalesce(column_expr) %}
  {% set expr = column_expr | replace("'", "") %}
  from_json(coalesce(nullif({{ expr }}, ''), '[]'))
{% endmacro %}

{% macro json_build_object(pairs) %}
  {{ adapter.dispatch('json_build_object', 'adinsights')(pairs) }}
{% endmacro %}

{% macro default__json_build_object(pairs) %}
  jsonb_build_object(
    {%- for key, value in pairs.items() -%}
      '{{ key }}', {{ value }}{% if not loop.last %}, {% endif %}
    {%- endfor -%}
  )
{% endmacro %}

{% macro duckdb__json_build_object(pairs) %}
  json_object(
    {%- for key, value in pairs.items() -%}
      '{{ key }}', {{ value }}{% if not loop.last %}, {% endif %}
    {%- endfor -%}
  )
{% endmacro %}

{% macro json_array_agg(expression, distinct=false) %}
  {{ adapter.dispatch('json_array_agg', 'adinsights')(expression, distinct) }}
{% endmacro %}

{% macro default__json_array_agg(expression, distinct=false) %}
  jsonb_agg({% if distinct %}distinct {% endif %}{{ expression }})
{% endmacro %}

{% macro duckdb__json_array_agg(expression, distinct=false) %}
  json_group_array({% if distinct %}distinct {% endif %}{{ expression }})
{% endmacro %}

{% macro json_empty_array() %}
  {{ adapter.dispatch('json_empty_array', 'adinsights')() }}
{% endmacro %}

{% macro default__json_empty_array() %}
  '[]'::jsonb
{% endmacro %}

{% macro duckdb__json_empty_array() %}
  json('[]')
{% endmacro %}

{% macro json_typeof(expression) %}
  {{ adapter.dispatch('json_typeof', 'adinsights')(expression) }}
{% endmacro %}

{% macro default__json_typeof(expression) %}
  jsonb_typeof({{ expression }})
{% endmacro %}

{% macro duckdb__json_typeof(expression) %}
  lower(json_type({{ expression }}))
{% endmacro %}

{% macro json_get_text(json_expr, key) %}
  {{ adapter.dispatch('json_get_text', 'adinsights')(json_expr, key) }}
{% endmacro %}

{% macro default__json_get_text(json_expr, key) %}
  {{ json_expr }} ->> {{ key }}
{% endmacro %}

{% macro duckdb__json_get_text(json_expr, key) %}
  {% set key_clean = key | replace("'", "") %}
  json_extract_string({{ json_expr }}, '$.{{ key_clean }}')
{% endmacro %}

{% macro json_array_agg_ordered(expression, order_by, distinct=false) %}
  {{ adapter.dispatch('json_array_agg_ordered', 'adinsights')(expression, order_by, distinct) }}
{% endmacro %}

{% macro default__json_array_agg_ordered(expression, order_by, distinct=false) %}
  jsonb_agg({% if distinct %}distinct {% endif %}{{ expression }} order by {{ order_by }})
{% endmacro %}

{% macro duckdb__json_array_agg_ordered(expression, order_by, distinct=false) %}
  json(list({% if distinct %}distinct {% endif %}{{ expression }} order by {{ order_by }}))
{% endmacro %}
