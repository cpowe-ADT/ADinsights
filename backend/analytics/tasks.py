from __future__ import annotations

import csv
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from celery import shared_task
from django.utils import timezone

from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from analytics.models import AISummary, ReportExportJob, TenantMetricsSnapshot
from analytics.snapshots import (
    default_snapshot_metrics,
    fetch_snapshot_metrics,
    snapshot_metrics_to_combined_payload,
)
from analytics.summaries import build_daily_summary_payload, summarize_daily_metrics
from analytics.notifications import send_daily_summary_email
from app.llm import get_llm_client
from core.metrics import observe_task
from core.tasks import BaseAdInsightsTask

logger = logging.getLogger(__name__)

SNAPSHOT_STALE_TTL_SECONDS = 60 * 60  # 60 minutes


@dataclass
class SnapshotOutcome:
    tenant_id: str
    status: str
    generated_at: datetime
    stale: bool
    row_counts: dict[str, int]


@dataclass
class DailySummaryOutcome:
    tenant_id: str
    status: str
    generated_at: datetime
    summary: str
    payload: dict[str, object]
    summary_status: str
    model_name: str


def _ensure_aware(dt: datetime | None) -> datetime:
    """Return an aware datetime, defaulting to now if missing."""
    if dt is None:
        return timezone.now()
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _snapshot_payload_for_tenant(tenant_id: str) -> tuple[dict, datetime, str]:
    metrics = fetch_snapshot_metrics(tenant_id=tenant_id)
    if metrics is None:
        metrics = default_snapshot_metrics(tenant_id=tenant_id)
        status = "default"
    else:
        status = "fetched"
    generated_at = _ensure_aware(metrics.generated_at)
    payload = snapshot_metrics_to_combined_payload(metrics)
    payload["snapshot_generated_at"] = generated_at.isoformat()
    return payload, generated_at, status


def _daily_summary_for_tenant(tenant_id: str) -> DailySummaryOutcome:
    metrics = fetch_snapshot_metrics(tenant_id=tenant_id)
    if metrics is None:
        metrics = default_snapshot_metrics(tenant_id=tenant_id)
        status = "default"
    else:
        status = "fetched"

    payload = build_daily_summary_payload(metrics)
    llm_client = get_llm_client()
    summary = summarize_daily_metrics(payload)
    summary_status = (
        AISummary.STATUS_GENERATED if llm_client.is_enabled() else AISummary.STATUS_FALLBACK
    )
    return DailySummaryOutcome(
        tenant_id=tenant_id,
        status=status,
        generated_at=_ensure_aware(metrics.generated_at),
        summary=summary,
        payload=payload,
        summary_status=summary_status,
        model_name=llm_client.model if llm_client.is_enabled() else "",
    )


def _safe_len(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def _count_payload_rows(payload: dict) -> dict[str, int]:
    campaign = payload.get("campaign") or {}
    return {
        "campaign_rows": _safe_len(campaign.get("rows")),
        "campaign_trend": _safe_len(campaign.get("trend")),
        "creative": _safe_len(payload.get("creative")),
        "budget": _safe_len(payload.get("budget")),
        "parish": _safe_len(payload.get("parish")),
    }


def generate_snapshots_for_tenants(tenant_ids: Sequence[str] | None = None) -> list[SnapshotOutcome]:
    tenants: Iterable[Tenant]
    queryset = Tenant.objects.all().order_by("created_at")
    if tenant_ids:
        queryset = queryset.filter(id__in=tenant_ids)
    tenants = queryset

    outcomes: list[SnapshotOutcome] = []
    for tenant in tenants:
        tenant_id = str(tenant.id)
        with tenant_context(tenant_id):
            payload, generated_at, status = _snapshot_payload_for_tenant(tenant_id)
            generated_at = _ensure_aware(generated_at)
            TenantMetricsSnapshot.objects.update_or_create(
                tenant=tenant,
                source="warehouse",
                defaults={
                    "payload": payload,
                    "generated_at": generated_at,
                },
            )
            row_counts = _count_payload_rows(payload)
            age_seconds = (timezone.now() - generated_at).total_seconds()
            is_stale = age_seconds > SNAPSHOT_STALE_TTL_SECONDS
            outcomes.append(
                SnapshotOutcome(
                    tenant_id=tenant_id,
                    status=status,
                    generated_at=generated_at,
                    stale=is_stale,
                    row_counts=row_counts,
                )
            )
            if is_stale:
                logger.warning(
                    "metrics.snapshot.stale",
                    extra={
                        "tenant_id": tenant_id,
                        "status": status,
                        "generated_at": generated_at.isoformat(),
                        "age_seconds": age_seconds,
                        "row_counts": row_counts,
                    },
                )
            logger.info(
                "metrics.snapshot.persisted",
                extra={
                    "tenant_id": tenant_id,
                    "status": status,
                    "generated_at": generated_at.isoformat(),
                    "age_seconds": age_seconds,
                    "row_counts": row_counts,
                },
            )
    return outcomes


def generate_daily_summaries_for_tenants(
    tenant_ids: Sequence[str] | None = None,
) -> list[DailySummaryOutcome]:
    tenants: Iterable[Tenant]
    queryset = Tenant.objects.all().order_by("created_at")
    if tenant_ids:
        queryset = queryset.filter(id__in=tenant_ids)
    tenants = queryset

    outcomes: list[DailySummaryOutcome] = []
    for tenant in tenants:
        tenant_id = str(tenant.id)
        with tenant_context(tenant_id):
            outcome = _daily_summary_for_tenant(tenant_id)
            summary_length = len(outcome.summary or "")
            send_daily_summary_email(
                tenant=tenant,
                summary=outcome.summary,
                generated_at=outcome.generated_at,
                status=outcome.status,
            )
            AISummary.objects.create(
                tenant=tenant,
                title=f"Daily summary for {outcome.generated_at.date().isoformat()}",
                summary=outcome.summary,
                payload=outcome.payload,
                source="daily_summary",
                model_name=outcome.model_name,
                status=outcome.summary_status,
                generated_at=outcome.generated_at,
            )
            logger.info(
                "metrics.daily_summary.generated",
                extra={
                    "tenant_id": tenant_id,
                    "status": outcome.status,
                    "generated_at": outcome.generated_at.isoformat(),
                    "summary_length": summary_length,
                },
            )
            outcomes.append(outcome)
    return outcomes


@shared_task(
    bind=True,
    name="analytics.sync_metrics_snapshots",
    base=BaseAdInsightsTask,
    max_retries=5,
)
def sync_metrics_snapshots(self, tenant_ids: list[str] | None = None) -> dict:
    started = timezone.now()
    try:
        outcomes = generate_snapshots_for_tenants(tenant_ids)
    except Exception as exc:  # pragma: no cover - surfaced via Celery retry mechanisms
        duration = (timezone.now() - started).total_seconds()
        observe_task(self.name, "failure", duration)
        logger.exception(
            "metrics.snapshot.failed",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "tenant_count": len(tenant_ids) if tenant_ids else None,
            },
        )
        raise self.retry_with_backoff(exc=exc, base_delay=60, max_delay=900)

    duration = (timezone.now() - started).total_seconds()
    observe_task(self.name, "success", duration)
    stale_tenant_ids = [outcome.tenant_id for outcome in outcomes if outcome.stale]
    status_counts = {
        "default": sum(outcome.status == "default" for outcome in outcomes),
        "fetched": sum(outcome.status == "fetched" for outcome in outcomes),
    }
    row_totals = {
        "campaign_rows": sum(outcome.row_counts.get("campaign_rows", 0) for outcome in outcomes),
        "campaign_trend": sum(outcome.row_counts.get("campaign_trend", 0) for outcome in outcomes),
        "creative": sum(outcome.row_counts.get("creative", 0) for outcome in outcomes),
        "budget": sum(outcome.row_counts.get("budget", 0) for outcome in outcomes),
        "parish": sum(outcome.row_counts.get("parish", 0) for outcome in outcomes),
    }
    generated_at_values = [outcome.generated_at for outcome in outcomes]
    logger.info(
        "metrics.snapshot.completed",
        extra={
            "task_id": getattr(getattr(self, "request", None), "id", None),
            "processed": len(outcomes),
            "duration_seconds": duration,
            "status_counts": status_counts,
            "stale_count": len(stale_tenant_ids),
            "stale_tenants_sample": stale_tenant_ids[:10],
            "row_totals": row_totals,
            "oldest_snapshot_generated_at": min(generated_at_values).isoformat()
            if generated_at_values
            else None,
            "newest_snapshot_generated_at": max(generated_at_values).isoformat()
            if generated_at_values
            else None,
        },
    )
    return {
        "processed": len(outcomes),
        "duration_seconds": duration,
        "status_counts": status_counts,
        "stale_count": len(stale_tenant_ids),
        "row_totals": row_totals,
        "oldest_snapshot_generated_at": min(generated_at_values).isoformat()
        if generated_at_values
        else None,
        "newest_snapshot_generated_at": max(generated_at_values).isoformat()
        if generated_at_values
        else None,
    }


@shared_task(
    bind=True,
    name="analytics.ai_daily_summary",
    base=BaseAdInsightsTask,
    max_retries=5,
)
def ai_daily_summary(self, tenant_ids: list[str] | None = None) -> dict:
    started = timezone.now()
    try:
        outcomes = generate_daily_summaries_for_tenants(tenant_ids)
    except Exception as exc:  # pragma: no cover - surfaced via Celery retry mechanisms
        duration = (timezone.now() - started).total_seconds()
        observe_task(self.name, "failure", duration)
        logger.exception(
            "metrics.daily_summary.failed",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "tenant_count": len(tenant_ids) if tenant_ids else None,
            },
        )
        raise self.retry_with_backoff(exc=exc, base_delay=60, max_delay=900)

    duration = (timezone.now() - started).total_seconds()
    observe_task(self.name, "success", duration)
    summary_lengths = [len(outcome.summary or "") for outcome in outcomes]
    logger.info(
        "metrics.daily_summary.completed",
        extra={
            "task_id": getattr(getattr(self, "request", None), "id", None),
            "processed": len(outcomes),
            "duration_seconds": duration,
            "summary_length_avg": (sum(summary_lengths) / len(summary_lengths))
            if summary_lengths
            else 0,
        },
    )
    return {
        "processed": len(outcomes),
        "duration_seconds": duration,
    }


def generate_ai_summary_for_tenant(
    *, tenant_id: str, task_id: str | None = None
) -> dict[str, object]:
    """Synchronously generate and persist one tenant summary."""

    with tenant_context(tenant_id):
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is None:
            return {"status": "missing_tenant"}

        outcome = _daily_summary_for_tenant(tenant_id)
        record = AISummary.objects.create(
            tenant=tenant,
            title=f"Daily summary for {outcome.generated_at.date().isoformat()}",
            summary=outcome.summary,
            payload=outcome.payload,
            source="manual_refresh",
            model_name=outcome.model_name,
            status=outcome.summary_status,
            generated_at=outcome.generated_at,
            task_id=task_id or "",
        )
        return {
            "status": "ok",
            "summary_id": str(record.id),
            "generated_at": record.generated_at.isoformat(),
        }


@shared_task(
    bind=True,
    name="analytics.run_report_export_job",
    base=BaseAdInsightsTask,
    max_retries=3,
)
def run_report_export_job(self, report_export_job_id: str) -> dict[str, object]:
    """Execute an async export job lifecycle for report downloads."""

    job = (
        ReportExportJob.all_objects.select_related("report", "tenant")
        .filter(id=report_export_job_id)
        .first()
    )
    if job is None:
        return {"status": "missing", "report_export_job_id": report_export_job_id}

    with tenant_context(str(job.tenant_id)):
        job.status = ReportExportJob.STATUS_RUNNING
        job.error_message = ""
        job.save(update_fields=["status", "error_message", "updated_at"])

        timestamp = timezone.now()
        source = str((job.report.filters or {}).get("source") or "").strip().lower()
        if source == "meta_pages":
            try:
                outcome = _export_meta_pages_report(job=job, timestamp=timestamp)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.exception(
                    "Meta pages export failed",
                    exc_info=exc,
                    extra={"tenant_id": str(job.tenant_id), "report_export_job_id": str(job.id)},
                )
                job.status = ReportExportJob.STATUS_FAILED
                job.error_message = str(exc)
                job.completed_at = timezone.now()
                job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
                return {"status": job.status, "report_export_job_id": str(job.id)}

            job.status = ReportExportJob.STATUS_COMPLETED
            job.artifact_path = str(outcome["artifact_path"])
            job.completed_at = timestamp
            job.metadata = outcome["metadata"]
            job.save(
                update_fields=[
                    "status",
                    "artifact_path",
                    "completed_at",
                    "metadata",
                    "updated_at",
                ]
            )
            return {
                "status": job.status,
                "report_export_job_id": str(job.id),
                "artifact_path": job.artifact_path,
            }

        extension = job.export_format.lower()
        artifact_path = f"/exports/{job.tenant_id}/{job.report_id}/{job.id}.{extension}"

        job.status = ReportExportJob.STATUS_COMPLETED
        job.artifact_path = artifact_path
        job.completed_at = timestamp
        job.metadata = {
            "report_name": job.report.name,
            "filters": job.report.filters,
            "layout": job.report.layout,
            "generated_at": timestamp.isoformat(),
        }
        job.save(
            update_fields=[
                "status",
                "artifact_path",
                "completed_at",
                "metadata",
                "updated_at",
            ]
        )
        return {
            "status": job.status,
            "report_export_job_id": str(job.id),
            "artifact_path": artifact_path,
        }


def _exports_base_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "integrations" / "exporter" / "out"


def _artifact_file_path(*, job: ReportExportJob, extension: str) -> tuple[str, Path]:
    artifact_path = f"/exports/{job.tenant_id}/{job.report_id}/{job.id}.{extension}"
    file_path = (_exports_base_dir() / artifact_path.lstrip("/")).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return artifact_path, file_path


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return date.fromisoformat(trimmed)


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    try:
        if isinstance(value, int):
            return f"{value:,}"
        num = float(value)
        if num.is_integer():
            return f"{int(num):,}"
        return f"{num:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _export_meta_pages_report(*, job: ReportExportJob, timestamp: datetime) -> dict[str, Any]:
    from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
    from django.db.models.expressions import OrderBy

    from integrations.models import MetaInsightPoint, MetaPage, MetaPost, MetaPostInsightPoint, MetaMetricRegistry
    from integrations.page_insights_serializers import resolve_date_range
    from integrations.services.metric_registry import get_default_metric_keys, resolve_metric_key

    tenant_id = str(job.tenant_id)
    page_id = str((job.report.filters or {}).get("page_id") or "").strip()
    if not page_id:
        raise ValueError("meta_pages export missing report.filters.page_id")

    page = MetaPage.objects.filter(tenant_id=tenant_id, page_id=page_id).first()
    if page is None:
        raise ValueError("Page not found for export.")

    request_payload = (job.metadata or {}).get("request") or {}
    if not isinstance(request_payload, dict):
        request_payload = {}

    date_preset = str(request_payload.get("date_preset") or "last_28d")
    since = _parse_iso_date(request_payload.get("since"))
    until = _parse_iso_date(request_payload.get("until"))
    since_date, until_date = resolve_date_range(date_preset=date_preset, since=since, until=until)

    trend_metric = str(request_payload.get("trend_metric") or "page_post_engagements").strip()
    trend_period = str(request_payload.get("trend_period") or "day").strip()
    posts_metric = str(request_payload.get("posts_metric") or "post_media_view").strip()
    posts_sort = str(request_payload.get("posts_sort") or "created_desc").strip()
    posts_limit = int(request_payload.get("posts_limit") or 10)
    q = str(request_payload.get("q") or "").strip()
    media_type = str(request_payload.get("media_type") or "").strip()

    page_kpi_keys = [key for key in get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE) if key]

    kpis_for_pdf: list[dict[str, str]] = []
    csv_rows: list[dict[str, Any]] = []

    for metric_key in page_kpi_keys:
        resolved = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, metric_key)
        base_qs = MetaInsightPoint.objects.filter(
            tenant_id=tenant_id,
            page=page,
            metric_key=resolved,
            period="day",
            end_time__date__gte=since_date,
            end_time__date__lte=until_date,
        )
        range_total = base_qs.aggregate(total=Sum("value_num")).get("total")
        last_day_total = base_qs.filter(end_time__date=until_date).aggregate(total=Sum("value_num")).get("total")

        range_value = float(range_total) if range_total is not None else None
        last_day_value = float(last_day_total) if last_day_total is not None else None

        csv_rows.append(
            {
                "record_type": "page_kpi_range",
                "tenant_id": tenant_id,
                "page_id": page_id,
                "post_id": "",
                "metric_key": metric_key,
                "resolved_metric_key": resolved,
                "period": "day",
                "since": since_date.isoformat(),
                "until": until_date.isoformat(),
                "end_time": "",
                "value": range_value if range_value is not None else "",
                "created_time": "",
                "media_type": "",
                "permalink": "",
                "message_snippet": "",
            }
        )
        csv_rows.append(
            {
                "record_type": "page_kpi_last_day",
                "tenant_id": tenant_id,
                "page_id": page_id,
                "post_id": "",
                "metric_key": metric_key,
                "resolved_metric_key": resolved,
                "period": "day",
                "since": since_date.isoformat(),
                "until": until_date.isoformat(),
                "end_time": until_date.isoformat(),
                "value": last_day_value if last_day_value is not None else "",
                "created_time": "",
                "media_type": "",
                "permalink": "",
                "message_snippet": "",
            }
        )

        kpis_for_pdf.append(
            {
                "label": metric_key,
                "rangeValue": _format_number(range_value),
                "lastDayValue": _format_number(last_day_value),
            }
        )

    resolved_trend = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, trend_metric)
    trend_rows = (
        MetaInsightPoint.objects.filter(
            tenant_id=tenant_id,
            page=page,
            metric_key=resolved_trend,
            period=trend_period,
            end_time__date__gte=since_date,
            end_time__date__lte=until_date,
        )
        .values("end_time__date")
        .annotate(value=Sum("value_num"))
        .order_by("end_time__date")
    )
    trend_points: list[dict[str, Any]] = []
    for row in trend_rows:
        end_date = row["end_time__date"]
        value = row["value"]
        trend_points.append(
            {
                "date": end_date.isoformat() if end_date else "",
                "value": float(value) if value is not None else None,
            }
        )
        csv_rows.append(
            {
                "record_type": "page_timeseries_point",
                "tenant_id": tenant_id,
                "page_id": page_id,
                "post_id": "",
                "metric_key": trend_metric,
                "resolved_metric_key": resolved_trend,
                "period": trend_period,
                "since": since_date.isoformat(),
                "until": until_date.isoformat(),
                "end_time": end_date.isoformat() if end_date else "",
                "value": float(value) if value is not None else "",
                "created_time": "",
                "media_type": "",
                "permalink": "",
                "message_snippet": "",
            }
        )

    posts_qs = MetaPost.objects.filter(
        tenant_id=tenant_id,
        page=page,
        created_time__date__gte=since_date,
        created_time__date__lte=until_date,
    )
    if q:
        posts_qs = posts_qs.filter(Q(message__icontains=q) | Q(post_id__icontains=q))
    if media_type:
        posts_qs = posts_qs.filter(media_type__iexact=media_type)

    resolved_posts_metric = resolve_metric_key(MetaMetricRegistry.LEVEL_POST, posts_metric)
    sort_value_sq = (
        MetaPostInsightPoint.objects.filter(
            tenant_id=tenant_id,
            post=OuterRef("pk"),
            metric_key=resolved_posts_metric,
        )
        .order_by("-end_time")
        .values("value_num")[:1]
    )
    if posts_sort == "metric_desc":
        posts_qs = posts_qs.annotate(
            _sort_value=Subquery(sort_value_sq, output_field=DecimalField())
        ).order_by(
            OrderBy(F("_sort_value"), descending=True, nulls_last=True),
            OrderBy(F("created_time"), descending=True, nulls_last=True),
            "pk",
        )
    else:
        posts_qs = posts_qs.order_by("-created_time", "pk")

    top_posts = list(posts_qs[:posts_limit])
    top_post_rows: list[dict[str, Any]] = []
    for post in top_posts:
        latest_value = (
            MetaPostInsightPoint.objects.filter(
                tenant_id=tenant_id,
                post=post,
                metric_key=resolved_posts_metric,
            )
            .order_by("-end_time")
            .values_list("value_num", flat=True)
            .first()
        )
        value_num = float(latest_value) if latest_value is not None else None
        snippet = (post.message or "")[:180]
        top_post_rows.append(
            {
                "createdTime": post.created_time.date().isoformat() if post.created_time else "—",
                "mediaType": post.media_type or "—",
                "messageSnippet": snippet or "—",
                "metricValue": _format_number(value_num),
                "permalink": post.permalink_url or "",
            }
        )
        csv_rows.append(
            {
                "record_type": "post_row",
                "tenant_id": tenant_id,
                "page_id": page_id,
                "post_id": post.post_id,
                "metric_key": posts_metric,
                "resolved_metric_key": resolved_posts_metric,
                "period": "lifetime",
                "since": since_date.isoformat(),
                "until": until_date.isoformat(),
                "end_time": "",
                "value": value_num if value_num is not None else "",
                "created_time": post.created_time.isoformat() if post.created_time else "",
                "media_type": post.media_type or "",
                "permalink": post.permalink_url or "",
                "message_snippet": snippet,
            }
        )

    extension = job.export_format.lower()
    artifact_path, file_path = _artifact_file_path(job=job, extension=extension)
    artifacts: dict[str, str] = {"requested": artifact_path}

    if extension == "csv":
        headers = [
            "record_type",
            "tenant_id",
            "page_id",
            "post_id",
            "metric_key",
            "resolved_metric_key",
            "period",
            "since",
            "until",
            "end_time",
            "value",
            "created_time",
            "media_type",
            "permalink",
            "message_snippet",
        ]
        with file_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow({key: row.get(key, "") for key in headers})
    else:
        pdf_path, pdf_file = _artifact_file_path(job=job, extension="pdf")
        png_path, png_file = _artifact_file_path(job=job, extension="png")

        exporter_dir = Path(__file__).resolve().parents[2] / "integrations" / "exporter"
        data_payload = {
            "template": "meta_pages_v1",
            "title": "Facebook Page Insights",
            "subtitle": f"Tenant {tenant_id} · Page: {page.name} ({page.page_id})",
            "dateRange": f"{since_date.isoformat()} → {until_date.isoformat()} (America/Jamaica)",
            "generatedAt": timestamp.isoformat(),
            "kpis": kpis_for_pdf,
            "trend": {
                "title": f"{trend_metric} trend",
                "note": f"Period: {trend_period}",
                "rangeLabel": f"{since_date.isoformat()} → {until_date.isoformat()}",
                "points": trend_points,
            },
            "topPosts": {
                "title": "Top posts",
                "metricLabel": posts_metric,
                "rows": top_post_rows,
            },
        }
        data_file = pdf_file.with_suffix(".json")
        data_file.write_text(json.dumps(data_payload), encoding="utf-8")

        cmd = [
            "node",
            "bin/export-report",
            "--data",
            str(data_file),
            "--out",
            str(pdf_file),
            "--png",
            str(png_file),
        ]
        subprocess.run(cmd, cwd=str(exporter_dir), check=True, capture_output=True, text=True)

        artifacts.update({"pdf": pdf_path, "png": png_path})
        artifact_path = png_path if extension == "png" else pdf_path

    metadata = {
        "redacted": True,
        "source": "meta_pages",
        "page_id": page.page_id,
        "page_name": page.name,
        "generated_at": timestamp.isoformat(),
        "since": since_date.isoformat(),
        "until": until_date.isoformat(),
        "trend_metric": trend_metric,
        "trend_period": trend_period,
        "posts_metric": posts_metric,
        "posts_sort": posts_sort,
        "artifacts": artifacts,
    }
    return {"artifact_path": artifact_path, "metadata": metadata}
