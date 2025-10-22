{{ config(materialized='table') }}

with ranked as (
    select
        {{ tenant_id_expr() }} as tenant_id,
        parish_code,
        parish_name,
        region_name,
        latitude,
        longitude,
        row_number() over (partition by parish_code order by parish_name) as parish_rank
    from {{ ref('geo_parish_lookup') }}
)

select
    tenant_id,
    parish_code,
    parish_name,
    region_name,
    latitude,
    longitude
from ranked
where parish_rank = 1
