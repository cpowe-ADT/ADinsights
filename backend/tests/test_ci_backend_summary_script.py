from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

def _write_junit(path: Path) -> None:
    path.write_text(
        (
            '<testsuite name="backend" tests="3" errors="0" failures="0" '
            'skipped="1" time="1.50" timestamp="2026-03-06T10:00:00+00:00"></testsuite>'
        ),
        encoding="utf-8",
    )


def _write_coverage(path: Path) -> None:
    path.write_text(
        '<coverage lines-valid="10" lines-covered="8" line-rate="0.8" timestamp="12345"></coverage>',
        encoding="utf-8",
    )


def _run_backend_summary(
    *,
    workdir: Path,
    junit_path: Path,
    coverage_path: Path,
    summary_path: Path,
    metrics_path: Path,
    release_smoke_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "ci" / "backend-summary.py"
    command = [
        sys.executable,
        str(script_path),
        "--junit",
        str(junit_path),
        "--coverage",
        str(coverage_path),
        "--json-output",
        str(summary_path),
        "--csv-output",
        str(metrics_path),
    ]
    if release_smoke_path is not None:
        command.extend(["--release-smoke", str(release_smoke_path)])
    return subprocess.run(
        command,
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )


def test_backend_summary_script_includes_release_smoke_success(tmp_path):
    junit_path = tmp_path / "junit.xml"
    coverage_path = tmp_path / "coverage.xml"
    release_smoke_path = tmp_path / "release-smoke.json"
    summary_path = tmp_path / "backend-ci-summary.json"
    metrics_path = tmp_path / "ci-metrics.csv"

    _write_junit(junit_path)
    _write_coverage(coverage_path)
    release_smoke_path.write_text(
        json.dumps(
            {
                "ok": True,
                "strict_external": False,
                "strict_observability": True,
                "missing_metrics": [],
                "missing_metric_labels": [],
                "unknown_retry_share": 0.0,
                "max_unknown_retry_share": 0.1,
                "unknown_retry_reason_labels": ["unknown", "airbyte_unknown_error"],
                "unknown_retry_count": 0.0,
                "retry_total": 2.0,
                "checks": [],
            }
        ),
        encoding="utf-8",
    )

    result = _run_backend_summary(
        workdir=tmp_path,
        junit_path=junit_path,
        coverage_path=coverage_path,
        summary_path=summary_path,
        metrics_path=metrics_path,
        release_smoke_path=release_smoke_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["release_smoke"]["ok"] is True
    assert payload["inputs"]["release_smoke_json"] == str(release_smoke_path)
    assert payload["release_smoke"]["unknown_retry_reason_labels"] == [
        "unknown",
        "airbyte_unknown_error",
    ]
    metrics_text = metrics_path.read_text(encoding="utf-8")
    assert "release_smoke,status,1,bool" in metrics_text
    assert "release_smoke,unknown_retry_share,0.0,ratio" in metrics_text
    assert "release_smoke,unknown_retry_count,0.0,count" in metrics_text


def test_backend_summary_script_fails_when_release_smoke_fails(tmp_path):
    junit_path = tmp_path / "junit.xml"
    coverage_path = tmp_path / "coverage.xml"
    release_smoke_path = tmp_path / "release-smoke.json"
    summary_path = tmp_path / "backend-ci-summary.json"
    metrics_path = tmp_path / "ci-metrics.csv"

    _write_junit(junit_path)
    _write_coverage(coverage_path)
    release_smoke_path.write_text(
        json.dumps(
            {
                "ok": False,
                "strict_external": False,
                "strict_observability": True,
                "missing_metrics": ["celery_task_retries_total"],
                "missing_metric_labels": [{"metric_name": "celery_task_queue_starts_total"}],
                "unknown_retry_share": 0.4,
                "max_unknown_retry_share": 0.1,
                "unknown_retry_reason_labels": ["unknown", "airbyte_unknown_error"],
                "unknown_retry_count": 4.0,
                "retry_total": 10.0,
                "checks": [],
            }
        ),
        encoding="utf-8",
    )

    result = _run_backend_summary(
        workdir=tmp_path,
        junit_path=junit_path,
        coverage_path=coverage_path,
        summary_path=summary_path,
        metrics_path=metrics_path,
        release_smoke_path=release_smoke_path,
    )

    assert result.returncode == 1
    assert "Release smoke report indicates failure." in result.stderr
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["release_smoke"]["ok"] is False
    assert payload["release_smoke"]["unknown_retry_count"] == 4.0
    metrics_text = metrics_path.read_text(encoding="utf-8")
    assert "release_smoke,status,0,bool" in metrics_text
    assert "release_smoke,unknown_retry_count,4.0,count" in metrics_text
