"""Sprint 3 coverage: Client grouping REST API."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from analytics.models import AdAccount
from integrations.models import (
    Client,
    ClientPlatformAccount,
    GoogleAdsAccountMapping,
)


@pytest.fixture
def other_tenant(db) -> Tenant:
    return Tenant.objects.create(name="Other Tenant")


@pytest.fixture
def other_user(other_tenant) -> User:
    u = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
    )
    u.set_password("p")
    u.save()
    return u


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def auth_other(api_client, other_user) -> APIClient:
    api_client.force_authenticate(user=other_user)
    return api_client


class TestClientListCreate:
    def test_create_client_auto_slug(self, auth_client):
        r = auth_client.post(
            "/api/clients/",
            data={"name": "Jamaica Deposit Insurance Corp."},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["slug"] == "jamaica-deposit-insurance-corp"
        assert r.data["platform_counts"] == {}

    def test_create_explicit_slug(self, auth_client):
        r = auth_client.post(
            "/api/clients/", data={"name": "JDIC", "slug": "jdic"}, format="json"
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["slug"] == "jdic"

    def test_duplicate_slug_returns_409(self, auth_client, tenant):
        Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        r = auth_client.post(
            "/api/clients/", data={"name": "JDIC v2", "slug": "jdic"}, format="json"
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    def test_list_scoped_to_tenant(self, auth_client, tenant, other_tenant):
        Client.all_objects.create(tenant=tenant, name="Mine", slug="mine")
        Client.all_objects.create(tenant=other_tenant, name="Theirs", slug="theirs")
        r = auth_client.get("/api/clients/")
        assert r.status_code == 200
        names = [c["name"] for c in r.data["results"]]
        assert names == ["Mine"]


class TestClientDetailTenantIsolation:
    def test_cross_tenant_get_returns_404(self, auth_other, tenant):
        client = Client.all_objects.create(tenant=tenant, name="X", slug="x")
        r = auth_other.get(f"/api/clients/{client.id}/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_tenant_patch_returns_404(self, auth_other, tenant):
        client = Client.all_objects.create(tenant=tenant, name="X", slug="x")
        r = auth_other.patch(
            f"/api/clients/{client.id}/", data={"name": "hacked"}, format="json"
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_tenant_delete_returns_404(self, auth_other, tenant):
        client = Client.all_objects.create(tenant=tenant, name="X", slug="x")
        r = auth_other.delete(f"/api/clients/{client.id}/")
        assert r.status_code == status.HTTP_404_NOT_FOUND


class TestAttachAndDetach:
    def test_attach_account(self, auth_client, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        r = auth_client.post(
            f"/api/clients/{client.id}/accounts/",
            data={
                "platform": "google_ads",
                "external_id": "5211685017",
                "display_name": "JDIC — Google",
                "is_primary": True,
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["platform"] == "google_ads"
        assert r.data["external_id"] == "5211685017"

    def test_attach_already_claimed_returns_409(self, auth_client, tenant):
        a = Client.all_objects.create(tenant=tenant, name="A", slug="a")
        b = Client.all_objects.create(tenant=tenant, name="B", slug="b")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=a,
            platform="google_ads",
            external_id="111",
        )
        r = auth_client.post(
            f"/api/clients/{b.id}/accounts/",
            data={"platform": "google_ads", "external_id": "111"},
            format="json",
        )
        assert r.status_code == status.HTTP_409_CONFLICT
        assert r.data["claimed_by"]["client_id"] == str(a.id)

    def test_detach_removes_link(self, auth_client, tenant):
        client = Client.all_objects.create(tenant=tenant, name="C", slug="c")
        link = ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform="meta_ads",
            external_id="act_1",
        )
        r = auth_client.delete(
            f"/api/clients/{client.id}/accounts/{link.id}/"
        )
        assert r.status_code == status.HTTP_204_NO_CONTENT
        assert ClientPlatformAccount.all_objects.filter(id=link.id).count() == 0


class TestSuggestEndpoint:
    def test_suggest_returns_cross_platform_group(self, auth_client, tenant):
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="8406755766",
            customer_name="Bank of Jamaica Limited",
            is_manager=False,
        )
        AdAccount.all_objects.create(
            tenant=tenant, external_id="act_100", name="Bank of Jamaica"
        )
        r = auth_client.get("/api/clients/suggest/")
        assert r.status_code == 200
        assert r.data["threshold"] == 0.7
        assert len(r.data["results"]) >= 1
        first = r.data["results"][0]
        platforms = {a["platform"] for a in first["unclaimed_accounts"]}
        assert "google_ads" in platforms and "meta_ads" in platforms

    def test_suggest_bad_threshold(self, auth_client):
        r = auth_client.get("/api/clients/suggest/?threshold=2.0")
        assert r.status_code == status.HTTP_400_BAD_REQUEST


class TestSuggestApply:
    def test_apply_creates_client_and_attaches(self, auth_client, tenant):
        r = auth_client.post(
            "/api/clients/suggest/apply/",
            data={
                "create_name": "Bank of Jamaica",
                "accounts": [
                    {"platform": "google_ads", "external_id": "8406755766"},
                    {"platform": "meta_ads", "external_id": "act_100"},
                ],
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED, r.data
        assert r.data["client"]["name"] == "Bank of Jamaica"
        assert r.data["client"]["slug"] == "bank-of-jamaica"
        assert len(r.data["attached_accounts"]) == 2
        # Verify DB state
        assert Client.all_objects.filter(tenant=tenant, slug="bank-of-jamaica").exists()
        assert (
            ClientPlatformAccount.all_objects.filter(tenant=tenant).count() == 2
        )

    def test_apply_to_existing_client(self, auth_client, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        r = auth_client.post(
            "/api/clients/suggest/apply/",
            data={
                "client_id": str(client.id),
                "accounts": [
                    {"platform": "google_ads", "external_id": "5211685017"}
                ],
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert (
            ClientPlatformAccount.all_objects.filter(
                client=client, external_id="5211685017"
            ).count()
            == 1
        )

    def test_apply_atomic_when_one_account_conflicts(self, auth_client, tenant):
        """Pre-flight conflict must abort the whole apply — no partial attachment."""

        a = Client.all_objects.create(tenant=tenant, name="A", slug="a")
        # Claim the first account for tenant-A.
        ClientPlatformAccount.all_objects.create(
            tenant=tenant, client=a, platform="google_ads", external_id="111"
        )

        r = auth_client.post(
            "/api/clients/suggest/apply/",
            data={
                "create_name": "New Client",
                "accounts": [
                    {"platform": "google_ads", "external_id": "111"},  # conflict
                    {"platform": "meta_ads", "external_id": "act_222"},
                ],
            },
            format="json",
        )
        assert r.status_code == status.HTTP_409_CONFLICT
        # No new client should have been created.
        assert not Client.all_objects.filter(slug="new-client").exists()
        # No new link for the second account either.
        assert not ClientPlatformAccount.all_objects.filter(
            external_id="act_222"
        ).exists()

    def test_apply_requires_exactly_one_of_id_or_name(self, auth_client):
        r = auth_client.post(
            "/api/clients/suggest/apply/",
            data={"accounts": [{"platform": "google_ads", "external_id": "1"}]},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
