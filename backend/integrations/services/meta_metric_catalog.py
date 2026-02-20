from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def metric_catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "meta_metric_catalog.json"


def metric_catalog_doc_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "project" / "meta-page-insights-metric-catalog.md"


@lru_cache(maxsize=1)
def load_metric_catalog() -> list[dict[str, Any]]:
    path = metric_catalog_path()
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Metric catalog must be a list of metric definitions.")

    normalized: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        metric_key = str(row.get("metric_key", "")).strip()
        level = str(row.get("level", "")).strip()
        if not metric_key or not level:
            continue
        normalized.append(
            {
                "metric_key": metric_key,
                "level": level,
                "supported_periods": _as_string_list(row.get("supported_periods")),
                "supports_breakdowns": _as_string_list(row.get("supports_breakdowns")),
                "status": str(row.get("status", "UNKNOWN")).strip() or "UNKNOWN",
                "replacement_metric_key": str(row.get("replacement_metric_key", "")).strip(),
                "is_default": bool(row.get("is_default", False)),
                "deprecated_on": str(row.get("deprecated_on", "")).strip(),
            }
        )
    return normalized


def replacement_candidates_from_catalog(catalog: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    candidates: dict[tuple[str, str], str] = {}
    for definition in catalog:
        replacement = str(definition.get("replacement_metric_key", "")).strip()
        if not replacement:
            continue
        key = (
            str(definition.get("level", "")).strip(),
            str(definition.get("metric_key", "")).strip(),
        )
        if key[0] and key[1]:
            candidates[key] = replacement
    return candidates


def render_metric_catalog_markdown(catalog: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        "# Meta Page Insights Metric Catalog",
        "",
        "This document is generated from `backend/integrations/data/meta_metric_catalog.json`.",
        "",
    ]
    levels = [
        ("PAGE", "Page metrics"),
        ("POST", "Post metrics"),
    ]
    for level, title in levels:
        level_rows = sorted(
            [row for row in catalog if str(row.get("level")) == level],
            key=lambda row: str(row.get("metric_key")),
        )
        lines.extend(
            [
                f"## {title}",
                "",
                "| Metric | Status | Default | Periods | Breakdowns | Replacement | Deprecated note |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in level_rows:
            periods = ", ".join(_as_string_list(row.get("supported_periods"))) or "-"
            breakdowns = ", ".join(_as_string_list(row.get("supports_breakdowns"))) or "-"
            replacement = str(row.get("replacement_metric_key", "")).strip() or "-"
            deprecated_on = str(row.get("deprecated_on", "")).strip() or "-"
            is_default = "yes" if bool(row.get("is_default")) else "no"
            lines.append(
                f"| `{row['metric_key']}` | `{row.get('status', 'UNKNOWN')}` | {is_default} | {periods} | {breakdowns} | {replacement} | {deprecated_on} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _as_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]
