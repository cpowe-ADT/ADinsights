#!/usr/bin/env python3
"""Generate backend CI summary and timing metrics.

The script consumes the pytest JUnit XML report and the coverage.py XML
report produced in CI. It emits two artifacts in the working directory:

* ``backend-ci-summary.json`` – structured metadata about the test run
  including status, counts, timing, and coverage ratios.
* ``ci-metrics.csv`` – tabular metrics that downstream observability jobs
  can ingest for SLO calculations.

Both outputs are deterministic and stable, enabling lightweight ingestion
pipelines in BigQuery or other metrics stores.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional
import xml.etree.ElementTree as ET


@dataclass
class SuiteResult:
    """Container for aggregated information about a test suite."""

    name: str
    tests: int
    errors: int
    failures: int
    skipped: int
    duration: float
    timestamp: Optional[str] = None

    @property
    def passed(self) -> int:
        value = self.tests - (self.errors + self.failures + self.skipped)
        return value if value >= 0 else 0


@dataclass
class CoverageResult:
    """Container for parsed coverage metadata."""

    lines_covered: Optional[int]
    lines_valid: Optional[int]
    line_rate: Optional[float]
    timestamp: Optional[str]

    @property
    def percent(self) -> Optional[float]:
        if self.line_rate is None:
            return None
        return self.line_rate * 100


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarise backend CI outputs.")
    parser.add_argument(
        "--junit",
        required=True,
        help="Path to the pytest-generated JUnit XML report.",
    )
    parser.add_argument(
        "--coverage",
        required=True,
        help="Path to the coverage.py XML report.",
    )
    parser.add_argument(
        "--json-output",
        default="backend-ci-summary.json",
        help="Filename for the JSON summary output.",
    )
    parser.add_argument(
        "--csv-output",
        default="ci-metrics.csv",
        help="Filename for the metrics CSV output.",
    )
    parser.add_argument(
        "--release-smoke",
        default=None,
        help=(
            "Optional path to backend_release_smoke JSON output. "
            "When provided, it is included in summary artifacts."
        ),
    )
    return parser.parse_args(argv)


def iter_test_suites(root: ET.Element) -> Iterator[ET.Element]:
    """Yield unique ``testsuite`` elements from a JUnit XML tree."""

    if root.tag == "testsuite":
        yield root
        for child in root.findall("testsuite"):
            yield from iter_test_suites(child)
        return

    if root.tag == "testsuites":
        for child in root.findall("testsuite"):
            yield from iter_test_suites(child)
        return

    for child in root:
        yield from iter_test_suites(child)


def coerce_int(value: Optional[str]) -> int:
    try:
        if value is None:
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def coerce_float(value: Optional[str]) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def optional_int(value: Optional[str]) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def optional_float(value: Optional[str]) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_junit_report(path: Path) -> list[SuiteResult]:
    tree = ET.parse(path)
    root = tree.getroot()

    suites: list[SuiteResult] = []
    seen: set[int] = set()

    for suite in iter_test_suites(root):
        # ``id`` is optional but helps deduplicate nested suites in some
        # PyTest configurations. Fallback to Python's ``id`` for stability.
        suite_key = suite.get("id")
        key = hash((suite_key, suite.get("name")))
        if key in seen:
            continue
        seen.add(key)

        name = suite.get("name") or "unnamed"
        tests = coerce_int(suite.get("tests"))
        errors = coerce_int(suite.get("errors"))
        failures = coerce_int(suite.get("failures"))
        skipped = coerce_int(suite.get("skipped"))
        duration = coerce_float(suite.get("time"))
        timestamp = suite.get("timestamp")

        suites.append(
            SuiteResult(
                name=name,
                tests=tests,
                errors=errors,
                failures=failures,
                skipped=skipped,
                duration=duration,
                timestamp=timestamp,
            )
        )

    return suites


def parse_coverage_report(path: Path) -> CoverageResult:
    tree = ET.parse(path)
    root = tree.getroot()

    def attr(*names: str) -> Optional[str]:
        for name in names:
            if name in root.attrib:
                return root.attrib[name]
        return None

    lines_valid = attr("lines-valid", "linesValid")
    lines_covered = attr("lines-covered", "linesCovered")
    line_rate = attr("line-rate", "lineRate")

    return CoverageResult(
        lines_covered=optional_int(lines_covered),
        lines_valid=optional_int(lines_valid),
        line_rate=optional_float(line_rate),
        timestamp=attr("timestamp"),
    )


def parse_release_smoke_report(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("release smoke report must be a JSON object")
    return payload


def build_summary(
    suites: list[SuiteResult],
    coverage: CoverageResult,
    junit_path: Path,
    coverage_path: Path,
    release_smoke_path: Path | None = None,
    release_smoke: dict[str, object] | None = None,
) -> dict[str, object]:
    total_tests = sum(suite.tests for suite in suites)
    total_errors = sum(suite.errors for suite in suites)
    total_failures = sum(suite.failures for suite in suites)
    total_skipped = sum(suite.skipped for suite in suites)
    total_passed = sum(suite.passed for suite in suites)
    total_duration = sum(suite.duration for suite in suites)

    status = "passed" if (total_errors + total_failures) == 0 else "failed"
    release_smoke_ok = None
    if isinstance(release_smoke, dict):
        release_smoke_ok = bool(release_smoke.get("ok"))
        if release_smoke_ok is False:
            status = "failed"

    suites_payload = [
        {
            "name": suite.name,
            "tests": suite.tests,
            "passed": suite.passed,
            "failures": suite.failures,
            "errors": suite.errors,
            "skipped": suite.skipped,
            "duration_seconds": round(suite.duration, 6),
            "timestamp": suite.timestamp,
        }
        for suite in sorted(suites, key=lambda item: item.duration, reverse=True)
    ]

    summary = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": status,
        "inputs": {
            "junit_xml": str(junit_path),
            "coverage_xml": str(coverage_path),
            "release_smoke_json": str(release_smoke_path) if release_smoke_path else None,
        },
        "tests": {
            "total": total_tests,
            "passed": total_passed,
            "failures": total_failures,
            "errors": total_errors,
            "skipped": total_skipped,
        },
        "timing": {
            "total_duration_seconds": round(total_duration, 6),
            "suites": suites_payload,
        },
        "coverage": {
            "lines_covered": coverage.lines_covered,
            "lines_valid": coverage.lines_valid,
            "line_rate": coverage.line_rate,
            "line_rate_percent": round(coverage.percent, 4) if coverage.percent is not None else None,
            "timestamp": coverage.timestamp,
        },
    }

    if suites_payload:
        summary["timing"]["longest_suite"] = suites_payload[0]
    if release_smoke is not None:
        summary["release_smoke"] = {
            "ok": release_smoke_ok,
            "strict_external": release_smoke.get("strict_external"),
            "strict_observability": release_smoke.get("strict_observability"),
            "missing_metrics": release_smoke.get("missing_metrics"),
            "missing_metric_labels": release_smoke.get("missing_metric_labels"),
            "unknown_retry_share": release_smoke.get("unknown_retry_share"),
            "max_unknown_retry_share": release_smoke.get("max_unknown_retry_share"),
            "unknown_retry_reason_labels": release_smoke.get("unknown_retry_reason_labels"),
            "unknown_retry_count": release_smoke.get("unknown_retry_count"),
            "retry_total": release_smoke.get("retry_total"),
            "checks": release_smoke.get("checks"),
        }

    return summary


def build_metrics_rows(summary: dict[str, object]) -> list[dict[str, str]]:
    timing = summary["timing"]
    coverage = summary["coverage"]
    tests = summary["tests"]

    rows: list[dict[str, str]] = []

    rows.append(
        {
            "scope": "total",
            "metric": "pytest_duration",
            "value": f"{timing['total_duration_seconds']}",
            "unit": "seconds",
            "notes": (
                "tests={total};passed={passed};failures={failures};"
                "errors={errors};skipped={skipped}"
            ).format(**tests),
        }
    )

    longest_suite = timing.get("longest_suite")
    if isinstance(longest_suite, dict):
        rows.append(
            {
                "scope": f"suite:{longest_suite.get('name', 'unnamed')}",
                "metric": "pytest_longest_suite",
                "value": f"{longest_suite.get('duration_seconds')}",
                "unit": "seconds",
                "notes": (
                    "tests={tests};passed={passed};failures={failures};"
                    "errors={errors};skipped={skipped}"
                ).format(
                    tests=longest_suite.get("tests"),
                    passed=longest_suite.get("passed"),
                    failures=longest_suite.get("failures"),
                    errors=longest_suite.get("errors"),
                    skipped=longest_suite.get("skipped"),
                ),
            }
        )

    suites = timing.get("suites", [])
    if isinstance(suites, list):
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            rows.append(
                {
                    "scope": f"suite:{suite.get('name', 'unnamed')}",
                    "metric": "pytest_suite_duration",
                    "value": f"{suite.get('duration_seconds')}",
                    "unit": "seconds",
                    "notes": (
                        "tests={tests};passed={passed};failures={failures};"
                        "errors={errors};skipped={skipped}"
                    ).format(
                        tests=suite.get("tests"),
                        passed=suite.get("passed"),
                        failures=suite.get("failures"),
                        errors=suite.get("errors"),
                        skipped=suite.get("skipped"),
                    ),
                }
            )

    line_rate_percent = coverage.get("line_rate_percent")
    if line_rate_percent is not None:
        rows.append(
            {
                "scope": "coverage",
                "metric": "line_rate",
                "value": f"{line_rate_percent}",
                "unit": "percent",
                "notes": (
                    "lines_covered={covered};lines_valid={valid}"
                ).format(
                    covered=coverage.get("lines_covered"),
                    valid=coverage.get("lines_valid"),
                ),
            }
        )

    release_smoke = summary.get("release_smoke")
    if isinstance(release_smoke, dict):
        release_smoke_ok = bool(release_smoke.get("ok"))
        rows.append(
            {
                "scope": "release_smoke",
                "metric": "status",
                "value": "1" if release_smoke_ok else "0",
                "unit": "bool",
                "notes": (
                    "strict_external={strict_external};strict_observability={strict_observability}"
                ).format(
                    strict_external=release_smoke.get("strict_external"),
                    strict_observability=release_smoke.get("strict_observability"),
                ),
            }
        )
        missing_metrics = release_smoke.get("missing_metrics")
        if isinstance(missing_metrics, list):
            rows.append(
                {
                    "scope": "release_smoke",
                    "metric": "missing_metrics_count",
                    "value": f"{len(missing_metrics)}",
                    "unit": "count",
                    "notes": "backend_release_smoke missing metric names",
                }
            )
        missing_metric_labels = release_smoke.get("missing_metric_labels")
        if isinstance(missing_metric_labels, list):
            rows.append(
                {
                    "scope": "release_smoke",
                    "metric": "missing_metric_labels_count",
                    "value": f"{len(missing_metric_labels)}",
                    "unit": "count",
                    "notes": "backend_release_smoke missing metric labels",
                }
            )
        unknown_retry_share = release_smoke.get("unknown_retry_share")
        if isinstance(unknown_retry_share, (int, float)):
            rows.append(
                {
                    "scope": "release_smoke",
                    "metric": "unknown_retry_share",
                    "value": f"{unknown_retry_share}",
                    "unit": "ratio",
                    "notes": (
                        "max_unknown_retry_share={max_unknown_retry_share}"
                    ).format(
                        max_unknown_retry_share=release_smoke.get("max_unknown_retry_share"),
                    ),
                }
            )
        unknown_retry_count = release_smoke.get("unknown_retry_count")
        if isinstance(unknown_retry_count, (int, float)):
            rows.append(
                {
                    "scope": "release_smoke",
                    "metric": "unknown_retry_count",
                    "value": f"{unknown_retry_count}",
                    "unit": "count",
                    "notes": (
                        "retry_total={retry_total};labels={labels}"
                    ).format(
                        retry_total=release_smoke.get("retry_total"),
                        labels=release_smoke.get("unknown_retry_reason_labels"),
                    ),
                }
            )

    return rows


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["scope", "metric", "value", "unit", "notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    junit_path = Path(args.junit)
    coverage_path = Path(args.coverage)
    release_smoke_path = Path(args.release_smoke) if args.release_smoke else None

    if not junit_path.exists():
        print(f"JUnit XML report not found: {junit_path}", file=sys.stderr)
        return 1
    if not coverage_path.exists():
        print(f"Coverage XML report not found: {coverage_path}", file=sys.stderr)
        return 1
    release_smoke_payload: dict[str, object] | None = None
    if release_smoke_path is not None:
        if not release_smoke_path.exists():
            print(f"Release smoke report not found: {release_smoke_path}", file=sys.stderr)
            return 1
        try:
            release_smoke_payload = parse_release_smoke_report(release_smoke_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"Invalid release smoke report ({release_smoke_path}): {exc}", file=sys.stderr)
            return 1

    suites = parse_junit_report(junit_path)
    if not suites:
        print("No test suites found in JUnit XML report.", file=sys.stderr)
        return 1

    coverage = parse_coverage_report(coverage_path)
    summary = build_summary(
        suites,
        coverage,
        junit_path,
        coverage_path,
        release_smoke_path=release_smoke_path,
        release_smoke=release_smoke_payload,
    )
    metrics_rows = build_metrics_rows(summary)

    write_json(Path(args.json_output), summary)
    write_csv(Path(args.csv_output), metrics_rows)

    release_smoke = summary.get("release_smoke")
    if isinstance(release_smoke, dict) and release_smoke.get("ok") is False:
        print("Release smoke report indicates failure.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
