{% snapshot meta_adset_snapshot %}
    {{
        config(
            unique_key="tenant_id || ':' || adset_id",
            strategy='check',
            check_cols=['name', 'status', 'budget'],
            pre_hook="{{ reset_snapshot_if_missing_tenant(this) }}"
        )
    }}

    select
        tenant_id,
        adset_id,
        ad_account_id,
        campaign_id,
        name,
        status,
        cast(daily_budget as numeric) as budget,
        created_time,
        updated_time
    from {{ ref('stg_meta_adsets') }}
{% endsnapshot %}
