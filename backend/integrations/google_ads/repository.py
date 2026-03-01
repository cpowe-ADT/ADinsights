from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from django.utils import timezone

from accounts.models import Tenant
from integrations.google_ads.client import (
    AccessibleCustomerRow,
    AdGroupAdDailyRow,
    AssetGroupDailyRow,
    CampaignDailyRow,
    ChangeEventRow,
    ConversionActionDailyRow,
    GeographicDailyRow,
    KeywordDailyRow,
    RecommendationRow,
    SearchTermDailyRow,
)
from integrations.models import (
    GoogleAdsAccountMapping,
    GoogleAdsSdkAdGroupAdDaily,
    GoogleAdsSdkAssetGroupDaily,
    GoogleAdsSdkCampaignDaily,
    GoogleAdsSdkChangeEvent,
    GoogleAdsSdkConversionActionDaily,
    GoogleAdsSdkGeographicDaily,
    GoogleAdsSdkKeywordDaily,
    GoogleAdsSdkRecommendation,
    GoogleAdsSdkSearchTermDaily,
)


def _decimal(value: Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def upsert_campaign_daily_rows(*, tenant: Tenant, rows: Iterable[CampaignDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkCampaignDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            date_day=row.date_day,
            defaults={
                "campaign_name": row.campaign_name,
                "campaign_status": row.campaign_status,
                "advertising_channel_type": row.advertising_channel_type,
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_ad_group_ad_daily_rows(*, tenant: Tenant, rows: Iterable[AdGroupAdDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkAdGroupAdDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            ad_group_id=row.ad_group_id,
            ad_id=row.ad_id,
            date_day=row.date_day,
            defaults={
                "campaign_name": row.campaign_name,
                "ad_name": row.ad_name,
                "ad_status": row.ad_status,
                "policy_approval_status": row.policy_approval_status,
                "policy_review_status": row.policy_review_status,
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_geographic_daily_rows(*, tenant: Tenant, rows: Iterable[GeographicDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkGeographicDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            date_day=row.date_day,
            geo_target_country=row.geo_target_country,
            geo_target_region=row.geo_target_region,
            geo_target_city=row.geo_target_city,
            defaults={
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_keyword_daily_rows(*, tenant: Tenant, rows: Iterable[KeywordDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkKeywordDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            ad_group_id=row.ad_group_id,
            criterion_id=row.criterion_id,
            date_day=row.date_day,
            defaults={
                "keyword_text": row.keyword_text,
                "match_type": row.match_type,
                "criterion_status": row.criterion_status,
                "quality_score": row.quality_score,
                "ad_relevance": row.ad_relevance,
                "expected_ctr": row.expected_ctr,
                "landing_page_experience": row.landing_page_experience,
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_search_term_daily_rows(*, tenant: Tenant, rows: Iterable[SearchTermDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkSearchTermDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            ad_group_id=row.ad_group_id,
            search_term=row.search_term,
            date_day=row.date_day,
            defaults={
                "criterion_id": row.criterion_id,
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_asset_group_daily_rows(*, tenant: Tenant, rows: Iterable[AssetGroupDailyRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkAssetGroupDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            campaign_id=row.campaign_id,
            asset_group_id=row.asset_group_id,
            date_day=row.date_day,
            defaults={
                "asset_group_name": row.asset_group_name,
                "asset_group_status": row.asset_group_status,
                "currency_code": row.currency_code,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "conversions": _decimal(row.conversions),
                "conversions_value": _decimal(row.conversions_value),
                "cost_micros": int(row.cost_micros),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_conversion_action_daily_rows(
    *,
    tenant: Tenant,
    rows: Iterable[ConversionActionDailyRow],
) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkConversionActionDaily.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            conversion_action_id=row.conversion_action_id,
            date_day=row.date_day,
            defaults={
                "conversion_action_name": row.conversion_action_name,
                "conversion_action_type": row.conversion_action_type,
                "conversions": _decimal(row.conversions),
                "all_conversions": _decimal(row.all_conversions),
                "conversions_value": _decimal(row.conversions_value),
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_change_event_rows(*, tenant: Tenant, rows: Iterable[ChangeEventRow]) -> int:
    persisted = 0
    for row in rows:
        GoogleAdsSdkChangeEvent.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            event_fingerprint=row.event_fingerprint,
            defaults={
                "change_date_time": row.change_date_time,
                "user_email": row.user_email,
                "client_type": row.client_type,
                "change_resource_type": row.change_resource_type,
                "resource_change_operation": row.resource_change_operation,
                "campaign_id": row.campaign_id,
                "ad_group_id": row.ad_group_id,
                "ad_id": row.ad_id,
                "changed_fields": row.changed_fields,
                "source_request_id": row.request_id,
            },
        )
        persisted += 1
    return persisted


def upsert_recommendation_rows(*, tenant: Tenant, rows: Iterable[RecommendationRow]) -> int:
    persisted = 0
    now = timezone.now()
    for row in rows:
        GoogleAdsSdkRecommendation.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            recommendation_type=row.recommendation_type,
            resource_name=row.resource_name,
            defaults={
                "campaign_id": row.campaign_id,
                "ad_group_id": row.ad_group_id,
                "dismissed": row.dismissed,
                "impact_metadata": row.impact_metadata,
                "source_request_id": row.request_id,
                "last_seen_at": now,
            },
        )
        persisted += 1
    return persisted


def upsert_accessible_customer_rows(
    *,
    tenant: Tenant,
    rows: Iterable[AccessibleCustomerRow],
) -> int:
    persisted = 0
    now = timezone.now()
    for row in rows:
        GoogleAdsAccountMapping.all_objects.update_or_create(
            tenant=tenant,
            customer_id=row.customer_id,
            defaults={
                "manager_customer_id": row.manager_customer_id,
                "customer_name": row.customer_name,
                "currency_code": row.currency_code,
                "time_zone": row.time_zone,
                "status": row.status,
                "is_manager": row.is_manager,
                "last_seen_at": now,
            },
        )
        persisted += 1
    return persisted
