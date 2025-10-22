from __future__ import annotations

import pytest

from accounts.models import AuditLog, Role, Tenant, UserRole
from accounts.serializers import TenantSwitchSerializer


@pytest.mark.django_db
def test_tenant_switch_serializer_validates_membership(user):
    other_tenant = Tenant.objects.create(name="Other")

    serializer = TenantSwitchSerializer(
        data={"tenant_id": str(other_tenant.id)},
        context={"user": user},
    )

    assert not serializer.is_valid()
    assert "tenant_id" in serializer.errors


@pytest.mark.django_db
def test_tenant_switch_serializer_accepts_secondary_membership(user):
    other_tenant = Tenant.objects.create(name="Other")
    role, _ = Role.objects.get_or_create(name=Role.ADMIN)
    UserRole.objects.create(user=user, tenant=other_tenant, role=role)

    serializer = TenantSwitchSerializer(
        data={"tenant_id": str(other_tenant.id)},
        context={"user": user},
    )

    assert serializer.is_valid(), serializer.errors
    tenant = serializer.save()
    assert tenant.id == other_tenant.id


class DummyConnection:
    vendor = "postgresql"

    def __init__(self) -> None:
        self.statements: list[tuple[str, list[str] | None]] = []

    def cursor(self):  # pragma: no cover - used via context manager protocol
        connection = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, sql: str, params: list[str] | None = None):
                connection.statements.append((sql, params))

        return _Cursor()


@pytest.mark.django_db
def test_tenant_switch_view_sets_tenant_and_logs_audit(
    api_client, user, monkeypatch
):
    connection = DummyConnection()
    monkeypatch.setattr("accounts.views.connection", connection, raising=False)

    api_client.force_authenticate(user=user)
    response = api_client.post(
        "/api/auth/switch-tenant/",
        {"tenant_id": str(user.tenant_id)},
        format="json",
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    assert connection.statements == [
        ("SET app.tenant_id = %s", [str(user.tenant_id)])
    ]

    audit_entry = AuditLog.objects.get(
        action="tenant_switched", resource_id=str(user.tenant_id)
    )
    assert audit_entry.user_id == user.id
