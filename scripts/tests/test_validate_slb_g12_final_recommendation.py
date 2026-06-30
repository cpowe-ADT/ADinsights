from __future__ import annotations

import json

import scripts.validate_slb_g12_final_recommendation as cli


TEMPLATE = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-g12-final-recommendation.template.json"
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _g6_parity_validation_payload(recommendation):
    target = recommendation["target"]
    return {
        "schema_version": "slb_evidence_validation.v1",
        "readiness_status": "pass",
        "blocker_count": 0,
        "warning_count": 0,
        "blockers": [],
        "warnings": [],
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


def _write_evidence_rollup_files(repo_root, recommendation):
    for goal_id, row in recommendation["evidence_rollup"].items():
        path = repo_root / row["evidence_link"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if goal_id == "G6":
            _write_json(path, _g6_parity_validation_payload(recommendation))
        elif path.suffix == ".json":
            _write_json(
                path, {"schema_version": "test_g12_evidence.v1", "status": "passed"}
            )
        else:
            path.write_text("status: passed\n", encoding="utf-8")


def _run_validator(recommendation_path, status_manifest_path, window_path, capsys):
    args = ["--recommendation-file", str(recommendation_path), "--format", "json"]
    if status_manifest_path:
        args.extend(["--status-manifest-file", str(status_manifest_path)])
    if window_path:
        args.extend(["--g11-window-file", str(window_path)])
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


def _valid_status_manifest():
    return {
        "schema_version": "slb_cancellation_readiness_status.v1",
        "sub_goals": [{"id": f"G{index}", "status": "passed"} for index in range(13)],
    }


def _valid_g11_window():
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
        },
        "target": _target(),
    }


def _valid_recommendation(recommendation="cancel_dashthis_recommended"):
    evidence_rollup = {}
    for index in range(12):
        goal_id = f"G{index}"
        evidence_rollup[goal_id] = {
            "status": "passed",
            "evidence_link": (
                "docs/project/evidence/dashthis-replacement/g6-parity-validation.json"
                if goal_id == "G6"
                else f"docs/project/evidence/dashthis-replacement/{goal_id.lower()}-proof.md"
            ),
            "reviewer_approval": "approved",
        }
    dashthis_action = (
        "cancel_after_acceptance"
        if recommendation == "cancel_dashthis_recommended"
        else "keep_active"
    )
    return {
        "schema_version": "slb_g12_final_recommendation.v1",
        "status": "final_decision_recorded",
        "references": {
            "status_manifest_file": "tmp/status.json",
            "status_manifest_valid": True,
            "g1_intake_file": "tmp/g1-intake.json",
            "g1_intake_valid": True,
            "g2_g9_run_file": "tmp/g2-g9-run.json",
            "g2_g9_run_valid": True,
            "g10_review_file": "tmp/g10-review.json",
            "g10_review_valid": True,
            "g11_window_file": "tmp/g11.json",
            "g11_window_valid": True,
            "decision_id": "slb-g12-20260616-final",
            "decision_timestamp": "2026-06-18T09:30:00-05:00",
            "operator": "operator",
        },
        "target": _target(),
        "guardrails": {
            "instagram_deferred": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
            "dashthis_active_until_decision": True,
        },
        "decision": {
            "recommendation": recommendation,
            "reason": "All required evidence passed and business owner accepted the decision.",
            "business_owner_acceptance": True,
            "dashthis_action": dashthis_action,
            "effective_date": "2026-06-20",
            "dashthis_cancellation_date": "2026-06-21"
            if recommendation == "cancel_dashthis_recommended"
            else "",
        },
        "evidence_rollup": evidence_rollup,
        "cancellation_scope": {
            "included_datasets": [
                "paid_meta_ads",
                "organic_facebook_page",
                "content_ops",
            ],
            "excluded_datasets": ["organic_instagram"],
            "render_source": "stored_aggregate_adinsights_data_only",
            "live_provider_calls_at_render_export_time": "forbidden",
            "official_fallback": "dashthis_active_until_cancellation_date"
            if recommendation == "cancel_dashthis_recommended"
            else "dashthis_active_until_decision",
        },
        "final_acceptance": {
            "g0_g11_passed": True,
            "fixed_target_locked": True,
            "all_required_sections_rendered": True,
            "csv_pdf_png_reproducible": True,
            "no_secrets_raw_user_data": True,
            "parity_complete": True,
            "scheduled_dry_run_safe": True,
            "diagnostics_support_ready": True,
            "safety_controls_passed": True,
            "adversarial_no_blocker": True,
            "hardening_completed_without_reset": True,
            "rollback_monitoring_documented": True,
        },
        "rollback_monitoring": {
            "support_owner": "Hannah",
            "escalation_owner": "Raj / Mira / Omar",
            "monitoring_owner": "Omar",
            "rollback_path": "Use DashThis until cancellation date and retained historical exports after.",
            "reversal_triggers": "Any blocker report failure reinstates fallback review.",
            "client_communication": "Business owner confirms final transition message.",
        },
        "reviewer_signoffs": {
            "raj": "approved",
            "mira": "approved",
            "sofia": "approved",
            "andre": "approved",
            "lina_or_joel": "approved",
            "omar": "approved",
            "hannah": "approved",
            "nina": "approved",
            "business_owner": "approved_cancel"
            if recommendation == "cancel_dashthis_recommended"
            else "approved_keep",
        },
        "decision_change_log": [
            {
                "timestamp": "2026-06-18T09:30:00-05:00",
                "recommendation": recommendation,
                "reason": "Final evidence review recorded.",
                "approver_or_owner": "Business owner",
            }
        ],
    }


def test_valid_g12_final_recommendation_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    recommendation_path = tmp_path / "recommendation.json"
    status_path = tmp_path / "status.json"
    window_path = tmp_path / "g11.json"
    _write_json(recommendation_path, recommendation)
    _write_json(status_path, _valid_status_manifest())
    _write_json(window_path, _valid_g11_window())

    exit_code, result = _run_validator(
        recommendation_path, status_path, window_path, capsys
    )

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_valid_no_cancel_recommendation_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation("cancel_dashthis_not_recommended")
    _write_evidence_rollup_files(tmp_path, recommendation)
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_template_pending_values_fail(tmp_path, capsys):
    recommendation_path = tmp_path / "recommendation.json"
    recommendation_path.write_text(
        TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8"
    )

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "status must be final_decision_recorded" in error for error in result["errors"]
    )
    assert any(
        "references.status_manifest_valid must be true" in error
        for error in result["errors"]
    )


def test_status_manifest_must_have_g0_g11_passed(tmp_path, capsys):
    recommendation_path = tmp_path / "recommendation.json"
    status_path = tmp_path / "status.json"
    status = _valid_status_manifest()
    status["sub_goals"][5]["status"] = "evidence_pending"
    _write_json(recommendation_path, _valid_recommendation())
    _write_json(status_path, status)

    exit_code, result = _run_validator(recommendation_path, status_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "Status manifest G5 must be passed before G12" in error
        for error in result["errors"]
    )


def test_target_must_match_g11_window(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["target"]["report_definition_id"] = "99"
    recommendation_path = tmp_path / "recommendation.json"
    window_path = tmp_path / "g11.json"
    _write_json(recommendation_path, recommendation)
    _write_json(window_path, _valid_g11_window())

    exit_code, result = _run_validator(recommendation_path, None, window_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "target.report_definition_id must match G11 window" in error
        for error in result["errors"]
    )


def test_g11_window_must_reference_same_upstream_inputs(tmp_path, capsys):
    recommendation = _valid_recommendation()
    window = _valid_g11_window()
    window["references"]["g2_g9_run_file"] = "tmp/other-g2-g9-run.json"
    window["references"]["g10_review_valid"] = False
    recommendation_path = tmp_path / "recommendation.json"
    window_path = tmp_path / "g11.json"
    _write_json(recommendation_path, recommendation)
    _write_json(window_path, window)

    exit_code, result = _run_validator(recommendation_path, None, window_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G11 window references.g10_review_valid must be true." in result["errors"]
    assert (
        "references.g2_g9_run_file must match G11 window references.g2_g9_run_file."
        in result["errors"]
    )


def test_cancel_recommendation_requires_business_owner_and_cancel_action(
    tmp_path, capsys
):
    recommendation = _valid_recommendation()
    recommendation["decision"]["business_owner_acceptance"] = False
    recommendation["decision"]["dashthis_action"] = "keep_active"
    recommendation["reviewer_signoffs"]["business_owner"] = "pending"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "decision.business_owner_acceptance must be true" in error
        for error in result["errors"]
    )
    assert any(
        "decision.dashthis_action must be cancel_after_acceptance" in error
        for error in result["errors"]
    )
    assert any(
        "reviewer_signoffs.business_owner is required" in error
        for error in result["errors"]
    )


def test_cancel_recommendation_requires_cancellation_date(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["decision"]["dashthis_cancellation_date"] = ""
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "decision.dashthis_cancellation_date is required." in result["errors"]


def test_cancel_date_must_not_precede_effective_date(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["decision"]["effective_date"] = "2026-06-20"
    recommendation["decision"]["dashthis_cancellation_date"] = "2026-06-19"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "decision.dashthis_cancellation_date must be on or after decision.effective_date."
        in result["errors"]
    )


def test_keep_recommendation_rejects_cancellation_date(tmp_path, capsys):
    recommendation = _valid_recommendation("cancel_dashthis_not_recommended")
    recommendation["decision"]["dashthis_cancellation_date"] = "2026-06-21"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "decision.dashthis_cancellation_date must be empty when cancellation is not recommended."
        in result["errors"]
    )


def test_unfinished_evidence_rollup_fails(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["evidence_rollup"]["G10"]["status"] = "pending"
    recommendation["final_acceptance"]["adversarial_no_blocker"] = False
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_rollup.G10.status must be passed" in error
        for error in result["errors"]
    )
    assert any(
        "final_acceptance.adversarial_no_blocker must be true" in error
        for error in result["errors"]
    )


def test_evidence_rollup_rejects_denied_or_pending_approval(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["evidence_rollup"]["G2"]["reviewer_approval"] = "denied"
    recommendation["evidence_rollup"]["G3"]["reviewer_approval"] = "review pending"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_rollup.G2.reviewer_approval must be an approved" in error
        for error in result["errors"]
    )
    assert any(
        "evidence_rollup.G3.reviewer_approval must be an approved" in error
        for error in result["errors"]
    )


def test_g6_evidence_rollup_requires_validation_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    recommendation["evidence_rollup"]["G6"]["evidence_link"] = (
        "docs/project/evidence/dashthis-replacement/g6-parity-proof.md"
    )
    (tmp_path / recommendation["evidence_rollup"]["G6"]["evidence_link"]).write_text(
        "status: passed\n",
        encoding="utf-8",
    )
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_rollup.G6.evidence_link must point to slb_evidence_validation.v1 JSON"
        in error
        for error in result["errors"]
    )


def test_g6_validation_json_must_have_no_parity_blockers(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    g6_path = tmp_path / recommendation["evidence_rollup"]["G6"]["evidence_link"]
    payload = _g6_parity_validation_payload(recommendation)
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
                "by_dataset": {"paid_meta_ads": {"blocked_missing_source_value": 1}},
                "rows": [
                    {
                        "dataset": "paid_meta_ads",
                        "result": "blocked_missing_source_value",
                    }
                ],
            },
            "source_value_inventory": {
                "missing_source_value_count": 1,
                "missing_source_values": [
                    {"dataset": "paid_meta_ads", "metric": "spend"}
                ],
                "unmatched_source_value_count": 0,
                "unmatched_source_values": [],
            },
            "parity_completion_requirements": {
                "ready_for_final_parity": False,
                "requirement_count": 1,
                "requirements": [
                    {"code": "approved_selected_account_paid_source_export_required"}
                ],
            },
        }
    )
    _write_json(g6_path, payload)
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_rollup.G6.evidence_link.readiness_status must be pass or warning."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.blocker_count must be 0." in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.unresolved_parity.row_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.parity_completion_requirements.ready_for_final_parity must be true."
        in result["errors"]
    )


def test_g6_validation_json_blocks_missing_adinsights_parity(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    g6_path = tmp_path / recommendation["evidence_rollup"]["G6"]["evidence_link"]
    payload = _g6_parity_validation_payload(recommendation)
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
    _write_json(g6_path, payload)
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_rollup.G6.evidence_link.unresolved_parity.row_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.unresolved_parity.rows must be empty."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.parity_completion_requirements.ready_for_final_parity must be true."
        in result["errors"]
    )


def test_g6_validation_json_must_have_no_blocking_next_actions(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    g6_path = tmp_path / recommendation["evidence_rollup"]["G6"]["evidence_link"]
    payload = _g6_parity_validation_payload(recommendation)
    payload["blocking_next_actions"] = {
        "action_count": 1,
        "ready_to_run_action_count": 0,
        "blocked_prerequisite_count": 1,
        "primary_next_action": "Provide an approved selected-account paid source export.",
        "actions": [
            {
                "code": "approved_selected_account_paid_source_export_required",
                "dataset": "paid_meta_ads",
            }
        ],
    }
    _write_json(g6_path, payload)
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_rollup.G6.evidence_link.blocking_next_actions.action_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.blocking_next_actions.blocked_prerequisite_count must be 0."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.blocking_next_actions.actions must be empty."
        in result["errors"]
    )


def test_g6_validation_json_must_match_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    g6_path = tmp_path / recommendation["evidence_rollup"]["G6"]["evidence_link"]
    payload = _g6_parity_validation_payload(recommendation)
    payload["evidence"]["report"]["id"] = "different-report"
    payload["evidence"]["date_range"]["start_date"] = "2026-04-01"
    payload["evidence"]["parity_preview_hash"] = "different-preview-hash"
    _write_json(g6_path, payload)
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "evidence_rollup.G6.evidence_link.evidence.report.id must match target.report_definition_id."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.evidence.date_range.start_date must match target.primary_start_date."
        in result["errors"]
    )
    assert (
        "evidence_rollup.G6.evidence_link.evidence.parity_preview_hash must match evidence.preview_hash."
        in result["errors"]
    )


def test_reviewer_signoffs_reject_denied_signoff(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["reviewer_signoffs"]["mira"] = "denied"
    recommendation["reviewer_signoffs"]["omar"] = "review_pending"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "reviewer_signoffs.mira must be an approved" in error
        for error in result["errors"]
    )
    assert any(
        "reviewer_signoffs.omar must be an approved" in error
        for error in result["errors"]
    )


def test_keep_recommendation_requires_business_owner_acceptance_value(tmp_path, capsys):
    recommendation = _valid_recommendation("cancel_dashthis_not_recommended")
    recommendation["reviewer_signoffs"]["business_owner"] = "denied"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "reviewer_signoffs.business_owner must approve or accept the final recommendation"
        in error
        for error in result["errors"]
    )


def test_sensitive_values_are_rejected(tmp_path, capsys):
    recommendation = _valid_recommendation()
    recommendation["rollback_monitoring"]["support_owner"] = "hannah@example.com"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "Sensitive or user-level pattern detected" in error
        for error in result["errors"]
    )


def test_evidence_rollup_link_must_exist_under_evidence_root(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    recommendation["evidence_rollup"]["G4"]["evidence_link"] = "tmp/g4-proof.md"
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "evidence_rollup.G4.evidence_link must be under docs/project/evidence/dashthis-replacement"
        in error
        for error in result["errors"]
    )


def test_evidence_rollup_link_sensitive_contents_are_rejected(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    recommendation = _valid_recommendation()
    _write_evidence_rollup_files(tmp_path, recommendation)
    (tmp_path / recommendation["evidence_rollup"]["G8"]["evidence_link"]).write_text(
        "diagnostics included user_id and should fail\n",
        encoding="utf-8",
    )
    recommendation_path = tmp_path / "recommendation.json"
    _write_json(recommendation_path, recommendation)

    exit_code, result = _run_validator(recommendation_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(
        "Sensitive or user-level pattern detected in evidence_rollup.G8.evidence_link"
        in error
        for error in result["errors"]
    )
