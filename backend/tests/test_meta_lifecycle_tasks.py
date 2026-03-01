from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from integrations.meta_graph import MetaGraphClientError
from integrations.models import PlatformCredential
from integrations.tasks import refresh_meta_credentials_lifecycle


def _create_meta_credential(user, *, account_id: str, auth_mode: str = PlatformCredential.AUTH_MODE_USER_OAUTH):
    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id=account_id,
        auth_mode=auth_mode,
        expires_at=timezone.now() + timedelta(days=30),
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    credential.set_raw_tokens("meta-token", None)
    credential.save()
    return credential


@pytest.mark.django_db
def test_refresh_meta_credentials_lifecycle_validates_tokens(monkeypatch, user):
    credential = _create_meta_credential(user, account_id="act_123")

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            assert input_token == "meta-token"
            return {
                "is_valid": True,
                "expires_at": int((timezone.now() + timedelta(days=30)).timestamp()),
                "issued_at": int(timezone.now().timestamp()),
                "scopes": ["ads_read", "business_management"],
            }

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            raise AssertionError("refresh should not run for long-lived credential")

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())

    result = refresh_meta_credentials_lifecycle.run()
    assert result["processed"] == 1
    assert result["validated"] == 1

    credential.refresh_from_db()
    assert credential.token_status == PlatformCredential.TOKEN_STATUS_VALID
    assert credential.last_validated_at is not None
    assert sorted(credential.granted_scopes) == ["ads_read", "business_management"]


@pytest.mark.django_db
def test_refresh_meta_credentials_lifecycle_refreshes_near_expiry_user_oauth(monkeypatch, user):
    credential = _create_meta_credential(user, account_id="act_123")
    credential.expires_at = timezone.now() + timedelta(hours=1)
    credential.save(update_fields=["expires_at", "updated_at"])

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            return {
                "is_valid": True,
                "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
                "issued_at": int(timezone.now().timestamp()),
            }

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            return type("Token", (), {"access_token": "refreshed-token", "expires_in": 60 * 60 * 24 * 60})()

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())

    result = refresh_meta_credentials_lifecycle.run()
    assert result["refreshed"] == 1

    credential.refresh_from_db()
    assert credential.decrypt_access_token() == "refreshed-token"
    assert credential.last_refresh_attempt_at is not None
    assert credential.last_refreshed_at is not None
    assert credential.token_status == PlatformCredential.TOKEN_STATUS_VALID


@pytest.mark.django_db
def test_refresh_meta_credentials_lifecycle_marks_reauth_when_refresh_fails(monkeypatch, user):
    credential = _create_meta_credential(user, account_id="act_123")
    credential.expires_at = timezone.now() + timedelta(hours=1)
    credential.save(update_fields=["expires_at", "updated_at"])

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def debug_token(self, *, input_token: str):
            return {
                "is_valid": True,
                "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
                "issued_at": int(timezone.now().timestamp()),
            }

        def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str):
            raise MetaGraphClientError("refresh failed")

    monkeypatch.setattr("integrations.tasks.MetaGraphClient.from_settings", lambda: DummyClient())

    result = refresh_meta_credentials_lifecycle.run()
    assert result["processed"] == 1

    credential.refresh_from_db()
    assert credential.token_status == PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED
    assert "refresh failed" in credential.token_status_reason
