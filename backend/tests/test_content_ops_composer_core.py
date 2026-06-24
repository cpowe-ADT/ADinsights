"""Provider-free composer core: defaulting, payload, coercion, validation, preview."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from content_ops.input_brief import resolve_sections_defaults
from content_ops.models import BrandKit, ContentWorkspace, RegionalAgentProfile
from content_ops.prompt_contract import (
    build_composer_payload,
    coerce_composed_prompt,
    validate_composed_prompt,
)

BASE = "/api/content-ops"


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _workspace(tenant) -> ContentWorkspace:
    return ContentWorkspace.all_objects.create(tenant=tenant, name="WS")


# --- resolve_sections_defaults ------------------------------------------------


def test_resolve_defaults_precedence_and_provenance(tenant):
    workspace = _workspace(tenant)
    kit = BrandKit.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        name="Kit",
        standing_instructions={"tone": "premium", "visual_style": "studio_product"},
        required_terms=["fresh"],
        blocked_terms=["cheap"],
    )
    agent = RegionalAgentProfile.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        name="PE",
        region=RegionalAgentProfile.REGION_PERU_LATAM,
        brand_voice={"tone": "playful"},
    )
    sections = {
        "base_idea": "A studio shot of the bottle",
        "post_type": "product_feature",
        "format": "square_1x1",
        "tone": "urgent",  # user-set: must win
        "blocked_terms": ["tacky"],
    }
    resolved, provenance = resolve_sections_defaults(sections, brand_kit=kit, agent=agent)

    assert resolved["tone"] == "urgent" and provenance["tone"] == "user"
    assert resolved["visual_style"] == "studio_product" and provenance["visual_style"] == "brand_kit"
    assert resolved["color_direction"] == "brand_palette" and provenance["color_direction"] == "default"
    assert resolved["locale"] == "es-PE" and provenance["locale"] == "agent"
    assert set(resolved["required_terms"]) == {"fresh"}
    assert set(resolved["blocked_terms"]) == {"tacky", "cheap"}


def test_resolve_defaults_brandkit_tone_beats_agent(tenant):
    workspace = _workspace(tenant)
    kit = BrandKit.all_objects.create(
        tenant=tenant, workspace=workspace, name="K",
        standing_instructions={"tone": "premium"},
    )
    agent = RegionalAgentProfile.all_objects.create(
        tenant=tenant, workspace=workspace, name="A",
        region=RegionalAgentProfile.REGION_CARIBBEAN, brand_voice={"tone": "playful"},
    )
    resolved, provenance = resolve_sections_defaults(
        {"base_idea": "x"}, brand_kit=kit, agent=agent
    )
    assert resolved["tone"] == "premium" and provenance["tone"] == "brand_kit"


def test_resolve_defaults_is_idempotent(tenant):
    sections = {"base_idea": "x", "post_type": "event", "format": "story_9x16"}
    once, _ = resolve_sections_defaults(sections)
    twice, _ = resolve_sections_defaults(once)
    assert once == twice


# --- build_composer_payload ---------------------------------------------------


def test_build_payload_maps_and_redacts():
    resolved = {
        "base_idea": "Launch deal contact api_key=ABCDEFGHIJKLMNOP1234567890",
        "post_type": "promo_offer",
        "format": "portrait_4x5",
        "tone": "urgent",
        "visual_style": "bold_graphic",
        "mood_keywords": ["festive", "vibrant"],
        "must_avoid": ["alcohol"],
    }
    payload = build_composer_payload(resolved, logo_corner="top_right")
    assert "ABCDEFGHIJKLMNOP1234567890" not in payload["base_idea"]
    assert payload["aspect_ratio"] == "4:5"  # derived from format
    assert payload["logo_corner"] == "top_right"
    assert "tone: urgent" in payload["brand_style"]
    assert "mood: festive, vibrant" in payload["brand_style"]
    assert payload["must_avoid"] == ["alcohol"]
    # The literal footer is never sent — only whether intent exists.
    assert payload["footer_intent"] is False


# --- coerce_composed_prompt ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("```\nA calm square scene\n```", "A calm square scene"),
        ("Here's the prompt: A calm square scene", "A calm square scene"),
        ('"A calm square scene"', "A calm square scene"),
        ("Sure! A calm square scene", "A calm square scene"),
        ("A calm square scene", "A calm square scene"),
    ],
)
def test_coerce_strips_wrappers(raw, expected):
    assert coerce_composed_prompt(raw) == expected


# --- validate_composed_prompt (Layer-1 eval) ----------------------------------

VALID = (
    "A vibrant studio scene of an insulated bottle in the upper two-thirds, bright "
    "premium lighting and an on-brand teal palette, with a calm low-detail lower band "
    "and a plain bottom-right corner, composed in a square framing."
)


def test_validate_clean_prompt_passes():
    assert validate_composed_prompt(VALID, required_terms=["bottle"], aspect_ratio="1:1") == []


def test_validate_flags_each_violation():
    def codes(**kw):
        return {f["code"] for f in validate_composed_prompt(**kw)}

    assert "url_present" in codes(prompt=VALID + " visit www.acme.jm", aspect_ratio="1:1")
    assert "blocked_term" in codes(prompt=VALID, blocked_terms=["bottle"], aspect_ratio="1:1")
    assert "required_missing" in codes(prompt=VALID, required_terms=["mango"], aspect_ratio="1:1")
    # A busy prompt with no reserved-space language, and a wrong aspect word.
    busy = "A bustling vivid market scene packed edge to edge with people and stalls."
    assert "no_reserved_space" in codes(prompt=busy, aspect_ratio="1:1")
    assert "aspect_unstated" in codes(prompt=busy, aspect_ratio="1:1")
    assert "empty" in codes(prompt="   ")


# --- preview endpoint ---------------------------------------------------------


def test_sections_preview_endpoint(auth_client, tenant):
    workspace = _workspace(tenant)
    kit = BrandKit.all_objects.create(
        tenant=tenant, workspace=workspace, name="K",
        standing_instructions={"visual_style": "lifestyle_photo"},
        logo_placement=BrandKit.LOGO_PLACEMENT_TOP_RIGHT,
    )
    resp = auth_client.post(
        f"{BASE}/sections/preview/",
        {
            "sections": {
                "base_idea": "Community beach cleanup this Saturday",
                "post_type": "event",
                "format": "portrait_4x5",
            },
            "brand_kit_id": str(kit.id),
            "footer_intent": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK, resp.content
    body = resp.json()
    assert body["resolved_sections"]["visual_style"] == "lifestyle_photo"
    assert body["provenance"]["visual_style"] == "brand_kit"
    assert body["strength"] in {"weak", "ok", "strong"}
    assert body["composer_payload"]["aspect_ratio"] == "4:5"
    assert body["composer_payload"]["logo_corner"] == "top_right"
    assert isinstance(body["lint"], list)


def test_sections_preview_requires_sections(auth_client, tenant):
    resp = auth_client.post(f"{BASE}/sections/preview/", {}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_sections_preview_brand_kit_is_tenant_scoped(auth_client, tenant, django_user_model):
    from accounts.models import Tenant

    other = Tenant.objects.create(name="Other")
    other_ws = ContentWorkspace.all_objects.create(tenant=other, name="OWS")
    other_kit = BrandKit.all_objects.create(tenant=other, workspace=other_ws, name="OK")
    resp = auth_client.post(
        f"{BASE}/sections/preview/",
        {"sections": {"base_idea": "x"}, "brand_kit_id": str(other_kit.id)},
        format="json",
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
