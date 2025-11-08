from __future__ import annotations

from django.conf import settings
from django.db import connection

from accounts.tenant_context import get_current_tenant_id, tenant_context


def test_tenant_context_sets_and_restores_connection():
    original = getattr(connection, settings.TENANT_SETTING_KEY, None)

    with tenant_context("tenant-abc"):
        assert get_current_tenant_id() == "tenant-abc"
        assert getattr(connection, settings.TENANT_SETTING_KEY, None) == "tenant-abc"

    assert get_current_tenant_id() is None
    assert getattr(connection, settings.TENANT_SETTING_KEY, None) == original


def test_tenant_context_restores_previous_value():
    with tenant_context("tenant-outer"):
        assert get_current_tenant_id() == "tenant-outer"
        with tenant_context("tenant-inner"):
            assert get_current_tenant_id() == "tenant-inner"
            assert getattr(connection, settings.TENANT_SETTING_KEY, None) == "tenant-inner"
        assert get_current_tenant_id() == "tenant-outer"
        assert getattr(connection, settings.TENANT_SETTING_KEY, None) == "tenant-outer"

