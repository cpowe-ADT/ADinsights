from __future__ import annotations

from decimal import Decimal

import pytest

from analytics.models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord
from integrations.meta_graph import MetaGraphClientError
from integrations.models import APIErrorLog, MetaAccountSyncState, PlatformCredential
from integrations.tasks import (
    sync_meta_accounts,
    sync_meta_hierarchy,
    sync_meta_insights_incremental,
)


def _seed_meta_credential(user) -> PlatformCredential:
    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    credential.set_raw_tokens("meta-token", None)
    credential.save()
    return credential


@pytest.mark.django_db
def test_sync_meta_accounts_persists_ad_accounts(monkeypatch, user):
    _seed_meta_credential(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_ad_accounts(self, *, user_access_token: str):
            assert user_access_token == "meta-token"
            return [
                {
                    "id": "act_123",
                    "account_id": "123",
                    "name": "Primary Account",
                    "currency": "USD",
                    "account_status": 1,
                    "business_name": "Demo Biz",
                }
            ]

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())
    result = sync_meta_accounts.run()
    assert result["processed"] == 1
    assert result["succeeded"] == 1
    assert AdAccount.objects.filter(tenant=user.tenant, external_id="act_123").exists()
    sync_state = MetaAccountSyncState.objects.get(tenant=user.tenant, account_id="act_123")
    assert sync_state.last_job_status == "succeeded"


@pytest.mark.django_db
def test_sync_meta_hierarchy_persists_campaign_adset_ad(monkeypatch, user):
    _seed_meta_credential(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_campaigns(self, *, account_id: str, user_access_token: str):
            assert account_id == "act_123"
            return [
                {
                    "id": "cmp-1",
                    "account_id": "123",
                    "name": "Campaign 1",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                    "objective": "LINK_CLICKS",
                    "created_time": "2026-01-01T00:00:00+00:00",
                    "updated_time": "2026-01-02T00:00:00+00:00",
                }
            ]

        def list_adsets(self, *, account_id: str, user_access_token: str):
            return [
                {
                    "id": "adset-1",
                    "campaign_id": "cmp-1",
                    "name": "AdSet 1",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                    "daily_budget": "1200",
                    "targeting": {"geo_locations": {"countries": ["JM"]}},
                }
            ]

        def list_ads(self, *, account_id: str, user_access_token: str):
            return [
                {
                    "id": "ad-1",
                    "campaign_id": "cmp-1",
                    "adset_id": "adset-1",
                    "name": "Ad 1",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                    "creative": {"id": "creative-1", "thumbnail_url": "https://example.com/thumb.jpg"},
                }
            ]

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())
    result = sync_meta_hierarchy.run()
    assert result["processed"] == 1
    assert result["campaigns_synced"] == 1
    assert result["adsets_synced"] == 1
    assert result["ads_synced"] == 1

    campaign = Campaign.objects.get(tenant=user.tenant, external_id="cmp-1")
    adset = AdSet.objects.get(tenant=user.tenant, external_id="adset-1")
    ad = Ad.objects.get(tenant=user.tenant, external_id="ad-1")
    assert campaign.platform == "meta"
    assert adset.campaign_id == campaign.id
    assert ad.adset_id == adset.id


@pytest.mark.django_db
def test_sync_meta_insights_incremental_persists_metrics(monkeypatch, user):
    _seed_meta_credential(user)
    account = AdAccount.objects.create(
        tenant=user.tenant,
        external_id="act_123",
        account_id="123",
        currency="USD",
    )
    campaign = Campaign.objects.create(
        tenant=user.tenant,
        ad_account=account,
        external_id="cmp-1",
        name="Campaign 1",
        platform="meta",
        account_external_id="act_123",
        status="ACTIVE",
    )
    adset = AdSet.objects.create(
        tenant=user.tenant,
        campaign=campaign,
        external_id="adset-1",
        name="AdSet 1",
        status="ACTIVE",
    )
    Ad.objects.create(
        tenant=user.tenant,
        adset=adset,
        external_id="ad-1",
        name="Ad 1",
        status="ACTIVE",
    )

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_insights(
            self,
            *,
            account_id: str,
            user_access_token: str,
            level: str,
            since: str,
            until: str,
        ):
            assert level == "ad"
            assert since == "2026-01-01"
            assert until == "2026-01-31"
            return [
                {
                    "date_start": "2026-01-30",
                    "account_id": "123",
                    "campaign_id": "cmp-1",
                    "adset_id": "adset-1",
                    "ad_id": "ad-1",
                    "impressions": "1000",
                    "reach": "920",
                    "clicks": "35",
                    "spend": "17.5",
                    "cpc": "0.5",
                    "cpm": "17.5",
                    "actions": [{"action_type": "purchase", "value": "3"}],
                }
            ]

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())
    result = sync_meta_insights_incremental.run(level="ad", since="2026-01-01", until="2026-01-31")
    assert result["processed"] == 1
    assert result["insights_synced"] == 1
    insight = RawPerformanceRecord.objects.get(
        tenant=user.tenant,
        external_id="ad-1",
        source="meta",
        level="ad",
    )
    assert insight.reach == 920
    assert insight.spend == Decimal("17.5")
    assert insight.cpc == Decimal("0.5")
    assert insight.cpm == Decimal("17.5")
    assert insight.conversions == 3


@pytest.mark.django_db
def test_sync_meta_accounts_logs_api_error(monkeypatch, user):
    _seed_meta_credential(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def list_ad_accounts(self, *, user_access_token: str):
            raise MetaGraphClientError(
                "Rate limit",
                status_code=429,
                error_code=4,
                retryable=True,
                payload={"error": {"message": "Rate limit"}},
            )

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())
    result = sync_meta_accounts.run()
    assert result["failed"] == 1
    log = APIErrorLog.objects.get(tenant=user.tenant, provider=PlatformCredential.META)
    assert log.status_code == 429
    assert log.is_retryable is True
