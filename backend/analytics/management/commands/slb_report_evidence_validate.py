"""Validate offline SLB cancellation-readiness evidence artifacts."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError

from analytics.reporting_templates import get_template_export_policy


REQUIRED_DATASETS = {"paid_meta_ads", "organic_facebook_page", "content_ops"}
REQUIRED_PAGE_IDS = {
    "cover",
    "executive_summary",
    "paid_meta_ads",
    "organic_facebook",
    "top_posts",
    "content_activity",
    "recommendations",
    "appendix",
}
DEFAULT_REQUIRED_FORMATS = {"csv", "pdf", "png"}
VALIDATION_MODES = {"cancellation", "product_finish"}
ALLOWED_PARITY_RESULTS = {
    "pass",
    "fail",
    "blocked_missing_dashthis_value",
    "blocked_missing_source_value",
    "blocked_missing_adinsights_value",
    "blocked_metric_semantics",
}
BLOCKING_COVERAGE_STATUSES = {
    "permission_missing",
    "unsupported_metric",
    "missing_history",
    "not_previously_synced",
}
NO_DATA_PARITY_COVERAGE_STATUSES = {"missing_history", "not_previously_synced"}
SLB_ALLOWED_ORGANIC_RENDER_METRICS = {
    "page_follows",
    "post_reactions",
    "post_comments",
    "post_shares",
}
SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"bearer\s+[a-z0-9._~+/=-]{20,}",
        r"access_token",
        r"refresh_token",
        r"client_secret",
        r"page_token",
        r"private key",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bAIza[0-9A-Za-z_-]{20,}\b",
        r"\bya29\.[0-9A-Za-z_-]+",
        r"\bEAAG[0-9A-Za-z]+",
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        r"\buser_id\b",
        r"\bprofile_id\b",
        r"\bviewer_id\b",
        r"\bactor_id\b",
        r"raw_payload",
        r"raw-provider-payload",
    ]
]


class Command(BaseCommand):
    help = "Validate offline SLB evidence-bundle and parity-comparison artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--evidence-bundle", required=True)
        parser.add_argument("--parity-comparison", required=False)
        parser.add_argument(
            "--validation-mode",
            choices=sorted(VALIDATION_MODES),
            default="cancellation",
            help=(
                "Use cancellation for strict G6/G12 parity evidence; use "
                "product_finish to validate internal product readiness while "
                "treating parity/source comparison as optional."
            ),
        )
        parser.add_argument("--expected-start-date", required=False, default="")
        parser.add_argument("--expected-end-date", required=False, default="")
        parser.add_argument(
            "--required-export-format",
            action="append",
            dest="required_export_formats",
            default=None,
            choices=["csv", "pdf", "png"],
        )
        parser.add_argument("--format", choices=["json", "markdown"], default="json")

    def handle(self, *args, **options):
        bundle = _load_json_file(options["evidence_bundle"], expected="evidence bundle")
        parity = (
            _load_json_file(options["parity_comparison"], expected="parity comparison")
            if options.get("parity_comparison")
            else None
        )
        result = validate_evidence(
            bundle=bundle,
            parity=parity,
            expected_start_date=options.get("expected_start_date") or "",
            expected_end_date=options.get("expected_end_date") or "",
            validation_mode=options["validation_mode"],
            required_export_formats=set(
                options.get("required_export_formats") or DEFAULT_REQUIRED_FORMATS
            ),
        )
        if options["format"] == "markdown":
            self.stdout.write(_markdown(result))
        else:
            self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))


def validate_evidence(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    expected_start_date: str = "",
    expected_end_date: str = "",
    validation_mode: str = "cancellation",
    required_export_formats: set[str] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []
    required_export_formats = required_export_formats or DEFAULT_REQUIRED_FORMATS

    _check_bundle_schema(bundle, blockers, checks)
    _check_date_range(
        bundle=bundle,
        parity=parity,
        expected_start_date=expected_start_date,
        expected_end_date=expected_end_date,
        blockers=blockers,
        checks=checks,
    )
    _check_datasets(bundle, blockers, warnings, checks)
    _check_data_availability(bundle, blockers, checks)
    _check_source_health(bundle, blockers, checks)
    _check_rendering(bundle, blockers, checks)
    _check_exports(bundle, required_export_formats, blockers, checks)
    _check_parity(
        bundle,
        parity,
        blockers,
        warnings,
        checks,
        validation_mode=validation_mode,
    )
    _check_instagram_deferred(bundle, blockers, checks)
    _check_sensitive_payloads(
        bundle=bundle, parity=parity, blockers=blockers, checks=checks
    )

    export_evidence = _export_evidence_inventory(bundle)
    unresolved_parity = _unresolved_parity_inventory(parity)
    source_value_inventory = _source_value_inventory(parity)
    parity_completion_requirements = _parity_completion_requirements(
        bundle=bundle,
        parity=parity,
    )

    return {
        "schema_version": "slb_evidence_validation.v1",
        "validation_mode": validation_mode,
        "evidence": _evidence_identity(bundle=bundle, parity=parity),
        "readiness_status": "blocked"
        if blockers
        else "warning"
        if warnings
        else "pass",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "export_evidence": export_evidence,
        "unresolved_parity": unresolved_parity,
        "source_value_inventory": source_value_inventory,
        "parity_completion_requirements": parity_completion_requirements,
        "blocking_next_actions": _blocking_next_actions(
            parity_completion_requirements
        ),
        "checks": checks,
    }


def _load_json_file(path: str, *, expected: str) -> Any:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CommandError(f"{expected} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"{expected} file is not valid JSON: {path}") from exc


def _evidence_identity(
    *, bundle: Mapping[str, Any], parity: Mapping[str, Any] | None
) -> dict[str, Any]:
    parity_payload = parity or {}
    return {
        "report": bundle.get("report")
        if isinstance(bundle.get("report"), Mapping)
        else {},
        "date_range": bundle.get("date_range")
        if isinstance(bundle.get("date_range"), Mapping)
        else {},
        "preview_hash": str(bundle.get("preview_hash") or ""),
        "parity_preview_hash": str(parity_payload.get("preview_hash") or ""),
    }


def _check_bundle_schema(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    if bundle.get("schema_version") != "slb_evidence_bundle.v1":
        blockers.append(
            _finding(
                "bundle_schema",
                "Evidence bundle schema_version must be slb_evidence_bundle.v1.",
            )
        )
        return
    checks.append(_passed("bundle_schema", "Evidence bundle schema is recognized."))


def _check_date_range(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    expected_start_date: str,
    expected_end_date: str,
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    date_range = (
        bundle.get("date_range")
        if isinstance(bundle.get("date_range"), Mapping)
        else {}
    )
    if date_range.get("date_range") != "custom":
        blockers.append(
            _finding(
                "date_range", "Evidence bundle must use a bounded custom date range."
            )
        )
    start_date = str(date_range.get("start_date") or "")
    end_date = str(date_range.get("end_date") or "")
    if not start_date or not end_date:
        blockers.append(
            _finding(
                "date_range", "Evidence bundle start_date and end_date are required."
            )
        )
    if expected_start_date and start_date != expected_start_date:
        blockers.append(
            _finding(
                "date_range",
                "Evidence bundle start_date does not match expected G1 start date.",
            )
        )
    if expected_end_date and end_date != expected_end_date:
        blockers.append(
            _finding(
                "date_range",
                "Evidence bundle end_date does not match expected G1 end date.",
            )
        )
    if parity is not None:
        parity_range = (
            parity.get("date_range")
            if isinstance(parity.get("date_range"), Mapping)
            else {}
        )
        if parity_range != date_range:
            blockers.append(
                _finding(
                    "date_range",
                    "Parity comparison date_range does not match evidence bundle.",
                )
            )
    checks.append(_passed("date_range", "Date-range consistency check completed."))


def _check_datasets(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    warning_only_allowed = bundle.get("export_ready") is True and not bundle.get(
        "blocking_reasons"
    )
    coverage_summary = (
        bundle.get("coverage_summary")
        if isinstance(bundle.get("coverage_summary"), Mapping)
        else {}
    )
    datasets = (
        coverage_summary.get("datasets")
        if isinstance(coverage_summary.get("datasets"), list)
        else []
    )
    by_dataset = {
        str(row.get("dataset") or ""): row
        for row in datasets
        if isinstance(row, Mapping) and row.get("dataset")
    }
    missing = REQUIRED_DATASETS - set(by_dataset)
    if missing:
        blockers.append(
            _finding(
                "coverage_datasets",
                f"Missing required datasets: {', '.join(sorted(missing))}.",
            )
        )
    for dataset, row in by_dataset.items():
        statuses = (
            row.get("statuses") if isinstance(row.get("statuses"), Mapping) else {}
        )
        blocking_statuses = sorted(set(statuses) & BLOCKING_COVERAGE_STATUSES)
        warning_only_statuses = _warning_only_coverage_statuses(bundle, dataset)
        hard_blocking_statuses = [
            status
            for status in blocking_statuses
            if status not in warning_only_statuses
        ]
        policy_warning_statuses = [
            status for status in blocking_statuses if status in warning_only_statuses
        ]
        if policy_warning_statuses and not warning_only_allowed:
            hard_blocking_statuses.extend(policy_warning_statuses)
            policy_warning_statuses = []
        if blocking_statuses:
            target = (
                warnings
                if policy_warning_statuses and not hard_blocking_statuses
                else blockers
            )
            target.append(
                _finding(
                    "coverage_status",
                    _coverage_status_message(
                        dataset=dataset,
                        blocking_statuses=hard_blocking_statuses,
                        warning_statuses=policy_warning_statuses,
                    ),
                )
            )
        if (
            "partial" in statuses
            or "stale" in statuses
            or "source_disconnected" in statuses
        ):
            warnings.append(
                _finding(
                    "coverage_status",
                    f"{dataset} has warning coverage statuses that require reviewer explanation.",
                )
            )
        if int(row.get("row_count") or 0) <= 0:
            if (
                warning_only_allowed
                and policy_warning_statuses
                and not hard_blocking_statuses
            ):
                warnings.append(
                    _finding(
                        "coverage_row_count",
                        f"{dataset} has no aggregate rows and is warning-only for this export-ready bundle.",
                    )
                )
            else:
                blockers.append(
                    _finding("coverage_row_count", f"{dataset} has no aggregate rows.")
                )
    checks.append(
        _passed("coverage_datasets", "Required dataset coverage check completed.")
    )


def _check_data_availability(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    availability = bundle.get("data_availability")
    if not isinstance(availability, Mapping):
        checks.append(
            _passed(
                "data_availability",
                "Report data-availability summary is absent; legacy evidence compatibility mode.",
            )
        )
        return
    if availability.get("schema_version") != "report_data_availability.v1":
        blockers.append(
            _finding(
                "data_availability",
                "data_availability schema_version must be report_data_availability.v1.",
            )
        )
        return
    if availability.get("stored_aggregate_only") is not True:
        blockers.append(
            _finding(
                "data_availability",
                "data_availability must confirm stored_aggregate_only.",
            )
        )
    if availability.get("no_live_provider_calls") is not True:
        blockers.append(
            _finding(
                "data_availability",
                "data_availability must confirm no_live_provider_calls.",
            )
        )
    _check_data_availability_date_range(bundle, availability, blockers)
    availability_eligible = availability.get("eligible_for_report_export") is True
    bundle_export_ready = bundle.get("export_ready") is True
    if availability_eligible != bundle_export_ready:
        blockers.append(
            _finding(
                "data_availability_export_ready",
                "data_availability eligibility does not match evidence bundle export_ready.",
            )
        )
    blocking_datasets = {
        str(dataset)
        for dataset in availability.get("blocking_datasets", [])
        if str(dataset)
    }
    datasets = (
        availability.get("datasets")
        if isinstance(availability.get("datasets"), Mapping)
        else {}
    )
    paid = (
        datasets.get("paid_meta_ads")
        if isinstance(datasets.get("paid_meta_ads"), Mapping)
        else {}
    )
    if paid:
        _check_paid_out_of_scope_retained_rows(paid, blockers)
    if "paid_meta_ads" in blocking_datasets:
        _check_paid_data_availability(paid, blockers)
    checks.append(
        _passed(
            "data_availability", "Report data-availability summary check completed."
        )
    )


def _check_data_availability_date_range(
    bundle: Mapping[str, Any],
    availability: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    bundle_range = (
        bundle.get("date_range")
        if isinstance(bundle.get("date_range"), Mapping)
        else {}
    )
    requested = (
        availability.get("requested")
        if isinstance(availability.get("requested"), Mapping)
        else {}
    )
    for key in ("start_date", "end_date"):
        if str(bundle_range.get(key) or "") != str(requested.get(key) or ""):
            blockers.append(
                _finding(
                    "data_availability_date_range",
                    f"data_availability requested.{key} does not match evidence bundle date_range.",
                )
            )


def _check_paid_data_availability(
    paid: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    diagnostic = (
        paid.get("scope_diagnostic")
        if isinstance(paid.get("scope_diagnostic"), Mapping)
        else {}
    )
    if not diagnostic:
        blockers.append(
            _finding(
                "data_availability_paid_scope",
                "Blocked paid_meta_ads availability must include a selected account/client scope diagnostic.",
            )
        )
        return
    credential_status = (
        diagnostic.get("credential_status")
        if isinstance(diagnostic.get("credential_status"), Mapping)
        else {}
    )
    if credential_status.get("status") == "missing":
        blockers.append(
            _finding(
                "data_availability_paid_credential",
                "Selected paid Meta account has no retained credential; reconnect/select that account and run paid backfill before export evidence.",
            )
        )


def _check_paid_out_of_scope_retained_rows(
    paid: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    out_of_scope = (
        paid.get("out_of_scope_retained_rows")
        if isinstance(paid.get("out_of_scope_retained_rows"), Mapping)
        else {}
    )
    if not out_of_scope:
        return

    invalid_messages: list[str] = []
    if out_of_scope.get("reason") != "retained_meta_rows_exist_outside_requested_scope":
        invalid_messages.append("reason must identify excluded retained Meta rows")
    if out_of_scope.get("excluded_from_selected_scope") is not True:
        invalid_messages.append("excluded_from_selected_scope must be true")
    if _int_value(out_of_scope.get("account_count")) <= 0:
        invalid_messages.append("account_count must be aggregate and positive")
    if _int_value(out_of_scope.get("row_count")) <= 0:
        invalid_messages.append("row_count must be aggregate and positive")
    if _int_value(out_of_scope.get("selected_scope_row_count")) != 0:
        invalid_messages.append("selected_scope_row_count must remain zero")
    if _contains_forbidden_out_of_scope_detail(out_of_scope):
        invalid_messages.append(
            "out-of-scope summary must not expose account identifiers, names, or row-level account details"
        )
    if invalid_messages:
        blockers.append(
            _finding(
                "data_availability_paid_out_of_scope_rows",
                "Invalid paid_meta_ads out_of_scope_retained_rows evidence: "
                + "; ".join(invalid_messages)
                + ".",
            )
        )


def _contains_forbidden_out_of_scope_detail(value: object) -> bool:
    forbidden_keys = {
        "id",
        "account_id",
        "external_id",
        "name",
        "account_name",
        "accounts",
        "available_accounts",
        "requested_account",
        "currency",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in forbidden_keys:
                return True
            if _contains_forbidden_out_of_scope_detail(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_out_of_scope_detail(item) for item in value)
    return False


def _check_source_health(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    diagnostics = (
        bundle.get("diagnostics")
        if isinstance(bundle.get("diagnostics"), Mapping)
        else {}
    )
    source_health = (
        diagnostics.get("source_health")
        if isinstance(diagnostics.get("source_health"), Mapping)
        else {}
    )
    if source_health.get("schema_version") != "slb_source_health.v1":
        blockers.append(
            _finding(
                "source_health",
                "Diagnostics source_health schema_version must be slb_source_health.v1.",
            )
        )
        return
    if source_health.get("stored_aggregate_only") is not True:
        blockers.append(
            _finding(
                "source_health", "source_health must confirm stored_aggregate_only."
            )
        )
    if source_health.get("no_live_provider_calls") is not True:
        blockers.append(
            _finding(
                "source_health", "source_health must confirm no_live_provider_calls."
            )
        )

    for key in [
        "meta_credentials",
        "meta_page_connection",
        "meta_airbyte",
        "stored_assets",
        "stored_rows",
    ]:
        if not isinstance(source_health.get(key), Mapping):
            blockers.append(
                _finding("source_health", f"source_health.{key} is required.")
            )

    stored_rows = (
        source_health.get("stored_rows")
        if isinstance(source_health.get("stored_rows"), Mapping)
        else {}
    )
    for key in [
        "paid_meta_ads",
        "organic_facebook_page",
        "organic_facebook_posts",
        "content_ops",
    ]:
        row = stored_rows.get(key) if isinstance(stored_rows.get(key), Mapping) else {}
        if "row_count" not in row:
            blockers.append(
                _finding(
                    "source_health",
                    f"source_health.stored_rows.{key}.row_count is required.",
                )
            )

    _check_source_health_report_scope(source_health, blockers)

    actions = source_health.get("recommended_next_actions")
    if not isinstance(actions, list) or not actions:
        blockers.append(
            _finding(
                "source_health",
                "source_health.recommended_next_actions must be non-empty.",
            )
        )

    checks.append(
        _passed(
            "source_health", "Diagnostics source-health support proof check completed."
        )
    )


def _check_source_health_report_scope(
    source_health: Mapping[str, Any], blockers: list[dict[str, str]]
) -> None:
    report_scope = source_health.get("report_scope")
    if not isinstance(report_scope, Mapping):
        return
    if report_scope.get("schema_version") != "slb_report_scope_health.v1":
        blockers.append(
            _finding(
                "source_health_report_scope",
                "source_health.report_scope schema_version must be slb_report_scope_health.v1.",
            )
        )
        return
    for dataset in ["paid_meta_ads", "organic_facebook_page"]:
        scope = (
            report_scope.get(dataset)
            if isinstance(report_scope.get(dataset), Mapping)
            else {}
        )
        if not scope:
            blockers.append(
                _finding(
                    "source_health_report_scope",
                    f"source_health.report_scope.{dataset} is required.",
                )
            )
            continue
        for key in ["backfill_status", "required_action", "scoped_rows"]:
            if key not in scope:
                blockers.append(
                    _finding(
                        "source_health_report_scope",
                        f"source_health.report_scope.{dataset}.{key} is required.",
                    )
                )
        scoped_rows = (
            scope.get("scoped_rows")
            if isinstance(scope.get("scoped_rows"), Mapping)
            else {}
        )
        if "row_count" not in scoped_rows:
            blockers.append(
                _finding(
                    "source_health_report_scope",
                    f"source_health.report_scope.{dataset}.scoped_rows.row_count is required.",
                )
            )


def _check_rendering(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    rendering = (
        bundle.get("rendering") if isinstance(bundle.get("rendering"), Mapping) else {}
    )
    pages = rendering.get("pages") if isinstance(rendering.get("pages"), list) else []
    page_ids = {
        str(page.get("id") or "") for page in pages if isinstance(page, Mapping)
    }
    missing = REQUIRED_PAGE_IDS - page_ids
    if missing:
        blockers.append(
            _finding(
                "rendering_pages",
                f"Missing required report pages: {', '.join(sorted(missing))}.",
            )
        )
    if int(rendering.get("widget_count") or 0) <= 0:
        blockers.append(
            _finding("rendering_widgets", "Rendering summary has no widgets.")
        )
    _check_rendering_widget_inventory(rendering, blockers)
    checks.append(_passed("rendering", "Report rendering summary check completed."))


def _check_rendering_widget_inventory(
    rendering: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    widgets = (
        rendering.get("widgets") if isinstance(rendering.get("widgets"), list) else []
    )
    if not widgets:
        return
    expected_count = int(rendering.get("widget_count") or 0)
    if expected_count and len(widgets) != expected_count:
        blockers.append(
            _finding(
                "rendering_widget_inventory",
                (
                    "Rendering widget inventory count does not match "
                    f"widget_count ({len(widgets)} != {expected_count})."
                ),
            )
        )

    legacy_widgets = []
    has_organic_availability_note = False
    for widget in widgets:
        if not isinstance(widget, Mapping):
            continue
        note = widget.get("note") if isinstance(widget.get("note"), Mapping) else {}
        if bool(note.get("mentions_reach_impressions_unavailable")):
            has_organic_availability_note = True
        if str(widget.get("dataset") or "") != "organic_facebook_page":
            continue
        declared_metrics = {
            str(metric)
            for metric in widget.get("declared_metrics", [])
            if str(metric or "").strip()
        }
        legacy_metrics = sorted(declared_metrics - SLB_ALLOWED_ORGANIC_RENDER_METRICS)
        if legacy_metrics:
            legacy_widgets.append(
                f"{widget.get('widget_id') or 'unknown'}: {', '.join(legacy_metrics)}"
            )
    if legacy_widgets:
        blockers.append(
            _finding(
                "rendering_legacy_organic_metrics",
                (
                    "SLB organic widgets still declare metrics outside the "
                    "approved Page follows/post engagement set: "
                    f"{'; '.join(legacy_widgets)}."
                ),
            )
        )
    if not has_organic_availability_note:
        blockers.append(
            _finding(
                "rendering_organic_availability_note",
                (
                    "SLB rendering inventory is missing the client-facing "
                    "reach/impressions unavailable note."
                ),
            )
        )


def _check_exports(
    bundle: Mapping[str, Any],
    required_formats: set[str],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    exports = bundle.get("exports") if isinstance(bundle.get("exports"), list) else []
    completed_by_format = {}
    dry_run_rendered = False
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    if not bundle_hash:
        blockers.append(
            _finding(
                "preview_hash",
                "Evidence bundle preview_hash is required for export reproducibility.",
            )
        )
    for row in exports:
        if not isinstance(row, Mapping):
            continue
        export_format = str(row.get("format") or "")
        preview_hash = str(row.get("preview_hash") or "").strip()
        snapshot_preview_hash = str(row.get("snapshot_preview_hash") or "").strip()
        completed_non_empty = (
            row.get("status") == "completed"
            and row.get("artifact_present") is True
            and int(row.get("artifact_size_bytes") or 0) > 0
        )
        hash_reproducible = True
        if completed_non_empty:
            current_hash_candidate = (
                not bundle_hash or not preview_hash or preview_hash == bundle_hash
            )
            if not preview_hash:
                blockers.append(
                    _finding(
                        "export_hash",
                        f"{export_format} export preview_hash is required.",
                    )
                )
                hash_reproducible = False
            elif bundle_hash and preview_hash != bundle_hash:
                hash_reproducible = False
            if current_hash_candidate and not snapshot_preview_hash:
                blockers.append(
                    _finding(
                        "export_hash",
                        f"{export_format} export snapshot_preview_hash is required.",
                    )
                )
                hash_reproducible = False
            elif (
                current_hash_candidate
                and bundle_hash
                and snapshot_preview_hash != bundle_hash
            ):
                blockers.append(
                    _finding(
                        "export_hash",
                        f"{export_format} snapshot_preview_hash differs from bundle.",
                    )
                )
                hash_reproducible = False
        if (
            completed_non_empty
            and hash_reproducible
            and not _is_scheduled_dry_run_export(row)
            and export_format not in completed_by_format
        ):
            completed_by_format[export_format] = row
        delivery_status = (
            row.get("delivery_status")
            if isinstance(row.get("delivery_status"), Mapping)
            else {}
        )
        if (
            _is_scheduled_dry_run_export(row)
            and delivery_status.get("status") == "rendered"
            and (not bundle_hash or preview_hash == bundle_hash)
        ):
            dry_run_rendered = True
    missing_formats = required_formats - set(completed_by_format)
    if missing_formats:
        blockers.append(
            _finding(
                "exports",
                f"Missing completed non-empty exports for: {', '.join(sorted(missing_formats))}.",
            )
        )
    if not dry_run_rendered:
        blockers.append(
            _finding(
                "scheduled_dry_run", "No rendered scheduled dry-run evidence found."
            )
        )
    checks.append(
        _passed("exports", "Export and scheduled dry-run evidence check completed.")
    )


def _export_evidence_inventory(bundle: Mapping[str, Any]) -> dict[str, Any]:
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    selected = _selected_current_export_rows(bundle)
    rows = [_export_evidence_row(row) for _, row in sorted(selected.items())]
    return {
        "preview_hash": bundle_hash,
        "selected_completed_format_count": len(rows),
        "selected_completed_exports": rows,
        "selected_layout_source_count": sum(
            1 for row in rows if str(row.get("report_layout_source") or "").strip()
        ),
    }


def _selected_current_export_rows(
    bundle: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    exports = bundle.get("exports") if isinstance(bundle.get("exports"), list) else []
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    selected: dict[str, Mapping[str, Any]] = {}
    for row in exports:
        if not isinstance(row, Mapping):
            continue
        export_format = str(row.get("format") or "")
        if not export_format or export_format in selected:
            continue
        if _is_scheduled_dry_run_export(row):
            continue
        preview_hash = str(row.get("preview_hash") or "").strip()
        snapshot_preview_hash = str(row.get("snapshot_preview_hash") or "").strip()
        completed_non_empty = (
            row.get("status") == "completed"
            and row.get("artifact_present") is True
            and int(row.get("artifact_size_bytes") or 0) > 0
        )
        current_hash = bool(
            bundle_hash
            and preview_hash == bundle_hash
            and snapshot_preview_hash == bundle_hash
        )
        if completed_non_empty and current_hash:
            selected[export_format] = row
    return selected


def _is_scheduled_dry_run_export(row: Mapping[str, Any]) -> bool:
    delivery_status = row.get("delivery_status")
    return (
        isinstance(delivery_status, Mapping) and delivery_status.get("mode") == "dry_run"
    )


def _export_evidence_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "format": str(row.get("format") or ""),
        "status": str(row.get("status") or ""),
        "artifact_size_bytes": int(row.get("artifact_size_bytes") or 0),
        "preview_hash": str(row.get("preview_hash") or ""),
        "snapshot_preview_hash": str(row.get("snapshot_preview_hash") or ""),
        "source": str(row.get("source") or ""),
        "row_count": row.get("row_count"),
        "report_layout_source": str(row.get("report_layout_source") or ""),
        "report_layout_governed_widget_append_count": row.get(
            "report_layout_governed_widget_append_count"
        ),
    }


def _check_parity(
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    checks: list[dict[str, str]],
    *,
    validation_mode: str,
) -> None:
    _check_no_data_parity_values(
        bundle.get("parity_rows"),
        artifact_label="Evidence bundle",
        blockers=blockers,
    )
    if parity is None:
        if validation_mode == "product_finish":
            warnings.append(
                _finding(
                    "parity_optional",
                    (
                        "Parity comparison artifact is optional for product-finish "
                        "validation and remains required for cancellation evidence."
                    ),
                )
            )
            checks.append(
                _passed(
                    "product_finish_parity",
                    "Product-finish validation treated missing parity as optional.",
                )
            )
        else:
            blockers.append(
                _finding("parity", "Parity comparison artifact is required.")
            )
        return
    parity_blockers = blockers
    if validation_mode == "product_finish":
        parity_blockers = []
    if parity.get("schema_version") != "slb_parity_comparison.v1":
        parity_blockers.append(
            _finding(
                "parity_schema",
                "Parity comparison schema_version must be slb_parity_comparison.v1.",
            )
        )
    bundle_report = (
        bundle.get("report") if isinstance(bundle.get("report"), Mapping) else {}
    )
    parity_report = (
        parity.get("report") if isinstance(parity.get("report"), Mapping) else {}
    )
    _check_parity_report_identity(bundle_report, parity_report, parity_blockers)
    bundle_hash = str(bundle.get("preview_hash") or "").strip()
    parity_hash = str(parity.get("preview_hash") or "").strip()
    if not parity_hash:
        parity_blockers.append(
            _finding("parity_hash", "Parity comparison preview_hash is required.")
        )
    elif bundle_hash and parity_hash != bundle_hash:
        parity_blockers.append(
            _finding(
                "parity_hash",
                "Parity comparison preview_hash does not match evidence bundle.",
            )
        )
    rows = parity.get("rows") if isinstance(parity.get("rows"), list) else []
    declared_row_count = _int_value(parity.get("row_count"))
    actual_row_count = len([row for row in rows if isinstance(row, Mapping)])
    if declared_row_count <= 0:
        parity_blockers.append(
            _finding("parity_rows", "Parity comparison has no rows.")
        )
    elif declared_row_count != actual_row_count:
        parity_blockers.append(
            _finding(
                "parity_rows", "Parity comparison row_count does not match rows length."
            )
        )
    _check_no_data_parity_values(
        rows,
        artifact_label="Parity comparison",
        blockers=parity_blockers,
    )
    summary = (
        parity.get("result_summary")
        if isinstance(parity.get("result_summary"), Mapping)
        else {}
    )
    declared_summary = {str(key): _int_value(value) for key, value in summary.items()}
    actual_summary: dict[str, int] = {}
    unsupported_results: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        result = str(row.get("result") or "").strip()
        if result:
            actual_summary[result] = actual_summary.get(result, 0) + 1
            if result not in ALLOWED_PARITY_RESULTS:
                unsupported_results.add(result)
        if result == "pass":
            _validate_pass_parity_row(index, row, parity_blockers)
    if unsupported_results:
        parity_blockers.append(
            _finding(
                "parity_results",
                f"Parity has unsupported result labels: {', '.join(sorted(unsupported_results))}.",
            )
        )
    if actual_summary and declared_summary != actual_summary:
        parity_blockers.append(
            _finding(
                "parity_results", "Parity result_summary does not match row results."
            )
        )
    if declared_summary.get("pass", 0) <= 0:
        parity_blockers.append(
            _finding(
                "parity_results",
                "Parity comparison must include at least one passing row.",
            )
        )
    if declared_summary.get("blocked_missing_source_value", 0) > 0:
        _check_missing_source_provenance(parity, parity_blockers)
        _check_missing_source_inventory(parity, rows, parity_blockers)
    blocked_or_failed = {
        key: value
        for key, value in declared_summary.items()
        if (str(key).startswith("blocked_") or key == "fail") and value > 0
    }
    if blocked_or_failed:
        parity_blockers.append(
            _finding(
                "parity_results", f"Parity has unresolved rows: {blocked_or_failed}."
            )
        )
    if validation_mode == "product_finish" and parity_blockers:
        warnings.append(
            _finding(
                "parity_optional",
                (
                    "Optional parity comparison has unresolved cancellation-only "
                    f"findings: {_finding_summary(parity_blockers)}."
                ),
            )
        )
        checks.append(
            _passed(
                "product_finish_parity",
                "Product-finish validation treated parity findings as optional.",
            )
        )
        return
    checks.append(_passed("parity", "Parity comparison check completed."))


def _check_no_data_parity_values(
    rows: object,
    *,
    artifact_label: str,
    blockers: list[dict[str, str]],
) -> None:
    if not isinstance(rows, list):
        return
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        coverage_status = str(row.get("coverage_status") or "")
        if (
            coverage_status in NO_DATA_PARITY_COVERAGE_STATUSES
            and row.get("adinsights_value") is not None
        ):
            blockers.append(
                _finding(
                    "parity_no_data_value",
                    (
                        f"{artifact_label} row {index} has coverage_status "
                        f"{coverage_status} but a non-null adinsights_value."
                    ),
                )
            )


def _check_missing_source_provenance(
    parity: Mapping[str, Any], blockers: list[dict[str, str]]
) -> None:
    provenance = parity.get("source_search_provenance")
    if not isinstance(provenance, list) or not provenance:
        blockers.append(
            _finding(
                "parity_source_provenance",
                "Parity rows with blocked_missing_source_value require source_search_provenance search proof.",
            )
        )
        return
    has_substantive_entry = False
    for entry in provenance:
        if not isinstance(entry, Mapping):
            continue
        source = str(entry.get("source") or "").strip()
        result = str(entry.get("result") or "").strip()
        if source and result and source != "redacted" and result != "redacted":
            has_substantive_entry = True
            break
    if not has_substantive_entry:
        blockers.append(
            _finding(
                "parity_source_provenance",
                "source_search_provenance entries must include non-redacted source and result text.",
            )
        )


def _check_missing_source_inventory(
    parity: Mapping[str, Any], rows: list[Any], blockers: list[dict[str, str]]
) -> None:
    source_missing_rows = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("result") or "") == "blocked_missing_source_value"
    ]
    if not source_missing_rows:
        return
    inventory = (
        parity.get("missing_source_values")
        if isinstance(parity.get("missing_source_values"), list)
        else []
    )
    if not inventory:
        blockers.append(
            _finding(
                "parity_source_inventory",
                "Parity rows with blocked_missing_source_value require matching missing_source_values inventory entries.",
            )
        )
        return

    inventory_by_key: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for entry in inventory:
        if not isinstance(entry, Mapping):
            continue
        key = _source_inventory_key(entry)
        if key[0] and key[2]:
            inventory_by_key.setdefault(key, []).append(entry)

    missing_entries: list[str] = []
    missing_reasons: list[str] = []
    for row in source_missing_rows:
        key = _source_inventory_key(row)
        label = _source_inventory_label(row)
        entries = inventory_by_key.get(key, [])
        if not entries:
            missing_entries.append(label)
            continue
        if not any(str(entry.get("reason") or "").strip() for entry in entries):
            missing_reasons.append(label)

    if missing_entries:
        blockers.append(
            _finding(
                "parity_source_inventory",
                (
                    "missing_source_values does not cover unresolved source-missing rows: "
                    f"{', '.join(sorted(missing_entries))}."
                ),
            )
        )
    if missing_reasons:
        blockers.append(
            _finding(
                "parity_source_inventory",
                (
                    "missing_source_values entries must include reason text for unresolved "
                    f"source-missing rows: {', '.join(sorted(missing_reasons))}."
                ),
            )
        )

def _source_inventory_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("dataset") or "").strip(),
        str(row.get("widget_id") or "").strip(),
        str(row.get("metric") or "").strip(),
    )


def _source_inventory_label(row: Mapping[str, Any]) -> str:
    dataset, widget_id, metric = _source_inventory_key(row)
    return ".".join(part for part in [dataset, widget_id, metric] if part)


def _validate_pass_parity_row(
    index: int, row: Mapping[str, Any], blockers: list[dict[str, str]]
) -> None:
    for key in ["dataset", "widget_id", "metric", "label"]:
        if not str(row.get(key) or "").strip():
            blockers.append(
                _finding(
                    "parity_pass_row", f"Parity pass row {index} is missing {key}."
                )
            )
    for key in ["adinsights_value", "source_value", "absolute_delta"]:
        if row.get(key) is None:
            blockers.append(
                _finding(
                    "parity_pass_row", f"Parity pass row {index} is missing {key}."
                )
            )
    for key in [
        "adinsights_value",
        "source_value",
        "absolute_delta",
        "absolute_delta_magnitude",
        "percentage_delta",
    ]:
        if row.get(key) is not None and _finite_decimal_or_none(row.get(key)) is None:
            blockers.append(
                _finding(
                    "parity_pass_row",
                    f"Parity pass row {index} has non-finite or non-numeric {key}.",
                )
            )
    has_tolerance = (
        row.get("accepted_tolerance_percent") is not None
        or row.get("accepted_tolerance_absolute") is not None
    )
    if not has_tolerance:
        blockers.append(
            _finding(
                "parity_pass_row",
                f"Parity pass row {index} is missing accepted tolerance.",
            )
        )
    for key in ["accepted_tolerance_percent", "accepted_tolerance_absolute"]:
        if row.get(key) is not None and _finite_decimal_or_none(row.get(key)) is None:
            blockers.append(
                _finding(
                    "parity_pass_row",
                    f"Parity pass row {index} has non-finite or non-numeric {key}.",
                )
            )
    if not str(row.get("explanation") or "").strip():
        blockers.append(
            _finding(
                "parity_pass_row", f"Parity pass row {index} is missing explanation."
            )
        )


def _finite_decimal_or_none(value: object) -> Decimal | None:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _unresolved_parity_inventory(parity: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parity, Mapping):
        return {"row_count": 0, "by_result": {}, "by_dataset": {}, "rows": []}
    unresolved_rows = parity.get("unresolved_rows")
    if isinstance(unresolved_rows, list):
        source_rows = [row for row in unresolved_rows if isinstance(row, Mapping)]
    else:
        parity_rows = parity.get("rows") if isinstance(parity.get("rows"), list) else []
        source_rows = [
            row
            for row in parity_rows
            if isinstance(row, Mapping) and str(row.get("result") or "") != "pass"
        ]
    by_result: dict[str, int] = {}
    by_dataset: dict[str, dict[str, int]] = {}
    normalized_rows: list[dict[str, Any]] = []
    for row in source_rows:
        normalized = _unresolved_parity_row(row)
        normalized_rows.append(normalized)
        result = normalized["result"]
        dataset = normalized["dataset"]
        by_result[result] = by_result.get(result, 0) + 1
        dataset_summary = by_dataset.setdefault(dataset, {})
        dataset_summary[result] = dataset_summary.get(result, 0) + 1
    return {
        "row_count": len(normalized_rows),
        "by_result": by_result,
        "by_dataset": by_dataset,
        "rows": normalized_rows,
    }


def _unresolved_parity_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset": str(row.get("dataset") or ""),
        "widget_id": str(row.get("widget_id") or ""),
        "metric": str(row.get("metric") or ""),
        "label": str(row.get("label") or ""),
        "result": str(row.get("result") or ""),
        "coverage_status": str(row.get("coverage_status") or ""),
        "source_label": str(row.get("source_label") or ""),
        "has_adinsights_value": bool(row.get("has_adinsights_value"))
        if "has_adinsights_value" in row
        else row.get("adinsights_value") is not None,
        "has_source_value": bool(row.get("has_source_value"))
        if "has_source_value" in row
        else row.get("source_value") is not None,
        "explanation": str(row.get("explanation") or ""),
        "recommended_next_action": str(row.get("recommended_next_action") or ""),
    }


def _source_value_inventory(parity: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parity, Mapping):
        return {
            "missing_source_value_count": 0,
            "missing_source_values": [],
            "unmatched_source_value_count": 0,
            "unmatched_source_values": [],
        }
    missing_source_values = _source_value_rows(parity.get("missing_source_values"))
    unmatched_source_values = _source_value_rows(parity.get("unmatched_source_values"))
    return {
        "missing_source_value_count": len(missing_source_values),
        "missing_source_values": missing_source_values,
        "unmatched_source_value_count": len(unmatched_source_values),
        "unmatched_source_values": unmatched_source_values,
    }


def _source_value_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _parity_completion_requirements(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    unresolved = _unresolved_parity_inventory(parity)
    unresolved_rows = unresolved.get("rows") if isinstance(unresolved, Mapping) else []
    source_rows = [row for row in unresolved_rows if isinstance(row, Mapping)]
    parity_requirements = (
        parity.get("parity_completion_requirements")
        if isinstance(parity, Mapping)
        and isinstance(parity.get("parity_completion_requirements"), Mapping)
        else {}
    )
    if parity_requirements:
        requirements = _normalized_completion_requirements(
            parity_requirements.get("requirements"),
            bundle=bundle,
        )
    else:
        requirements = _derived_completion_requirements(
            unresolved_rows=source_rows,
            bundle=bundle,
        )
    return {
        "ready_for_final_parity": not requirements and not source_rows,
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


def _normalized_completion_requirements(
    value: object,
    *,
    bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        dataset = str(row.get("dataset") or "")
        normalized.append(
            {
                "code": str(row.get("code") or ""),
                "dataset": dataset,
                "row_count": _int_value(row.get("row_count")),
                "metrics": _safe_string_list(row.get("metrics")),
                "blocking_results": {
                    str(key): _int_value(count)
                    for key, count in (
                        row.get("blocking_results")
                        if isinstance(row.get("blocking_results"), Mapping)
                        else {}
                    ).items()
                },
                "can_run_now": bool(row.get("can_run_now")),
                "required_action": str(row.get("required_action") or ""),
                "scope_evidence": _scope_evidence_for_dataset(bundle, dataset),
            }
        )
    return normalized


def _derived_completion_requirements(
    *,
    unresolved_rows: list[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    paid_rows = _matching_unresolved_rows(
        unresolved_rows,
        dataset="paid_meta_ads",
        results={"blocked_missing_source_value", "blocked_missing_dashthis_value"},
    )
    if paid_rows:
        requirements.append(
            _completion_requirement(
                code="approved_selected_account_paid_source_export_required",
                dataset="paid_meta_ads",
                rows=paid_rows,
                can_run_now=False,
                required_action=(
                    "Provide an approved selected-account May 2026 Meta Ads source export, "
                    "then dry-run `import_meta_paid_csv` if retained ADinsights rows are missing. "
                    "Do not substitute another tenant ad account."
                ),
                bundle=bundle,
            )
        )
    paid_import_rows = _matching_unresolved_rows(
        unresolved_rows,
        dataset="paid_meta_ads",
        results={"blocked_missing_adinsights_value"},
    )
    if paid_import_rows:
        requirements.append(
            _completion_requirement(
                code="selected_account_paid_backfill_or_import_required",
                dataset="paid_meta_ads",
                rows=paid_import_rows,
                can_run_now=False,
                required_action=(
                    "Backfill the selected SLB Meta ad account or import the approved daily paid CSV, "
                    "then rerun parity. Do not substitute another tenant ad account."
                ),
                bundle=bundle,
            )
        )

    organic_import_rows = [
        row
        for row in _matching_unresolved_rows(
            unresolved_rows,
            dataset="organic_facebook_page",
            results={"blocked_missing_adinsights_value"},
        )
        if bool(row.get("has_source_value"))
        and not bool(row.get("has_adinsights_value"))
    ]
    if organic_import_rows:
        organic_scope = _scope_evidence_for_dataset(bundle, "organic_facebook_page")
        can_run_now = (
            bool(organic_scope.get("page_scope_present"))
            and _int_value(organic_scope.get("matched_page_count")) > 0
        )
        requirements.append(
            _completion_requirement(
                code="tenant_owned_slb_page_required_for_organic_import",
                dataset="organic_facebook_page",
                rows=organic_import_rows,
                can_run_now=can_run_now,
                required_action=(
                    "Select the tenant-owned SLB Facebook Page, confirm source metric semantics, "
                    "then dry-run `import_meta_organic_csv` before importing the approved aggregate values. "
                    "Do not import SLB values into an unrelated Page."
                ),
                bundle=bundle,
            )
        )

    content_rows = _matching_unresolved_rows(
        unresolved_rows,
        dataset="content_ops",
        results={"blocked_missing_source_value", "blocked_missing_dashthis_value"},
    )
    if content_rows:
        requirements.append(
            _completion_requirement(
                code="approved_content_ops_source_totals_required",
                dataset="content_ops",
                rows=content_rows,
                can_run_now=False,
                required_action=(
                    "Provide an approved aggregate Content Ops source export for May 2026 totals. "
                    "Do not infer totals from top-post examples."
                ),
                bundle=bundle,
            )
        )
    content_import_rows = _matching_unresolved_rows(
        unresolved_rows,
        dataset="content_ops",
        results={"blocked_missing_adinsights_value"},
    )
    if content_import_rows:
        requirements.append(
            _completion_requirement(
                code="content_ops_import_or_backfill_required",
                dataset="content_ops",
                rows=content_import_rows,
                can_run_now=False,
                required_action=(
                    "Import or backfill the approved aggregate Content Ops source totals for May 2026, "
                    "then rerun parity."
                ),
                bundle=bundle,
            )
        )

    semantic_rows = [
        row
        for row in unresolved_rows
        if str(row.get("result") or "") == "blocked_metric_semantics"
        and row not in organic_import_rows
    ]
    if semantic_rows:
        requirements.append(
            _completion_requirement(
                code="metric_semantics_or_tolerance_confirmation_required",
                dataset="mixed",
                rows=semantic_rows,
                can_run_now=False,
                required_action=(
                    "Confirm metric semantics, date/account filters, and accepted tolerances before approving parity."
                ),
                bundle=bundle,
            )
        )

    failed_rows = [
        row for row in unresolved_rows if str(row.get("result") or "") == "fail"
    ]
    if failed_rows:
        requirements.append(
            _completion_requirement(
                code="parity_delta_investigation_required",
                dataset="mixed",
                rows=failed_rows,
                can_run_now=False,
                required_action=(
                    "Investigate non-zero parity deltas before approving the fixed-target report."
                ),
                bundle=bundle,
            )
        )
    return requirements


def _completion_requirement(
    *,
    code: str,
    dataset: str,
    rows: list[Mapping[str, Any]],
    can_run_now: bool,
    required_action: str,
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "dataset": dataset,
        "row_count": len(rows),
        "metrics": _unresolved_metrics(rows),
        "blocking_results": _unresolved_result_counts(rows),
        "can_run_now": can_run_now,
        "required_action": required_action,
        "scope_evidence": _scope_evidence_for_dataset(bundle, dataset),
    }


def _matching_unresolved_rows(
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


def _unresolved_metrics(rows: list[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {str(row.get("metric") or "") for row in rows if str(row.get("metric") or "")}
    )


def _unresolved_result_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        result = str(row.get("result") or "")
        if result:
            counts[result] = counts.get(result, 0) + 1
    return counts


def _safe_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item)})


def _scope_evidence_for_dataset(
    bundle: Mapping[str, Any],
    dataset: str,
) -> dict[str, Any]:
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
    row_summary = _scoped_row_summary(scoped_rows)
    if dataset == "paid_meta_ads":
        credential_status = scope.get("credential_status")
        return {
            "account_scope_present": bool(scope.get("account_scope_present")),
            "client_scope_present": bool(scope.get("client_scope_present")),
            "backfill_status": str(scope.get("backfill_status") or ""),
            "credential_status": _credential_status_summary(credential_status),
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


def _scoped_row_summary(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"row_count": 0, "min_date": "", "max_date": ""}
    return {
        "row_count": _int_value(value.get("row_count")),
        "min_date": str(value.get("min_date") or ""),
        "max_date": str(value.get("max_date") or ""),
    }


def _credential_status_summary(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "status": str(value.get("status") or ""),
        "provider": str(value.get("provider") or ""),
        "matched": bool(value.get("matched")),
        "token_status": str(value.get("token_status") or ""),
        "last_validated_at": str(value.get("last_validated_at") or ""),
    }


def _check_parity_report_identity(
    bundle_report: Mapping[str, Any],
    parity_report: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> None:
    bundle_report_id = str(bundle_report.get("id") or "").strip()
    parity_report_id = str(parity_report.get("id") or "").strip()
    bundle_template_key = str(bundle_report.get("template_key") or "").strip()
    parity_template_key = str(parity_report.get("template_key") or "").strip()
    if not bundle_report_id:
        blockers.append(
            _finding("report_identity", "Evidence bundle report.id is required.")
        )
    if not parity_report_id:
        blockers.append(
            _finding("report_identity", "Parity comparison report.id is required.")
        )
    elif bundle_report_id and parity_report_id != bundle_report_id:
        blockers.append(
            _finding(
                "report_identity",
                "Parity comparison report.id does not match evidence bundle.",
            )
        )
    if not bundle_template_key:
        blockers.append(
            _finding(
                "report_identity", "Evidence bundle report.template_key is required."
            )
        )
    if not parity_template_key:
        blockers.append(
            _finding(
                "report_identity", "Parity comparison report.template_key is required."
            )
        )
    elif bundle_template_key and parity_template_key != bundle_template_key:
        blockers.append(
            _finding(
                "report_identity",
                "Parity comparison report.template_key does not match evidence bundle.",
            )
        )


def _check_instagram_deferred(
    bundle: Mapping[str, Any],
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    serialized = json.dumps(bundle, sort_keys=True, default=str).lower()
    if "organic_instagram" in serialized or "instagram" in serialized:
        blockers.append(
            _finding(
                "instagram",
                "Instagram appears in v1 evidence and must remain deferred.",
            )
        )
    else:
        checks.append(
            _passed("instagram", "Instagram is absent from v1 evidence bundle.")
        )


def _check_sensitive_payloads(
    *,
    bundle: Mapping[str, Any],
    parity: Mapping[str, Any] | None,
    blockers: list[dict[str, str]],
    checks: list[dict[str, str]],
) -> None:
    serialized = json.dumps(
        {"bundle": bundle, "parity": parity or {}}, sort_keys=True, default=str
    )
    matches = sorted(
        {
            pattern.pattern
            for pattern in SENSITIVE_PATTERNS
            if pattern.search(serialized)
        }
    )
    if matches:
        blockers.append(
            _finding(
                "sensitive_payload",
                f"Sensitive pattern(s) found in evidence artifacts: {len(matches)}.",
            )
        )
    else:
        checks.append(
            _passed(
                "sensitive_payload",
                "No high-signal sensitive patterns found in evidence artifacts.",
            )
        )


def _warning_only_coverage_statuses(
    bundle: Mapping[str, Any], dataset: str
) -> set[str]:
    report = bundle.get("report") if isinstance(bundle.get("report"), Mapping) else {}
    template_key = str(report.get("template_key") or "")
    policy = get_template_export_policy(template_key)
    statuses_by_dataset = (
        policy.get("warning_only_coverage_statuses")
        if isinstance(policy.get("warning_only_coverage_statuses"), Mapping)
        else {}
    )
    statuses = statuses_by_dataset.get(dataset)
    if not isinstance(statuses, (list, tuple, set)):
        return set()
    return {str(status) for status in statuses}


def _coverage_status_message(
    *,
    dataset: str,
    blocking_statuses: list[str],
    warning_statuses: list[str],
) -> str:
    if blocking_statuses:
        return (
            f"{dataset} has cancellation-blocking coverage statuses: "
            f"{', '.join(sorted(set(blocking_statuses)))}."
        )
    return (
        f"{dataset} has warning-only coverage statuses that require reviewer explanation: "
        f"{', '.join(sorted(set(warning_statuses)))}."
    )


def _finding(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _finding_summary(findings: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for finding in findings:
        code = str(finding.get("code") or "unknown")
        counts[code] = counts.get(code, 0) + 1
    return ", ".join(f"{code}={count}" for code, count in sorted(counts.items()))


def _passed(code: str, message: str) -> dict[str, str]:
    return {"code": code, "status": "pass", "message": message}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SLB Evidence Validation",
        "",
        f"- Readiness status: `{result.get('readiness_status')}`",
        f"- Blockers: `{result.get('blocker_count')}`",
        f"- Warnings: `{result.get('warning_count')}`",
        "",
        "## Blockers",
        "",
    ]
    for finding in result.get("blockers", []):
        if isinstance(finding, Mapping):
            lines.append(f"- `{finding.get('code')}`: {finding.get('message')}")
    if not result.get("blockers"):
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    for finding in result.get("warnings", []):
        if isinstance(finding, Mapping):
            lines.append(f"- `{finding.get('code')}`: {finding.get('message')}")
    if not result.get("warnings"):
        lines.append("- None")
    return "\n".join(lines)
