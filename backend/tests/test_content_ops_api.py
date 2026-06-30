from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from content_ops.assets import public_media_fetch_url
from content_ops.models import (
    ApprovalDecision,
    ApprovalRequest,
    ContentDraft,
    ContentDraftVersion,
    ContentExportArtifact,
    ContentSchedule,
    ContentWorkspace,
    GenerationJob,
    MediaAsset,
    OrganicPostMetricSnapshot,
    PublishedPost,
    PublishingIdentity,
    PublishAttempt,
)
from content_ops.tasks import refresh_content_published_post_metrics
from integrations.models import (
    Client,
    MetaConnection,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)


@pytest.fixture
def other_tenant(db) -> Tenant:
    return Tenant.objects.create(name="Other Tenant")


@pytest.fixture
def other_user(other_tenant) -> User:
    return User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
    )


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_workspace_list_is_tenant_scoped(auth_client, tenant, other_tenant):
    ContentWorkspace.all_objects.create(tenant=tenant, name="Visible")
    ContentWorkspace.all_objects.create(tenant=other_tenant, name="Hidden")

    response = auth_client.get("/api/content-ops/workspaces/")

    assert response.status_code == status.HTTP_200_OK
    names = [item["name"] for item in response.data["results"]]
    assert names == ["Visible"]


@pytest.mark.django_db
def test_workspace_create_rejects_cross_tenant_client(auth_client, other_tenant):
    client = Client.all_objects.create(
        tenant=other_tenant,
        name="Other Client",
        slug="other-client",
    )

    response = auth_client.post(
        "/api/content-ops/workspaces/",
        data={
            "name": "June content",
            "client_id": str(client.id),
            "target_channels": ["facebook_page", "instagram"],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "client" in response.data


@pytest.mark.django_db
def test_viewer_can_read_but_not_create_content_ops_records(api_client, tenant):
    viewer = _user_with_role(tenant, Role.VIEWER, "viewer@example.com")
    ContentWorkspace.all_objects.create(tenant=tenant, name="Readonly")
    api_client.force_authenticate(user=viewer)

    list_response = api_client.get("/api/content-ops/workspaces/")
    create_response = api_client.post(
        "/api/content-ops/workspaces/",
        data={"name": "Blocked"},
        format="json",
    )

    assert list_response.status_code == status.HTTP_200_OK
    assert [item["name"] for item in list_response.data["results"]] == ["Readonly"]
    assert create_response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_draft_version_endpoint_creates_active_version(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Generated caption", "platform_overrides": {}},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["version_number"] == 1

    draft_response = auth_client.get(f"/api/content-ops/drafts/{draft_id}/")
    assert draft_response.status_code == status.HTTP_200_OK
    assert str(draft_response.data["active_version"]) == response.data["id"]
    assert draft_response.data["state"] == ContentDraft.STATE_GENERATED


@pytest.mark.django_db
def test_draft_version_allows_unpublished_asset_during_draft_stage(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    asset = _create_media_asset(
        tenant=tenant,
        workspace=workspace,
        tmp_path=tmp_path,
        renditions={},
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={
            "caption": "Draft-stage graphic option",
            "media_assets": [str(asset.id)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert [str(asset_id) for asset_id in response.data["media_assets"]] == [str(asset.id)]


@pytest.mark.django_db
def test_scheduled_draft_version_requires_public_media_url_proof(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    draft = ContentDraft.all_objects.get(id=draft_id)
    draft.state = ContentDraft.STATE_SCHEDULED
    draft.save(update_fields=["state", "updated_at"])
    asset = _create_media_asset(
        tenant=tenant,
        workspace=draft.workspace,
        tmp_path=tmp_path,
        renditions={},
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={
            "caption": "Scheduled graphic swap",
            "media_assets": [str(asset.id)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["media_assets"]["reason"] == "asset_public_url_missing"


@pytest.mark.django_db
def test_public_media_proof_uses_configured_https_url_without_storage_key(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    settings.CONTENT_OPS_PUBLIC_MEDIA_BASE_URL = (
        "https://media.example.com/api/content-ops/public-media"
    )
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    draft = ContentDraft.all_objects.get(id=draft_id)
    asset = _create_media_asset(
        tenant=tenant,
        workspace=draft.workspace,
        tmp_path=tmp_path,
        renditions={},
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Approved media",
    )
    version.media_assets.add(asset)
    draft.active_version = version
    draft.state = ContentDraft.STATE_CLIENT_APPROVED
    draft.save(update_fields=["active_version", "state", "updated_at"])

    response = auth_client.get(
        f"/api/content-ops/assets/{asset.id}/public-media-proof/"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["ready"] is True
    assert response.data["public_url_scheme"] == "https"
    assert response.data["public_url_host"] == "media.example.com"
    assert response.data["public_url_redacted"].endswith(f"/.../{asset.id}")
    assert response.data["approved_for_public_fetch"] is True
    assert response.data["content_length"] == len(b"image bytes")
    assert response.data["storage_key_exposed"] is False
    rendered = str(response.data)
    assert "content_ops/assets" not in rendered
    assert str(tenant.id) not in rendered
    assert str(draft.workspace_id) not in rendered
    assert public_media_fetch_url(asset).endswith(f"/{asset.id}/")


@pytest.mark.django_db
def test_public_media_endpoint_serves_approved_asset_without_auth(
    api_client,
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    draft = ContentDraft.all_objects.get(id=draft_id)
    asset = _create_media_asset(
        tenant=tenant,
        workspace=draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": f"https://media.example.com/{uuid.uuid4()}"},
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Approved public media",
    )
    version.media_assets.add(asset)
    draft.active_version = version
    draft.state = ContentDraft.STATE_CLIENT_APPROVED
    draft.save(update_fields=["active_version", "state", "updated_at"])

    response = api_client.get(f"/api/content-ops/public-media/{asset.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "image/png"
    assert response["Content-Length"] == str(len(b"image bytes"))
    assert b"".join(response.streaming_content) == b"image bytes"
    rendered_headers = str(dict(response.items()))
    assert "content_ops/assets" not in rendered_headers
    assert str(tenant.id) not in rendered_headers


@pytest.mark.django_db
def test_public_media_endpoint_rejects_unapproved_asset(
    api_client,
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    draft = ContentDraft.all_objects.get(id=draft_id)
    asset = _create_media_asset(
        tenant=tenant,
        workspace=draft.workspace,
        tmp_path=tmp_path,
        renditions={"public_url": f"https://media.example.com/{uuid.uuid4()}"},
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Unapproved public media",
    )
    version.media_assets.add(asset)
    draft.active_version = version
    draft.state = ContentDraft.STATE_GENERATED
    draft.save(update_fields=["active_version", "state", "updated_at"])

    response = api_client.get(f"/api/content-ops/public-media/{asset.id}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "content_ops/assets" not in str(response.data)


@pytest.mark.django_db
def test_public_media_proof_rejects_private_configured_base_url(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    settings.CONTENT_OPS_PUBLIC_MEDIA_BASE_URL = (
        "http://localhost/api/content-ops/public-media"
    )
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    draft = ContentDraft.all_objects.get(id=draft_id)
    asset = _create_media_asset(
        tenant=tenant,
        workspace=draft.workspace,
        tmp_path=tmp_path,
        renditions={},
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Approved media",
    )
    version.media_assets.add(asset)
    draft.active_version = version
    draft.state = ContentDraft.STATE_CLIENT_APPROVED
    draft.save(update_fields=["active_version", "state", "updated_at"])

    response = auth_client.get(
        f"/api/content-ops/assets/{asset.id}/public-media-proof/"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["ready"] is False
    assert response.data["failure_code"] == "asset_public_url_not_fetchable"
    assert response.data["public_url_is_https"] is False
    assert "localhost" not in response.data["failure_detail_safe"]


@pytest.mark.django_db
def test_approval_flow_and_schedule_requires_client_approved_version(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    version_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Approve me"},
        format="json",
    )
    version_id = version_response.data["id"]

    blocked_schedule = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={"scheduled_at": timezone.now().isoformat()},
        format="json",
    )
    assert blocked_schedule.status_code == status.HTTP_400_BAD_REQUEST

    internal_request = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-internal-review/",
        data={},
        format="json",
    )
    assert internal_request.status_code == status.HTTP_201_CREATED
    assert internal_request.data["reviewer_type"] == ApprovalRequest.REVIEWER_INTERNAL

    internal_decision = auth_client.post(
        f"/api/content-ops/approval-requests/{internal_request.data['id']}/decisions/",
        data={"decision": "approved", "comment": "Ready for client"},
        format="json",
    )
    assert internal_decision.status_code == status.HTTP_201_CREATED

    client_request = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-client-review/",
        data={},
        format="json",
    )
    assert client_request.status_code == status.HTTP_201_CREATED
    assert str(client_request.data["version"]) == version_id

    client_decision = auth_client.post(
        f"/api/content-ops/approval-requests/{client_request.data['id']}/decisions/",
        data={"decision": "approved", "comment": "Client approved"},
        format="json",
    )
    assert client_decision.status_code == status.HTTP_201_CREATED

    schedule_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={
            "scheduled_at": timezone.now().replace(microsecond=0).isoformat(),
            "timezone": "America/Jamaica",
        },
        format="json",
    )
    assert schedule_response.status_code == status.HTTP_201_CREATED
    assert str(schedule_response.data["version"]) == version_id
    assert schedule_response.data["approval_snapshot"]["version_id"] == version_id
    assert schedule_response.data["approval_snapshot"]["target_channels"] == [
        {"type": "facebook_page"},
        {"type": "instagram"},
    ]
    assert len(schedule_response.data["approval_snapshot"]["approvals"]) == 2

    draft_response = auth_client.get(f"/api/content-ops/drafts/{draft_id}/")
    assert draft_response.data["state"] == ContentDraft.STATE_SCHEDULED


@pytest.mark.django_db
def test_schedule_snapshots_explicit_publishing_targets(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={
            "scheduled_at": timezone.now().replace(microsecond=0).isoformat(),
            "timezone": "America/Jamaica",
            "channels": [
                {"type": "facebook_page", "page_id": "page_123"},
                {"type": "instagram", "ig_user_id": "ig_123"},
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["approval_snapshot"]["target_channels"] == [
        {"type": "facebook_page", "page_id": "page_123"},
        {"type": "instagram", "ig_user_id": "ig_123"},
    ]


@pytest.mark.django_db
def test_schedule_rejects_invalid_publishing_targets(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={
            "scheduled_at": timezone.now().replace(microsecond=0).isoformat(),
            "channels": [{"type": "tiktok"}],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "channels" in response.data


@pytest.mark.django_db
def test_publish_now_requires_active_version(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "active_version" in response.data


@pytest.mark.django_db
def test_publish_now_bypass_mode_dispatches_without_client_approval(
    auth_client, tenant, user
):
    _create_meta_publishing_state(tenant=tenant, user=user)
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "One-click post"},
        format="json",
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["approval_mode"] == ContentWorkspace.APPROVAL_MODE_BYPASS
    attempts = response.data["attempts"]
    assert {attempt["channel"] for attempt in attempts} == {
        PublishAttempt.CHANNEL_FACEBOOK_PAGE,
        PublishAttempt.CHANNEL_INSTAGRAM,
    }
    assert {attempt["state"] for attempt in attempts} == {PublishAttempt.STATE_QUEUED}
    snapshot = response.data["schedule"]["approval_snapshot"]
    assert snapshot["approval_mode"] == ContentWorkspace.APPROVAL_MODE_BYPASS
    assert snapshot["bypassed_by"] == str(user.id)

    draft_response = auth_client.get(f"/api/content-ops/drafts/{draft_id}/")
    assert draft_response.data["state"] == ContentDraft.STATE_SCHEDULED


@pytest.mark.django_db
def test_publish_now_blocks_when_no_publishing_identity(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "No destination yet"},
        format="json",
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    attempts = response.data["attempts"]
    assert attempts, "expected blocked attempts to be reported back to the caller"
    assert {attempt["state"] for attempt in attempts} == {PublishAttempt.STATE_BLOCKED}
    assert all(
        attempt["failure_code"] == "publishing_identity_missing"
        for attempt in attempts
    )


@pytest.mark.django_db
def test_publish_now_required_mode_rejects_unapproved_draft(auth_client):
    workspace_id = _create_workspace(auth_client)
    patch = auth_client.patch(
        f"/api/content-ops/workspaces/{workspace_id}/",
        data={"quick_post_approval_mode": ContentWorkspace.APPROVAL_MODE_REQUIRED},
        format="json",
    )
    assert patch.status_code == status.HTTP_200_OK
    assert (
        patch.data["quick_post_approval_mode"]
        == ContentWorkspace.APPROVAL_MODE_REQUIRED
    )
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Needs approval"},
        format="json",
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "approval" in response.data


@pytest.mark.django_db
def test_publish_now_required_mode_publishes_client_approved_draft(
    auth_client, tenant, user
):
    _create_meta_publishing_state(tenant=tenant, user=user)
    workspace_id = _create_workspace(auth_client)
    auth_client.patch(
        f"/api/content-ops/workspaces/{workspace_id}/",
        data={"quick_post_approval_mode": ContentWorkspace.APPROVAL_MODE_REQUIRED},
        format="json",
    )
    draft_id = _create_client_approved_draft(auth_client, workspace_id)

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["approval_mode"] == ContentWorkspace.APPROVAL_MODE_REQUIRED
    attempts = response.data["attempts"]
    assert {attempt["state"] for attempt in attempts} == {PublishAttempt.STATE_QUEUED}


@pytest.mark.django_db
def test_publish_now_requires_publish_role(api_client, user, tenant):
    api_client.force_authenticate(user=user)
    workspace_id = _create_workspace(api_client)
    draft_id = _create_draft(api_client, workspace_id)
    api_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Quick post"},
        format="json",
    )
    analyst = _user_with_role(tenant, Role.ANALYST, "analyst-publish@example.com")
    api_client.force_authenticate(user=analyst)

    response = api_client.post(
        f"/api/content-ops/drafts/{draft_id}/publish-now/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_analyst_cannot_schedule_client_approved_draft(api_client, user, tenant):
    api_client.force_authenticate(user=user)
    workspace_id = _create_workspace(api_client)
    draft_id = _create_client_approved_draft(api_client, workspace_id)
    analyst = _user_with_role(tenant, Role.ANALYST, "analyst@example.com")
    api_client.force_authenticate(user=analyst)

    response = api_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={"scheduled_at": timezone.now().isoformat()},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_draft_state_cannot_be_patched_directly(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)

    response = auth_client.patch(
        f"/api/content-ops/drafts/{draft_id}/",
        data={"state": ContentDraft.STATE_CLIENT_APPROVED},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["state"] == ContentDraft.STATE_DRAFT


@pytest.mark.django_db
def test_workflow_collections_do_not_allow_direct_writes(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    version_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Only nested workflow writes versions"},
        format="json",
    )

    direct_version = auth_client.post(
        "/api/content-ops/versions/",
        data={
            "draft": draft_id,
            "version_number": 99,
            "caption": "Bypass",
        },
        format="json",
    )
    direct_approval = auth_client.post(
        "/api/content-ops/approval-requests/",
        data={
            "draft": draft_id,
            "version": version_response.data["id"],
            "reviewer_type": ApprovalRequest.REVIEWER_INTERNAL,
        },
        format="json",
    )
    direct_schedule = auth_client.post(
        "/api/content-ops/schedules/",
        data={
            "draft": draft_id,
            "version": version_response.data["id"],
            "scheduled_at": timezone.now().isoformat(),
        },
        format="json",
    )

    assert direct_version.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert direct_approval.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert direct_schedule.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_new_version_supersedes_existing_approvals(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "First version"},
        format="json",
    )
    approval = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-internal-review/",
        data={},
        format="json",
    )

    response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Second version"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    approval_response = auth_client.get(
        f"/api/content-ops/approval-requests/{approval.data['id']}/"
    )
    assert approval_response.data["status"] == ApprovalRequest.STATUS_SUPERSEDED
    assert approval_response.data["superseded_reason"] == "new_version_created"


@pytest.mark.django_db
def test_superseded_approval_request_cannot_be_decided(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "First version"},
        format="json",
    )
    approval = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-internal-review/",
        data={},
        format="json",
    )
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Second version"},
        format="json",
    )

    response = auth_client.post(
        f"/api/content-ops/approval-requests/{approval.data['id']}/decisions/",
        data={"decision": ApprovalDecision.DECISION_APPROVED},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "status" in response.data
    assert ApprovalDecision.all_objects.count() == 0


@pytest.mark.django_db
def test_stale_active_version_approval_request_cannot_be_decided(auth_client):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    first_version = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "First version"},
        format="json",
    )
    approval = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-internal-review/",
        data={},
        format="json",
    )
    draft = ContentDraft.all_objects.get(id=draft_id)
    second_version = ContentDraftVersion.all_objects.create(
        tenant=draft.tenant,
        draft=draft,
        version_number=2,
        caption="Unsuperseded stale version",
    )
    draft.active_version = second_version
    draft.state = ContentDraft.STATE_INTERNAL_REVIEW
    draft.save(update_fields=["active_version", "state", "updated_at"])
    stale_approval = ApprovalRequest.all_objects.get(id=approval.data["id"])
    stale_approval.status = ApprovalRequest.STATUS_PENDING
    stale_approval.version_id = first_version.data["id"]
    stale_approval.save(update_fields=["status", "version", "updated_at"])

    response = auth_client.post(
        f"/api/content-ops/approval-requests/{approval.data['id']}/decisions/",
        data={"decision": ApprovalDecision.DECISION_APPROVED},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "version" in response.data
    assert ApprovalDecision.all_objects.count() == 0


@pytest.mark.django_db
def test_generation_job_cancel_does_not_return_raw_prompt(auth_client):
    workspace_id = _create_workspace(auth_client)
    job_response = auth_client.post(
        "/api/content-ops/generation-jobs/",
        data={
            "workspace": workspace_id,
            "job_type": GenerationJob.TYPE_CAPTION,
            "provider": "openai",
            "model_name": "gpt-5",
            "redacted_prompt_summary": "3 posts for campaign theme",
        },
        format="json",
    )
    assert job_response.status_code == status.HTTP_201_CREATED
    assert job_response.data["status"] == GenerationJob.STATUS_QUEUED
    assert "prompt" not in job_response.data

    cancel_response = auth_client.post(
        f"/api/content-ops/generation-jobs/{job_response.data['id']}/cancel/",
        data={},
        format="json",
    )

    assert cancel_response.status_code == status.HTTP_200_OK
    assert cancel_response.data["status"] == GenerationJob.STATUS_CANCELLED
    assert "prompt" not in cancel_response.data


@pytest.mark.django_db
def test_generation_job_create_ignores_internal_result_fields(auth_client):
    workspace_id = _create_workspace(auth_client)

    response = auth_client.post(
        "/api/content-ops/generation-jobs/",
        data={
            "workspace": workspace_id,
            "job_type": GenerationJob.TYPE_CAPTION,
            "provider": "openai",
            "model_name": "gpt-5",
            "input_fingerprint": "client-supplied-fingerprint",
            "prompt_policy_result": {"unsafe": True},
            "result_summary": {"raw_response": "secret"},
            "error_code": "forced_failure",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["input_fingerprint"] == ""
    assert response.data["prompt_policy_result"] == {}
    assert response.data["result_summary"] == {}
    assert response.data["error_code"] == ""


@pytest.mark.django_db
def test_media_asset_direct_create_requires_upload_endpoint(auth_client):
    workspace_id = _create_workspace(auth_client)

    response = auth_client.post(
        "/api/content-ops/assets/",
        data={
            "workspace": workspace_id,
            "source": MediaAsset.SOURCE_UPLOADED,
            "storage_key": "private/tenant/raw.png",
            "mime_type": "image/png",
            "ai_lineage": {"provider_raw": "secret"},
            "status": MediaAsset.STATUS_QUARANTINED,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.data["reason"] == "asset_upload_required"
    assert MediaAsset.all_objects.count() == 0


@pytest.mark.django_db
def test_media_asset_upload_returns_download_url_and_hides_storage(
    auth_client,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    upload = SimpleUploadedFile(
        "../../campaign.png",
        b"fake image bytes",
        content_type="image/png",
    )

    response = auth_client.post(
        "/api/content-ops/assets/upload/",
        data={
            "workspace": workspace_id,
            "file": upload,
            "alt_text": "Campaign image",
            "storage_key": "../../unsafe.png",
            "ai_lineage": "secret",
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert "storage_key" not in response.data
    assert "ai_lineage" not in response.data
    assert response.data["status"] == MediaAsset.STATUS_AVAILABLE
    assert response.data["download_url"].endswith(
        f"/api/content-ops/assets/{response.data['id']}/download/"
    )
    asset = MediaAsset.all_objects.get(id=response.data["id"])
    assert str(asset.tenant_id) in asset.storage_key
    assert str(asset.workspace_id) in asset.storage_key
    assert asset.storage_key.endswith("/campaign.png")
    assert asset.ai_lineage == {}
    assert (tmp_path / asset.storage_key).read_bytes() == b"fake image bytes"

    download_response = auth_client.get(
        f"/api/content-ops/assets/{response.data['id']}/download/"
    )

    assert download_response.status_code == status.HTTP_200_OK
    assert download_response["Content-Type"] == "image/png"
    assert b"".join(download_response.streaming_content) == b"fake image bytes"


@pytest.mark.django_db
def test_media_asset_patch_cannot_mutate_server_owned_storage_fields(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="content_ops/assets/original/image.png",
        mime_type="image/png",
        status=MediaAsset.STATUS_AVAILABLE,
        alt_text="Original alt",
    )

    response = auth_client.patch(
        f"/api/content-ops/assets/{asset.id}/",
        data={
            "storage_key": "content_ops/assets/forged/file.mp4",
            "source": MediaAsset.SOURCE_IMPORTED,
            "mime_type": "video/mp4",
            "status": MediaAsset.STATUS_QUARANTINED,
            "renditions": {"thumb": "secret-url"},
            "alt_text": "Updated alt",
        },
        format="json",
    )

    asset.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert "storage_key" not in response.data
    assert asset.storage_key == "content_ops/assets/original/image.png"
    assert asset.source == MediaAsset.SOURCE_UPLOADED
    assert asset.mime_type == "image/png"
    assert asset.status == MediaAsset.STATUS_AVAILABLE
    assert asset.renditions == {}
    assert asset.alt_text == "Updated alt"


@pytest.mark.django_db
def test_media_asset_upload_rejects_unsupported_mime_type(auth_client, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    upload = SimpleUploadedFile(
        "raw.txt",
        b"not media",
        content_type="text/plain",
    )

    response = auth_client.post(
        "/api/content-ops/assets/upload/",
        data={"workspace": workspace_id, "file": upload},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == "asset_mime_type_unsupported"
    assert MediaAsset.all_objects.count() == 0


@pytest.mark.django_db
def test_media_asset_download_rejects_unsafe_storage_key(auth_client, tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="content_ops/assets/../../outside.png",
        mime_type="image/png",
    )

    response = auth_client.get(f"/api/content-ops/assets/{asset.id}/download/")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data["reason"] == "asset_storage_key_invalid"


@pytest.mark.django_db
def test_publishing_identity_create_hides_credentials_and_readiness(auth_client, tenant):
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_identity",
        granted_scopes=["pages_manage_posts"],
    )
    credential.set_raw_tokens("meta-access-token", None)
    credential.save()

    response = auth_client.post(
        "/api/content-ops/publishing-identities/",
        data={
            "platform": PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
            "meta_page_id": "page_identity",
            "display_name": "Identity Page",
            "credential_ref": str(credential.id),
            "selection_state": PublishingIdentity.SELECTION_SELECTED,
            "publish_readiness_state": PublishingIdentity.READINESS_READY,
            "publish_readiness_reason": "client-forced",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert "credential_ref" not in response.data
    assert response.data["publish_readiness_state"] == PublishingIdentity.READINESS_UNKNOWN
    assert response.data["publish_readiness_reason"] == ""


@pytest.mark.django_db
def test_retry_requeues_failed_retryable_publish_attempt(auth_client, tenant):
    attempt = _create_retryable_attempt(tenant=tenant)

    response = auth_client.post(
        f"/api/content-ops/publishing/attempts/{attempt.id}/retry/",
        data={},
        format="json",
    )

    attempt.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert response.data["reason"] == "requeued"
    assert response.data["attempt"]["state"] == PublishAttempt.STATE_QUEUED
    assert attempt.state == PublishAttempt.STATE_QUEUED
    assert attempt.failure_code == ""
    assert attempt.failure_detail_safe == ""
    assert attempt.next_retry_at is None


@pytest.mark.django_db
def test_retry_rejects_non_retryable_publish_attempt(auth_client, tenant):
    attempt = _create_retryable_attempt(tenant=tenant)
    attempt.state = PublishAttempt.STATE_FAILED_TERMINAL
    attempt.save(update_fields=["state", "updated_at"])

    response = auth_client.post(
        f"/api/content-ops/publishing/attempts/{attempt.id}/retry/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == "attempt_state_not_publishable"


@pytest.mark.django_db
def test_analyst_cannot_retry_publish_attempt(api_client, tenant):
    analyst = _user_with_role(tenant, Role.ANALYST, "retry-analyst@example.com")
    attempt = _create_retryable_attempt(tenant=tenant)
    api_client.force_authenticate(user=analyst)

    response = api_client.post(
        f"/api/content-ops/publishing/attempts/{attempt.id}/retry/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_publish_attempt_list_filters_by_schedule_window(auth_client, tenant):
    older = _create_retryable_attempt(tenant=tenant)
    older.schedule.scheduled_at = timezone.now() - timezone.timedelta(days=3)
    older.schedule.save(update_fields=["scheduled_at", "updated_at"])
    current = _create_retryable_attempt(tenant=tenant)
    current.schedule.scheduled_at = timezone.now()
    current.schedule.save(update_fields=["scheduled_at", "updated_at"])
    future = _create_retryable_attempt(tenant=tenant)
    future.schedule.scheduled_at = timezone.now() + timezone.timedelta(days=3)
    future.schedule.save(update_fields=["scheduled_at", "updated_at"])

    response = auth_client.get(
        "/api/content-ops/publishing/attempts/",
        {
            "scheduled_from": (timezone.now() - timezone.timedelta(hours=1)).isoformat(),
            "scheduled_to": (timezone.now() + timezone.timedelta(hours=1)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in response.data["results"]}
    assert ids == {str(current.id)}


@pytest.mark.django_db
def test_publish_attempt_list_filters_retry_due(auth_client, tenant):
    due = _create_retryable_attempt(tenant=tenant)
    due.next_retry_at = timezone.now() - timezone.timedelta(minutes=1)
    due.save(update_fields=["next_retry_at", "updated_at"])
    future = _create_retryable_attempt(tenant=tenant)
    future.next_retry_at = timezone.now() + timezone.timedelta(minutes=10)
    future.save(update_fields=["next_retry_at", "updated_at"])

    response = auth_client.get(
        "/api/content-ops/publishing/attempts/",
        {"retry_due": "true"},
    )

    assert response.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in response.data["results"]}
    assert ids == {str(due.id)}


@pytest.mark.django_db
def test_publish_attempt_list_rejects_invalid_schedule_filter(auth_client):
    response = auth_client.get(
        "/api/content-ops/publishing/attempts/",
        {"scheduled_from": "not-a-datetime"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "scheduled_from" in response.data


@pytest.mark.django_db
def test_readiness_keeps_publishing_and_reporting_axes_separate(auth_client, tenant, user):
    _create_meta_publishing_state(tenant=tenant, user=user)

    response = auth_client.get("/api/content-ops/readiness/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["meta_auth"]["state"] == "connected"
    assert response.data["page_selection"]["state"] == "complete"
    assert response.data["instagram_linkage"]["state"] == "complete"
    assert response.data["facebook_page_publishing"]["state"] == "ready"
    assert response.data["facebook_page_publishing"]["missing_permissions"] == []
    assert response.data["instagram_publishing"]["state"] == "ready"
    assert response.data["instagram_publishing"]["missing_permissions"] == []
    assert response.data["reporting_readiness"]["state"] == "blocked"
    assert (
        response.data["reporting_readiness"]["dataset_live_reason"]
        != response.data["facebook_page_publishing"]["state"]
    )


@pytest.mark.django_db
def test_readiness_reports_each_blocker_independently(auth_client):
    response = auth_client.get("/api/content-ops/readiness/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["meta_auth"]["state"] == "not_connected"
    assert response.data["page_selection"]["reason"] == "meta_auth_required"
    assert response.data["instagram_linkage"]["reason"] == "meta_auth_required"
    assert (
        response.data["facebook_page_publishing"]["reason"]
        == "publishing_identity_missing"
    )
    assert (
        response.data["instagram_publishing"]["reason"]
        == "publishing_identity_missing"
    )
    assert "reporting_readiness" in response.data


@pytest.mark.django_db
def test_readiness_blocks_unknown_publishing_identity(auth_client, tenant, user):
    _create_meta_publishing_state(
        tenant=tenant,
        user=user,
        facebook_readiness=PublishingIdentity.READINESS_UNKNOWN,
        instagram_readiness=PublishingIdentity.READINESS_UNKNOWN,
    )

    response = auth_client.get("/api/content-ops/readiness/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["facebook_page_publishing"]["state"] == "blocked"
    assert (
        response.data["facebook_page_publishing"]["reason"]
        == "publishing_identity_blocked"
    )
    assert response.data["facebook_page_publishing"]["identity_blockers"] == ["unknown"]
    assert response.data["instagram_publishing"]["state"] == "blocked"
    assert response.data["instagram_publishing"]["identity_blockers"] == ["unknown"]


@pytest.mark.django_db
def test_report_overview_returns_aggregate_content_metrics(auth_client, tenant):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    schedule_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/schedule/",
        data={"scheduled_at": timezone.now().isoformat()},
        format="json",
    )
    assert schedule_response.status_code == status.HTTP_201_CREATED
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)
    metric_date = timezone.now().date()
    OrganicPostMetricSnapshot.all_objects.create(
        tenant=tenant,
        published_post=published_post,
        metric_date=metric_date,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        source="page_post_insights",
        impressions=100,
        reach=80,
        engagements=12,
        clicks=5,
    )

    response = auth_client.get(
        f"/api/content-ops/reports/overview/?workspace_id={workspace_id}"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["drafts_by_state"][ContentDraft.STATE_SCHEDULED] == 1
    assert response.data["schedules_by_state"][ContentSchedule.STATE_SCHEDULED] == 1
    assert response.data["published_posts_by_channel"]["facebook_page"] == 1
    assert response.data["metric_totals"] == {
        "impressions": 100,
        "reach": 80,
        "engagements": 12,
        "clicks": 5,
        "saves": 0,
        "shares": 0,
        "video_views": 0,
    }


@pytest.mark.django_db
def test_report_posts_returns_aggregate_metrics_only(auth_client, tenant):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)
    OrganicPostMetricSnapshot.all_objects.create(
        tenant=tenant,
        published_post=published_post,
        metric_date=timezone.now().date(),
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        source="page_post_insights",
        impressions=42,
        engagements=7,
    )

    response = auth_client.get(
        f"/api/content-ops/reports/posts/?workspace_id={workspace_id}"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    result = response.data["results"][0]
    assert result["metrics"]["impressions"] == 42
    assert result["metrics"]["engagements"] == 7
    forbidden_keys = {"user_id", "viewer_id", "commenter_id", "reaction_user_id"}
    assert forbidden_keys.isdisjoint(result)
    assert forbidden_keys.isdisjoint(result["metrics"])


@pytest.mark.django_db
def test_published_post_refresh_metrics_creates_aggregate_snapshot(auth_client, tenant):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)
    metric_time = timezone.now()
    _create_meta_post_insight_points(
        tenant=tenant,
        published_post=published_post,
        end_time=metric_time,
        values={
            "post_impressions": 123,
            "post_impressions_unique": 99,
            "post_clicks": 7,
            "post_reactions_like_total": 4,
            "post_reactions_love_total": 2,
            "post_video_views": 11,
        },
    )

    response = auth_client.post(
        f"/api/content-ops/published-posts/{published_post.id}/refresh-metrics/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["reason"] == "refreshed"
    assert response.data["reporting_link_state"] == PublishedPost.REPORTING_LINKED
    snapshot = OrganicPostMetricSnapshot.all_objects.get(
        published_post=published_post,
        metric_date=metric_time.date(),
        source="meta_post_insights",
    )
    assert response.data["snapshot_id"] == str(snapshot.id)
    assert snapshot.impressions == 123
    assert snapshot.reach == 99
    assert snapshot.clicks == 7
    assert snapshot.engagements == 13
    assert snapshot.video_views == 11
    published_post.refresh_from_db()
    assert published_post.last_metrics_refresh_at is not None


@pytest.mark.django_db
def test_published_post_refresh_metrics_supports_current_meta_post_metric_aliases(auth_client, tenant):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)
    metric_time = timezone.now()
    _create_meta_post_insight_points(
        tenant=tenant,
        published_post=published_post,
        end_time=metric_time,
        values={
            "post_media_view": 123,
            "post_total_media_view_unique": 99,
            "post_clicks": 7,
        },
    )
    post = MetaPost.all_objects.get(tenant=tenant, post_id=published_post.meta_post_id)
    for breakdown_key, value in {"like": 4, "love": 2}.items():
        MetaPostInsightPoint.all_objects.create(
            tenant=tenant,
            post=post,
            metric_key="post_reactions_by_type_total",
            period="lifetime",
            end_time=metric_time,
            value_num=Decimal(value),
            value_json={"like": 4, "love": 2},
            breakdown_key=breakdown_key,
            breakdown_key_normalized=breakdown_key,
            breakdown_json={"key": breakdown_key, "value": value},
        )

    response = auth_client.post(
        f"/api/content-ops/published-posts/{published_post.id}/refresh-metrics/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    snapshot = OrganicPostMetricSnapshot.all_objects.get(
        published_post=published_post,
        metric_date=metric_time.date(),
        source="meta_post_insights",
    )
    assert snapshot.impressions == 123
    assert snapshot.reach == 99
    assert snapshot.clicks == 7
    assert snapshot.engagements == 13


@pytest.mark.django_db
def test_published_post_refresh_metrics_uses_latest_utc_end_time_snapshot(
    auth_client,
    tenant,
):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)
    metric_time = datetime(2026, 6, 16, 4, 15, tzinfo=dt_timezone.utc)
    _create_meta_post_insight_points(
        tenant=tenant,
        published_post=published_post,
        end_time=metric_time,
        values={"post_impressions": 55, "post_clicks": 8},
    )

    response = auth_client.post(
        f"/api/content-ops/published-posts/{published_post.id}/refresh-metrics/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    snapshot = OrganicPostMetricSnapshot.all_objects.get(
        published_post=published_post,
        metric_date=metric_time.date(),
        source="meta_post_insights",
    )
    assert snapshot.impressions == 55
    assert snapshot.clicks == 8


@pytest.mark.django_db
def test_published_post_refresh_metrics_marks_unavailable_without_provider_rows(
    auth_client,
    tenant,
):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_client_approved_draft(auth_client, workspace_id)
    published_post = _create_published_post(tenant=tenant, draft_id=draft_id)

    response = auth_client.post(
        f"/api/content-ops/published-posts/{published_post.id}/refresh-metrics/",
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["reason"] == "organic_metrics_unavailable"
    assert response.data["reporting_link_state"] == PublishedPost.REPORTING_UNAVAILABLE


@pytest.mark.django_db
def test_refresh_content_published_post_metrics_task_refreshes_one_post(tenant):
    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name="Metrics task")
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Task post",
        state=ContentDraft.STATE_PUBLISHED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Task caption",
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    identity = PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_task",
        display_name="Task Page",
    )
    published_post = PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        publishing_identity=identity,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="task_post",
        published_at=timezone.now(),
    )
    _create_meta_post_insight_points(
        tenant=tenant,
        published_post=published_post,
        end_time=timezone.now(),
        values={"post_impressions": 44, "post_clicks": 6},
    )

    result = refresh_content_published_post_metrics.run(
        tenant_id=str(tenant.id),
        published_post_id=str(published_post.id),
    )

    assert result["status"] == "refreshed"
    snapshot = OrganicPostMetricSnapshot.all_objects.get(published_post=published_post)
    assert snapshot.impressions == 44
    assert snapshot.clicks == 6


@pytest.mark.django_db
def test_refresh_content_published_post_metrics_task_scans_tenant_posts(
    tenant,
    monkeypatch,
):
    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name="Metrics scan")
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Task post",
        state=ContentDraft.STATE_PUBLISHED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Task caption",
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    post = PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="task_scan_post",
        published_at=timezone.now(),
    )

    class DummyResult:
        status = "refreshed"

    calls = []

    def fake_refresh(*, tenant, published_post_id):  # noqa: ANN001
        calls.append((str(tenant.id), str(published_post_id)))
        return DummyResult()

    monkeypatch.setattr("content_ops.tasks.refresh_published_post_metrics", fake_refresh)

    result = refresh_content_published_post_metrics.run(
        tenant_id=str(tenant.id),
        limit=10,
    )

    assert result[str(tenant.id)] == {"scanned": 1, "refreshed": 1, "unavailable": 0}
    assert calls == [(str(tenant.id), str(post.id))]


@pytest.mark.django_db
def test_content_plan_export_is_client_safe(auth_client, tenant):
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    version_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Client-safe caption"},
        format="json",
    )
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="private/tenant/file.png",
        mime_type="image/png",
        width=1080,
        height=1080,
        alt_text="Product image",
    )
    version = ContentDraftVersion.all_objects.get(id=version_response.data["id"])
    version.media_assets.add(asset)

    response = auth_client.post(
        "/api/content-ops/exports/content-plan/",
        data={"workspace_id": workspace_id},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["item_count"] == 1
    exported_asset = response.data["items"][0]["active_version"]["media_assets"][0]
    assert exported_asset["id"] == str(asset.id)
    assert exported_asset["alt_text"] == "Product image"
    assert "storage_key" not in exported_asset
    assert "ai_lineage" not in exported_asset


@pytest.mark.django_db
def test_content_export_artifact_create_list_retrieve_and_download(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    draft_id = _create_draft(auth_client, workspace_id)
    version_response = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Persisted client packet"},
        format="json",
    )
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="private/tenant/export-file.png",
        mime_type="image/png",
        alt_text="Export image",
        ai_lineage={"prompt": "private prompt"},
    )
    version = ContentDraftVersion.all_objects.get(id=version_response.data["id"])
    version.media_assets.add(asset)

    create_response = auth_client.post(
        "/api/content-ops/exports/",
        data={"workspace_id": workspace_id, "states": [ContentDraft.STATE_GENERATED]},
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["export_type"] == ContentExportArtifact.TYPE_CONTENT_PLAN
    assert create_response.data["export_format"] == ContentExportArtifact.FORMAT_JSON
    assert create_response.data["status"] == ContentExportArtifact.STATUS_COMPLETED
    assert create_response.data["item_count"] == 1
    assert create_response.data["download_url"].endswith(
        f"/api/content-ops/exports/{create_response.data['id']}/download/"
    )
    assert "artifact_path" not in create_response.data

    artifact = ContentExportArtifact.all_objects.get(id=create_response.data["id"])
    assert artifact.requested_by_id is not None
    artifact_file = tmp_path / artifact.artifact_path.lstrip("/")
    assert artifact_file.exists()

    list_response = auth_client.get(
        f"/api/content-ops/exports/?workspace_id={workspace_id}"
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in list_response.data["results"]] == [
        create_response.data["id"]
    ]

    retrieve_response = auth_client.get(
        f"/api/content-ops/exports/{create_response.data['id']}/"
    )
    assert retrieve_response.status_code == status.HTTP_200_OK
    assert retrieve_response.data["id"] == create_response.data["id"]

    download_response = auth_client.get(
        f"/api/content-ops/exports/{create_response.data['id']}/download/"
    )
    assert download_response.status_code == status.HTTP_200_OK
    assert download_response["Content-Type"] == "application/json"
    payload = json.loads(b"".join(download_response.streaming_content).decode("utf-8"))
    assert payload["item_count"] == 1
    exported_asset = payload["items"][0]["active_version"]["media_assets"][0]
    assert exported_asset["id"] == str(asset.id)
    assert exported_asset["alt_text"] == "Export image"
    assert "storage_key" not in exported_asset
    assert "ai_lineage" not in exported_asset


@pytest.mark.django_db
def test_content_export_artifact_download_rejects_missing_or_unsafe_paths(
    auth_client,
    tenant,
    settings,
    tmp_path,
):
    settings.REPORT_EXPORT_ARTIFACT_ROOT = tmp_path
    workspace_id = _create_workspace(auth_client)
    workspace = ContentWorkspace.all_objects.get(id=workspace_id)
    missing = ContentExportArtifact.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        artifact_path=f"/content_ops/exports/{tenant.id}/{workspace.id}/missing.json",
        status=ContentExportArtifact.STATUS_COMPLETED,
    )
    unsafe = ContentExportArtifact.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        artifact_path="/content_ops/exports/../../outside.json",
        status=ContentExportArtifact.STATUS_COMPLETED,
    )

    missing_response = auth_client.get(
        f"/api/content-ops/exports/{missing.id}/download/"
    )
    unsafe_response = auth_client.get(
        f"/api/content-ops/exports/{unsafe.id}/download/"
    )

    assert missing_response.status_code == status.HTTP_404_NOT_FOUND
    assert missing_response.data["reason"] == "export_artifact_missing"
    assert unsafe_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert unsafe_response.data["reason"] == "export_artifact_path_unsafe"


def _create_workspace(auth_client: APIClient) -> str:
    response = auth_client.post(
        "/api/content-ops/workspaces/",
        data={
            "name": "June content",
            "objective": "Drive awareness",
            "target_channels": ["facebook_page", "instagram"],
            "timezone": "America/Jamaica",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data["id"]


def _create_client_approved_draft(auth_client: APIClient, workspace_id: str) -> str:
    draft_id = _create_draft(auth_client, workspace_id)
    auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/versions/",
        data={"caption": "Approved"},
        format="json",
    )
    internal_request = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-internal-review/",
        data={},
        format="json",
    )
    assert internal_request.status_code == status.HTTP_201_CREATED
    internal_decision = auth_client.post(
        f"/api/content-ops/approval-requests/{internal_request.data['id']}/decisions/",
        data={"decision": "approved"},
        format="json",
    )
    assert internal_decision.status_code == status.HTTP_201_CREATED
    client_request = auth_client.post(
        f"/api/content-ops/drafts/{draft_id}/submit-client-review/",
        data={},
        format="json",
    )
    assert client_request.status_code == status.HTTP_201_CREATED
    client_decision = auth_client.post(
        f"/api/content-ops/approval-requests/{client_request.data['id']}/decisions/",
        data={"decision": "approved"},
        format="json",
    )
    assert client_decision.status_code == status.HTTP_201_CREATED
    return draft_id


def _create_draft(auth_client: APIClient, workspace_id: str) -> str:
    response = auth_client.post(
        "/api/content-ops/drafts/",
        data={
            "workspace": workspace_id,
            "title": "Launch announcement",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data["id"]


def _create_media_asset(
    *,
    tenant: Tenant,
    workspace: ContentWorkspace,
    tmp_path,
    renditions: dict,
    mime_type: str = "image/png",
) -> MediaAsset:
    asset_id = uuid.uuid4()
    storage_key = f"content_ops/assets/{tenant.id}/{workspace.id}/{asset_id}/image.png"
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


def _create_published_post(*, tenant: Tenant, draft_id: str) -> PublishedPost:
    draft = ContentDraft.all_objects.select_related("workspace", "active_version").get(
        id=draft_id
    )
    identity = PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_report",
        display_name="Report Page",
    )
    return PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=draft.workspace,
        draft=draft,
        version=draft.active_version,
        publishing_identity=identity,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id=f"post_{draft.id}",
        published_at=timezone.now(),
    )


def _create_meta_post_insight_points(
    *,
    tenant: Tenant,
    published_post: PublishedPost,
    end_time,
    values: dict[str, int],
) -> MetaPost:
    user = User.objects.create_user(
        username=f"metrics-{uuid.uuid4()}",
        email=f"metrics-{uuid.uuid4()}@example.com",
        password=None,
        tenant=tenant,
    )
    connection = MetaConnection(
        tenant=tenant,
        user=user,
        scopes=["pages_read_engagement"],
    )
    connection.set_raw_token("page-token")
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id=published_post.publishing_identity.meta_page_id or "page_report",
        name="Report Page",
        can_analyze=True,
        is_default=True,
        perms=["ANALYZE"],
    )
    page.set_raw_page_token("page-token")
    page.save()
    post = MetaPost.all_objects.create(
        tenant=tenant,
        page=page,
        post_id=published_post.meta_post_id,
        permalink_url=published_post.permalink,
        created_time=published_post.published_at,
    )
    for metric_key, value in values.items():
        MetaPostInsightPoint.all_objects.create(
            tenant=tenant,
            post=post,
            metric_key=metric_key,
            period="lifetime",
            end_time=end_time,
            value_num=Decimal(value),
        )
    return post


def _create_retryable_attempt(*, tenant: Tenant) -> PublishAttempt:
    workspace = ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Retry workspace",
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Retry post",
        state=ContentDraft.STATE_PUBLISHING,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Retry caption",
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    schedule = ContentSchedule.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        scheduled_at=timezone.now() - timezone.timedelta(minutes=1),
        state=ContentSchedule.STATE_DISPATCHING,
        approval_snapshot={
            "version_id": str(version.id),
            "approvals": [{"reviewer_type": "client", "status": "approved"}],
        },
    )
    identity = PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id=f"retry_page_{uuid.uuid4()}",
        display_name="Retry Page",
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=PublishingIdentity.READINESS_READY,
    )
    return PublishAttempt.all_objects.create(
        tenant=tenant,
        schedule=schedule,
        draft=draft,
        version=version,
        publishing_identity=identity,
        channel=PublishAttempt.CHANNEL_FACEBOOK_PAGE,
        state=PublishAttempt.STATE_FAILED_RETRYABLE,
        idempotency_key=f"retry:{schedule.id}",
        failure_code="provider_retryable_error",
        failure_detail_safe="Rate limited.",
        next_retry_at=timezone.now() + timezone.timedelta(minutes=5),
        started_at=timezone.now(),
    )


def _user_with_role(tenant: Tenant, role_name: str, email: str) -> User:
    seed_default_roles()
    user = User.objects.create_user(username=email, email=email, tenant=tenant)
    assign_role(user, role_name)
    return user


def _create_meta_publishing_state(
    *,
    tenant: Tenant,
    user: User,
    facebook_readiness: str = PublishingIdentity.READINESS_READY,
    instagram_readiness: str = PublishingIdentity.READINESS_READY,
) -> None:
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        granted_scopes=[
            "pages_manage_posts",
            "instagram_basic",
            "instagram_content_publish",
        ],
    )
    credential.set_raw_tokens("meta-access-token", None)
    credential.save()

    connection = MetaConnection(tenant=tenant, user=user, scopes=["pages_show_list"])
    connection.set_raw_token("page-token")
    connection.save()

    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id="page_123",
        name="Test Page",
        can_analyze=True,
        is_default=True,
        perms=["CREATE_CONTENT"],
    )
    page.set_raw_page_token("page-access-token")
    page.save()

    PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_123",
        display_name="Test Page",
        credential_ref=credential,
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=facebook_readiness,
    )
    PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_INSTAGRAM,
        meta_page_id="page_123",
        ig_user_id="ig_123",
        display_name="Test IG",
        credential_ref=credential,
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=instagram_readiness,
    )
