from __future__ import annotations

import json
import re

import scripts.validate_slb_cancellation_readiness_status as cli


def _copy_control_files(tmp_path):
    status_path = tmp_path / "status.json"
    goal_doc_path = tmp_path / "goals.md"
    blocker_register_path = tmp_path / "blockers.md"
    status_path.write_text(cli.DEFAULT_STATUS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    goal_doc_path.write_text(cli.DEFAULT_GOAL_DOC.read_text(encoding="utf-8"), encoding="utf-8")
    blocker_register_path.write_text(
        cli.DEFAULT_BLOCKER_REGISTER.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return status_path, goal_doc_path, blocker_register_path


def _run_validator(status_path, goal_doc_path, blocker_register_path, capsys):
    exit_code = cli.main(
        [
            "--status-file",
            str(status_path),
            "--goal-doc",
            str(goal_doc_path),
            "--blocker-register",
            str(blocker_register_path),
            "--format",
            "json",
        ]
    )
    return exit_code, json.loads(capsys.readouterr().out)


def _replace_table_status(text: str, row_id: str, status: str) -> str:
    pattern = re.compile(rf"^(\|\s*{re.escape(row_id)}\s*\|[^|]*\|\s*)`[^`]+`(\s*\|.*)$", re.MULTILINE)
    updated, count = pattern.subn(rf"\1`{status}`\2", text, count=1)
    assert count == 1, f"Expected to update status for {row_id}"
    return updated


def _write_goal_statuses(goal_doc_path, statuses):
    text = goal_doc_path.read_text(encoding="utf-8")
    for goal_id, status in statuses.items():
        text = _replace_table_status(text, goal_id, status)
    goal_doc_path.write_text(text, encoding="utf-8")


def _write_blocker_statuses(blocker_register_path, statuses):
    text = blocker_register_path.read_text(encoding="utf-8")
    for blocker_id, status in statuses.items():
        text = _replace_table_status(text, blocker_id, status)
    blocker_register_path.write_text(text, encoding="utf-8")


def test_current_slb_readiness_status_manifest_is_valid(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["warnings"] == []


def test_validator_rejects_missing_readiness_doctor_script(tmp_path, capsys, monkeypatch):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    monkeypatch.setattr(cli, "DOCTOR_SCRIPT", tmp_path / "missing-doctor.py")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("SLB readiness doctor script does not exist" in error for error in result["errors"])


def test_validator_rejects_readiness_doctor_product_capability_drift(
    tmp_path, capsys, monkeypatch
):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    fake_doctor = tmp_path / "fake-doctor.py"
    fake_doctor.write_text(
        "import json\n"
        f"ids = {cli.EXPECTED_OBJECTIVE_IDS!r}\n"
        "print(json.dumps({"
        "'product_capability_assessment': {"
        "'schema_version': 'slb_product_capability_assessment.v1', "
        "'external_inputs_are_product_blockers': True, "
        "'no_fake_data_rule': 'Missing values are fine.', "
        "'counts': {'product_capability_blockers': 0, 'comparison_or_release_inputs': 0}, "
        "'lanes': {}"
        "}, "
        "'fixed_target_prerequisite': {'id': 'G1', 'status': 'blocked_external'}, "
        "'g1_intake_requirements': {"
        "'template_exists': True, "
        "'pending_fields': ['target.report_definition_id'], "
        "'false_confirmation_fields': ['comparison.tolerances_confirmed']"
        "}, "
        "'objective_progress': ["
        "{'id': objective_id, 'status': 'evidence_pending', "
        "'readiness_goals': [{'id': 'G2', 'status': 'evidence_pending'}], "
        "'fixed_target_prerequisite': {"
        "'required': True, "
        "'satisfied': False, "
        "'goal': {'id': 'G1', 'status': 'blocked_external'}"
        "}, "
        "'can_start_fixed_target_evidence': False, "
        "'note': 'Testing drift.'}"
        " for objective_id in ids"
        "]"
        "}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "DOCTOR_SCRIPT", fake_doctor)

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "must not classify external comparison/release inputs as product blockers"
        in error
        for error in result["errors"]
    )
    assert any("must preserve the no-fake-data rule" in error for error in result["errors"])


def test_validator_rejects_readiness_doctor_objective_map_drift(
    tmp_path, capsys, monkeypatch
):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    monkeypatch.setattr(cli, "EXPECTED_OBJECTIVE_IDS", ["SLB-001", "SLB-999"])

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("objective_progress must list active objectives in order" in error for error in result["errors"])


def test_validator_rejects_readiness_doctor_objective_fixed_target_gate_drift(
    tmp_path, capsys, monkeypatch
):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    fake_doctor = tmp_path / "fake-doctor.py"
    fake_doctor.write_text(
        "import json\n"
        f"ids = {cli.EXPECTED_OBJECTIVE_IDS!r}\n"
        "print(json.dumps({"
        "'fixed_target_prerequisite': {'id': 'G1', 'status': 'blocked_external'}, "
        "'g1_intake_requirements': {"
        "'template_exists': True, "
        "'pending_fields': ['target.report_definition_id'], "
        "'false_confirmation_fields': ['comparison.tolerances_confirmed']"
        "}, "
        "'objective_progress': ["
        "{'id': objective_id, 'status': 'evidence_pending', "
        "'readiness_goals': [{'id': 'G2', 'status': 'evidence_pending'}], "
        "'note': 'Testing drift.'}"
        " for objective_id in ids"
        "]"
        "}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "DOCTOR_SCRIPT", fake_doctor)

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "SLB readiness doctor objective SLB-001 must emit fixed_target_prerequisite" in error
        for error in result["errors"]
    )
    assert any(
        "SLB readiness doctor objective SLB-001 can_start_fixed_target_evidence must match G1 status" in error
        for error in result["errors"]
    )


def test_validator_rejects_goal_doc_status_drift(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    _write_goal_statuses(goal_doc_path, {"G2": "passed"})

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G2 status mismatch" in error for error in result["errors"])


def test_validator_rejects_blocker_register_status_drift(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    _write_blocker_statuses(blocker_register_path, {"BLK-005": "resolved"})

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("BLK-005 status mismatch" in error for error in result["errors"])


def test_validator_rejects_missing_g0_review_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g0_review_template"] = "docs/project/evidence/dashthis-replacement/missing-g0.json"
    payload["next_execution"]["g0_review_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g0_review_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g0_review_validator must reference" in error for error in result["errors"])


def test_validator_rejects_missing_valid_example_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["examples_readme"] = "docs/project/evidence/dashthis-replacement/examples/missing.md"
    payload["next_execution"]["g0_valid_example"] = "docs/project/evidence/dashthis-replacement/examples/missing-g0.json"
    payload["next_execution"]["g1_valid_example"] = "docs/project/evidence/dashthis-replacement/examples/missing-g1.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.examples_readme path does not exist" in error for error in result["errors"])
    assert any("next_execution.g0_valid_example path does not exist" in error for error in result["errors"])
    assert any("next_execution.g1_valid_example path does not exist" in error for error in result["errors"])


def test_validator_rejects_invalid_g0_valid_example(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    invalid_example = tmp_path / "invalid-g0-example.json"
    invalid_example.write_text(json.dumps({"schema_version": "slb_g0_raj_mira_review.v1"}), encoding="utf-8")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g0_valid_example"] = str(invalid_example)
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G0 valid example failed validation" in error for error in result["errors"])


def test_validator_rejects_invalid_g0_g1_example_handoff(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    invalid_intake = tmp_path / "invalid-g1-example.json"
    invalid_intake.write_text(json.dumps({"schema_version": "slb_g1_runtime_target_intake.v1"}), encoding="utf-8")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g1_valid_example"] = str(invalid_intake)
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G1 valid example failed validation" in error for error in result["errors"])
    assert any("G0/G1 valid example handoff failed validation" in error for error in result["errors"])


def test_validator_rejects_missing_g0_g1_external_handoff_link(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g0_g1_external_handoff"] = "docs/project/evidence/dashthis-replacement/missing-handoff.md"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g0_g1_external_handoff path does not exist" in error for error in result["errors"])


def test_validator_rejects_missing_g1_intake_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g1_intake_template"] = "docs/project/evidence/dashthis-replacement/missing-g1.json"
    payload["next_execution"]["g1_intake_draft_helper"] = "python3 scripts/other_draft.py"
    payload["next_execution"]["g1_intake_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g1_intake_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g1_intake_validator must reference" in error for error in result["errors"])
    assert any("next_execution.g1_intake_draft_helper must reference" in error for error in result["errors"])
    assert any(
        "doctor g1_intake_requirements must point to an existing template" in error
        for error in result["errors"]
    )


def test_validator_rejects_missing_g1_draft_helper_script(tmp_path, capsys, monkeypatch):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    monkeypatch.setattr(cli, "G1_DRAFT_HELPER_SCRIPT", tmp_path / "missing-draft.py")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G1 intake draft helper script does not exist" in error for error in result["errors"])


def test_validator_rejects_g1_draft_helper_example_output_drift(
    tmp_path, capsys, monkeypatch
):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    fake_helper = tmp_path / "fake-g1-draft-helper.py"
    fake_helper.write_text(
        "import json\n"
        "print(json.dumps({"
        "'schema_version': 'slb_g1_intake_draft_result.v1', "
        "'valid': True, "
        "'candidate_ready_for_review': False, "
        "'pending_fields': [], "
        "'false_confirmation_fields': []"
        "}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "G1_DRAFT_HELPER_SCRIPT", fake_helper)

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G1 draft helper example did not write draft output" in error for error in result["errors"])


def test_validator_rejects_missing_g0_g1_handoff_validator(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g0_g1_handoff_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g0_g1_handoff_validator must reference" in error for error in result["errors"])


def test_validator_rejects_missing_evidence_chain_validator(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["evidence_chain_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.evidence_chain_validator must reference" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --status-manifest-file" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --g1-intake-file" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --g2-g9-run-file" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --g10-review-file" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --g11-window-file" in error for error in result["errors"])
    assert any("next_execution.evidence_chain_validator must include --g12-recommendation-file" in error for error in result["errors"])


def test_validator_rejects_missing_g2_g9_run_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g2_g9_run_template"] = "docs/project/evidence/dashthis-replacement/missing-g2-g9.json"
    payload["next_execution"]["g2_g9_run_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g2_g9_run_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g2_g9_run_validator must reference" in error for error in result["errors"])
    assert any("next_execution.g2_g9_run_validator must include --intake-file" in error for error in result["errors"])


def test_validator_rejects_missing_g10_adversarial_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g10_adversarial_template"] = "docs/project/evidence/dashthis-replacement/missing-g10.json"
    payload["next_execution"]["g10_adversarial_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g10_adversarial_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g10_adversarial_validator must reference" in error for error in result["errors"])
    assert any("next_execution.g10_adversarial_validator must include --g2-g9-run-file" in error for error in result["errors"])
    assert any("next_execution.g10_adversarial_validator must include --intake-file" in error for error in result["errors"])


def test_validator_rejects_missing_g11_hardening_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g11_hardening_template"] = "docs/project/evidence/dashthis-replacement/missing-g11.json"
    payload["next_execution"]["g11_hardening_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g11_hardening_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g11_hardening_validator must reference" in error for error in result["errors"])
    assert any("next_execution.g11_hardening_validator must include --g10-review-file" in error for error in result["errors"])


def test_validator_rejects_g11_template_reference_drift(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    template_path = tmp_path / "g11-template.json"
    template = json.loads(
        (
            cli.DEFAULT_STATUS_FILE.parent
            / "2026-06-16-g11-hardening-window.template.json"
        ).read_text(encoding="utf-8")
    )
    del template["references"]["g1_intake_file"]
    template["references"]["g2_g9_run_valid"] = True
    template_path.write_text(json.dumps(template), encoding="utf-8")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g11_hardening_template"] = str(template_path)
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(
        status_path, goal_doc_path, blocker_register_path, capsys
    )

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "next_execution.g11_hardening_template.references.g1_intake_file is required."
        in result["errors"]
    )
    assert (
        "next_execution.g11_hardening_template.references.g2_g9_run_valid must default to false."
        in result["errors"]
    )


def test_validator_rejects_missing_g12_recommendation_links(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g12_recommendation_template"] = "docs/project/evidence/dashthis-replacement/missing-g12.json"
    payload["next_execution"]["g12_recommendation_validator"] = "python3 scripts/other_validator.py"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g12_recommendation_template path does not exist" in error for error in result["errors"])
    assert any("next_execution.g12_recommendation_validator must reference" in error for error in result["errors"])
    assert any(
        "next_execution.g12_recommendation_validator must include --status-manifest-file" in error
        for error in result["errors"]
    )
    assert any(
        "next_execution.g12_recommendation_validator must include --g11-window-file" in error
        for error in result["errors"]
    )


def test_validator_rejects_g12_template_reference_drift(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    template_path = tmp_path / "g12-template.json"
    template = json.loads(
        (
            cli.DEFAULT_STATUS_FILE.parent
            / "2026-06-16-g12-final-recommendation.template.json"
        ).read_text(encoding="utf-8")
    )
    del template["references"]["g10_review_file"]
    template["references"]["g11_window_valid"] = True
    template_path.write_text(json.dumps(template), encoding="utf-8")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g12_recommendation_template"] = str(template_path)
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(
        status_path, goal_doc_path, blocker_register_path, capsys
    )

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "next_execution.g12_recommendation_template.references.g10_review_file is required."
        in result["errors"]
    )
    assert (
        "next_execution.g12_recommendation_template.references.g11_window_valid must default to false."
        in result["errors"]
    )


def test_validator_rejects_missing_g12_approval_signoff_preflight(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["next_execution"]["g12_approval_signoff_preflight"] = (
        "docs/project/evidence/dashthis-replacement/preflight/missing-g12-approval-signoffs/"
    )
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("next_execution.g12_approval_signoff_preflight path does not exist" in error for error in result["errors"])


def test_validator_rejects_sensitive_status_manifest_values(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["decision"]["reason"] = "Do not put access_token values in readiness evidence."
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in status manifest" in error for error in result["errors"])


def test_validator_rejects_sensitive_goal_doc_values(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    goal_doc_path.write_text(
        goal_doc_path.read_text(encoding="utf-8") + "\nraw_payload: should not be pasted here\n",
        encoding="utf-8",
    )

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in goal doc" in error for error in result["errors"])


def test_validator_rejects_sensitive_blocker_register_values(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    blocker_register_path.write_text(
        blocker_register_path.read_text(encoding="utf-8") + "\nuser_id: should not be pasted here\n",
        encoding="utf-8",
    )

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in blocker register" in error for error in result["errors"])


def test_validator_rejects_premature_dashthis_cancellation_claim(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["decision"]["dashthis_cancellation"] = "cancel"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("dashthis_cancellation cannot move beyond no_go" in error for error in result["errors"])


def test_validator_rejects_passed_goal_with_unresolved_blocker(tmp_path, capsys):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["sub_goals"][2]["status"] = "passed"
    status_path.write_text(json.dumps(payload), encoding="utf-8")
    _write_goal_statuses(goal_doc_path, {"G2": "passed"})

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("G2 cannot be passed while linked blockers remain unresolved: BLK-005" in error for error in result["errors"])


def test_validator_rejects_cancellation_review_readiness_with_unresolved_blockers(
    tmp_path, capsys
):
    status_path, goal_doc_path, blocker_register_path = _copy_control_files(tmp_path)
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["decision"]["cancellation_review_readiness"] = "ready"
    for goal in payload["sub_goals"][:12]:
        goal["status"] = "passed"
    for blocker in payload["active_blockers"]:
        if blocker["id"] != "BLK-011":
            blocker["status"] = "resolved"
    payload["active_blockers"][0]["status"] = "waiting_external"
    status_path.write_text(json.dumps(payload), encoding="utf-8")
    _write_goal_statuses(
        goal_doc_path,
        {f"G{index}": "passed" for index in range(12)},
    )
    _write_blocker_statuses(
        blocker_register_path,
        {f"BLK-{index:03d}": "resolved" for index in range(2, 11)},
    )

    exit_code, result = _run_validator(status_path, goal_doc_path, blocker_register_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "cancellation_review_readiness cannot move beyond no_go while G0-G11 blockers remain unresolved: BLK-001"
        in error
        for error in result["errors"]
    )
