{{ config(materialized='view') }}

select
    tenant_id,
    campaign_id,
    ad_account_id,
    name as campaign_name,
    status,
    effective_status,
    objective,
    created_time,
    updated_time,
    dbt_valid_from,
    dbt_valid_to
from {{ ref('meta_campaign_snapshot') }}
