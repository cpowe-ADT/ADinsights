{% snapshot ad %}
    {{
        config(
            unique_key='ad_id',
            strategy='check',
            check_cols=['name', 'status', 'budget']
        )
    }}

    select
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
