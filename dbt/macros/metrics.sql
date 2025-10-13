{% macro metric_ctr(clicks, impressions) %}
    {{ safe_divide(clicks, impressions) }}
{% endmacro %}

{% macro metric_conversion_rate(conversions, clicks) %}
    {{ safe_divide(conversions, clicks) }}
{% endmacro %}

{% macro metric_cost_per_conversion(spend, conversions) %}
case
    when {{ conversions }} is null or {{ conversions }} = 0 then null
    else {{ spend }}::numeric / nullif({{ conversions }}, 0)
end
{% endmacro %}

{% macro metric_cost_per_click(spend, clicks) %}
case
    when {{ clicks }} is null or {{ clicks }} = 0 then null
    else {{ spend }}::numeric / nullif({{ clicks }}, 0)
end
{% endmacro %}

{% macro metric_cpm(spend, impressions) %}
    {{ safe_divide(spend * 1000, impressions) }}
{% endmacro %}

{% macro metric_roas(revenue, spend) %}
    {{ safe_divide(revenue, spend) }}
{% endmacro %}
