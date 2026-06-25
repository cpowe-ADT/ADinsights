"""Deterministic brand overlay — the source of truth for footer text + logo.

Image models render literal text and place logos unreliably, so the model only
ever produces the *scene* (and is asked to reserve a calm band + a plain logo
corner). This module paints the real footer text and the real logo on top
deterministically: a gradient scrim guarantees legibility even if the model
ignored the reservation.

The transform is **pure** — no network, no DB, no clock, no RNG — so the same
input always yields the same output bytes (it is therefore idempotent and
pixel-assertable). The caller resolves the brand kit and logo bytes and passes
plain values in; nothing here touches the ORM.
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, field
from functools import lru_cache

from .safe_areas import SAFE_AREA_VERSION, band_fraction, logo_safe_fraction

try:  # Pillow is an optional-at-import dependency; degrade, never 500.
    from PIL import Image, ImageDraw, ImageFont

    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when Pillow is absent
    _PIL_AVAILABLE = False


# --- Tunables (deterministic constants) ---------------------------------------

DEFAULT_SCRIM_HEX = "#101820"
DEFAULT_TEXT_HEX = "#FFFFFF"
SCRIM_MAX_ALPHA = 230          # opacity at the outer edge of the band
SCRIM_TEXT_FLOOR_ALPHA = 200   # minimum opacity under the text rows (legibility)
MIN_CANVAS_PX = 320            # below this the band would dominate — skip
MIN_FONT_PX = 10
LOGO_PAD_FRACTION = 0.04
LOGO_CENTER_FRACTION = 0.30
OUTPUT_MIME = "image/png"
PNG_COMPRESS_LEVEL = 6
# Vendored DejaVu Sans — full Latin + Spanish (es-PE) + symbol coverage. The
# Pillow bundled default is ASCII-only and renders accents/bullets as tofu, so a
# real Unicode font is required and pinned for deterministic rendering.
FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "DejaVuSans.ttf")


class BrandOverlayError(ValueError):
    """Client-safe overlay failure (e.g. undecodable image)."""


class BrandOverlayUnavailable(RuntimeError):
    """Pillow is not installed; the caller maps this to ``overlay_unavailable``."""


@dataclass(frozen=True)
class FooterContent:
    website: str = ""
    contact: str = ""
    handles: tuple[str, ...] = ()
    tagline: str = ""
    background_hex: str = ""
    text_hex: str = ""
    band_position: str = "bottom"
    band_height_pct: float | None = None
    separator: str = " • "
    field_priority: tuple[str, ...] = ()
    uppercase_primary: bool = False
    locale: str = ""

    def is_empty(self) -> bool:
        return not any(
            [self.website, self.contact, self.tagline, list(self.handles or [])]
        )


@dataclass(frozen=True)
class LogoSpec:
    """Logo bytes by variant. The overlay picks light/dark by background luminance."""

    default_bytes: bytes | None = None
    light_bytes: bytes | None = None
    dark_bytes: bytes | None = None

    def is_empty(self) -> bool:
        return not any([self.default_bytes, self.light_bytes, self.dark_bytes])


@dataclass(frozen=True)
class BrandOverlayResult:
    content: bytes
    mime_type: str
    width: int
    height: int
    logo_variant_used: str = ""
    footer_lines: tuple[str, ...] = field(default_factory=tuple)
    band_height_px: int = 0
    overlay_fingerprint: str = ""
    skipped: bool = False
    skip_reason: str = ""


# --- Public API ---------------------------------------------------------------


def apply_brand_overlay(
    image_bytes: bytes,
    *,
    footer: FooterContent | None = None,
    logo: LogoSpec | None = None,
    placement: str = "bottom_right",
    aspect_ratio: str = "",
    safe_area_version: str = SAFE_AREA_VERSION,
) -> BrandOverlayResult:
    """Composite the footer scrim/text and the logo onto a scene image."""

    if not _PIL_AVAILABLE:  # pragma: no cover - tested via monkeypatch
        raise BrandOverlayUnavailable("Pillow is not installed.")
    if not image_bytes:
        raise BrandOverlayError("empty_image")

    try:
        base = Image.open(io.BytesIO(image_bytes))
        base.load()
    except Exception as exc:  # noqa: BLE001 - any decode failure is client-safe
        raise BrandOverlayError("invalid_image") from exc

    width, height = base.size
    base = base.convert("RGBA")

    footer = footer or FooterContent()
    logo = logo or LogoSpec()
    nothing_to_do = footer.is_empty() and logo.is_empty()
    if nothing_to_do:
        return _passthrough(image_bytes, width, height, "nothing_to_apply")
    if min(width, height) < MIN_CANVAS_PX:
        return _passthrough(image_bytes, width, height, "canvas_too_small")

    # Reserve horizontal band space for a bottom-corner logo so footer text is
    # never drawn underneath it.
    reserve_left = reserve_right = 0
    bottom_logo = (
        not logo.is_empty()
        and footer.band_position != "top"
        and placement in ("bottom_left", "bottom_right")
    )
    if bottom_logo and not footer.is_empty():
        pad = max(1, int(LOGO_PAD_FRACTION * min(width, height)))
        reserve = int(width * logo_safe_fraction(aspect_ratio)) + 2 * pad
        if placement == "bottom_right":
            reserve_right = reserve
        else:
            reserve_left = reserve

    band_px = 0
    footer_lines: tuple[str, ...] = ()
    if not footer.is_empty():
        band_px, footer_lines = _draw_footer(
            base, footer, aspect_ratio, reserve_left, reserve_right
        )

    logo_variant = ""
    if not logo.is_empty():
        logo_variant = _draw_logo(
            base, logo, placement, aspect_ratio, band_px, footer.band_position
        )

    out = base.convert("RGB")
    buffer = io.BytesIO()
    out.save(buffer, format="PNG", optimize=False, compress_level=PNG_COMPRESS_LEVEL)
    content = buffer.getvalue()

    fingerprint = _fingerprint(
        image_bytes=image_bytes,
        footer=footer,
        logo_variant=logo_variant,
        placement=placement,
        band_px=band_px,
        footer_lines=footer_lines,
        safe_area_version=safe_area_version,
    )
    return BrandOverlayResult(
        content=content,
        mime_type=OUTPUT_MIME,
        width=width,
        height=height,
        logo_variant_used=logo_variant,
        footer_lines=footer_lines,
        band_height_px=band_px,
        overlay_fingerprint=fingerprint,
    )


# --- Footer scrim + text ------------------------------------------------------


def _draw_footer(
    base,
    footer: FooterContent,
    aspect_ratio: str,
    reserve_left: int = 0,
    reserve_right: int = 0,
) -> tuple[int, tuple[str, ...]]:
    width, height = base.size
    fraction = footer.band_height_pct
    if not fraction or fraction <= 0 or fraction > 1:
        fraction = band_fraction(aspect_ratio, footer.band_position)
    band_px = max(1, int(round(height * float(fraction))))
    top_band = footer.band_position == "top"
    band_y0 = 0 if top_band else height - band_px

    scrim_rgb = _hex_to_rgb(footer.background_hex, DEFAULT_SCRIM_HEX)
    scrim = Image.new("RGBA", (width, band_px), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scrim)
    fade_rows = max(1, int(band_px * 0.35))
    for i in range(band_px):
        # ``depth`` runs 0 at the inner edge → 1 at the outer (image) edge.
        depth = i if not top_band else (band_px - 1 - i)
        if depth < fade_rows:
            alpha = int(SCRIM_TEXT_FLOOR_ALPHA * (depth / fade_rows))
        else:
            span = max(1, band_px - fade_rows - 1)
            ramp = (depth - fade_rows) / span
            alpha = int(
                SCRIM_TEXT_FLOOR_ALPHA
                + (SCRIM_MAX_ALPHA - SCRIM_TEXT_FLOOR_ALPHA) * min(1.0, ramp)
            )
        sdraw.line([(0, i), (width, i)], fill=(*scrim_rgb, alpha))
    base.alpha_composite(scrim, (0, band_y0))

    lines = _footer_lines(footer)
    if not lines:
        return band_px, ()

    text_rgb = _hex_to_rgb(footer.text_hex, DEFAULT_TEXT_HEX)
    draw = ImageDraw.Draw(base)
    margin = int(width * 0.04)
    left = margin + max(0, reserve_left)
    right = width - margin - max(0, reserve_right)
    avail = max(1, right - left)
    max_text_width = int(avail * 0.98)
    center_x = (left + right) // 2
    rendered = _layout_lines(draw, lines, band_px, max_text_width)

    total_h = sum(h for _, _, h in rendered) + max(0, len(rendered) - 1) * int(band_px * 0.08)
    cursor_y = band_y0 + (band_px - total_h) // 2
    for text, font, line_h in rendered:
        text_w = int(draw.textlength(text, font=font))
        x = center_x - text_w // 2
        # Soft shadow so text survives the scrim's lighter top edge.
        draw.text((x + 1, cursor_y + 1), text, font=font, fill=(0, 0, 0, 160))
        draw.text((x, cursor_y), text, font=font, fill=(*text_rgb, 255))
        cursor_y += line_h + int(band_px * 0.08)
    return band_px, tuple(text for text, _, _ in rendered)


def _footer_lines(footer: FooterContent) -> tuple[str, ...]:
    primary = footer.website.strip()
    if primary and footer.uppercase_primary:
        primary = primary.upper()
    secondary_parts = []
    if footer.contact.strip():
        secondary_parts.append(footer.contact.strip())
    secondary_parts.extend(h.strip() for h in (footer.handles or []) if str(h).strip())
    if footer.tagline.strip():
        secondary_parts.append(footer.tagline.strip())
    separator = footer.separator or " • "
    secondary = separator.join(secondary_parts)
    return tuple(line for line in (primary, secondary) if line)


def _layout_lines(draw, lines, band_px, max_width):
    """Fit each line: shrink toward a floor, then middle-truncate. Returns
    a list of (text, font, line_height)."""

    base_sizes = [int(band_px * 0.34), int(band_px * 0.24)]
    rendered = []
    for idx, text in enumerate(lines):
        target = base_sizes[idx] if idx < len(base_sizes) else base_sizes[-1]
        font = _load_font(target)
        size = target
        while size > MIN_FONT_PX and draw.textlength(text, font=font) > max_width:
            size -= 1
            font = _load_font(size)
        if draw.textlength(text, font=font) > max_width:
            text = _middle_truncate(
                lambda s, f=font: draw.textlength(s, font=f), text, max_width
            )
        bbox = draw.textbbox((0, 0), text, font=font)
        rendered.append((text, font, bbox[3] - bbox[1]))
    return rendered


def _middle_truncate(measure, text, max_width):
    ell = "…"
    if measure(text) <= max_width:
        return text
    for keep in range(len(text) - 1, 0, -1):
        head = (keep + 1) // 2
        tail = keep - head
        candidate = text[:head] + ell + (text[len(text) - tail:] if tail else "")
        if measure(candidate) <= max_width:
            return candidate
    return ell


# --- Logo ---------------------------------------------------------------------


def _draw_logo(base, logo: LogoSpec, placement, aspect_ratio, band_px, band_position):
    width, height = base.size
    pad = max(1, int(LOGO_PAD_FRACTION * min(width, height)))
    in_bottom_band = (
        band_px > 0 and band_position != "top" and placement.startswith("bottom")
    )

    if placement == "center":
        box_w = box_h = int(min(width, height) * LOGO_CENTER_FRACTION)
    else:
        corner = logo_safe_fraction(aspect_ratio)
        box_w = int(width * corner)
        box_h = int(band_px * 0.8) if in_bottom_band else int(height * corner)
    box_w = max(1, box_w)
    box_h = max(1, box_h)

    # Sample the target region's luminance BEFORE compositing to pick the variant.
    region = _placement_region(width, height, box_w, box_h, placement, pad, band_px, in_bottom_band)
    variant, logo_bytes = _select_logo_variant(logo, base, region)
    if logo_bytes is None:
        return ""
    try:
        logo_img = Image.open(io.BytesIO(logo_bytes))
        logo_img.load()
        logo_img = logo_img.convert("RGBA")
    except Exception:  # noqa: BLE001 - a bad logo never breaks the scene
        return ""

    logo_img = _scale_within(logo_img, box_w, box_h)
    lw, lh = logo_img.size
    x, y = _logo_xy(width, height, lw, lh, placement, pad, band_px, in_bottom_band)
    base.alpha_composite(logo_img, (x, y))
    return variant


def _placement_region(width, height, box_w, box_h, placement, pad, band_px, in_bottom_band):
    x, y = _logo_xy(width, height, box_w, box_h, placement, pad, band_px, in_bottom_band)
    return (x, y, min(width, x + box_w), min(height, y + box_h))


def _logo_xy(width, height, lw, lh, placement, pad, band_px, in_bottom_band):
    if placement == "top_left":
        return pad, pad
    if placement == "top_right":
        return width - lw - pad, pad
    if placement == "center":
        return (width - lw) // 2, (height - lh) // 2
    # Bottom corners: sit inside the scrim band when present, else above the edge.
    if in_bottom_band:
        y = height - band_px + (band_px - lh) // 2
    else:
        y = height - lh - pad
    if placement == "bottom_left":
        return pad, max(0, y)
    return width - lw - pad, max(0, y)  # bottom_right (default)


def _select_logo_variant(logo: LogoSpec, base, region):
    luminance = _mean_luminance(base, region)
    prefer_light = luminance < 0.5
    if prefer_light and logo.light_bytes:
        return "light", logo.light_bytes
    if not prefer_light and logo.dark_bytes:
        return "dark", logo.dark_bytes
    if logo.default_bytes:
        return "default", logo.default_bytes
    if logo.light_bytes:
        return "light", logo.light_bytes
    if logo.dark_bytes:
        return "dark", logo.dark_bytes
    return "", None


def _scale_within(img, max_w, max_h):
    lw, lh = img.size
    if lw <= 0 or lh <= 0:
        return img
    scale = min(max_w / lw, max_h / lh, 1.0)  # never upscale past native
    if scale >= 1.0:
        return img
    return img.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.LANCZOS)


# --- Small helpers ------------------------------------------------------------


@lru_cache(maxsize=32)
def _load_font(size: int):
    size = max(MIN_FONT_PX, int(size))
    try:
        return ImageFont.truetype(FONT_PATH, size=size)
    except Exception:  # pragma: no cover - vendored font should always load
        return ImageFont.load_default(size=size)


def _hex_to_rgb(value: str, fallback: str) -> tuple[int, int, int]:
    candidate = (value or "").strip() or fallback
    candidate = candidate.lstrip("#")
    if len(candidate) != 6:
        candidate = fallback.lstrip("#")
    return (
        int(candidate[0:2], 16),
        int(candidate[2:4], 16),
        int(candidate[4:6], 16),
    )


def _mean_luminance(base, region) -> float:
    x0, y0, x1, y1 = region
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(base.size[0], int(x1)), min(base.size[1], int(y1))
    if x1 <= x0 or y1 <= y0:
        return 0.5
    crop = base.convert("RGB").crop((x0, y0, x1, y1)).resize((1, 1), Image.BILINEAR)
    r, g, b = crop.getpixel((0, 0))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _passthrough(image_bytes, width, height, reason) -> BrandOverlayResult:
    return BrandOverlayResult(
        content=image_bytes,
        mime_type=OUTPUT_MIME,
        width=width,
        height=height,
        skipped=True,
        skip_reason=reason,
    )


def _fingerprint(
    *,
    image_bytes,
    footer: FooterContent,
    logo_variant,
    placement,
    band_px,
    footer_lines,
    safe_area_version,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(hashlib.sha256(image_bytes).digest())
    parts = [
        safe_area_version,
        placement,
        logo_variant,
        str(band_px),
        footer.band_position,
        footer.background_hex,
        footer.text_hex,
        "|".join(footer_lines),
    ]
    hasher.update("\x1f".join(parts).encode("utf-8"))
    return hasher.hexdigest()


# --- Media-kind seam (B4: video/carousel slot in here later) ------------------

IMAGE_MEDIA_KIND = "image"


class ImageBrandOverlay:
    """Adapter wrapping :func:`apply_brand_overlay` for the media-kind registry."""

    media_kind = IMAGE_MEDIA_KIND

    def apply(self, image_bytes: bytes, **kwargs) -> BrandOverlayResult:
        return apply_brand_overlay(image_bytes, **kwargs)


_OVERLAYS = {IMAGE_MEDIA_KIND: ImageBrandOverlay()}


def get_overlay(media_kind: str = IMAGE_MEDIA_KIND) -> ImageBrandOverlay:
    overlay = _OVERLAYS.get(media_kind)
    if overlay is None:
        raise BrandOverlayError(f"unsupported_media_kind:{media_kind}")
    return overlay
