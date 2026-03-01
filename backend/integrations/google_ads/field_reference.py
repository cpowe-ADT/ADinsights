from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIELD_PREFIXES = ("segments.", "metrics.")
FIELD_LABELS = {
    "field description": "field_description",
    "category": "category",
    "data type": "data_type",
    "type url": "type_url",
    "filterable": "filterable",
    "selectable": "selectable",
    "sortable": "sortable",
    "repeated": "repeated",
    "selectable with": "selectable_with",
}
SELECTABLE_WITH_HINT_PREFIX = "the following fields/resources can be selected with this field"
HEADER_TOKENS = {
    "google ads api",
    "ads api",
    "send feedback",
    "proto definition",
    "github",
    "segments",
    "metrics",
}
FIELD_NAME_RE = re.compile(r"(?P<name>(segments|metrics)\.[A-Za-z0-9_.]+)")


def default_fields_reference_path(version: str = "v23") -> Path:
    return Path(__file__).resolve().parents[1] / "data" / f"google_ads_{version}_fields_reference.json"


def load_fields_reference(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else default_fields_reference_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    return _normalize_fields_reference(payload)


def save_fields_reference(payload: dict[str, Any], *, path: str | Path | None = None) -> Path:
    normalized = _normalize_fields_reference(payload)
    target = Path(path) if path is not None else default_fields_reference_path(
        str(normalized.get("version", "v23"))
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def parse_fields_reference_text(raw_text: str, *, version: str = "v23") -> dict[str, Any]:
    sections: dict[str, list[dict[str, Any]]] = {"segments": [], "metrics": []}
    seen: dict[str, set[str]] = {"segments": set(), "metrics": set()}
    current: dict[str, Any] | None = None
    pending_key: str | None = None
    in_selectable_with = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_selectable_with:
                in_selectable_with = False
            continue

        if current is not None and in_selectable_with:
            lowered = line.lower()
            if lowered.startswith(SELECTABLE_WITH_HINT_PREFIX):
                continue
            if _is_likely_selectable_item(line):
                _add_selectable_item(current, line)
                continue

        field_name, remainder = _extract_field_name(line)
        if field_name:
            _flush_field(current=current, sections=sections, seen=seen)
            current = _new_field_template(field_name)
            pending_key = None
            in_selectable_with = False
            if remainder:
                _consume_line_content(current, remainder)
            continue

        if current is None:
            continue

        lowered = line.lower()
        if _looks_like_ignored_header(lowered):
            continue

        label_match = _match_label(line)
        if label_match:
            label_key, value = label_match
            pending_key = None
            if label_key == "selectable_with":
                in_selectable_with = True
                if value:
                    _extend_selectable_with(current, value)
                continue
            in_selectable_with = False
            if value:
                _apply_value(current, label_key, value)
            else:
                pending_key = label_key
            continue

        if pending_key:
            _apply_value(current, pending_key, line)
            pending_key = None
            continue

        if in_selectable_with:
            if lowered.startswith(SELECTABLE_WITH_HINT_PREFIX):
                continue
            if _is_likely_selectable_item(line):
                _add_selectable_item(current, line)
            continue

        # Treat unlabeled continuation text as description tail.
        _append_description(current, line)

    _flush_field(current=current, sections=sections, seen=seen)

    payload = {
        "version": version,
        "fields": sections,
        "counts": {
            "segments": len(sections["segments"]),
            "metrics": len(sections["metrics"]),
        },
        "total_fields": len(sections["segments"]) + len(sections["metrics"]),
    }
    return _normalize_fields_reference(payload)


def ingest_fields_reference_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    version: str = "v23",
) -> dict[str, Any]:
    source = Path(input_path)
    payload = parse_fields_reference_text(source.read_text(encoding="utf-8"), version=version)
    save_fields_reference(payload, path=output_path)
    return payload


def _normalize_fields_reference(payload: dict[str, Any]) -> dict[str, Any]:
    version = str(payload.get("version") or "v23")
    raw_sections = payload.get("fields")
    sections: dict[str, list[dict[str, Any]]] = {"segments": [], "metrics": []}

    if isinstance(raw_sections, dict):
        for section in ("segments", "metrics"):
            rows = raw_sections.get(section)
            if not isinstance(rows, list):
                continue
            seen: set[str] = set()
            normalized_rows: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                normalized_rows.append(
                    {
                        "name": name,
                        "field_description": str(row.get("field_description") or "").strip(),
                        "category": str(row.get("category") or "").strip().upper(),
                        "data_type": str(row.get("data_type") or "").strip().upper(),
                        "type_url": str(row.get("type_url") or "").strip(),
                        "filterable": _coerce_bool(row.get("filterable")),
                        "selectable": _coerce_bool(row.get("selectable")),
                        "sortable": _coerce_bool(row.get("sortable")),
                        "repeated": _coerce_bool(row.get("repeated")),
                        "selectable_with": _normalize_selectable_with(row.get("selectable_with")),
                    }
                )
            sections[section] = sorted(normalized_rows, key=lambda item: item["name"])

    counts = {
        "segments": len(sections["segments"]),
        "metrics": len(sections["metrics"]),
    }
    return {
        "version": version,
        "fields": sections,
        "counts": counts,
        "total_fields": counts["segments"] + counts["metrics"],
    }


def _new_field_template(name: str) -> dict[str, Any]:
    category = "SEGMENT" if name.startswith("segments.") else "METRIC"
    return {
        "name": name,
        "field_description": "",
        "category": category,
        "data_type": "",
        "type_url": "",
        "filterable": None,
        "selectable": None,
        "sortable": None,
        "repeated": None,
        "selectable_with": [],
    }


def _flush_field(
    *,
    current: dict[str, Any] | None,
    sections: dict[str, list[dict[str, Any]]],
    seen: dict[str, set[str]],
) -> None:
    if current is None:
        return
    name = str(current.get("name") or "").strip()
    if not name:
        return
    section = "segments" if name.startswith("segments.") else "metrics"
    if name in seen[section]:
        existing = _find_field(sections[section], name)
        if existing is not None:
            _merge_field(existing, current)
        return
    seen[section].add(name)
    sections[section].append(current)


def _find_field(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("name") == name:
            return row
    return None


def _merge_field(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    if incoming.get("field_description"):
        existing["field_description"] = _append_text(
            str(existing.get("field_description") or ""),
            str(incoming.get("field_description") or ""),
        )
    for key in ("category", "data_type", "type_url"):
        if incoming.get(key):
            existing[key] = incoming[key]
    for key in ("filterable", "selectable", "sortable", "repeated"):
        if incoming.get(key) is not None:
            existing[key] = incoming[key]
    existing_items = set(existing.get("selectable_with") or [])
    for item in incoming.get("selectable_with") or []:
        token = str(item).strip()
        if token and token not in existing_items:
            existing.setdefault("selectable_with", []).append(token)
            existing_items.add(token)


def _extract_field_name(line: str) -> tuple[str | None, str]:
    matched = FIELD_NAME_RE.search(line)
    if not matched:
        return (None, "")
    name = matched.group("name").strip()
    remainder = line[matched.end() :].strip()
    return (name, remainder)


def _match_label(line: str) -> tuple[str, str] | None:
    lowered = line.lower()
    for label in sorted(FIELD_LABELS.keys(), key=len, reverse=True):
        key = FIELD_LABELS[label]
        if lowered.startswith(label):
            value = line[len(label) :].strip(" :\t")
            return (key, value)
    return None


def _apply_value(field: dict[str, Any], key: str, value: str) -> None:
    normalized = value.strip()
    if not normalized:
        return

    if key == "field_description":
        _append_description(field, normalized)
        return
    if key == "category":
        field["category"] = normalized.upper()
        return
    if key == "data_type":
        field["data_type"] = normalized.upper()
        return
    if key == "type_url":
        field["type_url"] = normalized
        return
    if key in {"filterable", "selectable", "sortable", "repeated"}:
        field[key] = _coerce_bool(normalized)
        return
    if key == "selectable_with":
        _extend_selectable_with(field, normalized)
        return


def _append_description(field: dict[str, Any], extra: str) -> None:
    field["field_description"] = _append_text(str(field.get("field_description") or ""), extra)


def _append_text(existing: str, extra: str) -> str:
    if not existing:
        return extra.strip()
    return f"{existing.rstrip()} {extra.strip()}"


def _coerce_bool(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def _extend_selectable_with(field: dict[str, Any], raw_value: str) -> None:
    for part in raw_value.split(","):
        _add_selectable_item(field, part)


def _add_selectable_item(field: dict[str, Any], raw_item: str) -> None:
    token = raw_item.strip().strip("-*•").strip()
    if not token:
        return
    if token.lower().startswith(SELECTABLE_WITH_HINT_PREFIX):
        return
    if token.lower().startswith("field description"):
        return
    if token.lower().startswith("category"):
        return
    if token.lower().startswith("data type"):
        return
    if token.lower().startswith("type url"):
        return
    if token.lower().startswith("filterable"):
        return
    if token.lower().startswith("selectable"):
        return
    if token.lower().startswith("sortable"):
        return
    if token.lower().startswith("repeated"):
        return
    values = field.setdefault("selectable_with", [])
    if token not in values:
        values.append(token)


def _is_likely_selectable_item(line: str) -> bool:
    token = line.strip().strip("-*•").strip()
    if not token:
        return False
    if token.lower().startswith(SELECTABLE_WITH_HINT_PREFIX):
        return False
    if token.startswith("segments.") or token.startswith("metrics."):
        return True
    if re.fullmatch(r"[a-z_][a-z0-9_]*", token):
        return True
    return False


def _looks_like_ignored_header(lowered: str) -> bool:
    for token in HEADER_TOKENS:
        if lowered.startswith(token):
            return True
    return False


def _consume_line_content(field: dict[str, Any], content: str) -> None:
    label_match = _match_label(content)
    if label_match:
        _apply_value(field, label_match[0], label_match[1])
        return
    _append_description(field, content)


def _normalize_selectable_with(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        token = str(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized
