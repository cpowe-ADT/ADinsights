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
