{% macro scd2_dimension(source_query, natural_key, tracked_columns, valid_from_column='valid_from', valid_to_column='valid_to', is_current_column='is_current', end_of_time="to_timestamp('9999-12-31', 'YYYY-MM-DD')") %}
-- Macro to build SCD Type 2 dimensions.
-- source_query: SQL string that returns the latest snapshot with an "effective_from" column.
-- natural_key: string or list of columns representing natural key
-- tracked_columns: list of column names to watch for changes

{% set nk_cols = natural_key if natural_key is iterable and natural_key is not string else [natural_key] %}
{% set change_cols = nk_cols + tracked_columns + ['effective_from'] %}
{% set nk_partition_expr = ', '.join(nk_cols) %}
{% set nk_partition_clause = nk_partition_expr if nk_partition_expr|length > 0 else '1' %}

with ordered_source as (
    select
        {{ ', '.join(change_cols) }},
        row_number() over (
            partition by {{ nk_partition_clause }}
            order by effective_from
        ) as _dbt_scd2_row
        {% if tracked_columns|length > 0 %},
        {% for col in tracked_columns %}
        lag({{ col }}) over (
            partition by {{ nk_partition_clause }}
            order by effective_from
        ) as _dbt_prev_{{ loop.index }}{% if not loop.last %},{% endif %}
        {% endfor %}
        {% endif %}
    from (
        {{ source_query }}
    ) as src
),

deduped_source as (
    select {{ ', '.join('o.' + col for col in change_cols) }}
    from ordered_source o
    where o._dbt_scd2_row = 1
    {% if tracked_columns|length > 0 %}
        or (
            {% for col in tracked_columns %}
            {{ 'o.' + col }} is distinct from o._dbt_prev_{{ loop.index }}{% if not loop.last %}
            or{% endif %}
            {% endfor %}
        )
    {% endif %}
),

changes as (
    select
        {{ ', '.join(nk_cols) }},
        {{ ', '.join(tracked_columns) }},
        effective_from,
        lead(effective_from) over (partition by {{ ', '.join(nk_cols) }} order by effective_from) as next_effective_from
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
