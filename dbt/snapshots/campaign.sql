{% snapshot campaign %}
    {{
        config(
            unique_key='campaign_id',
            strategy='check',
            check_cols=['name', 'status', 'budget']
        )
    }}

    select
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
