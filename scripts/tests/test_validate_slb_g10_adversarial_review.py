from __future__ import annotations

import json

import scripts.validate_slb_g10_adversarial_review as cli


TEMPLATE = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "2026-06-16-g10-adversarial-review.template.json"
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_attack_evidence_files(repo_root, review):
    for row in review["attack_reviews"].values():
        path = repo_root / row["evidence"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            _write_json(path, {"schema_version": "test_g10_evidence.v1", "status": "pass"})
        else:
            path.write_text("status: pass\n", encoding="utf-8")


def _write_g2_g9_evidence_validation(repo_root, run):
    path = repo_root / run["evidence_files"]["evidence_validation"]
    path.parent.mkdir(parents=True, exist_ok=True)
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
        },
    )


def _run_validator(review_path, run_path, intake_path, capsys):
    args = ["--review-file", str(review_path), "--format", "json"]
    if run_path:
        args.extend(["--g2-g9-run-file", str(run_path)])
    if intake_path:
        args.extend(["--intake-file", str(intake_path)])
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


def _valid_g2_g9_run():
    return {
        "schema_version": "slb_g2_g9_evidence_run.v1",
        "status": "ready_for_g10_review",
        "references": {"g0_can_proceed": True, "g1_intake_file": "tmp/g1-intake.json"},
        "target": _target(),
        "evidence_files": {
            "evidence_validation": "docs/project/evidence/dashthis-replacement/runs/slb-g2-g9-20260616-op/evidence-validation.json"
        },
    }


def _valid_intake():
    return {
        "schema_version": "slb_g1_runtime_target_intake.v1",
        "status": "candidate_ready_for_review",
        "g0_clearance": {
            "raj_decision": "approved",
            "mira_decision": "approved",
            "can_proceed_to_g1_g11": "approved",
        },
        "target": _target(),
        "comparison": {"tolerances_confirmed": True},
        "delivery": {"scheduled_delivery_mode": "dry_run_only", "dashthis_active": True},
        "guardrails": {
            "instagram_decision": "deferred_in_v1",
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
    }


def _valid_review():
    attack_reviews = {}
    for attack in cli.REQUIRED_ATTACKS:
        attack_reviews[attack] = {
            "outcome": "pass",
            "severity": "medium",
            "evidence": f"docs/project/evidence/dashthis-replacement/runs/slb-g10-20260616-op/{attack}.md",
            "resolution": f"closed {attack}",
            "reviewer": "Raj",
        }
    attack_reviews["rollback_gap"]["outcome"] = "fixed"
    attack_reviews["rollback_gap"]["severity"] = "high"
    return {
        "schema_version": "slb_g10_adversarial_review.v1",
        "status": "ready_for_g11_hardening",
        "references": {
            "g1_intake_file": "tmp/g1-intake.json",
            "g1_intake_valid": True,
            "g2_g9_run_file": "tmp/g2-g9-run.json",
            "g2_g9_run_valid": True,
            "review_id": "slb-g10-20260616-op",
            "review_timestamp": "2026-06-16T21:00:00-05:00",
            "operator": "operator",
        },
        "target": _target(),
        "guardrails": {
            "instagram_deferred": True,
            "dashthis_active": True,
            "stored_aggregate_only": True,
            "no_live_provider_calls_at_render_export_time": True,
        },
        "attack_reviews": attack_reviews,
        "final_checks": {
            "all_attack_reviews_closed": True,
            "no_unresolved_blocker_or_high": True,
            "no_unsupported_instagram_claim": True,
            "no_hidden_stale_partial_missing_history": True,
            "no_user_level_secret_or_raw_provider_data": True,
            "rollback_path_confirmed": True,
            "dashthis_still_active": True,
            "raj_mira_acceptance": True,
        },
        "reviewer_route": {
            "raj": "approved",
            "mira": "approved",
            "sofia": "approved",
            "andre": "approved",
            "lina_or_joel": "approved",
            "omar_or_hannah": "approved",
            "nina_if_sensitive": "not_required",
        },
    }


def _write_valid_g2_g9_run(repo_root, run_path):
    run = _valid_g2_g9_run()
    _write_g2_g9_evidence_validation(repo_root, run)
    _write_json(run_path, run)
    return run


def _write_valid_intake(intake_path):
    intake = _valid_intake()
    _write_json(intake_path, intake)
    return intake


def test_valid_g10_adversarial_review_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    _write_json(review_path, review)
    _write_valid_g2_g9_run(tmp_path, run_path)
    intake_path = tmp_path / "intake.json"
    _write_valid_intake(intake_path)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert result["errors"] == []


def test_g10_requires_g1_intake_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    _write_json(review_path, review)
    _write_valid_g2_g9_run(tmp_path, run_path)

    exit_code, result = _run_validator(review_path, run_path, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G10 validation requires --intake-file with a filled G1 runtime target intake." in result["errors"]


def test_g10_requires_g2_g9_run_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    intake_path = tmp_path / "intake.json"
    _write_json(review_path, review)
    _write_valid_intake(intake_path)

    exit_code, result = _run_validator(review_path, None, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G10 validation requires --g2-g9-run-file with a filled G2-G9 evidence run." in result["errors"]


def test_g10_rejects_pending_g1_intake(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    intake_path = tmp_path / "intake.json"
    _write_json(review_path, review)
    _write_valid_g2_g9_run(tmp_path, run_path)
    intake = _valid_intake()
    intake["status"] = "pending_operator_input"
    _write_json(intake_path, intake)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert (
        "G1 intake status must be candidate_ready_for_review before G10 adversarial review can pass."
        in result["errors"]
    )


def test_target_must_match_g1_intake(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    intake_path = tmp_path / "intake.json"
    intake = _valid_intake()
    intake["target"]["report_definition_id"] = "99"
    _write_json(review_path, review)
    _write_valid_g2_g9_run(tmp_path, run_path)
    _write_json(intake_path, intake)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("target.report_definition_id must match G1 intake target.report_definition_id" in error for error in result["errors"])


def test_template_pending_values_fail(tmp_path, capsys):
    review_path = tmp_path / "review.json"
    review_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("status must be ready_for_g11_hardening" in error for error in result["errors"])
    assert any("references.g2_g9_run_valid must be true" in error for error in result["errors"])


def test_target_must_match_g2_g9_run(tmp_path, capsys):
    review = _valid_review()
    review["target"]["report_definition_id"] = "99"
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    _write_json(review_path, review)
    _write_valid_g2_g9_run(tmp_path, run_path)
    intake_path = tmp_path / "intake.json"
    _write_valid_intake(intake_path)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("target.report_definition_id must match G2-G9 run" in error for error in result["errors"])


def test_g10_requires_g2_g9_evidence_validation_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    run = _write_valid_g2_g9_run(tmp_path, run_path)
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
    _write_json(review_path, review)
    intake_path = tmp_path / "intake.json"
    _write_valid_intake(intake_path)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G2-G9 evidence validation report.id must match target.report_definition_id." in result["errors"]
    assert "G2-G9 evidence validation report.template_key must match target.template_key." in result["errors"]
    assert "G2-G9 evidence validation start_date must match target.primary_start_date." in result["errors"]
    assert "G2-G9 evidence validation end_date must match target.primary_end_date." in result["errors"]
    assert "G2-G9 evidence validation preview_hash must match parity_preview_hash." in result["errors"]


def test_open_attack_review_blocks_g11(tmp_path, capsys):
    review = _valid_review()
    review["attack_reviews"]["missing_history"]["outcome"] = "open"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("attack_reviews.missing_history.outcome must be closed before G11" in error for error in result["errors"])


def test_high_or_blocker_severity_requires_resolution_outcome(tmp_path, capsys):
    review = _valid_review()
    review["attack_reviews"]["tenant_scope"]["severity"] = "blocker"
    review["attack_reviews"]["tenant_scope"]["outcome"] = "pass"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("attack_reviews.tenant_scope severity blocker requires outcome" in error for error in result["errors"])


def test_accepted_risk_requires_structured_approval(tmp_path, capsys):
    review = _valid_review()
    review["attack_reviews"]["partial_coverage"]["outcome"] = "accepted_risk"
    review["attack_reviews"]["partial_coverage"]["severity"] = "high"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("attack_reviews.partial_coverage.approval must be an object" in error for error in result["errors"])


def test_waived_risk_requires_raj_and_mira_approval(tmp_path, capsys):
    review = _valid_review()
    review["attack_reviews"]["artifact_safety"]["outcome"] = "waived"
    review["attack_reviews"]["artifact_safety"]["severity"] = "high"
    review["attack_reviews"]["artifact_safety"]["approval"] = {
        "risk_owner": "Omar",
        "accepted_by": ["Raj"],
        "expires_or_review_by": "2026-06-30",
        "rationale": "Temporary waiver until artifact-store control lands.",
    }
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("attack_reviews.artifact_safety.approval.accepted_by must include Raj and Mira" in error for error in result["errors"])


def test_accepted_risk_with_approval_passes_with_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    review["attack_reviews"]["source_disconnected"]["outcome"] = "accepted_risk"
    review["attack_reviews"]["source_disconnected"]["severity"] = "high"
    review["attack_reviews"]["source_disconnected"]["approval"] = {
        "risk_owner": "Omar",
        "accepted_by": ["Raj", "Mira"],
        "expires_or_review_by": "2026-06-30",
        "rationale": "Accepted only for fixed range with stored history and visible notes.",
    }
    _write_attack_evidence_files(tmp_path, review)
    review_path = tmp_path / "review.json"
    run_path = tmp_path / "g2-g9-run.json"
    _write_json(review_path, review)
    intake_path = tmp_path / "intake.json"
    _write_valid_g2_g9_run(tmp_path, run_path)
    _write_valid_intake(intake_path)

    exit_code, result = _run_validator(review_path, run_path, intake_path, capsys)

    assert exit_code == 0
    assert result["valid"] is True
    assert any("source_disconnected has accepted_risk" in warning for warning in result["warnings"])


def test_sensitive_values_are_rejected(tmp_path, capsys):
    review = _valid_review()
    review["attack_reviews"]["user_level_data"]["evidence"] = "reviewer@example.com"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected" in error for error in result["errors"])


def test_attack_evidence_must_exist_under_evidence_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    review["attack_reviews"]["tenant_scope"]["evidence"] = "tmp/tenant-scope.md"
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("attack_reviews.tenant_scope.evidence must be under docs/project/evidence/dashthis-replacement" in error for error in result["errors"])


def test_attack_evidence_sensitive_contents_are_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    review = _valid_review()
    _write_attack_evidence_files(tmp_path, review)
    (tmp_path / review["attack_reviews"]["user_level_data"]["evidence"]).write_text(
        "found user_id in artifact\n",
        encoding="utf-8",
    )
    review_path = tmp_path / "review.json"
    _write_json(review_path, review)

    exit_code, result = _run_validator(review_path, None, None, capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any("Sensitive or user-level pattern detected in attack_reviews.user_level_data.evidence" in error for error in result["errors"])
