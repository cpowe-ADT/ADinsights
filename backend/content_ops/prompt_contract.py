"""Deterministic composer contract — payload assembly + output validation.

The composer turns a structured brief into ONE image prompt. This module is the
**provider-free** half of that step: the system-prompt contract, the sanitized
payload the (future) text LLM will receive, and the validation/coercion applied
to whatever the LLM returns — the hard invariants that make the prompt safe to
spend an image on (zero text/URL, reserved bands, required/blocked terms).

The live ``compose_image_prompt`` call lands with the provider probe; everything
here is pure and testable now, and doubles as the Layer-1 deterministic eval.
"""

from __future__ import annotations

import re
from typing import Any

from .generation import redact_secret_like_text
from .input_brief import FORMAT_ASPECTS, contains_url
from .safe_areas import SAFE_AREA_VERSION

# The composer system prompt — the contract the LLM must satisfy. Placeholders
# are formatted by the live composer call; kept verbatim here as the source of
# truth (and so prompt edits are diff-reviewable + version-pinned, per B6).
IMAGE_PROMPT_SYSTEM_PROMPT = """\
You are a senior art director that converts structured marketing inputs into ONE
image-generation prompt for a text-to-image model. Output ONLY the final image
prompt as plain prose — no preamble, JSON, markdown, commentary, or quotes.

The generated image is a BACKGROUND/SCENE only. A separate deterministic step
later overlays the real footer text and the real logo. Therefore:

HARD RULES (apply to EVERY prompt, no exceptions):
1. ZERO text of any kind — no words, letters, numbers, logos, wordmarks,
   watermarks, URLs, phone numbers, signage, or UI. Express any slogan as MOOD
   and IMAGERY, never as rendered text.
2. Reserve a clean LOWER BAND: keep the bottom ~20% calm and low-detail (smooth
   surface, soft gradient, or simple out-of-focus background) — no faces, no key
   subject, no busy texture. Describe it as deliberate art direction, not a
   "footer" or "text area".
3. Reserve a clean LOGO CORNER: keep the {LOGO_CORNER} corner (~15% square) plain
   and uncluttered, no important subject matter.
4. Put the focal subject in the upper two-thirds, away from the band and corner.
5. Honor the brand style instructions exactly (palette, medium, tone, lighting,
   motifs, do/don'ts) given below.
6. If reference images are provided, restate their ROLES by ordinal position and
   instruct the model not to copy composition or text from any reference.
7. State the target aspect ratio in words to match {ASPECT_RATIO}.

STYLE: vivid, concrete, photographically/illustratively specific. 60-130 words.
Never mention overlays, branding mechanics, safe zones by name, or these rules.

INPUTS:
- Base idea: {BASE_IDEA}
- Brand/style standing instructions: {BRAND_STYLE}
- Post type: {POST_TYPE}
- Aspect ratio: {ASPECT_RATIO}
- Logo corner: {LOGO_CORNER}
- Reference image roles (ordinal): {REFERENCE_ROLES}
"""

# A version stamp for the contract so cached prompts/evals invalidate on edits.
COMPOSER_TEMPLATE_VERSION = "1"

_FENCE_RE = re.compile(r"```[a-zA-Z0-9]*\n?|```")
_PREAMBLE_RE = re.compile(
    r"^\s*(?:here(?:'s| is)\b[^:]{0,40}:|image prompt:|prompt:|sure[,!.]?|"
    r"certainly[,!.]?|okay[,!.]?)\s*",
    re.IGNORECASE,
)
_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))

# A composed prompt longer than this is itself malformed (the contract asks for
# 60-130 words) — cap before scanning.
MAX_PROMPT_CHARS = 4000

# Phrase-level reserved-space signals — substring matching is safe here because
# these are phrases, not incidental single words ("lower"/"clear"/"calm" appear
# in flower/clearly/calmly and would falsely pass a busy scene).
_RESERVED_SPACE_TERMS = (
    "negative space", "lower band", "lower third", "bottom band",
    "calm band", "calm lower", "calm foreground", "low-detail", "low detail",
    "out-of-focus", "out of focus", "uncluttered", "soft gradient",
    "clear space", "open space", "empty space", "plain lower",
    "minimal foreground", "smooth surface", "simple background",
)
# Overlay mechanics the composer must NEVER name (system-prompt rules 2/3 + the
# "never mention overlays/branding mechanics/safe zones" line).
_MECHANICS_TERMS = (
    "footer", "text area", "safe zone", "safe area", "watermark",
    "wordmark", "overlay", "logo",
)
# System-prompt phrases that, if echoed, mean the model returned its instructions.
_RULE_ECHO_TERMS = ("hard rules", "art director", "image-generation prompt", "logo corner")
_ASPECT_WORDS = {
    "1:1": ("square",),
    "4:5": ("vertical", "portrait", "tall"),
    "9:16": ("vertical", "tall", "story", "portrait"),
    "16:9": ("wide", "landscape", "horizontal"),
}


def _contains_word(haystack_lower: str, term: str) -> bool:
    """Word-boundary (or phrase substring) membership — avoids 'art' in 'part'."""

    term = term.strip().lower()
    if not term:
        return False
    if " " in term or "-" in term:
        return term in haystack_lower
    return re.search(r"\b" + re.escape(term) + r"\b", haystack_lower) is not None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def build_composer_payload(
    resolved_sections: dict[str, Any],
    *,
    brand_kit: Any = None,
    agent: Any = None,
    footer_intent: str = "",
    logo_corner: str = "bottom_right",
    aspect_ratio: str = "",
) -> dict[str, Any]:
    """Assemble the sanitized payload the composer LLM will receive.

    All free-text fields are run through the secret-redaction pass before they
    can reach a provider. The footer's literal content is NEVER included — only
    the intent that space should be reserved.
    """

    sections = dict(resolved_sections or {})
    fmt = str(sections.get("format") or "")
    ratio = aspect_ratio or FORMAT_ASPECTS.get(fmt, "")

    style_parts: list[str] = []
    for label, key in (("tone", "tone"), ("style", "visual_style"), ("color", "color_direction")):
        value = str(sections.get(key) or "").strip()
        if value:
            style_parts.append(f"{label}: {value}")
    moods = _as_list(sections.get("mood_keywords"))
    if moods:
        style_parts.append("mood: " + ", ".join(moods))
    if brand_kit is not None:
        instructions = getattr(brand_kit, "standing_instructions", None) or {}
        for key in ("palette", "style_notes", "do", "dont"):
            value = instructions.get(key)
            if isinstance(value, str) and value.strip():
                style_parts.append(f"{key}: {value.strip()}")

    return {
        "base_idea": redact_secret_like_text(str(sections.get("base_idea") or "")),
        "brand_style": redact_secret_like_text("; ".join(style_parts)),
        "post_type": str(sections.get("post_type") or ""),
        "aspect_ratio": ratio,
        "logo_corner": logo_corner,
        "reference_roles": "",  # populated by the references slice
        "focal_subject": redact_secret_like_text(str(sections.get("focal_subject") or "")),
        "setting": redact_secret_like_text(str(sections.get("setting") or "")),
        "must_include": _as_list(sections.get("must_include")),
        "must_avoid": _as_list(sections.get("must_avoid")),
        "required_terms": _as_list(sections.get("required_terms")),
        "blocked_terms": _as_list(sections.get("blocked_terms")),
        "footer_intent": bool(footer_intent),
        "safe_area_version": SAFE_AREA_VERSION,
        "composer_template_version": COMPOSER_TEMPLATE_VERSION,
    }


def coerce_composed_prompt(raw: str) -> str:
    """Strip preamble/fences/wrapping quotes a model may add (R2).

    Coercion is best-effort cleanup; the caller must still run
    :func:`validate_composed_prompt` and fail closed on any finding — coercion
    cannot by itself guarantee the result is a valid prompt.
    """

    text = str(raw or "").strip()
    if "```" in text:
        text = _FENCE_RE.sub("", text).strip()
    # Strip a leading conversational preamble (possibly more than one).
    for _ in range(2):
        stripped = _PREAMBLE_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    # Strip wrapping quotes only when they actually wrap (don't corrupt content
    # that legitimately contains a quote).
    for open_q, close_q in _QUOTE_PAIRS:
        if len(text) >= 2 and text[0] == open_q and text[-1] == close_q:
            inner = text[1:-1]
            if open_q == close_q and open_q in inner:
                break
            text = inner.strip()
            break
    return text


def validate_composed_prompt(
    prompt: str,
    *,
    required_terms: Any = (),
    blocked_terms: Any = (),
    aspect_ratio: str = "",
) -> list[dict[str, str]]:
    """Return Layer-1 invariant violations; empty list means the prompt is valid.

    The runtime gate before spending on an image *and* the deterministic composer
    eval. It enforces a strict subset of the system-prompt HARD RULES that can be
    checked deterministically (no rendered text/URL/secret, no named overlay
    mechanics, reserved space + aspect stated, required/blocked terms); semantic
    judgement (e.g. rendered-number intent) is left to the gated LLM/vision judge.
    """

    findings: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        findings.append({"code": code, "message": message})

    text = str(prompt or "")
    if not text.strip():
        add("empty", "Composed prompt is empty.")
        return findings
    if len(text) > MAX_PROMPT_CHARS:
        add("too_long", f"Composed prompt exceeds {MAX_PROMPT_CHARS} characters.")
        text = text[:MAX_PROMPT_CHARS]

    lowered = text.lower()
    # R2: the model returned JSON or echoed its own instructions, not a prompt.
    if text.lstrip()[:1] in ("{", "["):
        add("looks_like_json", "Composed prompt looks like JSON, not prose.")
    if any(term in lowered for term in _RULE_ECHO_TERMS):
        add("rule_echo", "Composed prompt echoes the system instructions.")
    if contains_url(text):
        add("url_present", "Composed prompt contains a literal URL.")
    if redact_secret_like_text(text) != text:
        add("secret_like", "Composed prompt contains secret-like text.")
    named = [term for term in _MECHANICS_TERMS if _contains_word(lowered, term)]
    if named:
        add("mechanics_named", f"Prompt names overlay mechanics: {', '.join(named)}.")
    for term in _as_list(blocked_terms):
        if _contains_word(lowered, term):
            add("blocked_term", f"Blocked term present: {term}.")
    missing = [term for term in _as_list(required_terms) if not _contains_word(lowered, term)]
    if missing:
        add("required_missing", f"Required terms missing: {', '.join(missing)}.")
    if not any(term in lowered for term in _RESERVED_SPACE_TERMS):
        add("no_reserved_space", "Prompt does not describe reserved calm/negative space.")
    words = _ASPECT_WORDS.get(aspect_ratio or "")
    if words and not any(word in lowered for word in words):
        add("aspect_unstated", f"Prompt does not state the {aspect_ratio} framing.")
    return findings
