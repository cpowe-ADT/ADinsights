#!/usr/bin/env python3
"""
Generate a GitHub Actions step summary table from coverage reports and JUnit
test results.

The script understands Coverage.py XML outputs, LCOV/``.info`` reports, and
JUnit XML reports.
It appends a markdown table to ``$GITHUB_STEP_SUMMARY`` by default. If the
summary file cannot be resolved the table is printed to stdout.

Usage example:

    scripts/ci/coverage-summary.py \
        --coverage backend=backend/coverage.xml \
        --coverage frontend=frontend/coverage.lcov \
        --junit backend=backend/test-results/junit.xml
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class CoverageResult:
    name: str
    lines_covered: Optional[int] = None
    lines_total: Optional[int] = None
    coverage_ratio: Optional[float] = None
    note: Optional[str] = None

    @property
    def formatted_percentage(self) -> str:
        if self.coverage_ratio is None:
            return "N/A"
        return f"{self.coverage_ratio * 100:.2f}%"

    @property
    def formatted_lines_covered(self) -> str:
        if self.lines_covered is None:
            return "—"
        return str(self.lines_covered)

    @property
    def formatted_lines_total(self) -> str:
        if self.lines_total is None:
            return "—"
        return str(self.lines_total)


@dataclass
class JUnitResult:
    name: str
    tests_total: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_skipped: Optional[int] = None
    note: Optional[str] = None

    @property
    def formatted_tests_total(self) -> str:
        if self.tests_total is None:
            return "—"
        return str(self.tests_total)

    @property
    def formatted_tests_passed(self) -> str:
        if self.tests_passed is None:
            return "—"
        return str(self.tests_passed)

    @property
    def formatted_tests_failed(self) -> str:
        if self.tests_failed is None:
            return "—"
        return str(self.tests_failed)


@dataclass
class SummaryRow:
    name: str
    coverage: Optional[CoverageResult] = None
    junit: Optional[JUnitResult] = None
    notes: list[str] = field(default_factory=list)

    def iter_notes(self) -> list[str]:
        entries: list[str] = []
        if self.coverage and self.coverage.note:
            entries.append(self.coverage.note)
        if self.junit:
            if self.junit.note:
                entries.append(self.junit.note)
            if self.junit.tests_skipped:
                entries.append(f"Skipped: {self.junit.tests_skipped}")
        entries.extend(self.notes)
        return entries

def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarise coverage files.")
    parser.add_argument(
        "--coverage",
        "-c",
        action="append",
        metavar="LABEL=PATH",
        help="Mapping between a display label and a coverage file path.",
    )
    parser.add_argument(
        "--junit",
        "-j",
        action="append",
        metavar="LABEL=PATH",
        help="Mapping between a display label and a JUnit XML report path.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Explicit path to the GitHub step summary file.",
        default=None,
    )
    return parser.parse_args(argv)


def strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def coerce_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_mapping(mapping: str) -> tuple[str, Path]:
    if "=" not in mapping:
        raise ValueError(
            f"Invalid mapping '{mapping}'. Expected the form LABEL=PATH."
        )
    label, path = mapping.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError(f"Invalid mapping '{mapping}'. LABEL cannot be empty.")
    return label, Path(path.strip())


def parse_coverage_file(path: Path) -> tuple[Optional[int], Optional[int], Optional[float]]:
    suffix = path.suffix.lower()

    if suffix == ".xml":
        return parse_xml_coverage(path)
    if suffix in {".lcov", ".info"}:
        return parse_lcov_coverage(path)

    raise ValueError(f"Unsupported coverage format for file '{path}'.")


def parse_xml_coverage(path: Path) -> tuple[Optional[int], Optional[int], Optional[float]]:
    tree = ET.parse(path)
    root = tree.getroot()

    def _get_attr(*names: str) -> Optional[str]:
        for name in names:
            if name in root.attrib:
                return root.attrib[name]
        return None

    lines_total = coerce_int(_get_attr("lines-valid", "linesValid"))
    lines_covered = coerce_int(_get_attr("lines-covered", "linesCovered"))
    line_rate = coerce_float(_get_attr("line-rate", "lineRate"))

    if lines_covered is None and lines_total is not None and line_rate is not None:
        lines_covered = int(round(line_rate * lines_total))

    if line_rate is None and lines_total and lines_total > 0 and lines_covered is not None:
        line_rate = lines_covered / lines_total

    return lines_covered, lines_total, line_rate


def parse_lcov_coverage(path: Path) -> tuple[Optional[int], Optional[int], Optional[float]]:
    total = 0
    covered = 0

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("DA:"):
                try:
                    _, count = line.split(":", 1)[1].split(",")
                    executions = int(count)
                except ValueError:
                    continue
                total += 1
                if executions > 0:
                    covered += 1

    if total == 0:
        return None, None, None

    return covered, total, covered / total


def parse_junit_report(path: Path) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    tree = ET.parse(path)
    root = tree.getroot()

    testcases = [node for node in root.iter() if strip_namespace(node.tag) == "testcase"]

    def _count_results_from_cases() -> tuple[int, int, int, int]:
        total_cases = len(testcases)
        failed_cases = 0
        skipped_cases = 0

        for case in testcases:
            children = [strip_namespace(child.tag) for child in case]
            if any(child in {"failure", "error"} for child in children):
                failed_cases += 1
            if any(child == "skipped" for child in children):
                skipped_cases += 1

        passed_cases = total_cases - failed_cases - skipped_cases
        if passed_cases < 0:
            passed_cases = 0
        return total_cases, passed_cases, failed_cases, skipped_cases

    if testcases:
        return _count_results_from_cases()

    suites = [node for node in root.iter() if strip_namespace(node.tag) == "testsuite"]
    if not suites:
        raise ValueError("No <testcase> or <testsuite> elements found in JUnit report")

    total = 0
    failures = 0
    errors = 0
    skipped = 0

    for suite in suites:
        tests_attr = coerce_int(suite.attrib.get("tests"))
        if tests_attr is not None:
            total += tests_attr
        else:
            total += sum(1 for node in suite.iter() if strip_namespace(node.tag) == "testcase")

        failures_attr = coerce_int(suite.attrib.get("failures")) or 0
        errors_attr = coerce_int(suite.attrib.get("errors")) or 0
        skipped_attr = coerce_int(suite.attrib.get("skipped"))
        if skipped_attr is None:
            skipped_attr = coerce_int(suite.attrib.get("disabled")) or 0

        failures += failures_attr
        errors += errors_attr
        skipped += skipped_attr

    failed = failures + errors
    passed = total - failed - skipped
    if passed < 0:
        passed = 0

    return total, passed, failed, skipped


def resolve_summary_path(explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        return Path(explicit_path)
    env_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if env_path:
        return Path(env_path)
    return None


def build_table(rows: list[SummaryRow]) -> str:
    header = (
        "| Target | Lines Covered | Lines Total | Coverage | Tests Passed | Tests Failed | "
        "Tests Total | Notes |"
    )
    separator = "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    table_rows = [header, separator]

    for row in rows:
        coverage = row.coverage
        junit = row.junit
        notes = row.iter_notes()
        notes_text = "; ".join(notes).replace("|", "/") if notes else ""

        table_rows.append(
            "| {name} | {covered} | {total} | {coverage_pct} | {tests_passed} | {tests_failed} | {tests_total} | {notes} |".format(
                name=row.name,
                covered=coverage.formatted_lines_covered if coverage else "—",
                total=coverage.formatted_lines_total if coverage else "—",
                coverage_pct=coverage.formatted_percentage if coverage else "N/A",
                tests_passed=junit.formatted_tests_passed if junit else "—",
                tests_failed=junit.formatted_tests_failed if junit else "—",
                tests_total=junit.formatted_tests_total if junit else "—",
                notes=notes_text,
            )
        )

    return "\n".join(table_rows) + "\n"


def append_summary(table: str, summary_path: Optional[Path]) -> None:
    if summary_path is None:
        print(table)
        return

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(table)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    if not args.coverage and not args.junit:
        message = textwrap.dedent(
            """
            No coverage or JUnit files were provided. Use --coverage LABEL=PATH or
            --junit LABEL=PATH to specify at least one report. Skipping summary
            generation.
            """
        ).strip()
        print(message, file=sys.stderr)
        return 0

    rows: dict[str, SummaryRow] = {}
    order: list[str] = []
    errors_found = False

    def ensure_row(name: str) -> SummaryRow:
        if name not in rows:
            rows[name] = SummaryRow(name=name)
            order.append(name)
        return rows[name]

    def record_error(name: str, note: str) -> None:
        nonlocal errors_found
        errors_found = True
        row = ensure_row(name)
        row.notes.append(note)
        print(note, file=sys.stderr)

    for mapping in args.coverage or []:
        try:
            label, path = parse_mapping(mapping)
        except ValueError as exc:
            record_error(mapping, str(exc))
            continue

        if not path.exists():
            record_error(label, f"File not found: {path}")
            continue

        row = ensure_row(label)

        try:
            lines_covered, lines_total, coverage_ratio = parse_coverage_file(path)
            row.coverage = CoverageResult(
                name=label,
                lines_covered=lines_covered,
                lines_total=lines_total,
                coverage_ratio=coverage_ratio,
            )
        except Exception as exc:  # pylint: disable=broad-except
            record_error(label, f"Error reading {path}: {exc}")

    for mapping in args.junit or []:
        try:
            label, path = parse_mapping(mapping)
        except ValueError as exc:
            record_error(mapping, str(exc))
            continue

        if not path.exists():
            record_error(label, f"File not found: {path}")
            continue

        row = ensure_row(label)

        try:
            tests_total, tests_passed, tests_failed, tests_skipped = parse_junit_report(path)
            row.junit = JUnitResult(
                name=label,
                tests_total=tests_total,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=tests_skipped,
            )
        except Exception as exc:  # pylint: disable=broad-except
            record_error(label, f"Error reading {path}: {exc}")

    if not order:
        print("No results gathered; nothing to summarise.", file=sys.stderr)
        return 1 if errors_found else 0

    table = build_table([rows[name] for name in order])
    summary_path = resolve_summary_path(args.output)
    append_summary(table, summary_path)
    return 1 if errors_found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
