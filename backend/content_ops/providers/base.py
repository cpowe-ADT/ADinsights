"""Vendor-neutral caption provider boundary for Content Operations.

Concrete adapters (OpenAI, Anthropic) subclass :class:`BaseHTTPCaptionProvider`
and implement :meth:`_invoke` for their wire protocol. Shared prompt building,
tolerant JSON parsing, candidate normalization, and token-usage capture live
here so the adapters stay thin. The parsed result is handed back to
``content_ops.generation.validate_caption_generation_result`` which enforces the
full content-policy schema, so this layer is deliberately tolerant.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from ..generation import (
    CAPTION_FAILURE_PROVIDER_ERROR,
    CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED,
    CAPTION_FAILURE_SCHEMA_INVALID,
    CaptionGenerationError,
)

CAPTION_SYSTEM_PROMPT = (
    "You are a social media copywriter for a marketing analytics platform. "
    "You receive a JSON brief describing a workspace, its brand profile, the "
    "campaign brief, the requested platforms, and a candidate count. Write that "
    "many caption candidates that match the brand voice and stay on brief. "
    "Honour every required term and never use a blocked term. If an 'agent' "
    "block is present, write the captions in agent.language (locale "
    "agent.locale), follow agent.brand_voice, also honour agent.required_terms "
    "and agent.blocked_terms, and you may draw on the visual ideas described in "
    "agent.approved_references (by their alt_text) — otherwise, if "
    "brand_profile.language or brand_profile.locale is present, write in that "
    "language. Return ONLY minified JSON (no markdown, no "
    "prose) shaped exactly as: "
    '{"candidates":[{"platform":"<one of the requested platforms>",'
    '"caption":"<text>","hashtags":["#tag"],"cta":"<short call to action>",'
    '"alt_text":"<image alt text>","image_prompt":"<text-to-image prompt for a '
    'matching visual>","risk_flags":[],"quality_score":0.0}],"warnings":[]}. '
    "quality_score is your own 0.0-1.0 confidence. image_prompt is a concise "
    "prompt a designer could feed to an image generator for an on-brand visual "
    "(it is reviewed by a human before any image is rendered). Produce one "
    "candidate per requested platform, cycling through the platforms until the "
    "candidate count is met."
)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ProviderUsage:
    """Usage reported by a provider call, used for metering and billing.

    Text providers report tokens; image/video providers report ``images``.
    """

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0

    @property
    def total_tokens(self) -> int:
        return max(self.input_tokens, 0) + max(self.output_tokens, 0)


def build_caption_messages(payload: dict[str, Any]) -> tuple[str, str]:
    """Build the (system, user) prompt pair from a redacted provider payload."""

    workspace = payload.get("workspace") if isinstance(payload, dict) else {}
    brief = payload.get("brief") if isinstance(payload, dict) else {}
    workspace = workspace if isinstance(workspace, dict) else {}
    brief = brief if isinstance(brief, dict) else {}
    user_payload = {
        "platforms": payload.get("platforms", []),
        "candidate_count": payload.get("candidate_count", 1),
        "workspace": {
            "name": workspace.get("name", ""),
            "objective": workspace.get("objective", ""),
            "brand_profile": workspace.get("brand_profile", {}),
        },
        "brief": brief,
        "tone_override": payload.get("tone_override", ""),
    }
    agent = payload.get("agent") if isinstance(payload, dict) else None
    if isinstance(agent, dict):
        user_payload["agent"] = agent
    user_prompt = json.dumps(user_payload, ensure_ascii=False, default=str)
    return CAPTION_SYSTEM_PROMPT, user_prompt


def _coerce_quality(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    if score > 1.0:
        # Tolerate 0-100 style scores from some models.
        score = score / 100.0 if score <= 100.0 else 1.0
    if score < 0.0:
        return 0.0
    return min(score, 1.0)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from raw model text, tolerating fences and prose."""

    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    for candidate in (cleaned, _first_json_blob(cleaned)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"candidates": parsed, "warnings": []}
    raise CaptionGenerationError(
        code=CAPTION_FAILURE_SCHEMA_INVALID,
        detail_safe="Caption provider returned a non-JSON response.",
    )


def _first_json_blob(text: str) -> str | None:
    match = _JSON_OBJECT_RE.search(text or "")
    return match.group(0) if match else None


def normalize_caption_payload(
    raw_text: str,
    *,
    requested_platforms: list[str],
) -> dict[str, Any]:
    """Coerce raw model JSON into the candidate shape the validator expects."""

    data = extract_json_object(raw_text)
    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise CaptionGenerationError(
            code=CAPTION_FAILURE_SCHEMA_INVALID,
            detail_safe="Caption provider returned no candidates.",
        )
    platforms = requested_platforms or ["facebook_page"]
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_candidates):
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "").strip()
        if platform not in platforms:
            platform = platforms[index % len(platforms)]
        normalized.append(
            {
                "platform": platform,
                "caption": str(item.get("caption") or "").strip(),
                "hashtags": _string_list(item.get("hashtags")),
                "cta": str(item.get("cta") or "").strip(),
                "alt_text": str(item.get("alt_text") or "").strip(),
                "image_prompt": str(item.get("image_prompt") or "").strip(),
                "risk_flags": _string_list(item.get("risk_flags")),
                "quality_score": _coerce_quality(item.get("quality_score")),
            }
        )
    if not normalized:
        raise CaptionGenerationError(
            code=CAPTION_FAILURE_SCHEMA_INVALID,
            detail_safe="Caption provider returned no usable candidates.",
        )
    return {"candidates": normalized, "warnings": _string_list(data.get("warnings"))}


class BaseHTTPCaptionProvider:
    """Shared HTTP caption provider; subclasses implement :meth:`_invoke`."""

    provider_name = "base"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        base_url: str | None,
        timeout: float,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = float(timeout)
        self.last_usage: ProviderUsage | None = None

    def is_enabled(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled():
            raise CaptionGenerationError(
                code=CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED,
                detail_safe="Caption generation provider is not configured.",
            )
        system_prompt, user_prompt = build_caption_messages(payload)
        try:
            raw_text, usage = self._invoke(system=system_prompt, user=user_prompt)
        except CaptionGenerationError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise CaptionGenerationError(
                code=CAPTION_FAILURE_PROVIDER_ERROR,
                detail_safe="Caption provider request failed.",
            ) from exc
        self.last_usage = usage
        requested_platforms = list(payload.get("platforms") or ["facebook_page"])
        return normalize_caption_payload(
            raw_text,
            requested_platforms=requested_platforms,
        )

    def _invoke(self, *, system: str, user: str) -> tuple[str, ProviderUsage]:
        raise NotImplementedError


__all__ = [
    "CAPTION_SYSTEM_PROMPT",
    "BaseHTTPCaptionProvider",
    "ProviderUsage",
    "build_caption_messages",
    "extract_json_object",
    "normalize_caption_payload",
]
