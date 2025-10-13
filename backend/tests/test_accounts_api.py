from __future__ import annotations

import pytest

from accounts.models import AuditLog, Invitation, Role, Tenant, User, assign_role


@pytest.mark.django_db
def test_tenant_signup_creates_admin(api_client):
    payload = {
        "name": "Acme Corp",
        "admin_email": "owner@acme.com",
        "admin_password": "supersecret",
        "admin_first_name": "Ada",
        "admin_last_name": "Lovelace",
    }

    response = api_client.post("/api/tenants/", payload, format="json")

    assert response.status_code == 201
    data = response.json()

    tenant = Tenant.objects.get(id=data["id"])
    admin_user = User.objects.get(id=data["admin_user_id"])

    assert admin_user.tenant_id == tenant.id
    assert admin_user.check_password(payload["admin_password"])
    assert admin_user.user_roles.filter(role__name=Role.ADMIN).exists()


@pytest.mark.django_db
def test_tenant_signup_seeds_default_roles(api_client):
    Role.objects.all().delete()

    payload = {
        "name": "Beta LLC",
        "admin_email": "admin@beta.com",
        "admin_password": "changeme123",
    }

    response = api_client.post("/api/tenants/", payload, format="json")

    assert response.status_code == 201
    role_names = set(Role.objects.values_list("name", flat=True))
    assert role_names.issuperset({Role.ADMIN, Role.ANALYST, Role.VIEWER})


@pytest.mark.django_db
def test_user_list_scoped_to_tenant(api_client):
    tenant_one = Tenant.objects.create(name="Tenant One")
    tenant_two = Tenant.objects.create(name="Tenant Two")

    admin = User.objects.create_user(
        username="admin@one.com", email="admin@one.com", tenant=tenant_one
    )
    admin.set_password("password123")
    admin.save()
    assign_role(admin, Role.ADMIN)

    User.objects.create_user(
        username="alice@one.com",
        email="alice@one.com",
        tenant=tenant_one,
    )
    User.objects.create_user(
        username="bob@two.com",
        email="bob@two.com",
        tenant=tenant_two,
    )

    api_client.force_authenticate(user=admin)
    response = api_client.get("/api/users/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert emails == {"admin@one.com", "alice@one.com"}


@pytest.mark.django_db
def test_viewer_cannot_assign_roles(api_client):
    tenant = Tenant.objects.create(name="Restricted Tenant")

    admin = User.objects.create_user(
        username="admin@tenant.com", email="admin@tenant.com", tenant=tenant
    )
    admin.set_password("password123")
    admin.save()
    assign_role(admin, Role.ADMIN)

    viewer = User.objects.create_user(
        username="viewer@tenant.com", email="viewer@tenant.com", tenant=tenant
    )
    viewer.set_password("password123")
    viewer.save()
    assign_role(viewer, Role.VIEWER)

    api_client.force_authenticate(user=viewer)
    response = api_client.post(
        "/api/roles/assign/",
        {"user": str(viewer.id), "role": Role.ANALYST},
        format="json",
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_assign_role_records_audit_log(api_client):
    tenant = Tenant.objects.create(name="Role Tenant")

    admin = User.objects.create_user(
        username="admin@role.com", email="admin@role.com", tenant=tenant
    )
    admin.set_password("password123")
    admin.save()
    assign_role(admin, Role.ADMIN)

    teammate = User.objects.create_user(
        username="analyst@role.com", email="analyst@role.com", tenant=tenant
    )

    api_client.force_authenticate(user=admin)
    response = api_client.post(
        "/api/roles/assign/",
        {"user": str(teammate.id), "role": Role.ANALYST},
        format="json",
    )
    api_client.force_authenticate(user=None)

    assert response.status_code == 201
    teammate.refresh_from_db()
    assert teammate.user_roles.filter(role__name=Role.ANALYST).exists()

    audit_entry = AuditLog.objects.get(
        action="role_assigned", resource_id=str(teammate.id)
    )
    assert audit_entry.action == "role_assigned"
    assert audit_entry.resource_type == "role"
    assert audit_entry.metadata == {"role": Role.ANALYST}
    assert audit_entry.user_id == admin.id


@pytest.mark.django_db
def test_invitation_flow(api_client):
    tenant = Tenant.objects.create(name="Invite Tenant")
    admin = User.objects.create_user(
        username="admin@invite.com", email="admin@invite.com", tenant=tenant
    )
    admin.set_password("password123")
    admin.save()
    assign_role(admin, Role.ADMIN)

    api_client.force_authenticate(user=admin)
    invite_response = api_client.post(
        f"/api/tenants/{tenant.id}/invite/",
        {"email": "newhire@example.com", "role": Role.ANALYST},
        format="json",
    )
    api_client.force_authenticate(user=None)

    assert invite_response.status_code == 201
    invite_data = invite_response.json()
    token = invite_data["token"]

    accept_payload = {
        "token": token,
        "password": "onboarding123",
        "first_name": "New",
        "last_name": "Hire",
    }

    accept_response = api_client.post(
        "/api/users/accept-invite/", accept_payload, format="json"
    )

    assert accept_response.status_code == 201
    user = User.objects.get(email="newhire@example.com", tenant=tenant)
    assert user.user_roles.filter(role__name=Role.ANALYST).exists()

    invitation = Invitation.objects.get(token=token)
    assert invitation.accepted_at is not None
