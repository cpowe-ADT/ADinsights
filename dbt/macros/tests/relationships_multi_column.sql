{% test relationships_multi_column(model, to, from_columns, to_columns, column_name=None) %}
    select
        {% for column in from_columns %}
            m.{{ column }}{{ ',' if not loop.last }}
        {% endfor %}
    from {{ model }} as m
    left join {{ to }} as t
        on {% for idx in range(from_columns | length) %}
            m.{{ from_columns[idx] }} = t.{{ to_columns[idx] }}{% if not loop.last %} and {% endif %}
        {% endfor %}
        and t.dbt_valid_from <= coalesce(m.effective_from, m.date_day::timestamp)
        and coalesce(t.dbt_valid_to, cast('9999-12-31 23:59:59' as timestamp)) >= coalesce(m.effective_from, m.date_day::timestamp)
    where t.{{ to_columns[0] }} is null
    limit 1
{% endtest %}
