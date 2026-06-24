"""Tests for Content Ops regional agent profiles + approved-reference plumbing."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Tenant
from content_ops.generation import (
    CAPTION_FAILURE_POLICY_BLOCKED,
    CAPTION_PROCESS_STATUS_FAILED,
    CAPTION_PROCESS_STATUS_SUCCEEDED,
    build_caption_provider_payload,
    create_caption_generation_job,
    process_content_caption_generation_job,
)
from content_ops.models import (
    ContentBrief,
    ContentDraft,
    ContentWorkspace,
    GenerationJob,
    MediaAsset,
    RegionalAgentProfile,
)


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _workspace(tenant, user=None) -> ContentWorkspace:
    return ContentWorkspace.all_objects.create(
        tenant=tenant,
        name="Caption workspace",
        objective="Drive qualified enquiries",
        brand_profile={"voice": "clear, premium, practical"},
        target_channels=["facebook_page"],
        created_by=user,
    )


def _brief(tenant, workspace, *, blocked_terms=None) -> ContentBrief:
    return ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme="Summer campaign",
        audience="SMB owners",
        offer="Book a consultation",
        tone="clear and practical",
        required_terms=[],
        blocked_terms=blocked_terms or [],
        status=ContentBrief.STATUS_ACTIVE,
    )


def _agent(tenant, workspace, *, region=RegionalAgentProfile.REGION_PERU_LATAM, **kwargs):
    return RegionalAgentProfile.all_objects.create(
        tenant=tenant, workspace=workspace, name=kwargs.pop("name", "Agent"), region=region, **kwargs
    )


def _approved_asset(tenant, workspace, *, alt_text, region="", approved=True):
    return MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key=f"ref/{alt_text.replace(' ', '_')}.png",
        mime_type="image/png",
        alt_text=alt_text,
        is_approved_reference=approved,
        reference_region=region,
        status=MediaAsset.STATUS_AVAILABLE,
    )


def _candidate(*, caption="A practical campaign caption.", platform="facebook_page") -> dict:
    return {
        "platform": platform,
        "caption": caption,
        "hashtags": ["#ADinsights"],
        "cta": "Learn more",
        "alt_text": "Campaign graphic",
        "risk_flags": [],
        "quality_score": 0.9,
    }


class _FakeCaptionProvider:
    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = candidates
        self.payloads: list[dict] = []

    def generate(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {"candidates": self.candidates, "warnings": []}


def _ids(response) -> set[str]:
    data = response.data
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return {str(row["id"]) for row in rows}


@pytest.mark.django_db
def test_region_defaults_fill_locale_language_timezone(tenant):
    workspace = _workspace(tenant)

    caribbean = _agent(tenant, workspace, region="caribbean", name="JM")
    peru = _agent(tenant, workspace, region="peru_latam", name="PE")
    custom = _agent(
        tenant, workspace, region="caribbean", name="TT", locale="en-TT", timezone="America/Port_of_Spain"
    )

    assert (caribbean.locale, caribbean.language, caribbean.timezone) == (
        "en-JM",
        "English",
        "America/Jamaica",
    )
    assert (peru.locale, peru.language, peru.timezone) == ("es-PE", "Spanish", "America/Lima")
    assert custom.locale == "en-TT"
    assert custom.timezone == "America/Port_of_Spain"


@pytest.mark.django_db
def test_regional_agent_api_crud_and_tenant_isolation(auth_client, tenant, user):
    workspace = _workspace(tenant, user)

    create = auth_client.post(
        "/api/content-ops/regional-agents/",
        data={"workspace": str(workspace.id), "name": "Peru agent", "region": "peru_latam"},
        format="json",
    )

    assert create.status_code == status.HTTP_201_CREATED
    assert create.data["locale"] == "es-PE"
    assert create.data["timezone"] == "America/Lima"
    agent_id = str(create.data["id"])

    other = Tenant.objects.create(name="Other Tenant")
    other_ws = _workspace(other)
    RegionalAgentProfile.all_objects.create(
        tenant=other, workspace=other_ws, name="Other agent", region="caribbean"
    )

    listing = auth_client.get("/api/content-ops/regional-agents/")
    assert listing.status_code == status.HTTP_200_OK
    assert _ids(listing) == {agent_id}


@pytest.mark.django_db
def test_payload_includes_agent_locale_and_brand_voice(tenant):
    workspace = _workspace(tenant)
    brief = _brief(tenant, workspace)
    agent = _agent(
        tenant, workspace, region="peru_latam", brand_voice={"tone": "warm and direct"}
    )

    payload = build_caption_provider_payload(
        brief=brief, candidate_count=1, platforms=["facebook_page"], agent=agent
    )

    assert payload["agent"]["locale"] == "es-PE"
    assert payload["agent"]["language"] == "Spanish"
    assert payload["agent"]["timezone"] == "America/Lima"
    assert payload["agent"]["brand_voice"] == {"tone": "warm and direct"}


@pytest.mark.django_db
def test_payload_only_includes_approved_in_region_references_without_secrets(tenant):
    workspace = _workspace(tenant)
    brief = _brief(tenant, workspace)
    agent = _agent(tenant, workspace, region="peru_latam")
    _approved_asset(tenant, workspace, alt_text="Generic banner", region="")
    _approved_asset(tenant, workspace, alt_text="Lima market", region="peru_latam")
    _approved_asset(tenant, workspace, alt_text="Kingston beach", region="caribbean")
    _approved_asset(tenant, workspace, alt_text="Unapproved draft", region="", approved=False)

    payload = build_caption_provider_payload(
        brief=brief, candidate_count=1, platforms=["facebook_page"], agent=agent
    )

    refs = payload["agent"]["approved_references"]
    alt_texts = {ref["alt_text"] for ref in refs}
    assert alt_texts == {"Generic banner", "Lima market"}
    rendered = str(refs)
    assert "storage_key" not in rendered
    assert ".png" not in rendered  # storage keys never leak to the provider


@pytest.mark.django_db
def test_generate_captions_endpoint_attaches_agent(auth_client, tenant, user):
    workspace = _workspace(tenant, user)
    brief = _brief(tenant, workspace)
    agent = _agent(tenant, workspace, region="peru_latam")

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={
            "candidate_count": 1,
            "platforms": ["facebook_page"],
            "regional_agent_profile_id": str(agent.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert str(response.data["regional_agent_profile"]) == str(agent.id)
    job = GenerationJob.all_objects.get(id=response.data["id"])
    assert job.regional_agent_profile_id == agent.id
    assert job.prompt_policy_result["region"] == "peru_latam"
    assert job.prompt_policy_result["locale"] == "es-PE"


@pytest.mark.django_db
def test_generate_captions_rejects_agent_from_other_workspace(auth_client, tenant, user):
    workspace_one = _workspace(tenant, user)
    workspace_two = _workspace(tenant, user)
    brief = _brief(tenant, workspace_one)
    agent = _agent(tenant, workspace_two, region="caribbean")

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"regional_agent_profile_id": str(agent.id)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert GenerationJob.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_generate_captions_rejects_cross_tenant_agent(auth_client, tenant, user):
    workspace = _workspace(tenant, user)
    brief = _brief(tenant, workspace)
    other = Tenant.objects.create(name="Other Tenant")
    other_ws = _workspace(other)
    other_agent = RegionalAgentProfile.all_objects.create(
        tenant=other, workspace=other_ws, name="Other", region="caribbean"
    )

    response = auth_client.post(
        f"/api/content-ops/briefs/{brief.id}/captions/generate/",
        data={"regional_agent_profile_id": str(other_agent.id)},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_agent_block_reaches_provider_and_blocked_terms_enforced(tenant, user):
    workspace = _workspace(tenant, user)
    brief = _brief(tenant, workspace)
    agent = _agent(tenant, workspace, region="peru_latam", blocked_terms=["gratis"])

    # A clean caption succeeds and the provider receives the agent block.
    clean_job = create_caption_generation_job(
        tenant=tenant, brief=brief, user=user, candidate_count=1,
        platforms=["facebook_page"], agent=agent,
    )
    clean_provider = _FakeCaptionProvider([_candidate(caption="Reserva tu consulta hoy.")])
    clean_result = process_content_caption_generation_job(clean_job.id, provider=clean_provider)

    assert clean_result.status == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert clean_provider.payloads[0]["agent"]["locale"] == "es-PE"

    # A caption containing the agent's blocked term is rejected.
    blocked_job = create_caption_generation_job(
        tenant=tenant, brief=brief, user=user, candidate_count=1,
        platforms=["facebook_page"], agent=agent,
    )
    blocked_provider = _FakeCaptionProvider([_candidate(caption="Oferta gratis por hoy.")])
    blocked_result = process_content_caption_generation_job(blocked_job.id, provider=blocked_provider)

    blocked_job.refresh_from_db()
    assert blocked_result.status == CAPTION_PROCESS_STATUS_FAILED
    assert blocked_result.failure_code == CAPTION_FAILURE_POLICY_BLOCKED
    assert ContentDraft.all_objects.filter(brief=brief).count() == 1  # only the clean one
