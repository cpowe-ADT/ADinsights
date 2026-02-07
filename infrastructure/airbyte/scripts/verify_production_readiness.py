#!/usr/bin/env python3
"""Validate required Airbyte production connector configuration."""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Iterable

if __package__ is None or __package__ == "":  # pragma: no cover - CLI execution path
    current_dir = pathlib.Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from config import load_environment  # type: ignore
else:  # pragma: no cover - module execution path
    from .config import load_environment


REQUIRED_META_ENV = [
    "AIRBYTE_META_ACCOUNT_ID",
    "AIRBYTE_META_ACCESS_TOKEN",
    "AIRBYTE_META_APP_ID",
    "AIRBYTE_META_APP_SECRET",
]
REQUIRED_GOOGLE_ENV = [
    "AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN",
    "AIRBYTE_GOOGLE_ADS_CLIENT_ID",
    "AIRBYTE_GOOGLE_ADS_CLIENT_SECRET",
    "AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN",
    "AIRBYTE_GOOGLE_ADS_CUSTOMER_ID",
    "AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID",
]

PLACEHOLDER_TOKENS = (
    "replace-me",
    "redacted",
    "insert_",
    "example.com",
    "eaabsb",
    "your-",
    "changeme",
)


def _is_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    return any(token in lower for token in PLACEHOLDER_TOKENS)


def _check_env_vars(names: Iterable[str], report: dict[str, object]) -> None:
    missing: list[str] = []
    placeholders: list[str] = []
    for name in names:
        value = os.getenv(name, "").strip()
        if not value:
            missing.append(name)
            continue
        if _is_placeholder(value):
            placeholders.append(name)
    if missing:
        report.setdefault("errors", []).append(
            {"check": "required_env", "message": f"Missing required variables: {', '.join(missing)}"}
        )
    if placeholders:
        report.setdefault("errors", []).append(
            {
                "check": "placeholder_env",
                "message": f"Placeholder values detected for: {', '.join(placeholders)}",
            }
        )


def main() -> int:
    report: dict[str, object] = {
        "status": "ok",
        "checks": [],
    }

    try:
        env = load_environment()
    except ValueError as exc:
        report["status"] = "error"
        report.setdefault("errors", []).append(
            {"check": "tenant_config", "message": str(exc)}
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    report["checks"].append(
        {
            "check": "tenant_count",
            "message": f"Loaded {len(env.tenants)} tenant configuration(s).",
        }
    )

    timezone = os.getenv("AIRBYTE_DEFAULT_TIMEZONE", "America/Jamaica")
    if timezone != "America/Jamaica":
        report.setdefault("warnings", []).append(
            {
                "check": "timezone",
                "message": "AIRBYTE_DEFAULT_TIMEZONE is not America/Jamaica.",
            }
        )

    _check_env_vars(REQUIRED_META_ENV, report)
    _check_env_vars(REQUIRED_GOOGLE_ENV, report)

    if "errors" in report:
        report["status"] = "error"

    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

