"""Tests for TenantMiddleware tenant propagation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from accounts import middleware as tenant_middleware
from backend.middleware.tenant import TenantHeaderMiddleware
from django.test import override_settings


class DummyConnection:
    """Connection stub capturing executed statements."""

    vendor = "postgresql"

    def __init__(self) -> None:
        self.statements: list[tuple[str, list[str] | None]] = []

    def cursor(self):  # pragma: no cover - exercised via context protocol
        connection = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, sql: str, params: list[str] | None = None):
                connection.statements.append((sql, params))

        return _Cursor()


@pytest.fixture
def stub_connection(monkeypatch):
    connection = DummyConnection()
    monkeypatch.setattr(tenant_middleware, "connection", connection)
    monkeypatch.setattr("accounts.tenant_context.connection", connection)
    return connection


def test_process_request_authenticated_user_sets_tenant(monkeypatch, stub_connection):
    tenant_id = 42
    set_mock = MagicMock()
    monkeypatch.setattr(tenant_middleware, "set_current_tenant_id", set_mock)

    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, tenant_id=tenant_id),
        META={},
    )

    middleware = tenant_middleware.TenantMiddleware(lambda req: None)
    middleware.process_request(request)

    set_mock.assert_called_once_with(str(tenant_id))
    assert stub_connection.statements == [("SET app.tenant_id = %s", [str(tenant_id)])]


def test_process_request_falls_back_to_header_for_unauthenticated_user(
    monkeypatch, stub_connection
):
    header_tenant = "tenant-from-header"
    set_mock = MagicMock()
    monkeypatch.setattr(tenant_middleware, "set_current_tenant_id", set_mock)

    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False, tenant_id=None),
        META={"HTTP_X_TENANT_ID": header_tenant},
    )

    middleware = tenant_middleware.TenantMiddleware(lambda req: None)
    middleware.process_request(request)

    set_mock.assert_called_once_with(header_tenant)
    assert stub_connection.statements == [("SET app.tenant_id = %s", [header_tenant])]


def test_process_request_without_tenant_sets_default(monkeypatch, stub_connection):
    set_mock = MagicMock()
    monkeypatch.setattr(tenant_middleware, "set_current_tenant_id", set_mock)

    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False, tenant_id=None),
        META={},
    )

    middleware = tenant_middleware.TenantMiddleware(lambda req: None)
    middleware.process_request(request)

    set_mock.assert_called_once_with(None)
    assert stub_connection.statements == [("SET app.tenant_id = DEFAULT", None)]


def test_process_response_resets_tenant_context(monkeypatch, stub_connection):
    clear_mock = MagicMock()
    monkeypatch.setattr(tenant_middleware, "clear_current_tenant", clear_mock)

    request = SimpleNamespace()
    response = object()

    middleware = tenant_middleware.TenantMiddleware(lambda req: response)
    result = middleware.process_response(request, response)

    clear_mock.assert_called_once_with()
    assert stub_connection.statements == [("RESET app.tenant_id", None)]
    assert result is response


@override_settings(ENABLE_TENANCY=True)
def test_tenant_header_middleware_sets_request_attribute():
    request = SimpleNamespace(META={"HTTP_X_TENANT_ID": "tenant-123"})
    middleware = TenantHeaderMiddleware(lambda req: None)

    middleware.process_request(request)

    assert request.tenant_id == "tenant-123"


@override_settings(ENABLE_TENANCY=False)
def test_tenant_header_middleware_is_noop_when_disabled():
    request = SimpleNamespace(META={"HTTP_X_TENANT_ID": "tenant-123"})
    middleware = TenantHeaderMiddleware(lambda req: None)

    middleware.process_request(request)

    assert not hasattr(request, "tenant_id")
