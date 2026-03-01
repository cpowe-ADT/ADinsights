from __future__ import annotations

import httpx
import pytest

from integrations.meta_graph import MetaGraphClient, MetaGraphClientError


def _response(status_code: int, payload: dict, *, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload, headers=headers or {})


@pytest.mark.django_db
def test_meta_graph_client_paginates_ad_accounts(monkeypatch):
    client = MetaGraphClient(app_id="app", app_secret="secret", graph_version="v24.0")

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        if "page=2" in url:
            return _response(
                200,
                {
                    "data": [
                        {
                            "id": "act_456",
                            "account_id": "456",
                            "name": "Secondary",
                        }
                    ]
                },
            )
        return _response(
            200,
            {
                "data": [
                    {
                        "id": "act_123",
                        "account_id": "123",
                        "name": "Primary",
                    }
                ],
                "paging": {"next": "https://graph.facebook.com/v24.0/me/adaccounts?page=2"},
            },
        )

    monkeypatch.setattr(client._client, "request", fake_request)
    ad_accounts = client.list_ad_accounts(user_access_token="token")
    assert [item.account_id for item in ad_accounts] == ["123", "456"]


@pytest.mark.django_db
def test_meta_graph_client_retries_then_succeeds(monkeypatch):
    client = MetaGraphClient(app_id="app", app_secret="secret", graph_version="v24.0")
    calls = {"count": 0}

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            return _response(
                429,
                {"error": {"message": "rate limited", "code": 4}},
            )
        return _response(200, {"data": {"is_valid": True}})

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.meta_graph.time.sleep", lambda *_args, **_kwargs: None)

    debug = client.debug_token(input_token="token")
    assert debug["is_valid"] is True
    assert calls["count"] == 2


@pytest.mark.django_db
def test_meta_graph_client_retry_exhaustion_raises(monkeypatch):
    client = MetaGraphClient(
        app_id="app",
        app_secret="secret",
        graph_version="v24.0",
        max_attempts=2,
    )

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        return _response(
            503,
            {"error": {"message": "temporary unavailable", "code": 2}},
        )

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.meta_graph.time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(MetaGraphClientError):
        client.debug_token(input_token="token")


@pytest.mark.django_db
def test_meta_graph_client_emits_throttle_event_from_usage_headers(monkeypatch):
    client = MetaGraphClient(app_id="app", app_secret="secret", graph_version="v24.0")
    observed = {"count": 0}

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        return _response(
            200,
            {"data": {"is_valid": True}},
            headers={"x-app-usage": '{"call_count": 95, "total_cputime": 20, "total_time": 10}'},
        )

    def fake_observe(*, header_name: str):
        assert header_name == "x-app-usage"
        observed["count"] += 1

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("integrations.meta_graph.observe_meta_graph_throttle_event", fake_observe)

    debug = client.debug_token(input_token="token")
    assert debug["is_valid"] is True
    assert observed["count"] == 1


@pytest.mark.django_db
def test_meta_graph_client_list_pages_retries_without_perms_field(monkeypatch):
    client = MetaGraphClient(app_id="app", app_secret="secret", graph_version="v24.0")
    calls = {"count": 0}

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            assert isinstance(params, dict)
            assert "perms" in str(params.get("fields"))
            return _response(
                400,
                {
                    "error": {
                        "message": "(#100) Tried accessing nonexisting field (perms)",
                        "code": 100,
                    }
                },
            )
        assert isinstance(params, dict)
        assert "perms" not in str(params.get("fields"))
        return _response(
            200,
            {
                "data": [
                    {
                        "id": "page-1",
                        "name": "Business Page",
                        "access_token": "page-token",
                        "category": "Business",
                        "tasks": ["ANALYZE"],
                    }
                ]
            },
        )

    monkeypatch.setattr(client._client, "request", fake_request)

    pages = client.list_pages(user_access_token="user-token")

    assert calls["count"] == 2
    assert len(pages) == 1
    assert pages[0].id == "page-1"
    assert pages[0].tasks == ["ANALYZE"]
    assert pages[0].perms == []


@pytest.mark.django_db
def test_meta_graph_client_list_pages_uses_user_token_when_page_token_missing(monkeypatch):
    client = MetaGraphClient(app_id="app", app_secret="secret", graph_version="v24.0")

    def fake_request(method: str, url: str, params=None):  # noqa: ANN001
        return _response(
            200,
            {
                "data": [
                    {
                        "id": "page-1",
                        "name": "Business Page",
                        "category": "Business",
                        "tasks": [],
                    }
                ]
            },
        )

    monkeypatch.setattr(client._client, "request", fake_request)

    pages = client.list_pages(user_access_token="user-token")

    assert len(pages) == 1
    assert pages[0].id == "page-1"
    assert pages[0].access_token == "user-token"
