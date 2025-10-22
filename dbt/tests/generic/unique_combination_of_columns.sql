{% test unique_combination_of_columns(model, combination) %}
with duplicates as (
    select
        {{ combination | join(', ') }},
        count(*) as record_count
    from {{ model }}
    group by {{ combination | join(', ') }}
    having count(*) > 1
)

select *
from duplicates
{% endtest %}
