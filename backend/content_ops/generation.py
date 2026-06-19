"""AI generation services for Content Operations.

The default caption provider is intentionally disabled. This module only
creates editable draft material when a caller injects a fake or future approved
provider boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentWorkspace,
    GenerationJob,
)

CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED = "provider_not_configured"
CAPTION_FAILURE_SCHEMA_INVALID = "caption_schema_invalid"
CAPTION_FAILURE_POLICY_BLOCKED = "caption_policy_blocked"
CAPTION_FAILURE_REQUIRED_TERMS_MISSING = "required_terms_missing"
CAPTION_FAILURE_JOB_CANCELLED = "generation_job_cancelled"
CAPTION_FAILURE_JOB_WRONG_TYPE = "generation_job_wrong_type"
CAPTION_FAILURE_BRIEF_MISSING = "brief_missing"
CAPTION_FAILURE_JOB_MISSING = "generation_job_missing"
CAPTION_FAILURE_ACTIVE_LIMIT_EXCEEDED = "caption_active_limit_exceeded"
CAPTION_FAILURE_DAILY_LIMIT_EXCEEDED = "caption_daily_limit_exceeded"
CAPTION_FAILURE_CANDIDATE_LIMIT_EXCEEDED = "caption_candidate_limit_exceeded"

CAPTION_PROCESS_STATUS_FAILED = "failed"
CAPTION_PROCESS_STATUS_NOOP = "noop"
CAPTION_PROCESS_STATUS_SUCCEEDED = "succeeded"

DEFAULT_CAPTION_CANDIDATE_COUNT = 3
MAX_CAPTION_CANDIDATE_COUNT = 5
DEFAULT_CAPTION_ACTIVE_JOB_LIMIT = 25
DEFAULT_CAPTION_DAILY_JOB_LIMIT = 100
DEFAULT_CAPTION_DAILY_CANDIDATE_LIMIT = 300
SUPPORTED_CAPTION_PLATFORMS = {
    ContentWorkspace.CHANNEL_FACEBOOK_PAGE,
    ContentWorkspace.CHANNEL_INSTAGRAM,
}

SAFE_PLATFORM_OVERRIDE_KEYS = {
    "alt_text",
    "cta",
    "hashtags",
    "platform",
    "quality_score",
    "risk_flags",
    "source",
}
FORBIDDEN_SECRET_FRAGMENTS = {
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "client_secret",
    "meta-access-token",
    "page-token",
    "raw_response",
    "refresh_token",
    "secret",
    "sk-",
}

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"access[_-]?token|refresh[_-]?token|api[_-]?key|client[_-]?secret|"
    r"page[_-]?token|meta[_-]?access[_-]?token|authorization|secret"
    r")\s*[:=]\s*([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{40,}\b")


@dataclass(frozen=True)
class CaptionCandidate:
    platform: str
    caption: str
    hashtags: tuple[str, ...] = ()
    cta: str = ""
    alt_text: str = ""
    risk_flags: tuple[str, ...] = ()
    quality_score: float = 0.0


@dataclass(frozen=True)
class CaptionGenerationResult:
    candidates: tuple[CaptionCandidate, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaptionGenerationProcessResult:
    status: str
    job_id: str = ""
    draft_ids: tuple[str, ...] = ()
    failure_code: str = ""
    failure_detail_safe: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "job_id": self.job_id,
            "draft_ids": list(self.draft_ids),
            "failure_code": self.failure_code,
            "failure_detail_safe": self.failure_detail_safe,
        }


class CaptionGenerationError(RuntimeError):
    """Client-safe generation error."""

    def __init__(self, *, code: str, detail_safe: str) -> None:
        super().__init__(code)
        self.code = code
        self.detail_safe = detail_safe


class CaptionGenerationQuotaError(CaptionGenerationError):
    """Client-safe quota error for caption generation requests."""

    def __init__(
        self,
        *,
        code: str,
        detail_safe: str,
        quota_snapshot: dict[str, Any],
    ) -> None:
        super().__init__(code=code, detail_safe=detail_safe)
        self.quota_snapshot = quota_snapshot


class DisabledCaptionGenerationProvider:
    """Default provider boundary that prevents accidental live AI calls."""

    def generate(self, payload: dict[str, Any]) -> CaptionGenerationResult:  # noqa: ARG002
        raise CaptionGenerationError(
            code=CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED,
            detail_safe="Caption generation provider is not configured.",
        )


def normalize_caption_candidate_count(value: Any = None) -> int:
    """Normalize requested candidate count to the bounded product cap."""

    if value in (None, ""):
        return DEFAULT_CAPTION_CANDIDATE_COUNT
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_count must be an integer.") from exc
    if count < 1:
        raise ValueError("candidate_count must be at least 1.")
    if count > MAX_CAPTION_CANDIDATE_COUNT:
        raise ValueError(
            f"candidate_count cannot exceed {MAX_CAPTION_CANDIDATE_COUNT}."
        )
    return count


def normalize_caption_platforms(
    *,
    workspace: ContentWorkspace,
    platforms: Any = None,
) -> list[str]:
    """Normalize requested caption platforms with workspace defaults."""

    if platforms in (None, ""):
        raw_platforms = workspace.target_channels or [
            ContentWorkspace.CHANNEL_FACEBOOK_PAGE
        ]
    else:
        raw_platforms = platforms
    if not isinstance(raw_platforms, list):
        raise ValueError("platforms must be a list.")

    normalized: list[str] = []
    for raw_platform in raw_platforms:
        platform = str(raw_platform).strip()
        if not platform:
            continue
        if platform not in SUPPORTED_CAPTION_PLATFORMS:
            raise ValueError(f"Unsupported caption platform: {platform}.")
        if platform not in normalized:
            normalized.append(platform)
    return normalized or [ContentWorkspace.CHANNEL_FACEBOOK_PAGE]


def create_caption_generation_job(
    *,
    tenant,
    brief: ContentBrief,
    user=None,
    candidate_count: Any = None,
    platforms: Any = None,
    tone_override: str = "",
) -> GenerationJob:
    """Create a queued caption generation job with only redacted prompt context."""

    if brief.tenant_id != tenant.id:
        raise ValueError("brief_missing")
    normalized_count = normalize_caption_candidate_count(candidate_count)
    quota_snapshot = enforce_caption_generation_quota(
        tenant=tenant,
        requested_candidate_count=normalized_count,
    )
    normalized_platforms = normalize_caption_platforms(
        workspace=brief.workspace,
        platforms=platforms,
    )
    provider_payload = build_caption_provider_payload(
        brief=brief,
        candidate_count=normalized_count,
        platforms=normalized_platforms,
        tone_override=tone_override,
    )
    prompt_summary = redacted_caption_prompt_summary(provider_payload)
    required_terms, blocked_terms = _content_policy_terms(brief)
    policy_result = {
        "candidate_count": normalized_count,
        "platforms": normalized_platforms,
        "provider_configured": False,
        "redacted": provider_payload["redaction"]["changed"],
        "required_term_count": len(required_terms),
        "blocked_term_count": len(blocked_terms),
        "tone_override": redact_secret_like_text(tone_override)[:128],
        "tone_override_present": bool(str(tone_override or "").strip()),
        "quota_snapshot": quota_snapshot,
    }
    return GenerationJob.all_objects.create(
        tenant=tenant,
        workspace=brief.workspace,
        brief=brief,
        job_type=GenerationJob.TYPE_CAPTION,
        provider="disabled",
        model_name="",
        status=GenerationJob.STATUS_QUEUED,
        input_fingerprint=_fingerprint(provider_payload),
        redacted_prompt_summary=prompt_summary,
        prompt_policy_result=policy_result,
        result_summary={},
        created_by=user,
    )


def build_caption_provider_payload(
    *,
    brief: ContentBrief,
    candidate_count: int,
    platforms: list[str],
    tone_override: str = "",
) -> dict[str, Any]:
    """Build sanitized provider input for fake/future caption providers."""

    raw_payload = {
        "job_type": GenerationJob.TYPE_CAPTION,
        "tenant_id": str(brief.tenant_id),
        "workspace_id": str(brief.workspace_id),
        "brief_id": str(brief.id),
        "candidate_count": candidate_count,
        "platforms": platforms,
        "workspace": {
            "name": brief.workspace.name,
            "objective": brief.workspace.objective,
            "brand_profile": brief.workspace.brand_profile,
        },
        "brief": {
            "campaign_theme": brief.campaign_theme,
            "audience": brief.audience,
            "offer": brief.offer,
            "tone": brief.tone,
            "required_terms": brief.required_terms,
            "blocked_terms": brief.blocked_terms,
            "landing_url": brief.landing_url,
        },
        "tone_override": tone_override,
    }
    redacted = _redact_json_value(raw_payload)
    return {
        **redacted,
        "redaction": {
            "changed": redacted != raw_payload,
            "policy": "content_ops_caption_v1",
        },
    }


def enforce_caption_generation_quota(
    *,
    tenant,
    requested_candidate_count: int,
    now=None,
) -> dict[str, Any]:
    """Fail closed when caption generation would exceed tenant-safe limits."""

    snapshot = caption_generation_quota_snapshot(
        tenant=tenant,
        now=now,
    )
    limits = snapshot["limits"]
    if snapshot["active_job_count"] >= limits["active_job_limit"]:
        raise CaptionGenerationQuotaError(
            code=CAPTION_FAILURE_ACTIVE_LIMIT_EXCEEDED,
            detail_safe="Caption generation active job limit has been reached.",
            quota_snapshot=snapshot,
        )
    if snapshot["rolling_24h_job_count"] >= limits["daily_job_limit"]:
        raise CaptionGenerationQuotaError(
            code=CAPTION_FAILURE_DAILY_LIMIT_EXCEEDED,
            detail_safe="Caption generation daily job limit has been reached.",
            quota_snapshot=snapshot,
        )
    if (
        snapshot["rolling_24h_candidate_count"] + requested_candidate_count
        > limits["daily_candidate_limit"]
    ):
        raise CaptionGenerationQuotaError(
            code=CAPTION_FAILURE_CANDIDATE_LIMIT_EXCEEDED,
            detail_safe="Caption generation daily candidate limit has been reached.",
            quota_snapshot=snapshot,
        )
    return snapshot


def caption_generation_quota_snapshot(
    *,
    tenant,
    now=None,
) -> dict[str, Any]:
    """Return safe tenant-level quota counters for caption generation."""

    now = now or timezone.now()
    since = now - timedelta(hours=24)
    active_statuses = {
        GenerationJob.STATUS_QUEUED,
        GenerationJob.STATUS_RUNNING,
    }
    base_queryset = GenerationJob.all_objects.filter(
        tenant=tenant,
        job_type=GenerationJob.TYPE_CAPTION,
    )
    recent_jobs = list(
        base_queryset.filter(created_at__gte=since).only(
            "id",
            "prompt_policy_result",
        )
    )
    return {
        "active_job_count": base_queryset.filter(status__in=active_statuses).count(),
        "rolling_24h_job_count": len(recent_jobs),
        "rolling_24h_candidate_count": sum(
            _job_candidate_count(job) for job in recent_jobs
        ),
        "limits": _caption_generation_limits(),
    }


def redacted_caption_prompt_summary(payload: dict[str, Any]) -> str:
    """Return a compact prompt summary safe for API responses and persistence."""

    workspace = payload.get("workspace") if isinstance(payload, dict) else {}
    brief = payload.get("brief") if isinstance(payload, dict) else {}
    workspace = workspace if isinstance(workspace, dict) else {}
    brief = brief if isinstance(brief, dict) else {}
    summary = (
        f"Caption generation for workspace={workspace.get('name', '')}; "
        f"theme={brief.get('campaign_theme', '')}; "
        f"audience={brief.get('audience', '')}; "
        f"offer={brief.get('offer', '')}; "
        f"tone={brief.get('tone', '')}; "
        f"platforms={','.join(payload.get('platforms', []))}; "
        f"candidate_count={payload.get('candidate_count')}; "
        f"tone_override_present={bool(str(payload.get('tone_override', '')).strip())}"
    )
    return redact_secret_like_text(summary)[:1000]


def redact_secret_like_text(value: str) -> str:
    """Redact token-like fragments before storage or provider handoff."""

    text = str(value or "")
    text = _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _OPENAI_KEY_RE.sub("[REDACTED]", text)
    text = _LONG_TOKEN_RE.sub("[REDACTED]", text)
    return text


def process_content_caption_generation_job(
    job_id: str | UUID,
    provider=None,
) -> CaptionGenerationProcessResult:
    """Run one caption generation job through an injected provider boundary."""

    existing_job = _get_job(job_id=job_id)
    if existing_job is None:
        return CaptionGenerationProcessResult(
            status=CAPTION_PROCESS_STATUS_NOOP,
            failure_code=CAPTION_FAILURE_JOB_MISSING,
            failure_detail_safe="Generation job does not exist.",
        )
    if existing_job.status == GenerationJob.STATUS_CANCELLED:
        return CaptionGenerationProcessResult(
            status=CAPTION_PROCESS_STATUS_NOOP,
            job_id=str(existing_job.id),
            failure_code=CAPTION_FAILURE_JOB_CANCELLED,
            failure_detail_safe="Generation job was cancelled.",
        )
    if existing_job.status == GenerationJob.STATUS_SUCCEEDED:
        draft_ids = tuple(
            str(draft_id)
            for draft_id in ContentDraft.all_objects.filter(
                tenant=existing_job.tenant,
                versions__source_generation_job=existing_job,
            )
            .distinct()
            .values_list("id", flat=True)
        )
        return CaptionGenerationProcessResult(
            status=CAPTION_PROCESS_STATUS_NOOP,
            job_id=str(existing_job.id),
            draft_ids=draft_ids,
        )
    if existing_job.job_type != GenerationJob.TYPE_CAPTION:
        return _mark_job_failed(
            job_id=existing_job.id,
            code=CAPTION_FAILURE_JOB_WRONG_TYPE,
            detail="Generation job is not a caption job.",
        )
    if existing_job.brief_id is None:
        return _mark_job_failed(
            job_id=existing_job.id,
            code=CAPTION_FAILURE_BRIEF_MISSING,
            detail="Generation job is missing a content brief.",
        )

    with transaction.atomic():
        job = _locked_job(job_id=job_id)
        if job is None:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                failure_code=CAPTION_FAILURE_JOB_MISSING,
                failure_detail_safe="Generation job does not exist.",
            )
        if job.status == GenerationJob.STATUS_CANCELLED:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                job_id=str(job.id),
                failure_code=CAPTION_FAILURE_JOB_CANCELLED,
                failure_detail_safe="Generation job was cancelled.",
            )
        if job.status == GenerationJob.STATUS_SUCCEEDED:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                job_id=str(job.id),
            )
        job.status = GenerationJob.STATUS_RUNNING
        job.error_code = ""
        job.save(update_fields=["status", "error_code", "updated_at"])
        provider_payload = _payload_from_job(job)

    selected_provider = provider or DisabledCaptionGenerationProvider()
    try:
        provider_result = selected_provider.generate(provider_payload)
        parsed_result = validate_caption_generation_result(
            provider_result,
            requested_platforms=set(provider_payload["platforms"]),
        )
    except CaptionGenerationError as exc:
        return _mark_job_failed(
            job_id=existing_job.id,
            code=exc.code,
            detail=exc.detail_safe,
        )

    return _create_generated_drafts_from_candidates(
        job_id=existing_job.id,
        parsed_result=parsed_result,
        requested_candidate_count=int(provider_payload["candidate_count"]),
    )


def validate_caption_generation_result(
    value: Any,
    *,
    requested_platforms: set[str],
) -> CaptionGenerationResult:
    """Validate and coerce a provider caption response."""

    if isinstance(value, CaptionGenerationResult):
        candidates = value.candidates
        warnings = value.warnings
    elif isinstance(value, dict):
        candidates = value.get("candidates")
        warnings = value.get("warnings", [])
    elif isinstance(value, list):
        candidates = value
        warnings = []
    else:
        raise _schema_error("Provider returned an unsupported response shape.")
    if not isinstance(candidates, (list, tuple)):
        raise _schema_error("Caption response must include a candidate list.")
    if not candidates:
        raise _schema_error("Caption response did not include candidates.")
    parsed_candidates = tuple(
        _validate_caption_candidate(
            candidate,
            requested_platforms=requested_platforms,
        )
        for candidate in candidates
    )
    parsed_warnings = tuple(_string_list(warnings, field_name="warnings", max_items=10))
    return CaptionGenerationResult(
        candidates=parsed_candidates,
        warnings=parsed_warnings,
    )


def _create_generated_drafts_from_candidates(
    *,
    job_id: str | UUID,
    parsed_result: CaptionGenerationResult,
    requested_candidate_count: int,
) -> CaptionGenerationProcessResult:
    with transaction.atomic():
        job = _locked_job(job_id=job_id)
        if job is None:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                failure_code=CAPTION_FAILURE_JOB_MISSING,
                failure_detail_safe="Generation job does not exist.",
            )
        if job.status == GenerationJob.STATUS_CANCELLED:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                job_id=str(job.id),
                failure_code=CAPTION_FAILURE_JOB_CANCELLED,
                failure_detail_safe="Generation job was cancelled.",
            )
        if job.job_type != GenerationJob.TYPE_CAPTION:
            return _mark_locked_job_failed(
                job=job,
                code=CAPTION_FAILURE_JOB_WRONG_TYPE,
                detail="Generation job is not a caption job.",
            )
        if job.brief is None:
            return _mark_locked_job_failed(
                job=job,
                code=CAPTION_FAILURE_BRIEF_MISSING,
                detail="Generation job is missing a content brief.",
            )

        required_terms, blocked_terms = _content_policy_terms(job.brief)
        accepted: list[CaptionCandidate] = []
        rejected_codes: list[str] = []
        for candidate in parsed_result.candidates:
            policy_code = _candidate_policy_failure(
                candidate,
                required_terms=required_terms,
                blocked_terms=blocked_terms,
            )
            if policy_code:
                rejected_codes.append(policy_code)
                continue
            accepted.append(candidate)
            if len(accepted) >= requested_candidate_count:
                break

        if not accepted:
            failure_code = (
                CAPTION_FAILURE_REQUIRED_TERMS_MISSING
                if required_terms
                and rejected_codes
                and all(
                    code == CAPTION_FAILURE_REQUIRED_TERMS_MISSING
                    for code in rejected_codes
                )
                else CAPTION_FAILURE_POLICY_BLOCKED
            )
            detail = (
                "Caption candidates did not include required terms."
                if failure_code == CAPTION_FAILURE_REQUIRED_TERMS_MISSING
                else "Caption candidates were blocked by content policy."
            )
            return _mark_locked_job_failed(
                job=job,
                code=failure_code,
                detail=detail,
                extra_summary={
                    "candidate_count": len(parsed_result.candidates),
                    "rejected_candidate_count": len(rejected_codes),
                    "warnings": list(parsed_result.warnings[:10]),
                },
            )

        draft_ids: list[str] = []
        for index, candidate in enumerate(accepted, start=1):
            draft = ContentDraft.all_objects.create(
                tenant=job.tenant,
                workspace=job.workspace,
                brief=job.brief,
                title=_draft_title(job.brief, candidate, index=index),
                state=ContentDraft.STATE_GENERATED,
                created_by=job.created_by,
                owner=job.created_by,
            )
            version = ContentDraftVersion.all_objects.create(
                tenant=job.tenant,
                draft=draft,
                version_number=1,
                caption=candidate.caption,
                platform_overrides=_safe_platform_overrides(candidate),
                created_by=job.created_by,
                change_note="Generated by Content Ops caption generation.",
                source_generation_job=job,
            )
            draft.active_version = version
            draft.save(update_fields=["active_version", "updated_at"])
            draft_ids.append(str(draft.id))

        job.status = GenerationJob.STATUS_SUCCEEDED
        job.error_code = ""
        job.result_summary = {
            "created_draft_count": len(draft_ids),
            "candidate_count": len(parsed_result.candidates),
            "rejected_candidate_count": len(rejected_codes),
            "platforms": sorted({candidate.platform for candidate in accepted}),
            "warnings": list(parsed_result.warnings[:10]),
        }
        job.save(update_fields=["status", "error_code", "result_summary", "updated_at"])
        return CaptionGenerationProcessResult(
            status=CAPTION_PROCESS_STATUS_SUCCEEDED,
            job_id=str(job.id),
            draft_ids=tuple(draft_ids),
        )


def _payload_from_job(job: GenerationJob) -> dict[str, Any]:
    prompt_policy = job.prompt_policy_result or {}
    platforms = normalize_caption_platforms(
        workspace=job.workspace,
        platforms=prompt_policy.get("platforms"),
    )
    candidate_count = normalize_caption_candidate_count(
        prompt_policy.get("candidate_count")
    )
    return build_caption_provider_payload(
        brief=job.brief,
        candidate_count=candidate_count,
        platforms=platforms,
        tone_override=str(prompt_policy.get("tone_override") or ""),
    )


def _validate_caption_candidate(
    value: Any,
    *,
    requested_platforms: set[str],
) -> CaptionCandidate:
    if not isinstance(value, dict):
        raise _schema_error("Caption candidate must be an object.")
    required_keys = {
        "alt_text",
        "caption",
        "cta",
        "hashtags",
        "platform",
        "quality_score",
        "risk_flags",
    }
    missing = sorted(required_keys - set(value))
    if missing:
        raise _schema_error(f"Caption candidate missing fields: {', '.join(missing)}.")
    platform = str(value.get("platform") or "").strip()
    if platform not in SUPPORTED_CAPTION_PLATFORMS or platform not in requested_platforms:
        raise _schema_error("Caption candidate has an unsupported platform.")
    caption = str(value.get("caption") or "").strip()
    if not caption:
        raise _schema_error("Caption candidate must include caption text.")
    try:
        quality_score = float(value.get("quality_score"))
    except (TypeError, ValueError) as exc:
        raise _schema_error("Caption candidate quality_score must be numeric.") from exc
    if quality_score < 0.0 or quality_score > 1.0:
        raise _schema_error("Caption candidate quality_score must be 0.0 to 1.0.")
    candidate = CaptionCandidate(
        platform=platform,
        caption=caption[:2200],
        hashtags=tuple(
            _string_list(value.get("hashtags"), field_name="hashtags", max_items=30)
        ),
        cta=str(value.get("cta") or "").strip()[:180],
        alt_text=str(value.get("alt_text") or "").strip()[:420],
        risk_flags=tuple(
            _string_list(value.get("risk_flags"), field_name="risk_flags", max_items=20)
        ),
        quality_score=quality_score,
    )
    if _candidate_contains_secret_like_text(candidate):
        raise CaptionGenerationError(
            code=CAPTION_FAILURE_POLICY_BLOCKED,
            detail_safe="Caption candidate contained secret-like text.",
        )
    return candidate


def _string_list(value: Any, *, field_name: str, max_items: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise _schema_error(f"Caption candidate {field_name} must be a list.")
    strings: list[str] = []
    for item in value[:max_items]:
        if not isinstance(item, str):
            raise _schema_error(f"Caption candidate {field_name} must contain strings.")
        cleaned = item.strip()
        if cleaned:
            strings.append(cleaned[:120])
    return strings


def _candidate_policy_failure(
    candidate: CaptionCandidate,
    *,
    required_terms: list[str],
    blocked_terms: list[str],
) -> str:
    searchable = _candidate_search_text(candidate)
    lowered = searchable.lower()
    for term in blocked_terms:
        if term.lower() in lowered:
            return CAPTION_FAILURE_POLICY_BLOCKED
    for term in required_terms:
        if term.lower() not in lowered:
            return CAPTION_FAILURE_REQUIRED_TERMS_MISSING
    return ""


def _candidate_search_text(candidate: CaptionCandidate) -> str:
    return " ".join(
        [
            candidate.caption,
            candidate.cta,
            candidate.alt_text,
            " ".join(candidate.hashtags),
            " ".join(candidate.risk_flags),
        ]
    )


def _candidate_contains_secret_like_text(candidate: CaptionCandidate) -> bool:
    rendered = _candidate_search_text(candidate)
    if redact_secret_like_text(rendered) != rendered:
        return True
    lowered = rendered.lower()
    return any(fragment in lowered for fragment in FORBIDDEN_SECRET_FRAGMENTS)


def _content_policy_terms(brief: ContentBrief) -> tuple[list[str], list[str]]:
    brand_profile = brief.workspace.brand_profile or {}
    required_terms = _safe_term_list(brief.required_terms)
    blocked_terms = _safe_term_list(brief.blocked_terms)
    if isinstance(brand_profile, dict):
        required_terms.extend(_safe_term_list(brand_profile.get("required_terms")))
        blocked_terms.extend(_safe_term_list(brand_profile.get("blocked_terms")))
    return _dedupe_terms(required_terms), _dedupe_terms(blocked_terms)


def _safe_term_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe_terms(value: list[str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in value:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def _safe_platform_overrides(candidate: CaptionCandidate) -> dict[str, Any]:
    overrides = {
        "alt_text": candidate.alt_text,
        "cta": candidate.cta,
        "hashtags": list(candidate.hashtags),
        "platform": candidate.platform,
        "quality_score": candidate.quality_score,
        "risk_flags": list(candidate.risk_flags),
        "source": "caption_generation",
    }
    return {key: overrides[key] for key in SAFE_PLATFORM_OVERRIDE_KEYS}


def _draft_title(brief: ContentBrief, candidate: CaptionCandidate, *, index: int) -> str:
    theme = str(brief.campaign_theme or "Generated caption").strip()
    platform_label = (
        "Facebook Page"
        if candidate.platform == ContentWorkspace.CHANNEL_FACEBOOK_PAGE
        else "Instagram"
    )
    return f"{theme[:160]} - {platform_label} option {index}"


def _mark_job_failed(
    *,
    job_id: str | UUID,
    code: str,
    detail: str,
    extra_summary: dict[str, Any] | None = None,
) -> CaptionGenerationProcessResult:
    with transaction.atomic():
        job = _locked_job(job_id=job_id)
        if job is None:
            return CaptionGenerationProcessResult(
                status=CAPTION_PROCESS_STATUS_NOOP,
                failure_code=CAPTION_FAILURE_JOB_MISSING,
                failure_detail_safe="Generation job does not exist.",
            )
        return _mark_locked_job_failed(
            job=job,
            code=code,
            detail=detail,
            extra_summary=extra_summary,
        )


def _mark_locked_job_failed(
    *,
    job: GenerationJob,
    code: str,
    detail: str,
    extra_summary: dict[str, Any] | None = None,
) -> CaptionGenerationProcessResult:
    safe_detail = _sanitize_generation_detail(detail)
    summary = {
        "failure_code": code,
        "failure_detail_safe": safe_detail,
    }
    if extra_summary:
        summary.update(_redact_json_value(extra_summary))
    job.status = GenerationJob.STATUS_FAILED
    job.error_code = code
    job.result_summary = summary
    job.save(update_fields=["status", "error_code", "result_summary", "updated_at"])
    return CaptionGenerationProcessResult(
        status=CAPTION_PROCESS_STATUS_FAILED,
        job_id=str(job.id),
        failure_code=code,
        failure_detail_safe=safe_detail,
    )


def _sanitize_generation_detail(value: str) -> str:
    detail = str(value or "Caption generation failed.").strip()
    detail = redact_secret_like_text(detail)[:500]
    lowered = detail.lower()
    if any(fragment in lowered for fragment in FORBIDDEN_SECRET_FRAGMENTS):
        return "Caption generation failed."
    return detail or "Caption generation failed."


def _schema_error(detail: str) -> CaptionGenerationError:
    return CaptionGenerationError(
        code=CAPTION_FAILURE_SCHEMA_INVALID,
        detail_safe=detail,
    )


def _get_job(*, job_id: str | UUID) -> GenerationJob | None:
    return (
        GenerationJob.all_objects.select_related("tenant", "workspace", "brief")
        .filter(id=job_id)
        .first()
    )


def _locked_job(*, job_id: str | UUID) -> GenerationJob | None:
    return (
        GenerationJob.all_objects.select_for_update()
        .select_related("tenant", "workspace", "brief")
        .filter(id=job_id)
        .first()
    )


def _fingerprint(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _caption_generation_limits() -> dict[str, int]:
    return {
        "active_job_limit": int(
            getattr(
                settings,
                "CONTENT_OPS_CAPTION_ACTIVE_JOB_LIMIT",
                DEFAULT_CAPTION_ACTIVE_JOB_LIMIT,
            )
        ),
        "daily_job_limit": int(
            getattr(
                settings,
                "CONTENT_OPS_CAPTION_DAILY_JOB_LIMIT",
                DEFAULT_CAPTION_DAILY_JOB_LIMIT,
            )
        ),
        "daily_candidate_limit": int(
            getattr(
                settings,
                "CONTENT_OPS_CAPTION_DAILY_CANDIDATE_LIMIT",
                DEFAULT_CAPTION_DAILY_CANDIDATE_LIMIT,
            )
        ),
    }


def _job_candidate_count(job: GenerationJob) -> int:
    try:
        return max(int((job.prompt_policy_result or {}).get("candidate_count") or 0), 0)
    except (TypeError, ValueError):
        return 0


def _redact_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_like_text(value)
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_json_value(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _redact_json_value(item) for key, item in value.items()}
    return value


__all__ = [
    "CAPTION_FAILURE_BRIEF_MISSING",
    "CAPTION_FAILURE_ACTIVE_LIMIT_EXCEEDED",
    "CAPTION_FAILURE_CANDIDATE_LIMIT_EXCEEDED",
    "CAPTION_FAILURE_DAILY_LIMIT_EXCEEDED",
    "CAPTION_FAILURE_JOB_CANCELLED",
    "CAPTION_FAILURE_JOB_MISSING",
    "CAPTION_FAILURE_JOB_WRONG_TYPE",
    "CAPTION_FAILURE_POLICY_BLOCKED",
    "CAPTION_FAILURE_PROVIDER_NOT_CONFIGURED",
    "CAPTION_FAILURE_REQUIRED_TERMS_MISSING",
    "CAPTION_FAILURE_SCHEMA_INVALID",
    "CAPTION_PROCESS_STATUS_FAILED",
    "CAPTION_PROCESS_STATUS_NOOP",
    "CAPTION_PROCESS_STATUS_SUCCEEDED",
    "DEFAULT_CAPTION_CANDIDATE_COUNT",
    "MAX_CAPTION_CANDIDATE_COUNT",
    "SUPPORTED_CAPTION_PLATFORMS",
    "CaptionCandidate",
    "CaptionGenerationError",
    "CaptionGenerationQuotaError",
    "CaptionGenerationProcessResult",
    "CaptionGenerationResult",
    "DisabledCaptionGenerationProvider",
    "build_caption_provider_payload",
    "caption_generation_quota_snapshot",
    "create_caption_generation_job",
    "enforce_caption_generation_quota",
    "normalize_caption_candidate_count",
    "normalize_caption_platforms",
    "process_content_caption_generation_job",
    "redact_secret_like_text",
    "redacted_caption_prompt_summary",
    "validate_caption_generation_result",
]
