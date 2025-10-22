{% test aggregate_snapshot_contract(model, parish_model) %}
{% set empty_array = json_empty_array() %}
with campaign_data as (
    select *
    from {{ model }}
),
latest_date as (
    select max(date_day) as date_day
    from campaign_data
),
scoped_campaigns as (
    select *
    from campaign_data
    where date_day = (select date_day from latest_date)
),
scoped_parishes as (
    select *
    from {{ parish_model }}
    where date_day = (select date_day from latest_date)
),
metrics as (
    select
        coalesce(sum(spend), 0) as total_spend,
        coalesce(sum(impressions), 0) as total_impressions,
        coalesce(sum(clicks), 0) as total_clicks,
        coalesce(sum(conversions), 0) as total_conversions,
        coalesce(count(distinct campaign_id), 0) as campaign_count
    from scoped_campaigns
),
parish_metrics as (
    select coalesce(count(distinct parish_code), 0) as parish_count
    from scoped_parishes
),
summary as (
    select {{ json_build_object({
        'currency': "'JMD'",
        'totalSpend': 'metrics.total_spend',
        'totalImpressions': 'metrics.total_impressions',
        'totalClicks': 'metrics.total_clicks',
        'totalConversions': 'metrics.total_conversions',
        'ctr': metric_ctr('metrics.total_clicks', 'metrics.total_impressions'),
        'conversionRate': metric_conversion_rate('metrics.total_conversions', 'metrics.total_clicks'),
        'costPerClick': metric_cost_per_click('metrics.total_spend', 'metrics.total_clicks'),
        'costPerConversion': metric_cost_per_conversion('metrics.total_spend', 'metrics.total_conversions'),
        'cpm': metric_cpm('metrics.total_spend', 'metrics.total_impressions'),
        'roas': metric_return_on_ad_spend('metrics.total_conversions', 'metrics.total_spend'),
        'campaignCount': 'metrics.campaign_count',
        'parishCount': 'parish_metrics.parish_count'
    }) }} as summary
    from metrics
    cross join parish_metrics
),
filters as (
    select
        coalesce(
            {{ json_array_agg('source_platform', true) }} filter (where source_platform is not null),
            {{ empty_array }}
        ) as source_platforms,
        coalesce(
            {{ json_array_agg('ad_account_id', true) }} filter (where ad_account_id is not null),
            {{ empty_array }}
        ) as ad_account_ids
    from scoped_campaigns
),
campaigns_json as (
    select coalesce(
        {{ json_array_agg(json_build_object({
            'date': "to_char(date_day, 'YYYY-MM-DD')",
            'sourcePlatform': 'source_platform',
            'adAccountId': 'ad_account_id',
            'campaignId': 'campaign_id',
            'campaignName': 'campaign_name',
            'spend': 'spend',
            'impressions': 'impressions',
            'clicks': 'clicks',
            'conversions': 'conversions',
            'ctr': 'ctr',
            'conversionRate': 'conversion_rate',
            'costPerClick': 'cost_per_click',
            'costPerConversion': 'cost_per_conversion',
            'cpm': 'cpm',
            'roas': 'roas',
            'parishCode': 'parish_code',
            'parishName': 'parish_name',
            'regionName': 'region_name',
            'firstSeenDate': "to_char(first_seen_date, 'YYYY-MM-DD')"
        })) }},
        {{ empty_array }}
    ) as campaigns
    from scoped_campaigns
),
parishes_json as (
    select coalesce(
        {{ json_array_agg(json_build_object({
            'date': "to_char(date_day, 'YYYY-MM-DD')",
            'parishCode': 'parish_code',
            'parishName': 'parish_name',
            'regionName': 'region_name',
            'spend': 'spend',
            'impressions': 'impressions',
            'clicks': 'clicks',
            'conversions': 'conversions',
            'campaignCount': 'campaign_count',
            'ctr': 'ctr',
            'conversionRate': 'conversion_rate',
            'costPerClick': 'cost_per_click',
            'costPerConversion': 'cost_per_conversion',
            'cpm': 'cpm',
            'roas': 'roas'
        })) }},
        {{ empty_array }}
    ) as parishes
    from scoped_parishes
),
generated as (
    select coalesce(date_day, current_date) as date_day
    from latest_date
),
payload as (
    select
        {{ json_build_object({
            'generatedAt': "to_char(date_day, 'YYYY-MM-DD""T""00:00:00""Z""')",
            'summary': 'summary.summary',
            'campaigns': 'campaigns_json.campaigns',
            'parishes': 'parishes_json.parishes',
            'filters': json_build_object({
                'sourcePlatforms': 'coalesce(filters.source_platforms, ' ~ empty_array ~ ')',
                'adAccountIds': 'coalesce(filters.ad_account_ids, ' ~ empty_array ~ ')'
            })
        }) }} as payload
    from generated
    cross join summary
    cross join campaigns_json
    cross join parishes_json
    cross join filters
),
violations as (
    select 'summary_missing_object' as error, payload
    from payload
    where {{ json_typeof("payload->'summary'") }} != 'object'

    union all

    select 'summary_missing_keys' as error, payload
    from payload
    where {{ json_contract_missing_keys_condition("payload->'summary'", [
        'currency',
        'totalSpend',
        'totalImpressions',
        'totalClicks',
        'totalConversions',
        'ctr',
        'conversionRate',
        'costPerClick',
        'costPerConversion',
        'cpm',
        'roas',
        'campaignCount',
        'parishCount'
    ]) }}

    union all

    select 'generated_at_not_string' as error, payload
    from payload
    where {{ json_typeof("payload->'generatedAt'") }} != 'string'

    union all

    select 'filters_missing_object' as error, payload
    from payload
    where {{ json_typeof("payload->'filters'") }} != 'object'

    union all

    select 'filters_missing_keys' as error, payload
    from payload
    where {{ json_contract_missing_keys_condition("payload->'filters'", ['sourcePlatforms', 'adAccountIds']) }}

    union all

    select 'filters_platforms_not_array' as error, payload
    from payload
    where {{ json_typeof("(payload->'filters')->'sourcePlatforms'") }} != 'array'

    union all

    select 'filters_accounts_not_array' as error, payload
    from payload
    where {{ json_typeof("(payload->'filters')->'adAccountIds'") }} != 'array'

    union all

    select 'filters_platform_elements_not_strings' as error, payload
    from payload
    where {{ json_contract_array_elements_invalid_type_condition("(payload->'filters')->'sourcePlatforms'", 'string') }}

    union all

    select 'filters_account_elements_not_strings' as error, payload
    from payload
    where {{ json_contract_array_elements_invalid_type_condition("(payload->'filters')->'adAccountIds'", 'string') }}

    union all

    select 'campaigns_not_array' as error, payload
    from payload
    where {{ json_typeof("payload->'campaigns'") }} != 'array'

    union all

    select 'campaigns_missing_keys' as error, payload
    from payload
    where {{ json_contract_array_missing_keys_condition("payload->'campaigns'", [
        'date',
        'sourcePlatform',
        'adAccountId',
        'campaignId',
        'campaignName',
        'spend',
        'impressions',
        'clicks',
        'conversions',
        'ctr',
        'conversionRate',
        'costPerClick',
        'costPerConversion',
        'cpm',
        'roas',
        'parishCode',
        'parishName',
        'regionName',
        'firstSeenDate'
    ]) }}

    union all

    select 'campaigns_numeric_types' as error, payload
    from payload
    where {{ json_contract_array_invalid_types_condition("payload->'campaigns'", [
        'spend',
        'impressions',
        'clicks',
        'conversions',
        'ctr',
        'conversionRate',
        'costPerClick',
        'costPerConversion',
        'cpm',
        'roas'
    ]) }}

    union all

    select 'parishes_not_array' as error, payload
    from payload
    where {{ json_typeof("payload->'parishes'") }} != 'array'

    union all

    select 'parishes_missing_keys' as error, payload
    from payload
    where {{ json_contract_array_missing_keys_condition("payload->'parishes'", [
        'date',
        'parishCode',
        'parishName',
        'regionName',
        'spend',
        'impressions',
        'clicks',
        'conversions',
        'campaignCount',
        'ctr',
        'conversionRate',
        'costPerClick',
        'costPerConversion',
        'cpm',
        'roas'
    ]) }}

    union all

    select 'parishes_numeric_types' as error, payload
    from payload
    where {{ json_contract_array_invalid_types_condition("payload->'parishes'", [
        'spend',
        'impressions',
        'clicks',
        'conversions',
        'campaignCount',
        'ctr',
        'conversionRate',
        'costPerClick',
        'costPerConversion',
        'cpm',
        'roas'
    ]) }}
)
select *
from violations
{% endtest %}
