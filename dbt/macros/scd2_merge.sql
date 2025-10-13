{% macro scd2_dimension(source_query, natural_key, tracked_columns, valid_from_column='valid_from', valid_to_column='valid_to', is_current_column='is_current', end_of_time="to_timestamp('9999-12-31', 'YYYY-MM-DD')", order_by_columns=[]) %}
-- Macro to build SCD Type 2 dimensions.
-- source_query: SQL string that returns the latest snapshot with an "effective_from" column.
-- natural_key: string or list of columns representing natural key
-- tracked_columns: list of column names to watch for changes

{% set nk_cols = natural_key if natural_key is iterable and natural_key is not string else [natural_key] %}
{% set partition_cols = nk_cols + tracked_columns %}
{% if order_by_columns is string %}
    {% set order_by_columns = [order_by_columns] %}
{% elif order_by_columns is none %}
    {% set order_by_columns = [] %}
{% endif %}

{% set base_change_cols = nk_cols + tracked_columns + ['effective_from'] %}
{% set change_cols = base_change_cols[:] %}
{% for col in order_by_columns %}
    {% if col not in change_cols %}
        {% do change_cols.append(col) %}
    {% endif %}
{% endfor %}
{% set order_clause = ['effective_from'] + order_by_columns %}
{% set partition_expr = ', '.join('coalesce(' + col + ", '__missing__')" for col in partition_cols) %}

with ordered_source as (
    select
        {{ ', '.join(change_cols) }},
        row_number() over (
            partition by {{ partition_expr }}
            order by {{ ', '.join(order_clause) }}
        ) as _dbt_scd2_row
    from (
        {{ source_query }}
    ) as src
),

deduped_source as (
    select {{ ', '.join('o.' + col for col in change_cols) }}
    from ordered_source o
    where o._dbt_scd2_row = 1
),

changes as (
    select
        {{ ', '.join(nk_cols) }},
        {{ ', '.join(tracked_columns) }},
        effective_from,
        lead(effective_from) over (
            partition by {{ ', '.join(nk_cols) }}
            order by {{ ', '.join(order_clause) }}
        ) as next_effective_from
    from deduped_source
)

select
    {{ ', '.join('c.' + col for col in nk_cols) }},
    {{ ', '.join('c.' + col for col in tracked_columns) }},
    c.effective_from as {{ valid_from_column }},
    coalesce(c.next_effective_from - interval '1 second', {{ end_of_time }}) as {{ valid_to_column }},
    case when c.next_effective_from is null then true else false end as {{ is_current_column }}
from changes c
{% endmacro %}
