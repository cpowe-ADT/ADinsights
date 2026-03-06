from __future__ import annotations

import httpx
import pytest

from integrations.services.meta_graph_client import (
    META_PAGE_RETRY_REASON_RATE_LIMITED,
    META_PAGE_RETRY_REASON_TRANSPORT,
    MetaInsightsGraphClient,
    MetaInsightsGraphClientError,
)


def _response(status_code: int, payload: dict):
    return httpx.Response(status_code=status_code, json=payload)


@pytest.mark.django_db
def test_meta_page_graph_client_retries_on_error_code_80001(monkeypatch):
    client = MetaInsightsGraphClient(graph_version="v24.0", max_attempts=3)
    calls = {"count": 0}
    observed_retry_reasons: list[str] = []

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            return _response(
                400,
                {
                    "error": {
                        "message": "Too many calls",
                        "code": 80001,
                    }
                },
            )
        return _response(200, {"data": []})

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.services.meta_graph_client.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "integrations.services.meta_graph_client.observe_meta_graph_retry",
        lambda *, reason: observed_retry_reasons.append(reason),
    )

    payload = client.fetch_page_insights(
        page_id="page-1",
        metrics=["page_post_engagements"],
        period="day",
        since="2026-02-01",
        until="2026-02-18",
        token="token",
    )
    assert payload["data"] == []
    assert calls["count"] == 2
    assert observed_retry_reasons == [META_PAGE_RETRY_REASON_RATE_LIMITED]


@pytest.mark.django_db
def test_meta_page_graph_client_raises_after_retry_exhaustion(monkeypatch):
    client = MetaInsightsGraphClient(graph_version="v24.0", max_attempts=2)

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        return _response(
            400,
            {
                "error": {
                    "message": "Too many calls",
                    "code": 80001,
                }
            },
        )

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.services.meta_graph_client.time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(MetaInsightsGraphClientError) as exc:
        client.fetch_page_insights(
            page_id="page-1",
            metrics=["page_post_engagements"],
            period="day",
            since="2026-02-01",
            until="2026-02-18",
            token="token",
        )
    assert exc.value.error_code == 80001


@pytest.mark.django_db
def test_meta_page_graph_client_emits_transport_retry_reason(monkeypatch):
    client = MetaInsightsGraphClient(graph_version="v24.0", max_attempts=3)
    calls = {"count": 0}
    observed_retry_reasons: list[str] = []

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timeout")
        return _response(200, {"data": []})

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.services.meta_graph_client.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "integrations.services.meta_graph_client.observe_meta_graph_retry",
        lambda *, reason: observed_retry_reasons.append(reason),
    )

    payload = client.fetch_page_insights(
        page_id="page-1",
        metrics=["page_post_engagements"],
        period="day",
        since="2026-02-01",
        until="2026-02-18",
        token="token",
    )
    assert payload["data"] == []
    assert calls["count"] == 2
    assert observed_retry_reasons == [META_PAGE_RETRY_REASON_TRANSPORT]
