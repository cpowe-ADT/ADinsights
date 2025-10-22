from __future__ import annotations

import datetime

import pytest

from accounts.models import Tenant, User
from analytics.models import AdSet, Campaign, RawPerformanceRecord


@pytest.mark.django_db
def test_campaign_crud_scoped_to_tenant(api_client, tenant, user):
    api_client.force_authenticate(user=user)

    create_payload = {
        "external_id": "camp-1",
        "name": "Awareness",
        "platform": "META",
        "status": "ACTIVE",
    }

    create_response = api_client.post(
        "/api/analytics/campaigns/", create_payload, format="json"
    )

    assert create_response.status_code == 201
    campaign_id = create_response.json()["id"]

    list_response = api_client.get("/api/analytics/campaigns/")
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["id"] == campaign_id

    update_response = api_client.patch(
        f"/api/analytics/campaigns/{campaign_id}/",
        {"status": "PAUSED"},
        format="json",
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "PAUSED"

    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_adset_creation_enforces_tenant_scoping(api_client, tenant, user):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
    )

    tenant_campaign = Campaign.all_objects.create(
        tenant=tenant,
        external_id="camp-tenant",
        name="Tenant Campaign",
        platform="META",
    )
    other_campaign = Campaign.all_objects.create(
        tenant=other_tenant,
        external_id="camp-other",
        name="Other Campaign",
        platform="META",
    )

    api_client.force_authenticate(user=user)
    create_payload = {
        "campaign": str(tenant_campaign.id),
        "external_id": "adset-1",
        "name": "Retargeting",
    }
    response = api_client.post(
        "/api/analytics/adsets/", create_payload, format="json"
    )
    assert response.status_code == 201

    cross_tenant_payload = {
        "campaign": str(other_campaign.id),
        "external_id": "adset-2",
        "name": "Should Fail",
    }
    cross_response = api_client.post(
        "/api/analytics/adsets/", cross_tenant_payload, format="json"
    )
    assert cross_response.status_code == 400

    api_client.force_authenticate(user=other_user)
    other_response = api_client.get("/api/analytics/adsets/")
    assert other_response.status_code == 200
    assert other_response.json() == []

    api_client.force_authenticate(user=None)


@pytest.mark.django_db
def test_performance_records_isolated_by_tenant(api_client, tenant, user):
    campaign = Campaign.all_objects.create(
        tenant=tenant,
        external_id="camp-tenant",
        name="Tenant Campaign",
        platform="META",
    )
    adset = AdSet.all_objects.create(
        tenant=tenant,
        campaign=campaign,
        external_id="adset-tenant",
        name="Tenant AdSet",
    )

    other_tenant = Tenant.objects.create(name="Isolation Tenant")
    other_campaign = Campaign.all_objects.create(
        tenant=other_tenant,
        external_id="camp-other",
        name="Other Campaign",
        platform="META",
    )
    RawPerformanceRecord.all_objects.create(
        tenant=other_tenant,
        external_id="perf-other",
        date=datetime.date(2024, 1, 1),
        source="meta",
        campaign=other_campaign,
        impressions=10,
    )

    api_client.force_authenticate(user=user)
    payload = {
        "external_id": "perf-tenant",
        "date": "2024-01-01",
        "source": "meta",
        "campaign": str(campaign.id),
        "adset": str(adset.id),
        "impressions": 100,
        "clicks": 5,
        "spend": "12.34",
    }
    create_response = api_client.post(
        "/api/analytics/performance-records/", payload, format="json"
    )
    assert create_response.status_code == 201

    list_response = api_client.get("/api/analytics/performance-records/")
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 1
    assert records[0]["external_id"] == "perf-tenant"

    api_client.force_authenticate(user=None)
