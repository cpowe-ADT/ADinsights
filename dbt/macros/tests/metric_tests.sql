{% test metric_roas_matches(model, revenue_column, spend_column, expected_column) %}
with calculations as (
    select
        {{ metric_roas(revenue_column, spend_column) }} as actual_roas,
        {{ expected_column }} as expected_roas
    from {{ model }}
), normalized as (
    select
        round(actual_roas::numeric, 6) as actual_roas,
        round(expected_roas::numeric, 6) as expected_roas
    from calculations
)
select *
from normalized
where actual_roas is distinct from expected_roas
{% endtest %}
