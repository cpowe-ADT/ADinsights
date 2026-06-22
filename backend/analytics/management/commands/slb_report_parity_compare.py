"""Compare SLB ADinsights parity rows against manual DashThis/source values."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Merge SLB evidence-bundle parity rows with redacted DashThis/source values."

    def add_arguments(self, parser):
        parser.add_argument("--evidence-bundle", required=True)
        parser.add_argument("--comparison-values", required=True)
        parser.add_argument("--format", choices=["json", "markdown"], default="json")

    def handle(self, *args, **options):
        bundle = _load_json_file(options["evidence_bundle"], expected="evidence bundle")
        comparison = _load_json_file(options["comparison_values"], expected="comparison values")
        result = build_parity_comparison(bundle=bundle, comparison=comparison)
        if options["format"] == "markdown":
            self.stdout.write(_markdown(result))
        else:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))


def build_parity_comparison(
    *,
    bundle: Mapping[str, Any],
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = _rows_from_bundle(bundle)
    comparison_rows = _comparison_rows(comparison)
    comparisons = _comparison_index(comparison_rows)
    output_rows = [_compare_row(row, comparisons) for row in rows]
    summary: dict[str, int] = {}
    for row in output_rows:
        result = str(row["result"])
        summary[result] = summary.get(result, 0) + 1
    return {
        "schema_version": "slb_parity_comparison.v1",
        "report": bundle.get("report") or {},
        "date_range": bundle.get("date_range") or {},
        "preview_hash": bundle.get("preview_hash") or "",
        "source_reference": _safe_source_reference(comparison),
        "row_count": len(output_rows),
        "result_summary": summary,
        "rows": output_rows,
    }


def _load_json_file(path: str, *, expected: str) -> Any:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CommandError(f"{expected} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"{expected} file is not valid JSON: {path}") from exc


def _rows_from_bundle(bundle: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = bundle.get("parity_rows")
    if not isinstance(rows, list):
        raise CommandError("Evidence bundle must include a parity_rows list.")
    return [row for row in rows if isinstance(row, Mapping)]


def _comparison_rows(comparison: Mapping[str, Any] | list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(comparison, list):
        return [row for row in comparison if isinstance(row, Mapping)]
    rows = comparison.get("rows") if isinstance(comparison, Mapping) else []
    if not isinstance(rows, list):
        raise CommandError("Comparison values must be a JSON list or an object with a rows list.")
    return [row for row in rows if isinstance(row, Mapping)]


def _comparison_index(rows: list[Mapping[str, Any]]) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    by_full_key: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    by_metric_key: dict[tuple[str, str, str, str], Mapping[str, Any] | None] = {}
    for row in rows:
        full_key = _row_key(row, include_label=True)
        metric_key = _row_key(row, include_label=False)
        by_full_key[full_key] = row
        by_metric_key[metric_key] = row if metric_key not in by_metric_key else None
    return {**{key: value for key, value in by_metric_key.items() if value is not None}, **by_full_key}


def _compare_row(
    row: Mapping[str, Any],
    comparisons: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    comparison = comparisons.get(_row_key(row, include_label=True)) or comparisons.get(
        _row_key(row, include_label=False)
    )
    base = {
        "page_id": str(row.get("page_id") or ""),
        "section_id": str(row.get("section_id") or ""),
        "widget_id": str(row.get("widget_id") or ""),
        "dataset": str(row.get("dataset") or ""),
        "metric": str(row.get("metric") or ""),
        "label": str(row.get("label") or ""),
        "coverage_status": str(row.get("coverage_status") or ""),
        "source_label": str(row.get("source_label") or ""),
        "adinsights_value": row.get("adinsights_value"),
        "dashthis_value": None,
        "source_value": None,
        "absolute_delta": None,
        "absolute_delta_magnitude": None,
        "percentage_delta": None,
        "accepted_tolerance_percent": None,
        "accepted_tolerance_absolute": None,
        "result": "blocked_missing_dashthis_value",
        "explanation": "",
    }
    if comparison is None:
        return base

    source_value = _first_present(
        comparison,
        "dashthis_value",
        "source_value",
        "comparison_value",
    )
    if source_value is None:
        base["result"] = "blocked_missing_source_value"
        base["explanation"] = str(comparison.get("explanation") or "")
        return base

    adinsights_value = _decimal_or_none(row.get("adinsights_value"))
    comparison_value = _decimal_or_none(source_value)
    if adinsights_value is None or comparison_value is None:
        base["result"] = "blocked_metric_semantics"
        base["dashthis_value"] = source_value
        base["source_value"] = source_value
        base["explanation"] = str(comparison.get("explanation") or "Non-numeric parity value.")
        return base

    absolute_delta = adinsights_value - comparison_value
    absolute_delta_magnitude = abs(absolute_delta)
    percentage_delta = absolute_delta_magnitude / max(abs(comparison_value), Decimal("1")) * Decimal("100")
    tolerance_percent = _decimal_or_none(comparison.get("accepted_tolerance_percent"))
    tolerance_absolute = _decimal_or_none(comparison.get("accepted_tolerance_absolute"))
    result = _result_for_delta(
        absolute_delta_magnitude=absolute_delta_magnitude,
        percentage_delta=percentage_delta,
        tolerance_percent=tolerance_percent,
        tolerance_absolute=tolerance_absolute,
    )
    return {
        **base,
        "dashthis_value": _number(comparison_value),
        "source_value": _number(comparison_value),
        "absolute_delta": _number(absolute_delta),
        "absolute_delta_magnitude": _number(absolute_delta_magnitude),
        "percentage_delta": _number(percentage_delta),
        "accepted_tolerance_percent": _number(tolerance_percent),
        "accepted_tolerance_absolute": _number(tolerance_absolute),
        "result": result,
        "explanation": str(comparison.get("explanation") or ""),
    }


def _result_for_delta(
    *,
    absolute_delta_magnitude: Decimal,
    percentage_delta: Decimal,
    tolerance_percent: Decimal | None,
    tolerance_absolute: Decimal | None,
) -> str:
    if tolerance_absolute is None and tolerance_percent is None:
        return "blocked_metric_semantics"
    absolute_passes = (
        tolerance_absolute is not None and absolute_delta_magnitude <= tolerance_absolute
    )
    percent_passes = tolerance_percent is not None and percentage_delta <= tolerance_percent
    return "pass" if absolute_passes or percent_passes else "fail"


def _row_key(row: Mapping[str, Any], *, include_label: bool) -> tuple[str, str, str, str]:
    return (
        str(row.get("dataset") or ""),
        str(row.get("widget_id") or ""),
        str(row.get("metric") or ""),
        str(row.get("label") or "") if include_label else "",
    )


def _first_present(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return int(normalized)
    return float(normalized)


def _safe_source_reference(comparison: Mapping[str, Any] | list[Mapping[str, Any]]) -> str:
    if not isinstance(comparison, Mapping):
        return ""
    value = str(comparison.get("source_reference") or "")
    lowered = value.lower()
    forbidden = ["@", "access_token", "refresh_token", "client_secret", "password", "secret"]
    if any(item in lowered for item in forbidden):
        return "redacted"
    return value


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SLB Parity Comparison",
        "",
        f"- Preview hash: `{result.get('preview_hash') or ''}`",
        f"- Row count: `{result.get('row_count') or 0}`",
        f"- Result summary: `{json.dumps(result.get('result_summary') or {}, sort_keys=True)}`",
        "",
        "| Dataset | Metric | Label | ADinsights | Source | Abs Delta | % Delta | Tolerance % | Result |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in result.get("rows", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {dataset} | {metric} | {label} | {adinsights} | {source} | {delta} | {percent} | {tolerance} | {result} |".format(
                dataset=row.get("dataset") or "",
                metric=row.get("metric") or "",
                label=str(row.get("label") or "").replace("|", "\\|"),
                adinsights=row.get("adinsights_value"),
                source=row.get("source_value"),
                delta=row.get("absolute_delta"),
                percent=row.get("percentage_delta"),
                tolerance=row.get("accepted_tolerance_percent"),
                result=row.get("result"),
            )
        )
    return "\n".join(lines)
