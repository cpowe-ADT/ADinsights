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
            "status_validator": "python3 scripts/validate_slb_cancellation_readiness_status.py",
            "g0_review_validator": "python3 scripts/validate_slb_g0_raj_mira_review.py --review-file <filled-g0.json>",
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
    assert any("validate_slb_g1_runtime_target_intake.py" in command for command in result["commands"])
    assert any("validate_slb_g0_g1_handoff.py" in command for command in result["commands"])


def test_doctor_reports_missing_status_file(tmp_path, capsys):
    missing_path = tmp_path / "missing.json"

    exit_code, result = _run_doctor(missing_path, capsys)

    assert exit_code == 1
    assert result["valid_input"] is False
    assert any("Status file does not exist" in error for error in result["errors"])
