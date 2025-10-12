{{ config(unique_key='id', incremental_strategy='delete+insert') }}

select
    id::text as ad_id,
    adset_id::text as adset_id,
    campaign_id::text as campaign_id,
    account_id::text as account_id,
    name,
    status,
    created_time::timestamp as created_time,
    updated_time::timestamp as updated_time
from {{ source('meta_raw', 'ads') }}
