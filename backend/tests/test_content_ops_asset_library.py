"""Slice 1 — asset library + presets data layer, RBAC, and input brief vocab."""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, Tenant, User, assign_role, seed_default_roles
from content_ops import input_brief
from content_ops.assets import store_uploaded_asset
from content_ops.models import (
    BrandKit,
    ContentWorkspace,
    FooterPreset,
    MediaAsset,
    MediaAssetCollection,
    MediaAssetCollectionItem,
    MediaAssetTag,
    MediaAssetTagAssignment,
)

BASE = "/api/content-ops"
PNG = b"\x89PNG\r\n\x1a\nlogo-bytes-aaaa"


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


def _workspace(tenant, user=None) -> ContentWorkspace:
    return ContentWorkspace.all_objects.create(
        tenant=tenant, name="Brand workspace", created_by=user
    )


def _user_with_role(tenant: Tenant, role_name: str, email: str) -> User:
    seed_default_roles()
    actor = User.objects.create_user(username=email, email=email, tenant=tenant)
    assign_role(actor, role_name)
    return actor


def _real_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _logo_asset(tenant, workspace, *, attested=True, variant="") -> MediaAsset:
    return MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key=f"content_ops/assets/{tenant.id}/{workspace.id}/logo/logo.png",
        mime_type="image/png",
        status=MediaAsset.STATUS_AVAILABLE,
        kind=MediaAsset.KIND_LOGO,
        logo_variant=variant,
        usage_rights_attested=attested,
    )


# --- Models smoke -------------------------------------------------------------


def test_asset_library_models_smoke(tenant, user):
    workspace = _workspace(tenant, user)
    footer = FooterPreset.all_objects.create(
        tenant=tenant, workspace=workspace, name="Default footer", website="acme.jm"
    )
    logo = _logo_asset(tenant, workspace)
    kit = BrandKit.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        name="Acme kit",
        default_logo=logo,
        default_footer_preset=footer,
    )
    assert kit.default_logo_id == logo.id
    assert kit.logo_placement == BrandKit.LOGO_PLACEMENT_BOTTOM_RIGHT

    collection = MediaAssetCollection.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        name="Hero logos",
        purpose=MediaAssetCollection.PURPOSE_LOGO_LIBRARY,
    )
    MediaAssetCollectionItem.all_objects.create(
        tenant=tenant, collection=collection, asset=logo, order=0
    )
    assert collection.items.count() == 1

    tag = MediaAssetTag.all_objects.create(
        tenant=tenant, workspace=workspace, label="Q3", slug="q3"
    )
    MediaAssetTagAssignment.all_objects.create(tenant=tenant, tag=tag, asset=logo)
    assert logo.tags.filter(slug="q3").exists()


# --- Storage: content-hash + dedup --------------------------------------------


def test_store_uploaded_asset_hashes_and_dedups(tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path)
    workspace = _workspace(tenant)
    first = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile("a.png", PNG, content_type="image/png"),
        kind=MediaAsset.KIND_LOGO,
    )
    assert first.content_hash and len(first.content_hash) == 64
    assert first.file_size_bytes == len(PNG)
    assert first.kind == MediaAsset.KIND_LOGO

    # Identical bytes + same kind → dedup returns the canonical row.
    second = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile("a-copy.png", PNG, content_type="image/png"),
        kind=MediaAsset.KIND_LOGO,
    )
    assert second.id == first.id
    assert MediaAsset.all_objects.filter(tenant=tenant, kind=MediaAsset.KIND_LOGO).count() == 1

    # Same bytes, different kind → a distinct row (different intent).
    other = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile("a.png", PNG, content_type="image/png"),
        kind=MediaAsset.KIND_REFERENCE,
    )
    assert other.id != first.id


# --- Upload API with facets + filters -----------------------------------------


def test_upload_logo_via_api_and_library_filter(auth_client, tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path)
    workspace = _workspace(tenant)
    resp = auth_client.post(
        f"{BASE}/assets/upload/",
        {
            "workspace": str(workspace.id),
            "kind": MediaAsset.KIND_LOGO,
            "logo_variant": MediaAsset.LOGO_VARIANT_LIGHT,
            "file": SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
        },
        format="multipart",
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.content
    assert resp.json()["kind"] == MediaAsset.KIND_LOGO
    assert resp.json()["logo_variant"] == MediaAsset.LOGO_VARIANT_LIGHT

    listed = auth_client.get(f"{BASE}/assets/?library=logos&workspace_id={workspace.id}")
    assert listed.status_code == status.HTTP_200_OK
    results = listed.json()
    rows = results["results"] if isinstance(results, dict) else results
    assert len(rows) == 1 and rows[0]["kind"] == MediaAsset.KIND_LOGO


def test_upload_rejects_invalid_kind(auth_client, tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path)
    workspace = _workspace(tenant)
    resp = auth_client.post(
        f"{BASE}/assets/upload/",
        {
            "workspace": str(workspace.id),
            "kind": "banana",
            "file": SimpleUploadedFile("x.png", PNG, content_type="image/png"),
        },
        format="multipart",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# --- Reference approval flow + guards -----------------------------------------


def test_reference_approval_requires_attestation(auth_client, tenant):
    workspace = _workspace(tenant)
    asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="content_ops/assets/x/y/z/ref.png",
        mime_type="image/png",
        status=MediaAsset.STATUS_AVAILABLE,
    )
    # Approve before attesting rights → blocked.
    early = auth_client.post(f"{BASE}/assets/{asset.id}/approve-reference/")
    assert early.status_code == status.HTTP_400_BAD_REQUEST
    assert early.json()["reason"] == "usage_rights_required"

    attest = auth_client.post(
        f"{BASE}/assets/{asset.id}/attest-rights/", {"note": "client-owned"}, format="json"
    )
    assert attest.status_code == status.HTTP_200_OK
    assert attest.json()["usage_rights_attested"] is True

    approved = auth_client.post(f"{BASE}/assets/{asset.id}/approve-reference/")
    assert approved.status_code == status.HTTP_200_OK
    body = approved.json()
    assert body["is_approved_reference"] is True
    assert body["kind"] == MediaAsset.KIND_REFERENCE


def test_logo_cannot_be_approved_as_reference(auth_client, tenant):
    workspace = _workspace(tenant)
    logo = _logo_asset(tenant, workspace)
    resp = auth_client.post(f"{BASE}/assets/{logo.id}/approve-reference/")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json()["reason"] == "logo_not_reference"


# --- Brand kit + default logo -------------------------------------------------


def test_brand_kit_set_default_logo(auth_client, tenant):
    workspace = _workspace(tenant)
    kit = BrandKit.all_objects.create(tenant=tenant, workspace=workspace, name="Kit")

    # A non-logo asset cannot be a default logo.
    content_asset = MediaAsset.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key="content_ops/assets/x/y/z/c.png",
        mime_type="image/png",
        status=MediaAsset.STATUS_AVAILABLE,
    )
    bad = auth_client.post(
        f"{BASE}/brand-kits/{kit.id}/set-default-logo/",
        {"logo_asset_id": str(content_asset.id)},
        format="json",
    )
    assert bad.status_code == status.HTTP_400_BAD_REQUEST

    # An un-attested logo is rejected.
    unattested = _logo_asset(tenant, workspace, attested=False)
    blocked = auth_client.post(
        f"{BASE}/brand-kits/{kit.id}/set-default-logo/",
        {"logo_asset_id": str(unattested.id)},
        format="json",
    )
    assert blocked.status_code == status.HTTP_400_BAD_REQUEST
    assert blocked.json()["reason"] == "usage_rights_required"

    # An attested logo with a light variant resolves correctly.
    logo = _logo_asset(tenant, workspace)
    ok = auth_client.post(
        f"{BASE}/brand-kits/{kit.id}/set-default-logo/",
        {"logo_asset_id": str(logo.id), "variant": MediaAsset.LOGO_VARIANT_LIGHT},
        format="json",
    )
    assert ok.status_code == status.HTTP_200_OK
    kit.refresh_from_db()
    assert kit.default_logo_id == logo.id
    assert kit.logo_light_id == logo.id

    resolved = auth_client.get(f"{BASE}/brand-kits/{kit.id}/resolved-logo/?luminance=0.2")
    assert resolved.status_code == status.HTTP_200_OK
    assert resolved.json()["logo_asset_id"] == str(logo.id)
    assert resolved.json()["variant"] == MediaAsset.LOGO_VARIANT_LIGHT


def test_brand_kit_requires_brand_admin(api_client, tenant):
    workspace = _workspace(tenant)
    analyst = _user_with_role(tenant, Role.ANALYST, "analyst@example.com")
    api_client.force_authenticate(user=analyst)
    # Reads are open to any tenant user.
    assert api_client.get(f"{BASE}/brand-kits/").status_code == status.HTTP_200_OK
    # Creating brand identity requires brand-admin.
    resp = api_client.post(
        f"{BASE}/brand-kits/",
        {"workspace": str(workspace.id), "name": "Sneaky kit"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert not BrandKit.all_objects.filter(tenant=tenant).exists()


# --- Footer preset validation -------------------------------------------------


def test_footer_preset_hex_and_band_validation(auth_client, tenant):
    workspace = _workspace(tenant)
    bad_hex = auth_client.post(
        f"{BASE}/footer-presets/",
        {"workspace": str(workspace.id), "name": "F", "background_hex": "navyblue"},
        format="json",
    )
    assert bad_hex.status_code == status.HTTP_400_BAD_REQUEST

    bad_band = auth_client.post(
        f"{BASE}/footer-presets/",
        {"workspace": str(workspace.id), "name": "F", "band_height_pct": "1.5"},
        format="json",
    )
    assert bad_band.status_code == status.HTTP_400_BAD_REQUEST

    ok = auth_client.post(
        f"{BASE}/footer-presets/",
        {
            "workspace": str(workspace.id),
            "name": "Brand footer",
            "background_hex": "#101820",
            "band_height_pct": "0.18",
            "website": "acme.jm",
        },
        format="json",
    )
    assert ok.status_code == status.HTTP_201_CREATED, ok.content


# --- Collections + tags -------------------------------------------------------


def test_collection_item_add_and_remove(auth_client, tenant):
    workspace = _workspace(tenant)
    logo = _logo_asset(tenant, workspace)
    created = auth_client.post(
        f"{BASE}/asset-collections/",
        {"workspace": str(workspace.id), "name": "Refs", "purpose": "reference_library"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    coll_id = created.json()["id"]

    added = auth_client.post(
        f"{BASE}/asset-collections/{coll_id}/items/",
        {"asset": str(logo.id), "order": 2},
        format="json",
    )
    assert added.status_code == status.HTTP_201_CREATED
    items = auth_client.get(f"{BASE}/asset-collections/{coll_id}/items/")
    assert items.json() == [{"asset": str(logo.id), "order": 2}]

    removed = auth_client.delete(f"{BASE}/asset-collections/{coll_id}/items/{logo.id}/")
    assert removed.status_code == status.HTTP_204_NO_CONTENT
    assert auth_client.get(f"{BASE}/asset-collections/{coll_id}/items/").json() == []


def test_tag_create_and_filter_assets(auth_client, tenant):
    workspace = _workspace(tenant)
    logo = _logo_asset(tenant, workspace)
    tag = auth_client.post(
        f"{BASE}/asset-tags/",
        {"workspace": str(workspace.id), "label": "Summer 2026"},
        format="json",
    )
    assert tag.status_code == status.HTTP_201_CREATED
    assert tag.json()["slug"] == "summer-2026"  # auto-derived

    auth_client.post(
        f"{BASE}/assets/{logo.id}/tags/", {"slug": "summer-2026"}, format="json"
    )
    listed = auth_client.get(f"{BASE}/assets/?tag=summer-2026")
    rows = listed.json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [r["id"] for r in rows] == [str(logo.id)]


# --- Apply overlay to an existing asset (deterministic, no AI) ----------------


def test_apply_overlay_to_asset_end_to_end(auth_client, tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path)
    workspace = _workspace(tenant)
    source = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile(
            "scene.png", _real_png(640, 640, (80, 80, 80)), content_type="image/png"
        ),
    )
    logo = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile(
            "logo.png", _real_png(160, 160, (255, 0, 255)), content_type="image/png"
        ),
        kind=MediaAsset.KIND_LOGO,
    )
    footer = FooterPreset.all_objects.create(
        tenant=tenant, workspace=workspace, name="F", website="acme.jm"
    )
    kit = BrandKit.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        name="Kit",
        default_logo=logo,
        logo_placement=BrandKit.LOGO_PLACEMENT_BOTTOM_RIGHT,
    )

    resp = auth_client.post(
        f"{BASE}/assets/{source.id}/apply-overlay/",
        {"brand_kit_id": str(kit.id), "footer_preset_id": str(footer.id)},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.content
    branded = MediaAsset.all_objects.get(id=resp.json()["id"])
    assert branded.source == MediaAsset.SOURCE_AI_GENERATED
    assert branded.status == MediaAsset.STATUS_AVAILABLE
    lineage = branded.ai_lineage
    assert lineage["overlay"]["fingerprint"]
    assert lineage["source_asset"]["asset_id"] == str(source.id)
    # Reproducibility snapshot: source + logo bytes are content-hashed into lineage.
    assert lineage["source_asset"]["content_hash"]
    assert lineage["footer_preset"]["website"] == "acme.jm"
    assert lineage["logo"]["default"]["content_hash"]
    # The branded bytes differ from the source (overlay was actually applied).
    assert branded.content_hash and branded.content_hash != source.content_hash


def test_apply_overlay_requires_inputs(auth_client, tenant, settings, tmp_path):
    settings.CONTENT_OPS_ASSET_ROOT = str(tmp_path)
    workspace = _workspace(tenant)
    source = store_uploaded_asset(
        tenant=tenant,
        workspace=workspace,
        upload=SimpleUploadedFile(
            "s.png", _real_png(640, 640, (20, 20, 20)), content_type="image/png"
        ),
    )
    resp = auth_client.post(f"{BASE}/assets/{source.id}/apply-overlay/", {}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json()["reason"] == "overlay_inputs_required"


# --- Input brief vocabulary + linter (pure, no DB) ----------------------------


def test_post_type_template_defaults_are_valid_enums():
    for post_type, template in input_brief.POST_TYPE_TEMPLATES.items():
        assert post_type in input_brief.POST_TYPES
        defaults = template["defaults"]
        assert defaults["tone"] in input_brief.TONES
        assert defaults["visual_style"] in input_brief.VISUAL_STYLES
        assert defaults["color_direction"] in input_brief.COLOR_DIRECTIONS
        assert defaults["format"] in input_brief.FORMATS
        for mood in template.get("mood_keywords", []):
            assert mood in input_brief.MOOD_KEYWORDS


def _codes(findings):
    return {f["code"] for f in findings}


def test_lint_sections_flags_weak_inputs():
    assert "idea_empty" in _codes(input_brief.lint_sections({"base_idea": ""}))

    url_idea = input_brief.lint_sections(
        {"base_idea": "Visit www.acme.jm for the weekend sale today"}
    )
    assert "literal_text_in_idea" in _codes(url_idea)

    bad_enum = input_brief.lint_sections(
        {"base_idea": "A clean hero shot of the bottle", "post_type": "nope"}
    )
    assert "enum_invalid" in _codes(bad_enum)

    contradiction = input_brief.lint_sections(
        {
            "base_idea": "A bright lifestyle beach scene with friends",
            "must_include": ["beach"],
            "must_avoid": ["beach"],
        }
    )
    assert "contradiction" in _codes(contradiction)

    clean = input_brief.lint_sections(
        {
            "base_idea": "A clean studio shot of our insulated water bottle",
            "post_type": "product_feature",
            "format": "square_1x1",
        }
    )
    assert clean == []


def test_brief_strength_levels():
    assert input_brief.brief_strength({"base_idea": ""}) == "weak"
    assert (
        input_brief.brief_strength(
            {
                "base_idea": "A studio shot of the bottle",
                "post_type": "product_feature",
                "format": "square_1x1",
            }
        )
        == "ok"
    )
    assert (
        input_brief.brief_strength(
            {
                "base_idea": "A studio shot of the bottle on a marble counter",
                "post_type": "product_feature",
                "format": "square_1x1",
                "focal_subject": "insulated bottle",
                "setting": "bright kitchen",
            }
        )
        == "strong"
    )
