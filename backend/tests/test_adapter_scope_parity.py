"""Adapter scope parity tests (A3b).

Verifies that fake, demo, and upload adapters honour client_scope_requested
and the client_scoped_* account lists in the same way warehouse does:
  - empty scope lists → empty payload (zeros, empty rows)
  - non-empty meta list only → only meta-platform rows returned
  - non-empty google list only → only google-platform rows returned
  - no scoping at all → full payload (legacy behaviour preserved)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from adapters.fake import FakeAdapter, META_CHANNEL_ALIASES, GOOGLE_CHANNEL_ALIASES
from adapters.demo import DemoAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _campaign_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("campaign", {}).get("rows") or []


def _total_spend(payload: dict[str, Any]) -> float:
    return float(payload.get("campaign", {}).get("summary", {}).get("totalSpend", 0))


def _platforms_in_rows(rows: list[dict[str, Any]]) -> set[str]:
    return {(r.get("platform") or "").lower() for r in rows}


# ---------------------------------------------------------------------------
# FakeAdapter tests
# ---------------------------------------------------------------------------

class TestFakeAdapterScopeParity:
    def setup_method(self):
        self.adapter = FakeAdapter()
        self.tenant = "tenant-test"

    def test_no_scope_returns_full_payload(self):
        """Legacy behaviour: no options → full _PAYLOAD returned."""
        payload = self.adapter.fetch_metrics(tenant_id=self.tenant, options=None)
        rows = _campaign_rows(payload)
        assert len(rows) == 3, "Expected 3 campaign rows in full payload"
        assert _total_spend(payload) == pytest.approx(1190, abs=1)

    def test_scope_requested_no_accounts_returns_empty(self):
        """client_scope_requested=True + empty lists → zeros."""
        payload = self.adapter.fetch_metrics(
            tenant_id=self.tenant,
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": [],
                "client_scoped_google_customer_ids": [],
            },
        )
        assert _total_spend(payload) == 0
        assert _campaign_rows(payload) == []

    def test_scope_meta_only_filters_to_meta_rows(self):
        """Only meta scoped → only Meta rows in campaign.rows."""
        payload = self.adapter.fetch_metrics(
            tenant_id=self.tenant,
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": [],
            },
        )
        rows = _campaign_rows(payload)
        assert len(rows) > 0, "Expected at least one Meta row"
        platforms = _platforms_in_rows(rows)
        for p in platforms:
            assert p in META_CHANNEL_ALIASES, f"Unexpected platform {p!r} in meta-only result"
        # Google Ads and TikTok must not appear
        assert not platforms.intersection(GOOGLE_CHANNEL_ALIASES), "Google rows leaked into meta-only result"

    def test_scope_google_only_filters_to_google_rows(self):
        """Only google scoped → only Google rows in campaign.rows."""
        payload = self.adapter.fetch_metrics(
            tenant_id=self.tenant,
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": [],
                "client_scoped_google_customer_ids": ["123-456-7890"],
            },
        )
        rows = _campaign_rows(payload)
        assert len(rows) > 0, "Expected at least one Google row"
        platforms = _platforms_in_rows(rows)
        for p in platforms:
            assert p in GOOGLE_CHANNEL_ALIASES, f"Unexpected platform {p!r} in google-only result"

    def test_scope_both_returns_all_non_tiktok_rows(self):
        """Both scopes provided → Meta + Google rows; TikTok excluded."""
        payload = self.adapter.fetch_metrics(
            tenant_id=self.tenant,
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": ["123-456-7890"],
            },
        )
        rows = _campaign_rows(payload)
        platforms = _platforms_in_rows(rows)
        # TikTok must be excluded
        assert "tiktok" not in platforms
        # At least one of Meta or Google should be present
        assert platforms.intersection(META_CHANNEL_ALIASES | GOOGLE_CHANNEL_ALIASES)


# ---------------------------------------------------------------------------
# DemoAdapter tests
# ---------------------------------------------------------------------------

class TestDemoAdapterScopeParity:
    def setup_method(self):
        self.adapter = DemoAdapter()
        self.tenant = "tenant-test"
        # Patch _load_seeded_demo_data to return None so static DEMO_DATASETS path is used
        self._seed_patcher = patch("adapters.demo._load_seeded_demo_data", return_value=None)
        self._seed_patcher.start()

    def teardown_method(self):
        self._seed_patcher.stop()

    def test_no_scope_returns_full_payload(self):
        """Legacy: no options → full static dataset returned."""
        payload = self.adapter.fetch_metrics(tenant_id=self.tenant, options=None)
        # Static dataset should have some campaign rows
        assert isinstance(payload, dict)
        assert "campaign" in payload

    def test_scope_requested_no_accounts_returns_empty(self):
        payload = self.adapter.fetch_metrics(
            tenant_id=self.tenant,
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": [],
                "client_scoped_google_customer_ids": [],
            },
        )
        assert _total_spend(payload) == 0
        assert _campaign_rows(payload) == []

    def test_scope_meta_only_excludes_google_rows(self):
        """Meta-only scope: Google Ads rows must be excluded."""
        # Inject a known payload via DEMO_DATASETS path
        test_payload = {
            "campaign": {
                "summary": {"totalSpend": 200, "totalImpressions": 1000, "totalClicks": 50, "totalConversions": 10},
                "rows": [
                    {"id": "c1", "platform": "Meta", "spend": 120},
                    {"id": "c2", "platform": "Google Ads", "spend": 80},
                ],
                "trend": [],
            },
            "creative": [
                {"id": "cr1", "platform": "Meta"},
                {"id": "cr2", "platform": "Google Ads"},
            ],
        }
        with patch("adapters.demo.DEMO_DATASETS", {"default": {"payload": test_payload, "label": "Test"}}):
            with patch("adapters.demo.DEFAULT_DEMO_TENANT", "default"):
                payload = self.adapter.fetch_metrics(
                    tenant_id=self.tenant,
                    options={
                        "client_scope_requested": True,
                        "client_scoped_meta_ad_account_ids": ["act_111"],
                        "client_scoped_google_customer_ids": [],
                    },
                )
        rows = _campaign_rows(payload)
        platforms = _platforms_in_rows(rows)
        assert "google ads" not in platforms, "Google Ads leaked into meta-only demo result"
        assert "meta" in platforms or "facebook" in platforms or any(p in platforms for p in {"meta", "meta ads"}), "No meta rows in result"


# ---------------------------------------------------------------------------
# Parametrized cross-adapter contract: empty scope always returns zeros
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("adapter_cls", [FakeAdapter])
def test_empty_scope_contract_fake(adapter_cls):
    """For fake adapter: client_scope_requested=True + empty lists → totalSpend == 0."""
    adapter = adapter_cls()
    payload = adapter.fetch_metrics(
        tenant_id="t1",
        options={
            "client_scope_requested": True,
            "client_scoped_meta_ad_account_ids": [],
            "client_scoped_google_customer_ids": [],
        },
    )
    assert _total_spend(payload) == 0
    assert _campaign_rows(payload) == []


@pytest.mark.parametrize("adapter_cls", [FakeAdapter])
def test_no_scope_legacy_contract_fake(adapter_cls):
    """For fake adapter: options=None → full payload (legacy behaviour preserved)."""
    adapter = adapter_cls()
    payload = adapter.fetch_metrics(tenant_id="t1", options=None)
    # Must have campaign rows
    assert len(_campaign_rows(payload)) > 0


# ---------------------------------------------------------------------------
# UploadAdapter tests (requires DB)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUploadAdapterScopeParity:
    def test_scope_requested_no_accounts_returns_empty(self, tenant):
        from adapters.upload import UploadAdapter
        from analytics.models import TenantMetricsSnapshot

        snapshot_payload = {
            "campaign": {
                "summary": {"totalSpend": 500, "totalImpressions": 10000, "totalClicks": 400, "totalConversions": 20},
                "rows": [
                    {"id": "c1", "platform": "Meta", "adAccountId": "act_111", "spend": 300},
                    {"id": "c2", "platform": "Google Ads", "adAccountId": "google-1", "spend": 200},
                ],
                "trend": [],
            },
        }
        TenantMetricsSnapshot.objects.create(
            tenant=tenant,
            source="upload",
            payload=snapshot_payload,
        )

        adapter = UploadAdapter()
        payload = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": [],
                "client_scoped_google_customer_ids": [],
            },
        )
        assert _campaign_rows(payload) == []

    def test_scope_meta_filters_by_account_id(self, tenant):
        from adapters.upload import UploadAdapter
        from analytics.models import TenantMetricsSnapshot

        snapshot_payload = {
            "campaign": {
                "summary": {"totalSpend": 500},
                "rows": [
                    {"id": "c1", "adAccountId": "act_111", "spend": 300},
                    {"id": "c2", "adAccountId": "google-1", "spend": 200},
                ],
                "trend": [],
            },
        }
        TenantMetricsSnapshot.objects.create(
            tenant=tenant,
            source="upload",
            payload=snapshot_payload,
        )

        adapter = UploadAdapter()
        payload = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": [],
            },
        )
        rows = _campaign_rows(payload)
        assert len(rows) == 1
        assert rows[0]["id"] == "c1"

    def test_scope_meta_filters_by_platform_fallback(self, tenant):
        from adapters.upload import UploadAdapter
        from analytics.models import TenantMetricsSnapshot

        snapshot_payload = {
            "campaign": {
                "summary": {"totalSpend": 500},
                "rows": [
                    {"id": "c1", "platform": "Meta", "spend": 300},
                    {"id": "c2", "platform": "Google Ads", "spend": 200},
                ],
                "trend": [],
            },
        }
        TenantMetricsSnapshot.objects.create(
            tenant=tenant,
            source="upload",
            payload=snapshot_payload,
        )

        adapter = UploadAdapter()
        payload = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": [],
            },
        )
        rows = _campaign_rows(payload)
        assert len(rows) == 1
        assert rows[0]["id"] == "c1"

    def test_no_scope_returns_full_snapshot(self, tenant):
        from adapters.upload import UploadAdapter
        from analytics.models import TenantMetricsSnapshot

        snapshot_payload = {
            "campaign": {
                "summary": {"totalSpend": 500},
                "rows": [
                    {"id": "c1", "platform": "Meta", "spend": 300},
                    {"id": "c2", "platform": "Google Ads", "spend": 200},
                ],
                "trend": [],
            },
        }
        TenantMetricsSnapshot.objects.create(
            tenant=tenant,
            source="upload",
            payload=snapshot_payload,
        )

        adapter = UploadAdapter()
        payload = adapter.fetch_metrics(tenant_id=str(tenant.id), options=None)
        rows = _campaign_rows(payload)
        assert len(rows) == 2
