from __future__ import annotations

import pytest

from integrations.airbyte.client import (
    AirbyteClient,
    AirbyteClientConfigurationError,
)


def test_airbyte_client_requires_auth(settings):
    settings.AIRBYTE_API_URL = "http://airbyte.local"
    settings.AIRBYTE_API_TOKEN = None
    settings.AIRBYTE_USERNAME = None
    settings.AIRBYTE_PASSWORD = None
    with pytest.raises(AirbyteClientConfigurationError):
        AirbyteClient.from_settings()


def test_airbyte_client_requests(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):  # noqa: D401 - httpx compatibility
            return None

        def json(self):
            return self._payload

    class DummyHttpClient:
        def __init__(self, *args, **kwargs):  # noqa: D401 - mimic httpx
            self.closed = False

        def post(self, path, json):
            calls.append((path, json))
            if path.endswith("/connections/sync"):
                return DummyResponse({"job": {"id": 42}})
            if path.endswith("/jobs/get"):
                return DummyResponse({"job": {"id": json["id"], "status": "succeeded"}})
            return DummyResponse({"jobs": [{"id": 42, "status": "succeeded"}]})

        def close(self):
            self.closed = True

    monkeypatch.setattr("integrations.airbyte.client.httpx.Client", DummyHttpClient)

    with AirbyteClient(base_url="http://airbyte", token="token") as client:
        sync_payload = client.trigger_sync("abc")
        assert sync_payload["job"]["id"] == 42
        job_payload = client.get_job(42)
        assert job_payload["job"]["status"] == "succeeded"
        latest_payload = client.latest_job("abc")
        assert latest_payload["id"] == 42

    assert calls[0][0].endswith("/connections/sync")
    assert calls[0][1] == {"connectionId": "abc"}
    assert calls[1][0].endswith("/jobs/get")
    assert calls[1][1] == {"id": 42}
    assert calls[2][0].endswith("/jobs/list")
