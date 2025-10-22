{% macro tenant_id_expr(column_expression=None) %}
    {%- set fallback = var('tenant_id', 'tenant_demo') -%}
    {%- set fallback_literal = "'" ~ fallback ~ "'" -%}
    {%- if column_expression -%}
        coalesce({{ column_expression }}, {{ fallback_literal }})
    {%- else -%}
        {{ fallback_literal }}
    {%- endif -%}
{% endmacro %}
