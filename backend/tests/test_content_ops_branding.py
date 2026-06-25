"""Deterministic brand-overlay evals (pixel-assertable, no AI, no provider)."""

from __future__ import annotations

import io

import pytest

np = pytest.importorskip("numpy")
from PIL import Image  # noqa: E402 - after importorskip

from content_ops.branding import (  # noqa: E402
    BrandOverlayError,
    FooterContent,
    LogoSpec,
    apply_brand_overlay,
    get_overlay,
)


def _png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _pattern_png(width: int, height: int) -> bytes:
    xs = np.arange(width, dtype=np.uint8)
    ys = np.arange(height, dtype=np.uint8)
    r = np.tile(xs, (height, 1))
    g = np.tile(ys.reshape(-1, 1), (1, width))
    b = (r + g).astype(np.uint8)
    arr = np.dstack([r, g, b]).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _arr(image_bytes: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB"))


def _rel_luminance(rgb: np.ndarray) -> float:
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])


def test_output_dims_and_format_preserved():
    result = apply_brand_overlay(
        _png(1080, 1080, (90, 90, 90)),
        footer=FooterContent(website="acme.jm", contact="876-555-0100"),
    )
    assert result.mime_type == "image/png"
    assert (result.width, result.height) == (1080, 1080)
    img = Image.open(io.BytesIO(result.content))
    assert img.format == "PNG"
    assert img.size == (1080, 1080)


def test_masked_write_subject_pixels_outside_band_identical():
    original = _pattern_png(1024, 1024)
    result = apply_brand_overlay(
        original, footer=FooterContent(website="acme.jm", contact="hello@acme.jm")
    )
    src = _arr(original)
    out = _arr(result.content)
    band_px = result.band_height_px
    assert band_px > 0
    top = src.shape[0] - band_px
    # Everything above the footer band must be pixel-identical (masked write).
    assert np.array_equal(src[:top, :, :], out[:top, :, :])
    # The band itself must have changed (scrim applied).
    assert not np.array_equal(src[top:, :, :], out[top:, :, :])


def test_scrim_darkens_band_and_text_is_legible():
    original = _png(1080, 1080, (200, 200, 200))  # light scene
    result = apply_brand_overlay(
        original,
        footer=FooterContent(website="acme.jm", contact="876-555-0100"),
    )
    src = _arr(original)
    out = _arr(result.content)
    band = out[src.shape[0] - result.band_height_px:, :, :]
    # The dark scrim makes the band markedly darker than the original light scene.
    assert band.mean() < src[-result.band_height_px:, :, :].mean() - 40
    # Legibility: bright (white) text pixels exist against the dark scrim, with a
    # WCAG contrast ratio >= 4.5:1 between the text and the scrim baseline.
    lum = (0.299 * band[..., 0] + 0.587 * band[..., 1] + 0.114 * band[..., 2])
    text_pixel = band.reshape(-1, 3)[np.argmax(lum)]
    scrim_pixel = band.reshape(-1, 3)[np.argmin(lum)]
    l_text = _rel_luminance(text_pixel)
    l_scrim = _rel_luminance(scrim_pixel)
    ratio = (max(l_text, l_scrim) + 0.05) / (min(l_text, l_scrim) + 0.05)
    assert ratio >= 4.5


def test_logo_lands_in_correct_corner_only():
    base = _png(1024, 1024, (40, 40, 40))
    magenta = _png(220, 220, (255, 0, 255))
    result = apply_brand_overlay(
        base, logo=LogoSpec(default_bytes=magenta), placement="bottom_right"
    )
    out = _arr(result.content)
    h, w, _ = out.shape

    def has_magenta(region: np.ndarray) -> bool:
        mask = (region[..., 0] > 200) & (region[..., 1] < 60) & (region[..., 2] > 200)
        return bool(mask.any())

    assert has_magenta(out[h // 2:, w // 2:, :])  # bottom-right
    assert not has_magenta(out[: h // 2, : w // 2, :])  # top-left clear
    assert result.logo_variant_used == "default"


def test_logo_variant_selected_by_background_luminance():
    dark_base = _png(1024, 1024, (15, 15, 15))
    light_logo = _png(200, 200, (255, 0, 255))
    dark_logo = _png(200, 200, (0, 120, 120))
    result = apply_brand_overlay(
        dark_base,
        logo=LogoSpec(light_bytes=light_logo, dark_bytes=dark_logo),
        placement="bottom_right",
    )
    # A dark background calls for the light logo variant.
    assert result.logo_variant_used == "light"


def test_determinism_and_idempotent_fingerprint():
    base = _png(1080, 1080, (70, 90, 110))
    footer = FooterContent(website="acme.jm", contact="876-555-0100")
    logo = LogoSpec(default_bytes=_png(180, 180, (255, 0, 255)))
    a = apply_brand_overlay(base, footer=footer, logo=logo, placement="bottom_right")
    b = apply_brand_overlay(base, footer=footer, logo=logo, placement="bottom_right")
    assert a.content == b.content
    assert a.overlay_fingerprint == b.overlay_fingerprint and a.overlay_fingerprint


def test_es_pe_accented_footer_renders_without_mangling():
    result = apply_brand_overlay(
        _png(1080, 1080, (60, 60, 60)),
        footer=FooterContent(
            website="acme.pe",
            tagline="Atención: diseño para niños — ¡pruébalo!",
            locale="es-PE",
        ),
    )
    joined = " ".join(result.footer_lines)
    # Accented characters survive (font covers them) — not collapsed to an ellipsis.
    assert "Atención" in joined and "diseño" in joined and "niños" in joined
    assert "…" not in result.footer_lines[0]


def test_tiny_canvas_is_skipped_unchanged():
    tiny = _png(120, 120, (10, 10, 10))
    result = apply_brand_overlay(tiny, footer=FooterContent(website="acme.jm"))
    assert result.skipped is True
    assert result.skip_reason == "canvas_too_small"
    assert result.content == tiny


def test_nothing_to_apply_passthrough():
    base = _png(1080, 1080, (10, 10, 10))
    result = apply_brand_overlay(base)
    assert result.skipped is True
    assert result.skip_reason == "nothing_to_apply"
    assert result.content == base


def test_missing_logo_still_applies_footer():
    base = _png(1080, 1080, (200, 200, 200))
    result = apply_brand_overlay(
        base, footer=FooterContent(website="acme.jm"), logo=LogoSpec()
    )
    assert result.skipped is False
    assert result.band_height_px > 0
    assert result.logo_variant_used == ""


def test_invalid_image_raises_client_safe():
    with pytest.raises(BrandOverlayError):
        apply_brand_overlay(b"not-an-image", footer=FooterContent(website="x.jm"))


def test_overlay_font_covers_es_pe_glyphs():
    # Guards against the ASCII-only-default-font regression: every es-PE accent
    # and the bullet/em-dash must render a real glyph, not the .notdef tofu box.
    from content_ops import branding

    font = branding._load_font(40)

    def glyph(ch: str) -> bytes:
        mask = font.getmask(ch)
        return Image.frombytes("L", mask.size, bytes(mask)).tobytes()

    tofu = glyph("")  # private-use codepoint => guaranteed .notdef
    for ch in "ñáéíóúÁÉ¡¿ü•—":
        assert glyph(ch) != tofu, f"overlay font is missing glyph {ch!r}"


def test_media_kind_seam():
    base = _png(1080, 1080, (50, 50, 50))
    overlay = get_overlay("image")
    result = overlay.apply(base, footer=FooterContent(website="acme.jm"))
    assert result.band_height_px > 0
    with pytest.raises(BrandOverlayError):
        get_overlay("hologram")
