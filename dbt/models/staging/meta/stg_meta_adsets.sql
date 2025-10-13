{{ config(unique_key='id', incremental_strategy='delete+insert') }}

select
    id::text as adset_id,
    campaign_id::text as campaign_id,
    account_id::text as ad_account_id,
    name,
    status,
    daily_budget::numeric as daily_budget,
    created_time::timestamp as created_time,
    updated_time::timestamp as updated_time
from {{ source('meta_raw', 'adsets') }}
