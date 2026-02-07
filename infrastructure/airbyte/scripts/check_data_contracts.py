#!/usr/bin/env python3
"""Validate cross-stream data contract assumptions for Phase 1 sources."""

from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _check_google_query_aliases(errors: list[str]) -> None:
    required_aliases = (
        "date_day",
        "customer_id",
        "campaign_id",
        "campaign_name",
        "ad_group_id",
        "criterion_id",
        "ad_name",
        "geo_target_region",
        "cost_micros",
        "currency_code",
        "impressions",
        "clicks",
        "conversions",
    )
    forbidden_aliases = ("ad_id", "region")
    files = (
        "infrastructure/airbyte/google_ads_source.yaml",
        "infrastructure/airbyte/sources/google_ads_daily_metrics.sql",
    )

    for rel_path in files:
        content = _read_text(rel_path)
        for alias in required_aliases:
            pattern = rf"\bAS\s+{re.escape(alias)}\b"
            if not re.search(pattern, content):
                errors.append(f"{rel_path}: missing alias '{alias}' in Google Ads query.")
        for alias in forbidden_aliases:
            pattern = rf"\bAS\s+{re.escape(alias)}\b"
            if re.search(pattern, content):
                errors.append(
                    f"{rel_path}: found deprecated alias '{alias}' in Google Ads query."
                )


def _check_lookback_env_consistency(errors: list[str]) -> None:
    canonical_name = "AIRBYTE_GOOGLE_ADS_LOOKBACK_WINDOW_DAYS"
    deprecated_name = "AIRBYTE_GOOGLE_ADS_LOOKBACK_DAYS"
    files = (
        "infrastructure/airbyte/google_ads_source.yaml",
        "infrastructure/airbyte/scripts/provision_meta_google_connectors.py",
        "infrastructure/airbyte/env.example",
        "infrastructure/airbyte/README.md",
        "infrastructure/airbyte/sources/google_ads.json.example",
    )

    for rel_path in files:
        content = _read_text(rel_path)
        if canonical_name not in content:
            errors.append(f"{rel_path}: missing canonical env var '{canonical_name}'.")
        if deprecated_name in content:
            errors.append(f"{rel_path}: contains deprecated env var '{deprecated_name}'.")


def _csv_headers(rel_path: str) -> list[str]:
    with (ROOT / rel_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _check_seed_headers(errors: list[str]) -> None:
    expected_columns = {
        "dbt/seeds/raw/google_ads_insights.csv": {
            "customer_id",
            "campaign_id",
            "ad_group_id",
            "criterion_id",
            "date_day",
            "geo_target_region",
            "cost_micros",
            "impressions",
            "clicks",
            "conversions",
            "_airbyte_emitted_at",
            "_airbyte_raw_id",
        },
        "dbt/seeds/raw/meta_ads_insights.csv": {
            "ad_account_id",
            "campaign_id",
            "adset_id",
            "ad_id",
            "date_start",
            "region",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "_airbyte_emitted_at",
            "_airbyte_raw_id",
        },
    }

    for rel_path, required in expected_columns.items():
        headers = set(_csv_headers(rel_path))
        missing = sorted(required - headers)
        if missing:
            errors.append(f"{rel_path}: missing required columns: {', '.join(missing)}.")


def _python_alias_keys(rel_path: str) -> set[str]:
    tree = ast.parse(_read_text(rel_path), filename=rel_path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "COLUMN_ALIASES":
                    if isinstance(node.value, ast.Dict):
                        keys: set[str] = set()
                        for key_node in node.value.keys:
                            if isinstance(key_node, ast.Constant) and isinstance(
                                key_node.value, str
                            ):
                                keys.add(key_node.value)
                        return keys
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "COLUMN_ALIASES":
                if isinstance(node.value, ast.Dict):
                    keys: set[str] = set()
                    for key_node in node.value.keys:
                        if isinstance(key_node, ast.Constant) and isinstance(
                            key_node.value, str
                        ):
                            keys.add(key_node.value)
                    return keys
    raise ValueError(f"{rel_path}: unable to find COLUMN_ALIASES.")


def _ts_alias_keys(rel_path: str) -> set[str]:
    content = _read_text(rel_path)
    marker = "const COLUMN_ALIASES"
    start = content.find(marker)
    if start == -1:
        raise ValueError(f"{rel_path}: unable to find COLUMN_ALIASES.")
    block_start = content.find("{", start)
    block_end = content.find("\n};", block_start)
    if block_start == -1 or block_end == -1:
        raise ValueError(f"{rel_path}: unable to parse COLUMN_ALIASES block.")
    block = content[block_start:block_end]
    return set(re.findall(r"^\s*([a-z_]+)\s*:\s*\[", block, flags=re.MULTILINE))


def _check_csv_alias_parity(errors: list[str]) -> None:
    backend_keys = _python_alias_keys("backend/analytics/uploads.py")
    frontend_keys = _ts_alias_keys("frontend/src/lib/uploadedMetrics.ts")
    backend_only = sorted(backend_keys - frontend_keys)
    frontend_only = sorted(frontend_keys - backend_keys)
    if backend_only:
        errors.append(
            "CSV alias mismatch: backend-only aliases: " + ", ".join(backend_only) + "."
        )
    if frontend_only:
        errors.append(
            "CSV alias mismatch: frontend-only aliases: " + ", ".join(frontend_only) + "."
        )


def _check_csv_runbook_link(errors: list[str]) -> None:
    runbook_path = ROOT / "docs/runbooks/csv-uploads.md"
    if not runbook_path.exists():
        errors.append("Missing runbook: docs/runbooks/csv-uploads.md.")
    link_target = "docs/runbooks/csv-uploads.md"
    content = _read_text("frontend/src/routes/DataSources.tsx")
    if link_target not in content:
        errors.append(
            "frontend/src/routes/DataSources.tsx: missing CSV runbook link target."
        )


def main() -> int:
    errors: list[str] = []
    _check_google_query_aliases(errors)
    _check_lookback_env_consistency(errors)
    _check_seed_headers(errors)
    _check_csv_alias_parity(errors)
    _check_csv_runbook_link(errors)

    if errors:
        print("Data-contract validation failed:")
        for message in errors:
            print(f"- {message}")
        return 1

    print("Data-contract validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
