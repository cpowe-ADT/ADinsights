from __future__ import annotations

import pytest

from content_ops.evals import load_caption_eval_cases, run_caption_eval_cases
from content_ops.generation import (
    CAPTION_FAILURE_POLICY_BLOCKED,
    CAPTION_PROCESS_STATUS_SUCCEEDED,
)
from content_ops.models import (
    ApprovalRequest,
    ContentDraft,
    ContentSchedule,
    OrganicPostMetricSnapshot,
    PublishedPost,
    PublishAttempt,
)


@pytest.mark.django_db
def test_caption_eval_fixture_set_covers_required_cases(tenant, user):
    cases = load_caption_eval_cases()
    case_ids = {case["id"] for case in cases}

    assert {
        "facebook_required_terms_pass",
        "instagram_schema_pass",
        "blocked_term_failure",
        "required_terms_missing_failure",
        "schema_invalid_missing_caption",
        "secret_prompt_redaction_pass",
        "multi_candidate_no_publish_side_effects",
    }.issubset(case_ids)

    result = run_caption_eval_cases(tenant=tenant, user=user, cases=cases)

    assert result.passed is True
    assert result.as_dict()["failed_count"] == 0
    assert ApprovalRequest.all_objects.count() == 0
    assert ContentSchedule.all_objects.count() == 0
    assert PublishAttempt.all_objects.count() == 0
    assert PublishedPost.all_objects.count() == 0
    assert OrganicPostMetricSnapshot.all_objects.count() == 0
    assert ContentDraft.all_objects.count() == sum(
        int((case.get("expected") or {}).get("draft_count") or 0)
        for case in cases
        if (case.get("expected") or {}).get("status")
        == CAPTION_PROCESS_STATUS_SUCCEEDED
    )


@pytest.mark.django_db
def test_caption_eval_failure_output_reports_expected_and_actual(tenant):
    case = {
        "id": "intentional_mismatch",
        "workspace": {
            "name": "Intentional mismatch",
            "target_channels": ["facebook_page"],
        },
        "brief": {
            "campaign_theme": "Mismatch",
            "audience": "Operators",
            "offer": "Review",
            "tone": "plain",
            "required_terms": [],
            "blocked_terms": ["guaranteed"],
        },
        "request": {
            "candidate_count": 1,
            "platforms": ["facebook_page"],
        },
        "provider_response": {
            "candidates": [
                {
                    "platform": "facebook_page",
                    "caption": "This guaranteed claim should fail policy.",
                    "hashtags": [],
                    "cta": "Review",
                    "alt_text": "Review graphic",
                    "risk_flags": [],
                    "quality_score": 0.7,
                }
            ],
            "warnings": [],
        },
        "expected": {
            "status": CAPTION_PROCESS_STATUS_SUCCEEDED,
            "failure_code": "",
            "draft_count": 1,
        },
    }

    result = run_caption_eval_cases(tenant=tenant, cases=[case])

    assert result.passed is False
    payload = result.as_dict()
    assert payload["failed_count"] == 1
    failed_case = payload["results"][0]
    assert failed_case["case_id"] == "intentional_mismatch"
    assert failed_case["expected_status"] == CAPTION_PROCESS_STATUS_SUCCEEDED
    assert failed_case["actual_status"] == "failed"
    assert failed_case["actual_failure_code"] == CAPTION_FAILURE_POLICY_BLOCKED
    assert failed_case["failures"]
