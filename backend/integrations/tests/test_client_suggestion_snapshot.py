"""Sprint 9a coverage: refresh_client_suggestions Celery task + snapshot endpoints."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from analytics.models import AdAccount
from integrations.clients.tasks import refresh_client_suggestions
from integrations.models import (
    Client,
    ClientPlatformAccount,
    ClientSuggestionSnapshot,
    GoogleAdsAccountMapping,
)


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _seed_unclaimed_cross_platform(tenant) -> None:
    """Create a Meta ad account and a Google Ads customer with matching names."""

    GoogleAdsAccountMapping.all_objects.create(
        tenant=tenant,
        customer_id="1111111111",
        customer_name="Bank of Jamaica Limited",
        is_manager=False,
    )
    AdAccount.all_objects.create(
        tenant=tenant,
        external_id="act_222222222",
        name="Bank of Jamaica",
        status="ACTIVE",
    )


class TestRefreshClientSuggestionsTask:
    def test_writes_snapshot_with_cross_platform_grouping(self, tenant):
        _seed_unclaimed_cross_platform(tenant)

        result = refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )

        assert result["suggestion_count"] >= 1
        snapshot = ClientSuggestionSnapshot.all_objects.get(tenant=tenant)
        assert snapshot.suggestion_count == result["suggestion_count"]
        assert snapshot.trigger_reason == ClientSuggestionSnapshot.REASON_META_SYNC
        assert isinstance(snapshot.payload, list)
        assert snapshot.payload  # non-empty
        first = snapshot.payload[0]
        assert set(first["unclaimed_accounts"][0].keys()) == {
            "platform",
            "external_id",
            "display_name",
        }
        platforms = {
            acct["platform"]
            for acct in first["unclaimed_accounts"]
        }
        assert {"google_ads", "meta_ads"}.issubset(platforms)

    def test_rerun_upserts_and_preserves_ack_when_count_and_reason_unchanged(self, tenant):
        _seed_unclaimed_cross_platform(tenant)
        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )
        snapshot = ClientSuggestionSnapshot.all_objects.get(tenant=tenant)
        from django.utils import timezone
        snapshot.acknowledged_at = timezone.now()
        snapshot.save(update_fields=["acknowledged_at"])

        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )

        snapshot.refresh_from_db()
        assert snapshot.acknowledged_at is not None

    def test_reason_change_clears_acknowledgement(self, tenant):
        _seed_unclaimed_cross_platform(tenant)
        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )
        snapshot = ClientSuggestionSnapshot.all_objects.get(tenant=tenant)
        from django.utils import timezone
        snapshot.acknowledged_at = timezone.now()
        snapshot.save(update_fields=["acknowledged_at"])

        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_GOOGLE_SYNC,
        )
        snapshot.refresh_from_db()
        assert snapshot.acknowledged_at is None
        assert snapshot.trigger_reason == ClientSuggestionSnapshot.REASON_GOOGLE_SYNC

    def test_empty_when_no_unclaimed_accounts(self, tenant):
        # Everything already linked → no suggestions.
        client = Client.all_objects.create(tenant=tenant, name="JDIC", slug="jdic")
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant,
            customer_id="9999999999",
            customer_name="JDIC",
            is_manager=False,
        )
        ClientPlatformAccount.all_objects.create(
            tenant=tenant,
            client=client,
            platform=ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            external_id="9999999999",
            display_name="JDIC",
        )

        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_MANUAL,
        )
        snapshot = ClientSuggestionSnapshot.all_objects.get(tenant=tenant)
        assert snapshot.suggestion_count == 0
        assert snapshot.payload == []


class TestClientSuggestionSnapshotEndpoints:
    def test_get_returns_null_when_absent(self, auth_client):
        r = auth_client.get("/api/clients/suggestions/latest/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data == {"snapshot": None}

    def test_get_returns_snapshot_when_present(self, auth_client, tenant):
        _seed_unclaimed_cross_platform(tenant)
        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )
        r = auth_client.get("/api/clients/suggestions/latest/")
        assert r.status_code == status.HTTP_200_OK
        body = r.data["snapshot"]
        assert body["suggestion_count"] >= 1
        assert body["is_unacknowledged"] is True
        assert body["trigger_reason"] == ClientSuggestionSnapshot.REASON_META_SYNC

    def test_acknowledge_marks_seen(self, auth_client, tenant):
        _seed_unclaimed_cross_platform(tenant)
        refresh_client_suggestions.run(
            tenant_id=str(tenant.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_MANUAL,
        )

        r = auth_client.post("/api/clients/suggestions/latest/acknowledge/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["snapshot"]["acknowledged_at"] is not None
        assert r.data["snapshot"]["is_unacknowledged"] is False

    def test_acknowledge_404_when_absent(self, auth_client):
        r = auth_client.post("/api/clients/suggestions/latest/acknowledge/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_refresh_enqueues_and_returns_202(self, auth_client, monkeypatch):
        calls: list[dict] = []

        from integrations.clients import tasks as client_tasks

        def fake_delay(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return None

        monkeypatch.setattr(
            client_tasks.refresh_client_suggestions,
            "delay",
            fake_delay,
        )

        r = auth_client.post(
            "/api/clients/suggestions/latest/refresh/",
            data={"threshold": 0.65},
            format="json",
        )
        assert r.status_code == status.HTTP_202_ACCEPTED
        assert calls
        assert calls[0]["trigger_reason"] == ClientSuggestionSnapshot.REASON_MANUAL

    def test_refresh_rejects_invalid_threshold(self, auth_client):
        r = auth_client.post(
            "/api/clients/suggestions/latest/refresh/",
            data={"threshold": "abc"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_snapshot_is_tenant_scoped(self, auth_client, tenant, db):
        from accounts.models import Tenant

        other = Tenant.objects.create(name="Other Tenant 9a")
        _seed_unclaimed_cross_platform(other)
        refresh_client_suggestions.run(
            tenant_id=str(other.id),
            trigger_reason=ClientSuggestionSnapshot.REASON_META_SYNC,
        )
        # Current user belongs to `tenant` (no snapshot).
        r = auth_client.get("/api/clients/suggestions/latest/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data == {"snapshot": None}
