from __future__ import annotations

import json
from pathlib import Path

import scripts.slb_g1_intake_draft as draft_cli
import scripts.validate_slb_g1_runtime_target_intake as validator_cli


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_TARGET_OUTPUT = REPO_ROOT / "docs/project/evidence/dashthis-replacement/examples/slb-report-target-intake-output.redacted-example.json"


def _target_output(report_id: str = "11111111-2222-3333-4444-555555555555"):
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


def _write_target_output(tmp_path, payload=None):
    path = tmp_path / "target-intake-output.json"
    path.write_text(json.dumps(payload or _target_output()), encoding="utf-8")
    return path


def test_draft_prefills_target_metadata_and_keeps_operator_status_pending(tmp_path, capsys):
    target_output_path = _write_target_output(tmp_path)

    exit_code = draft_cli.main(
        [
            "--target-intake-output",
            str(target_output_path),
            "--environment",
            "staging",
            "--backend-url",
            "https://backend.example.invalid",
            "--frontend-url",
            "https://frontend.example.invalid",
            "--safe-tenant-identifier",
            "tenant-slb-redacted",
            "--currency",
            "JMD",
            "--paid-meta-account-scope",
            "paid-meta-account-redacted",
            "--organic-facebook-page-scope",
            "facebook-page-redacted",
            "--content-ops-workspace-scope",
            "content-ops-workspace-redacted",
            "--comparison-owner",
            "Andre",
            "--comparison-evidence-location",
            "docs/project/evidence/dashthis-replacement/source-platform-comparison-worksheet.md",
            "--recipient-assumption",
            "internal-review-list-redacted",
            "--operator-notes",
            "Drafted from redacted target-intake output.",
            "--g0-raj-decision",
            "approved_with_followups",
            "--g0-mira-decision",
            "approved_with_followups",
            "--g0-can-proceed-to-g1-g11",
            "approved_with_conditions",
            "--g0-conditions",
            "Complete reviewer followups before G12.",
        ]
    )

    draft = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert draft["schema_version"] == "slb_g1_runtime_target_intake.v1"
    assert draft["status"] == "pending_operator_input"
    assert draft["target"]["report_definition_id"] == "11111111-2222-3333-4444-555555555555"
    assert draft["target"]["template_key"] == "slb_monthly_social_report"
    assert draft["target"]["report_schema_version"] == "report.v1"
    assert draft["target"]["primary_start_date"] == "2026-05-01"
    assert draft["target"]["primary_end_date"] == "2026-05-31"
    assert draft["target"]["currency"] == "JMD"
    assert draft["evidence"]["slb_report_target_intake_output"] == str(target_output_path)
    assert draft["comparison"]["tolerances_confirmed"] is False

    draft_path = tmp_path / "draft-g1.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    validator_exit = validator_cli.main(["--intake-file", str(draft_path), "--format", "json"])
    validator_result = json.loads(capsys.readouterr().out)

    assert validator_exit == 1
    assert "status must be candidate_ready_for_review." in validator_result["errors"]
    assert "comparison.tolerances_confirmed must be true before G1 can pass." in validator_result["errors"]


def test_draft_can_write_to_output_file(tmp_path, capsys):
    target_output_path = _write_target_output(tmp_path)
    output_path = tmp_path / "drafts" / "g1-draft.json"

    exit_code = draft_cli.main(
        [
            "--target-intake-output",
            str(target_output_path),
            "--output",
            str(output_path),
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["draft_status"] == "pending_operator_input"
    assert result["candidate_ready_for_review"] is False
    assert "target.environment" in result["pending_fields"]
    assert "target.report_definition_id" not in result["pending_fields"]
    assert "evidence.slb_report_target_intake_output" not in result["pending_fields"]
    assert result["false_confirmation_fields"] == ["comparison.tolerances_confirmed"]
    assert any("validate_slb_g1_runtime_target_intake.py" in action for action in result["next_required_actions"])
    assert output_path.exists()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["target"]["report_definition_id"] == "11111111-2222-3333-4444-555555555555"


def test_draft_matches_checked_in_redacted_target_example(tmp_path, capsys):
    output_path = tmp_path / "g1-draft-from-example.json"

    exit_code = draft_cli.main(
        [
            "--target-intake-output",
            str(EXAMPLE_TARGET_OUTPUT),
            "--output",
            str(output_path),
            "--environment",
            "staging-example",
            "--backend-url",
            "https://adinsights-backend.example.invalid",
            "--frontend-url",
            "https://adinsights-frontend.example.invalid",
            "--safe-tenant-identifier",
            "tenant-slb-redacted-example",
            "--safe-client-identifier",
            "SLB / Students' Loan Bureau",
            "--currency",
            "JMD",
            "--paid-meta-account-scope",
            "paid-meta-account-redacted-example",
            "--organic-facebook-page-scope",
            "facebook-page-redacted-example",
            "--content-ops-workspace-scope",
            "content-ops-workspace-redacted-example",
            "--comparison-owner",
            "Andre",
            "--comparison-evidence-location",
            "docs/project/evidence/dashthis-replacement/source-platform-comparison-worksheet.md",
            "--tolerances-confirmed",
            "--recipient-assumption",
            "internal-review-group-redacted-example",
            "--operator-notes",
            "Example only: generated from the redacted target-intake example.",
            "--g0-raj-decision",
            "approved_with_followups",
            "--g0-mira-decision",
            "approved_with_followups",
            "--g0-can-proceed-to-g1-g11",
            "approved_with_conditions",
            "--g0-conditions",
            "Example only: complete listed G0 followups before G12; DashThis remains active.",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    draft = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert result["pending_fields"] == []
    assert result["false_confirmation_fields"] == []
    assert result["candidate_ready_for_review"] is False
    assert draft["status"] == "pending_operator_input"
    assert draft["target"]["report_definition_id"] == "11111111-2222-3333-4444-555555555555"
    assert draft["evidence"]["slb_report_target_intake_output"] == "docs/project/evidence/dashthis-replacement/examples/slb-report-target-intake-output.redacted-example.json"

    validator_exit = validator_cli.main(["--intake-file", str(output_path), "--format", "json"])
    validator_result = json.loads(capsys.readouterr().out)

    assert validator_exit == 1
    assert validator_result["errors"] == ["status must be candidate_ready_for_review."]


def test_draft_rejects_invalid_target_output_schema(tmp_path, capsys):
    target = _target_output()
    target["schema_version"] = "other.v1"
    target_output_path = _write_target_output(tmp_path, target)

    exit_code = draft_cli.main(["--target-intake-output", str(target_output_path)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("schema_version must be slb_target_intake.v1" in error for error in result["errors"])


def test_draft_rejects_sensitive_cli_values(tmp_path, capsys):
    target_output_path = _write_target_output(tmp_path)

    exit_code = draft_cli.main(
        [
            "--target-intake-output",
            str(target_output_path),
            "--operator-notes",
            "access_token should never be pasted here",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in draft" in error for error in result["errors"])
