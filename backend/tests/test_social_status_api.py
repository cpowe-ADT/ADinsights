from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from django.urls import reverse

from accounts.models import AuditLog
from integrations.models import AirbyteConnection, MetaAccountSyncState, PlatformCredential


def _authenticate(api_client, user) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": "user@example.com", "password": "password123"},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _create_meta_credential(user, account_id: str = "act_123") -> PlatformCredential:
    credential = PlatformCredential.objects.create(
        tenant=user.tenant,
        provider=PlatformCredential.META,
        account_id=account_id,
        expires_at=None,
        access_token_enc=b"",
        access_token_nonce=b"",
        access_token_tag=b"",
    )
    credential.set_raw_tokens("meta-token", None)
    credential.save()
    return credential


def _create_meta_connection(user, *, is_active: bool = True, last_synced_at=None, last_job_status: str = ""):
    return AirbyteConnection.objects.create(
        tenant=user.tenant,
        name="Meta connection",
        connection_id=uuid.uuid4(),
        provider=PlatformCredential.META,
        schedule_type=AirbyteConnection.SCHEDULE_CRON,
        cron_expression="0 6-22 * * *",
        is_active=is_active,
        last_synced_at=last_synced_at,
        last_job_status=last_job_status,
        last_job_updated_at=last_synced_at,
    )


def _platform(payload, name: str):
    return next(item for item in payload["platforms"] if item["platform"] == name)


@pytest.mark.django_db
def test_social_status_not_connected_without_meta_credential(api_client, user):
    _authenticate(api_client, user)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "meta")["status"] == "not_connected"
    assert _platform(payload, "instagram")["status"] == "not_connected"


@pytest.mark.django_db
def test_social_status_started_not_complete_with_credential_only(api_client, user):
    _authenticate(api_client, user)
    _create_meta_credential(user)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "meta")["status"] == "started_not_complete"
    assert _platform(payload, "instagram")["status"] == "started_not_complete"


@pytest.mark.django_db
def test_social_status_complete_when_connection_is_inactive(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    _create_meta_credential(user)
    _create_meta_connection(
        user,
        is_active=False,
        last_synced_at=timezone.now() - timedelta(hours=3),
        last_job_status="succeeded",
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "meta")["status"] == "complete"


@pytest.mark.django_db
def test_social_status_active_when_connection_recent_success(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    _create_meta_credential(user)
    _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "meta")["status"] == "active"


@pytest.mark.django_db
def test_social_status_instagram_active_when_linked_and_meta_active(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    credential = _create_meta_credential(user)
    _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    AuditLog.objects.create(
        tenant=user.tenant,
        user=user,
        action="meta_oauth_connected",
        resource_type="platform_credential",
        resource_id=str(credential.id),
        metadata={"instagram_account_id": "ig-1"},
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "instagram")["status"] == "active"


@pytest.mark.django_db
def test_social_status_is_tenant_isolated(api_client, user):
    _authenticate(api_client, user)

    _create_meta_credential(user, account_id="act_123")

    from accounts.models import Tenant, User

    other_tenant = Tenant.objects.create(name="Other tenant")
    other_user = User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
    )
    other_user.set_password("password123")
    other_user.save()
    _create_meta_credential(other_user, account_id="act_999")
    _create_meta_connection(
        other_user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=5),
        last_job_status="succeeded",
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["metadata"]["credential_account_id"] == "act_123"


@pytest.mark.django_db
def test_social_status_uses_instagram_link_for_selected_meta_credential(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    old_credential = _create_meta_credential(user, account_id="act_123")
    AuditLog.objects.create(
        tenant=user.tenant,
        user=user,
        action="meta_oauth_connected",
        resource_type="platform_credential",
        resource_id=str(old_credential.id),
        metadata={"instagram_account_id": "ig-legacy"},
    )

    # Most recent credential should drive status selection.
    _create_meta_credential(user, account_id="act_456")

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    assert _platform(payload, "meta")["metadata"]["credential_account_id"] == "act_456"
    assert _platform(payload, "instagram")["status"] == "started_not_complete"


@pytest.mark.django_db
def test_social_status_includes_meta_sync_state_metadata(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    _create_meta_credential(user, account_id="act_123")
    _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        last_job_id="job-1",
        last_job_status="succeeded",
        last_job_error="",
        last_success_at=timezone.now() - timedelta(minutes=5),
    )

    response = api_client.get(reverse("social-connection-status"))
    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["metadata"]["sync_state_last_job_status"] == "succeeded"
    assert meta["metadata"]["sync_state_last_success_at"] is not None
