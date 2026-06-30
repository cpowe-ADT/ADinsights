"""Structured creative-brief vocabulary, templates, and input linting.

The graphic composer turns a ``sections`` object into one image prompt. This
module is the *input side* of that contract: the controlled vocabularies that
keep inputs consistent (enums where a field drives behavior, free text only for
the open creative idea), per-post-type starter templates, and a pure,
provider-free linter that flags weak or contradictory inputs before any spend.

Nothing here calls a provider; it is deterministic and cheap so it can run in
default CI and client-side for instant feedback.
"""

from __future__ import annotations

import copy
import re
from typing import Any


# --- Controlled vocabularies (start tight; expand only on eval evidence) -------

POST_TYPES = (
    "product_feature",
    "promo_offer",
    "event",
    "announcement",
    "testimonial",
    "educational_tip",
    "brand_story",
    "seasonal_holiday",
    "recruitment",
)

# Semantic format names map to an aspect ratio (the canonical currency — adapters
# translate the ratio to a provider-native size; raw WxH is never stored here).
FORMAT_ASPECTS = {
    "square_1x1": "1:1",
    "portrait_4x5": "4:5",
    "story_9x16": "9:16",
    "landscape_16x9": "16:9",
}
FORMATS = tuple(FORMAT_ASPECTS)

TONES = (
    "professional",
    "friendly",
    "premium",
    "playful",
    "urgent",
    "inspirational",
    "community",
    "informative",
)

VISUAL_STYLES = (
    "photographic",
    "lifestyle_photo",
    "studio_product",
    "flat_illustration",
    "bold_graphic",
    "minimal",
    "collage",
    "three_d_render",
)

COLOR_DIRECTIONS = (
    "brand_palette",
    "warm",
    "cool",
    "high_contrast",
    "muted_pastel",
    "monochrome",
)

MOOD_KEYWORDS = (
    "energetic",
    "calm",
    "premium",
    "approachable",
    "trustworthy",
    "vibrant",
    "nostalgic",
    "modern",
    "festive",
    "bold",
)

# Input bounds.
IDEA_MIN_CHARS = 12
IDEA_MAX_CHARS = 240
MOOD_KEYWORDS_MAX = 4


# --- Field spec (machine-readable "how to create great inputs") ----------------

# tier 1 = minimal viable brief (always shown); tier 2 = refine the look;
# tier 3 = brand/compliance (mostly derived from the BrandKit).
SECTIONS_FIELD_SPEC: dict[str, dict[str, Any]] = {
    "base_idea": {"tier": 1, "type": "text", "required": True,
                  "help": "What is this post about? One sentence."},
    "post_type": {"tier": 1, "type": "enum", "required": True, "values": POST_TYPES},
    "format": {"tier": 1, "type": "enum", "required": True, "values": FORMATS},
    "tone": {"tier": 2, "type": "enum", "required": False, "values": TONES},
    "visual_style": {"tier": 2, "type": "enum", "required": False, "values": VISUAL_STYLES},
    "color_direction": {"tier": 2, "type": "enum", "required": False,
                        "values": COLOR_DIRECTIONS},
    "focal_subject": {"tier": 2, "type": "text", "required": False},
    "setting": {"tier": 2, "type": "text", "required": False},
    "mood_keywords": {"tier": 2, "type": "enum_multi", "required": False,
                      "values": MOOD_KEYWORDS, "max": MOOD_KEYWORDS_MAX},
    "must_include": {"tier": 2, "type": "text_list", "required": False},
    "must_avoid": {"tier": 2, "type": "text_list", "required": False},
    "locale": {"tier": 3, "type": "text", "required": False},
}

# Per-post-type starter templates: sensible enum defaults + an example idea.
# These double as golden-input eval fixtures.
POST_TYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "product_feature": {
        "defaults": {"tone": "professional", "visual_style": "studio_product",
                     "color_direction": "brand_palette", "format": "square_1x1"},
        "example_base_idea": "Hero shot of our new insulated water bottle.",
        "what_good_looks_like": "Clear single product, brand colors, clean space for the footer.",
    },
    "promo_offer": {
        "defaults": {"tone": "urgent", "visual_style": "bold_graphic",
                     "color_direction": "high_contrast", "format": "square_1x1"},
        "example_base_idea": "Weekend sale on garden furniture, up to 30% off.",
        "what_good_looks_like": "High-energy scene, bold color, obvious focal subject.",
    },
    "event": {
        "defaults": {"tone": "inspirational", "visual_style": "lifestyle_photo",
                     "color_direction": "warm", "format": "portrait_4x5"},
        "example_base_idea": "Community beach cleanup this Saturday in Kingston.",
        "what_good_looks_like": "People + place, warm light, calm lower band for details.",
    },
    "seasonal_holiday": {
        "defaults": {"tone": "friendly", "visual_style": "lifestyle_photo",
                     "color_direction": "warm", "format": "square_1x1"},
        "example_base_idea": "Independence Day greetings from our team.",
        "what_good_looks_like": "Festive mood via imagery and warm color, no literal text.",
        "mood_keywords": ["festive", "vibrant"],
    },
}


# URL/domain detection is a per-token anchored match over a length-bounded slice
# — linear, so a long adversarial brief can't trigger catastrophic backtracking
# (a whole-string regex with `\b` + greedy dotted runs is quadratic; see tests).
URL_SCAN_LIMIT = 4000
_URL_TOKEN_RE = re.compile(
    r"^(?:https?://|www\.)\S+$"
    r"|^[\w-]+(?:\.[\w-]+){0,8}\.(?:com|net|org|io|co|jm|pe)$",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
_QUOTED_RE = re.compile(r"[\"“”']{1}[^\"“”']{2,}[\"“”']{1}")
_SAYS_RE = re.compile(r"\btext that says\b|\bwords?\s+saying\b|\bcaption reads\b",
                      re.IGNORECASE)


def contains_url(text: Any) -> bool:
    """True if a length-bounded slice of ``text`` contains a URL or known domain."""

    head = str(text or "")[:URL_SCAN_LIMIT]
    for token in head.split():
        clean = token.strip(".,;:!?()[]{}\"'“”")[:256]
        if clean and _URL_TOKEN_RE.match(clean):
            return True
    return False


def _norm_terms(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        items = []
    return [item.strip().lower() for item in items if str(item).strip()]


def lint_sections(
    sections: dict[str, Any], *, brand_kit: Any = None
) -> list[dict[str, str]]:
    """Return structured findings for a creative-brief ``sections`` object.

    Pure and deterministic. ``severity`` is ``block`` (cannot submit), ``warn``
    (allowed, shown inline), or ``info``. Provider/capability-coupled checks
    (e.g. format-not-supported-by-provider, blocked-term-in-required) are added
    in later slices alongside the composer and capability descriptor.
    """

    findings: list[dict[str, str]] = []

    def add(severity: str, field: str, code: str, message: str, fix: str = "") -> None:
        findings.append(
            {
                "severity": severity,
                "field": field,
                "code": code,
                "message": message,
                "suggested_fix": fix,
            }
        )

    sections = sections or {}
    idea = str(sections.get("base_idea") or "").strip()
    if not idea:
        add("block", "base_idea", "idea_empty", "Describe what this post is about.")
    else:
        if len(idea) < IDEA_MIN_CHARS:
            add("warn", "base_idea", "idea_too_short",
                "Add a few words — who/what/where.", "Expand the idea to a full phrase.")
        if len(idea) > IDEA_MAX_CHARS:
            add("warn", "base_idea", "idea_too_long",
                "This is long; the focal subject may get diluted.", "Trim to one idea.")
        idea_head = idea[:URL_SCAN_LIMIT]
        if contains_url(idea_head) or _PHONE_RE.search(idea_head) \
                or _QUOTED_RE.search(idea_head) or _SAYS_RE.search(idea_head):
            add("warn", "base_idea", "literal_text_in_idea",
                "The image renders no text — a URL, phone, or slogan belongs in the footer.",
                "Move literal text to the footer preset.")

    # Enum validity.
    enum_fields = {
        "post_type": POST_TYPES,
        "format": FORMATS,
        "tone": TONES,
        "visual_style": VISUAL_STYLES,
        "color_direction": COLOR_DIRECTIONS,
    }
    for field, allowed in enum_fields.items():
        value = sections.get(field)
        if value in (None, ""):
            continue
        if str(value) not in allowed:
            add("block", field, "enum_invalid",
                f"'{value}' is not a valid {field}.",
                f"Choose one of: {', '.join(allowed)}.")

    # Mood overload.
    moods = _norm_terms(sections.get("mood_keywords"))
    if len(moods) > MOOD_KEYWORDS_MAX:
        add("warn", "mood_keywords", "mood_overload",
            f"Pick the {MOOD_KEYWORDS_MAX} moods that matter most.",
            "Remove the least important mood chips.")

    # Contradiction: a term in must_include is also in must_avoid (or blocked).
    include = set(_norm_terms(sections.get("must_include")))
    avoid = set(_norm_terms(sections.get("must_avoid")))
    blocked = set()
    if brand_kit is not None:
        blocked = set(_norm_terms(getattr(brand_kit, "blocked_terms", None)))
    conflicts = (include & avoid) | (include & blocked)
    if conflicts:
        add("block", "must_include", "contradiction",
            f"These appear in both include and avoid/blocked: {', '.join(sorted(conflicts))}.",
            "Remove the conflicting term from one side.")

    return findings


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen[key.lower()] = key
    return list(seen.values())


def resolve_sections_defaults(
    sections: dict[str, Any], *, brand_kit: Any = None, agent: Any = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Fill unset Tier-2/3 fields from BrandKit -> agent -> system default.

    Returns ``(resolved, provenance)`` where ``provenance`` maps each populated
    field to its origin (``user`` | ``brand_kit`` | ``agent`` | ``default``).
    The resolved object is what gets snapshotted into job lineage so a later
    regenerate reads the snapshot, never a since-edited BrandKit (spec A4/F5).
    Pure and idempotent: ``resolve(resolve(x)) == resolve(x)``.
    """

    # Deep-copy so the resolved snapshot (frozen into lineage) never aliases the
    # caller's nested lists/dicts.
    resolved = copy.deepcopy(sections) if isinstance(sections, dict) else {}
    provenance: dict[str, str] = {}
    instructions = dict(getattr(brand_kit, "standing_instructions", None) or {})
    visual = dict(getattr(brand_kit, "visual_config", None) or {})
    voice = dict(getattr(agent, "brand_voice", None) or {})

    def fill(field: str, candidates: list[tuple[str, Any]], system_default: str | None = None) -> None:
        # These are string-valued enum fields: only a non-empty string counts as
        # a deliberate user value; a stray number/dict/blank is treated as unset.
        current = resolved.get(field)
        if isinstance(current, str) and current.strip():
            provenance[field] = "user"
            return
        for origin, value in candidates:
            if isinstance(value, str) and value.strip():
                resolved[field] = value.strip()
                provenance[field] = origin
                return
        if system_default is not None:
            resolved[field] = system_default
            provenance[field] = "default"

    fill("tone", [("brand_kit", instructions.get("tone")), ("agent", voice.get("tone"))])
    fill(
        "visual_style",
        [("brand_kit", instructions.get("visual_style") or visual.get("visual_style"))],
    )
    fill(
        "color_direction",
        [("brand_kit", instructions.get("color_direction"))],
        system_default="brand_palette",
    )
    agent_locale = getattr(agent, "locale", "") if agent is not None else ""
    fill("locale", [("agent", agent_locale)])

    # Derived required/blocked terms (Tier 3): union of user-provided + BrandKit.
    kit_required = _as_list(getattr(brand_kit, "required_terms", None))
    kit_blocked = _as_list(getattr(brand_kit, "blocked_terms", None))
    if kit_required:
        resolved["required_terms"] = _dedupe([*_as_list(resolved.get("required_terms")), *kit_required])
        provenance.setdefault("required_terms", "brand_kit")
    if kit_blocked:
        resolved["blocked_terms"] = _dedupe([*_as_list(resolved.get("blocked_terms")), *kit_blocked])
        provenance.setdefault("blocked_terms", "brand_kit")

    return resolved, provenance


def brief_strength(sections: dict[str, Any]) -> str:
    """A deterministic weak | ok | strong indicator of input completeness."""

    sections = sections or {}
    idea = str(sections.get("base_idea") or "").strip()
    has_idea = IDEA_MIN_CHARS <= len(idea) <= IDEA_MAX_CHARS
    has_required = bool(sections.get("post_type")) and bool(sections.get("format"))
    detail_signals = sum(
        1
        for key in ("focal_subject", "setting")
        if str(sections.get(key) or "").strip()
    )
    if _norm_terms(sections.get("mood_keywords")):
        detail_signals += 1
    blocking = [f for f in lint_sections(sections) if f["severity"] == "block"]
    if blocking or not has_idea or not has_required:
        return "weak"
    if detail_signals >= 2:
        return "strong"
    return "ok"
