{% snapshot adset %}
    {{
        config(
            unique_key='adset_id',
            strategy='check',
            check_cols=['name', 'status', 'budget']
        )
    }}

    select
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
