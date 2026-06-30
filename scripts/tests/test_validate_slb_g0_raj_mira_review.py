from __future__ import annotations

import json

import scripts.validate_slb_g0_raj_mira_review as cli


TEMPLATE = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-g0-raj-mira-review-decision.template.json"
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_preflight_packet_dir(path, *, scope_status="ESCALATE_ARCH_RISK", contract_status="WARN_POSSIBLE_CONTRACT_CHANGE", release_status="GATE_BLOCK"):
    path.mkdir()
    _write_json(path / "scope-packet.json", {"schema_version": "1.1.0", "scope_status": scope_status})
    _write_json(path / "contract-packet.json", {"schema_version": "1.0.0", "contract_status": contract_status})
    _write_json(path / "release-packet.json", {"schema_version": "1.1.0", "release_status": release_status})


def _run_validator(review_path, capsys):
    exit_code = cli.main(["--review-file", str(review_path), "--format", "json"])
    return exit_code, json.loads(capsys.readouterr().out)


def _valid_review(status="approved_for_g1"):
    return {
        "schema_version": "slb_g0_raj_mira_review.v1",
        "status": status,
        "references": {
            "review_packet": "docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md",
            "preflight_packet": "docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/",
            "checked_preflight_packet": "docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/",
            "decision_id": "slb-g0-20260616-raj-mira",
            "decision_timestamp": "2026-06-16T22:00:00-05:00",
            "operator": "operator",
        },
        "decision": {
            "scope_classification": "accepted_cross_stream_scope",
            "architecture_classification": "accepted_architecture",
            "g1_g11_evidence_capture": "proceed_to_g1",
            "dashthis_cancellation": "no_go",
            "reason": "Raj and Mira approved fixed-target evidence capture; cancellation remains no-go.",
        },
        "reviewers": {
            "raj": {
                "decision": status,
                "name_or_handle": "Raj",
                "notes": "Cross-stream scope accepted for G1-G11 evidence capture.",
            },
            "mira": {
                "decision": status,
                "name_or_handle": "Mira",
                "notes": "Architecture accepted for fixed-target evidence capture.",
            },
        },
        "guardrails": {
            "instagram_deferred": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
            "tenant_isolation_required": True,
            "aggregate_only_no_user_level_metrics": True,
            "dashthis_active_until_g12": True,
        },
        "preflight_interpretation": {
            "scope_status": "ESCALATE_ARCH_RISK",
            "contract_status": "WARN_POSSIBLE_CONTRACT_CHANGE",
            "release_status": "GATE_BLOCK",
            "classified_as_architecture_review_not_runtime_failure": True,
            "contract_warning_route": "Raj/Mira/Sofia/Andre",
            "security_pii_warning_route": "Nina/Omar/Hannah",
        },
        "required_followups": [],
        "reviewer_route_confirmed": {
            "sofia": True,
            "andre": True,
            "lina_or_joel": True,
            "omar_or_hannah": True,
            "nina_if_sensitive": True,
            "priya_martin_if_retention_gap": True,
            "raj_mira_for_g12": True,
        },
        "decision_log": [
            {
                "timestamp": "2026-06-16T22:00:00-05:00",
                "actor": "Raj/Mira",
                "summary": "Approved G1-G11 evidence capture with DashThis cancellation still blocked.",
            }
        ],
    }


def test_valid_g0_review_passes(tmp_path, capsys):
    review_path = tmp_path / "review.json"
    _write_json(review_path, _valid_review())

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_template_pending_values_fail(tmp_path, capsys):
    review_path = tmp_path / "review.json"
    review_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status must be approved_for_g1" in error for error in result["errors"])
    assert any("decision.scope_classification is unsupported" in error for error in result["errors"])


def test_blocked_before_g1_decision_passes_as_valid_classification(tmp_path, capsys):
    review = _valid_review("blocked_pending_changes")
    review["decision"]["scope_classification"] = "blocked_pending_split"
    review["decision"]["architecture_classification"] = "blocked_pending_architecture_changes"
    review["decision"]["g1_g11_evidence_capture"] = "blocked_before_g1"
    review["reviewers"]["raj"]["decision"] = "blocked_pending_changes"
    review["reviewers"]["mira"]["decision"] = "blocked_pending_changes"
    review["required_followups"] = [
        {
            "id": "split-backend-frontend-review",
            "owner_route": ["Raj", "Mira"],
            "required_before_g1": True,
            "required_before_g12": True,
            "description": "Split or reclassify the cross-stream scope before fixed-target evidence capture.",
        }
    ]
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_approved_with_followups_requires_followup_capture_mode(tmp_path, capsys):
    review = _valid_review("approved_with_followups")
    review["reviewers"]["raj"]["decision"] = "approved_with_followups"
    review["decision"]["scope_classification"] = "accepted_with_followups"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status approved_with_followups requires decision.g1_g11_evidence_capture" in error for error in result["errors"])


def test_approved_with_followups_rejects_placeholder_followup_row(tmp_path, capsys):
    review = _valid_review("approved_with_followups")
    review["reviewers"]["raj"]["decision"] = "approved_with_followups"
    review["decision"]["scope_classification"] = "accepted_with_followups"
    review["decision"]["g1_g11_evidence_capture"] = "proceed_to_g1_with_followups"
    review["required_followups"] = [
        {
            "id": "pending",
            "owner_route": ["pending"],
            "required_before_g1": False,
            "required_before_g12": False,
            "description": "pending",
        }
    ]
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("required_followups must include real followup rows" in error for error in result["errors"])


def test_clean_approval_rejects_followup_classification(tmp_path, capsys):
    review = _valid_review("approved_for_g1")
    review["decision"]["scope_classification"] = "accepted_with_followups"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status approved_for_g1 requires clean scope acceptance" in error for error in result["errors"])


def test_blocked_status_requires_blocked_evidence_capture(tmp_path, capsys):
    review = _valid_review("blocked_pending_changes")
    review["reviewers"]["raj"]["decision"] = "blocked_pending_changes"
    review["decision"]["scope_classification"] = "blocked_pending_split"
    review["required_followups"] = [
        {
            "id": "split-before-g1",
            "owner_route": ["Raj"],
            "required_before_g1": True,
            "required_before_g12": True,
            "description": "Split scope before evidence capture.",
        }
    ]
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status blocked_pending_changes requires decision.g1_g11_evidence_capture" in error for error in result["errors"])


def test_proceeding_to_g1_requires_scope_and_architecture_acceptance(tmp_path, capsys):
    review = _valid_review()
    review["decision"]["scope_classification"] = "blocked_pending_split"
    review["decision"]["architecture_classification"] = "blocked_pending_architecture_changes"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("decision.scope_classification must accept scope" in error for error in result["errors"])
    assert any("decision.architecture_classification must accept architecture" in error for error in result["errors"])


def test_missing_reviewer_route_fails(tmp_path, capsys):
    review = _valid_review()
    review["reviewer_route_confirmed"]["nina_if_sensitive"] = False
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("reviewer_route_confirmed.nina_if_sensitive must be true" in error for error in result["errors"])


def test_preflight_packet_statuses_must_match_interpretation(tmp_path, capsys):
    packet_dir = tmp_path / "preflight"
    checked_packet_dir = tmp_path / "checked-preflight"
    _write_preflight_packet_dir(packet_dir, scope_status="PASS_SINGLE_SCOPE")
    _write_preflight_packet_dir(checked_packet_dir)
    review = _valid_review()
    review["references"]["preflight_packet"] = str(packet_dir)
    review["references"]["checked_preflight_packet"] = str(checked_packet_dir)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("references.preflight_packet scope-packet scope_status does not match" in error for error in result["errors"])


def test_checked_preflight_packet_statuses_must_match_interpretation(tmp_path, capsys):
    packet_dir = tmp_path / "preflight"
    checked_packet_dir = tmp_path / "checked-preflight"
    _write_preflight_packet_dir(packet_dir)
    _write_preflight_packet_dir(checked_packet_dir, contract_status="PASS_NO_CONTRACT_CHANGE", release_status="GATE_PASS")
    review = _valid_review()
    review["references"]["preflight_packet"] = str(packet_dir)
    review["references"]["checked_preflight_packet"] = str(checked_packet_dir)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("references.checked_preflight_packet contract-packet contract_status does not match" in error for error in result["errors"])
    assert any("references.checked_preflight_packet release-packet release_status does not match" in error for error in result["errors"])


def test_preflight_packet_must_include_required_packet_files(tmp_path, capsys):
    packet_dir = tmp_path / "preflight"
    checked_packet_dir = tmp_path / "checked-preflight"
    packet_dir.mkdir()
    checked_packet_dir.mkdir()
    _write_json(packet_dir / "scope-packet.json", {"scope_status": "ESCALATE_ARCH_RISK"})
    _write_json(packet_dir / "contract-packet.json", {"contract_status": "WARN_POSSIBLE_CONTRACT_CHANGE"})
    _write_json(checked_packet_dir / "scope-packet.json", {"scope_status": "ESCALATE_ARCH_RISK"})
    _write_json(checked_packet_dir / "contract-packet.json", {"contract_status": "WARN_POSSIBLE_CONTRACT_CHANGE"})
    _write_json(checked_packet_dir / "release-packet.json", {"release_status": "GATE_BLOCK"})
    review = _valid_review()
    review["references"]["preflight_packet"] = str(packet_dir)
    review["references"]["checked_preflight_packet"] = str(checked_packet_dir)
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("references.preflight_packet/release-packet.json does not exist" in error for error in result["errors"])


def test_dashthis_cancellation_must_remain_no_go(tmp_path, capsys):
    review = _valid_review()
    review["decision"]["dashthis_cancellation"] = "cancel"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("decision.dashthis_cancellation must remain no_go" in error for error in result["errors"])


def test_sensitive_values_are_rejected(tmp_path, capsys):
    review = _valid_review()
    review["reviewers"]["raj"]["notes"] = "Contact raj@example.com"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected" in error for error in result["errors"])


def test_decision_id_must_be_stable_g0_slug(tmp_path, capsys):
    review = _valid_review()
    review["references"]["decision_id"] = "slb decision 1"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("references.decision_id must be a stable slug" in error for error in result["errors"])


def test_decision_timestamp_requires_timezone(tmp_path, capsys):
    review = _valid_review()
    review["references"]["decision_timestamp"] = "2026-06-16T22:00:00"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("references.decision_timestamp must be an ISO-8601 timestamp with timezone" in error for error in result["errors"])


def test_decision_log_timestamps_must_be_ordered(tmp_path, capsys):
    review = _valid_review()
    review["decision_log"] = [
        {
            "timestamp": "2026-06-16T22:05:00-05:00",
            "actor": "Raj",
            "summary": "Raj approved evidence capture.",
        },
        {
            "timestamp": "2026-06-16T22:00:00-05:00",
            "actor": "Mira",
            "summary": "Mira approved evidence capture.",
        },
    ]
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("decision_log timestamps must be in ascending order" in error for error in result["errors"])


def test_blocked_g0_requires_before_g1_followup(tmp_path, capsys):
    review = _valid_review("blocked_pending_changes")
    review["decision"]["scope_classification"] = "blocked_pending_split"
    review["decision"]["architecture_classification"] = "blocked_pending_architecture_changes"
    review["decision"]["g1_g11_evidence_capture"] = "blocked_before_g1"
    review["reviewers"]["raj"]["decision"] = "blocked_pending_changes"
    review["reviewers"]["mira"]["decision"] = "blocked_pending_changes"
    review["required_followups"] = []
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("required_followups must list blocking changes" in error for error in result["errors"])


def test_followup_owner_route_rejects_placeholder_and_requires_deadline(tmp_path, capsys):
    review = _valid_review("approved_with_followups")
    review["decision"]["scope_classification"] = "accepted_with_followups"
    review["decision"]["g1_g11_evidence_capture"] = "proceed_to_g1_with_followups"
    review["reviewers"]["raj"]["decision"] = "approved_with_followups"
    review["required_followups"] = [
        {
            "id": "artifact-safety-review",
            "owner_route": ["pending"],
            "required_before_g1": False,
            "required_before_g12": False,
            "description": "Confirm artifact safety routing before cancellation recommendation.",
        }
    ]
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("required_followups[0].owner_route[0] is required" in error for error in result["errors"])
    assert any("required_followups[0] must be required before G1 or before G12" in error for error in result["errors"])
