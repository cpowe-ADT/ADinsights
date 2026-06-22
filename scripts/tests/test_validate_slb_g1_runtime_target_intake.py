from __future__ import annotations

import json

import scripts.validate_slb_g1_runtime_target_intake as cli


def _valid_payload():
    return {
        "schema_version": "slb_g1_runtime_target_intake.v1",
        "status": "candidate_ready_for_review",
        "g0_clearance": {
            "raj_decision": "approved",
            "mira_decision": "approved",
            "can_proceed_to_g1_g11": "approved",
            "conditions": "None",
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


def _valid_target_intake_output(report_id="11111111-2222-3333-4444-555555555555"):
    return {
        "schema_version": "slb_target_intake.v1",
        "status": "candidate_ready_for_operator_confirmation",
        "report": {
            "id": report_id,
            "tenant_id": "tenant-redacted-example",
            "is_active": True,
            "schema_version": "report.v1",
            "template_key": "slb_monthly_social_report",
            "catalog_schema_version": "reporting_catalog.v1",
        },
        "date_range": {
            "report_filter": {
                "date_range": "custom",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
            },
            "layout_filters": [],
        },
        "source_scope_presence": {
            "client_id_present": True,
            "account_id_present": True,
            "page_id_present": True,
            "workspace_id_present": True,
            "delivery_recipient_count": 0,
        },
        "datasets": {
            "active": ["content_ops", "organic_facebook_page", "paid_meta_ads"],
            "required_active_v1_present": ["content_ops", "organic_facebook_page", "paid_meta_ads"],
            "missing_required_active_v1": [],
            "by_widget": [],
        },
        "pages": {
            "count": 8,
            "ids": [
                "cover",
                "executive_summary",
                "paid_meta_ads",
                "organic_facebook",
                "top_posts",
                "content_activity",
                "recommendations",
                "appendix",
            ],
            "required_slb_pages_present": True,
        },
        "widgets": {"count": 8, "by_type": {"kpi": 3, "line_chart": 2, "bar_chart": 1, "data_table": 2}},
        "schedule": {"schedule_enabled": False, "schedule_cron_present": False, "last_scheduled_at": None},
        "guardrails": {
            "report_v1": True,
            "slb_template": True,
            "instagram_deferred": True,
            "no_sensitive_patterns_detected": True,
            "no_live_provider_check": "not_applicable_offline_metadata_only",
        },
        "validation_errors": [],
        "operator_fields_still_required": [],
    }


def _attach_target_intake_output(payload, tmp_path, output=None):
    output_path = tmp_path / "target-intake-output.json"
    output_path.write_text(json.dumps(output or _valid_target_intake_output()), encoding="utf-8")
    payload["evidence"]["slb_report_target_intake_output"] = str(output_path)
    return payload


def _run_validator(payload, tmp_path, capsys):
    if payload["evidence"].get("slb_report_target_intake_output") == "docs/project/evidence/dashthis-replacement/g1-target-intake-output-redacted.json":
        payload = _attach_target_intake_output(payload, tmp_path)
    intake_path = tmp_path / "g1-intake.json"
    intake_path.write_text(json.dumps(payload), encoding="utf-8")
    exit_code = cli.main(["--intake-file", str(intake_path), "--format", "json"])
    return exit_code, json.loads(capsys.readouterr().out)


def test_valid_g1_runtime_target_intake_passes(tmp_path, capsys):
    exit_code, result = _run_validator(_valid_payload(), tmp_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_template_pending_values_do_not_pass(tmp_path, capsys):
    payload = _valid_payload()
    payload["status"] = "pending_operator_input"
    payload["target"]["report_definition_id"] = "Pending"

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "status must be candidate_ready_for_review." in result["errors"]
    assert "target.report_definition_id is required." in result["errors"]


def test_g1_intake_requires_g0_clearance(tmp_path, capsys):
    payload = _valid_payload()
    payload["g0_clearance"]["can_proceed_to_g1_g11"] = "no"

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("can_proceed_to_g1_g11" in error for error in result["errors"])


def test_g1_intake_rejects_unapproved_reviewer_decision(tmp_path, capsys):
    payload = _valid_payload()
    payload["g0_clearance"]["raj_decision"] = "blocked_pending_changes"

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "g0_clearance.raj_decision must approve or conditionally approve evidence capture." in result["errors"]


def test_g1_intake_requires_conditions_for_conditional_clearance(tmp_path, capsys):
    payload = _valid_payload()
    payload["g0_clearance"]["raj_decision"] = "approved_with_followups"
    payload["g0_clearance"]["can_proceed_to_g1_g11"] = "approved_with_conditions"
    payload["g0_clearance"]["conditions"] = "none"

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "g0_clearance.conditions is required when G0 approval is conditional or has followups." in result["errors"]


def test_g1_intake_preserves_conditional_reviewer_decision(tmp_path, capsys):
    payload = _valid_payload()
    payload["g0_clearance"]["mira_decision"] = "approved_with_conditions"
    payload["g0_clearance"]["can_proceed_to_g1_g11"] = "approved"
    payload["g0_clearance"]["conditions"] = "Complete reviewer followups before G12."

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("must preserve conditional approval" in error for error in result["errors"])


def test_g1_intake_requires_dry_run_delivery_and_active_dashthis(tmp_path, capsys):
    payload = _valid_payload()
    payload["delivery"]["scheduled_delivery_mode"] = "send_to_client"
    payload["delivery"]["dashthis_active"] = False

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "delivery.scheduled_delivery_mode must be dry_run_only." in result["errors"]
    assert "delivery.dashthis_active must be true." in result["errors"]


def test_g1_intake_requires_instagram_deferred_and_stored_aggregate_guardrails(tmp_path, capsys):
    payload = _valid_payload()
    payload["guardrails"]["instagram_decision"] = "included_in_v1"
    payload["guardrails"]["stored_aggregate_only"] = False
    payload["guardrails"]["no_live_provider_calls_at_render_export_time"] = False

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "guardrails.instagram_decision must be deferred_in_v1." in result["errors"]
    assert "guardrails.stored_aggregate_only must be true." in result["errors"]
    assert "guardrails.no_live_provider_calls_at_render_export_time must be true." in result["errors"]


def test_g1_intake_requires_existing_target_intake_output(tmp_path, capsys):
    payload = _valid_payload()
    payload["evidence"]["slb_report_target_intake_output"] = str(tmp_path / "missing-output.json")

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("slb_report_target_intake_output path does not exist" in error for error in result["errors"])


def test_g1_intake_target_output_must_match_report_id_and_dates(tmp_path, capsys):
    payload = _valid_payload()
    output = _valid_target_intake_output(report_id="99999999-2222-3333-4444-555555555555")
    output["date_range"]["report_filter"]["start_date"] = "2026-04-01"
    payload = _attach_target_intake_output(payload, tmp_path, output)

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("report.id must match target.report_definition_id" in error for error in result["errors"])
    assert any("report_filter.start_date must match target.primary_start_date" in error for error in result["errors"])


def test_g1_intake_target_output_must_confirm_required_datasets_and_guardrails(tmp_path, capsys):
    payload = _valid_payload()
    output = _valid_target_intake_output()
    output["datasets"]["required_active_v1_present"] = ["paid_meta_ads", "organic_facebook_page"]
    output["datasets"]["missing_required_active_v1"] = ["content_ops"]
    output["pages"]["required_slb_pages_present"] = False
    output["guardrails"]["instagram_deferred"] = False
    output["source_scope_presence"]["page_id_present"] = False
    payload = _attach_target_intake_output(payload, tmp_path, output)

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("must include paid_meta_ads, organic_facebook_page, and content_ops" in error for error in result["errors"])
    assert any("must not list missing required active v1 datasets" in error for error in result["errors"])
    assert any("must confirm required SLB pages are present" in error for error in result["errors"])
    assert any("guardrails.instagram_deferred must be true" in error for error in result["errors"])
    assert any("source_scope_presence.page_id_present must be true" in error for error in result["errors"])


def test_g1_intake_rejects_sensitive_values(tmp_path, capsys):
    payload = _valid_payload()
    payload["evidence"]["operator_notes"] = "access_token should never be pasted here"

    exit_code, result = _run_validator(payload, tmp_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected" in error for error in result["errors"])
