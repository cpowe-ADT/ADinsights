from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GOOGLE_ADS_REFERENCE_SECTIONS = (
    "services",
    "common",
    "enums",
    "errors",
    "misc",
    "resources",
)

_ENTRY_WITH_DESCRIPTION_RE = re.compile(r"^(?P<name>.+?)\s{2,}(?P<description>.+)$")
_IGNORED_HEADER_LINES = {
    "google ads api v23 - reference",
    "overview",
}


def default_reference_catalog_path(version: str = "v23") -> Path:
    return Path(__file__).resolve().parents[1] / "data" / f"google_ads_{version}_reference.json"


def load_reference_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else default_reference_catalog_path()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    return _normalize_catalog(payload)


def save_reference_catalog(
    catalog: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> Path:
    catalog_path = Path(path) if path is not None else default_reference_catalog_path(
        str(catalog.get("version", "v23"))
    )
    normalized = _normalize_catalog(catalog)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return catalog_path


def parse_reference_text(raw_text: str, *, version: str = "v23") -> dict[str, Any]:
    catalog = _empty_catalog(version=version)
    sections = catalog["sections"]
    seen: dict[str, set[str]] = {section: set() for section in GOOGLE_ADS_REFERENCE_SECTIONS}

    active_section: str | None = None
    current_entry: dict[str, str] | None = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered in _IGNORED_HEADER_LINES:
            continue
        if lowered in GOOGLE_ADS_REFERENCE_SECTIONS:
            active_section = lowered
            current_entry = None
            continue
        if active_section is None:
            continue

        parsed = _parse_entry_line(line)
        if parsed is None:
            if current_entry is not None:
                current_entry["description"] = _append_description(
                    current_entry.get("description", ""),
                    line,
                )
            continue

        name, description = parsed
        if name in seen[active_section]:
            current_entry = _get_entry_by_name(sections[active_section], name)
            if current_entry is not None and description:
                current_entry["description"] = _append_description(
                    current_entry.get("description", ""),
                    description,
                )
            continue

        entry = {"name": name, "description": description}
        sections[active_section].append(entry)
        seen[active_section].add(name)
        current_entry = entry

    return _normalize_catalog(catalog)


def ingest_reference_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    version: str = "v23",
) -> dict[str, Any]:
    source_path = Path(input_path)
    catalog = parse_reference_text(source_path.read_text(encoding="utf-8"), version=version)
    save_reference_catalog(catalog, path=output_path)
    return catalog


def _empty_catalog(version: str) -> dict[str, Any]:
    return {
        "version": version,
        "sections": {section: [] for section in GOOGLE_ADS_REFERENCE_SECTIONS},
        "counts": {section: 0 for section in GOOGLE_ADS_REFERENCE_SECTIONS},
        "total_entries": 0,
    }


def _normalize_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    version = str(payload.get("version") or "v23")
    raw_sections = payload.get("sections")
    sections: dict[str, list[dict[str, str]]] = {
        section: [] for section in GOOGLE_ADS_REFERENCE_SECTIONS
    }

    if isinstance(raw_sections, dict):
        for section in GOOGLE_ADS_REFERENCE_SECTIONS:
            rows = raw_sections.get(section)
            if not isinstance(rows, list):
                continue
            normalized_rows: list[dict[str, str]] = []
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name", "")).strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                normalized_rows.append(
                    {
                        "name": name,
                        "description": str(row.get("description", "")).strip(),
                    }
                )
            sections[section] = normalized_rows

    counts = {section: len(rows) for section, rows in sections.items()}
    return {
        "version": version,
        "sections": sections,
        "counts": counts,
        "total_entries": sum(counts.values()),
    }


def _parse_entry_line(line: str) -> tuple[str, str] | None:
    if "\t" in line:
        name, description = line.split("\t", 1)
        return _clean_entry(name, description)

    matched = _ENTRY_WITH_DESCRIPTION_RE.match(line)
    if matched:
        return _clean_entry(
            matched.group("name"),
            matched.group("description"),
        )

    if " " in line:
        return None

    name, description = _clean_entry(line, "")
    if not name:
        return None
    return (name, description)


def _clean_entry(name: str, description: str) -> tuple[str, str]:
    return (name.strip(), description.strip())


def _append_description(existing: str, addition: str) -> str:
    if not existing:
        return addition.strip()
    return f"{existing.rstrip()} {addition.strip()}"


def _get_entry_by_name(entries: list[dict[str, str]], name: str) -> dict[str, str] | None:
    for entry in entries:
        if entry.get("name") == name:
            return entry
    return None
