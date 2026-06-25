"""Resolve stored brand assets and apply the deterministic overlay to an asset.

This is the *caller* the pure overlay expects: it reads the source scene + the
logo bytes from storage, freezes the footer preset + brand kit into plain
values, runs :func:`content_ops.branding.apply_brand_overlay`, and stores the
result with a reproducibility snapshot (the resolved preset/logo + content
hashes) in ``ai_lineage`` so a later swap or edit can never silently change a
past graphic (spec A4/H7). No provider, no spend.
"""

from __future__ import annotations

import hashlib

from .assets import (
    ContentOpsAssetStorageError,
    asset_file_path,
    store_generated_asset_bytes,
)
from .branding import (
    BrandOverlayError,
    BrandOverlayUnavailable,
    FooterContent,
    LogoSpec,
    apply_brand_overlay,
)
from .models import BrandKit, FooterPreset, MediaAsset
from .safe_areas import SAFE_AREA_VERSION


class OverlayServiceError(ValueError):
    """Client-safe overlay orchestration failure carrying a stable ``reason``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _read_asset_bytes(asset: MediaAsset | None) -> bytes:
    if asset is None or not asset.storage_key:
        return b""
    try:
        path = asset_file_path(asset.storage_key)
    except ContentOpsAssetStorageError:
        return b""
    if not path.exists() or path.stat().st_size <= 0:
        return b""
    return path.read_bytes()


def _footer_from_preset(preset: FooterPreset | None) -> FooterContent | None:
    if preset is None:
        return None
    return FooterContent(
        website=preset.website,
        contact=preset.contact,
        handles=tuple(preset.handles or []),
        tagline=preset.tagline,
        background_hex=preset.background_hex,
        text_hex=preset.text_hex,
        band_position=preset.band_position,
        band_height_pct=(
            float(preset.band_height_pct)
            if preset.band_height_pct is not None
            else None
        ),
        separator=preset.separator or " • ",
        field_priority=tuple(preset.field_priority or []),
        uppercase_primary=preset.uppercase_primary,
        locale=preset.locale,
    )


def _logo_from_brand_kit(brand_kit: BrandKit | None) -> tuple[LogoSpec, dict]:
    if brand_kit is None:
        return LogoSpec(), {}
    snapshot: dict[str, dict] = {}
    resolved: dict[str, bytes | None] = {}
    for key, asset in (
        ("default", brand_kit.default_logo),
        ("light", brand_kit.logo_light),
        ("dark", brand_kit.logo_dark),
    ):
        data = _read_asset_bytes(asset)
        resolved[key] = data or None
        if asset is not None and data:
            snapshot[key] = {
                "asset_id": str(asset.id),
                "content_hash": asset.content_hash or hashlib.sha256(data).hexdigest(),
            }
    spec = LogoSpec(
        default_bytes=resolved["default"],
        light_bytes=resolved["light"],
        dark_bytes=resolved["dark"],
    )
    return spec, snapshot


def _footer_preset_snapshot(preset: FooterPreset | None) -> dict:
    if preset is None:
        return {}
    return {
        "footer_preset_id": str(preset.id),
        "website": preset.website,
        "contact": preset.contact,
        "handles": list(preset.handles or []),
        "tagline": preset.tagline,
        "background_hex": preset.background_hex,
        "text_hex": preset.text_hex,
        "band_position": preset.band_position,
        "band_height_pct": (
            str(preset.band_height_pct) if preset.band_height_pct is not None else ""
        ),
        "uppercase_primary": preset.uppercase_primary,
        "locale": preset.locale,
    }


def apply_overlay_to_asset(
    *,
    tenant,
    source_asset: MediaAsset,
    brand_kit: BrandKit | None = None,
    footer_preset: FooterPreset | None = None,
    placement: str = "",
):
    """Brand an existing image asset and store the result as a new MediaAsset."""

    if source_asset.status != MediaAsset.STATUS_AVAILABLE:
        raise OverlayServiceError("source_not_available")
    if not str(source_asset.mime_type or "").startswith("image/"):
        raise OverlayServiceError("source_not_image")
    source_bytes = _read_asset_bytes(source_asset)
    if not source_bytes:
        raise OverlayServiceError("source_file_missing")

    footer = _footer_from_preset(footer_preset)
    logo, logo_snapshot = _logo_from_brand_kit(brand_kit)
    resolved_placement = placement or (
        brand_kit.logo_placement if brand_kit else "bottom_right"
    )

    try:
        result = apply_brand_overlay(
            source_bytes, footer=footer, logo=logo, placement=resolved_placement
        )
    except BrandOverlayUnavailable as exc:
        raise OverlayServiceError("overlay_unavailable") from exc
    except BrandOverlayError as exc:
        raise OverlayServiceError(str(exc)) from exc

    lineage = {
        "stage": "final",
        "overlay": {
            "fingerprint": result.overlay_fingerprint,
            "safe_area_version": SAFE_AREA_VERSION,
            "logo_variant_used": result.logo_variant_used,
            "band_height_px": result.band_height_px,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
        "source_asset": {
            "asset_id": str(source_asset.id),
            "content_hash": source_asset.content_hash
            or hashlib.sha256(source_bytes).hexdigest(),
        },
        "brand_kit_id": str(brand_kit.id) if brand_kit else "",
        "footer_preset": _footer_preset_snapshot(footer_preset),
        "logo": logo_snapshot,
        "placement": resolved_placement,
    }
    asset = store_generated_asset_bytes(
        tenant=tenant,
        workspace=source_asset.workspace,
        content=result.content,
        mime_type=result.mime_type,
        alt_text=source_asset.alt_text,
        ai_lineage=lineage,
        width=result.width,
        height=result.height,
    )
    return asset, result
