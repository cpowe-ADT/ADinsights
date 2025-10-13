from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from integrations.models import TenantAirbyteSyncStatus

AIRBYTE_STALE_THRESHOLD = timedelta(hours=1)
DBT_STALE_THRESHOLD = timedelta(hours=24)
RUN_RESULTS_PATH = (Path(settings.BASE_DIR).parent / "dbt" / "target" / "run_results.json")


def health(request):
    return JsonResponse({"status": "ok"})


def timezone_view(request):
    return JsonResponse({"timezone": settings.TIME_ZONE})


def airbyte_health(request):
    configured = _airbyte_is_configured()
    latest_status = TenantAirbyteSyncStatus.all_objects.order_by("-last_synced_at").first()
    response_data: Dict[str, Any] = {
        "component": "airbyte",
        "configured": configured,
        "last_sync": _serialize_sync_status(latest_status),
    }

    if not configured:
        response_data.update({"status": "misconfigured", "detail": "Airbyte API credentials are not fully configured."})
        return JsonResponse(response_data, status=503)

    if not latest_status or not latest_status.last_synced_at:
        response_data.update({"status": "no_recent_sync", "detail": "No Airbyte sync has completed yet."})
        return JsonResponse(response_data, status=503)

    now = timezone.now()
    is_stale = now - latest_status.last_synced_at > AIRBYTE_STALE_THRESHOLD
    response_data["stale"] = is_stale
    if is_stale:
        response_data.update({"status": "stale", "detail": "Latest Airbyte sync is older than the freshness threshold."})
        return JsonResponse(response_data, status=503)

    job_status = (latest_status.last_job_status or "").strip().lower()
    if job_status != "succeeded":
        detail_status = latest_status.last_job_status or "unknown"
        response_data.update(
            {
                "status": "sync_failed",
                "detail": f"Latest Airbyte sync finished with status '{detail_status}'.",
            }
        )
        return JsonResponse(response_data, status=502)

    response_data["status"] = "ok"
    return JsonResponse(response_data)


def dbt_health(request):
    response_data: Dict[str, Any] = {
        "component": "dbt",
        "run_results_path": str(RUN_RESULTS_PATH),
    }

    if not RUN_RESULTS_PATH.exists():
        response_data.update({"status": "missing_run_results", "detail": "dbt run_results.json not found."})
        return JsonResponse(response_data, status=503)

    try:
        run_results = json.loads(RUN_RESULTS_PATH.read_text())
    except json.JSONDecodeError as exc:  # pragma: no cover - unexpected corruption
        response_data.update({"status": "invalid_run_results", "detail": str(exc)})
        return JsonResponse(response_data, status=500)

    metadata = run_results.get("metadata", {})
    generated_at = metadata.get("generated_at")
    failing_models = [
        result.get("unique_id")
        for result in run_results.get("results", [])
        if result.get("status") not in {"success", "skipped"}
    ]

    response_data.update(
        {
            "generated_at": generated_at,
            "failing_models": failing_models,
        }
    )

    if failing_models:
        response_data.update({"status": "failing"})
        return JsonResponse(response_data, status=502)

    if generated_at:
        parsed_generated_at = _parse_timestamp(generated_at)
        if parsed_generated_at:
            is_stale = timezone.now() - parsed_generated_at > DBT_STALE_THRESHOLD
            response_data["stale"] = is_stale
            if is_stale:
                response_data.update({"status": "stale", "detail": "Latest dbt run is older than 24 hours."})
                return JsonResponse(response_data, status=503)

    response_data["status"] = "ok"
    return JsonResponse(response_data)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _airbyte_is_configured() -> bool:
    if not settings.AIRBYTE_API_URL:
        return False
    if settings.AIRBYTE_API_TOKEN:
        return True
    return bool(settings.AIRBYTE_USERNAME and settings.AIRBYTE_PASSWORD)


def _serialize_sync_status(status: TenantAirbyteSyncStatus | None) -> Dict[str, Any] | None:
    if not status:
        return None
    return {
        "tenant_id": str(status.tenant_id),
        "last_synced_at": status.last_synced_at.isoformat() if status.last_synced_at else None,
        "last_job_status": status.last_job_status,
        "last_job_id": status.last_job_id,
    }
