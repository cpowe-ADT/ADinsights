from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from integrations.google_ads.client import GoogleAdsSdkClient, GoogleAdsSdkError
from integrations.models import PlatformCredential

pytestmark = pytest.mark.django_db


def _make_credential(tenant) -> PlatformCredential:
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("access", "refresh")
    credential.save()
    return credential


def test_google_ads_sdk_client_fetch_campaign_daily(monkeypatch, tenant, settings):
    settings.GOOGLE_ADS_CLIENT_ID = "client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "client-secret"
    settings.GOOGLE_ADS_DEVELOPER_TOKEN = "dev-token"
    credential = _make_credential(tenant)

    row = SimpleNamespace(
        customer=SimpleNamespace(id="1234567890", currency_code="USD"),
        campaign=SimpleNamespace(id="111", name="Campaign 1"),
        segments=SimpleNamespace(date="2026-02-20"),
        metrics=SimpleNamespace(
            impressions=100,
            clicks=10,
            conversions=Decimal("2"),
            conversions_value=Decimal("9"),
            cost_micros=1200000,
        ),
    )
    batch = SimpleNamespace(request_id="req-1", results=[row])

    class FakeService:
        def search_stream(self, **kwargs):  # noqa: ANN003
            return [batch]

    class FakeGoogleAdsClient:
        def get_service(self, name):  # noqa: ANN001
            assert name == "GoogleAdsService"
            return FakeService()

        @classmethod
        def load_from_dict(cls, config):  # noqa: ANN001
            assert config["developer_token"] == "dev-token"
            return cls()

    monkeypatch.setattr(
        "integrations.google_ads.client._import_google_ads_symbols",
        lambda: (FakeGoogleAdsClient, Exception),
    )
    client = GoogleAdsSdkClient(credential=credential, login_customer_id="1234567890")
    rows = client.fetch_campaign_daily(
        customer_id="1234567890",
        start_date=date(2026, 2, 20),
        end_date=date(2026, 2, 20),
    )
    assert len(rows) == 1
    assert rows[0].campaign_id == "111"
    assert rows[0].cost_micros == 1200000


def test_google_ads_sdk_client_raises_when_refresh_token_missing(tenant, settings):
    settings.GOOGLE_ADS_CLIENT_ID = "client-id"
    settings.GOOGLE_ADS_CLIENT_SECRET = "client-secret"
    settings.GOOGLE_ADS_DEVELOPER_TOKEN = "dev-token"
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.GOOGLE,
        account_id="1234567890",
    )
    credential.set_raw_tokens("access", None)
    credential.save()

    with pytest.raises(GoogleAdsSdkError):
        GoogleAdsSdkClient(credential=credential)
