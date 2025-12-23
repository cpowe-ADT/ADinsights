{{ config(unique_key=['tenant_id', 'campaign_id'], incremental_strategy='delete+insert') }}

select
    {{ tenant_id_expr() }} as tenant_id,
    id::text as campaign_id,
    account_id::text as account_id,
    name,
    status,
    effective_status,
    objective,
    created_time::timestamp as created_time,
    updated_time::timestamp as updated_time
from {{ source('meta_raw', 'campaigns') }}
