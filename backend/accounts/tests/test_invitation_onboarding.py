from __future__ import annotations

import pytest

from accounts.models import Invitation, Role, Tenant, User, assign_role, seed_default_roles


def _create_admin_user(*, tenant: Tenant, email: str, password: str = "password123") -> User:
    user = User.objects.create_user(
        username=email,
        email=email,
        tenant=tenant,
        password=password,
    )
    assign_role(user, Role.ADMIN)
    return user


@pytest.mark.django_db
def test_admin_can_resend_invitation_and_complete_onboarding(api_client):
    seed_default_roles()
    tenant = Tenant.objects.create(name="Flow Tenant")
    admin = _create_admin_user(tenant=tenant, email="admin@flow.com")

    api_client.force_authenticate(user=admin)

    invite_response = api_client.post(
        "/api/users/invite/",
        {"email": "hire@flow.com", "role": Role.ANALYST},
        format="json",
    )
    assert invite_response.status_code == 201
    invite_payload = invite_response.json()

    invitation_id = invite_payload["id"]
    initial_token = invite_payload["token"]

    resend_response = api_client.post(
        "/api/users/invite/resend/",
        {"invitation_id": invitation_id},
        format="json",
    )
    assert resend_response.status_code == 200
    resend_payload = resend_response.json()

    assert resend_payload["id"] == invitation_id
    refreshed_token = resend_payload["token"]
    assert refreshed_token != initial_token

    api_client.force_authenticate(user=None)
    accept_response = api_client.post(
        "/api/users/accept-invite/",
        {
            "token": refreshed_token,
            "password": "onboarding123",
            "first_name": "Flow",
            "last_name": "Teammate",
        },
        format="json",
    )
    assert accept_response.status_code == 201

    onboarded = User.objects.get(email="hire@flow.com", tenant=tenant)
    assert onboarded.user_roles.filter(role__name=Role.ANALYST).exists()

    invitation = Invitation.objects.get(id=invitation_id)
    assert invitation.accepted_at is not None


@pytest.mark.django_db
def test_resend_invitation_rejected_for_other_tenant(api_client):
    seed_default_roles()
    tenant_alpha = Tenant.objects.create(name="Alpha")
    tenant_beta = Tenant.objects.create(name="Beta")

    admin_alpha = _create_admin_user(tenant=tenant_alpha, email="alpha@tenant.com")

    admin_beta = _create_admin_user(tenant=tenant_beta, email="beta@tenant.com")

    role = Role.objects.get(name=Role.VIEWER)
    foreign_invitation = Invitation.objects.create(
        tenant=tenant_beta,
        email="outsider@example.com",
        role=role,
        invited_by=admin_beta,
    )
    original_token = foreign_invitation.token

    api_client.force_authenticate(user=admin_alpha)
    resend_response = api_client.post(
        "/api/users/invite/resend/",
        {"invitation_id": str(foreign_invitation.id)},
        format="json",
    )
    assert resend_response.status_code == 400
    assert resend_response.json()["invitation_id"] == ["Invitation not found."]

    foreign_invitation.refresh_from_db()
    # Token remains unchanged when the request is rejected.
    assert foreign_invitation.token == original_token
