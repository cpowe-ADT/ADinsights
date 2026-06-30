from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from content_ops.models import (
    ApprovalRequest,
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentSchedule,
    ContentWorkspace,
    OrganicPostMetricSnapshot,
    PublishedPost,
    PublishingIdentity,
    PublishAttempt,
)


def _draft_graph(tenant: Tenant, *, title: str = "June content"):
    workspace = ContentWorkspace.all_objects.create(tenant=tenant, name=f"{title} workspace")
    brief = ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme=title,
    )
    draft = ContentDraft.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        brief=brief,
        title=title,
    )
    version = ContentDraftVersion.all_objects.create(
        tenant=tenant,
        draft=draft,
        version_number=1,
        caption="Approved caption",
    )
    draft.active_version = version
    draft.save(update_fields=["active_version", "updated_at"])
    return workspace, brief, draft, version


@pytest.mark.django_db
def test_content_workspace_manager_filters_by_current_tenant(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    ContentWorkspace.all_objects.create(tenant=tenant, name="Visible workspace")
    ContentWorkspace.all_objects.create(tenant=other_tenant, name="Hidden workspace")

    with tenant_context(str(tenant.id)):
        assert list(ContentWorkspace.objects.values_list("name", flat=True)) == [
            "Visible workspace"
        ]


@pytest.mark.django_db
def test_draft_invalidate_approvals_supersedes_approved_request(tenant):
    _, _, draft, version = _draft_graph(tenant)
    approval = ApprovalRequest.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        reviewer_type=ApprovalRequest.REVIEWER_CLIENT,
        status=ApprovalRequest.STATUS_APPROVED,
    )

    changed_count = draft.invalidate_approvals("caption_edited")

    approval.refresh_from_db()
    assert changed_count == 1
    assert approval.status == ApprovalRequest.STATUS_SUPERSEDED
    assert approval.superseded_reason == "caption_edited"
    assert approval.superseded_at is not None


@pytest.mark.django_db
def test_publish_attempt_idempotency_key_is_unique_per_tenant(tenant):
    workspace, _, draft, version = _draft_graph(tenant)
    identity = PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_123",
        display_name="Test Page",
    )
    schedule = ContentSchedule.all_objects.create(
        tenant=tenant,
        draft=draft,
        version=version,
        scheduled_at=timezone.now(),
        approval_snapshot={"version_id": str(version.id)},
    )
    PublishAttempt.all_objects.create(
        tenant=tenant,
        schedule=schedule,
        draft=draft,
        version=version,
        publishing_identity=identity,
        channel=PublishAttempt.CHANNEL_FACEBOOK_PAGE,
        idempotency_key="tenant-page-123",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        PublishAttempt.all_objects.create(
            tenant=tenant,
            schedule=schedule,
            draft=draft,
            version=version,
            publishing_identity=identity,
            channel=PublishAttempt.CHANNEL_FACEBOOK_PAGE,
            idempotency_key="tenant-page-123",
        )

    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_workspace, _, other_draft, other_version = _draft_graph(
        other_tenant, title="Other content"
    )
    other_identity = PublishingIdentity.all_objects.create(
        tenant=other_tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_123",
    )
    other_schedule = ContentSchedule.all_objects.create(
        tenant=other_tenant,
        draft=other_draft,
        version=other_version,
        scheduled_at=timezone.now(),
        approval_snapshot={"workspace_id": str(other_workspace.id)},
    )
    PublishAttempt.all_objects.create(
        tenant=other_tenant,
        schedule=other_schedule,
        draft=other_draft,
        version=other_version,
        publishing_identity=other_identity,
        channel=PublishAttempt.CHANNEL_FACEBOOK_PAGE,
        idempotency_key="tenant-page-123",
    )
    assert workspace.tenant_id == tenant.id


@pytest.mark.django_db
def test_organic_metric_snapshot_uses_aggregate_grain_only(tenant):
    workspace, _, draft, version = _draft_graph(tenant)
    identity = PublishingIdentity.all_objects.create(
        tenant=tenant,
        platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        meta_page_id="page_456",
    )
    published_post = PublishedPost.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        draft=draft,
        version=version,
        publishing_identity=identity,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        meta_post_id="post_123",
        published_at=timezone.now(),
    )
    metric_date = timezone.now().date()
    OrganicPostMetricSnapshot.all_objects.create(
        tenant=tenant,
        published_post=published_post,
        metric_date=metric_date,
        channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
        source="page_post_insights",
        impressions=100,
        reach=80,
        engagements=10,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        OrganicPostMetricSnapshot.all_objects.create(
            tenant=tenant,
            published_post=published_post,
            metric_date=metric_date,
            channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
            source="page_post_insights",
        )

    forbidden_field_names = {
        "user_id",
        "viewer_id",
        "commenter_id",
        "reaction_user_id",
        "profile_id",
    }
    model_field_names = {field.name for field in OrganicPostMetricSnapshot._meta.fields}
    assert forbidden_field_names.isdisjoint(model_field_names)
