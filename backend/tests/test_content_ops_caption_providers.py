"""Tests for the vendor-neutral Content Ops caption providers + usage metering."""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from django.test import override_settings

from content_ops.generation import (
    CAPTION_FAILURE_POLICY_BLOCKED,
    CAPTION_FAILURE_PROVIDER_ERROR,
    CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED,
    CAPTION_FAILURE_TOKEN_QUOTA_EXCEEDED,
    CAPTION_PROCESS_STATUS_FAILED,
    CAPTION_PROCESS_STATUS_SUCCEEDED,
    DisabledCaptionGenerationProvider,
    create_caption_generation_job,
    process_content_caption_generation_job,
)
from content_ops.metering import estimate_cost
from content_ops.models import (
    AIUsageRecord,
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentWorkspace,
    GenerationJob,
)
from content_ops.providers import (
    AnthropicCaptionProvider,
    OpenAICaptionProvider,
    get_caption_provider,
)
from content_ops.providers.base import normalize_caption_payload

OPENAI_SETTINGS = {
    "CONTENT_OPS_TEXT_PROVIDER": "openai",
    "CONTENT_OPS_OPENAI_API_KEY": "test-openai-key",
    "CONTENT_OPS_OPENAI_MODEL": "gpt-5.1",
    "CONTENT_OPS_OPENAI_BASE_URL": "https://api.openai.com/v1",
}
ANTHROPIC_SETTINGS = {
    "CONTENT_OPS_TEXT_PROVIDER": "anthropic",
    "CONTENT_OPS_ANTHROPIC_API_KEY": "test-anthropic-key",
    "CONTENT_OPS_ANTHROPIC_MODEL": "claude-opus-4-8",
    "CONTENT_OPS_ANTHROPIC_BASE_URL": "https://api.anthropic.com/v1",
}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _candidates_json(
    *,
    caption: str = "A practical campaign caption for SMB owners.",
    platform: str = "facebook_page",
) -> str:
    return json.dumps(
        {
            "candidates": [
                {
                    "platform": platform,
                    "caption": caption,
                    "hashtags": ["#ADinsights"],
                    "cta": "Learn more",
                    "alt_text": "Campaign graphic",
                    "risk_flags": [],
                    "quality_score": 0.9,
                }
            ],
            "warnings": [],
        }
    )


def _openai_payload(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80},
    }


def _anthropic_payload(content: str) -> dict:
    return {
        "content": [{"type": "text", "text": content}],
        "usage": {"input_tokens": 130, "output_tokens": 70},
    }


def _install_fake_post(monkeypatch, *, payload=None, error=None, calls=None):
    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        if calls is not None:
            calls.append({"url": url, "json": json, "headers": headers})
        if error is not None:
            raise error
        return _FakeResponse(payload)

    monkeypatch.setattr("httpx.post", fake_post)


def _brief(*, tenant, user=None, required_terms=None, blocked_terms=None) -> ContentBrief:
    workspace = ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Caption workspace",
        objective="Drive qualified enquiries",
        brand_profile={"voice": "clear, premium, practical"},
        target_channels=["facebook_page"],
        created_by=user,
    )
    return ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme="Summer campaign",
        audience="SMB owners",
        offer="Book a consultation",
        tone="clear and practical",
        required_terms=required_terms or [],
        blocked_terms=blocked_terms or [],
        status=ContentBrief.STATUS_ACTIVE,
    )


def _caption_job(*, tenant, brief, user=None) -> GenerationJob:
    return create_caption_generation_job(
        tenant=tenant,
        brief=brief,
        user=user,
        candidate_count=1,
        platforms=["facebook_page"],
    )


@pytest.mark.django_db
@override_settings(**OPENAI_SETTINGS)
def test_openai_provider_creates_draft_and_records_usage(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    calls: list[dict] = []
    _install_fake_post(monkeypatch, payload=_openai_payload(_candidates_json()), calls=calls)

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert job.status == GenerationJob.STATUS_SUCCEEDED
    assert len(result.draft_ids) == 1
    assert ContentDraftVersion.all_objects.filter(draft_id__in=result.draft_ids).count() == 1
    assert calls and calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-openai-key"

    usage = AIUsageRecord.all_objects.get(generation_job=job)
    assert usage.tenant_id == tenant.id
    assert usage.provider == "openai"
    assert usage.input_tokens == 120
    assert usage.output_tokens == 80
    assert usage.total_tokens == 200


@pytest.mark.django_db
@override_settings(**OPENAI_SETTINGS)
def test_caption_output_includes_image_prompt_override(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    content = json.dumps(
        {
            "candidates": [
                {
                    "platform": "facebook_page",
                    "caption": "Plan your next campaign with us.",
                    "hashtags": [],
                    "cta": "",
                    "alt_text": "",
                    "image_prompt": "A sunny beach product flatlay, on-brand colours",
                    "risk_flags": [],
                    "quality_score": 0.8,
                }
            ],
            "warnings": [],
        }
    )
    _install_fake_post(monkeypatch, payload=_openai_payload(content))

    result = process_content_caption_generation_job(job.id)

    assert result.status == CAPTION_PROCESS_STATUS_SUCCEEDED
    version = ContentDraftVersion.all_objects.get(draft_id=result.draft_ids[0])
    assert version.platform_overrides["image_prompt"] == (
        "A sunny beach product flatlay, on-brand colours"
    )


@pytest.mark.django_db
@override_settings(**ANTHROPIC_SETTINGS)
def test_anthropic_provider_creates_draft_and_records_usage(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    calls: list[dict] = []
    _install_fake_post(
        monkeypatch, payload=_anthropic_payload(_candidates_json()), calls=calls
    )

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert job.status == GenerationJob.STATUS_SUCCEEDED
    assert calls and calls[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert calls[0]["headers"]["x-api-key"] == "test-anthropic-key"
    assert calls[0]["headers"]["anthropic-version"] == "2023-06-01"

    usage = AIUsageRecord.all_objects.get(generation_job=job)
    assert usage.provider == "anthropic"
    assert usage.total_tokens == 200


@pytest.mark.django_db
@override_settings(**OPENAI_SETTINGS)
def test_blocked_term_in_provider_output_is_rejected(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user, blocked_terms=["guaranteed"])
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    _install_fake_post(
        monkeypatch,
        payload=_openai_payload(
            _candidates_json(caption="This guaranteed result should be blocked.")
        ),
    )

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_POLICY_BLOCKED
    assert ContentDraft.all_objects.count() == 0
    # Tokens were still spent on the provider call, so usage is still recorded.
    assert AIUsageRecord.all_objects.filter(generation_job=job).count() == 1


@pytest.mark.django_db
@override_settings(**OPENAI_SETTINGS, CONTENT_OPS_TENANT_MONTHLY_TOKEN_CAP=100)
def test_token_quota_cap_blocks_provider_call(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    AIUsageRecord.all_objects.create(
        tenant=tenant,
        generation_job=job,
        provider="openai",
        input_tokens=90,
        output_tokens=60,
        total_tokens=150,
    )
    calls: list[dict] = []
    _install_fake_post(monkeypatch, payload=_openai_payload(_candidates_json()), calls=calls)

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_TOKEN_QUOTA_EXCEEDED
    assert job.status == GenerationJob.STATUS_FAILED
    assert calls == []  # provider was never called
    assert ContentDraft.all_objects.count() == 0
    assert AIUsageRecord.all_objects.filter(generation_job=job).count() == 1  # no new row


@pytest.mark.django_db
@override_settings(**OPENAI_SETTINGS)
def test_provider_http_error_marks_job_failed_without_usage(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    _install_fake_post(monkeypatch, error=httpx.HTTPError("boom"))

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_PROVIDER_ERROR
    assert job.status == GenerationJob.STATUS_FAILED
    assert AIUsageRecord.all_objects.filter(generation_job=job).count() == 0


@pytest.mark.django_db
@override_settings(CONTENT_OPS_TEXT_PROVIDER="openai", CONTENT_OPS_OPENAI_API_KEY=None)
def test_provider_without_key_fails_closed(tenant, user, monkeypatch):
    brief = _brief(tenant=tenant, user=user)
    job = _caption_job(tenant=tenant, brief=brief, user=user)
    calls: list[dict] = []
    _install_fake_post(monkeypatch, payload=_openai_payload(_candidates_json()), calls=calls)

    result = process_content_caption_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == CAPTION_PROCESS_STATUS_FAILED
    assert result.failure_code == CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED
    assert calls == []  # never reached the network


def test_factory_selects_provider_by_setting():
    with override_settings(**OPENAI_SETTINGS):
        assert isinstance(get_caption_provider(), OpenAICaptionProvider)
    with override_settings(**ANTHROPIC_SETTINGS):
        assert isinstance(get_caption_provider(), AnthropicCaptionProvider)
    with override_settings(CONTENT_OPS_TEXT_PROVIDER="disabled"):
        assert isinstance(get_caption_provider(), DisabledCaptionGenerationProvider)


def test_normalize_caption_payload_tolerates_fenced_json():
    raw = "```json\n" + json.dumps(
        {"candidates": [{"platform": "facebook_page", "caption": "Hi", "quality_score": 0.8}]}
    ) + "\n```"

    result = normalize_caption_payload(raw, requested_platforms=["facebook_page"])

    candidate = result["candidates"][0]
    assert candidate["caption"] == "Hi"
    assert candidate["platform"] == "facebook_page"
    assert candidate["hashtags"] == []  # missing keys filled with safe defaults
    assert candidate["quality_score"] == 0.8


def test_normalize_caption_payload_reassigns_unrequested_platform():
    raw = json.dumps(
        {"candidates": [{"platform": "instagram", "caption": "Hi", "quality_score": 0.5}]}
    )

    result = normalize_caption_payload(raw, requested_platforms=["facebook_page"])

    assert result["candidates"][0]["platform"] == "facebook_page"


@override_settings(
    CONTENT_OPS_OPENAI_USD_PER_1K_TOKENS="2",
    CONTENT_OPS_ANTHROPIC_USD_PER_1K_TOKENS="0",
)
def test_estimate_cost_uses_configured_rate():
    assert estimate_cost(provider="openai", total_tokens=1000) == Decimal("2")
    assert estimate_cost(provider="openai", total_tokens=500) == Decimal("1")
    assert estimate_cost(provider="anthropic", total_tokens=1000) == Decimal("0")
    assert estimate_cost(provider="openai", total_tokens=0) == Decimal("0")
