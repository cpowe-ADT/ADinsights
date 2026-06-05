"""Sprint 6: Combined metrics endpoint accepts ``client_id``.

The combined view scopes the meta_direct adapter to the Client's linked
Meta ad accounts, honours ``platforms=`` toggles to enable/disable each
configured platform, and surfaces a ``client_resolution`` body plus the
``X-Adinsights-Resolved-Via`` header.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from adapters.meta_direct import MetaDirectAdapter
from analytics.models import (
    Ad,
    AdAccount,
    AdSet,
    Campaign,
    DailyFxRate,
    RawPerformanceRecord,
)
from analytics.fx import convert, load_rate_table, resolve_rate
from analytics.platform_registry import (
    COMBINED_SUPPORTED,
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PlatformRegistry,
    parse_enabled_param,
)
from integrations.models import (
    Client as IntegrationsClient,
    ClientPlatformAccount,
)


@pytest.fixture
def enable_meta_direct_adapter(settings):
    settings.ENABLE_META_DIRECT_ADAPTER = True
    settings.ENABLE_FAKE_ADAPTER = False
    settings.ENABLE_DEMO_ADAPTER = False


def _seed_ad_account(
    tenant,
    *,
    external_id: str,
    name: str,
) -> AdAccount:
    account = AdAccount.objects.create(
        tenant=tenant,
        external_id=external_id,
        account_id=external_id.replace("act_", ""),
        name=name,
        currency="USD",
        status="ACTIVE",
    )
    campaign = Campaign.objects.create(
        tenant=tenant,
        ad_account=account,
        external_id=f"cmp-{external_id}",
        name=f"Campaign {name}",
        platform="meta",
        account_external_id=external_id,
        status="ACTIVE",
        objective="OUTCOME_AWARENESS",
        currency="USD",
    )
    adset = AdSet.objects.create(
        tenant=tenant,
        campaign=campaign,
        external_id=f"adset-{external_id}",
        name=f"Ad set {name}",
        status="ACTIVE",
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        daily_budget=100,
    )
    ad = Ad.objects.create(
        tenant=tenant,
        adset=adset,
        external_id=f"ad-{external_id}",
        name=f"Creative {name}",
        status="ACTIVE",
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        adset=adset,
        ad=ad,
        external_id=ad.external_id,
        source="meta",
        level="ad",
        date=date(2026, 4, 3),
        impressions=1000,
        reach=800,
        clicks=50,
        spend=Decimal("75"),
        cpc=Decimal("1.5"),
        cpm=Decimal("75"),
        conversions=6,
        currency="USD",
    )
    return account


@pytest.mark.django_db
def test_combined_client_id_scopes_meta_direct_to_linked_accounts(
    api_client, user, enable_meta_direct_adapter
):
    """Combined view with client_id filters meta_direct to only linked accounts."""

    api_client.force_authenticate(user=user)
    a = _seed_ad_account(user.tenant, external_id="act_111", name="Alpha")
    _b = _seed_ad_account(user.tenant, external_id="act_222", name="Beta")
    _other = _seed_ad_account(user.tenant, external_id="act_999", name="Unrelated")

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    # Link Alpha only — Beta and the unrelated account must not contribute.
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS,
        external_id=a.external_id,
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "client_id": str(client.id),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Only Alpha's 75 spend should be present (Beta 75, Unrelated 75 excluded).
    assert payload["campaign"]["summary"]["totalSpend"] == pytest.approx(75.0)

    meta = payload["client_resolution"]
    assert meta["client_id"] == str(client.id)
    assert meta["reason"] is None
    assert meta["meta_ad_account_ids"] == ["act_111"]
    assert response["X-Adinsights-Resolved-Via"] == f"client:{client.id}"
    # Platform registry — Meta is configured + enabled; Google not configured.
    platforms = meta["platforms"]
    assert PLATFORM_META_ADS in platforms["configured"]
    assert PLATFORM_META_ADS in platforms["enabled"]
    assert PLATFORM_GOOGLE_ADS not in platforms["configured"]


@pytest.mark.django_db
def test_combined_client_id_unknown_returns_empty_payload(
    api_client, user, enable_meta_direct_adapter
):
    api_client.force_authenticate(user=user)
    _seed_ad_account(user.tenant, external_id="act_111", name="Alpha")

    bogus = "00000000-0000-0000-0000-000000000000"
    response = api_client.get(
        "/api/metrics/combined/",
        {"source": MetaDirectAdapter.key, "client_id": bogus},
    )
    assert response.status_code == 200
    payload = response.json()
    # Unknown client → empty meta_direct payload, client_not_found reason.
    assert payload["campaign"]["summary"]["totalSpend"] == 0
    assert payload["client_resolution"]["reason"] == "client_not_found"
    assert response["X-Adinsights-Resolved-Via"] == f"client:{bogus}"


@pytest.mark.django_db
def test_combined_client_id_platform_toggle_disables_meta(
    api_client, user, enable_meta_direct_adapter
):
    """platforms=google_ads filters out Meta contributions even if client has them."""

    api_client.force_authenticate(user=user)
    a = _seed_ad_account(user.tenant, external_id="act_111", name="Alpha")

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant,
        client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS,
        external_id=a.external_id,
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "client_id": str(client.id),
            "platforms": "google_ads",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    meta = payload["client_resolution"]
    # Meta is configured but NOT enabled (caller asked for google_ads only),
    # and google_ads isn't configured, so no platforms are enabled.
    assert PLATFORM_META_ADS in meta["platforms"]["configured"]
    assert PLATFORM_META_ADS not in meta["platforms"]["enabled"]
    assert meta["reason"] in {"no_enabled_platforms", "all_platforms_disabled"}
    # Empty totals since meta contribution was toggled off.
    assert payload["campaign"]["summary"]["totalSpend"] == 0


@pytest.mark.django_db
def test_combined_client_id_tenant_isolation(
    api_client, user, enable_meta_direct_adapter
):
    """A client owned by another tenant is invisible."""

    from accounts.models import Tenant

    api_client.force_authenticate(user=user)
    _seed_ad_account(user.tenant, external_id="act_111", name="Alpha")

    other = Tenant.objects.create(name="OtherCo")
    other_client = IntegrationsClient.all_objects.create(
        tenant=other, name="Competitor", slug="competitor"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=other,
        client=other_client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS,
        external_id="act_111",
    )

    response = api_client.get(
        "/api/metrics/combined/",
        {
            "source": MetaDirectAdapter.key,
            "client_id": str(other_client.id),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["client_resolution"]["reason"] == "client_not_found"


@pytest.mark.django_db
def test_combined_no_client_id_preserves_legacy_behavior(
    api_client, user, enable_meta_direct_adapter
):
    """Without client_id, legacy account_id / no-filter behavior is untouched."""

    api_client.force_authenticate(user=user)
    _seed_ad_account(user.tenant, external_id="act_111", name="Alpha")

    response = api_client.get(
        "/api/metrics/combined/",
        {"source": MetaDirectAdapter.key, "account_id": "act_111"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "client_resolution" not in payload
    assert "X-Adinsights-Resolved-Via" not in response


# -- Platform registry unit tests --------------------------------------------


def test_platform_registry_parses_enabled_param():
    assert parse_enabled_param(None) is None
    assert parse_enabled_param("") == []
    assert parse_enabled_param("meta_ads,google_ads") == [
        PLATFORM_META_ADS,
        PLATFORM_GOOGLE_ADS,
    ]
    # Unknown platforms dropped silently.
    assert parse_enabled_param("meta_ads,bogus") == [PLATFORM_META_ADS]
    # Duplicate entries deduped.
    assert parse_enabled_param("meta_ads,meta_ads") == [PLATFORM_META_ADS]


def test_platform_registry_default_enables_configured_supported_only():
    # Configured Meta + GA4 (GA4 is NOT combined_supported yet).
    reg = PlatformRegistry.from_configured([PLATFORM_META_ADS, "google_analytics_4"])
    assert reg.is_enabled(PLATFORM_META_ADS) is True
    assert reg.is_enabled("google_analytics_4") is False
    assert PLATFORM_META_ADS in reg.enabled_platforms
    assert reg.enabled_platforms.issubset(COMBINED_SUPPORTED)


def test_platform_registry_override_intersects_with_configured():
    reg = PlatformRegistry.from_configured(
        [PLATFORM_META_ADS],
        enabled=[PLATFORM_META_ADS, PLATFORM_GOOGLE_ADS],
    )
    # Google Ads was asked for but isn't configured — must not appear.
    assert reg.enabled_platforms == frozenset({PLATFORM_META_ADS})


# -- FX conversion unit tests ------------------------------------------------


@pytest.mark.django_db
def test_fx_convert_same_currency_returns_amount():
    result = convert(
        Decimal("100.00"),
        from_currency="USD",
        to_currency="USD",
        on_date=date(2026, 4, 10),
    )
    assert result == Decimal("100").quantize(Decimal("0.00000001"))


@pytest.mark.django_db
def test_fx_convert_direct_rate():
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 10),
        base_currency="USD",
        quote_currency="JMD",
        rate=Decimal("155.50000000"),
    )
    result = convert(
        Decimal("100"),
        from_currency="USD",
        to_currency="JMD",
        on_date=date(2026, 4, 10),
    )
    assert result == Decimal("15550.00000000")


@pytest.mark.django_db
def test_fx_convert_inverse_rate_when_direct_missing():
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 10),
        base_currency="USD",
        quote_currency="JMD",
        rate=Decimal("155.00000000"),
    )
    # Requesting JMD→USD with no direct row → flip the USD→JMD rate.
    result = convert(
        Decimal("15500"),
        from_currency="JMD",
        to_currency="USD",
        on_date=date(2026, 4, 10),
    )
    assert result is not None
    assert result == pytest.approx(Decimal("100"), rel=Decimal("0.001"))


@pytest.mark.django_db
def test_fx_convert_uses_most_recent_on_or_before_date():
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 5),
        base_currency="USD",
        quote_currency="JMD",
        rate=Decimal("150.0"),
    )
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 8),
        base_currency="USD",
        quote_currency="JMD",
        rate=Decimal("155.0"),
    )
    # Request on 2026-04-09 → should use the 2026-04-08 rate.
    lookup = resolve_rate(
        on_date=date(2026, 4, 9),
        base_currency="USD",
        quote_currency="JMD",
    )
    assert lookup is not None
    assert lookup.rate == Decimal("155.0")
    assert lookup.used_date == date(2026, 4, 8)


@pytest.mark.django_db
def test_fx_convert_missing_rate_returns_none():
    result = convert(
        Decimal("100"),
        from_currency="USD",
        to_currency="JMD",
        on_date=date(2026, 4, 10),
    )
    assert result is None


@pytest.mark.django_db
def test_fx_load_rate_table_batches_pairs():
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 1),
        base_currency="JMD",
        quote_currency="USD",
        rate=Decimal("0.0065"),
    )
    DailyFxRate.objects.create(
        rate_date=date(2026, 4, 2),
        base_currency="JMD",
        quote_currency="USD",
        rate=Decimal("0.0066"),
    )

    table = load_rate_table(
        currencies=["JMD"],
        target="USD",
        dates=[date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)],
    )
    assert table[(date(2026, 4, 1), "JMD")] == Decimal("0.00650000")
    assert table[(date(2026, 4, 2), "JMD")] == Decimal("0.00660000")
    # 2026-04-03 falls back to the 2026-04-02 rate.
    assert table[(date(2026, 4, 3), "JMD")] == Decimal("0.00660000")
