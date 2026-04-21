"""Sprint 5: Meta analytics endpoints accept ``client_id``.

When ``client_id`` is passed, Meta-only read endpoints scope the query to the
Client's Meta ad account external_ids, surface a ``client_resolution`` body,
and set the ``X-Adinsights-Resolved-Via`` header.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import Tenant
from analytics.models import AdAccount, Campaign, RawPerformanceRecord
from integrations.models import Client as IntegrationsClient, ClientPlatformAccount


def _auth(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.username, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _seed_two_meta_accounts(tenant):
    a = AdAccount.objects.create(
        tenant=tenant, external_id="act_111", account_id="111", name="Alpha"
    )
    b = AdAccount.objects.create(
        tenant=tenant, external_id="act_222", account_id="222", name="Beta"
    )
    c = AdAccount.objects.create(
        tenant=tenant, external_id="act_999", account_id="999", name="Unrelated"
    )
    return a, b, c


@pytest.mark.django_db
def test_meta_accounts_scoped_to_client(api_client, user):
    _auth(api_client, user)
    a, b, _c = _seed_two_meta_accounts(user.tenant)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    # Link act_111 and bare 222 — variants matter.
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_111",
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="222",
    )

    r = api_client.get(reverse("meta-accounts"), {"client_id": str(client.id)})
    assert r.status_code == 200
    body = r.json()
    ext_ids = sorted(row["external_id"] for row in body["results"])
    assert ext_ids == sorted([a.external_id, b.external_id])
    # Unrelated account 999 must be excluded.
    assert "act_999" not in ext_ids
    meta = body["client_resolution"]
    assert meta["client_id"] == str(client.id)
    assert meta["reason"] is None
    assert r["X-Adinsights-Resolved-Via"] == f"client:{client.id}"


@pytest.mark.django_db
def test_meta_accounts_empty_when_no_meta_accounts_for_client(api_client, user):
    _auth(api_client, user)
    _seed_two_meta_accounts(user.tenant)

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="NoMeta", slug="nometa"
    )

    r = api_client.get(reverse("meta-accounts"), {"client_id": str(client.id)})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["client_resolution"]["reason"] == "no_meta_accounts_for_client"


@pytest.mark.django_db
def test_meta_accounts_client_not_found(api_client, user):
    _auth(api_client, user)
    _seed_two_meta_accounts(user.tenant)

    bogus = "00000000-0000-0000-0000-000000000000"
    r = api_client.get(reverse("meta-accounts"), {"client_id": bogus})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["client_resolution"]["reason"] == "client_not_found"


@pytest.mark.django_db
def test_meta_accounts_tenant_isolation(api_client, user):
    """A client owned by another tenant is invisible."""

    _auth(api_client, user)
    _seed_two_meta_accounts(user.tenant)

    other = Tenant.objects.create(name="Other")
    other_client = IntegrationsClient.all_objects.create(
        tenant=other, name="OtherCo", slug="otherco"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=other, client=other_client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_111",
    )

    r = api_client.get(reverse("meta-accounts"), {"client_id": str(other_client.id)})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["client_resolution"]["reason"] == "client_not_found"


@pytest.mark.django_db
def test_meta_campaigns_scoped_to_client(api_client, user):
    _auth(api_client, user)
    a, b, c = _seed_two_meta_accounts(user.tenant)
    for account, ext in [(a, "cmp-a"), (b, "cmp-b"), (c, "cmp-unrelated")]:
        Campaign.objects.create(
            tenant=user.tenant, ad_account=account, external_id=ext,
            name=f"C-{ext}", platform="meta",
            account_external_id=account.external_id, status="ACTIVE",
        )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_111",
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_222",
    )

    r = api_client.get(reverse("meta-campaigns"), {"client_id": str(client.id)})
    assert r.status_code == 200
    ext_ids = sorted(row["external_id"] for row in r.json()["results"])
    assert ext_ids == ["cmp-a", "cmp-b"]


@pytest.mark.django_db
def test_meta_insights_scoped_to_client(api_client, user):
    _auth(api_client, user)
    a, b, c = _seed_two_meta_accounts(user.tenant)
    for account in (a, b, c):
        RawPerformanceRecord.objects.create(
            tenant=user.tenant, ad_account=account,
            external_id=f"ins-{account.account_id}",
            date=date(2026, 2, 20), source="meta", level="account",
            impressions=100, clicks=10, spend=Decimal("5.00"), currency="USD",
        )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_111",
    )

    r = api_client.get(reverse("meta-insights"), {"client_id": str(client.id)})
    assert r.status_code == 200
    body = r.json()
    results = body["results"]
    assert len(results) == 1
    assert results[0]["external_id"] == "ins-111"
    assert body["client_resolution"]["client_id"] == str(client.id)


@pytest.mark.django_db
def test_meta_insights_client_plus_account_intersection(api_client, user):
    """client_id + account_id: intersection wins; both inside → one row."""

    _auth(api_client, user)
    a, b, _c = _seed_two_meta_accounts(user.tenant)
    for account in (a, b):
        RawPerformanceRecord.objects.create(
            tenant=user.tenant, ad_account=account,
            external_id=f"ins-{account.account_id}",
            date=date(2026, 2, 20), source="meta", level="account",
            impressions=100, clicks=10, spend=Decimal("5.00"), currency="USD",
        )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    for ext in ("act_111", "act_222"):
        ClientPlatformAccount.all_objects.create(
            tenant=user.tenant, client=client,
            platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id=ext,
        )

    r = api_client.get(
        reverse("meta-insights"),
        {"client_id": str(client.id), "account_id": "111"},
    )
    assert r.status_code == 200
    body = r.json()
    assert [row["external_id"] for row in body["results"]] == ["ins-111"]
    assert body["client_resolution"]["reason"] == "client_plus_account"


@pytest.mark.django_db
def test_meta_insights_account_not_in_client(api_client, user):
    """client_id + account_id not part of client → empty + reason."""

    _auth(api_client, user)
    a, _b, _c = _seed_two_meta_accounts(user.tenant)
    RawPerformanceRecord.objects.create(
        tenant=user.tenant, ad_account=a, external_id="ins-111",
        date=date(2026, 2, 20), source="meta", level="account",
        impressions=100, clicks=10, spend=Decimal("5.00"), currency="USD",
    )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    ClientPlatformAccount.all_objects.create(
        tenant=user.tenant, client=client,
        platform=ClientPlatformAccount.PLATFORM_META_ADS, external_id="act_111",
    )

    r = api_client.get(
        reverse("meta-insights"),
        {"client_id": str(client.id), "account_id": "999"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["client_resolution"]["reason"] == "account_not_in_client"


@pytest.mark.django_db
def test_meta_pages_scoped_to_client(api_client, user):
    """MetaPagesInsightsListView accepts client_id and filters by meta_page links."""

    from integrations.models import MetaPage

    _auth(api_client, user)
    MetaPage.objects.create(
        tenant=user.tenant, page_id="p-111", name="Page A", can_analyze=True,
    )
    MetaPage.objects.create(
        tenant=user.tenant, page_id="p-222", name="Page B", can_analyze=True,
    )
    MetaPage.objects.create(
        tenant=user.tenant, page_id="p-999", name="Unrelated", can_analyze=True,
    )

    client = IntegrationsClient.all_objects.create(
        tenant=user.tenant, name="JDIC", slug="jdic"
    )
    for ext in ("p-111", "p-222"):
        ClientPlatformAccount.all_objects.create(
            tenant=user.tenant, client=client,
            platform=ClientPlatformAccount.PLATFORM_META_PAGE, external_id=ext,
        )

    r = api_client.get("/api/meta/pages/", {"client_id": str(client.id)})
    assert r.status_code == 200
    body = r.json()
    page_ids = sorted(row["page_id"] for row in body["results"])
    assert page_ids == ["p-111", "p-222"]
    assert body["client_resolution"]["client_id"] == str(client.id)
    assert body["client_resolution"]["reason"] is None
    assert r["X-Adinsights-Resolved-Via"] == f"client:{client.id}"


@pytest.mark.django_db
def test_meta_insights_no_client_legacy_behavior(api_client, user):
    """Without client_id, legacy account_id behavior is untouched."""

    _auth(api_client, user)
    a, _b, _c = _seed_two_meta_accounts(user.tenant)
    RawPerformanceRecord.objects.create(
        tenant=user.tenant, ad_account=a, external_id="ins-111",
        date=date(2026, 2, 20), source="meta", level="account",
        impressions=100, clicks=10, spend=Decimal("5.00"), currency="USD",
    )

    r = api_client.get(reverse("meta-insights"), {"account_id": "111"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 1
    assert "client_resolution" not in body
    assert "X-Adinsights-Resolved-Via" not in r
