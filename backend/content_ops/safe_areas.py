"""Versioned safe-area contract — the single source of truth for keep-clear zones.

Both the prompt guidance (the composer/image adapter, later slices) and the
deterministic brand overlay import these fractions, so the zone the model is
asked to reserve and the zone the overlay paints can never drift. Fractions are
of the FINAL canvas, origin top-left.
"""

from __future__ import annotations

SAFE_AREA_VERSION = "1"

# Per logical aspect ratio (the canonical currency, not WxH). ``default`` applies
# to 1:1 and 16:9; tall formats reserve a slightly smaller band and tighter logo
# corner because vertical pixels are scarcer and platform UI crowds the edges.
SAFE_AREAS: dict[str, dict] = {
    "default": {
        "footer": {"y0": 0.82, "y1": 1.0},
        "header": {"y0": 0.0, "y1": 0.18},
        "logo_safe": 0.18,
        "center_safe": {"x0": 0.35, "x1": 0.65, "y0": 0.35, "y1": 0.65},
        "platform_margin": 0.06,
    },
    "9:16": {
        "footer": {"y0": 0.86, "y1": 1.0},
        "header": {"y0": 0.0, "y1": 0.14},
        "logo_safe": 0.16,
        "platform_margin": 0.06,
    },
    "4:5": {
        "footer": {"y0": 0.86, "y1": 1.0},
        "header": {"y0": 0.0, "y1": 0.14},
        "logo_safe": 0.16,
        "platform_margin": 0.04,
    },
}


def _config(aspect_ratio: str) -> dict:
    return SAFE_AREAS.get(aspect_ratio or "", SAFE_AREAS["default"])


def band_fraction(aspect_ratio: str = "", band_position: str = "bottom") -> float:
    """Reserved band height as a fraction of canvas height for this format."""

    cfg = _config(aspect_ratio)
    zone = cfg.get("header" if band_position == "top" else "footer")
    if not zone:
        zone = SAFE_AREAS["default"]["footer"]
    return round(zone["y1"] - zone["y0"], 4)


def logo_safe_fraction(aspect_ratio: str = "") -> float:
    """Corner logo box as a fraction of canvas width for this format."""

    return _config(aspect_ratio).get(
        "logo_safe", SAFE_AREAS["default"]["logo_safe"]
    )
