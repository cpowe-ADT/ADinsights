"""Sprint 2 coverage: name-match suggester."""

from __future__ import annotations

import pytest

from accounts.models import Tenant
from analytics.models import AdAccount
from integrations.clients import (
    ClientSuggestion,
    normalize_name,
    suggest_clients,
)
from integrations.models import (
    Client,
    ClientPlatformAccount,
    GoogleAdsAccountMapping,
    MetaPage,
)


@pytest.fixture
def other_tenant(db) -> Tenant:
    return Tenant.objects.create(name="Other")


class TestNormalizeName:
    def test_strips_legal_suffixes(self):
        assert normalize_name("Bank of Jamaica Limited") == "bank of jamaica"
        assert normalize_name("Bank of Jamaica Ltd.") == "bank of jamaica"
        assert normalize_name("Bank of Jamaica Inc") == "bank of jamaica"

    def test_lowercases_and_strips_punctuation(self):
        assert normalize_name("JDIC — Jamaica Deposit!") == "jdic jamaica deposit"

    def test_drops_parentheticals(self):
        assert normalize_name("Grace Kennedy (Jamaica)") == "grace kennedy"

    def test_empty_and_none(self):
        assert normalize_name(None) == ""
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""


class TestSuggesterCrossPlatformGrouping:
    def test_matches_google_and_meta_by_name(self, tenant):
        """BOJ on Google + BOJ on Meta should group together."""

        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="8406755766",
            customer_name="Bank of Jamaica Limited",
            is_manager=False,
        )
        AdAccount.all_objects.create(
            tenant=tenant, external_id="act_100", name="Bank of Jamaica"
        )
        MetaPage.all_objects.create(
            tenant=tenant,
            page_id="page_100",
            name="Bank of Jamaica Official",
            page_token_enc=b"",
            page_token_nonce=b"",
            page_token_tag=b"",
        )

        suggestions = suggest_clients(str(tenant.id))
        # Expect one group containing all three.
        assert len(suggestions) == 1
        s = suggestions[0]
        assert isinstance(s, ClientSuggestion)
        assert s.confidence >= 0.7
        platforms = {a.platform for a in s.unclaimed_accounts}
        assert platforms == {"google_ads", "meta_ads", "meta_page"}
        assert s.existing_client_id is None  # no existing client yet

    def test_matches_against_existing_client_name(self, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="5211685017",
            customer_name="JDIC Jamaica Deposit Insurance",
            is_manager=False,
        )
        suggestions = suggest_clients(str(tenant.id))
        matching = [s for s in suggestions if s.existing_client_id == str(client.id)]
        assert matching, "Expected one suggestion to match existing JDIC client"
        assert matching[0].confidence >= 0.7

    def test_excludes_already_linked_accounts(self, tenant):
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="5211685017",
            customer_name="JDIC",
            is_manager=False,
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="5211685017",
        )
        # With only a linked account and no unlinked ones, the suggester has
        # nothing to propose.
        suggestions = suggest_clients(str(tenant.id))
        assert suggestions == []

    def test_excludes_manager_accounts(self, tenant):
        """MCC accounts don't hold metric data — don't suggest grouping them."""

        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="9999",
            customer_name="Grace Kennedy MCC",
            is_manager=True,
        )
        suggestions = suggest_clients(str(tenant.id))
        assert suggestions == []

    def test_low_similarity_not_grouped(self, tenant):
        """Totally unrelated names should not be merged."""

        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="1111",
            customer_name="Bank of Jamaica",
            is_manager=False,
        )
        AdAccount.all_objects.create(
            tenant=tenant, external_id="act_200", name="Sandals Resorts"
        )
        suggestions = suggest_clients(str(tenant.id))
        # No cross-platform signal, no multi-account group — suggester returns empty.
        for s in suggestions:
            platforms = {a.platform for a in s.unclaimed_accounts}
            assert platforms != {"google_ads", "meta_ads"}

    def test_tenant_isolation(self, tenant, other_tenant):
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="1111",
            customer_name="Bank of Jamaica",
            is_manager=False,
        )
        AdAccount.all_objects.create(
            tenant=tenant, external_id="act_1", name="Bank of Jamaica"
        )
        # Other tenant has a matching name — should not cross-pollinate.
        GoogleAdsAccountMapping.all_objects.create(
            tenant=other_tenant,
            customer_id="2222",
            customer_name="Bank of Jamaica",
            is_manager=False,
        )

        t1 = suggest_clients(str(tenant.id))
        t2 = suggest_clients(str(other_tenant.id))

        t1_ids = {a.external_id for s in t1 for a in s.unclaimed_accounts}
        t2_ids = {a.external_id for s in t2 for a in s.unclaimed_accounts}
        assert "2222" not in t1_ids
        assert "1111" not in t2_ids


class TestSuggesterPerformance:
    """Fast sanity check that the O(N²) implementation is fine at realistic scale."""

    def test_500_accounts_completes_quickly(self, tenant):
        import time

        for i in range(250):
            GoogleAdsAccountMapping.all_objects.create(
                tenant=tenant,
                customer_id=f"cust_{i}",
                customer_name=f"Client {i} Limited",
                is_manager=False,
            )
        for i in range(250):
            AdAccount.all_objects.create(
                tenant=tenant, external_id=f"act_{i}", name=f"Client {i}"
            )

        start = time.perf_counter()
        suggest_clients(str(tenant.id))
        elapsed = time.perf_counter() - start
        # Generous budget — in-mem SQLite is the bottleneck, not the algorithm.
        assert elapsed < 5.0, f"Suggester took {elapsed:.2f}s for 500 accounts"
