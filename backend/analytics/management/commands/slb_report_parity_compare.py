"""Compare SLB ADinsights parity rows against manual DashThis/source values."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

_FORBIDDEN_SOURCE_TEXT = [
    "@",
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "secret",
]
_MISSING_SOURCE_VALUE_TEXT = {"", "-", "na", "n/a", "none", "null", "tbd"}


class Command(BaseCommand):
    help = "Merge SLB evidence-bundle parity rows with redacted DashThis/source values."

    def add_arguments(self, parser):
        parser.add_argument("--evidence-bundle", required=True)
        parser.add_argument("--comparison-values", required=True)
        parser.add_argument("--format", choices=["json", "markdown"], default="json")

    def handle(self, *args, **options):
        bundle = _load_json_file(options["evidence_bundle"], expected="evidence bundle")
        comparison = _load_json_file(
            options["comparison_values"], expected="comparison values"
        )
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
    unresolved_rows = _unresolved_row_inventory(output_rows)
    completion_requirements = _completion_requirements(unresolved_rows, bundle)
    blocking_next_actions = _blocking_next_actions(completion_requirements)
    return {
        "schema_version": "slb_parity_comparison.v1",
        "report": bundle.get("report") or {},
        "date_range": bundle.get("date_range") or {},
        "preview_hash": bundle.get("preview_hash") or "",
        "source_reference": _safe_source_reference(comparison),
        "source_search_provenance": _safe_source_search_provenance(comparison),
        "missing_source_values": _safe_source_value_entries(
            comparison, "missing_source_values"
        ),
        "unmatched_source_values": _combined_unmatched_source_values(
            comparison=comparison,
            comparison_rows=comparison_rows,
            evidence_rows=rows,
        ),
        "row_count": len(output_rows),
        "result_summary": summary,
        "unresolved_row_count": len(unresolved_rows),
        "unresolved_summary": _unresolved_summary(unresolved_rows),
        "unresolved_rows": unresolved_rows,
        "parity_completion_requirements": completion_requirements,
        "blocking_next_actions": blocking_next_actions,
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


def _comparison_rows(
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(comparison, list):
        return [row for row in comparison if isinstance(row, Mapping)]
    rows = comparison.get("rows") if isinstance(comparison, Mapping) else []
    if not isinstance(rows, list):
        raise CommandError(
            "Comparison values must be a JSON list or an object with a rows list."
        )
    return [row for row in rows if isinstance(row, Mapping)]


def _comparison_index(
    rows: list[Mapping[str, Any]],
) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    by_full_key: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    by_metric_key: dict[tuple[str, str, str, str], Mapping[str, Any] | None] = {}
    for row in rows:
        full_key = _row_key(row, include_label=True)
        metric_key = _row_key(row, include_label=False)
        by_full_key[full_key] = row
        by_metric_key[metric_key] = row if metric_key not in by_metric_key else None
    return {
        **{key: value for key, value in by_metric_key.items() if value is not None},
        **by_full_key,
    }


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

    source_value = _first_source_value(
        comparison,
        "dashthis_value",
        "source_value",
        "comparison_value",
    )
    if _is_missing_source_value(source_value):
        base["result"] = "blocked_missing_source_value"
        base["explanation"] = str(comparison.get("explanation") or "")
        return base

    adinsights_value = _decimal_or_none(row.get("adinsights_value"))
    comparison_value = _decimal_or_none(source_value)
    if comparison_value is None:
        base["result"] = "blocked_metric_semantics"
        base["dashthis_value"] = source_value
        base["source_value"] = source_value
        base["explanation"] = str(
            comparison.get("explanation") or "Non-numeric parity value."
        )
        return base
    if adinsights_value is None:
        base["result"] = "blocked_missing_adinsights_value"
        base["dashthis_value"] = _number(comparison_value)
        base["source_value"] = _number(comparison_value)
        base["explanation"] = str(
            comparison.get("explanation")
            or "Source value is present, but ADinsights has no retained value to compare."
        )
        return base

    absolute_delta = adinsights_value - comparison_value
    absolute_delta_magnitude = abs(absolute_delta)
    percentage_delta = (
        absolute_delta_magnitude
        / max(abs(comparison_value), Decimal("1"))
        * Decimal("100")
    )
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
        tolerance_absolute is not None
        and absolute_delta_magnitude <= tolerance_absolute
    )
    percent_passes = (
        tolerance_percent is not None and percentage_delta <= tolerance_percent
    )
    return "pass" if absolute_passes or percent_passes else "fail"


def _row_key(
    row: Mapping[str, Any], *, include_label: bool
) -> tuple[str, str, str, str]:
    return (
        str(row.get("dataset") or ""),
        str(row.get("widget_id") or ""),
        str(row.get("metric") or ""),
        str(row.get("label") or "") if include_label else "",
    )


def _first_source_value(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if not _is_missing_source_value(value):
            return value
    return None


def _is_missing_source_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _MISSING_SOURCE_VALUE_TEXT
    return False


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if not value.is_finite():
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return int(normalized)
    return float(normalized)


def _safe_source_reference(
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
) -> str:
    if not isinstance(comparison, Mapping):
        return ""
    return _safe_text(comparison.get("source_reference") or "")


def _safe_source_search_provenance(
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(comparison, Mapping):
        return []
    provenance = comparison.get("source_search_provenance")
    if not isinstance(provenance, list):
        return []
    safe_entries: list[dict[str, Any]] = []
    for entry in provenance:
        if not isinstance(entry, Mapping):
            continue
        safe_entry: dict[str, Any] = {}
        searched_at = _safe_text(entry.get("searched_at") or "")
        source = _safe_text(entry.get("source") or "")
        result = _safe_text(entry.get("result") or "")
        queries = entry.get("queries")
        if searched_at:
            safe_entry["searched_at"] = searched_at
        if source:
            safe_entry["source"] = source
        if isinstance(queries, list):
            safe_entry["queries"] = [_safe_text(query) for query in queries]
        if result:
            safe_entry["result"] = result
        if safe_entry:
            safe_entries.append(safe_entry)
    return safe_entries


def _safe_source_value_entries(
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    if not isinstance(comparison, Mapping):
        return []
    entries = comparison.get(key)
    if not isinstance(entries, list):
        return []
    safe_entries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        safe_entry = {
            str(entry_key): _safe_json_value(entry_value)
            for entry_key, entry_value in entry.items()
        }
        if safe_entry:
            safe_entries.append(safe_entry)
    return safe_entries


def _combined_unmatched_source_values(
    *,
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
    comparison_rows: list[Mapping[str, Any]],
    evidence_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    explicit_entries = _safe_unmatched_source_value_entries(comparison)
    derived_entries = _unmatched_comparison_source_rows(
        comparison_rows=comparison_rows,
        evidence_rows=evidence_rows,
    )
    return [*explicit_entries, *derived_entries]


def _safe_unmatched_source_value_entries(
    comparison: Mapping[str, Any] | list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(comparison, Mapping):
        return []
    entries = comparison.get("unmatched_source_values")
    if not isinstance(entries, list):
        return []
    safe_entries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        source_value = entry.get("source_value")
        if _is_missing_source_value(source_value):
            continue
        safe_entry = {
            str(entry_key): _safe_json_value(entry_value)
            for entry_key, entry_value in entry.items()
        }
        if safe_entry:
            safe_entries.append(safe_entry)
    return safe_entries


def _unmatched_comparison_source_rows(
    *,
    comparison_rows: list[Mapping[str, Any]],
    evidence_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence_full_keys = {_row_key(row, include_label=True) for row in evidence_rows}
    evidence_metric_keys = {_row_key(row, include_label=False) for row in evidence_rows}
    unmatched: list[dict[str, Any]] = []
    for row in comparison_rows:
        full_key = _row_key(row, include_label=True)
        metric_key = _row_key(row, include_label=False)
        if full_key in evidence_full_keys or metric_key in evidence_metric_keys:
            continue
        source_value = _first_source_value(
            row,
            "dashthis_value",
            "source_value",
            "comparison_value",
        )
        if _is_missing_source_value(source_value):
            continue
        dataset = str(row.get("dataset") or "")
        widget_id = str(row.get("widget_id") or "")
        metric = str(row.get("metric") or "")
        entry = {
            "dataset": dataset,
            "widget_id": widget_id,
            "metric": metric,
            "label": _safe_text(row.get("label") or ""),
            "source_value": _safe_json_value(source_value),
            "reason_not_in_parity_rows": _safe_text(
                row.get("reason_not_in_parity_rows")
                or (
                    "No matching current evidence-bundle parity row exists for "
                    f"{dataset}.{widget_id}.{metric}; preserved as an unmatched source value."
                )
            ),
        }
        for source_key in (
            "source_document",
            "source_page",
            "source_pages",
            "source_label",
            "source_display_value",
            "explanation",
        ):
            if source_key in row:
                entry[source_key] = _safe_json_value(row[source_key])
        unmatched.append(entry)
    return unmatched


def _safe_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(child_key): _safe_json_value(child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_text(value: object) -> str:
    text = str(value)
    lowered = text.lower()
    if any(item in lowered for item in _FORBIDDEN_SOURCE_TEXT):
        return "redacted"
    return text


def _unresolved_row_inventory(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for row in rows:
        result = str(row.get("result") or "")
        if result == "pass":
            continue
        unresolved.append(
            {
                "dataset": str(row.get("dataset") or ""),
                "widget_id": str(row.get("widget_id") or ""),
                "metric": str(row.get("metric") or ""),
                "label": str(row.get("label") or ""),
                "result": result,
                "coverage_status": str(row.get("coverage_status") or ""),
                "source_label": str(row.get("source_label") or ""),
                "has_adinsights_value": row.get("adinsights_value") is not None,
                "has_source_value": row.get("source_value") is not None,
                "explanation": str(row.get("explanation") or ""),
                "recommended_next_action": _recommended_next_action(row),
            }
        )
    return unresolved


def _recommended_next_action(row: Mapping[str, Any]) -> str:
    dataset = str(row.get("dataset") or "")
    result = str(row.get("result") or "")
    has_source_value = row.get("source_value") is not None
    has_adinsights_value = row.get("adinsights_value") is not None
    if result == "fail":
        return "Investigate source/date/account filters and metric semantics before approving parity."
    if dataset == "paid_meta_ads":
        if result == "blocked_missing_adinsights_value":
            return (
                "Backfill the selected SLB Meta ad account or import the approved daily paid CSV, "
                "then rerun parity. Do not substitute another tenant account."
            )
        if result in {"blocked_missing_source_value", "blocked_missing_dashthis_value"}:
            return (
                "Provide an approved selected-account May 2026 Meta Ads source export for parity; "
                "if retained ADinsights rows are also missing, reconnect/backfill the selected SLB ad account. "
                "Do not substitute another tenant account."
            )
        return "Confirm paid Meta metric semantics, selected account scope, date range, and accepted tolerance."
    if dataset == "organic_facebook_page":
        if result == "blocked_missing_adinsights_value" or (
            has_source_value and not has_adinsights_value
        ):
            return (
                "After reviewer confirmation of organic metric semantics, import the approved aggregate source values "
                "through the manual Meta organic CSV path once a tenant-owned SLB Facebook Page exists. "
                "Do not import values into an unrelated Page."
            )
        if result in {"blocked_missing_source_value", "blocked_missing_dashthis_value"}:
            return "Provide approved aggregate Page/Post source values or keep the row unavailable with search provenance."
        return "Confirm organic metric semantics, especially reach/views/impressions naming and date boundaries."
    if dataset == "content_ops":
        if result == "blocked_missing_adinsights_value":
            return (
                "Import or backfill the approved aggregate Content Ops source totals for May 2026, "
                "then rerun parity."
            )
        if result in {"blocked_missing_source_value", "blocked_missing_dashthis_value"}:
            return (
                "Provide an approved aggregate Content Ops source export for the May 2026 totals; "
                "do not infer counts from top-post examples."
            )
        return "Confirm Content Ops metric scope, aggregate source, and exact-count tolerance."
    return "Review the source value, retained ADinsights value, metric semantics, and accepted tolerance."


def _unresolved_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_result: dict[str, int] = {}
    by_dataset: dict[str, dict[str, int]] = {}
    for row in rows:
        result = str(row.get("result") or "")
        dataset = str(row.get("dataset") or "")
        by_result[result] = by_result.get(result, 0) + 1
        dataset_summary = by_dataset.setdefault(dataset, {})
        dataset_summary[result] = dataset_summary.get(result, 0) + 1
    return {
        "by_result": by_result,
        "by_dataset": by_dataset,
    }


def _completion_requirements(
    unresolved_rows: list[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    paid_source_rows = _matching_rows(
        unresolved_rows,
        dataset="paid_meta_ads",
        results={"blocked_missing_source_value", "blocked_missing_dashthis_value"},
    )
    if paid_source_rows:
        requirements.append(
            {
                "code": "approved_selected_account_paid_source_export_required",
                "dataset": "paid_meta_ads",
                "row_count": len(paid_source_rows),
                "metrics": _row_metrics(paid_source_rows),
                "blocking_results": _result_counts(paid_source_rows),
                "can_run_now": False,
                "required_action": (
                    "Provide an approved selected-account May 2026 Meta Ads source export, "
                    "then dry-run `import_meta_paid_csv` if retained ADinsights rows are missing. "
                    "Do not substitute another tenant ad account."
                ),
                "scope_evidence": _safe_report_scope(bundle, "paid_meta_ads"),
            }
        )
    paid_import_rows = _matching_rows(
        unresolved_rows,
        dataset="paid_meta_ads",
        results={"blocked_missing_adinsights_value"},
    )
    if paid_import_rows:
        requirements.append(
            {
                "code": "selected_account_paid_backfill_or_import_required",
                "dataset": "paid_meta_ads",
                "row_count": len(paid_import_rows),
                "metrics": _row_metrics(paid_import_rows),
                "blocking_results": _result_counts(paid_import_rows),
                "can_run_now": False,
                "required_action": (
                    "Backfill the selected SLB Meta ad account or import the approved daily paid CSV, "
                    "then rerun parity. Do not substitute another tenant ad account."
                ),
                "scope_evidence": _safe_report_scope(bundle, "paid_meta_ads"),
            }
        )

    organic_source_rows = _matching_rows(
        unresolved_rows,
        dataset="organic_facebook_page",
        results={"blocked_missing_source_value", "blocked_missing_dashthis_value"},
    )
    if organic_source_rows:
        requirements.append(
            {
                "code": "approved_organic_page_post_source_values_required",
                "dataset": "organic_facebook_page",
                "row_count": len(organic_source_rows),
                "metrics": _row_metrics(organic_source_rows),
                "blocking_results": _result_counts(organic_source_rows),
                "can_run_now": False,
                "required_action": (
                    "Provide approved aggregate Facebook Page/Post source values for the current "
                    "SLB organic metrics, or preserve reviewed top-post examples as unmatched values "
                    "when they cannot represent monthly totals."
                ),
                "scope_evidence": _safe_report_scope(bundle, "organic_facebook_page"),
            }
        )

    organic_import_rows = [
        row
        for row in _matching_rows(
            unresolved_rows,
            dataset="organic_facebook_page",
            results={"blocked_missing_adinsights_value"},
        )
        if bool(row.get("has_source_value"))
        and not bool(row.get("has_adinsights_value"))
    ]
    if organic_import_rows:
        organic_scope = _safe_report_scope(bundle, "organic_facebook_page")
        page_scope_present = bool(organic_scope.get("page_scope_present"))
        matched_page_count = _int_value(organic_scope.get("matched_page_count"))
        can_run_now = page_scope_present and matched_page_count > 0
        requirements.append(
            {
                "code": "tenant_owned_slb_page_required_for_organic_import",
                "dataset": "organic_facebook_page",
                "row_count": len(organic_import_rows),
                "metrics": _row_metrics(organic_import_rows),
                "blocking_results": _result_counts(organic_import_rows),
                "can_run_now": can_run_now,
                "required_action": (
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                "scope_evidence": organic_scope,
            }
        )

    content_source_rows = _matching_rows(
        unresolved_rows,
        dataset="content_ops",
        results={"blocked_missing_source_value", "blocked_missing_dashthis_value"},
    )
    if content_source_rows:
        requirements.append(
            {
                "code": "approved_content_ops_source_totals_required",
                "dataset": "content_ops",
                "row_count": len(content_source_rows),
                "metrics": _row_metrics(content_source_rows),
                "blocking_results": _result_counts(content_source_rows),
                "can_run_now": False,
                "required_action": (
                    "Provide an approved aggregate Content Ops source export for May 2026 totals. "
                    "Do not infer totals from top-post examples."
                ),
                "scope_evidence": {},
            }
        )
    content_import_rows = _matching_rows(
        unresolved_rows,
        dataset="content_ops",
        results={"blocked_missing_adinsights_value"},
    )
    if content_import_rows:
        requirements.append(
            {
                "code": "content_ops_import_or_backfill_required",
                "dataset": "content_ops",
                "row_count": len(content_import_rows),
                "metrics": _row_metrics(content_import_rows),
                "blocking_results": _result_counts(content_import_rows),
                "can_run_now": False,
                "required_action": (
                    "Import or backfill the approved aggregate Content Ops source totals for May 2026, "
                    "then rerun parity."
                ),
                "scope_evidence": {},
            }
        )

    semantic_rows = [
        row
        for row in unresolved_rows
        if str(row.get("result") or "") == "blocked_metric_semantics"
        and row not in organic_import_rows
    ]
    if semantic_rows:
        requirements.append(
            {
                "code": "metric_semantics_or_tolerance_confirmation_required",
                "dataset": "mixed",
                "row_count": len(semantic_rows),
                "metrics": _row_metrics(semantic_rows),
                "blocking_results": _result_counts(semantic_rows),
                "can_run_now": False,
                "required_action": (
                    "Confirm metric semantics, date/account filters, and accepted tolerances before approving parity."
                ),
                "scope_evidence": {},
            }
        )

    failed_rows = [
        row for row in unresolved_rows if str(row.get("result") or "") == "fail"
    ]
    if failed_rows:
        requirements.append(
            {
                "code": "parity_delta_investigation_required",
                "dataset": "mixed",
                "row_count": len(failed_rows),
                "metrics": _row_metrics(failed_rows),
                "blocking_results": _result_counts(failed_rows),
                "can_run_now": False,
                "required_action": (
                    "Investigate non-zero parity deltas before approving the fixed-target report."
                ),
                "scope_evidence": {},
            }
        )

    return {
        "ready_for_final_parity": not requirements and not unresolved_rows,
        "requirement_count": len(requirements),
        "requirements": requirements,
    }


def _blocking_next_actions(
    parity_completion_requirements: Mapping[str, Any],
) -> dict[str, Any]:
    requirements = (
        parity_completion_requirements.get("requirements")
        if isinstance(parity_completion_requirements.get("requirements"), list)
        else []
    )
    actions: list[dict[str, Any]] = []
    for row in requirements:
        if not isinstance(row, Mapping):
            continue
        action = {
            "code": str(row.get("code") or ""),
            "dataset": str(row.get("dataset") or ""),
            "metrics": _safe_string_list(row.get("metrics")),
            "blocking_results": {
                str(key): _int_value(value)
                for key, value in (
                    row.get("blocking_results")
                    if isinstance(row.get("blocking_results"), Mapping)
                    else {}
                ).items()
            },
            "can_run_now": bool(row.get("can_run_now")),
            "required_action": str(row.get("required_action") or ""),
        }
        scope_evidence = row.get("scope_evidence")
        if isinstance(scope_evidence, Mapping) and scope_evidence:
            action["scope_evidence"] = dict(scope_evidence)
        actions.append(action)
    ready_to_run_count = sum(1 for action in actions if action["can_run_now"])
    return {
        "action_count": len(actions),
        "ready_to_run_action_count": ready_to_run_count,
        "blocked_prerequisite_count": len(actions) - ready_to_run_count,
        "primary_next_action": actions[0]["required_action"] if actions else "",
        "actions": actions,
    }


def _matching_rows(
    rows: list[Mapping[str, Any]],
    *,
    dataset: str,
    results: set[str],
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("dataset") or "") == dataset
        and str(row.get("result") or "") in results
    ]


def _row_metrics(rows: list[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {str(row.get("metric") or "") for row in rows if str(row.get("metric") or "")}
    )


def _safe_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item)})


def _result_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        result = str(row.get("result") or "")
        if result:
            counts[result] = counts.get(result, 0) + 1
    return counts


def _safe_report_scope(bundle: Mapping[str, Any], dataset: str) -> dict[str, Any]:
    diagnostics = bundle.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return {}
    source_health = diagnostics.get("source_health")
    if not isinstance(source_health, Mapping):
        return {}
    report_scope = source_health.get("report_scope")
    if not isinstance(report_scope, Mapping):
        return {}
    scope = report_scope.get(dataset)
    if not isinstance(scope, Mapping):
        return {}
    scoped_rows = scope.get("scoped_rows")
    row_summary = (
        {
            "row_count": _int_value(scoped_rows.get("row_count"))
            if isinstance(scoped_rows, Mapping)
            else 0,
            "min_date": str(scoped_rows.get("min_date") or "")
            if isinstance(scoped_rows, Mapping)
            else "",
            "max_date": str(scoped_rows.get("max_date") or "")
            if isinstance(scoped_rows, Mapping)
            else "",
        }
        if isinstance(scoped_rows, Mapping)
        else {"row_count": 0, "min_date": "", "max_date": ""}
    )
    if dataset == "paid_meta_ads":
        credential_status = scope.get("credential_status")
        return {
            "account_scope_present": bool(scope.get("account_scope_present")),
            "client_scope_present": bool(scope.get("client_scope_present")),
            "backfill_status": str(scope.get("backfill_status") or ""),
            "credential_status": _safe_credential_status(credential_status),
            "scoped_rows": row_summary,
            "required_action": str(scope.get("required_action") or ""),
        }
    if dataset == "organic_facebook_page":
        return {
            "page_scope_present": bool(scope.get("page_scope_present")),
            "matched_page_count": _int_value(scope.get("matched_page_count")),
            "available_page_count": _int_value(scope.get("available_page_count")),
            "analyzable_page_count": _int_value(scope.get("analyzable_page_count")),
            "backfill_status": str(scope.get("backfill_status") or ""),
            "scoped_rows": row_summary,
            "required_action": str(scope.get("required_action") or ""),
        }
    return {}


def _safe_credential_status(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "status": str(value.get("status") or ""),
        "provider": str(value.get("provider") or ""),
        "matched": bool(value.get("matched")),
        "token_status": str(value.get("token_status") or ""),
        "last_validated_at": str(value.get("last_validated_at") or ""),
    }


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SLB Parity Comparison",
        "",
        f"- Preview hash: `{result.get('preview_hash') or ''}`",
        f"- Row count: `{result.get('row_count') or 0}`",
        f"- Result summary: `{json.dumps(result.get('result_summary') or {}, sort_keys=True)}`",
        f"- Unresolved rows: `{result.get('unresolved_row_count') or 0}`",
        f"- Missing source values: `{len(result.get('missing_source_values') or [])}`",
        f"- Unmatched source values: `{len(result.get('unmatched_source_values') or [])}`",
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
