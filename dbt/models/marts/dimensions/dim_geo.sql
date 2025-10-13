{{ config(materialized='table') }}

select
    parish_code,
    parish_name,
    region_name,
    latitude,
    longitude
from {{ ref('geo_parish_lookup') }}
