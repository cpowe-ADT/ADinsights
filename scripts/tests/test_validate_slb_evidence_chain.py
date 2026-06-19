from __future__ import annotations

import json

import scripts.validate_slb_evidence_chain as cli


EXAMPLES_ROOT = (
    cli.REPO_ROOT
    / "docs"
    / "project"
    / "evidence"
    / "dashthis-replacement"
    / "examples"
)


def _run_validator(args, capsys):
    exit_code = cli.main([*args, "--format", "json"])
    return exit_code, json.loads(capsys.readouterr().out)


def test_valid_g0_g1_example_chain_passes(capsys):
    exit_code, result = _run_validator(
        [
            "--g0-review-file",
            str(EXAMPLES_ROOT / "g0-raj-mira-review-decision.valid-example.json"),
            "--g1-intake-file",
            str(EXAMPLES_ROOT / "g1-runtime-target-intake.valid-example.json"),
        ],
        capsys,
    )

    assert exit_code == 0
    assert result["valid"] is True
    assert [step["name"] for step in result["steps"]] == ["g0_review", "g1_intake", "g0_g1_handoff"]


def test_chain_requires_at_least_one_artifact(capsys):
    exit_code, result = _run_validator([], capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "At least one evidence artifact path is required." in result["errors"]


def test_chain_rejects_downstream_without_upstream(capsys, tmp_path):
    g10_path = tmp_path / "g10.json"
    g10_path.write_text(json.dumps({"schema_version": "slb_g10_adversarial_review.v1"}), encoding="utf-8")

    exit_code, result = _run_validator(["--g10-review-file", str(g10_path)], capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert "G10 validation requires --g2-g9-run-file." in result["errors"]
    assert "g10_review has a missing required upstream argument." in result["errors"]


def test_chain_prefixes_underlying_validator_errors(capsys, tmp_path):
    g0_path = tmp_path / "g0.json"
    g0_path.write_text(json.dumps({"schema_version": "slb_g0_raj_mira_review.v1"}), encoding="utf-8")

    exit_code, result = _run_validator(["--g0-review-file", str(g0_path)], capsys)

    assert exit_code == 1
    assert result["valid"] is False
    assert any(error.startswith("g0_review:") for error in result["errors"])
    assert "g0_review failed with exit code 1." in result["errors"]
