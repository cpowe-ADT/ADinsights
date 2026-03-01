from __future__ import annotations

import pytest

from accounts.hooks import send_invitation_email
from accounts.models import Invitation, PasswordResetToken, Role, seed_default_roles
from accounts.tasks import send_password_reset_email


@pytest.mark.django_db
def test_invitation_email_uses_frontend_base_url(user, settings, monkeypatch):
    settings.FRONTEND_BASE_URL = "http://localhost:5175"
    seed_default_roles()
    role = Role.objects.get(name=Role.VIEWER)
    invitation = Invitation.objects.create(
        tenant=user.tenant,
        email="invitee@example.com",
        role=role,
        invited_by=user,
    )

    captured: dict[str, str] = {}

    def _capture_email(payload):  # noqa: ANN001
        captured["body"] = payload.body
        return "sent"

    monkeypatch.setattr("accounts.hooks.send_email", _capture_email)
    send_invitation_email(invitation)

    assert "http://localhost:5175/invite?token=" in captured["body"]


@pytest.mark.django_db
def test_password_reset_email_uses_frontend_base_url(user, settings, monkeypatch):
    settings.FRONTEND_BASE_URL = "http://localhost:5175"
    token, raw_token = PasswordResetToken.issue(user=user)

    captured: dict[str, str] = {}

    def _capture_email(payload):  # noqa: ANN001
        captured["body"] = payload.body
        return "sent"

    monkeypatch.setattr("accounts.tasks.send_email", _capture_email)
    result = send_password_reset_email.run(str(token.id), raw_token)

    assert result == "sent"
    assert "http://localhost:5175/password-reset?token=" in captured["body"]
