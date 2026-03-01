from __future__ import annotations

import pytest


ENDPOINT = "/api/analytics/parish-geometry/"


@pytest.mark.django_db
def test_parish_geometry_requires_authentication(api_client):
    response = api_client.get(ENDPOINT)

    assert response.status_code == 401


@pytest.mark.django_db
def test_parish_geometry_returns_feature_collection(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get(ENDPOINT)

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("type") == "FeatureCollection"
    assert isinstance(payload.get("features"), list)
