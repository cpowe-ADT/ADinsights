"""Sprint 2 coverage: resolver service."""

from __future__ import annotations

import pytest

from accounts.models import Tenant
from integrations.clients import (
    ClientAccountBundle,
    resolve_client_accounts,
    resolve_client_for_external,
)
from integrations.models import (
    Client,
    ClientPlatformAccount,
    GoogleAdsAccountMapping,
)


@pytest.fixture
def other_tenant(db) -> Tenant:
    return Tenant.objects.create(name="Other Tenant")


@pytest.fixture
def jdic(tenant) -> Client:
    return Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")


class TestResolverBasic:
    def test_empty_client_returns_empty_bundle(self, tenant, jdic):
        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        assert isinstance(bundle, ClientAccountBundle)
        assert bundle.is_empty()
        assert bundle.google_customer_ids == []
        assert bundle.meta_ad_account_ids == []

    def test_resolves_all_platforms_by_default(self, tenant, jdic):
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="5211685017",
            customer_name="JDIC",
            is_manager=False,
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_META_ADS,
            external_id="act_999",
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_META_PAGE,
            external_id="page_123",
        )

        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        assert bundle.google_customer_ids == ["5211685017"]
        assert bundle.meta_ad_account_ids == ["act_999"]
        assert bundle.meta_page_ids == ["page_123"]
        assert bundle.mcc_expansions == []

    def test_platform_filter_skips_unrequested_tables(self, tenant, jdic):
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant, customer_id="5211685017", is_manager=False
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_META_ADS,
            external_id="act_999",
        )

        bundle = resolve_client_accounts(
            str(tenant.id), str(jdic.id), platforms={"google_ads"}
        )
        assert bundle.google_customer_ids == ["5211685017"]
        assert bundle.meta_ad_account_ids == []

    def test_unknown_platform_raises(self, tenant, jdic):
        with pytest.raises(ValueError):
            resolve_client_accounts(
                str(tenant.id), str(jdic.id), platforms={"bogus"}
            )

    def test_cross_tenant_client_lookup_raises(self, tenant, other_tenant, jdic):
        with pytest.raises(Client.DoesNotExist):
            resolve_client_accounts(str(other_tenant.id), str(jdic.id))


class TestMCCExpansion:
    """Transparent MCC expansion: linking an MCC returns its non-manager children."""

    def test_mcc_link_expands_to_children(self, tenant, jdic):
        # Tenant has an MCC 9999 with 3 children and 1 manager descendant.
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant, customer_id="9999", is_manager=True
        )
        for child in ("1111", "2222", "3333"):
            GoogleAdsAccountMapping.all_objects.create(
                tenant=tenant,
                customer_id=child,
                manager_customer_id="9999",
                is_manager=False,
            )
        # A nested manager under 9999 should NOT be included in expansion.
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="4444",
            manager_customer_id="9999",
            is_manager=True,
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="9999",
        )

        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        # MCC itself is not usable for metric queries, so expansion replaces it
        # with the children rather than appending. Children sorted deterministically.
        assert sorted(bundle.google_customer_ids) == ["1111", "2222", "3333"]
        assert len(bundle.mcc_expansions) == 1
        assert bundle.mcc_expansions[0].manager_customer_id == "9999"
        assert bundle.mcc_expansions[0].child_customer_ids == ("1111", "2222", "3333")

    def test_leaf_link_does_not_expand(self, tenant, jdic):
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant, customer_id="1111", is_manager=False
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="1111",
        )
        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        assert bundle.google_customer_ids == ["1111"]
        assert bundle.mcc_expansions == []

    def test_mcc_plus_direct_leaf_deduplicates(self, tenant, jdic):
        """Linking both an MCC and one of its children should not double-count."""

        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant, customer_id="9999", is_manager=True
        )
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="1111",
            manager_customer_id="9999",
            is_manager=False,
        )
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="2222",
            manager_customer_id="9999",
            is_manager=False,
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="9999",
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="1111",
        )
        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        assert sorted(bundle.google_customer_ids) == ["1111", "2222"]

    def test_unknown_customer_id_is_treated_as_leaf(self, tenant, jdic):
        """If a customer_id was linked but sync hasn't populated mapping yet,
        we still return it so the query eventually lands."""

        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="7777",
        )
        bundle = resolve_client_accounts(str(tenant.id), str(jdic.id))
        assert bundle.google_customer_ids == ["7777"]
        assert bundle.mcc_expansions == []


class TestResolveClientForExternal:
    def test_returns_owning_client(self, tenant, jdic):
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=jdic,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        result = resolve_client_for_external(
            str(tenant.id), "google_ads", "5211685017"
        )
        assert result is not None
        assert str(result.id) == str(jdic.id)

    def test_returns_none_when_unlinked(self, tenant):
        result = resolve_client_for_external(
            str(tenant.id), "google_ads", "does-not-exist"
        )
        assert result is None

    def test_invalid_platform_raises(self, tenant):
        with pytest.raises(ValueError):
            resolve_client_for_external(str(tenant.id), "bogus", "123")
