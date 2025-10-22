{% macro metric_ctr(clicks, impressions) %}
    {{ safe_divide(clicks, impressions) }}
{% endmacro %}

{% macro metric_conversion_rate(conversions, clicks) %}
    {{ safe_divide(conversions, clicks) }}
{% endmacro %}

{% macro metric_cost_per_click(spend, clicks) %}
case
    when {{ clicks }} is null or {{ clicks }} = 0 then null
    else {{ safe_divide(spend, clicks) }}
end
{% endmacro %}

{% macro metric_cost_per_conversion(spend, conversions) %}
case
    when {{ conversions }} is null or {{ conversions }} = 0 then null
    else {{ safe_divide(spend, conversions) }}
end
{% endmacro %}

{% macro metric_cpm(spend, impressions) %}
    {{ safe_divide('(' ~ spend ~ ') * 1000', impressions) }}
{% endmacro %}

{% macro metric_return_on_ad_spend(revenue, spend) %}
    {{ safe_divide(revenue, spend) }}
{% endmacro %}

{% macro metric_pacing(actual_value, target_value) %}
    {{ safe_divide(actual_value, target_value) }}
{% endmacro %}
