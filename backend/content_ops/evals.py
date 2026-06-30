"""Deterministic eval harnesses for Content Operations generation.

These helpers are local safety checks. They do not call AI providers and they
do not replace human approval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .generation import (
    CAPTION_PROCESS_STATUS_SUCCEEDED,
    create_caption_generation_job,
    process_content_caption_generation_job,
)
from .models import (
    ApprovalRequest,
    ContentBrief,
    ContentDraft,
    ContentSchedule,
    ContentWorkspace,
    MediaAsset,
    OrganicPostMetricSnapshot,
    PublishedPost,
    PublishAttempt,
)

DEFAULT_CAPTION_EVAL_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "content_ops"
    / "caption_eval_cases.json"
)


@dataclass(frozen=True)
class CaptionEvalCaseResult:
    case_id: str
    passed: bool
    expected_status: str
    actual_status: str
    expected_failure_code: str = ""
    actual_failure_code: str = ""
    draft_count: int = 0
    failures: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "expected_failure_code": self.expected_failure_code,
            "actual_failure_code": self.actual_failure_code,
            "draft_count": self.draft_count,
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class CaptionEvalRunResult:
    results: tuple[CaptionEvalCaseResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "case_count": len(self.results),
            "failed_count": sum(1 for result in self.results if not result.passed),
            "results": [result.as_dict() for result in self.results],
        }


def load_caption_eval_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load tenant-safe caption eval fixtures from JSON."""

    fixture_path = Path(path or DEFAULT_CAPTION_EVAL_FIXTURE_PATH)
    with fixture_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("Caption eval fixture must contain a case list.")
    return cases


def run_caption_eval_cases(
    *,
    tenant,
    user=None,
    cases: list[dict[str, Any]] | None = None,
    fixture_path: str | Path | None = None,
) -> CaptionEvalRunResult:
    """Run caption eval cases through the disabled-by-default generation runtime."""

    selected_cases = cases if cases is not None else load_caption_eval_cases(fixture_path)
    results = tuple(
        _run_caption_eval_case(tenant=tenant, user=user, case=case)
        for case in selected_cases
    )
    return CaptionEvalRunResult(results=results)


def _run_caption_eval_case(
    *,
    tenant,
    user,
    case: dict[str, Any],
) -> CaptionEvalCaseResult:
    case_id = str(case.get("id") or "unknown")
    expected = _dict(case.get("expected"))
    expected_status = str(expected.get("status") or "")
    expected_failure_code = str(expected.get("failure_code") or "")
    failures: list[str] = []

    before_side_effect_counts = _side_effect_counts()
    workspace = _create_workspace(tenant=tenant, user=user, case=case)
    brief = _create_brief(tenant=tenant, workspace=workspace, case=case)
    request = _dict(case.get("request"))
    job = create_caption_generation_job(
        tenant=tenant,
        brief=brief,
        user=user,
        candidate_count=request.get("candidate_count"),
        platforms=request.get("platforms"),
        tone_override=str(request.get("tone_override") or ""),
    )
    provider = _FixtureCaptionProvider(response=_dict(case.get("provider_response")))

    process_result = process_content_caption_generation_job(
        job.id,
        provider=provider,
    )
    job.refresh_from_db()

    draft_count = ContentDraft.all_objects.filter(
        tenant=tenant,
        versions__source_generation_job=job,
    ).distinct().count()
    actual_failure_code = process_result.failure_code or job.error_code
    if process_result.status != expected_status:
        failures.append(
            f"expected status {expected_status!r}, got {process_result.status!r}"
        )
    if actual_failure_code != expected_failure_code:
        failures.append(
            f"expected failure_code {expected_failure_code!r}, got {actual_failure_code!r}"
        )
    expected_draft_count = int(expected.get("draft_count") or 0)
    if draft_count != expected_draft_count:
        failures.append(f"expected draft_count {expected_draft_count}, got {draft_count}")

    expected_platforms = expected.get("platforms") or []
    if expected_platforms:
        actual_platforms = sorted(job.result_summary.get("platforms") or [])
        if actual_platforms != sorted(str(platform) for platform in expected_platforms):
            failures.append(
                f"expected platforms {sorted(expected_platforms)!r}, got {actual_platforms!r}"
            )

    for fragment in expected.get("redacted_fragments_absent") or []:
        rendered = _render_for_redaction_check(
            job=job,
            provider_payloads=provider.payloads,
            process_result=process_result.as_dict(),
        ).lower()
        fragment_text = str(fragment).lower()
        if fragment_text and fragment_text in rendered:
            failures.append(f"secret-like fragment {fragment!r} was not redacted")

    side_effect_deltas = _side_effect_deltas(before_side_effect_counts)
    forbidden_side_effects = {
        key: delta
        for key, delta in side_effect_deltas.items()
        if key != "drafts" and delta
    }
    if forbidden_side_effects:
        failures.append(f"unexpected side effects: {forbidden_side_effects!r}")

    if (
        expected_status == CAPTION_PROCESS_STATUS_SUCCEEDED
        and side_effect_deltas["drafts"] != expected_draft_count
    ):
        failures.append(
            "generated draft side effect did not match expected draft_count: "
            f"{side_effect_deltas['drafts']}"
        )

    return CaptionEvalCaseResult(
        case_id=case_id,
        passed=not failures,
        expected_status=expected_status,
        actual_status=process_result.status,
        expected_failure_code=expected_failure_code,
        actual_failure_code=actual_failure_code,
        draft_count=draft_count,
        failures=tuple(failures),
    )


def _create_workspace(*, tenant, user, case: dict[str, Any]) -> ContentWorkspace:
    workspace = _dict(case.get("workspace"))
    return ContentWorkspace.all_objects.create(
        tenant=tenant,
        name=str(workspace.get("name") or f"{case.get('id', 'caption')} workspace"),
        objective=str(workspace.get("objective") or ""),
        brand_profile=_dict(workspace.get("brand_profile")),
        target_channels=list(workspace.get("target_channels") or ["facebook_page"]),
        created_by=user,
    )


def _create_brief(
    *,
    tenant,
    workspace: ContentWorkspace,
    case: dict[str, Any],
) -> ContentBrief:
    brief = _dict(case.get("brief"))
    return ContentBrief.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        campaign_theme=str(brief.get("campaign_theme") or "Caption eval"),
        audience=str(brief.get("audience") or ""),
        offer=str(brief.get("offer") or ""),
        tone=str(brief.get("tone") or ""),
        required_terms=list(brief.get("required_terms") or []),
        blocked_terms=list(brief.get("blocked_terms") or []),
        landing_url=str(brief.get("landing_url") or ""),
        status=ContentBrief.STATUS_ACTIVE,
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _render_for_redaction_check(
    *,
    job,
    provider_payloads: list[dict[str, Any]],
    process_result: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "redacted_prompt_summary": job.redacted_prompt_summary,
            "prompt_policy_result": job.prompt_policy_result,
            "result_summary": job.result_summary,
            "provider_payloads": provider_payloads,
            "process_result": process_result,
        },
        sort_keys=True,
        default=str,
    )


def _side_effect_counts() -> dict[str, int]:
    return {
        "approvals": ApprovalRequest.all_objects.count(),
        "assets": MediaAsset.all_objects.count(),
        "drafts": ContentDraft.all_objects.count(),
        "metrics": OrganicPostMetricSnapshot.all_objects.count(),
        "published_posts": PublishedPost.all_objects.count(),
        "publish_attempts": PublishAttempt.all_objects.count(),
        "schedules": ContentSchedule.all_objects.count(),
    }


def _side_effect_deltas(before: dict[str, int]) -> dict[str, int]:
    after = _side_effect_counts()
    return {key: after[key] - before.get(key, 0) for key in after}


class _FixtureCaptionProvider:
    def __init__(self, *, response: dict[str, Any]) -> None:
        self.response = response
        self.payloads: list[dict[str, Any]] = []

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return self.response


__all__ = [
    "CaptionEvalCaseResult",
    "CaptionEvalRunResult",
    "DEFAULT_CAPTION_EVAL_FIXTURE_PATH",
    "load_caption_eval_cases",
    "run_caption_eval_cases",
]
