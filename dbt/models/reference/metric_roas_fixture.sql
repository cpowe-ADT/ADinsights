{{ config(materialized='view') }}

select *
from (
    values
        (100::numeric, 50::numeric, 2::numeric),
        (0::numeric, 0::numeric, 0::numeric),
        (null::numeric, 25::numeric, null::numeric),
        (50::numeric, null::numeric, 0::numeric)
) as fixtures(revenue, spend, expected_roas)
