from __future__ import annotations

import uuid
from urllib.parse import parse_qs

import httpx
import pytest
from django.utils import timezone

from accounts.models import Tenant, User
from content_ops.assets import (
    ASSET_PUBLISH_FILE_MISSING,
    ASSET_PUBLISH_PUBLIC_URL_MISSING,
    ASSET_PUBLISH_PUBLIC_URL_NOT_FETCHABLE,
)
from content_ops.facebook_graph import FacebookGraphPageClient, FacebookGraphPagePublisher
from content_ops.instagram_graph import InstagramGraphClient, InstagramGraphPublisher
from content_ops.models import (
    ContentDraft,
    ContentDraftVersion,
    ContentSchedule,
    ContentWorkspace,
    MediaAsset,
    PublishedPost,
    PublishingIdentity,
    PublishAttempt,
)
from integrations.models import MetaConnection, MetaPage
from content_ops.publisher import (
    FacebookPagePublishError,
    FacebookPagePublishPayload,
    FacebookPagePublishResult,
    InstagramMediaContainerPayload,
    InstagramMediaContainerResult,
    InstagramMediaContainerStatusResult,
    InstagramMediaPublishResult,
    InstagramPublishError,
    PREFLIGHT_APPROVAL_SNAPSHOT_MISSING,
    PREFLIGHT_ATTEMPT_MISSING,
    PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
    PREFLIGHT_ATTEMPT_WRONG_TENANT,
    PREFLIGHT_CLIENT_APPROVAL_MISSING,
    PREFLIGHT_CONTENT_MISSING,
    PREFLIGHT_FACEBOOK_PAGE_PUBLISHING_NOT_READY,
    PREFLIGHT_INSTAGRAM_MEDIA_REQUIRED,
    PREFLIGHT_INSTAGRAM_PUBLISHING_NOT_READY,
    PREFLIGHT_PUBLISHING_IDENTITY_MISSING,
    PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY,
    PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT,
    PREFLIGHT_SCHEDULE_VERSION_STALE,
    PREFLIGHT_UNSUPPORTED_CHANNEL,
    PROCESS_STATUS_FAILED,
    PROCESS_STATUS_NOOP,
    PROCESS_STATUS_PUBLISHED,
    PROVIDER_MAX_ATTEMPTS_EXCEEDED,
    PROVIDER_CONTAINER_EXPIRED,
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_RETRYABLE_ERROR,
    PROVIDER_TERMINAL_ERROR,
    preflight_facebook_page_attempt,
    preflight_instagram_attempt,
    process_due_publish_attempts,
    process_facebook_page_publish_attempt,
    process_instagram_publish_attempt,
    requeue_due_retryable_attempts,
    requeue_failed_publish_attempt,
)
from content_ops.tasks import (
    process_content_publish_attempt,
    process_due_content_publish_attempts,
    requeue_due_content_publish_attempts,
)


@pytest.mark.django_db
def test_facebook_page_preflight_succeeds_for_ready_attempt(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is True
    assert result.failure_code == ""
    assert result.channel == PublishAttempt.CHANNEL_FACEBOOK_PAGE
    assert result.attempt_id == str(attempt.id)
    assert result.publishing_identity_id == str(attempt.publishing_identity_id)


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_missing_attempt(tenant):
    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id="00000000-0000-0000-0000-000000000000",
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_ATTEMPT_MISSING


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_wrong_tenant(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    attempt = _publish_attempt_graph(tenant=tenant)

    result = preflight_facebook_page_attempt(
        tenant=other_tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_ATTEMPT_WRONG_TENANT


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_unsupported_channel(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_UNSUPPORTED_CHANNEL


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_non_publishable_attempt_state(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_BLOCKED,
    )

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_stale_schedule_version(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    new_version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=attempt.draft,
        version_number=2,
        caption="New active version",
    )
    attempt.draft.active_version = new_version
    attempt.draft.save(update_fields=["active_version", "updated_at"])

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_SCHEDULE_VERSION_STALE


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_missing_approval_records(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        approval_snapshot={"version_id": None},
    )
    attempt.schedule.approval_snapshot = {
        "version_id": str(attempt.version_id),
    }
    attempt.schedule.save(update_fields=["approval_snapshot", "updated_at"])

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_APPROVAL_SNAPSHOT_MISSING


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_missing_client_approval(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        approval_snapshot={
            "approvals": [
                {"reviewer_type": "internal", "status": "approved"},
            ],
        },
    )

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_CLIENT_APPROVAL_MISSING


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_missing_identity(tenant):
    attempt = _publish_attempt_graph(tenant=tenant, with_identity=False)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_PUBLISHING_IDENTITY_MISSING


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_cross_tenant_identity(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    attempt = _publish_attempt_graph(tenant=tenant)
    other_identity = _publishing_identity(tenant=other_tenant)
    attempt.publishing_identity = other_identity
    attempt.save(update_fields=["publishing_identity", "updated_at"])

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_identity_not_ready(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        identity_readiness=PublishingIdentity.READINESS_NEEDS_REAUTH,
    )

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_readiness_axis_not_ready(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness={
            "facebook_page_publishing": {
                "state": "blocked",
                "reason": "missing_publishing_permissions",
            }
        },
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_FACEBOOK_PAGE_PUBLISHING_NOT_READY


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_missing_caption_content(tenant):
    attempt = _publish_attempt_graph(tenant=tenant, caption="")

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_CONTENT_MISSING


@pytest.mark.django_db
def test_facebook_page_preflight_accepts_attached_media_with_public_url(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(tenant=tenant)
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": "https://cdn.example.com/content/image.png"},
    )
    attempt.version.media_assets.add(asset)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is True
    assert result.failure_code == ""


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_media_without_public_url(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(tenant=tenant)
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={},
    )
    attempt.version.media_assets.add(asset)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == ASSET_PUBLISH_PUBLIC_URL_MISSING
    assert "https" in result.failure_detail_safe.lower()
    assert "cdn.example.com" not in result.failure_detail_safe


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_media_with_private_url(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(tenant=tenant)
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": "http://localhost/content/image.png"},
    )
    attempt.version.media_assets.add(asset)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == ASSET_PUBLISH_PUBLIC_URL_NOT_FETCHABLE
    assert "localhost" not in result.failure_detail_safe


@pytest.mark.django_db
def test_facebook_page_preflight_blocks_media_with_missing_storage_file(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(tenant=tenant)
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": "https://cdn.example.com/content/image.png"},
        write_file=False,
    )
    attempt.version.media_assets.add(asset)

    result = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == ASSET_PUBLISH_FILE_MISSING


@pytest.mark.django_db
def test_instagram_preflight_succeeds_for_ready_media_attempt(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)

    result = preflight_instagram_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_combined_ready_readiness(),
    )

    assert result.ready is True
    assert result.failure_code == ""


@pytest.mark.django_db
def test_instagram_preflight_blocks_missing_readiness_axis(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )

    result = preflight_instagram_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_INSTAGRAM_PUBLISHING_NOT_READY


@pytest.mark.django_db
def test_instagram_preflight_requires_one_media_asset(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )

    result = preflight_instagram_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_combined_ready_readiness(),
    )

    assert result.ready is False
    assert result.failure_code == PREFLIGHT_INSTAGRAM_MEDIA_REQUIRED


@pytest.mark.django_db
def test_process_instagram_attempt_creates_polls_and_publishes_container(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    publisher = _FakeInstagramPublisher(statuses=["FINISHED"])

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    published = PublishedPost.all_objects.get(draft=attempt.draft)
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_container_id == "ig-container-1"
    assert attempt.meta_post_id == "ig-media-1"
    assert published.channel == PublishedPost.CHANNEL_INSTAGRAM
    assert publisher.container_payloads[0].ig_user_id.startswith("ig_")
    assert publisher.container_payloads[0].media_url == "https://cdn.example.com/image.png"


@pytest.mark.django_db
def test_process_instagram_attempt_leaves_container_pending_until_finished(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    publisher = _FakeInstagramPublisher(statuses=["IN_PROGRESS", "FINISHED"])

    first = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_combined_ready_readiness(),
    )
    attempt.refresh_from_db()
    assert first.status == "queued"
    assert attempt.state == PublishAttempt.STATE_CONTAINER_PENDING
    assert attempt.meta_container_id == "ig-container-1"

    second = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert second.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert len(publisher.container_payloads) == 1
    assert publisher.status_checks == [
        (attempt.publishing_identity.ig_user_id, "ig-container-1"),
        (attempt.publishing_identity.ig_user_id, "ig-container-1"),
    ]


@pytest.mark.django_db
def test_process_instagram_attempt_marks_expired_container(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
        state=PublishAttempt.STATE_CONTAINER_PENDING,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    attempt.meta_container_id = "expired-container"
    attempt.meta_container_created_at = now - timezone.timedelta(hours=24)
    attempt.save(
        update_fields=["meta_container_id", "meta_container_created_at", "updated_at"]
    )

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=_FakeInstagramPublisher(statuses=["FINISHED"]),
        readiness=_combined_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_CONTAINER_EXPIRED
    assert attempt.failure_code == PROVIDER_CONTAINER_EXPIRED


@pytest.mark.django_db
def test_process_instagram_attempt_records_retryable_container_error(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=_FakeInstagramPublisher(statuses=["ERROR"]),
        readiness=_combined_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == "instagram_container_error"
    assert attempt.next_retry_at is not None


@pytest.mark.django_db
def test_process_instagram_attempt_records_retryable_container_create_error(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=_FailingInstagramPublisher(fail_on="create"),
        readiness=_combined_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == "instagram_create_retryable"
    assert attempt.meta_container_id == ""
    assert attempt.attempt_count == 1
    assert attempt.next_retry_at is not None


@pytest.mark.django_db
def test_process_instagram_attempt_records_retryable_publish_error(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    publisher = _FailingInstagramPublisher(fail_on="publish")

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_combined_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == "instagram_publish_retryable"
    assert attempt.meta_container_id == "ig-container-1"
    assert publisher.publish_calls == [
        (attempt.publishing_identity.ig_user_id, "ig-container-1")
    ]
    assert attempt.next_retry_at is not None


@pytest.mark.django_db
def test_process_instagram_attempt_provider_error_details_are_secret_safe(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    publisher = _FailingInstagramPublisher(
        fail_on="publish",
        detail_safe="bearer meta-access-token raw_response refresh_token",
    )

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == "instagram_publish_retryable"
    assert attempt.failure_detail_safe == "Publishing failed with a provider error."
    rendered = str(result.as_dict()).lower()
    forbidden_fragments = {
        "access_token",
        "authorization",
        "bearer",
        "meta-access-token",
        "raw_response",
        "refresh_token",
        "secret",
    }
    assert not any(fragment in rendered for fragment in forbidden_fragments)


@pytest.mark.django_db
def test_process_instagram_attempt_without_publisher_fails_closed(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_NOT_CONFIGURED
    assert attempt.meta_container_id == ""
    assert "access_token" not in attempt.failure_detail_safe.lower()
    assert "secret" not in attempt.failure_detail_safe.lower()


@pytest.mark.django_db
def test_process_instagram_attempt_with_graph_publisher_creates_polls_and_publishes(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    _meta_page_for_attempt(attempt=attempt, tenant=tenant, token="page-live-token")
    graph_client = _FakeInstagramGraphClient(statuses=["FINISHED"])

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=InstagramGraphPublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_container_id == "ig-container-1"
    assert attempt.meta_post_id == "ig-media-1"
    assert graph_client.calls == [
        {
            "operation": "create",
            "ig_user_id": attempt.publishing_identity.ig_user_id,
            "media_url": "https://cdn.example.com/image.png",
            "caption": "Approved Facebook Page caption",
            "media_type": "image/png",
            "access_token": "user-token",
        },
        {
            "operation": "status",
            "container_id": "ig-container-1",
            "access_token": "user-token",
        },
        {
            "operation": "publish",
            "ig_user_id": attempt.publishing_identity.ig_user_id,
            "container_id": "ig-container-1",
            "access_token": "user-token",
        },
    ]


def test_instagram_graph_client_uses_bearer_token_not_url_or_body():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": "ig-container-123"})
        if request.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "ig-media-123"})
        return httpx.Response(
            200,
            json={"status_code": "FINISHED", "status": "Finished"},
        )

    client = InstagramGraphClient(graph_version="v24.0")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    create_result = client.create_media_container(
        ig_user_id="ig_123",
        media_url="https://cdn.example.com/image.png",
        caption="Approved post",
        media_type="image/png",
        access_token="ig-live-token",
    )
    status_result = client.get_media_container_status(
        container_id=create_result.container_id,
        access_token="ig-live-token",
    )
    publish_result = client.publish_media_container(
        ig_user_id="ig_123",
        container_id=create_result.container_id,
        access_token="ig-live-token",
    )

    client.close()
    assert create_result.container_id == "ig-container-123"
    assert status_result.status_code == "FINISHED"
    assert publish_result.media_id == "ig-media-123"
    assert [request.method for request in captured] == ["POST", "GET", "POST"]
    assert [request.url.path for request in captured] == [
        "/v24.0/ig_123/media",
        "/v24.0/ig-container-123",
        "/v24.0/ig_123/media_publish",
    ]
    for request in captured:
        assert request.headers["authorization"] == "Bearer ig-live-token"
        assert "ig-live-token" not in str(request.url)
        assert b"ig-live-token" not in request.content


@pytest.mark.django_db
def test_instagram_graph_publisher_rejects_cross_tenant_page_token(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    other_tenant = Tenant.objects.create(name="Other Tenant")
    _meta_page_for_attempt(
        attempt=attempt,
        tenant=other_tenant,
        token="other-tenant-token",
    )
    graph_client = _FakeInstagramGraphClient(statuses=["FINISHED"])

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=InstagramGraphPublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_TERMINAL_ERROR
    assert graph_client.calls == []
    assert "other-tenant-token" not in attempt.failure_detail_safe


@pytest.mark.django_db
def test_instagram_graph_publisher_retryable_error_is_safe(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    _meta_page_for_attempt(attempt=attempt, tenant=tenant, token="page-live-token")
    graph_client = _FailingInstagramGraphClient(
        detail="rate limited bearer user-token raw_response",
        retryable=True,
    )

    result = process_instagram_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=InstagramGraphPublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == PROVIDER_RETRYABLE_ERROR
    assert attempt.failure_detail_safe == "Publishing failed with a provider error."
    rendered = str(result.as_dict()).lower()
    assert "user-token" not in rendered
    assert "raw_response" not in rendered


@pytest.mark.django_db
def test_facebook_page_preflight_failure_details_are_secret_safe(tenant):
    attempts = [
        _publish_attempt_graph(tenant=tenant, with_identity=False),
        _publish_attempt_graph(tenant=tenant, caption=""),
        _publish_attempt_graph(
            tenant=tenant,
            identity_readiness=PublishingIdentity.READINESS_NEEDS_REAUTH,
        ),
    ]

    results = [
        preflight_facebook_page_attempt(
            tenant=tenant,
            attempt_id=attempt.id,
            readiness={
                "facebook_page_publishing": {
                    "state": "blocked",
                    "reason": "missing_publishing_permissions",
                }
            },
        )
        for attempt in attempts
    ]

    forbidden_fragments = {
        "access_token",
        "authorization",
        "bearer",
        "meta-access-token",
        "page-token",
        "raw_response",
        "refresh_token",
        "secret",
    }
    for result in results:
        rendered = str(result.as_dict()).lower()
        assert result.ready is False
        assert forbidden_fragments.isdisjoint(rendered.split())
        assert not any(fragment in rendered for fragment in forbidden_fragments)


@pytest.mark.django_db
def test_process_facebook_page_attempt_with_fake_publisher_creates_published_post(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    publisher = _FakePublisher(meta_post_id="fb_post_123")

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_ready_readiness(),
        now=timezone.now(),
    )

    attempt.refresh_from_db()
    attempt.schedule.refresh_from_db()
    attempt.draft.refresh_from_db()
    published_post = PublishedPost.all_objects.get(id=result.published_post_id)
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_post_id == "fb_post_123"
    assert attempt.failure_code == ""
    assert attempt.attempt_count == 1
    assert attempt.schedule.state == ContentSchedule.STATE_PUBLISHED
    assert attempt.draft.state == ContentDraft.STATE_PUBLISHED
    assert published_post.meta_post_id == "fb_post_123"
    assert published_post.draft_id == attempt.draft_id
    assert publisher.payloads[0].caption == "Approved Facebook Page caption"


@pytest.mark.django_db
def test_process_facebook_page_attempt_without_publisher_fails_closed(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_NOT_CONFIGURED
    assert "access_token" not in attempt.failure_detail_safe.lower()


@pytest.mark.django_db
def test_process_facebook_page_attempt_with_graph_publisher_posts_safely(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    _meta_page_for_attempt(attempt=attempt, tenant=tenant, token="page-live-token")
    graph_client = _FakeFacebookGraphClient(post_id="page_post_123")

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=FacebookGraphPagePublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_post_id == "page_post_123"
    assert graph_client.calls == [
        {
            "page_id": attempt.publishing_identity.meta_page_id,
            "message": "Approved Facebook Page caption",
            "page_token": "page-live-token",
        }
    ]


@pytest.mark.django_db
def test_process_facebook_page_attempt_with_media_publishes_photo(tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    attempt = _publish_attempt_graph(tenant=tenant)
    _meta_page_for_attempt(attempt=attempt, tenant=tenant, token="page-live-token")
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": "https://cdn.example.com/content/image.png"},
    )
    attempt.version.media_assets.add(asset)
    graph_client = _FakeFacebookGraphClient(post_id="page_post_photo_1")

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=FacebookGraphPagePublisher(graph_client=graph_client, enabled=True),
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_post_id == "page_post_photo_1"
    # A photo post is published via /photos with the media URL, not a text feed post.
    assert graph_client.calls == [
        {
            "page_id": attempt.publishing_identity.meta_page_id,
            "caption": "Approved Facebook Page caption",
            "media_url": "https://cdn.example.com/content/image.png",
            "page_token": "page-live-token",
        }
    ]


def test_facebook_graph_client_posts_page_photo_without_token_in_url():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "photo_1", "post_id": "page_123_post_789"})

    client = FacebookGraphPageClient(graph_version="v24.0")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = client.publish_page_photo(
        page_id="page_123",
        caption="Approved post",
        media_url="https://cdn.example.com/content/image.png",
        page_token="page-live-token",
    )

    client.close()
    assert result.post_id == "page_123_post_789"
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/v24.0/page_123/photos"
    assert "page-live-token" not in str(request.url)
    body = parse_qs(request.content.decode("utf-8"))
    assert body["url"] == ["https://cdn.example.com/content/image.png"]
    assert body["caption"] == ["Approved post"]
    assert body["published"] == ["true"]
    assert body["access_token"] == ["page-live-token"]


def test_facebook_graph_client_posts_page_feed_without_token_in_url():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "page_123_post_456"})

    client = FacebookGraphPageClient(graph_version="v24.0")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = client.publish_page_feed(
        page_id="page_123",
        message="Approved post",
        page_token="page-live-token",
    )

    client.close()
    assert result.post_id == "page_123_post_456"
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/v24.0/page_123/feed"
    assert "page-live-token" not in str(request.url)
    body = parse_qs(request.content.decode("utf-8"))
    assert body["message"] == ["Approved post"]
    assert body["published"] == ["true"]
    assert body["access_token"] == ["page-live-token"]


@pytest.mark.django_db
def test_facebook_graph_publisher_rejects_cross_tenant_page_token(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    other_tenant = Tenant.objects.create(name="Other Tenant")
    _meta_page_for_attempt(
        attempt=attempt,
        tenant=other_tenant,
        token="other-tenant-token",
    )
    graph_client = _FakeFacebookGraphClient(post_id="should_not_publish")

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=FacebookGraphPagePublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_TERMINAL_ERROR
    assert graph_client.calls == []
    assert "other-tenant-token" not in attempt.failure_detail_safe


@pytest.mark.django_db
def test_process_facebook_page_attempt_is_noop_after_success(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    first_publisher = _FakePublisher(meta_post_id="fb_post_once")
    first = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=first_publisher,
        readiness=_ready_readiness(),
    )
    second_publisher = _FakePublisher(meta_post_id="fb_post_twice")

    second = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=second_publisher,
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert first.status == PROCESS_STATUS_PUBLISHED
    assert second.status == PROCESS_STATUS_NOOP
    assert attempt.meta_post_id == "fb_post_once"
    assert PublishedPost.all_objects.filter(draft=attempt.draft).count() == 1
    assert second_publisher.payloads == []


@pytest.mark.django_db
def test_process_facebook_page_attempt_retryable_provider_error_is_safe(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    now = timezone.now()
    publisher = _FailingPublisher(
        code=PROVIDER_RETRYABLE_ERROR,
        detail_safe="rate limited bearer meta-access-token raw_response",
        retryable=True,
    )

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == PROVIDER_RETRYABLE_ERROR
    assert attempt.failure_detail_safe == "Publishing failed with a provider error."
    assert now + timezone.timedelta(minutes=5) <= attempt.next_retry_at
    assert attempt.next_retry_at <= now + timezone.timedelta(minutes=5, seconds=60)
    assert attempt.attempt_count == 1


@pytest.mark.django_db
def test_process_facebook_graph_publisher_retryable_error_is_safe(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    _meta_page_for_attempt(attempt=attempt, tenant=tenant, token="page-live-token")
    graph_client = _FailingFacebookGraphClient(
        detail="rate limited bearer page-live-token raw_response",
        retryable=True,
    )

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=FacebookGraphPagePublisher(
            graph_client=graph_client,
            enabled=True,
        ),
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert attempt.failure_code == PROVIDER_RETRYABLE_ERROR
    assert attempt.failure_detail_safe == "Publishing failed with a provider error."
    rendered = str(result.as_dict()).lower()
    assert "page-live-token" not in rendered
    assert "raw_response" not in rendered


@pytest.mark.django_db
def test_process_facebook_page_attempt_retryable_error_stops_after_fifth_attempt(
    tenant,
):
    attempt = _publish_attempt_graph(tenant=tenant)
    attempt.attempt_count = 4
    attempt.save(update_fields=["attempt_count", "updated_at"])
    now = timezone.now()
    publisher = _FailingPublisher(
        code=PROVIDER_RETRYABLE_ERROR,
        detail_safe="temporary provider error",
        retryable=True,
    )

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_ready_readiness(),
        now=now,
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.attempt_count == 5
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_MAX_ATTEMPTS_EXCEEDED
    assert attempt.next_retry_at is None
    assert attempt.finished_at == now


@pytest.mark.django_db
def test_process_facebook_page_attempt_terminal_provider_error_is_safe(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    publisher = _FailingPublisher(
        code=PROVIDER_TERMINAL_ERROR,
        detail_safe="invalid page-token secret",
        retryable=False,
    )

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=publisher,
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.status == PROCESS_STATUS_FAILED
    assert attempt.state == PublishAttempt.STATE_FAILED_TERMINAL
    assert attempt.failure_code == PROVIDER_TERMINAL_ERROR
    assert attempt.failure_detail_safe == "Publishing failed with a provider error."
    assert attempt.next_retry_at is None
    assert attempt.finished_at is not None


@pytest.mark.django_db
def test_process_facebook_page_attempt_marks_schedule_partial_with_blocked_sibling(tenant):
    attempt = _publish_attempt_graph(tenant=tenant)
    PublishAttempt.all_objects.create(
        tenant=tenant,
        schedule=attempt.schedule,
        draft=attempt.draft,
        version=attempt.version,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        state=PublishAttempt.STATE_BLOCKED,
        idempotency_key=f"blocked-sibling:{attempt.schedule_id}",
        failure_code="publishing_identity_missing",
        failure_detail_safe="No selected publishing identity exists for this channel.",
    )

    result = process_facebook_page_publish_attempt(
        tenant=tenant,
        attempt_id=attempt.id,
        publisher=_FakePublisher(meta_post_id="fb_partial"),
        readiness=_ready_readiness(),
    )

    attempt.schedule.refresh_from_db()
    attempt.draft.refresh_from_db()
    assert result.status == PROCESS_STATUS_PUBLISHED
    assert attempt.schedule.state == ContentSchedule.STATE_PARTIAL
    assert attempt.draft.state == ContentDraft.STATE_PARTIALLY_PUBLISHED


@pytest.mark.django_db
def test_requeue_failed_publish_attempt_clears_retry_fields(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    attempt.failure_code = PROVIDER_RETRYABLE_ERROR
    attempt.failure_detail_safe = "Rate limited."
    attempt.next_retry_at = timezone.now() + timezone.timedelta(minutes=5)
    attempt.started_at = timezone.now()
    attempt.finished_at = timezone.now()
    attempt.save()

    requeued = requeue_failed_publish_attempt(tenant=tenant, attempt_id=attempt.id)

    requeued.refresh_from_db()
    requeued.schedule.refresh_from_db()
    requeued.draft.refresh_from_db()
    assert requeued.state == PublishAttempt.STATE_QUEUED
    assert requeued.failure_code == ""
    assert requeued.failure_detail_safe == ""
    assert requeued.next_retry_at is None
    assert requeued.started_at is None
    assert requeued.finished_at is None
    assert requeued.schedule.state == ContentSchedule.STATE_DISPATCHING
    assert requeued.draft.state == ContentDraft.STATE_PUBLISHING


@pytest.mark.django_db
def test_requeue_failed_publish_attempt_rejects_terminal_state(tenant):
    attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_TERMINAL,
    )

    with pytest.raises(ValueError, match=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE):
        requeue_failed_publish_attempt(tenant=tenant, attempt_id=attempt.id)


@pytest.mark.django_db
def test_requeue_due_retryable_attempts_only_requeues_due_tenant_attempts(tenant):
    now = timezone.now()
    due_attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    due_attempt.next_retry_at = now - timezone.timedelta(minutes=1)
    due_attempt.save(update_fields=["next_retry_at", "updated_at"])
    future_attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    future_attempt.next_retry_at = now + timezone.timedelta(minutes=5)
    future_attempt.save(update_fields=["next_retry_at", "updated_at"])
    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_attempt = _publish_attempt_graph(
        tenant=other_tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    other_attempt.next_retry_at = now - timezone.timedelta(minutes=1)
    other_attempt.save(update_fields=["next_retry_at", "updated_at"])

    result = requeue_due_retryable_attempts(tenant=tenant, now=now)

    due_attempt.refresh_from_db()
    future_attempt.refresh_from_db()
    other_attempt.refresh_from_db()
    assert result.as_dict() == {"scanned": 1, "requeued": 1, "skipped": 0}
    assert due_attempt.state == PublishAttempt.STATE_QUEUED
    assert future_attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE
    assert other_attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE


@pytest.mark.django_db
def test_process_due_publish_attempts_requeues_and_processes_due_channel_attempts(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    queued_attempt = _publish_attempt_graph(tenant=tenant)
    retry_attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    retry_attempt.next_retry_at = now - timezone.timedelta(minutes=1)
    retry_attempt.save(update_fields=["next_retry_at", "updated_at"])
    future_attempt = _publish_attempt_graph(tenant=tenant)
    future_attempt.schedule.scheduled_at = now + timezone.timedelta(minutes=10)
    future_attempt.schedule.save(update_fields=["scheduled_at", "updated_at"])
    instagram_attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
    )
    _attach_publishable_media(attempt=instagram_attempt, tenant=tenant, tmp_path=tmp_path)
    publisher = _SequencedPublisher()
    instagram_publisher = _FakeInstagramPublisher(statuses=["FINISHED"])

    result = process_due_publish_attempts(
        tenant=tenant,
        now=now,
        publisher=publisher,
        instagram_publisher=instagram_publisher,
        readiness=_combined_ready_readiness(),
    )

    queued_attempt.refresh_from_db()
    retry_attempt.refresh_from_db()
    future_attempt.refresh_from_db()
    instagram_attempt.refresh_from_db()
    assert result.as_dict() == {
        "scanned": 3,
        "processed": 3,
        "published": 3,
        "blocked": 0,
        "failed": 0,
        "skipped": 0,
        "requeued": 1,
    }
    assert queued_attempt.state == PublishAttempt.STATE_PUBLISHED
    assert retry_attempt.state == PublishAttempt.STATE_PUBLISHED
    assert future_attempt.state == PublishAttempt.STATE_QUEUED
    assert instagram_attempt.state == PublishAttempt.STATE_PUBLISHED
    assert len(publisher.payloads) == 2
    assert len(instagram_publisher.container_payloads) == 1


@pytest.mark.django_db
def test_process_due_publish_attempts_polls_due_instagram_container_attempts(
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        identity_platform=PublishingIdentity.PLATFORM_INSTAGRAM,
        state=PublishAttempt.STATE_CONTAINER_PENDING,
    )
    _attach_publishable_media(attempt=attempt, tenant=tenant, tmp_path=tmp_path)
    attempt.meta_container_id = "ig-container-due"
    attempt.meta_container_created_at = now - timezone.timedelta(minutes=5)
    attempt.save(
        update_fields=["meta_container_id", "meta_container_created_at", "updated_at"]
    )
    publisher = _FakeInstagramPublisher(statuses=["FINISHED"])

    result = process_due_publish_attempts(
        tenant=tenant,
        now=now,
        instagram_publisher=publisher,
        readiness=_combined_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.as_dict() == {
        "scanned": 1,
        "processed": 1,
        "published": 1,
        "blocked": 0,
        "failed": 0,
        "skipped": 0,
        "requeued": 0,
    }
    assert attempt.state == PublishAttempt.STATE_PUBLISHED
    assert attempt.meta_post_id == "ig-media-1"
    assert publisher.container_payloads == []
    assert publisher.status_checks == [
        (attempt.publishing_identity.ig_user_id, "ig-container-due")
    ]
    assert publisher.publish_calls == [
        (attempt.publishing_identity.ig_user_id, "ig-container-due")
    ]


@pytest.mark.django_db
def test_process_due_publish_attempts_counts_blocked_attempts(tenant):
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        with_identity=False,
    )

    result = process_due_publish_attempts(
        tenant=tenant,
        now=now,
        readiness=_ready_readiness(),
    )

    attempt.refresh_from_db()
    assert result.as_dict() == {
        "scanned": 1,
        "processed": 1,
        "published": 0,
        "blocked": 1,
        "failed": 0,
        "skipped": 0,
        "requeued": 0,
    }
    assert attempt.state == PublishAttempt.STATE_BLOCKED
    assert attempt.failure_code == PREFLIGHT_PUBLISHING_IDENTITY_MISSING


@pytest.mark.django_db
def test_process_content_publish_attempt_task_returns_processor_result(
    tenant, monkeypatch
):
    attempt = _publish_attempt_graph(tenant=tenant)

    class DummyResult:
        def as_dict(self):
            return {
                "status": PROCESS_STATUS_PUBLISHED,
                "attempt_id": str(attempt.id),
                "state": PublishAttempt.STATE_PUBLISHED,
                "failure_code": "",
                "failure_detail_safe": "",
                "published_post_id": "post-id",
            }

    def fake_process(*, tenant, attempt_id):  # noqa: ANN001
        assert str(tenant.id)
        assert str(attempt_id) == str(attempt.id)
        return DummyResult()

    monkeypatch.setattr("content_ops.tasks.process_facebook_page_publish_attempt", fake_process)

    result = process_content_publish_attempt.run(str(tenant.id), str(attempt.id))

    assert result["status"] == PROCESS_STATUS_PUBLISHED
    assert result["attempt_id"] == str(attempt.id)


@pytest.mark.django_db
def test_process_due_content_publish_attempts_task_can_target_one_tenant(
    tenant, monkeypatch
):
    other_tenant = Tenant.objects.create(name="Other Tenant")

    class DummyResult:
        def __init__(self, tenant_id):
            self.tenant_id = tenant_id

        def as_dict(self):
            return {
                "scanned": 1,
                "processed": 1,
                "published": 1,
                "blocked": 0,
                "failed": 0,
                "skipped": 0,
                "requeued": 0,
            }

    calls = []

    def fake_process(*, tenant, limit):  # noqa: ANN001
        calls.append((str(tenant.id), limit))
        return DummyResult(tenant.id)

    monkeypatch.setattr("content_ops.tasks.process_due_publish_attempts", fake_process)

    result = process_due_content_publish_attempts.run(
        tenant_id=str(tenant.id),
        limit=25,
    )

    assert set(result) == {str(tenant.id)}
    assert result[str(tenant.id)]["published"] == 1
    assert calls == [(str(tenant.id), 25)]
    assert str(other_tenant.id) not in result


@pytest.mark.django_db
def test_process_due_content_publish_attempts_task_scans_all_tenants(
    tenant, monkeypatch
):
    other_tenant = Tenant.objects.create(name="Other Tenant")

    class DummyResult:
        def __init__(self, tenant_id):
            self.tenant_id = tenant_id

        def as_dict(self):
            return {
                "scanned": 1,
                "processed": 1,
                "published": 0,
                "blocked": 1,
                "failed": 0,
                "skipped": 0,
                "requeued": 0,
            }

    calls = []

    def fake_process(*, tenant, limit):  # noqa: ANN001
        calls.append((str(tenant.id), limit))
        return DummyResult(tenant.id)

    monkeypatch.setattr("content_ops.tasks.process_due_publish_attempts", fake_process)

    result = process_due_content_publish_attempts.run(limit=15)

    assert set(result) == {str(tenant.id), str(other_tenant.id)}
    assert sorted(calls) == sorted(
        [(str(tenant.id), 15), (str(other_tenant.id), 15)]
    )


def test_content_ops_publish_tasks_allow_five_retries():
    assert process_content_publish_attempt.max_retries == 5
    assert process_due_content_publish_attempts.max_retries == 5
    assert requeue_due_content_publish_attempts.max_retries == 5


@pytest.mark.django_db
def test_requeue_due_content_publish_attempts_task_can_target_one_tenant(tenant):
    now = timezone.now()
    attempt = _publish_attempt_graph(
        tenant=tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    attempt.next_retry_at = now - timezone.timedelta(minutes=1)
    attempt.save(update_fields=["next_retry_at", "updated_at"])
    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_attempt = _publish_attempt_graph(
        tenant=other_tenant,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
    )
    other_attempt.next_retry_at = now - timezone.timedelta(minutes=1)
    other_attempt.save(update_fields=["next_retry_at", "updated_at"])

    result = requeue_due_content_publish_attempts.run(tenant_id=str(tenant.id))

    attempt.refresh_from_db()
    other_attempt.refresh_from_db()
    assert set(result) == {str(tenant.id)}
    assert result[str(tenant.id)]["requeued"] == 1
    assert attempt.state == PublishAttempt.STATE_QUEUED
    assert other_attempt.state == PublishAttempt.STATE_FAILED_RETRYABLE


def _publish_attempt_graph(
    *,
    tenant,
    channel: str = PublishAttempt.CHANNEL_FACEBOOK_PAGE,
    identity_platform: str = PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
    state: str = PublishAttempt.STATE_QUEUED,
    caption: str = "Approved Facebook Page caption",
    with_identity: bool = True,
    identity_readiness: str = PublishingIdentity.READINESS_READY,
    approval_snapshot: dict | None = None,
) -> PublishAttempt:
    workspace = ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Publisher workspace",
        target_channels=[channel],
    )
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Approved post",
        state=ContentDraft.STATE_SCHEDULED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption=caption,
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    snapshot = {
        "draft_id": str(draft.id),
        "version_id": str(version.id),
        "approvals": [
            {"reviewer_type": "client", "status": "approved"},
        ],
    }
    if approval_snapshot is not None:
        snapshot.update(approval_snapshot)
    schedule = ContentSchedule.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        scheduled_at=timezone.now() - timezone.timedelta(minutes=1),
        state=ContentSchedule.STATE_DISPATCHING,
        approval_snapshot=snapshot,
    )
    identity = (
        _publishing_identity(
            tenant=tenant,
            platform=identity_platform,
            readiness=identity_readiness,
        )
        if with_identity
        else None
    )
    return PublishAttempt.all_objects.create(
        tenant=tenant,
        schedule=schedule,
        draft=draft,
        version=version,
        publishing_identity=identity,
        channel=channel,
        state=state,
        idempotency_key=f"preflight:{schedule.id}:{channel}:{state}:{caption}",
    )


def _publishing_identity(
    *,
    tenant,
    platform: str = PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
    readiness: str = PublishingIdentity.READINESS_READY,
) -> PublishingIdentity:
    return PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=platform,
        meta_page_id=f"page_{uuid.uuid4()}",
        ig_user_id=f"ig_{uuid.uuid4()}"
        if platform == PublishingIdentity.PLATFORM_INSTAGRAM
        else "",
        display_name="Publisher Identity",
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=readiness,
    )


def _meta_page_for_attempt(
    *,
    attempt: PublishAttempt,
    tenant,
    token: str,
) -> MetaPage:
    user = User.objects.create_user(
        username=f"content-page-{uuid.uuid4()}",
        email=f"content-page-{uuid.uuid4()}@example.com",
        tenant=tenant,
    )
    connection = MetaConnection(tenant=tenant, user=user, scopes=["pages_manage_posts"])
    connection.set_raw_token("user-token")
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id=attempt.publishing_identity.meta_page_id,
        name="Publisher Page",
        can_analyze=True,
        perms=["CREATE_CONTENT"],
    )
    page.set_raw_page_token(token)
    page.save()
    return page


def _media_asset(
    *,
    tenant,
    workspace: ContentWorkspace,
    tmp_path,
    renditions: dict,
    mime_type: str = "image/png",
    write_file: bool = True,
) -> MediaAsset:
    asset_id = uuid.uuid4()
    storage_key = f"content_ops/assets/{tenant.id}/{workspace.id}/{asset_id}/image.png"
    if write_file:
        file_path = tmp_path / storage_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"image bytes")
    return MediaAsset.all_objects.create(
        id=asset_id,
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key=storage_key,
        mime_type=mime_type,
        status=MediaAsset.STATUS_AVAILABLE,
        renditions=renditions,
    )


def _attach_publishable_media(*, attempt: PublishAttempt, tenant, tmp_path) -> MediaAsset:
    asset = _media_asset(
        tenant=tenant,
        workspace=attempt.draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": "https://cdn.example.com/image.png"},
    )
    attempt.version.media_assets.add(asset)
    return asset


def _ready_readiness() -> dict:
    return {
        "facebook_page_publishing": {
            "state": "ready",
            "reason": None,
        }
    }


def _combined_ready_readiness() -> dict:
    return {
        **_ready_readiness(),
        "instagram_publishing": {
            "state": "ready",
            "reason": None,
        },
    }


class _FakePublisher:
    def __init__(self, *, meta_post_id: str) -> None:
        self.meta_post_id = meta_post_id
        self.payloads: list[FacebookPagePublishPayload] = []

    def publish(
        self, payload: FacebookPagePublishPayload
    ) -> FacebookPagePublishResult:
        self.payloads.append(payload)
        return FacebookPagePublishResult(
            meta_post_id=self.meta_post_id,
            permalink=f"https://facebook.example/{self.meta_post_id}",
        )


class _SequencedPublisher:
    def __init__(self) -> None:
        self.payloads: list[FacebookPagePublishPayload] = []

    def publish(
        self, payload: FacebookPagePublishPayload
    ) -> FacebookPagePublishResult:
        self.payloads.append(payload)
        meta_post_id = f"post-{len(self.payloads)}"
        return FacebookPagePublishResult(
            meta_post_id=meta_post_id,
            permalink=f"https://facebook.example/{meta_post_id}",
        )


class _FakeFacebookGraphClient:
    def __init__(self, *, post_id: str) -> None:
        self.post_id = post_id
        self.calls: list[dict[str, str]] = []

    def publish_page_feed(
        self,
        *,
        page_id: str,
        message: str,
        page_token: str,
    ):
        self.calls.append(
            {
                "page_id": page_id,
                "message": message,
                "page_token": page_token,
            }
        )
        return type(
            "GraphResult",
            (),
            {
                "post_id": self.post_id,
                "permalink": f"https://facebook.example/{self.post_id}",
            },
        )()

    def publish_page_photo(
        self,
        *,
        page_id: str,
        caption: str,
        media_url: str,
        page_token: str,
    ):
        self.calls.append(
            {
                "page_id": page_id,
                "caption": caption,
                "media_url": media_url,
                "page_token": page_token,
            }
        )
        return type(
            "GraphResult",
            (),
            {
                "post_id": self.post_id,
                "permalink": f"https://facebook.example/{self.post_id}",
            },
        )()


class _FailingFacebookGraphClient:
    def __init__(self, *, detail: str, retryable: bool) -> None:
        self.detail = detail
        self.retryable = retryable

    def publish_page_feed(
        self,
        *,
        page_id: str,  # noqa: ARG002
        message: str,  # noqa: ARG002
        page_token: str,  # noqa: ARG002
    ):
        raise FacebookPagePublishError(
            code=PROVIDER_RETRYABLE_ERROR if self.retryable else PROVIDER_TERMINAL_ERROR,
            detail_safe=self.detail,
            retryable=self.retryable,
        )


class _FakeInstagramGraphClient:
    def __init__(self, *, statuses: list[str]) -> None:
        self.statuses = list(statuses)
        self.calls: list[dict[str, str]] = []

    def create_media_container(
        self,
        *,
        ig_user_id: str,
        media_url: str,
        caption: str,
        media_type: str,
        access_token: str,
    ):
        self.calls.append(
            {
                "operation": "create",
                "ig_user_id": ig_user_id,
                "media_url": media_url,
                "caption": caption,
                "media_type": media_type,
                "access_token": access_token,
            }
        )
        return type(
            "GraphResult",
            (),
            {
                "container_id": "ig-container-1",
            },
        )()

    def get_media_container_status(
        self,
        *,
        container_id: str,
        access_token: str,
    ):
        self.calls.append(
            {
                "operation": "status",
                "container_id": container_id,
                "access_token": access_token,
            }
        )
        status = self.statuses.pop(0) if self.statuses else "FINISHED"
        return type(
            "GraphResult",
            (),
            {
                "status_code": status,
                "status": status.title(),
            },
        )()

    def publish_media_container(
        self,
        *,
        ig_user_id: str,
        container_id: str,
        access_token: str,
    ):
        self.calls.append(
            {
                "operation": "publish",
                "ig_user_id": ig_user_id,
                "container_id": container_id,
                "access_token": access_token,
            }
        )
        return type(
            "GraphResult",
            (),
            {
                "media_id": "ig-media-1",
                "permalink": "https://instagram.example/ig-media-1",
            },
        )()


class _FailingInstagramGraphClient:
    def __init__(self, *, detail: str, retryable: bool) -> None:
        self.detail = detail
        self.retryable = retryable

    def create_media_container(
        self,
        *,
        ig_user_id: str,  # noqa: ARG002
        media_url: str,  # noqa: ARG002
        caption: str,  # noqa: ARG002
        media_type: str,  # noqa: ARG002
        access_token: str,  # noqa: ARG002
    ):
        raise InstagramPublishError(
            code=PROVIDER_RETRYABLE_ERROR if self.retryable else PROVIDER_TERMINAL_ERROR,
            detail_safe=self.detail,
            retryable=self.retryable,
        )


class _FakeInstagramPublisher:
    def __init__(self, *, statuses: list[str]) -> None:
        self.statuses = list(statuses)
        self.container_payloads: list[InstagramMediaContainerPayload] = []
        self.status_checks: list[tuple[str, str]] = []
        self.publish_calls: list[tuple[str, str]] = []

    def create_media_container(
        self,
        payload: InstagramMediaContainerPayload,
    ) -> InstagramMediaContainerResult:
        self.container_payloads.append(payload)
        return InstagramMediaContainerResult(
            container_id=f"ig-container-{len(self.container_payloads)}"
        )

    def get_media_container_status(
        self,
        *,
        tenant_id: str = "",  # noqa: ARG002
        publishing_identity_id: str = "",  # noqa: ARG002
        meta_page_id: str = "",  # noqa: ARG002
        ig_user_id: str,
        container_id: str,
    ) -> InstagramMediaContainerStatusResult:
        self.status_checks.append((ig_user_id, container_id))
        status = self.statuses.pop(0) if self.statuses else "FINISHED"
        return InstagramMediaContainerStatusResult(status_code=status)

    def publish_media_container(
        self,
        *,
        tenant_id: str = "",  # noqa: ARG002
        publishing_identity_id: str = "",  # noqa: ARG002
        meta_page_id: str = "",  # noqa: ARG002
        ig_user_id: str,
        container_id: str,
    ) -> InstagramMediaPublishResult:
        self.publish_calls.append((ig_user_id, container_id))
        return InstagramMediaPublishResult(
            meta_media_id=f"ig-media-{len(self.publish_calls)}",
            permalink=f"https://instagram.example/ig-media-{len(self.publish_calls)}",
        )


class _FailingInstagramPublisher(_FakeInstagramPublisher):
    def __init__(
        self,
        *,
        fail_on: str,
        detail_safe: str = "Instagram provider operation failed.",
    ) -> None:
        super().__init__(statuses=["FINISHED"])
        self.fail_on = fail_on
        self.detail_safe = detail_safe

    def create_media_container(
        self,
        payload: InstagramMediaContainerPayload,
    ) -> InstagramMediaContainerResult:
        if self.fail_on == "create":
            raise InstagramPublishError(
                code="instagram_create_retryable",
                detail_safe=self.detail_safe,
                retryable=True,
            )
        return super().create_media_container(payload)

    def publish_media_container(
        self,
        *,
        tenant_id: str = "",  # noqa: ARG002
        publishing_identity_id: str = "",  # noqa: ARG002
        meta_page_id: str = "",  # noqa: ARG002
        ig_user_id: str,
        container_id: str,
    ) -> InstagramMediaPublishResult:
        self.publish_calls.append((ig_user_id, container_id))
        if self.fail_on == "publish":
            raise InstagramPublishError(
                code="instagram_publish_retryable",
                detail_safe=self.detail_safe,
                retryable=True,
            )
        return InstagramMediaPublishResult(
            meta_media_id=f"ig-media-{len(self.publish_calls)}",
            permalink=f"https://instagram.example/ig-media-{len(self.publish_calls)}",
        )


class _FailingPublisher:
    def __init__(self, *, code: str, detail_safe: str, retryable: bool) -> None:
        self.code = code
        self.detail_safe = detail_safe
        self.retryable = retryable

    def publish(
        self, payload: FacebookPagePublishPayload  # noqa: ARG002
    ) -> FacebookPagePublishResult:
        raise FacebookPagePublishError(
            code=self.code,
            detail_safe=self.detail_safe,
            retryable=self.retryable,
        )
