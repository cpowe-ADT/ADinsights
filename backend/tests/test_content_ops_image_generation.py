"""Tests for Content Ops AI image generation (job -> asset, quarantine, metering)."""

from __future__ import annotations

import base64

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from content_ops.image_generation import (
    IMAGE_FAILURE_ACTIVE_LIMIT_EXCEEDED,
    IMAGE_FAILURE_IMAGE_LIMIT_EXCEEDED,
    IMAGE_FAILURE_PROVIDER_NOT_CONFIGURED,
    IMAGE_PROCESS_STATUS_FAILED,
    IMAGE_PROCESS_STATUS_SUCCEEDED,
    create_image_generation_job,
    process_content_image_generation_job,
)
from content_ops.models import (
    AIUsageRecord,
    ContentWorkspace,
    GenerationJob,
    MediaAsset,
)
from content_ops.providers.base import ProviderUsage
from content_ops.providers.image_base import GeneratedImage, build_image_prompt
from content_ops.providers.openai_image import OpenAIImageProvider


@pytest.fixture(autouse=True)
def _asset_root(settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path / "assets")


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _workspace(tenant, user=None) -> ContentWorkspace:
    return ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Image workspace",
        objective="Visuals",
        brand_profile={"voice": "bright"},
        target_channels=["facebook_page"],
        created_by=user,
    )


class _FakeImageProvider:
    def __init__(self, images, usage=None) -> None:
        self.images = images
        self.last_usage = usage
        self.payloads: list[dict] = []

    def is_enabled(self) -> bool:
        return True

    def generate(self, payload: dict):
        self.payloads.append(payload)
        return self.images


@pytest.mark.django_db
def test_image_job_creates_ai_generated_asset_with_lineage(tenant, user):
    workspace = _workspace(tenant, user)
    job = create_image_generation_job(
        tenant=tenant,
        workspace=workspace,
        prompt="A bright Caribbean market scene",
        user=user,
        count=1,
    )
    provider = _FakeImageProvider(
        [GeneratedImage(content=b"PNGBYTES", mime_type="image/png", seed="42")],
        usage=ProviderUsage(provider="openai", model="gpt-image-1", images=1),
    )

    result = process_content_image_generation_job(job.id, provider=provider)

    job.refresh_from_db()
    assert result.status == IMAGE_PROCESS_STATUS_SUCCEEDED
    assert job.status == GenerationJob.STATUS_SUCCEEDED
    assert result.available_count == 1
    assert provider.payloads[0]["prompt"] == "A bright Caribbean market scene"

    asset = MediaAsset.all_objects.get(id=result.asset_ids[0])
    assert asset.source == MediaAsset.SOURCE_AI_GENERATED
    assert asset.status == MediaAsset.STATUS_AVAILABLE
    assert asset.ai_lineage["provider"] == "openai"
    assert asset.ai_lineage["model"] == "gpt-image-1"
    assert asset.ai_lineage["prompt_fingerprint"] == job.input_fingerprint
    assert asset.ai_lineage["seed"] == "42"

    usage = AIUsageRecord.all_objects.get(generation_job=job)
    assert usage.provider == "openai"
    assert usage.images == 1


@pytest.mark.django_db
def test_image_job_disabled_provider_fails_closed(tenant, user):
    workspace = _workspace(tenant, user)
    job = create_image_generation_job(
        tenant=tenant, workspace=workspace, prompt="anything", user=user
    )

    result = process_content_image_generation_job(job.id)

    job.refresh_from_db()
    assert result.status == IMAGE_PROCESS_STATUS_FAILED
    assert result.failure_code == IMAGE_FAILURE_PROVIDER_NOT_CONFIGURED
    assert job.status == GenerationJob.STATUS_FAILED
    assert MediaAsset.all_objects.count() == 0


@pytest.mark.django_db
def test_oversized_output_is_quarantined(settings, tenant, user):
    settings.CONTENT_OPS_GENERATED_ASSET_MAX_BYTES = 8
    workspace = _workspace(tenant, user)
    job = create_image_generation_job(
        tenant=tenant, workspace=workspace, prompt="big", user=user
    )
    provider = _FakeImageProvider(
        [GeneratedImage(content=b"0123456789ABCDEF", mime_type="image/png")],
        usage=ProviderUsage(provider="openai", model="m", images=1),
    )

    result = process_content_image_generation_job(job.id, provider=provider)

    assert result.status == IMAGE_PROCESS_STATUS_SUCCEEDED
    assert result.quarantined_count == 1
    assert result.available_count == 0
    asset = MediaAsset.all_objects.get(id=result.asset_ids[0])
    assert asset.status == MediaAsset.STATUS_QUARANTINED
    assert asset.ai_lineage["quarantine_reason"] == "too_large"
    assert asset.storage_key == ""  # rejected bytes are not written to disk


@pytest.mark.django_db
def test_unsupported_mime_output_is_quarantined(tenant, user):
    workspace = _workspace(tenant, user)
    job = create_image_generation_job(
        tenant=tenant, workspace=workspace, prompt="weird", user=user
    )
    provider = _FakeImageProvider(
        [GeneratedImage(content=b"<html>error</html>", mime_type="text/html")],
        usage=ProviderUsage(provider="openai", model="m", images=0),
    )

    result = process_content_image_generation_job(job.id, provider=provider)

    asset = MediaAsset.all_objects.get(id=result.asset_ids[0])
    assert asset.status == MediaAsset.STATUS_QUARANTINED
    assert asset.ai_lineage["quarantine_reason"] == "unsupported_mime"
    assert asset.storage_key == ""  # rejected bytes are not written to disk


@pytest.mark.django_db
def test_image_generate_endpoint_enqueues_redacted_job(auth_client, tenant, user):
    workspace = _workspace(tenant, user)

    response = auth_client.post(
        f"/api/content-ops/workspaces/{workspace.id}/images/generate/",
        data={
            "prompt": "Sunset over Kingston api_key=secret-value",
            "count": 2,
            "size": "1024x1024",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    job = GenerationJob.all_objects.get(id=response.data["id"])
    assert job.job_type == GenerationJob.TYPE_GRAPHIC_BATCH
    assert job.status == GenerationJob.STATUS_QUEUED
    assert job.prompt_policy_result["count"] == 2
    assert job.prompt_policy_result["size"] == "1024x1024"
    assert "secret-value" not in str(response.data).lower()
    assert "secret-value" not in job.prompt_policy_result["prompt"].lower()


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _install_fake_image_post(monkeypatch, *, calls):
    payload = {
        "data": [{"b64_json": base64.b64encode(b"PNGBYTES").decode()}],
        "usage": {},
    }

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse(payload)

    monkeypatch.setattr("httpx.post", fake_post)


def test_openai_image_adapter_omits_response_format_for_gpt_image(monkeypatch):
    calls: list[dict] = []
    _install_fake_image_post(monkeypatch, calls=calls)
    provider = OpenAIImageProvider(
        api_key="k", model="gpt-image-1", base_url="https://api.openai.com/v1", timeout=5
    )

    images = provider.generate({"prompt": "x", "count": 1, "size": "1024x1024"})

    assert len(images) == 1
    assert "response_format" not in calls[0]["json"]


def test_openai_image_adapter_sends_response_format_for_dalle(monkeypatch):
    calls: list[dict] = []
    _install_fake_image_post(monkeypatch, calls=calls)
    provider = OpenAIImageProvider(
        api_key="k", model="dall-e-3", base_url="https://api.openai.com/v1", timeout=5
    )

    provider.generate({"prompt": "x", "count": 1, "size": "1024x1024"})

    assert calls[0]["json"]["response_format"] == "b64_json"


@pytest.mark.django_db
@override_settings(CONTENT_OPS_IMAGE_ACTIVE_JOB_LIMIT=1)
def test_image_active_job_quota_blocks_second_request(auth_client, tenant, user):
    workspace = _workspace(tenant, user)
    create_image_generation_job(
        tenant=tenant, workspace=workspace, prompt="first", user=user
    )

    response = auth_client.post(
        f"/api/content-ops/workspaces/{workspace.id}/images/generate/",
        data={"prompt": "second"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == IMAGE_FAILURE_ACTIVE_LIMIT_EXCEEDED
    assert response.data["quota"]["active_job_count"] == 1


@pytest.mark.django_db
@override_settings(CONTENT_OPS_IMAGE_DAILY_IMAGE_LIMIT=1)
def test_image_daily_image_quota_blocks_high_count(auth_client, tenant, user):
    workspace = _workspace(tenant, user)

    response = auth_client.post(
        f"/api/content-ops/workspaces/{workspace.id}/images/generate/",
        data={"prompt": "many", "count": 2},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["reason"] == IMAGE_FAILURE_IMAGE_LIMIT_EXCEEDED
    assert GenerationJob.all_objects.count() == 0


def _image_response(content: bytes, usage: dict | None = None) -> _FakeResponse:
    return _FakeResponse(
        {"data": [{"b64_json": base64.b64encode(content).decode()}], "usage": usage or {}}
    )


def test_openai_image_adapter_sniffs_png_and_excludes_tokens(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"payload"

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        return _image_response(png, usage={"input_tokens": 500, "output_tokens": 10})

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OpenAIImageProvider(
        api_key="k", model="gpt-image-1", base_url="https://api.openai.com/v1", timeout=5
    )

    images = provider.generate({"prompt": "x", "count": 1, "size": "1024x1024"})

    assert images[0].mime_type == "image/png"
    # image usage must not pollute the text token counters / monthly token cap
    assert provider.last_usage.input_tokens == 0
    assert provider.last_usage.output_tokens == 0
    assert provider.last_usage.images == 1


def test_openai_image_adapter_sniffs_jpeg(monkeypatch):
    jpeg = b"\xff\xd8\xff\xe0" + b"payload"

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        return _image_response(jpeg)

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OpenAIImageProvider(
        api_key="k", model="gpt-image-1", base_url="https://api.openai.com/v1", timeout=5
    )

    images = provider.generate({"prompt": "x", "count": 1, "size": "1024x1024"})

    assert images[0].mime_type == "image/jpeg"


def test_build_image_prompt_folds_in_regional_agent():
    assert build_image_prompt({"prompt": "A market scene"}) == "A market scene"

    enriched = build_image_prompt(
        {
            "prompt": "A market scene",
            "agent": {
                "region": "peru_latam",
                "locale": "es-PE",
                "language": "Spanish",
                "brand_voice": {"tone": "warm"},
            },
        }
    )

    assert "A market scene" in enriched
    assert "es-PE" in enriched
    assert "peru_latam" in enriched
    assert "warm" in enriched
