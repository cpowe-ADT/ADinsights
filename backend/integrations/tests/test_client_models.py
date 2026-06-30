"""Sprint 1 coverage: Client + ClientPlatformAccount data model."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from integrations.models import Client, ClientPlatformAccount


@pytest.fixture
def other_tenant(db) -> Tenant:
    return Tenant.objects.create(name="Other Tenant")


class TestClientModel:
    def test_create_client_requires_tenant(self, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        assert client.pk is not None
        assert client.is_active is True
        assert client.metadata == {}

    def test_slug_unique_per_tenant(self, tenant, other_tenant):
        Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        # Same slug in another tenant is fine.
        Client.all_objects.create(tenant=other_tenant, name="JDIC", slug="jdic")
        # Same slug in same tenant is a violation.
        with pytest.raises(IntegrityError), transaction.atomic():
            Client.all_objects.create(tenant=tenant, name="Dup", slug="jdic")

    def test_tenant_isolation_via_manager(self, tenant, other_tenant):
        Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        Client.all_objects.create(tenant=other_tenant, name="BOJ", slug="boj")

        with tenant_context(str(tenant.id)):
            names = sorted(Client.objects.values_list("name", flat=True))
        assert names == ["JDIC"]

        with tenant_context(str(other_tenant.id)):
            names = sorted(Client.objects.values_list("name", flat=True))
        assert names == ["BOJ"]


class TestClientPlatformAccount:
    def test_attach_google_account(self, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        cpa = ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
            display_name="JDIC — Google",
            is_primary=True,
        )
        assert cpa.pk is not None
        assert client.platform_accounts.count() == 1

    def test_unique_per_platform_external_id_per_tenant(self, tenant):
        a = Client.all_objects.create(tenant=tenant, name="A", slug="a")
        b = Client.all_objects.create(tenant=tenant, name="B", slug="b")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=a,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            ClientPlatformAccount.all_objects.create(
                tenant=tenant,
                client=b,
                platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
                external_id="5211685017",
            )

    def test_same_external_id_allowed_across_platforms(self, tenant):
        """An external_id is only unique within a platform — Meta act_1234567 and
        Google customer 1234567 can coexist (different namespaces)."""
        client = Client.all_objects.create(tenant=tenant, name="C", slug="c")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="1234567",
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_META_ADS,
            external_id="1234567",
        )
        assert client.platform_accounts.count() == 2

    def test_same_external_id_allowed_across_tenants(self, tenant, other_tenant):
        a = Client.all_objects.create(tenant=tenant, name="A", slug="a")
        b = Client.all_objects.create(tenant=other_tenant, name="B", slug="b")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=a,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        # Different tenant — should not collide.
        ClientPlatformAccount.all_objects.create(
            tenant=other_tenant,
            client=b,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        assert ClientPlatformAccount.all_objects.count() == 2

    def test_cascade_delete_removes_platform_accounts(self, tenant):
        client = Client.all_objects.create(tenant=tenant, name="C", slug="c")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_META_ADS,
            external_id="act_123",
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_META_PAGE,
            external_id="page_123",
        )
        assert ClientPlatformAccount.all_objects.count() == 2
        client.delete()
        assert ClientPlatformAccount.all_objects.count() == 0

    def test_platform_account_tenant_isolation(self, tenant, other_tenant):
        t1_client = Client.all_objects.create(tenant=tenant, name="T1", slug="t1")
        t2_client = Client.all_objects.create(tenant=other_tenant, name="T2", slug="t2")
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=t1_client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="1111",
        )
        ClientPlatformAccount.all_objects.create(
            tenant=other_tenant,
            client=t2_client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="2222",
        )

        with tenant_context(str(tenant.id)):
            ids = sorted(
                ClientPlatformAccount.objects.values_list("external_id", flat=True)
            )
        assert ids == ["1111"]

        with tenant_context(str(other_tenant.id)):
            ids = sorted(
                ClientPlatformAccount.objects.values_list("external_id", flat=True)
            )
        assert ids == ["2222"]
