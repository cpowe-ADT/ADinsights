#!/usr/bin/env python3
"""Validate the filled SLB cancellation-readiness evidence chain in order."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_slb_cancellation_readiness_status as status_validator
from scripts import validate_slb_g0_g1_handoff as g0_g1_validator
from scripts import validate_slb_g0_raj_mira_review as g0_validator
from scripts import validate_slb_g1_runtime_target_intake as g1_validator
from scripts import validate_slb_g2_g9_evidence_run as g2_g9_validator
from scripts import validate_slb_g10_adversarial_review as g10_validator
from scripts import validate_slb_g11_hardening_window as g11_validator
from scripts import validate_slb_g12_final_recommendation as g12_validator


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a filled SLB DashThis cancellation evidence chain.")
    parser.add_argument("--status-manifest-file", help="Optional readiness status manifest.")
    parser.add_argument("--goal-doc", help="Optional human-readable goal controller.")
    parser.add_argument("--blocker-register", help="Optional blocker register.")
    parser.add_argument("--g0-review-file", help="Filled G0 Raj/Mira review decision JSON.")
    parser.add_argument("--g1-intake-file", help="Filled G1 runtime target intake JSON.")
    parser.add_argument("--g2-g9-run-file", help="Filled G2-G9 evidence run JSON.")
    parser.add_argument("--g10-review-file", help="Filled G10 adversarial review JSON.")
    parser.add_argument("--g11-window-file", help="Filled G11 hardening window JSON.")
    parser.add_argument("--g12-recommendation-file", help="Filled G12 final recommendation JSON.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    warnings: list[str] = []
    results: list[dict[str, Any]] = []

    _validate_dependencies(args, errors)

    if args.status_manifest_file:
        status_args = ["--status-file", args.status_manifest_file, "--format", "json"]
        if args.goal_doc:
            status_args.extend(["--goal-doc", args.goal_doc])
        if args.blocker_register:
            status_args.extend(["--blocker-register", args.blocker_register])
        _run_step("status_manifest", status_validator.main, status_args, results, errors, warnings)

    if args.g0_review_file:
        _run_step(
            "g0_review",
            g0_validator.main,
            ["--review-file", args.g0_review_file, "--format", "json"],
            results,
            errors,
            warnings,
        )

    if args.g1_intake_file:
        _run_step(
            "g1_intake",
            g1_validator.main,
            ["--intake-file", args.g1_intake_file, "--format", "json"],
            results,
            errors,
            warnings,
        )

    if args.g0_review_file and args.g1_intake_file:
        _run_step(
            "g0_g1_handoff",
            g0_g1_validator.main,
            [
                "--g0-review-file",
                args.g0_review_file,
                "--g1-intake-file",
                args.g1_intake_file,
                "--format",
                "json",
            ],
            results,
            errors,
            warnings,
        )

    if args.g2_g9_run_file:
        _run_step(
            "g2_g9_run",
            g2_g9_validator.main,
            [
                "--run-file",
                args.g2_g9_run_file,
                "--intake-file",
                args.g1_intake_file or "",
                "--format",
                "json",
            ],
            results,
            errors,
            warnings,
        )

    if args.g10_review_file:
        _run_step(
            "g10_review",
            g10_validator.main,
            [
                "--review-file",
                args.g10_review_file,
                "--g2-g9-run-file",
                args.g2_g9_run_file or "",
                "--format",
                "json",
            ],
            results,
            errors,
            warnings,
        )

    if args.g11_window_file:
        _run_step(
            "g11_window",
            g11_validator.main,
            [
                "--window-file",
                args.g11_window_file,
                "--g10-review-file",
                args.g10_review_file or "",
                "--format",
                "json",
            ],
            results,
            errors,
            warnings,
        )

    if args.g12_recommendation_file:
        step_args = ["--recommendation-file", args.g12_recommendation_file, "--format", "json"]
        if args.status_manifest_file:
            step_args.extend(["--status-manifest-file", args.status_manifest_file])
        if args.g11_window_file:
            step_args.extend(["--g11-window-file", args.g11_window_file])
        _run_step("g12_recommendation", g12_validator.main, step_args, results, errors, warnings)

    payload = {
        "schema_version": "slb_evidence_chain_validation.v1",
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "steps": results,
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"SLB evidence chain valid: {str(payload['valid']).lower()}")
        print(f"Steps: {len(results)}")
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"- ERROR: {error}")
        print(f"Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"- WARNING: {warning}")
    return 1 if errors else 0


def _validate_dependencies(args: argparse.Namespace, errors: list[str]) -> None:
    if not any(
        [
            args.status_manifest_file,
            args.g0_review_file,
            args.g1_intake_file,
            args.g2_g9_run_file,
            args.g10_review_file,
            args.g11_window_file,
            args.g12_recommendation_file,
        ]
    ):
        errors.append("At least one evidence artifact path is required.")
    required_upstream = [
        ("g2_g9_run_file", "g1_intake_file", "G2-G9 validation requires --g1-intake-file."),
        ("g10_review_file", "g2_g9_run_file", "G10 validation requires --g2-g9-run-file."),
        ("g11_window_file", "g10_review_file", "G11 validation requires --g10-review-file."),
        ("g12_recommendation_file", "g11_window_file", "G12 validation requires --g11-window-file."),
        ("g12_recommendation_file", "status_manifest_file", "G12 validation requires --status-manifest-file."),
    ]
    for downstream, upstream, message in required_upstream:
        if getattr(args, downstream) and not getattr(args, upstream):
            errors.append(message)


def _run_step(
    name: str,
    runner: Callable[[list[str]], int],
    step_args: list[str],
    results: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    if "" in step_args:
        errors.append(f"{name} has a missing required upstream argument.")
        return
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = runner(step_args)
    output = stdout.getvalue()
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = {"raw_output": output.strip()}
        errors.append(f"{name} did not return JSON output.")
    step_errors = payload.get("errors") if isinstance(payload, dict) else None
    step_warnings = payload.get("warnings") if isinstance(payload, dict) else None
    if isinstance(step_errors, list):
        errors.extend([f"{name}: {error}" for error in step_errors])
    if isinstance(step_warnings, list):
        warnings.extend([f"{name}: {warning}" for warning in step_warnings])
    if exit_code != 0:
        errors.append(f"{name} failed with exit code {exit_code}.")
    results.append(
        {
            "name": name,
            "valid": exit_code == 0 and not step_errors,
            "exit_code": exit_code,
            "result": payload,
        }
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
