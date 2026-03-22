#!/usr/bin/env python3
"""
Probe the Airbyte OSS API for connection health.

Usage:
  AIRBYTE_WORKSPACE_ID=... python3 infrastructure/airbyte/scripts/airbyte_health_check.py

Environment variables:
  AIRBYTE_BASE_URL                 Base URL for the Airbyte API (default: http://localhost:8001)
  AIRBYTE_WORKSPACE_ID             Workspace UUID (required)
  AIRBYTE_API_AUTH_HEADER          Optional pre-formatted Authorization header value
  AIRBYTE_CONNECTION_IDS           Optional comma-separated allowlist of connection UUIDs to check
  AIRBYTE_STALE_MULTIPLIER         Multiplier applied to the expected schedule interval (default: 1.5)
  AIRBYTE_FALLBACK_STALE_MINUTES   Threshold in minutes when interval cannot be derived (default: 90)

Exit codes:
  0 when all connections are healthy.
  1 when at least one connection is failing or stale.
  2 when the probe cannot reach the Airbyte API.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib import error, request


BASE_URL = os.getenv("AIRBYTE_BASE_URL", "http://localhost:8001")
WORKSPACE_ID = os.getenv("AIRBYTE_WORKSPACE_ID")
AUTH_HEADER = os.getenv("AIRBYTE_API_AUTH_HEADER")
CONNECTION_ALLOWLIST = {
    item.strip()
    for item in os.getenv("AIRBYTE_CONNECTION_IDS", "").split(",")
    if item.strip()
}
STALE_MULTIPLIER = float(os.getenv("AIRBYTE_STALE_MULTIPLIER", "1.5"))
FALLBACK_STALE_MINUTES = int(os.getenv("AIRBYTE_FALLBACK_STALE_MINUTES", "90"))


def _build_request(path: str, payload: Dict) -> request.Request:
    url = f"{BASE_URL.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if AUTH_HEADER:
        headers["Authorization"] = AUTH_HEADER
    body = json.dumps(payload).encode("utf-8")
    return request.Request(url, data=body, headers=headers, method="POST")


def _call_api(path: str, payload: Dict) -> Dict:
    req = _build_request(path, payload)
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"Airbyte API responded with HTTP {exc.code} for {path}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach Airbyte API at {BASE_URL}: {exc.reason}") from exc


def _seconds_from_units(units: Optional[int], unit_name: Optional[str]) -> Optional[int]:
    if not units or not unit_name:
        return None
    unit_name = unit_name.lower()
    seconds_per_unit = {
        "minutes": 60,
        "hours": 3600,
        "days": 86400,
    }.get(unit_name)
    if seconds_per_unit is None:
        return None
    return int(units * seconds_per_unit)


def _parse_cron_interval(cron_expression: str) -> Optional[int]:
    if not cron_expression:
        return None

    parts = cron_expression.strip().split()
    if len(parts) != 5:
        # We only support standard 5-part cron for now.
        return None

    minute, hour, day, month, dow = parts

    # Helper to parse "*/N"
    def get_step(field: str) -> Optional[int]:
        if field.startswith("*/"):
            try:
                return int(field[2:])
            except ValueError:
                return None
        return None

    # Case 1: Every minute (* * * * *)
    if minute == "*" and hour == "*" and day == "*" and month == "*" and dow == "*":
        return 60

    # Case 2: Every N minutes (*/N * * * *)
    step_min = get_step(minute)
    if step_min and hour == "*" and day == "*" and month == "*" and dow == "*":
        return step_min * 60

    # Case 3: Every hour (0 * * * *)
    # Note: If minute is specific (e.g. 5 * * * *), it's still every hour, just at minute 5.
    # So we check if minute is a specific number.
    if minute.isdigit() and hour == "*" and day == "*" and month == "*" and dow == "*":
        return 3600

    # Case 4: Every N hours (0 */N * * *) or (5 */N * * *)
    step_hour = get_step(hour)
    if minute.isdigit() and step_hour and day == "*" and month == "*" and dow == "*":
        return step_hour * 3600

    # Case 5: Daily (0 0 * * *) or (30 14 * * *)
    if minute.isdigit() and hour.isdigit() and day == "*" and month == "*" and dow == "*":
        return 86400

    # Case 6: Weekly (0 0 * * 0)
    # If minute and hour are digits, day and month are *, and dow is digit.
    if minute.isdigit() and hour.isdigit() and day == "*" and month == "*" and dow.isdigit():
        return 7 * 86400

    return None


def _stale_threshold_seconds(connection: Dict) -> int:
    schedule_type = connection.get("scheduleType")
    schedule_data = connection.get("scheduleData") or {}

    if schedule_type == "basic":
        basic = schedule_data.get("basicSchedule") or {}
        interval_seconds = _seconds_from_units(basic.get("units"), basic.get("timeUnit"))
        if interval_seconds:
            return int(interval_seconds * STALE_MULTIPLIER)
    elif schedule_type == "cron":
        cron_data = schedule_data.get("cron") or {}
        cron_expression = cron_data.get("cronExpression")
        interval_seconds = _parse_cron_interval(cron_expression)
        if interval_seconds:
            return int(interval_seconds * STALE_MULTIPLIER)

    return FALLBACK_STALE_MINUTES * 60


def _latest_job(connection_id: str) -> Optional[Dict]:
    payload = {
        "configTypes": ["sync"],
        "configId": connection_id,
        "pagination": {"pageSize": 1},
    }
    jobs_response = _call_api("/api/v1/jobs/list", payload)
    jobs = jobs_response.get("jobs") or []
    if not jobs:
        return None
    return jobs[0]


def _classify(connection: Dict, job_wrapper: Optional[Dict], now_ts: int) -> Tuple[str, Dict]:
    if job_wrapper is None:
        return (
            "failing",
            {
                "reason": "no_jobs_found",
                "message": "No sync jobs found for connection",
            },
        )

    job = job_wrapper.get("job") or {}
    status = (job.get("status") or "").lower()
    updated_at = job.get("updatedAt")
    created_at = job.get("createdAt")

    details = {
        "jobId": job.get("id"),
        "status": status,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }

    if status in {"failed", "incomplete", "cancelled"}:
        return (
            "failing",
            {
                **details,
                "reason": "last_job_failed",
            },
        )

    if updated_at is None:
        return (
            "failing",
            {
                **details,
                "reason": "missing_timestamp",
            },
        )

    age_seconds = now_ts - int(updated_at)
    threshold_seconds = _stale_threshold_seconds(connection)
    if age_seconds > threshold_seconds:
        return (
            "stale",
            {
                **details,
                "reason": "job_outside_expected_window",
                "ageSeconds": age_seconds,
                "thresholdSeconds": threshold_seconds,
            },
        )

    return (
        "healthy",
        {
            **details,
            "ageSeconds": age_seconds,
        },
    )


def _filter_connections(connections: Iterable[Dict]) -> List[Dict]:
    if not CONNECTION_ALLOWLIST:
        return list(connections)
    return [
        conn
        for conn in connections
        if conn.get("connectionId") in CONNECTION_ALLOWLIST
    ]


def main() -> int:
    if not WORKSPACE_ID:
        print("AIRBYTE_WORKSPACE_ID is required", file=sys.stderr)
        return 2

    try:
        connections_response = _call_api(
            "/api/v1/connections/list", {"workspaceId": WORKSPACE_ID}
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    connections = _filter_connections(connections_response.get("connections") or [])
    now_ts = int(time.time())
    issues: List[Dict] = []
    rows: List[Dict] = []

    for connection in connections:
        connection_id = connection.get("connectionId")
        name = connection.get("name")
        try:
            job_wrapper = _latest_job(connection_id)
        except RuntimeError as exc:
            issues.append(
                {
                    "connectionId": connection_id,
                    "name": name,
                    "status": "failing",
                    "reason": "api_error",
                    "message": str(exc),
                }
            )
            continue

        status, detail = _classify(connection, job_wrapper, now_ts)
        row = {
            "connectionId": connection_id,
            "name": name,
            "status": status,
            "detail": detail,
            "scheduleType": connection.get("scheduleType"),
        }
        rows.append(row)
        if status != "healthy":
            issues.append(row)

    print(
        json.dumps(
            {
                "checkedAt": now_ts,
                "baseUrl": BASE_URL,
                "workspaceId": WORKSPACE_ID,
                "connections": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
