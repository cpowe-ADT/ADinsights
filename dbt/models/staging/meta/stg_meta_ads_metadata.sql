{{ config(unique_key=['tenant_id', 'ad_id'], incremental_strategy='delete+insert') }}

select
    {{ tenant_id_expr() }} as tenant_id,
    id::text as ad_id,
    adset_id::text as adset_id,
    campaign_id::text as campaign_id,
    account_id::text as account_id,
    name,
    status,
    created_time::timestamp as created_time,
    updated_time::timestamp as updated_time
from {{ source('meta_raw', 'ads') }}
