"""Tests for the schedule-time client-approval gate and the agent draft path."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from content_ops.generation import (
    create_caption_generation_job,
    process_content_caption_generation_job,
)
from content_ops.models import (
    ApprovalRequest,
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentSchedule,
    ContentWorkspace,
)

API = "/api/content-ops"


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _workspace(tenant, user=None) -> ContentWorkspace:
    return ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Schedule workspace",
        objective="Publish",
        brand_profile={},
        target_channels=["facebook_page"],
        created_by=user,
    )


def _draft_with_version(tenant, user=None, *, state=ContentDraft.STATE_CLIENT_APPROVED):
    workspace = _workspace(tenant, user)
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Post",
        state=state,
        created_by=user,
        owner=user,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant, draft=draft, version_number=1, caption="Hello world", created_by=user
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    return draft, version


def _client_approval(tenant, draft, version, user=None):
    return ApprovalRequest.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        reviewer_type=ApprovalRequest.REVIEWER_CLIENT,
        status=ApprovalRequest.STATUS_APPROVED,
        requested_by=user,
    )


def _schedule(auth_client, draft_id):
    body = {
        "scheduled_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "channels": ["facebook_page"],
    }
    return auth_client.post(f"{API}/drafts/{draft_id}/schedule/", data=body, format="json")


def _candidate() -> dict:
    return {
        "platform": "facebook_page",
        "caption": "A practical caption for the campaign.",
        "hashtags": ["#ADinsights"],
        "cta": "Learn more",
        "alt_text": "Campaign graphic",
        "risk_flags": [],
        "quality_score": 0.9,
    }


class _FakeCaptionProvider:
    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = candidates

    def generate(self, payload: dict) -> dict:
        return {"candidates": self.candidates, "warnings": []}


# --- model invariant -------------------------------------------------------


@pytest.mark.django_db
def test_has_current_client_approval_true_when_approved(tenant, user):
    draft, version = _draft_with_version(tenant, user)
    _client_approval(tenant, draft, version, user)

    assert draft.has_current_client_approval() is True


@pytest.mark.django_db
def test_has_current_client_approval_false_without_approval(tenant, user):
    draft, _version = _draft_with_version(tenant, user, state=ContentDraft.STATE_GENERATED)

    assert draft.has_current_client_approval() is False


@pytest.mark.django_db
def test_has_current_client_approval_false_when_superseded(tenant, user):
    draft, version = _draft_with_version(tenant, user)
    _client_approval(tenant, draft, version, user)

    draft.invalidate_approvals("edited")

    assert draft.has_current_client_approval() is False


# --- schedule gate ---------------------------------------------------------


@pytest.mark.django_db
def test_schedule_blocked_without_client_approval(auth_client, tenant, user):
    draft, _version = _draft_with_version(tenant, user, state=ContentDraft.STATE_GENERATED)

    response = _schedule(auth_client, draft.id)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "approval" in response.data
    assert ContentSchedule.all_objects.count() == 0


@pytest.mark.django_db
def test_schedule_blocked_after_new_version_supersedes_approval(auth_client, tenant, user):
    draft, version = _draft_with_version(tenant, user)
    _client_approval(tenant, draft, version, user)
    # An edit creates a new active version and supersedes the prior approval.
    new_version = ContentDraftVersion.all_objects.create(
        tenant=tenant, draft=draft, version_number=2, caption="Edited", created_by=user
    )
    draft.active_version = new_version
    draft.save(update_fields=["active_version", "updated_at"])
    draft.invalidate_approvals("edited")

    response = _schedule(auth_client, draft.id)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "approval" in response.data
    assert ContentSchedule.all_objects.count() == 0


@pytest.mark.django_db
def test_schedule_succeeds_with_current_client_approval(auth_client, tenant, user):
    draft, version = _draft_with_version(tenant, user)
    _client_approval(tenant, draft, version, user)

    response = _schedule(auth_client, draft.id)

    assert response.status_code == status.HTTP_201_CREATED
    draft.refresh_from_db()
    assert draft.state == ContentDraft.STATE_SCHEDULED
    schedule = ContentSchedule.all_objects.get(draft=draft)
    assert any(
        entry.get("reviewer_type") == "client"
        for entry in schedule.approval_snapshot["approvals"]
    )


# --- end-to-end: agent-generated draft through approval to schedule --------


@pytest.mark.django_db
def test_agent_generated_draft_flows_through_approval_to_schedule(auth_client, tenant, user):
    workspace = _workspace(tenant, user)
    brief = ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme="Launch",
        audience="SMB owners",
        offer="Book now",
        tone="clear",
        status=ContentBrief.STATUS_ACTIVE,
    )
    job = create_caption_generation_job(
        tenant=tenant, brief=brief, user=user, candidate_count=1, platforms=["facebook_page"]
    )
    result = process_content_caption_generation_job(
        job.id, provider=_FakeCaptionProvider([_candidate()])
    )
    draft_id = result.draft_ids[0]

    internal = auth_client.post(f"{API}/drafts/{draft_id}/submit-internal-review/")
    assert internal.status_code == status.HTTP_201_CREATED
    auth_client.post(
        f"{API}/approval-requests/{internal.data['id']}/decisions/",
        data={"decision": "approved"},
        format="json",
    )
    client = auth_client.post(f"{API}/drafts/{draft_id}/submit-client-review/")
    assert client.status_code == status.HTTP_201_CREATED
    auth_client.post(
        f"{API}/approval-requests/{client.data['id']}/decisions/",
        data={"decision": "approved"},
        format="json",
    )

    scheduled = _schedule(auth_client, draft_id)

    assert scheduled.status_code == status.HTTP_201_CREATED
    draft = ContentDraft.all_objects.get(id=draft_id)
    assert draft.state == ContentDraft.STATE_SCHEDULED
