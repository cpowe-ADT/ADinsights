"""Service helpers for resolving combined metrics payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from django.db import IntegrityError, connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from adapters.base import MetricsAdapter

from .models import TenantMetricsSnapshot
from .serializers import CombinedMetricsQueryParamsSerializer


@dataclass(frozen=True)
class CombinedMetricsResult:
    payload: dict[str, Any]
    source: str
    cache_outcome: str
    has_filters: bool
    snapshot_written: bool
    query_count: int


def _payloads_equal(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    return existing == candidate


class _DatabaseQueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):  # noqa: ANN001
        self.count += 1
        return execute(sql, params, many, context)


def default_adapter_key(registry: Mapping[str, MetricsAdapter]) -> str:
    if "warehouse" in registry:
        return "warehouse"
    if "fake" in registry:
        return "fake"
    return next(iter(registry))


def parse_cache_flag(value: Any) -> bool:
    return str(value or "true").lower() != "false"


def _resolve_filter_options(query_params) -> tuple[dict[str, Any], bool, list[str]]:  # noqa: ANN001
    if not any(key in query_params for key in ("start_date", "end_date", "parish")):
        return query_params.dict(), False, []

    filters_data = query_params
    parishes = query_params.getlist("parish")
    if len(parishes) > 1:
        filters_data = query_params.copy()
        filters_data["parish"] = ",".join(parishes)

    filters_serializer = CombinedMetricsQueryParamsSerializer(data=filters_data)
    filters_serializer.is_valid(raise_exception=True)
    filters = filters_serializer.validated_data
    has_filters = bool(
        filters.get("start_date") or filters.get("end_date") or filters.get("parish")
    )

    options = query_params.dict()
    if parishes:
        options["parish"] = parishes
    options.update(filters)
    return options, has_filters, parishes


def _create_snapshot_after_cache_miss(
    *,
    tenant,
    source: str,
    payload: Mapping[str, Any],
    generated_at: datetime,
) -> None:
    try:
        TenantMetricsSnapshot.objects.create(
            tenant=tenant,
            source=source,
            payload=dict(payload),
            generated_at=generated_at,
        )
    except IntegrityError:
        TenantMetricsSnapshot.objects.filter(tenant=tenant, source=source).update(
            payload=dict(payload),
            generated_at=generated_at,
            updated_at=timezone.now(),
        )


def _upsert_snapshot_without_cached_row(
    *,
    tenant,
    source: str,
    payload: Mapping[str, Any],
    generated_at: datetime,
) -> None:
    updated = TenantMetricsSnapshot.objects.filter(tenant=tenant, source=source).update(
        payload=dict(payload),
        generated_at=generated_at,
        updated_at=timezone.now(),
    )
    if updated:
        return
    _create_snapshot_after_cache_miss(
        tenant=tenant,
        source=source,
        payload=payload,
        generated_at=generated_at,
    )


def _resolve_snapshot_timestamp(candidate: Any) -> datetime:
    if isinstance(candidate, datetime):
        resolved = candidate
    elif isinstance(candidate, str):
        parsed = parse_datetime(candidate)
        resolved = parsed if parsed is not None else None
    else:
        resolved = None
    if resolved is None:
        resolved = timezone.now()
    if timezone.is_naive(resolved):  # pragma: no cover - depends on db backend
        resolved = timezone.make_aware(resolved)
    return resolved


def _normalize_combined_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], datetime]:
    normalized: dict[str, Any] = dict(payload)
    metrics = normalized.get("metrics")
    if isinstance(metrics, Mapping):
        normalized.setdefault("campaign", metrics.get("campaign_metrics"))
        normalized.setdefault("creative", metrics.get("creative_metrics") or [])
        normalized.setdefault("budget", metrics.get("budget_metrics") or [])
        normalized.setdefault("parish", metrics.get("parish_metrics") or [])

    generated_at = _resolve_snapshot_timestamp(
        normalized.get("snapshot_generated_at") or normalized.get("generated_at")
    )
    normalized["snapshot_generated_at"] = generated_at.isoformat()
    normalized.pop("generated_at", None)
    return normalized, generated_at


def load_combined_metrics_payload(
    *,
    tenant,
    tenant_id: str,
    source: str,
    adapter: MetricsAdapter,
    query_params,
    ttl_seconds: int,
    cache_enabled: bool,
) -> CombinedMetricsResult:  # noqa: ANN001
    query_counter = _DatabaseQueryCounter()
    with connection.execute_wrapper(query_counter):
        options, has_filters, _parishes = _resolve_filter_options(query_params)
        snapshot = (
            TenantMetricsSnapshot.latest_for(tenant=tenant, source=source)
            if cache_enabled and not has_filters
            else None
        )
        if snapshot and snapshot.is_fresh(ttl_seconds):
            cached_payload = dict(snapshot.payload)
            cached_payload["snapshot_generated_at"] = snapshot.generated_at.isoformat()
            return CombinedMetricsResult(
                payload=cached_payload,
                source=source,
                cache_outcome="hit",
                has_filters=has_filters,
                snapshot_written=False,
                query_count=query_counter.count,
            )

        payload = adapter.fetch_metrics(
            tenant_id=tenant_id,
            options=options,
        )
        combined, generated_at = _normalize_combined_payload(payload)
        snapshot_written = False
        if not has_filters:
            if snapshot is not None:
                if (
                    snapshot.generated_at == generated_at
                    and _payloads_equal(snapshot.payload, combined)
                ):
                    snapshot_written = False
                else:
                    snapshot.payload = combined
                    snapshot.generated_at = generated_at
                    snapshot.save(update_fields=["payload", "generated_at", "updated_at"])
                    snapshot_written = True
            elif cache_enabled:
                _create_snapshot_after_cache_miss(
                    tenant=tenant,
                    source=source,
                    payload=combined,
                    generated_at=generated_at,
                )
                snapshot_written = True
            else:
                _upsert_snapshot_without_cached_row(
                    tenant=tenant,
                    source=source,
                    payload=combined,
                    generated_at=generated_at,
                )
                snapshot_written = True

        cache_outcome = "filtered"
        if not has_filters:
            cache_outcome = "miss" if cache_enabled else "disabled"
        return CombinedMetricsResult(
            payload=combined,
            source=source,
            cache_outcome=cache_outcome,
            has_filters=has_filters,
            snapshot_written=snapshot_written,
            query_count=query_counter.count,
        )
