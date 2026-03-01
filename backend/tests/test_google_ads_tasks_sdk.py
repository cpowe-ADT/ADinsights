from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from alerts.models import AlertRun
from integrations.google_ads.client import (
    AdGroupAdDailyRow,
    CampaignDailyRow,
    GeographicDailyRow,
    GoogleAdsSdkError,
)
from integrations.models import GoogleAdsSyncState, PlatformCredential
from integrations.tasks import sync_google_ads_sdk_incremental

pytestmark = pytest.mark.django_db


def _create_google_credential(tenant) -> PlatformCredential:
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("access-token", "refresh-token")
    credential.save()
    return credential


def test_sync_google_ads_sdk_incremental_success_resets_failures(monkeypatch, tenant):
    _create_google_credential(tenant)
    state = GoogleAdsSyncState.objects.create(
        tenant=tenant,
        account_id="1234567890",
        desired_engine=GoogleAdsSyncState.ENGINE_SDK,
        effective_engine=GoogleAdsSyncState.ENGINE_SDK,
        consecutive_sdk_failures=2,
    )

    class DummyClient:
        def __init__(self, *args, **kwargs):  # noqa: D401
            return None

        def fetch_campaign_daily(self, **kwargs):  # noqa: ANN003
            return [
                CampaignDailyRow(
                    customer_id="1234567890",
                    campaign_id="1",
                    campaign_name="Campaign",
                    campaign_status="ENABLED",
                    advertising_channel_type="SEARCH",
                    date_day=date(2026, 2, 20),
                    currency_code="USD",
                    impressions=10,
                    clicks=2,
                    conversions=Decimal("1"),
                    conversions_value=Decimal("5"),
                    cost_micros=1000000,
                    request_id="request-id",
                )
            ]

        def fetch_ad_group_ad_daily(self, **kwargs):  # noqa: ANN003
            return [
                AdGroupAdDailyRow(
                    customer_id="1234567890",
                    campaign_id="1",
                    ad_group_id="2",
                    ad_id="3",
                    campaign_name="Campaign",
                    ad_name="Ad",
                    ad_status="ENABLED",
                    policy_approval_status="APPROVED",
                    policy_review_status="REVIEWED",
                    date_day=date(2026, 2, 20),
                    currency_code="USD",
                    impressions=10,
                    clicks=2,
                    conversions=Decimal("1"),
                    conversions_value=Decimal("5"),
                    cost_micros=1000000,
                    request_id="request-id",
                )
            ]

        def fetch_geographic_daily(self, **kwargs):  # noqa: ANN003
            return [
                GeographicDailyRow(
                    customer_id="1234567890",
                    campaign_id="1",
                    date_day=date(2026, 2, 20),
                    geo_target_country="JM",
                    geo_target_region="Kingston",
                    geo_target_city="Kingston",
                    currency_code="USD",
                    impressions=10,
                    clicks=2,
                    conversions=Decimal("1"),
                    conversions_value=Decimal("5"),
                    cost_micros=1000000,
                    request_id="request-id",
                )
            ]

        def fetch_accessible_customers(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_keyword_daily(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_search_term_daily(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_asset_group_daily(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_conversion_action_daily(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_change_events(self, **kwargs):  # noqa: ANN003
            return []

        def fetch_recommendations(self, **kwargs):  # noqa: ANN003
            return []

    monkeypatch.setattr("integrations.tasks.GoogleAdsSdkClient", DummyClient)
    result = sync_google_ads_sdk_incremental.run(str(tenant.id))
    state.refresh_from_db()

    assert result["synced"] == 1
    assert state.consecutive_sdk_failures == 0
    assert state.fallback_active is False


def test_sync_google_ads_sdk_incremental_auto_rolls_back_after_three_failures(monkeypatch, tenant):
    _create_google_credential(tenant)
    state = GoogleAdsSyncState.objects.create(
        tenant=tenant,
        account_id="1234567890",
        desired_engine=GoogleAdsSyncState.ENGINE_SDK,
        effective_engine=GoogleAdsSyncState.ENGINE_SDK,
        consecutive_sdk_failures=2,
    )

    class FailingClient:
        def __init__(self, *args, **kwargs):  # noqa: D401
            raise GoogleAdsSdkError("boom", classification="google_ads_api_error")

    monkeypatch.setattr("integrations.tasks.GoogleAdsSdkClient", FailingClient)
    result = sync_google_ads_sdk_incremental.run(str(tenant.id))
    state.refresh_from_db()

    assert result["failed"] == 1
    assert state.effective_engine == GoogleAdsSyncState.ENGINE_AIRBYTE
    assert state.fallback_active is True
    assert AlertRun.objects.filter(rule_slug="google_ads_sdk_auto_rollback").exists()
