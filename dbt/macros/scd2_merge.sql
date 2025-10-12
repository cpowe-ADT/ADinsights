{% macro scd2_dimension(source_query, natural_key, tracked_columns, valid_from_column='valid_from', valid_to_column='valid_to', is_current_column='is_current') %}
-- Macro to build SCD Type 2 dimensions.
-- source_query: SQL string that returns the latest snapshot with an "effective_from" column.
-- natural_key: string or list of columns representing natural key
-- tracked_columns: list of column names to watch for changes

{% set nk_cols = natural_key if natural_key is iterable and natural_key is not string else [natural_key] %}
{% set change_cols = nk_cols + tracked_columns + ['effective_from'] %}

with ordered_source as (
    select
        {{ ', '.join(change_cols) }}
    from (
        {{ source_query }}
    ) as src
),

changes as (
    select
        {{ ', '.join(nk_cols) }},
        {{ ', '.join(tracked_columns) }},
        effective_from,
        lead(effective_from) over (partition by {{ ', '.join(nk_cols) }} order by effective_from) as next_effective_from
    from ordered_source
)

select
    {{ ', '.join('c.' + col for col in nk_cols) }},
    {{ ', '.join('c.' + col for col in tracked_columns) }},
    c.effective_from as {{ valid_from_column }},
    coalesce(c.next_effective_from - interval '1 second', to_timestamp('9999-12-31', 'YYYY-MM-DD')) as {{ valid_to_column }},
    case when c.next_effective_from is null then true else false end as {{ is_current_column }}
from changes c
{% endmacro %}
