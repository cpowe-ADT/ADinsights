from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from django.db import OperationalError
from django.utils import timezone
from django.urls import reverse

from adapters.warehouse import WAREHOUSE_SNAPSHOT_STATUS_FETCHED, WAREHOUSE_SNAPSHOT_STATUS_KEY
from accounts.models import AuditLog
from analytics.models import TenantMetricsSnapshot
from integrations.models import AirbyteConnection, MetaAccountSyncState, PlatformCredential
from integrations.models import MetaConnection, MetaPage


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


def _create_meta_page_connection(user, *, scopes: list[str] | None = None) -> MetaConnection:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id=f"page-insights-{user.id}",
        scopes=scopes
        or [
            "ads_read",
            "business_management",
            "pages_show_list",
            "pages_read_engagement",
        ],
        is_active=True,
    )
    connection.set_raw_token("page-insights-token")
    connection.save()
    return connection


def _create_meta_page(user, connection: MetaConnection, *, page_id: str = "page-1") -> MetaPage:
    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id=page_id,
        name="Business Page",
        can_analyze=True,
        is_default=True,
        tasks=["ANALYZE"],
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


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
def test_social_status_reports_page_insights_connection_without_marketing_credential(api_client, user):
    _authenticate(api_client, user)
    page_connection = _create_meta_page_connection(user)
    _create_meta_page(user, page_connection)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "started_not_complete"
    assert meta["reason"]["code"] == "orphaned_marketing_access"
    assert meta["metadata"]["has_credential"] is False
    assert meta["metadata"]["has_marketing_credential"] is False
    assert meta["metadata"]["has_page_insights_connection"] is True
    assert meta["metadata"]["has_recoverable_marketing_access"] is True
    assert meta["metadata"]["marketing_recovery_source"] == "existing_meta_connection"


@pytest.mark.django_db
def test_social_status_reports_page_insights_permission_gap_without_marketing_credential(api_client, user):
    _authenticate(api_client, user)
    page_connection = _create_meta_page_connection(
        user,
        scopes=["pages_read_engagement"],
    )
    _create_meta_page(user, page_connection)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "started_not_complete"
    assert meta["reason"]["code"] == "page_insights_permissions_missing"
    assert "pages_show_list" in meta["reason"]["message"]


@pytest.mark.django_db
def test_social_status_reports_marketing_permission_gap_without_marketing_credential(api_client, user):
    _authenticate(api_client, user)
    page_connection = _create_meta_page_connection(
        user,
        scopes=["pages_show_list", "pages_read_engagement"],
    )
    _create_meta_page(user, page_connection)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "started_not_complete"
    assert meta["reason"]["code"] == "marketing_permissions_missing"
    assert "business_management" in meta["reason"]["message"]
    assert meta["metadata"]["has_recoverable_marketing_access"] is False


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
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-1",
        last_job_status="succeeded",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=12,
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "active"
    assert meta["metadata"]["has_recoverable_marketing_access"] is False
    assert meta["metadata"]["marketing_recovery_source"] is None


@pytest.mark.django_db
def test_social_status_keeps_direct_sync_active_before_next_local_sync_window(
    api_client,
    user,
    settings,
    monkeypatch,
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    fixed_now = timezone.make_aware(datetime(2026, 4, 5, 0, 30))
    monkeypatch.setattr("integrations.views.timezone.now", lambda: fixed_now)

    _create_meta_credential(user)
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=fixed_now - timedelta(hours=7),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-overnight-grace",
        last_job_status="succeeded",
        last_success_at=fixed_now - timedelta(hours=7),
        last_window_end=timezone.localdate(fixed_now) - timedelta(days=2),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=11,
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    meta = _platform(response.json(), "meta")
    assert meta["status"] == "active"
    assert meta["reason"]["code"] == "active_direct_sync"


@pytest.mark.django_db
def test_social_status_reports_live_reporting_disabled_when_meta_sync_is_healthy(
    api_client,
    user,
    settings,
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    _create_meta_credential(user)
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-healthy",
        last_job_status="succeeded",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=7,
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    meta = _platform(response.json(), "meta")
    assert meta["reporting_readiness"]["stage"] == "live_reporting_disabled"
    assert meta["reporting_readiness"]["warehouse_status"] == "disabled"
    assert meta["reporting_readiness"]["dataset_live_reason"] == "adapter_disabled"
    assert meta["metadata"]["dataset_status"]["warehouse_adapter_enabled"] is False


@pytest.mark.django_db
def test_social_status_reports_waiting_for_first_snapshot_when_direct_sync_is_complete(
    api_client,
    user,
    settings,
):
    _authenticate(api_client, user)
    settings.ENABLE_WAREHOUSE_ADAPTER = True
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    _create_meta_credential(user)
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-healthy",
        last_job_status="succeeded",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=7,
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    meta = _platform(response.json(), "meta")
    assert meta["reporting_readiness"]["stage"] == "waiting_for_warehouse_snapshot"
    assert meta["reporting_readiness"]["warehouse_status"] == "waiting_snapshot"
    assert meta["reporting_readiness"]["dataset_live_reason"] == "missing_snapshot"


@pytest.mark.django_db
def test_social_status_reports_live_reporting_ready_when_snapshot_exists(api_client, user, settings):
    _authenticate(api_client, user)
    settings.ENABLE_WAREHOUSE_ADAPTER = True
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"

    _create_meta_credential(user)
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-healthy",
        last_job_status="succeeded",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=7,
    )
    TenantMetricsSnapshot.objects.create(
        tenant=user.tenant,
        source="warehouse",
        payload={
            "campaign": {"summary": {"currency": "USD"}},
            WAREHOUSE_SNAPSHOT_STATUS_KEY: WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
        },
        generated_at=timezone.now(),
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    meta = _platform(response.json(), "meta")
    assert meta["reporting_readiness"]["stage"] == "live_reporting_ready"
    assert meta["reporting_readiness"]["warehouse_status"] == "ready"
    assert meta["reporting_readiness"]["dataset_live_reason"] == "ready"


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
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-direct-2",
        last_job_status="succeeded",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=8,
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
def test_social_status_instagram_contract_routes_back_to_meta_setup(api_client, user):
    _authenticate(api_client, user)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    instagram = _platform(response.json(), "instagram")
    assert instagram["actions"] == ["open_meta_setup"]
    assert instagram["metadata"]["standalone_oauth_supported"] is False
    assert instagram["metadata"]["connection_contract"] == "linked_via_meta_setup"


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
def test_social_status_prefers_connection_linked_valid_credential_over_newer_reauth_record(
    api_client, user, settings
):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    active_credential = _create_meta_credential(user, account_id="act_123")
    active_connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=active_connection,
        last_job_id="job-1",
        last_job_status="succeeded",
        last_job_error="",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=5,
    )

    stale_credential = _create_meta_credential(user, account_id="act_999")
    stale_credential.token_status = PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED
    stale_credential.token_status_reason = "Meta credential needs to be re-authorized."
    stale_credential.save(update_fields=["token_status", "token_status_reason", "updated_at"])

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "active"
    assert meta["metadata"]["credential_account_id"] == active_credential.account_id


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


@pytest.mark.django_db
def test_social_status_reports_no_recent_reportable_data(api_client, user, settings):
    _authenticate(api_client, user)
    settings.META_APP_ID = "meta-app-id"
    settings.META_APP_SECRET = "meta-app-secret"
    settings.META_LOGIN_CONFIG_ID = "2323589144820085"
    settings.META_OAUTH_REDIRECT_URI = "http://localhost:5173/dashboards/data-sources"
    settings.AIRBYTE_DEFAULT_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    settings.AIRBYTE_DEFAULT_DESTINATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    _create_meta_credential(user, account_id="act_123")
    connection = _create_meta_connection(
        user,
        is_active=True,
        last_synced_at=timezone.now() - timedelta(minutes=10),
        last_job_status="succeeded",
    )
    MetaAccountSyncState.objects.create(
        tenant=user.tenant,
        account_id="act_123",
        connection=connection,
        last_job_id="job-no-data",
        last_job_status="succeeded",
        last_job_error="",
        last_success_at=timezone.now() - timedelta(minutes=5),
        last_window_start=timezone.localdate() - timedelta(days=89),
        last_window_end=timezone.localdate() - timedelta(days=1),
        last_sync_engine=MetaAccountSyncState.SYNC_ENGINE_DIRECT,
        last_rows_synced=0,
    )

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 200
    payload = response.json()
    meta = _platform(payload, "meta")
    assert meta["status"] == "complete"
    assert meta["reason"]["code"] == "no_recent_reportable_data"


@pytest.mark.django_db
def test_social_status_returns_schema_out_of_date_when_db_is_behind(api_client, user, monkeypatch):
    _authenticate(api_client, user)

    def _raise_schema_error(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OperationalError("no such column: integrations_platformcredential.auth_mode")

    monkeypatch.setattr("integrations.views.PlatformCredential.objects.filter", _raise_schema_error)

    response = api_client.get(reverse("social-connection-status"))

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "schema_out_of_date"
    assert "Run backend migrations" in payload["detail"]
