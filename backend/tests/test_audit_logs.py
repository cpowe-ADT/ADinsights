from __future__ import annotations

from django.urls import reverse

from accounts.models import AuditLog, Role, Tenant, User, assign_role
from integrations.models import PlatformCredential
from core.tasks import sync_meta_example


def authenticate(api_client, user):
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": user.username, "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return token


def test_login_creates_audit_log_and_list_filters(api_client, user, tenant):
    authenticate(api_client, user)

    logs = AuditLog.all_objects.filter(tenant=tenant, action="login")
    assert logs.count() == 1

    response = api_client.get(reverse("auditlog-list"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "login"

    filtered = api_client.get(reverse("auditlog-list"), {"action": "login"})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1


def test_platform_credential_crud_logs(api_client, user, tenant):
    authenticate(api_client, user)

    payload = {
        "provider": PlatformCredential.META,
        "account_id": "123",
        "access_token": "secret-token",
        "refresh_token": "refresh-token",
    }

    create_resp = api_client.post(reverse("platformcredential-list"), payload, format="json")
    assert create_resp.status_code == 201
    credential_id = create_resp.json()["id"]

    update_resp = api_client.patch(
        reverse("platformcredential-detail", args=[credential_id]),
        {"access_token": "updated-token"},
        format="json",
    )
    assert update_resp.status_code == 200

    delete_resp = api_client.delete(
        reverse("platformcredential-detail", args=[credential_id])
    )
    assert delete_resp.status_code == 204

    actions = list(
        AuditLog.all_objects.filter(
            tenant=tenant, resource_type="platform_credential"
        ).values_list("action", flat=True)
    )
    assert actions.count("credential_created") == 1
    assert actions.count("credential_updated") == 1
    assert actions.count("credential_deleted") == 1


def test_role_assignment_logs(api_client, user, tenant):
    assign_role(user, Role.ADMIN)
    authenticate(api_client, user)

    teammate = User.objects.create_user(
        username="member@example.com",
        email="member@example.com",
        tenant=tenant,
    )

    assign_resp = api_client.post(
        reverse("userrole-list"),
        {"user": teammate.id, "role": "VIEWER"},
        format="json",
    )
    assert assign_resp.status_code == 201
    assignment_id = assign_resp.json()["id"]

    delete_resp = api_client.delete(reverse("userrole-detail", args=[assignment_id]))
    assert delete_resp.status_code == 204

    actions = list(
        AuditLog.all_objects.filter(
            tenant=tenant, resource_type="role"
        ).values_list("action", flat=True)
    )
    assert "role_assigned" in actions
    assert "role_revoked" in actions


def test_sync_trigger_logs(api_client, user, tenant):
    authenticate(api_client, user)

    result = sync_meta_example(tenant_id=str(tenant.id), triggered_by_user_id=str(user.id))
    assert result == "meta_sync_triggered"

    log = AuditLog.all_objects.get(
        tenant=tenant, resource_type="sync", resource_id=PlatformCredential.META
    )
    assert log.action == "sync_triggered"
    assert log.user_id == user.id


def test_audit_log_endpoint_is_tenant_scoped(api_client, user, tenant, db):
    other_tenant = Tenant.objects.create(name="Other")
    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
    )
    other_user.set_password("password123")
    other_user.save()

    authenticate(api_client, user)

    log = AuditLog.all_objects.create(
        tenant=other_tenant,
        user=other_user,
        action="login",
        resource_type="auth",
        resource_id=str(other_user.id),
    )

    response = api_client.get(reverse("auditlog-list"))
    assert response.status_code == 200
    body = response.json()
    assert all(entry["tenant"] == str(tenant.id) for entry in body)
    assert log.id not in {entry["id"] for entry in body}

    filtered = api_client.get(
        reverse("auditlog-list"), {"resource_type": "auth", "action": "login"}
    )
    assert filtered.status_code == 200
    assert all(entry["tenant"] == str(tenant.id) for entry in filtered.json())
