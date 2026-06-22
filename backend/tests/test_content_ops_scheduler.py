from __future__ import annotations

from typing import Any

import pytest
from django.utils import timezone

from accounts.models import Tenant, User
from content_ops.models import (
    ContentDraft,
    ContentDraftVersion,
    ContentSchedule,
    ContentWorkspace,
    PublishingIdentity,
    PublishAttempt,
)
from content_ops.scheduler import dispatch_due_schedules
from content_ops.tasks import dispatch_due_content_schedules
from integrations.models import MetaConnection, MetaPage, PlatformCredential


@pytest.mark.django_db
def test_dispatch_due_schedules_creates_queued_attempt_for_ready_facebook(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    _ready_facebook_state(tenant=tenant, user=user)

    result = dispatch_due_schedules(tenant=tenant)

    schedule.refresh_from_db()
    attempts = list(PublishAttempt.all_objects.filter(schedule=schedule))
    assert result.as_dict() == {
        "scanned": 1,
        "schedules_dispatched": 1,
        "attempts_created": 1,
        "attempts_existing": 0,
        "attempts_blocked": 0,
    }
    assert schedule.state == ContentSchedule.STATE_DISPATCHING
    assert len(attempts) == 1
    assert attempts[0].channel == PublishAttempt.CHANNEL_FACEBOOK_PAGE
    assert attempts[0].state == PublishAttempt.STATE_QUEUED
    assert attempts[0].idempotency_key == (
        f"schedule:{schedule.id}:channel:{PublishAttempt.CHANNEL_FACEBOOK_PAGE}"
    )
    assert attempts[0].meta_container_id == ""


@pytest.mark.django_db
def test_dispatch_due_schedules_blocks_when_identity_missing(tenant):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )

    result = dispatch_due_schedules(tenant=tenant)

    schedule.refresh_from_db()
    attempt = PublishAttempt.all_objects.get(schedule=schedule)
    assert result.attempts_created == 1
    assert result.attempts_blocked == 1
    assert schedule.state == ContentSchedule.STATE_FAILED
    assert attempt.state == PublishAttempt.STATE_BLOCKED
    assert attempt.failure_code == "publishing_identity_missing"
    assert "access_token" not in attempt.failure_detail_safe


@pytest.mark.django_db
def test_dispatch_due_schedules_is_idempotent(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    _ready_facebook_state(tenant=tenant, user=user)

    first = dispatch_due_schedules(tenant=tenant)
    schedule.state = ContentSchedule.STATE_SCHEDULED
    schedule.save(update_fields=["state", "updated_at"])
    second = dispatch_due_schedules(tenant=tenant)

    assert first.attempts_created == 1
    assert second.attempts_created == 0
    assert second.attempts_existing == 1
    assert PublishAttempt.all_objects.filter(schedule=schedule).count() == 1


@pytest.mark.django_db
def test_dispatch_due_schedules_uses_snapshotted_targets_after_workspace_change(
    tenant,
    user,
):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    schedule.draft.workspace.target_channels = [ContentWorkspace.CHANNEL_INSTAGRAM]
    schedule.draft.workspace.save(update_fields=["target_channels", "updated_at"])
    _ready_facebook_state(tenant=tenant, user=user)

    result = dispatch_due_schedules(tenant=tenant)

    attempt = PublishAttempt.all_objects.get(schedule=schedule)
    assert result.attempts_created == 1
    assert attempt.channel == PublishAttempt.CHANNEL_FACEBOOK_PAGE
    assert attempt.idempotency_key == (
        f"schedule:{schedule.id}:channel:{PublishAttempt.CHANNEL_FACEBOOK_PAGE}"
    )


@pytest.mark.django_db
def test_dispatch_due_schedules_selects_explicit_target_identity(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[
            {"type": ContentWorkspace.CHANNEL_FACEBOOK_PAGE, "page_id": "page_b"},
        ],
    )
    _ready_facebook_state(tenant=tenant, user=user)
    PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_b",
        display_name="Dispatch Page B",
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=PublishingIdentity.READINESS_READY,
    )

    result = dispatch_due_schedules(tenant=tenant)

    attempt = PublishAttempt.all_objects.get(schedule=schedule)
    assert result.attempts_created == 1
    assert attempt.state == PublishAttempt.STATE_QUEUED
    assert attempt.publishing_identity is not None
    assert attempt.publishing_identity.meta_page_id == "page_b"
    assert f"schedule:{schedule.id}:target:" in attempt.idempotency_key


@pytest.mark.django_db
def test_dispatch_due_schedules_rejects_stale_approval_snapshot(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    draft = schedule.draft
    stale_version = draft.active_version
    new_version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=2,
        caption="New active version",
    )
    draft.active_version = new_version
    draft.save(update_fields=["active_version", "updated_at"])
    _ready_facebook_state(tenant=tenant, user=user)

    result = dispatch_due_schedules(tenant=tenant)

    schedule.refresh_from_db()
    assert str(schedule.version_id) == str(stale_version.id)
    assert result.schedules_dispatched == 1
    assert result.attempts_created == 0
    assert schedule.state == ContentSchedule.STATE_FAILED
    assert PublishAttempt.all_objects.filter(schedule=schedule).count() == 0


@pytest.mark.django_db
def test_dispatch_due_schedules_rejects_snapshot_without_client_approval(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    schedule.approval_snapshot = {
        "draft_id": str(schedule.draft_id),
        "version_id": str(schedule.version_id),
        "approvals": [
            {"reviewer_type": "internal", "status": "approved"},
        ],
    }
    schedule.save(update_fields=["approval_snapshot", "updated_at"])
    _ready_facebook_state(tenant=tenant, user=user)

    result = dispatch_due_schedules(tenant=tenant)

    schedule.refresh_from_db()
    assert result.schedules_dispatched == 1
    assert result.attempts_created == 0
    assert schedule.state == ContentSchedule.STATE_FAILED
    assert PublishAttempt.all_objects.filter(schedule=schedule).count() == 0


@pytest.mark.django_db
def test_dispatch_due_schedules_keeps_mixed_channel_schedule_dispatching(tenant, user):
    schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[
            ContentWorkspace.CHANNEL_FACEBOOK_PAGE,
            ContentWorkspace.CHANNEL_INSTAGRAM,
        ],
    )
    _ready_facebook_state(tenant=tenant, user=user)

    result = dispatch_due_schedules(tenant=tenant)

    schedule.refresh_from_db()
    attempts = {
        attempt.channel: attempt
        for attempt in PublishAttempt.all_objects.filter(schedule=schedule)
    }
    assert result.attempts_created == 2
    assert result.attempts_blocked == 1
    assert schedule.state == ContentSchedule.STATE_DISPATCHING
    assert attempts[PublishAttempt.CHANNEL_FACEBOOK_PAGE].state == PublishAttempt.STATE_QUEUED
    assert attempts[PublishAttempt.CHANNEL_INSTAGRAM].state == PublishAttempt.STATE_BLOCKED
    assert (
        attempts[PublishAttempt.CHANNEL_INSTAGRAM].failure_code
        == "publishing_identity_missing"
    )


@pytest.mark.django_db
def test_dispatch_due_content_schedules_task_can_target_one_tenant(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    tenant_schedule = _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    other_schedule = _scheduled_draft(
        tenant=other_tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )

    result = dispatch_due_content_schedules.run(tenant_id=str(tenant.id))

    tenant_schedule.refresh_from_db()
    other_schedule.refresh_from_db()
    assert set(result) == {str(tenant.id)}
    assert result[str(tenant.id)]["scanned"] == 1
    assert tenant_schedule.state == ContentSchedule.STATE_FAILED
    assert other_schedule.state == ContentSchedule.STATE_SCHEDULED
    assert PublishAttempt.all_objects.filter(tenant=tenant).count() == 1
    assert PublishAttempt.all_objects.filter(tenant=other_tenant).count() == 0


@pytest.mark.django_db
def test_dispatch_due_content_schedules_task_can_scan_all_tenants(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    _scheduled_draft(
        tenant=tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )
    _scheduled_draft(
        tenant=other_tenant,
        target_channels=[ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
    )

    result = dispatch_due_content_schedules.run()

    assert result[str(tenant.id)]["scanned"] == 1
    assert result[str(other_tenant.id)]["scanned"] == 1
    assert PublishAttempt.all_objects.filter(tenant=tenant).count() == 1
    assert PublishAttempt.all_objects.filter(tenant=other_tenant).count() == 1


def test_content_ops_scheduler_task_allows_five_retries():
    assert dispatch_due_content_schedules.max_retries == 5


def _scheduled_draft(*, tenant, target_channels: list[Any]) -> ContentSchedule:
    workspace = ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Dispatch workspace",
        target_channels=target_channels,
    )
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        title="Due post",
        state=ContentDraft.STATE_CLIENT_APPROVED,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Approved caption",
    )
    draft.active_version = version
    draft.state = ContentDraft.STATE_SCHEDULED
    draft.save(update_fields=["active_version", "state", "updated_at"])
    return ContentSchedule.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        scheduled_at=timezone.now() - timezone.timedelta(minutes=1),
        approval_snapshot={
            "draft_id": str(draft.id),
            "version_id": str(version.id),
            "target_channels": target_channels,
            "approvals": [
                {"reviewer_type": "client", "status": "approved"},
            ],
        },
    )


def _ready_facebook_state(*, tenant, user) -> None:
    if user.tenant_id != tenant.id:
        user = User.objects.create_user(
            username=f"meta-{tenant.id}@example.com",
            email=f"meta-{tenant.id}@example.com",
            tenant=tenant,
        )
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        granted_scopes=["pages_manage_posts"],
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
        name="Dispatch Page",
        can_analyze=True,
        is_default=True,
    )
    page.set_raw_page_token("page-access-token")
    page.save()

    PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_123",
        display_name="Dispatch Page",
        credential_ref=credential,
        selection_state=PublishingIdentity.SELECTION_SELECTED,
        publish_readiness_state=PublishingIdentity.READINESS_READY,
    )
