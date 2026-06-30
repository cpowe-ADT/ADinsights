from __future__ import annotations

import json

import scripts.slb_cancellation_readiness_doctor as cli


def _run_doctor(status_path, capsys):
    exit_code = cli.main(["--status-file", str(status_path), "--format", "json"])
    return exit_code, json.loads(capsys.readouterr().out)


def _minimal_status():
    return {
        "schema_version": "slb_cancellation_readiness_status.v1",
        "decision": {
            "implementation_readiness": "partial",
            "cancellation_review_readiness": "no_go",
            "dashthis_cancellation": "no_go",
            "reason": "Testing",
        },
        "guardrails": {
            "instagram_v1": "deferred",
            "render_export_data_source": "stored_aggregate_adinsights_data_only",
            "live_provider_calls_at_render_export_time": "forbidden",
            "dashthis_status": "keep_active_until_evidence_passes",
        },
        "sub_goals": [
            {
                "id": "G0",
                "name": "Raj/Mira architecture and scope review",
                "status": "review_pending",
                "blocked_by": ["BLK-001"],
                "primary_evidence": "docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md",
            },
            {
                "id": "G1",
                "name": "Fixed SLB proof target and date range",
                "status": "blocked_external",
                "blocked_by": ["BLK-002"],
                "primary_evidence": "docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md",
            },
        ],
        "active_blockers": [
            {
                "id": "BLK-001",
                "status": "waiting_external",
                "owner_route": ["Raj", "Mira"],
                "unblock_action": "Classify the architecture/scope GATE_BLOCK.",
            },
            {
                "id": "BLK-002",
                "status": "waiting_external",
                "owner_route": ["Operator", "Hannah", "Raj"],
                "unblock_action": "Fill the G1 fixed runtime target.",
            },
        ],
        "next_execution": {
            "preferred_next_action": "Get Raj/Mira G0 classification and fill G1.",
            "next_without_external_input": (
                "Continue improving evidence automation or documentation only; do not mark "
                "G1-G12 sub-goals passed without fixed-target evidence."
            ),
            "status_validator": "python3 scripts/validate_slb_cancellation_readiness_status.py",
            "g0_review_validator": "python3 scripts/validate_slb_g0_raj_mira_review.py --review-file <filled-g0.json>",
            "g1_intake_template": "docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json",
            "g1_intake_draft_helper": "python3 scripts/slb_g1_intake_draft.py --target-intake-output <target-output.json> --output <draft-g1.json>",
            "g1_intake_validator": "python3 scripts/validate_slb_g1_runtime_target_intake.py --intake-file <filled-g1.json>",
            "g0_g1_handoff_validator": "python3 scripts/validate_slb_g0_g1_handoff.py --g0-review-file <filled-g0.json> --g1-intake-file <filled-g1.json>",
        },
        "required_updates_when_status_changes": ["docs/ops/agent-activity-log.md"],
    }


def test_doctor_reports_current_g0_blocker(tmp_path, capsys):
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(_minimal_status()), encoding="utf-8")

    exit_code, result = _run_doctor(status_path, capsys)

    assert exit_code == 0
    assert result["next_goal"]["id"] == "G0"
    assert result["next_blockers"][0]["id"] == "BLK-001"
    assert "G0 Raj/Mira review decision" in result["recommended_action"]
    assert result["local_progress_action"] == (
        "Continue improving evidence automation or documentation only; do not mark "
        "G1-G12 sub-goals passed without fixed-target evidence."
    )
    product_capability = result["product_capability_assessment"]
    assert product_capability["schema_version"] == "slb_product_capability_assessment.v1"
    assert product_capability["status"] == "needs_internal_product_evidence"
    assert product_capability["external_inputs_are_product_blockers"] is False
    assert product_capability["counts"]["product_capability_blockers"] == 1
    assert product_capability["counts"]["comparison_or_release_inputs"] == 1
    assert any("validate_slb_g0_raj_mira_review.py" in command for command in result["commands"])
    assert result["decision"]["dashthis_cancellation"] == "no_go"


def test_doctor_reports_g1_after_g0_passes(tmp_path, capsys):
    payload = _minimal_status()
    payload["sub_goals"][0]["status"] = "passed"
    payload["active_blockers"][0]["status"] = "resolved"
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_doctor(status_path, capsys)

    assert exit_code == 0
    assert result["next_goal"]["id"] == "G1"
    assert result["next_blockers"][0]["id"] == "BLK-002"
    assert "G1 runtime target intake" in result["recommended_action"]
    assert any("slb_g1_intake_draft.py" in command for command in result["commands"])
    assert any("validate_slb_g1_runtime_target_intake.py" in command for command in result["commands"])
    assert any("validate_slb_g0_g1_handoff.py" in command for command in result["commands"])
    assert result["fixed_target_prerequisite"]["id"] == "G1"
    assert result["fixed_target_prerequisite"]["status"] == "blocked_external"
    slb_objective = next(row for row in result["objective_progress"] if row["id"] == "SLB-001")
    assert slb_objective["can_start_fixed_target_evidence"] is False
    assert slb_objective["fixed_target_prerequisite"]["required"] is True
    assert slb_objective["fixed_target_prerequisite"]["satisfied"] is False
    assert slb_objective["fixed_target_prerequisite"]["goal"]["id"] == "G1"
    assert slb_objective["fixed_target_prerequisite"]["goal"]["status"] == "blocked_external"
    g1_requirements = result["g1_intake_requirements"]
    assert g1_requirements["template_exists"] is True
    assert "target.environment" in g1_requirements["pending_fields"]
    assert "target.report_definition_id" in g1_requirements["pending_fields"]
    assert "comparison.tolerances_confirmed" in g1_requirements["false_confirmation_fields"]
    product_capability = result["product_capability_assessment"]
    assert (
        product_capability["status"]
        == "product_capable_pending_comparison_or_release_inputs"
    )
    assert product_capability["counts"]["product_capability_blockers"] == 0
    assert product_capability["counts"]["comparison_or_release_inputs"] == 1
    assert (
        "Missing DashThis/source values can block a parity or cancellation claim"
        in product_capability["no_fake_data_rule"]
    )


def test_doctor_reports_missing_g1_intake_template(tmp_path, capsys):
    payload = _minimal_status()
    payload["next_execution"]["g1_intake_template"] = "docs/project/evidence/dashthis-replacement/missing-g1-template.json"
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_doctor(status_path, capsys)

    assert exit_code == 0
    assert result["g1_intake_requirements"]["template_exists"] is False
    assert result["g1_intake_requirements"]["pending_fields"] == []


def test_doctor_maps_objective_progress_to_readiness_blockers(tmp_path, capsys):
    payload = _minimal_status()
    payload["sub_goals"][0]["status"] = "passed"
    payload["active_blockers"][0]["status"] = "resolved"
    payload["sub_goals"].append(
        {
            "id": "G6",
            "name": "Parity worksheet against DashThis/source values",
            "status": "evidence_pending",
            "blocked_by": ["BLK-004"],
            "primary_evidence": "docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md",
        }
    )
    payload["active_blockers"].append(
        {
            "id": "BLK-004",
            "status": "waiting_external",
            "owner_route": ["DashThis/source owner", "Andre", "Raj", "Business owner"],
            "unblock_action": "Provide fixed-range DashThis/source values.",
        }
    )
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_doctor(status_path, capsys)

    assert exit_code == 0
    objective = next(row for row in result["objective_progress"] if row["id"] == "SLB-004")
    assert objective["status"] == "blocked_external"
    assert objective["readiness_goals"][0]["id"] == "G6"
    assert objective["blockers"][0]["id"] == "BLK-004"
    assert objective["blockers"][0]["capability_lane"] == "source_comparison_input"
    assert objective["blockers"][0]["product_blocker"] is False
    assert "never invented" in objective["note"]
    product_capability = result["product_capability_assessment"]
    assert (
        product_capability["status"]
        == "product_capable_pending_comparison_or_release_inputs"
    )
    assert "source_comparison_input" in product_capability["lanes"]


def test_doctor_reports_missing_status_file(tmp_path, capsys):
    missing_path = tmp_path / "missing.json"

    exit_code, result = _run_doctor(missing_path, capsys)

    assert exit_code == 1
    assert result["valid_input"] is False
    assert any("Status file does not exist" in error for error in result["errors"])


def test_doctor_text_output_includes_local_progress_guidance(tmp_path, capsys):
    payload = _minimal_status()
    payload["sub_goals"][0]["status"] = "passed"
    payload["active_blockers"][0]["status"] = "resolved"
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = cli.main(["--status-file", str(status_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Recommended action: Fill the G1 runtime target intake JSON" in output
    assert (
        "Product capability status: product_capable_pending_comparison_or_release_inputs"
        in output
    )
    assert "Product blockers: 0 internal, 1 comparison/release inputs" in output
    assert (
        "Local progress while waiting: Continue improving evidence automation or documentation only; "
        "do not mark G1-G12 sub-goals passed without fixed-target evidence."
    ) in output
    assert "Fixed-target prerequisite: G1 (blocked_external)" in output
    assert "G1 intake template:" in output
    assert "target.report_definition_id" in output
    assert "comparison.tolerances_confirmed" in output
    assert "Objective map:" in output
    assert "G1_prereq=blocked_external" in output
    assert "- SLB-004" in output
