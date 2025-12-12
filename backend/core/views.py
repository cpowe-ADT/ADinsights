from __future__ import annotations

import json
from datetime import datetime, timedelta
from statistics import mean
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from accounts.tenant_context import tenant_context

from analytics.models import TenantMetricsSnapshot

from core.metrics import observe_dbt_run, render_metrics
from integrations.models import AirbyteJobTelemetry, TenantAirbyteSyncStatus

AIRBYTE_STALE_THRESHOLD = timedelta(hours=1)
DBT_STALE_THRESHOLD = timedelta(hours=24)
RUN_RESULTS_PATH = (Path(settings.BASE_DIR).parent / "dbt" / "target" / "run_results.json")

AIRBYTE_SUCCESS_STATUSES = {"succeeded", "success"}
AIRBYTE_FAILURE_STATUSES = {
    "failed",
    "error",
    "errored",
    "cancelled",
    "canceled",
}


def health(request):
    return JsonResponse({"status": "ok"})


def timezone_view(request):
    return JsonResponse({"timezone": settings.TIME_ZONE})


def health_version(request):
    return JsonResponse({"version": settings.APP_VERSION})


def airbyte_health(request):
    configured = _airbyte_is_configured()
    with tenant_context(None):
        latest_status = (
            TenantAirbyteSyncStatus.objects.select_related("last_connection")
            .order_by("-last_synced_at")
            .first()
        )
    response_data: Dict[str, Any] = {
        "component": "airbyte",
        "configured": configured,
        "last_sync": _serialize_sync_status(latest_status),
    }

    recent_jobs: list[AirbyteJobTelemetry] = []
    if latest_status and latest_status.last_connection_id:
        with tenant_context(str(latest_status.tenant_id) if latest_status.tenant_id else None):
            recent_jobs = list(
                AirbyteJobTelemetry.objects.filter(connection=latest_status.last_connection)
                .order_by("-started_at")[:5]
            )
    response_data["recent_jobs"] = [_serialize_job(job) for job in recent_jobs]
    response_data["job_summary"] = _summarise_jobs(recent_jobs) if recent_jobs else None

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
    if job_status:
        if job_status in AIRBYTE_FAILURE_STATUSES:
            detail_status = latest_status.last_job_status or "unknown"
            response_data.update(
                {
                    "status": "sync_failed",
                    "detail": f"Latest Airbyte sync finished with status '{detail_status}'.",
                }
            )
            if latest_status.last_job_error:
                response_data["error"] = latest_status.last_job_error
            return JsonResponse(response_data, status=502)
        if job_status not in AIRBYTE_SUCCESS_STATUSES:
            response_data["status"] = "pending"
            response_data["detail"] = f"Latest Airbyte sync is in status '{latest_status.last_job_status}'."
            return JsonResponse(response_data, status=200)

    response_data["status"] = "ok"
    snapshot = (
        TenantMetricsSnapshot.objects.filter(source="warehouse")
        .order_by("-generated_at", "-created_at")
        .first()
    )
    if snapshot:
        response_data["latest_snapshot_generated_at"] = snapshot.generated_at.isoformat()
    return JsonResponse(response_data)


def not_found(request, exception):  # noqa: ANN001 - Django signature
    return _json_error(
        code="not_found",
        message="The requested resource was not found.",
        status=404,
        path=request.path,
    )


def server_error(request):  # noqa: ANN001 - Django signature
    return _json_error(
        code="server_error",
        message="An unexpected error occurred. Please try again later.",
        status=500,
        path=request.path,
    )


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
    elapsed = metadata.get("elapsed_time")
    generated_at = metadata.get("generated_at")
    model_results = [
        {
            "unique_id": result.get("unique_id"),
            "status": result.get("status"),
            "message": result.get("message"),
            "adapter_response": result.get("adapter_response"),
        }
        for result in run_results.get("results", [])
    ]
    failing_models = [
        detail["unique_id"]
        for detail in model_results
        if detail.get("status") not in {"success", "skipped"}
    ]
    failing_details = [
        detail
        for detail in model_results
        if detail.get("status") not in {"success", "skipped"}
    ]

    response_data.update(
        {
            "generated_at": generated_at,
            "failing_models": failing_models,
            "failing_models_detail": failing_details,
        }
    )

    if failing_models:
        response_data.update({"status": "failing"})
        observe_dbt_run("failure", elapsed if isinstance(elapsed, (int, float)) else None)
        return JsonResponse(response_data, status=502)

    if generated_at:
        parsed_generated_at = _parse_timestamp(generated_at)
        if parsed_generated_at:
            is_stale = timezone.now() - parsed_generated_at > DBT_STALE_THRESHOLD
            response_data["stale"] = is_stale
            if is_stale:
                response_data.update({"status": "stale", "detail": "Latest dbt run is older than 24 hours."})
                return JsonResponse(response_data, status=503)

    if isinstance(elapsed, (int, float)):
        observe_dbt_run("success", float(elapsed))

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
        "last_job_updated_at": status.last_job_updated_at.isoformat()
        if status.last_job_updated_at
        else None,
        "last_job_completed_at": status.last_job_completed_at.isoformat()
        if status.last_job_completed_at
        else None,
        "last_job_error": status.last_job_error or None,
    }


def _serialize_job(job: AirbyteJobTelemetry) -> Dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "started_at": job.started_at.isoformat(),
        "duration_seconds": job.duration_seconds,
        "records_synced": job.records_synced,
        "bytes_synced": job.bytes_synced,
        "api_cost": float(job.api_cost) if job.api_cost is not None else None,
    }


def _summarise_jobs(jobs: Iterable[AirbyteJobTelemetry]) -> Dict[str, Any]:
    snapshots = list(jobs)
    if not snapshots:
        return {}

    latest = snapshots[0]

    def _mean(values: List[float]) -> float | None:
        return float(mean(values)) if values else None

    durations = [
        float(job.duration_seconds)
        for job in snapshots
        if job.duration_seconds is not None
    ]
    records = [
        float(job.records_synced)
        for job in snapshots
        if job.records_synced is not None
    ]
    costs = [
        float(job.api_cost)
        for job in snapshots
        if job.api_cost is not None
    ]

    return {
        "latest_job": _serialize_job(latest),
        "average_duration_seconds": _mean(durations),
        "average_records_synced": _mean(records),
        "average_api_cost": _mean(costs),
        "job_count": len(snapshots),
    }


def prometheus_metrics(request):
    payload, content_type = render_metrics()
    return HttpResponse(payload, content_type=content_type)


def _json_error(*, code: str, message: str, status: int, **details: Any) -> JsonResponse:
    payload: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        payload["error"].update(details)
    return JsonResponse(payload, status=status)
