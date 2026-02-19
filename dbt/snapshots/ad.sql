{% snapshot meta_ad_snapshot %}
    {{
        config(
            unique_key="tenant_id || ':' || ad_id",
            strategy='check',
            check_cols=['name', 'status', 'budget'],
            pre_hook="{{ reset_snapshot_if_missing_tenant(this) }}"
        )
    }}

    select
        tenant_id,
        ad_id,
        account_id as ad_account_id,
        adset_id,
        campaign_id,
        name,
        status,
        cast(null as numeric) as budget,
        created_time,
        updated_time
    from {{ ref('stg_meta_ads_metadata') }}
{% endsnapshot %}
