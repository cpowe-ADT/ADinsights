#!/usr/bin/env python3
"""Validate persona-catalog.yaml against ADinsights source docs and schema expectations."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime environment guard
    raise SystemExit("Missing dependency: pyyaml. Install with `pip install pyyaml`.") from exc


REQUIRED_PERSONA_NAMES = {
    "Maya",
    "Leo",
    "Priya",
    "Martin",
    "Sofia",
    "Andre",
    "Lina",
    "Joel",
    "Nina",
    "Victor",
    "Omar",
    "Hannah",
    "Carlos",
    "Mei",
    "Raj",
    "Mira",
}

REQUIRED_PERSONA_FIELDS = {
    "id",
    "name",
    "aliases",
    "role",
    "primary_scope",
    "backup_scope",
    "review_focus",
    "required_tests",
    "primary_docs",
    "escalation_rules",
}

REQUIRED_STREAM_IDS = {f"S{i}" for i in range(1, 8)}


def default_repo_root() -> Path:
    # /repo/docs/ops/skills/adinsights-persona-router/scripts/validate_persona_catalog.py
    return Path(__file__).resolve().parents[5]


def check_list_field(errors: list[str], persona_name: str, persona: dict, field: str) -> None:
    value = persona.get(field)
    if not isinstance(value, list) or not value:
        errors.append(
            f"Persona '{persona_name}' field '{field}' must be a non-empty list."
        )


def validate_catalog(
    catalog_path: Path,
    workstreams_path: Path,
    ownership_path: Path,
) -> int:
    errors: list[str] = []

    for path, label in (
        (catalog_path, "Catalog"),
        (workstreams_path, "Workstreams"),
        (ownership_path, "Feature ownership map"),
    ):
        if not path.exists():
            errors.append(f"{label} file not found: {path}")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    catalog = yaml.safe_load(catalog_path.read_text()) or {}
    personas = catalog.get("personas")
    streams = catalog.get("streams")
    confidence_policy = catalog.get("confidence_policy")

    if not isinstance(personas, list) or not personas:
        errors.append("`personas` must be a non-empty list.")

    if not isinstance(streams, dict):
        errors.append("`streams` must be a mapping (S1..S7).")
    else:
        stream_ids = set(streams.keys())
        missing_streams = sorted(REQUIRED_STREAM_IDS - stream_ids)
        extra_streams = sorted(stream_ids - REQUIRED_STREAM_IDS)
        if missing_streams:
            errors.append(f"Missing stream definitions: {', '.join(missing_streams)}")
        if extra_streams:
            errors.append(f"Unexpected stream definitions: {', '.join(extra_streams)}")

    if not isinstance(confidence_policy, dict):
        errors.append("`confidence_policy` must be a mapping.")
    else:
        auto_resolve_min = confidence_policy.get("auto_resolve_min")
        clarify_min = confidence_policy.get("clarify_min")
        if not isinstance(auto_resolve_min, (int, float)):
            errors.append("confidence_policy.auto_resolve_min must be numeric.")
        if not isinstance(clarify_min, (int, float)):
            errors.append("confidence_policy.clarify_min must be numeric.")
        if (
            isinstance(auto_resolve_min, (int, float))
            and isinstance(clarify_min, (int, float))
            and not (0 <= clarify_min <= auto_resolve_min <= 1)
        ):
            errors.append(
                "confidence_policy thresholds must satisfy 0 <= clarify_min <= auto_resolve_min <= 1."
            )

    persona_ids_seen: set[str] = set()
    persona_names_seen: set[str] = set()

    if isinstance(personas, list):
        for idx, persona in enumerate(personas, start=1):
            if not isinstance(persona, dict):
                errors.append(f"Persona #{idx} must be a mapping/object.")
                continue

            missing_fields = sorted(REQUIRED_PERSONA_FIELDS - set(persona.keys()))
            if missing_fields:
                errors.append(
                    f"Persona #{idx} missing required field(s): {', '.join(missing_fields)}"
                )
                continue

            persona_id = str(persona["id"]).strip()
            persona_name = str(persona["name"]).strip()

            if not re.fullmatch(r"[a-z0-9-]+", persona_id):
                errors.append(
                    f"Persona '{persona_name}' has invalid id '{persona_id}'. Use lowercase hyphen-case."
                )
            if persona_id in persona_ids_seen:
                errors.append(f"Duplicate persona id: {persona_id}")
            persona_ids_seen.add(persona_id)

            if persona_name in persona_names_seen:
                errors.append(f"Duplicate persona name: {persona_name}")
            persona_names_seen.add(persona_name)

            check_list_field(errors, persona_name, persona, "aliases")
            check_list_field(errors, persona_name, persona, "primary_scope")
            check_list_field(errors, persona_name, persona, "backup_scope")
            check_list_field(errors, persona_name, persona, "review_focus")
            check_list_field(errors, persona_name, persona, "required_tests")
            check_list_field(errors, persona_name, persona, "primary_docs")
            check_list_field(errors, persona_name, persona, "escalation_rules")

    missing_required_names = sorted(REQUIRED_PERSONA_NAMES - persona_names_seen)
    extra_names = sorted(persona_names_seen - REQUIRED_PERSONA_NAMES)

    if missing_required_names:
        errors.append(
            "Missing required persona name(s): " + ", ".join(missing_required_names)
        )
    if extra_names:
        errors.append(
            "Unexpected persona name(s) not in v1 core set: " + ", ".join(extra_names)
        )

    if isinstance(streams, dict):
        for stream_id, stream_data in sorted(streams.items()):
            if not isinstance(stream_data, dict):
                errors.append(f"{stream_id} must be an object with primary/backup/folder_hints/keywords.")
                continue

            for required_key in ("primary", "backup", "folder_hints", "keywords"):
                if required_key not in stream_data:
                    errors.append(f"{stream_id} missing required key '{required_key}'.")

            primary_id = stream_data.get("primary")
            backup_id = stream_data.get("backup")
            if primary_id not in persona_ids_seen:
                errors.append(f"{stream_id}.primary references unknown persona id '{primary_id}'.")
            if backup_id not in persona_ids_seen:
                errors.append(f"{stream_id}.backup references unknown persona id '{backup_id}'.")

            for list_key in ("folder_hints", "keywords"):
                value = stream_data.get(list_key)
                if not isinstance(value, list) or not value:
                    errors.append(f"{stream_id}.{list_key} must be a non-empty list.")

    workstreams_text = workstreams_path.read_text()
    ownership_text = ownership_path.read_text()

    for persona_name in sorted(persona_names_seen):
        if re.search(rf"\b{re.escape(persona_name)}\b", workstreams_text) is None:
            errors.append(
                f"Persona '{persona_name}' not found in {workstreams_path.name}."
            )
        if re.search(rf"\b{re.escape(persona_name)}\b", ownership_text) is None:
            errors.append(
                f"Persona '{persona_name}' not found in {ownership_path.name}."
            )

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print(
        "[OK] Catalog valid: "
        f"{len(personas)} personas, stream map + confidence policy valid, "
        f"and all persona names referenced in {workstreams_path.name} and {ownership_path.name}."
    )
    return 0


def parse_args() -> argparse.Namespace:
    root = default_repo_root()
    default_catalog = (
        root
        / "docs"
        / "ops"
        / "skills"
        / "adinsights-persona-router"
        / "references"
        / "persona-catalog.yaml"
    )
    default_workstreams = root / "docs" / "workstreams.md"
    default_ownership = root / "docs" / "project" / "feature-ownership-map.md"

    parser = argparse.ArgumentParser(
        description="Validate ADinsights persona catalog consistency."
    )
    parser.add_argument("--catalog", type=Path, default=default_catalog)
    parser.add_argument("--workstreams", type=Path, default=default_workstreams)
    parser.add_argument("--ownership", type=Path, default=default_ownership)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return validate_catalog(args.catalog, args.workstreams, args.ownership)


if __name__ == "__main__":
    sys.exit(main())
