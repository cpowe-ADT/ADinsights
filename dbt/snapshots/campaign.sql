{% snapshot meta_campaign_snapshot %}
    {{
        config(
            unique_key="tenant_id || ':' || campaign_id",
            strategy='check',
            check_cols=['name', 'status', 'budget'],
            pre_hook="{{ reset_snapshot_if_missing_tenant(this) }}"
        )
    }}

    select
        tenant_id,
        campaign_id,
        account_id as ad_account_id,
        name,
        status,
        cast(null as numeric) as budget,
        effective_status,
        objective,
        created_time,
        updated_time
    from {{ ref('stg_meta_campaigns') }}
{% endsnapshot %}
