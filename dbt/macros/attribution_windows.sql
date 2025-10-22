{% macro attribution_window_days_expr(source_platform_expression) %}
    {%- set meta_days = var('meta_attribution_window_days', 7) -%}
    {%- set google_days = var('google_attribution_window_days', 30) -%}
    {%- set default_days = var('default_attribution_window_days', 7) -%}
    {%- set expression = "case when lower(" ~ source_platform_expression ~ ") = 'meta_ads' then " ~ (meta_days | string)
        ~ " when lower(" ~ source_platform_expression ~ ") = 'google_ads' then " ~ (google_days | string)
        ~ " else " ~ (default_days | string) ~ " end" -%}
    {{ return('(' ~ expression ~ ')') }}
{% endmacro %}

{% macro normalize_attribution_metric(metric_expression, source_platform_expression) %}
    {%- set target = var('target_attribution_window_days', 7) -%}
    {%- set numerator = metric_expression ~ ' * ' ~ (target | string) -%}
    {%- set denominator = attribution_window_days_expr(source_platform_expression) -%}
    {{ safe_divide(numerator, denominator) }}
{% endmacro %}
