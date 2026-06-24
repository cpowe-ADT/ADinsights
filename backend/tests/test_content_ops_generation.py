from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tenant_context import get_current_tenant_id
from accounts.models import Tenant
from content_ops.generation import (
    CAPTION_FAILURE_ACTIVE_LIMIT_EXCEEDED,
    CAPTION_FAILURE_CANDIDATE_LIMIT_EXCEEDED,
    CAPTION_FAILURE_POLICY_BLOCKED,
    CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED,
    CAPTION_FAILURE_REQUIRED_TERMS_MISSING,
    CAPTION_FAILURE_SCHEMA_INVALID,
    CAPTION_PROCESS_STATUS_FAILED,
    CAPTION_PROCESS_STATUS_NOOP,
    CAPTION_PROCESS_STATUS_SUCCEEDED,
    process_content_caption_generation_job,
)
from content_ops.models import (
    ApprovalRequest,
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentSchedule,
    ContentWorkspace,
    GenerationJob,
    PublishedPost,
    PublishAttempt,
)
from content_ops.tasks import process_content_caption_generation_job as caption_task


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_caption_generate_endpoint_creates_tenant_scoped_queued_job(
    auth_client,
    tenant,
    user,
):
    brief = _brief(
        tenant=tenant,
        campaign_theme="June launch access_token=raw-token sk-livecaption",
        offer="Quote bundle with api_key=secret-value",
    )

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={
            "candidate_count": 2,
            "platforms": ["facebook_page", "instagram"],
            "tone_override": "clear secret=abc123 Bearer token-value",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    job = GenerationJob.all_objects.get(id=response.data["id"])
    assert job.tenant_id == tenant.id
    assert job.workspace_id == brief.workspace_id
    assert job.brief_id == brief.id
    assert job.created_by_id == user.id
    assert job.job_type == GenerationJob.TYPE_CAPTION
    assert job.status == GenerationJob.STATUS_QUEUED
    assert job.provider == "disabled"
    assert job.prompt_policy_result["candidate_count"] == 2
    assert job.prompt_policy_result["platforms"] == ["facebook_page", "instagram"]
    assert job.prompt_policy_result["quota_snapshot"]["active_job_count"] == 0
    rendered = str(response.data).lower()
    assert "prompt" not in response.data
    assert "raw-token" not in rendered
    assert "secret-value" not in rendered
    assert "sk-livecaption" not in rendered
    assert "abc123" not in rendered
    assert "bearer token-value" not in rendered


@pytest.mark.django_db
def test_caption_generate_endpoint_rejects_cross_tenant_brief(auth_client, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    brief = _brief(tenant=other_tenant)

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"candidate_count": 1},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert GenerationJob.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
@override_settings(CONTENT_OPS_CAPTION_ACTIVE_JOB_LIMIT=1)
def test_caption_generate_endpoint_blocks_active_job_quota(auth_client, tenant):
    brief = _brief(tenant=tenant)
    _caption_job(tenant=tenant, brief=brief)

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"candidate_count": 1, "platforms": ["facebook_page"]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == CAPTION_FAILURE_ACTIVE_LIMIT_EXCEEDED
    assert response.data["quota"]["active_job_count"] == 1
    assert GenerationJob.all_objects.filter(tenant=tenant).count() == 1


@pytest.mark.django_db
@override_settings(CONTENT_OPS_CAPTION_DAILY_CANDIDATE_LIMIT=1)
def test_caption_generate_endpoint_blocks_daily_candidate_quota(auth_client, tenant):
    brief = _brief(tenant=tenant)

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"candidate_count": 2, "platforms": ["facebook_page"]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == CAPTION_FAILURE_CANDIDATE_LIMIT_EXCEEDED
    assert response.data["quota"]["rolling_24h_candidate_count"] == 0
    assert GenerationJob.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
@override_settings(CONTENT_OPS_CAPTION_ACTIVE_JOB_LIMIT=1)
def test_caption_generation_quota_is_tenant_scoped(auth_client, tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    other_brief = _brief(tenant=other_tenant)
    _caption_job(tenant=other_tenant, brief=other_brief)
    brief = _brief(tenant=tenant)

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"candidate_count": 1, "platforms": ["facebook_page"]},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["prompt_policy_result"]["quota_snapshot"]["active_job_count"] == 0
    assert GenerationJob.all_objects.filter(tenant=tenant).count() == 1
    assert GenerationJob.all_objects.filter(tenant=other_tenant).count() == 1


@pytest.mark.django_db
def test_fake_caption_provider_success_creates_generated_drafts_and_versions(
    tenant,
    user,
):
    brief = _brief(
        tenant=tenant,
        user=user,
        required_terms=["Terms apply"],
        blocked_terms=["guaranteed"],
    )
    job = _caption_job(
        tenant=tenant,
        brief=brief,
        user=user,
        candidate_count=2,
        platforms=["facebook_page", "instagram"],
        tone_override="premium api_key=provider-secret",
    )
    provider = _FakeCaptionProvider(
        [
            _candidate(
                platform="facebook_page",
                caption="A practical offer for your next campaign. Terms apply.",
            ),
            _candidate(
                platform="instagram",
                caption="Plan the week with a clean campaign push. Terms apply.",
            ),
        ]
    )

    result = process_content_caption_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert job.status == GenerationJob.STATUS_SUCCEEDED
    assert job.error_code == ""
    assert job.result_summary["created_draft_count"] == 2
    assert len(result.draft_ids) == 2
    assert "provider-secret" not in str(provider.payloads[0]).lower()
    drafts = list(
        ContentDraft.all_objects.filter(id__in=result.draft_ids)
        .select_related("active_version")
        .order_by("title")
    )
    assert {draft.state for draft in drafts} == {ContentDraft.STATE_GENERATED}
    assert all(draft.created_by_id == user.id for draft in drafts)
    assert all(draft.active_version_id for draft in drafts)
    versions = ContentDraftVersion.all_objects.filter(
        draft_id__in=result.draft_ids
    ).order_by("created_at")
    assert versions.count() == 2
    for version in versions:
        assert version.source_generation_job_id == job.id
        assert version.caption
        assert set(version.platform_overrides) == {
            "alt_text",
            "cta",
            "hashtags",
            "image_prompt",
            "platform",
            "quality_score",
            "risk_flags",
            "source",
        }
        assert version.platform_overrides["source"] == "caption_generation"
        assert "provider-secret" not in str(version.platform_overrides).lower()

    assert ApprovalRequest.all_objects.count() == 0
    assert ContentSchedule.all_objects.count() == 0
    assert PublishAttempt.all_objects.count() == 0
    assert PublishedPost.all_objects.count() == 0


@pytest.mark.django_db
def test_invalid_caption_provider_schema_marks_job_failed_without_drafts(tenant):
    brief = _brief(tenant=tenant)
    job = _caption_job(tenant=tenant, brief=brief)
    provider = _FakeCaptionProvider(
        [
            {
                "platform": "facebook_page",
                "hashtags": [],
                "cta": "",
                "alt_text": "",
                "risk_flags": [],
                "quality_score": 0.9,
            }
        ]
    )

    result = process_content_caption_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_SCHEMA_INVALID
    assert job.status == GenerationJob.STATUS_FAILED
    assert job.error_code == CAPTION_FAILURE_SCHEMA_INVALID
    assert ContentDraft.all_objects.count() == 0


@pytest.mark.django_db
def test_blocked_terms_reject_caption_candidates(tenant):
    brief = _brief(tenant=tenant, blocked_terms=["guaranteed"])
    job = _caption_job(tenant=tenant, brief=brief)
    provider = _FakeCaptionProvider(
        [
            _candidate(
                caption="This guaranteed result claim should not become a draft."
            )
        ]
    )

    result = process_content_caption_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_POLICY_BLOCKED
    assert job.error_code == CAPTION_FAILURE_POLICY_BLOCKED
    assert ContentDraft.all_objects.count() == 0


@pytest.mark.django_db
def test_missing_required_terms_fails_safely(tenant):
    brief = _brief(tenant=tenant, required_terms=["Terms apply"])
    job = _caption_job(tenant=tenant, brief=brief)
    provider = _FakeCaptionProvider(
        [_candidate(caption="A caption without the required disclaimer.")]
    )

    result = process_content_caption_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_REQUIRED_TERMS_MISSING
    assert job.error_code == CAPTION_FAILURE_REQUIRED_TERMS_MISSING
    assert "required terms" in result.failure_detail_safe.lower()
    assert ContentDraft.all_objects.count() == 0


@pytest.mark.django_db
def test_cancelled_caption_generation_job_is_noop(tenant):
    brief = _brief(tenant=tenant)
    job = _caption_job(tenant=tenant, brief=brief)
    job.status = GenerationJob.STATUS_CANCELLED
    job.save(update_fields=["status", "updated_at"])
    provider = _FakeCaptionProvider([_candidate()])

    result = process_content_caption_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_NOOP
    assert job.status == GenerationJob.STATUS_CANCELLED
    assert provider.payloads == []
    assert ContentDraft.all_objects.count() == 0


@pytest.mark.django_db
def test_disabled_caption_provider_fails_closed(tenant):
    brief = _brief(tenant=tenant)
    job = _caption_job(tenant=tenant, brief=brief)

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED
    assert job.status == GenerationJob.STATUS_FAILED
    assert job.error_code == CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED
    assert "access_token" not in result.failure_detail_safe.lower()
    assert ContentDraft.all_objects.count() == 0


@pytest.mark.django_db
def test_caption_generation_task_returns_processor_result(tenant, monkeypatch):
    brief = _brief(tenant=tenant)
    job = _caption_job(tenant=tenant, brief=brief)

    class DummyResult:
        def as_dict(self):
            return {
                "status": CAPTION_PROCESS_STATUS_SUCCEEDED,
                "job_id": str(job.id),
                "draft_ids": ["draft-id"],
                "failure_code": "",
                "failure_detail_safe": "",
            }

    observed_tenant_ids = []

    def fake_process(*, job_id):  # noqa: ANN001
        assert str(job_id) == str(job.id)
        observed_tenant_ids.append(get_current_tenant_id())
        return DummyResult()

    monkeypatch.setattr("content_ops.tasks.process_caption_generation_job", fake_process)

    result = caption_task.run(str(job.id))

    assert result["status"] == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert result["job_id"] == str(job.id)
    assert observed_tenant_ids == [str(tenant.id)]


def test_caption_generation_task_allows_five_retries():
    assert caption_task.max_retries == 5


def _brief(
    *,
    tenant,
    user=None,
    campaign_theme: str = "Summer campaign",
    offer: str = "Book a consultation",
    required_terms: list[str] | None = None,
    blocked_terms: list[str] | None = None,
) -> ContentBrief:
    workspace = ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Caption workspace",
        objective="Drive qualified enquiries",
        brand_profile={
            "voice": "clear, premium, practical",
            "blocked_terms": ["instant riches"],
        },
        target_channels=["facebook_page", "instagram"],
        created_by=user,
    )
    return ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme=campaign_theme,
        audience="SMB owners",
        offer=offer,
        tone="clear and practical",
        required_terms=required_terms or [],
        blocked_terms=blocked_terms or [],
        status=ContentBrief.STATUS_ACTIVE,
    )


def _caption_job(
    *,
    tenant,
    brief: ContentBrief,
    user=None,
    candidate_count: int = 1,
    platforms: list[str] | None = None,
    tone_override: str = "",
) -> GenerationJob:
    from content_ops.generation import create_caption_generation_job

    return create_caption_generation_job(
        tenant=tenant,
        brief=brief,
        user=user,
        candidate_count=candidate_count,
        platforms=platforms or ["facebook_page"],
        tone_override=tone_override,
    )


def _candidate(
    *,
    platform: str = "facebook_page",
    caption: str = "A useful post caption.",
) -> dict:
    return {
        "platform": platform,
        "caption": caption,
        "hashtags": ["#ADinsights"],
        "cta": "Learn more",
        "alt_text": "Simple campaign graphic",
        "risk_flags": [],
        "quality_score": 0.91,
    }


class _FakeCaptionProvider:
    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = candidates
        self.payloads: list[dict] = []

    def generate(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {
            "candidates": self.candidates,
            "warnings": ["deterministic_fake_provider"],
        }
