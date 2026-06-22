from __future__ import annotations

import json

import scripts.validate_slb_g2_g9_evidence_run as cli


TEMPLATE = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-g2-g9-fixed-range-evidence-run.template.json"
)
EVIDENCE_RUN_DIR = "docs/project/evidence/dashthis-replacement/runs/slb-20260616-op"


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_evidence_files(repo_root, run):
    for key, value in run["evidence_files"].items():
        if value == "not_in_scope":
            continue
        path = repo_root / value
        path.parent.mkdir(parents=True, exist_ok=True)
        if key == "evidence_validation":
            _write_json(
                path,
                {
                    "schema_version": "slb_evidence_validation.v1",
                    "evidence": {
                        "report": {"id": "42", "template_key": "slb_monthly_social_report"},
                        "date_range": {
                            "date_range": "custom",
                            "start_date": "2026-05-01",
                            "end_date": "2026-05-31",
                        },
                        "preview_hash": "preview-hash-1",
                        "parity_preview_hash": "preview-hash-1",
                    },
                    "readiness_status": "pass",
                    "blocker_count": 0,
                    "warning_count": 0,
                    "blockers": [],
                    "warnings": [],
                },
            )
        elif path.suffix == ".json":
            _write_json(path, {"schema_version": f"test_{key}.v1", "status": "pass"})
        elif path.suffix == ".png":
            path.write_bytes(b"\x89PNG\r\n\x1a\nnon-empty-test-png")
        else:
            path.write_text(f"{key}: pass\n", encoding="utf-8")


def _run_validator(run_path, intake_path, capsys):
    args = ["--run-file", str(run_path), "--format", "json"]
    if intake_path:
        args.extend(["--intake-file", str(intake_path)])
    exit_code = cli.main(args)
    return exit_code, json.loads(capsys.readouterr().out)


def _valid_intake():
    return {
        "schema_version": "slb_g1_runtime_target_intake.v1",
        "status": "candidate_ready_for_review",
        "g0_clearance": {
            "raj_decision": "approved",
            "mira_decision": "approved",
            "can_proceed_to_g1_g11": "approved",
            "conditions": "Use fixed-range evidence only.",
        },
        "target": {
            "environment": "staging",
            "backend_url": "https://backend.example.invalid",
            "frontend_url": "https://frontend.example.invalid",
            "safe_tenant_identifier": "tenant-slb-safe",
            "safe_client_identifier": "SLB / Students' Loan Bureau",
            "report_definition_id": "42",
            "template_key": "slb_monthly_social_report",
            "report_schema_version": "report.v1",
            "primary_start_date": "2026-05-01",
            "primary_end_date": "2026-05-31",
            "timezone": "America/Jamaica",
            "currency": "JMD",
            "paid_meta_account_scope": "safe-paid-meta-account",
            "organic_facebook_page_scope": "safe-page",
            "content_ops_workspace_scope": "safe-content-workspace",
        },
        "comparison": {
            "dashthis_source_comparison_owner": "Andre",
            "dashthis_source_evidence_location": "redacted-internal-sheet",
            "tolerances_confirmed": True,
        },
        "delivery": {
            "scheduled_delivery_mode": "dry_run_only",
            "recipient_assumption": "redacted recipient group",
            "dashthis_active": True,
        },
        "guardrails": {
            "instagram_decision": "deferred_in_v1",
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
        "evidence": {
            "slb_report_target_intake_output": "tmp/target-intake.json",
            "operator_notes": "Ready for fixed-range run.",
        },
    }


def _valid_run():
    export_row = {
        "job_id": "job-1",
        "status": "completed",
        "byte_count": 2048,
        "preview_hash": "preview-hash-1",
        "snapshot_preview_hash": "preview-hash-1",
    }
    dataset_row = {
        "status": "fresh",
        "row_count": 31,
        "covered_start_date": "2026-05-01",
        "covered_end_date": "2026-05-31",
        "reviewer": "Andre",
    }
    return {
        "schema_version": "slb_g2_g9_evidence_run.v1",
        "status": "ready_for_g10_review",
        "references": {
            "g1_intake_file": "tmp/g1-intake.json",
            "g0_can_proceed": True,
            "evidence_run_id": "slb-20260616-op",
            "run_timestamp": "2026-06-16T20:30:00-05:00",
            "operator": "operator",
        },
        "target": {
            "environment": "staging",
            "backend_url": "https://backend.example.invalid",
            "frontend_url": "https://frontend.example.invalid",
            "safe_tenant_identifier": "tenant-slb-safe",
            "safe_client_identifier": "SLB / Students' Loan Bureau",
            "report_definition_id": "42",
            "template_key": "slb_monthly_social_report",
            "report_schema_version": "report.v1",
            "primary_start_date": "2026-05-01",
            "primary_end_date": "2026-05-31",
            "timezone": "America/Jamaica",
        },
        "guardrails": {
            "instagram_deferred": True,
            "dashthis_active": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
        "evidence_files": {
            "preview": f"{EVIDENCE_RUN_DIR}/preview.json",
            "diagnostics": f"{EVIDENCE_RUN_DIR}/diagnostics.json",
            "history_probe": f"{EVIDENCE_RUN_DIR}/history-probe.json",
            "evidence_bundle": f"{EVIDENCE_RUN_DIR}/evidence-bundle.json",
            "evidence_validation": f"{EVIDENCE_RUN_DIR}/evidence-validation.json",
            "parity_output": f"{EVIDENCE_RUN_DIR}/parity.md",
            "parity_comparison": f"{EVIDENCE_RUN_DIR}/parity-comparison.csv",
            "report_ui_screenshot": f"{EVIDENCE_RUN_DIR}/report-ui.png",
            "dashboard_ui_screenshot": "not_in_scope",
            "scheduled_dry_run": f"{EVIDENCE_RUN_DIR}/scheduled-dry-run.json",
            "redaction_scan": f"{EVIDENCE_RUN_DIR}/redaction-scan.txt",
            "gate_output": f"{EVIDENCE_RUN_DIR}/gates.txt",
        },
        "coverage": {
            "datasets": {
                "paid_meta_ads": dict(dataset_row),
                "organic_facebook_page": dict(dataset_row),
                "content_ops": dict(dataset_row),
            },
            "monthly_and_90_day_history_proven": True,
        },
        "rendering": {
            "report_v1_pages_rendered": True,
            "dashboard_v1_rendered_or_not_in_scope": True,
            "required_sections_present": {
                "cover": True,
                "executive_summary": True,
                "paid_meta_ads": True,
                "organic_facebook_page": True,
                "top_posts": True,
                "content_ops": True,
                "recommendations": True,
                "appendix_data_notes": True,
            },
            "coverage_notes_visible": True,
        },
        "exports": {
            "csv": dict(export_row),
            "pdf": {**export_row, "job_id": "job-2"},
            "png": {**export_row, "job_id": "job-3"},
        },
        "parity": {
            "comparison_values_attached": True,
            "result_counts": {"pass": 12, "fail": 0, "blocked": 0},
            "non_pass_rows_resolved": True,
            "reviewer": "Andre",
        },
        "delivery": {
            "scheduled_dry_run_status": "rendered",
            "delivery_mode": "dry_run",
            "no_client_email_sent": True,
            "sanitized_status_recorded": True,
        },
        "safety": {
            "diagnostics_support_proof_captured": True,
            "permissions_matrix_passed": True,
            "tenant_isolation_passed": True,
            "audit_events_verified": True,
            "quota_controls_verified": True,
            "aggregate_only_verified": True,
            "redaction_scan_passed": True,
        },
        "gates": {
            "backend_lint": "pass",
            "backend_test": "pass",
            "frontend_guardrails": "pass",
            "frontend_lint": "pass",
            "frontend_test": "pass",
            "frontend_build": "pass",
            "dev_healthcheck": "pass",
            "adinsights_preflight_status": "GATE_BLOCK",
            "adinsights_preflight_block_accepted_by_g0": True,
        },
        "reviewer_route": {
            "sofia": "approved",
            "andre": "approved",
            "lina_or_joel": "approved",
            "omar_or_hannah": "approved",
            "nina_if_sensitive": "not_required",
            "raj_mira": "approved",
        },
    }


def test_valid_g2_g9_evidence_run_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    _write_evidence_files(tmp_path, run)
    run_path = tmp_path / "run.json"
    intake_path = tmp_path / "intake.json"
    _write_json(run_path, run)
    _write_json(intake_path, _valid_intake())

    exit_code, result = _run_validator(run_path, intake_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_template_pending_values_fail(tmp_path, capsys):
    run_path = tmp_path / "run.json"
    run_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status must be ready_for_g10_review" in error for error in result["errors"])
    assert any("references.g0_can_proceed must be true" in error for error in result["errors"])


def test_target_must_match_g1_intake(tmp_path, capsys):
    run = _valid_run()
    intake = _valid_intake()
    run["target"]["report_definition_id"] = "99"
    run_path = tmp_path / "run.json"
    intake_path = tmp_path / "intake.json"
    _write_json(run_path, run)
    _write_json(intake_path, intake)

    exit_code, result = _run_validator(run_path, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("target.report_definition_id must match G1 intake" in error for error in result["errors"])


def test_export_snapshot_hash_must_match(tmp_path, capsys):
    run = _valid_run()
    run["exports"]["pdf"]["snapshot_preview_hash"] = "different"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("exports.pdf preview_hash must match snapshot_preview_hash" in error for error in result["errors"])


def test_stale_coverage_requires_reviewer_note(tmp_path, capsys):
    run = _valid_run()
    run["coverage"]["datasets"]["paid_meta_ads"]["status"] = "stale"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("coverage.datasets.paid_meta_ads.reviewer_note is required" in error for error in result["errors"])
    assert any("paid_meta_ads.status needs explicit reviewer note" in warning for warning in result["warnings"])


def test_full_range_coverage_must_cover_target_dates(tmp_path, capsys):
    run = _valid_run()
    run["coverage"]["datasets"]["organic_facebook_page"]["covered_start_date"] = "2026-05-02"
    run["coverage"]["datasets"]["organic_facebook_page"]["covered_end_date"] = "2026-05-30"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("organic_facebook_page.covered_start_date must cover the target start date" in error for error in result["errors"])
    assert any("organic_facebook_page.covered_end_date must cover the target end date" in error for error in result["errors"])


def test_coverage_dates_must_be_valid_and_ordered(tmp_path, capsys):
    run = _valid_run()
    run["coverage"]["datasets"]["content_ops"]["covered_start_date"] = "2026-05-31"
    run["coverage"]["datasets"]["content_ops"]["covered_end_date"] = "2026-05-01"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "coverage.datasets.content_ops.covered_start_date must be on or before covered_end_date." in result["errors"]


def test_parity_non_pass_rows_block_g10(tmp_path, capsys):
    run = _valid_run()
    run["parity"]["result_counts"]["blocked"] = 1
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("parity.result_counts.blocked must be zero before G10" in error for error in result["errors"])


def test_offline_evidence_validation_must_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    _write_evidence_files(tmp_path, run)
    (tmp_path / run["evidence_files"]["evidence_validation"]).write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_validation.v1",
                "readiness_status": "blocked",
                "blocker_count": 2,
                "blockers": [{"code": "parity_results"}],
            }
        ),
        encoding="utf-8",
    )
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "evidence_files.evidence_validation readiness_status must be pass." in result["errors"]
    assert "evidence_files.evidence_validation blocker_count must be zero." in result["errors"]


def test_offline_evidence_validation_identity_must_match_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    _write_evidence_files(tmp_path, run)
    (tmp_path / run["evidence_files"]["evidence_validation"]).write_text(
        json.dumps(
            {
                "schema_version": "slb_evidence_validation.v1",
                "evidence": {
                    "report": {"id": "wrong-report", "template_key": "wrong_template"},
                    "date_range": {
                        "date_range": "custom",
                        "start_date": "2026-04-01",
                        "end_date": "2026-04-30",
                    },
                    "preview_hash": "preview-hash-1",
                    "parity_preview_hash": "different-preview-hash",
                },
                "readiness_status": "pass",
                "blocker_count": 0,
            }
        ),
        encoding="utf-8",
    )
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "evidence_files.evidence_validation report.id must match target.report_definition_id." in result["errors"]
    assert "evidence_files.evidence_validation report.template_key must match target.template_key." in result["errors"]
    assert "evidence_files.evidence_validation start_date must match target.primary_start_date." in result["errors"]
    assert "evidence_files.evidence_validation end_date must match target.primary_end_date." in result["errors"]
    assert "evidence_files.evidence_validation preview_hash must match parity_preview_hash." in result["errors"]


def test_sensitive_values_are_rejected(tmp_path, capsys):
    run = _valid_run()
    run["evidence_files"]["preview"] = "sent-to-reviewer@example.com"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected" in error for error in result["errors"])


def test_evidence_file_must_exist_under_evidence_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    run["evidence_files"]["preview"] = "tmp/preview.json"
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("evidence_files.preview must be under docs/project/evidence/dashthis-replacement" in error for error in result["errors"])


def test_evidence_file_must_use_expected_suffix(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    run["evidence_files"]["report_ui_screenshot"] = f"{EVIDENCE_RUN_DIR}/report-ui.txt"
    _write_evidence_files(tmp_path, run)
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("evidence_files.report_ui_screenshot must use one of" in error for error in result["errors"])


def test_text_evidence_file_sensitive_contents_are_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    run = _valid_run()
    _write_evidence_files(tmp_path, run)
    (tmp_path / run["evidence_files"]["diagnostics"]).write_text(
        json.dumps({"status": "pass", "user_id": "should-not-appear"}),
        encoding="utf-8",
    )
    run_path = tmp_path / "run.json"
    _write_json(run_path, run)

    exit_code, result = _run_validator(run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in evidence_files.diagnostics" in error for error in result["errors"])
