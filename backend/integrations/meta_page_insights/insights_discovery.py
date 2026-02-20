from __future__ import annotations

from datetime import timedelta
from typing import Literal

from django.utils import timezone

from integrations.meta_page_insights.meta_client import (
    MetaPageInsightsApiError,
    MetaPageInsightsClient,
)
from integrations.models import MetaMetricRegistry, MetaMetricSupportStatus, MetaPage
from integrations.services.metric_registry import mark_metric_invalid

ObjectType = Literal["page", "post"]


def validate_metrics(
    *,
    page: MetaPage,
    object_id: str,
    object_type: ObjectType,
    metrics: list[str],
    token: str,
    period: str | None = None,
    client: MetaPageInsightsClient | None = None,
) -> dict[str, bool]:
    now = timezone.now()
    since = (now - timedelta(days=2)).date()
    until = (now - timedelta(days=1)).date()
    resolved_period = period or ("day" if object_type == "page" else "lifetime")
    level = (
        MetaMetricRegistry.LEVEL_PAGE
        if object_type == "page"
        else MetaMetricRegistry.LEVEL_POST
    )

    support: dict[str, bool] = {metric: False for metric in metrics}
    errors: dict[str, dict] = {}
    own_client = client is None
    active_client = client or MetaPageInsightsClient.from_settings()

    try:
        if own_client:
            active_client.__enter__()

        def probe(chunk: list[str]) -> None:
            if not chunk:
                return
            try:
                active_client.fetch_insights(
                    object_type=object_type,
                    object_id=object_id,
                    metrics=chunk,
                    period=resolved_period,
                    since=since,
                    until=until,
                    token=token,
                )
                for metric_key in chunk:
                    support[metric_key] = True
            except MetaPageInsightsApiError as exc:
                if _is_invalid_metric_error(exc):
                    if len(chunk) == 1:
                        metric_key = chunk[0]
                        support[metric_key] = False
                        errors[metric_key] = {
                            "message": str(exc),
                            "error_code": exc.error_code,
                            "error_subcode": exc.error_subcode,
                        }
                        mark_metric_invalid(level, metric_key)
                        return
                    midpoint = max(len(chunk) // 2, 1)
                    probe(chunk[:midpoint])
                    probe(chunk[midpoint:])
                    return
                raise

        probe(metrics)

        for metric_key in metrics:
            MetaMetricSupportStatus.objects.update_or_create(
                tenant=page.tenant,
                page=page,
                level=level,
                metric_key=metric_key,
                defaults={
                    "supported": support.get(metric_key, False),
                    "last_checked_at": now,
                    "last_error": errors.get(metric_key, {}),
                },
            )
    finally:
        if own_client:
            active_client.__exit__(None, None, None)

    return support


def _is_invalid_metric_error(exc: MetaPageInsightsApiError) -> bool:
    if exc.error_code == 100:
        return True
    if exc.error_code == 3001:
        return True
    return False

