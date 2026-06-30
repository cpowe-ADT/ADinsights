from __future__ import annotations

import json

import scripts.validate_slb_g11_hardening_window as cli


TEMPLATE = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-g11-hardening-window.template.json"
)
EVIDENCE_WINDOW_DIR = (
    "docs/project/evidence/dashthis-replacement/runs/slb-g11-20260616-24h"
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _final_evidence_validation_payload(window):
    target = window["target"]
    return {
        "schema_version": "slb_evidence_validation.v1",
        "readiness_status": "warning",
        "blocker_count": 0,
        "warning_count": 1,
        "blockers": [],
        "warnings": [
            {
                "code": "warning_only_export_note",
                "message": "Warning-only export note is visible.",
            }
        ],
        "evidence": {
            "report": {
                "id": target["report_definition_id"],
                "template_key": target["template_key"],
                "schema_version": target["report_schema_version"],
            },
            "date_range": {
                "start_date": target["primary_start_date"],
                "end_date": target["primary_end_date"],
            },
            "preview_hash": "preview-hash",
            "parity_preview_hash": "preview-hash",
        },
        "unresolved_parity": {
            "row_count": 0,
            "by_result": {},
            "by_dataset": {},
            "rows": [],
        },
        "source_value_inventory": {
            "missing_source_value_count": 0,
            "missing_source_values": [],
            "unmatched_source_value_count": 0,
            "unmatched_source_values": [],
        },
        "parity_completion_requirements": {
            "ready_for_final_parity": True,
            "requirement_count": 0,
            "requirements": [],
        },
        "blocking_next_actions": {
            "action_count": 0,
            "ready_to_run_action_count": 0,
            "blocked_prerequisite_count": 0,
            "primary_next_action": "",
            "actions": [],
        },
    }


def _write_evidence_files(repo_root, window):
    for key, value in window["evidence_files"].items():
        if value == "not_required_for_24h":
            continue
        path = repo_root / value
        path.parent.mkdir(parents=True, exist_ok=True)
        if key == "final_evidence_validation":
            _write_json(path, _final_evidence_validation_payload(window))
        elif path.suffix == ".json":
            _write_json(
                path, {"schema_version": "test_g11_evidence.v1", "status": "pass"}
            )
        else:
            path.write_text("status: pass\n", encoding="utf-8")


def _run_validator(window_path, review_path, capsys):
    args = ["--window-file", str(window_path), "--format", "json"]
    if review_path:
        args.extend(["--g10-review-file", str(review_path)])
    exit_code = cli.main(args)
    return exit_code, json.loads(capsys.readouterr().out)


def _target():
    return {
        "environment": "staging",
        "safe_tenant_identifier": "tenant-slb-safe",
        "safe_client_identifier": "SLB / Students' Loan Bureau",
        "report_definition_id": "42",
        "template_key": "slb_monthly_social_report",
        "report_schema_version": "report.v1",
        "primary_start_date": "2026-05-01",
        "primary_end_date": "2026-05-31",
        "timezone": "America/Jamaica",
    }


def _valid_g10_review():
    return {
        "schema_version": "slb_g10_adversarial_review.v1",
        "status": "ready_for_g11_hardening",
        "references": {
            "g1_intake_file": "tmp/g1-intake.json",
            "g1_intake_valid": True,
            "g2_g9_run_file": "tmp/g2-g9-run.json",
            "g2_g9_run_valid": True,
        },
        "target": _target(),
        "final_checks": {"raj_mira_acceptance": True},
    }


def _checkpoint(timestamp):
    return {
        "timestamp": timestamp,
        "preview_status": "pass",
        "diagnostics_status": "pass",
        "export_status": "pass",
        "scheduled_dry_run_status": "dry_run_passed",
        "evidence_validation_status": "pass",
        "redaction_scan_passed": True,
        "reviewer_note": "Checkpoint reviewed by Omar.",
    }


def _valid_window(length_hours=24):
    checkpoints = {
        "start": _checkpoint("2026-06-16T09:00:00-05:00"),
        "midpoint_1": _checkpoint("2026-06-16T21:00:00-05:00"),
        "end": _checkpoint("2026-06-17T09:00:00-05:00"),
    }
    if length_hours > 24:
        checkpoints["midpoint_2"] = _checkpoint("2026-06-17T21:00:00-05:00")
    return {
        "schema_version": "slb_g11_hardening_window.v1",
        "status": "ready_for_g12_recommendation",
        "references": {
            "g1_intake_file": "tmp/g1-intake.json",
            "g1_intake_valid": True,
            "g2_g9_run_file": "tmp/g2-g9-run.json",
            "g2_g9_run_valid": True,
            "g10_review_file": "tmp/g10-review.json",
            "g10_review_valid": True,
            "window_id": "slb-g11-20260616-24h",
            "operator": "operator",
        },
        "target": _target(),
        "guardrails": {
            "instagram_deferred": True,
            "dashthis_active_during_window": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
        "window": {
            "length_hours": length_hours,
            "start_timestamp": "2026-06-16T09:00:00-05:00",
            "end_timestamp": "2026-06-17T09:00:00-05:00",
            "reset_occurred": False,
            "reset_reason": "",
            "evidence_validation_final_status": "pass",
            "redaction_scan_passed": True,
        },
        "checkpoints": checkpoints,
        "evidence_files": {
            "start_checkpoint": f"{EVIDENCE_WINDOW_DIR}/start-checkpoint.json",
            "midpoint_1_checkpoint": f"{EVIDENCE_WINDOW_DIR}/midpoint-1-checkpoint.json",
            "midpoint_2_checkpoint": (
                f"{EVIDENCE_WINDOW_DIR}/midpoint-2-checkpoint.json"
                if length_hours > 24
                else "not_required_for_24h"
            ),
            "end_checkpoint": f"{EVIDENCE_WINDOW_DIR}/end-checkpoint.json",
            "final_evidence_validation": f"{EVIDENCE_WINDOW_DIR}/final-evidence-validation.json",
            "final_redaction_scan": f"{EVIDENCE_WINDOW_DIR}/final-redaction-scan.txt",
            "export_snapshot_summary": f"{EVIDENCE_WINDOW_DIR}/export-snapshot-summary.json",
        },
        "export_reproducibility": {
            "csv": {
                "job_id": "job-csv-1",
                "byte_count": 1200,
                "preview_hash": "hash-fixed",
                "snapshot_preview_hash": "hash-fixed",
            },
            "pdf": {
                "job_id": "job-pdf-1",
                "byte_count": 2200,
                "preview_hash": "hash-fixed",
                "snapshot_preview_hash": "hash-fixed",
            },
            "png": {
                "job_id": "job-png-1",
                "byte_count": 3200,
                "preview_hash": "hash-fixed",
                "snapshot_preview_hash": "hash-fixed",
            },
        },
        "final_checks": {
            "no_reset_conditions": True,
            "no_unresolved_blocker_or_high": True,
            "dashthis_still_active": True,
            "rollback_path_available": True,
            "monitoring_owner_named": True,
            "support_owner_named": True,
            "raj_mira_acceptance": True,
        },
        "reviewer_route": {
            "raj": "approved",
            "mira": "approved",
            "omar": "approved",
            "hannah": "approved",
            "sofia_or_andre_if_metrics_drift": "not_required",
            "nina_if_artifact_safety": "not_required",
        },
    }


def test_valid_g11_hardening_window_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    window_path = tmp_path / "window.json"
    review_path = tmp_path / "review.json"
    _write_json(window_path, window)
    _write_json(review_path, _valid_g10_review())

    exit_code, result = _run_validator(window_path, review_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_template_pending_values_fail(tmp_path, capsys):
    window_path = tmp_path / "window.json"
    window_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "status must be ready_for_g12_recommendation" in error
        for error in result["errors"]
    )
    assert any(
        "references.g10_review_valid must be true" in error
        for error in result["errors"]
    )


def test_target_must_match_g10_review(tmp_path, capsys):
    window = _valid_window()
    window["target"]["report_definition_id"] = "99"
    window_path = tmp_path / "window.json"
    review_path = tmp_path / "review.json"
    _write_json(window_path, window)
    _write_json(review_path, _valid_g10_review())

    exit_code, result = _run_validator(window_path, review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "target.report_definition_id must match G10 review" in error
        for error in result["errors"]
    )


def test_g10_review_must_reference_same_g1_and_g2_g9_inputs(tmp_path, capsys):
    window = _valid_window()
    review = _valid_g10_review()
    review["references"]["g1_intake_file"] = "tmp/other-g1-intake.json"
    review["references"]["g2_g9_run_valid"] = False
    window_path = tmp_path / "window.json"
    review_path = tmp_path / "review.json"
    _write_json(window_path, window)
    _write_json(review_path, review)

    exit_code, result = _run_validator(window_path, review_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "G10 review references.g2_g9_run_valid must be true." in result["errors"]
    )
    assert (
        "references.g1_intake_file must match G10 review references.g1_intake_file."
        in result["errors"]
    )


def test_48_hour_window_requires_second_midpoint(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window(length_hours=48)
    _write_evidence_files(tmp_path, window)
    del window["checkpoints"]["midpoint_2"]
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "checkpoints.midpoint_2 must be an object" in error
        for error in result["errors"]
    )


def test_reset_occurred_blocks_g12(tmp_path, capsys):
    window = _valid_window()
    window["window"]["reset_occurred"] = True
    window["window"]["reset_reason"] = "PDF export failed at midpoint."
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "window.reset_occurred must be false" in error for error in result["errors"]
    )
    assert any(
        "window.reset_reason must be empty" in error for error in result["errors"]
    )


def test_window_timestamps_must_span_declared_length(tmp_path, capsys):
    window = _valid_window()
    window["window"]["end_timestamp"] = "2026-06-16T20:00:00-05:00"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "window.end_timestamp must be at least window.length_hours after start_timestamp."
        in result["errors"]
    )


def test_checkpoint_timestamps_must_be_ordered(tmp_path, capsys):
    window = _valid_window()
    window["checkpoints"]["midpoint_1"]["timestamp"] = "2026-06-16T08:00:00-05:00"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "checkpoints.midpoint_1.timestamp must be on or after the previous checkpoint."
        in result["errors"]
    )


def test_checkpoint_timestamp_must_be_iso8601(tmp_path, capsys):
    window = _valid_window()
    window["checkpoints"]["start"]["timestamp"] = "June 16 2026"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "checkpoints.start.timestamp must be an ISO-8601 timestamp." in result["errors"]
    )


def test_export_hash_mismatch_or_empty_artifact_fails(tmp_path, capsys):
    window = _valid_window()
    window["export_reproducibility"]["pdf"]["byte_count"] = 0
    window["export_reproducibility"]["png"]["snapshot_preview_hash"] = "different"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "export_reproducibility.pdf.byte_count must be greater than zero" in error
        for error in result["errors"]
    )
    assert any(
        "export_reproducibility.png.preview_hash must match" in error
        for error in result["errors"]
    )


def test_sensitive_values_are_rejected(tmp_path, capsys):
    window = _valid_window()
    window["reviewer_route"]["hannah"] = "hannah@example.com"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "Sensitive or user-level pattern detected" in error
        for error in result["errors"]
    )


def test_required_evidence_file_must_exist_under_evidence_root(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    window["evidence_files"]["start_checkpoint"] = "tmp/start-checkpoint.json"
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_files.start_checkpoint must be under docs/project/evidence/dashthis-replacement"
        in error
        for error in result["errors"]
    )


def test_48_hour_window_requires_second_midpoint_evidence_file(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window(length_hours=48)
    del window["evidence_files"]["midpoint_2_checkpoint"]
    _write_evidence_files(tmp_path, window)
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "evidence_files.midpoint_2_checkpoint is required." in result["errors"]


def test_text_evidence_file_sensitive_contents_are_rejected(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    (tmp_path / window["evidence_files"]["final_redaction_scan"]).write_text(
        "user_id appeared in the exported artifact\n",
        encoding="utf-8",
    )
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "Sensitive or user-level pattern detected in evidence_files.final_redaction_scan"
        in error
        for error in result["errors"]
    )


def test_final_evidence_validation_must_be_validation_json(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    window["evidence_files"]["final_evidence_validation"] = (
        f"{EVIDENCE_WINDOW_DIR}/final-evidence-validation.md"
    )
    (tmp_path / window["evidence_files"]["final_evidence_validation"]).write_text(
        "status: pass\n",
        encoding="utf-8",
    )
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_files.final_evidence_validation must point to slb_evidence_validation.v1 JSON"
        in error
        for error in result["errors"]
    )


def test_final_evidence_validation_must_have_no_blockers(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    final_path = tmp_path / window["evidence_files"]["final_evidence_validation"]
    payload = _final_evidence_validation_payload(window)
    payload.update(
        {
            "readiness_status": "blocked",
            "blocker_count": 1,
            "blockers": [
                {"code": "parity_results", "message": "Parity has unresolved rows."}
            ],
            "unresolved_parity": {
                "row_count": 1,
                "by_result": {"blocked_missing_source_value": 1},
                "by_dataset": {"content_ops": {"blocked_missing_source_value": 1}},
                "rows": [
                    {"dataset": "content_ops", "result": "blocked_missing_source_value"}
                ],
            },
            "source_value_inventory": {
                "missing_source_value_count": 1,
                "missing_source_values": [
                    {"dataset": "content_ops", "metric": "published_posts"}
                ],
                "unmatched_source_value_count": 0,
                "unmatched_source_values": [],
            },
            "parity_completion_requirements": {
                "ready_for_final_parity": False,
                "requirement_count": 1,
                "requirements": [
                    {"code": "approved_content_ops_source_totals_required"}
                ],
            },
        }
    )
    _write_json(final_path, payload)
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_files.final_evidence_validation.readiness_status must be pass or warning."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.blocker_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.unresolved_parity.row_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.parity_completion_requirements.ready_for_final_parity must be true."
        in result["errors"]
    )


def test_final_evidence_validation_blocks_missing_adinsights_parity(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    final_path = tmp_path / window["evidence_files"]["final_evidence_validation"]
    payload = _final_evidence_validation_payload(window)
    payload.update(
        {
            "readiness_status": "warning",
            "blocker_count": 0,
            "blockers": [],
            "unresolved_parity": {
                "row_count": 1,
                "by_result": {"blocked_missing_adinsights_value": 1},
                "by_dataset": {
                    "organic_facebook_page": {"blocked_missing_adinsights_value": 1}
                },
                "rows": [
                    {
                        "dataset": "organic_facebook_page",
                        "metric": "page_follows",
                        "result": "blocked_missing_adinsights_value",
                    }
                ],
            },
            "parity_completion_requirements": {
                "ready_for_final_parity": False,
                "requirement_count": 1,
                "requirements": [
                    {"code": "tenant_owned_slb_page_required_for_organic_import"}
                ],
            },
        }
    )
    _write_json(final_path, payload)
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_files.final_evidence_validation.unresolved_parity.row_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.unresolved_parity.rows must be empty."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.parity_completion_requirements.ready_for_final_parity must be true."
        in result["errors"]
    )


def test_final_evidence_validation_must_have_no_blocking_next_actions(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    final_path = tmp_path / window["evidence_files"]["final_evidence_validation"]
    payload = _final_evidence_validation_payload(window)
    payload["blocking_next_actions"] = {
        "action_count": 1,
        "ready_to_run_action_count": 0,
        "blocked_prerequisite_count": 1,
        "primary_next_action": "Select the tenant-owned SLB Facebook Page.",
        "actions": [
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
            }
        ],
    }
    _write_json(final_path, payload)
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_files.final_evidence_validation.blocking_next_actions.action_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.blocking_next_actions.blocked_prerequisite_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.blocking_next_actions.actions must be empty."
        in result["errors"]
    )


def test_final_evidence_validation_must_match_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    window = _valid_window()
    _write_evidence_files(tmp_path, window)
    final_path = tmp_path / window["evidence_files"]["final_evidence_validation"]
    payload = _final_evidence_validation_payload(window)
    payload["evidence"]["report"]["id"] = "different-report"
    payload["evidence"]["date_range"]["end_date"] = "2026-04-30"
    payload["evidence"]["parity_preview_hash"] = "different-preview-hash"
    _write_json(final_path, payload)
    window_path = tmp_path / "window.json"
    _write_json(window_path, window)

    exit_code, result = _run_validator(window_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_files.final_evidence_validation.evidence.report.id must match target.report_definition_id."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.evidence.date_range.end_date must match target.primary_end_date."
        in result["errors"]
    )
    assert (
        "evidence_files.final_evidence_validation.evidence.parity_preview_hash must match evidence.preview_hash."
        in result["errors"]
    )
