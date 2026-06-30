"""Sanitized data-availability summaries for report evidence artifacts."""

from __future__ import annotations

from typing import Any, Mapping

from analytics.models import ReportDefinition
from analytics.reporting_availability import (
    ReportingAvailabilityError,
    build_report_data_availability,
)


def build_report_data_availability_evidence_summary(
    *, report: ReportDefinition, payload: Mapping[str, Any]
) -> dict[str, Any]:
    params = _availability_params(report=report, payload=payload)
    try:
        availability = build_report_data_availability(
            tenant=report.tenant, params=params
        )
    except ReportingAvailabilityError as exc:
        return {
            "schema_version": "report_data_availability.v1",
            "eligible_for_report_export": False,
            "error": {
                "status_code": exc.status_code,
                "messages": [str(error) for error in exc.errors],
            },
        }

    datasets = (
        availability.get("datasets")
        if isinstance(availability.get("datasets"), Mapping)
        else {}
    )
    return {
        "schema_version": availability.get("schema_version")
        or "report_data_availability.v1",
        "stored_aggregate_only": availability.get("stored_aggregate_only") is True,
        "no_live_provider_calls": availability.get("no_live_provider_calls") is True,
        "requested": availability.get("requested") or {},
        "blocking_datasets": [
            str(key) for key in availability.get("blocking_datasets", [])
        ],
        "warning_datasets": [
            str(key) for key in availability.get("warning_datasets", [])
        ],
        "eligible_for_report_export": availability.get("eligible_for_report_export")
        is True,
        "datasets": {
            str(dataset_key): _availability_dataset_summary(dataset)
            for dataset_key, dataset in datasets.items()
            if isinstance(dataset, Mapping)
        },
    }


def _availability_params(
    *, report: ReportDefinition, payload: Mapping[str, Any]
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if isinstance(report.filters, Mapping):
        params.update(report.filters)
    params.update({str(key): value for key, value in payload.items()})
    return params


def _availability_dataset_summary(dataset: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "dataset",
        "label",
        "coverage_status",
        "coverage_note",
        "row_count",
        "min_date",
        "max_date",
        "post_count",
        "published_post_count",
        "source_label",
    )
    summary = {key: dataset.get(key) for key in allowed_keys if key in dataset}
    coverage_gap = dataset.get("coverage_gap")
    if isinstance(coverage_gap, Mapping):
        summary["coverage_gap"] = _coverage_gap_summary(coverage_gap)
    scope_diagnostic = dataset.get("scope_diagnostic")
    if isinstance(scope_diagnostic, Mapping):
        summary["scope_diagnostic"] = _scope_diagnostic_summary(scope_diagnostic)
        out_of_scope_rows = _out_of_scope_paid_rows_summary(dataset, scope_diagnostic)
        if out_of_scope_rows:
            summary["out_of_scope_retained_rows"] = out_of_scope_rows
    return summary


def _coverage_gap_summary(coverage_gap: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "requested_day_count",
        "covered_day_count",
        "missing_day_count",
        "missing_start_date",
        "missing_end_date",
        "missing_dates_truncated",
        "has_leading_gap",
        "has_trailing_gap",
    )
    return {key: coverage_gap.get(key) for key in allowed_keys if key in coverage_gap}


def _scope_diagnostic_summary(scope_diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "code",
        "message",
        "required_action",
        "available_account_count",
        "client_id",
        "linked_meta_ad_account_ids",
    )
    summary = {
        key: scope_diagnostic.get(key)
        for key in allowed_keys
        if key in scope_diagnostic
    }
    requested_account = scope_diagnostic.get("requested_account")
    if isinstance(requested_account, Mapping):
        summary["requested_account"] = _requested_account_summary(requested_account)
    credential_status = scope_diagnostic.get("credential_status")
    if isinstance(credential_status, Mapping):
        summary["credential_status"] = _credential_status_summary(credential_status)
    return summary


def _out_of_scope_paid_rows_summary(
    dataset: Mapping[str, Any], scope_diagnostic: Mapping[str, Any]
) -> dict[str, Any]:
    if dataset.get("dataset") != "paid_meta_ads":
        return {}
    if scope_diagnostic.get("code") not in {
        "requested_account_no_rows",
        "client_scope_no_rows",
    }:
        return {}
    available_accounts = dataset.get("available_accounts")
    if not isinstance(available_accounts, list):
        return {}

    account_rows = [row for row in available_accounts if isinstance(row, Mapping)]
    row_count = sum(_safe_int(row.get("row_count")) for row in account_rows)
    if not account_rows or row_count <= 0:
        return {}

    min_dates = sorted(
        str(row.get("min_date")) for row in account_rows if row.get("min_date")
    )
    max_dates = sorted(
        str(row.get("max_date")) for row in account_rows if row.get("max_date")
    )
    return {
        "reason": "retained_meta_rows_exist_outside_requested_scope",
        "excluded_from_selected_scope": True,
        "account_count": len(account_rows),
        "row_count": row_count,
        "min_date": min_dates[0] if min_dates else None,
        "max_date": max_dates[-1] if max_dates else None,
        "selected_scope_row_count": _safe_int(dataset.get("row_count")),
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _requested_account_summary(requested_account: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = ("id", "account_id", "external_id", "name", "currency")
    return {
        key: requested_account.get(key)
        for key in allowed_keys
        if key in requested_account
    }


def _credential_status_summary(credential_status: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "status",
        "provider",
        "matched_account_id",
        "token_status",
        "last_validated_at",
    )
    return {
        key: credential_status.get(key)
        for key in allowed_keys
        if key in credential_status
    }
