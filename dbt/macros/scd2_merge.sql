{% macro scd2_dimension(source_query, natural_key, tracked_columns, valid_from_column='valid_from', valid_to_column='valid_to', is_current_column='is_current', end_of_time="cast('9999-12-31 23:59:59' as timestamp)") %}
-- Macro to build SCD Type 2 dimensions.
-- source_query: SQL string that returns the latest snapshot with an "effective_from" column.
-- natural_key: string or list of columns representing natural key
-- tracked_columns: list of column names to watch for changes

{% set nk_cols = natural_key if natural_key is iterable and natural_key is not string else [natural_key] %}
{% set partition_cols = nk_cols + tracked_columns %}
{% set change_cols = nk_cols + tracked_columns + ['effective_from'] %}
{% set partition_expr_parts = [] %}
{% for col in partition_cols %}
  {% do partition_expr_parts.append("coalesce(" ~ col ~ ", '__missing__')") %}
{% endfor %}
{% set partition_expr = ', '.join(partition_expr_parts) %}
{% set change_cols_aliases = [] %}
{% for col in change_cols %}
  {% do change_cols_aliases.append('o.' ~ col) %}
{% endfor %}
{% set nk_aliases = [] %}
{% for col in nk_cols %}
  {% do nk_aliases.append('c.' ~ col) %}
{% endfor %}
{% set tracked_aliases = [] %}
{% for col in tracked_columns %}
  {% do tracked_aliases.append('c.' ~ col) %}
{% endfor %}

with ordered_source as (
    select
        {{ ', '.join(change_cols) }},
        row_number() over (
            partition by {{ partition_expr }}
            order by effective_from
        ) as _dbt_scd2_row
    from (
        {{ source_query }}
    ) as src
),

deduped_source as (
    select {{ ', '.join(change_cols_aliases) }}
    from ordered_source o
    where o._dbt_scd2_row = 1
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
    {{ ', '.join(nk_aliases) }},
    {{ ', '.join(tracked_aliases) }},
    c.effective_from as {{ valid_from_column }},
    coalesce(c.next_effective_from - interval '1 second', {{ end_of_time }}) as {{ valid_to_column }},
    case when c.next_effective_from is null then true else false end as {{ is_current_column }}
from changes c
{% endmacro %}
