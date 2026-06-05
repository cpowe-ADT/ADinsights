"""Sprint 10: coverage for WarehouseAdapter client scoping wiring.

The adapter honours the ``client_scoped_*`` keys emitted by
``analytics.combined_metrics_service.resolve_client_scoping``. When a Client
is selected, the adapter must:

* fold the scoped Google + Meta account id sets into the ``account_ids``
  filter so the payload is restricted to that Client's accounts, and
* when scoping was requested but resolves to zero linked accounts, return
  an empty-shaped payload (not the unfiltered one — that would leak the
  tenant's full dataset).
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from accounts.tenant_context import tenant_context
from adapters.warehouse import WarehouseAdapter
from analytics.models import TenantMetricsSnapshot


def _build_payload() -> dict:
    return {
        "campaign": {
            "summary": {"currency": "JMD"},
            "trend": [
                {"date": "2026-04-01", "adAccountId": "act_111", "spend": 10},
                {"date": "2026-04-02", "adAccountId": "act_222", "spend": 20},
                {"date": "2026-04-03", "adAccountId": "1234567890", "spend": 30},
            ],
            "rows": [
                {
                    "id": "cmp-a",
                    "adAccountId": "act_111",
                    "name": "A",
                    "spend": 10,
                    "impressions": 100,
                    "clicks": 5,
                    "conversions": 1,
                    "roas": 2.0,
                },
                {
                    "id": "cmp-b",
                    "adAccountId": "act_222",
                    "name": "B",
                    "spend": 20,
                    "impressions": 200,
                    "clicks": 10,
                    "conversions": 2,
                    "roas": 3.0,
                },
                {
                    "id": "cmp-c",
                    "adAccountId": "1234567890",
                    "name": "C (Google)",
                    "spend": 30,
                    "impressions": 300,
                    "clicks": 15,
                    "conversions": 3,
                    "roas": 4.0,
                },
            ],
        },
        "creative": [
            {"id": "cr-a", "adAccountId": "act_111"},
            {"id": "cr-b", "adAccountId": "act_222"},
            {"id": "cr-c", "adAccountId": "1234567890"},
        ],
        "budget": [
            {"id": "bdg-a", "adAccountId": "act_111"},
            {"id": "bdg-b", "adAccountId": "act_222"},
        ],
        "parish": [
            {"adAccountId": "act_111", "parish": "Kingston"},
            {"adAccountId": "act_222", "parish": "St James"},
        ],
    }


def _seed(tenant) -> None:
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        payload={
            **_build_payload(),
            "snapshot_generated_at": timezone.now().isoformat(),
        },
        generated_at=timezone.now(),
    )


@pytest.mark.django_db
def test_client_scope_restricts_payload_to_scoped_accounts(tenant):
    """Selected Client with Meta + Google linked accounts narrows the payload."""

    _seed(tenant)
    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        filtered = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": ["1234567890"],
            },
        )

    assert sorted(row["id"] for row in filtered["campaign"]["rows"]) == ["cmp-a", "cmp-c"]
    assert sorted(row["id"] for row in filtered["creative"]) == ["cr-a", "cr-c"]
    assert [row["id"] for row in filtered["budget"]] == ["bdg-a"]
    assert [row["parish"] for row in filtered["parish"]] == ["Kingston"]
    # Summary recalculated from filtered rows
    assert filtered["campaign"]["summary"]["totalSpend"] == 40  # 10 + 30


@pytest.mark.django_db
def test_client_scope_google_bare_numeric_matches_act_prefix(tenant):
    """Google customer_id ``1234567890`` should match an ``act_1234567890``
    style value if the warehouse ever stored it under that alias."""

    payload = _build_payload()
    payload["campaign"]["rows"].append(
        {
            "id": "cmp-d",
            "adAccountId": "act_1234567890",  # Aliased form
            "name": "D",
            "spend": 7,
            "impressions": 70,
            "clicks": 1,
            "conversions": 0,
            "roas": 0.0,
        }
    )
    TenantMetricsSnapshot.objects.create(
        tenant=tenant,
        source="warehouse",
        payload={**payload, "snapshot_generated_at": timezone.now().isoformat()},
        generated_at=timezone.now(),
    )
    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        filtered = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_google_customer_ids": ["1234567890"],
                "client_scoped_meta_ad_account_ids": [],
            },
        )

    ids = sorted(row["id"] for row in filtered["campaign"]["rows"])
    assert ids == ["cmp-c", "cmp-d"]


@pytest.mark.django_db
def test_client_scope_requested_with_no_accounts_returns_empty_payload(tenant):
    """Scoping requested but zero linked accounts → empty-shaped payload,
    not the unfiltered one. This prevents tenant-wide leaks for Clients
    that have not yet attached any accounts."""

    _seed(tenant)
    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        filtered = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": [],
                "client_scoped_google_customer_ids": [],
            },
        )

    assert filtered["campaign"]["rows"] == []
    assert filtered["campaign"]["trend"] == []
    assert filtered["campaign"]["metrics"] == {}
    assert filtered["creative"]["rows"] == []
    assert filtered["parish"]["rows"] == []
    # The snapshot_generated_at metadata survives so the dashboard can still
    # render a "last updated" timestamp.
    assert "snapshot_generated_at" in filtered


@pytest.mark.django_db
def test_no_client_scope_requested_returns_full_payload(tenant):
    """Without the scope flag, the adapter behaves as before (no filtering)."""

    _seed(tenant)
    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        filtered = adapter.fetch_metrics(tenant_id=str(tenant.id))

    assert len(filtered["campaign"]["rows"]) == 3
    assert len(filtered["creative"]) == 3


@pytest.mark.django_db
def test_client_scope_combines_with_explicit_account_id_filter(tenant):
    """If the caller already passed ``account_id``, the client-scoped ids
    are unioned in so both restrictions apply."""

    _seed(tenant)
    adapter = WarehouseAdapter()
    with tenant_context(str(tenant.id)):
        filtered = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={
                "account_id": "act_222",
                "client_scope_requested": True,
                "client_scoped_meta_ad_account_ids": ["act_111"],
                "client_scoped_google_customer_ids": [],
            },
        )

    ids = sorted(row["id"] for row in filtered["campaign"]["rows"])
    assert ids == ["cmp-a", "cmp-b"]
