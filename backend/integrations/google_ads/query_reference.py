from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GAQL_FIELD_ATTRIBUTE_DEFINITIONS = {
    "category": "Artifact category (resource, segment, metric, or attribute).",
    "data_type": "The underlying data type of the field.",
    "type": "The typed field classification exposed by Google Ads API metadata.",
    "url": "Canonical URL for field metadata documentation.",
    "filterable": "Whether the field can be used in GAQL WHERE conditions.",
    "selectable": "Whether the field can be selected in GAQL SELECT.",
    "sortable": "Whether the field can be used in GAQL ORDER BY.",
    "repeated": "Whether the field returns a repeated/list value.",
}

_RESOURCE_LINE_RE = re.compile(r"^(?P<name>[a-z0-9_]+)\s{2,}(?P<description>.+)$")


def default_query_reference_path(version: str = "v23") -> Path:
    return Path(__file__).resolve().parents[1] / "data" / f"google_ads_{version}_query_reference.json"


def load_query_reference(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else default_query_reference_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    return _normalize_query_reference(payload)


def save_query_reference(
    payload: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> Path:
    normalized = _normalize_query_reference(payload)
    target = Path(path) if path is not None else default_query_reference_path(
        str(normalized.get("version", "v23"))
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def parse_query_reference_text(raw_text: str, *, version: str = "v23") -> dict[str, Any]:
    overview_lines: list[str] = []
    resources: list[dict[str, str]] = []
    seen: set[str] = set()
    in_overview = False
    in_resource_list = False
    current_entry: dict[str, str] | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered == "overview":
            in_overview = True
            in_resource_list = False
            continue
        if lowered.startswith("list of all resources"):
            in_overview = False
            in_resource_list = False
            continue
        if lowered.startswith("resource types"):
            in_overview = False
            in_resource_list = True
            current_entry = None
            continue
        if lowered.startswith("was this helpful"):
            break

        if in_overview:
            overview_lines.append(line)
            continue

        if not in_resource_list:
            continue

        parsed = _parse_resource_line(line)
        if parsed is None:
            if current_entry is not None:
                current_entry["description"] = _append_sentence(current_entry.get("description", ""), line)
            continue

        name, description = parsed
        if name in seen:
            current_entry = _find_resource(resources, name)
            if current_entry is not None and description:
                current_entry["description"] = _append_sentence(current_entry.get("description", ""), description)
            continue

        current_entry = {
            "name": name,
            "description": description,
        }
        resources.append(current_entry)
        seen.add(name)

    payload = {
        "version": version,
        "overview": " ".join(overview_lines).strip(),
        "field_attributes": dict(GAQL_FIELD_ATTRIBUTE_DEFINITIONS),
        "resource_types": resources,
        "resource_count": len(resources),
    }
    return _normalize_query_reference(payload)


def ingest_query_reference_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    version: str = "v23",
) -> dict[str, Any]:
    source = Path(input_path)
    parsed = parse_query_reference_text(source.read_text(encoding="utf-8"), version=version)
    save_query_reference(parsed, path=output_path)
    return parsed


def _normalize_query_reference(payload: dict[str, Any]) -> dict[str, Any]:
    version = str(payload.get("version") or "v23")
    overview = str(payload.get("overview") or "").strip()
    raw_attributes = payload.get("field_attributes")
    field_attributes = dict(GAQL_FIELD_ATTRIBUTE_DEFINITIONS)
    if isinstance(raw_attributes, dict):
        for key in field_attributes:
            value = raw_attributes.get(key)
            if isinstance(value, str) and value.strip():
                field_attributes[key] = value.strip()

    resources: list[dict[str, str]] = []
    seen: set[str] = set()
    raw_resources = payload.get("resource_types")
    if isinstance(raw_resources, list):
        for row in raw_resources:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            description = str(row.get("description") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            resources.append({"name": name, "description": description})
    resources = sorted(resources, key=lambda item: item["name"])
    return {
        "version": version,
        "overview": overview,
        "field_attributes": field_attributes,
        "resource_types": resources,
        "resource_count": len(resources),
    }


def _parse_resource_line(line: str) -> tuple[str, str] | None:
    if "\t" in line:
        name, description = line.split("\t", 1)
        return _clean_resource_entry(name, description)

    matched = _RESOURCE_LINE_RE.match(line)
    if matched:
        return _clean_resource_entry(matched.group("name"), matched.group("description"))

    tokens = line.split(" ", 1)
    if len(tokens) != 2:
        return None
    maybe_name, remainder = tokens
    if not maybe_name or not re.fullmatch(r"[a-z0-9_]+", maybe_name):
        return None
    return _clean_resource_entry(maybe_name, remainder)


def _clean_resource_entry(name: str, description: str) -> tuple[str, str]:
    return (name.strip(), description.strip())


def _append_sentence(existing: str, addition: str) -> str:
    if not existing:
        return addition.strip()
    return f"{existing.rstrip()} {addition.strip()}"


def _find_resource(resources: list[dict[str, str]], name: str) -> dict[str, str] | None:
    for row in resources:
        if row.get("name") == name:
            return row
    return None
