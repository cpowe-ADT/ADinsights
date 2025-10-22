from __future__ import annotations

import pytest
from django.utils import timezone

from accounts.models import AuditLog, PasswordResetToken
from accounts.serializers import PasswordResetRequestSerializer


@pytest.mark.django_db
def test_password_reset_request_serializer_rejects_unknown_email(tenant):
    serializer = PasswordResetRequestSerializer(data={"email": "missing@example.com"})

    assert not serializer.is_valid()
    assert "email" in serializer.errors


@pytest.mark.django_db
def test_password_reset_request_dispatches_task_and_logs_audit(api_client, user, monkeypatch):
    captured: dict[str, str] = {}

    def fake_delay(token_id: str, raw_token: str) -> None:
        captured["token_id"] = token_id
        captured["raw_token"] = raw_token

    monkeypatch.setattr(
        "accounts.tasks.send_password_reset_email.delay",
        fake_delay,
        raising=False,
    )

    response = api_client.post(
        "/api/auth/password-reset/",
        {"email": user.email},
        format="json",
    )

    assert response.status_code == 202
    assert captured["token_id"]
    assert captured["raw_token"]

    token = PasswordResetToken.objects.get(id=captured["token_id"])
    assert token.user_id == user.id
    assert token.expires_at > timezone.now()
    assert token.token_hash != captured["raw_token"]

    audit_entry = AuditLog.objects.get(
        action="password_reset_requested", resource_id=str(user.id)
    )
    assert audit_entry.user_id == user.id


@pytest.mark.django_db
def test_password_reset_confirm_sets_new_password_and_logs_audit(api_client, user):
    token, raw_value = PasswordResetToken.issue(user=user)

    response = api_client.post(
        "/api/auth/password-reset/confirm/",
        {"token": raw_value, "password": "new-password-123"},
        format="json",
    )

    assert response.status_code == 204

    user.refresh_from_db()
    assert user.check_password("new-password-123")

    token.refresh_from_db()
    assert token.used_at is not None

    audit_entry = AuditLog.objects.get(
        action="password_reset_completed", resource_id=str(user.id)
    )
    assert audit_entry.user_id == user.id
