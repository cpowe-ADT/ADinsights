#!/usr/bin/env python3
"""
Generate a GitHub Actions step summary table from coverage reports.

The script understands Coverage.py XML outputs and LCOV/``.info`` reports.
It appends a markdown table to ``$GITHUB_STEP_SUMMARY`` by default. If the
summary file cannot be resolved the table is printed to stdout.

Usage example:

    scripts/ci/coverage-summary.py \
        --coverage backend=backend/coverage.xml \
        --coverage frontend=frontend/coverage.lcov
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
        "--output",
        "-o",
        help="Explicit path to the GitHub step summary file.",
        default=None,
    )
    return parser.parse_args(argv)


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

    def _coerce_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _coerce_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    lines_total = _coerce_int(_get_attr("lines-valid", "linesValid"))
    lines_covered = _coerce_int(_get_attr("lines-covered", "linesCovered"))
    line_rate = _coerce_float(_get_attr("line-rate", "lineRate"))

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


def resolve_summary_path(explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        return Path(explicit_path)
    env_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if env_path:
        return Path(env_path)
    return None


def build_table(results: list[CoverageResult]) -> str:
    header = "| Target | Lines Covered | Lines Total | Coverage | Notes |"
    separator = "| --- | ---: | ---: | ---: | --- |"
    rows = [header, separator]

    for result in results:
        notes = result.note or ""
        rows.append(
            "| {name} | {covered} | {total} | {coverage} | {notes} |".format(
                name=result.name,
                covered=result.formatted_lines_covered,
                total=result.formatted_lines_total,
                coverage=result.formatted_percentage,
                notes=notes.replace("|", "/"),
            )
        )

    return "\n".join(rows) + "\n"


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

    if not args.coverage:
        message = textwrap.dedent(
            """
            No coverage files were provided. Use --coverage LABEL=PATH to specify
            at least one report. Skipping summary generation.
            """
        ).strip()
        print(message, file=sys.stderr)
        return 0

    results: list[CoverageResult] = []

    for mapping in args.coverage:
        try:
            label, path = parse_mapping(mapping)
        except ValueError as exc:
            print(f"{exc}", file=sys.stderr)
            results.append(CoverageResult(name=mapping, note=str(exc)))
            continue

        if not path.exists():
            note = f"File not found: {path}"
            print(note, file=sys.stderr)
            results.append(CoverageResult(name=label, note=note))
            continue

        try:
            lines_covered, lines_total, coverage_ratio = parse_coverage_file(path)
            results.append(
                CoverageResult(
                    name=label,
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    coverage_ratio=coverage_ratio,
                )
            )
        except Exception as exc:  # pylint: disable=broad-except
            note = f"Error reading {path}: {exc}"
            print(note, file=sys.stderr)
            results.append(CoverageResult(name=label, note=note))

    if not results:
        print("No results gathered; nothing to summarise.", file=sys.stderr)
        return 0

    table = build_table(results)
    summary_path = resolve_summary_path(args.output)
    append_summary(table, summary_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
