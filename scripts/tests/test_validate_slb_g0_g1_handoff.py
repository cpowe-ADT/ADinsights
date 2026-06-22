from __future__ import annotations

import json

import scripts.validate_slb_g0_g1_handoff as cli


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_validator(g0_path, g1_path, capsys):
    exit_code = cli.main(
        [
            "--g0-review-file",
            str(g0_path),
            "--g1-intake-file",
            str(g1_path),
            "--format",
            "json",
        ]
    )
    return exit_code, json.loads(capsys.readouterr().out)


def _valid_g0(status="approved_for_g1"):
    capture = "proceed_to_g1" if status == "approved_for_g1" else "proceed_to_g1_with_followups"
    review = {
        "schema_version": "slb_g0_raj_mira_review.v1",
        "status": status,
        "decision": {
            "scope_classification": "accepted_cross_stream_scope",
            "architecture_classification": "accepted_architecture",
            "g1_g11_evidence_capture": capture,
            "dashthis_cancellation": "no_go",
            "reason": "Raj and Mira approved fixed-target evidence capture.",
        },
        "reviewers": {
            "raj": {"decision": status, "name_or_handle": "Raj", "notes": "Approved."},
            "mira": {"decision": status, "name_or_handle": "Mira", "notes": "Approved."},
        },
        "guardrails": {
            "instagram_deferred": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
            "tenant_isolation_required": True,
            "aggregate_only_no_user_level_metrics": True,
            "dashthis_active_until_g12": True,
        },
        "required_followups": [],
    }
    if status == "approved_with_followups":
        review["required_followups"] = [
            {
                "id": "FOLLOW-001",
                "owner_route": ["Omar"],
                "required_before_g1": False,
                "required_before_g12": True,
                "description": "Capture extra production-readiness evidence before G12.",
            }
        ]
    return review


def _valid_g1(proceed="approved", conditions="None", reviewer_decision="approved"):
    return {
        "schema_version": "slb_g1_runtime_target_intake.v1",
        "status": "candidate_ready_for_review",
        "g0_clearance": {
            "raj_decision": reviewer_decision,
            "mira_decision": reviewer_decision,
            "can_proceed_to_g1_g11": proceed,
            "conditions": conditions,
        },
        "target": {
            "environment": "staging",
            "backend_url": "https://adinsights.example.invalid",
            "frontend_url": "https://adinsights-ui.example.invalid",
            "safe_tenant_identifier": "tenant-slb-redacted",
            "safe_client_identifier": "SLB / Students' Loan Bureau",
            "report_definition_id": "11111111-2222-3333-4444-555555555555",
            "template_key": "slb_monthly_social_report",
            "report_schema_version": "report.v1",
            "primary_start_date": "2026-05-01",
            "primary_end_date": "2026-05-31",
            "timezone": "America/Jamaica",
            "currency": "JMD",
            "paid_meta_account_scope": "paid-meta-account-redacted",
            "organic_facebook_page_scope": "facebook-page-redacted",
            "content_ops_workspace_scope": "content-ops-workspace-redacted",
        },
        "comparison": {
            "dashthis_source_comparison_owner": "Andre",
            "dashthis_source_evidence_location": "docs/project/evidence/dashthis-replacement/source-platform-comparison-worksheet.md",
            "tolerances_confirmed": True,
        },
        "delivery": {
            "scheduled_delivery_mode": "dry_run_only",
            "recipient_assumption": "internal-review-list-redacted",
            "dashthis_active": True,
        },
        "guardrails": {
            "instagram_decision": "deferred_in_v1",
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
        "evidence": {
            "slb_report_target_intake_output": "docs/project/evidence/dashthis-replacement/g1-target-intake-output-redacted.json",
            "operator_notes": "Safe redacted intake values only.",
        },
    }


def test_valid_g0_g1_handoff_passes(tmp_path, capsys):
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0())
    _write_json(g1_path, _valid_g1())

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_conditional_g0_g1_handoff_passes(tmp_path, capsys):
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0("approved_with_followups"))
    _write_json(
        g1_path,
        _valid_g1(
            "approved_with_conditions",
            "Followups required before G12.",
            "approved_with_followups",
        ),
    )

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_g1_reviewer_decisions_must_preserve_g0_followup_approval(tmp_path, capsys):
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0("approved_with_followups"))
    _write_json(g1_path, _valid_g1("approved_with_conditions", "Followups required before G12.", "approved"))

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G1 g0_clearance.raj_decision must preserve G0 followup approval" in error for error in result["errors"])
    assert any("G1 g0_clearance.mira_decision must preserve G0 followup approval" in error for error in result["errors"])


def test_g1_reviewer_decisions_must_preserve_clean_g0_approval(tmp_path, capsys):
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0())
    _write_json(g1_path, _valid_g1("approved", "None", "approved_with_conditions"))

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G1 g0_clearance.raj_decision must preserve clean G0 approval" in error for error in result["errors"])
    assert any("G1 g0_clearance.mira_decision must preserve clean G0 approval" in error for error in result["errors"])


def test_g1_target_dates_must_be_ordered(tmp_path, capsys):
    g1 = _valid_g1()
    g1["target"]["primary_start_date"] = "2026-05-31"
    g1["target"]["primary_end_date"] = "2026-05-01"
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0())
    _write_json(g1_path, g1)

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G1 target.primary_start_date must be on or before primary_end_date." in result["errors"]


def test_g1_handoff_requires_target_intake_output(tmp_path, capsys):
    g1 = _valid_g1()
    g1["evidence"]["slb_report_target_intake_output"] = "pending"
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0())
    _write_json(g1_path, g1)

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G1 evidence.slb_report_target_intake_output is required." in result["errors"]


def test_mismatched_approval_path_fails(tmp_path, capsys):
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0("approved_with_followups"))
    _write_json(g1_path, _valid_g1("approved", "None", "approved_with_followups"))

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G0 approval path and G1" in error for error in result["errors"])
    assert any("G1 g0_clearance.conditions must summarize G0 followups" in error for error in result["errors"])


def test_blocked_g0_fails_handoff(tmp_path, capsys):
    g0 = _valid_g0()
    g0["status"] = "blocked_pending_changes"
    g0["decision"]["g1_g11_evidence_capture"] = "blocked_before_g1"
    g0["reviewers"]["raj"]["decision"] = "blocked_pending_changes"
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, g0)
    _write_json(g1_path, _valid_g1())

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G0 status must approve G1 evidence capture" in error for error in result["errors"])
    assert any("G0 decision.g1_g11_evidence_capture must proceed to G1" in error for error in result["errors"])


def test_guardrail_drift_fails(tmp_path, capsys):
    g0 = _valid_g0()
    g1 = _valid_g1()
    g0["guardrails"]["stored_aggregate_only"] = False
    g1["guardrails"]["no_live_provider_calls_at_render_export_time"] = False
    g1["delivery"]["dashthis_active"] = False
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, g0)
    _write_json(g1_path, g1)

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G0 guardrails.stored_aggregate_only must be true" in error for error in result["errors"])
    assert any("G1 guardrails.no_live_provider_calls_at_render_export_time must be true" in error for error in result["errors"])
    assert any("G1 delivery.dashthis_active must be true" in error for error in result["errors"])


def test_sensitive_values_are_rejected(tmp_path, capsys):
    g1 = _valid_g1()
    g1["evidence"]["operator_notes"] = "access_token should never be pasted here"
    g0_path = tmp_path / "g0.json"
    g1_path = tmp_path / "g1.json"
    _write_json(g0_path, _valid_g0())
    _write_json(g1_path, g1)

    exit_code, result = _run_validator(g0_path, g1_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected" in error for error in result["errors"])
