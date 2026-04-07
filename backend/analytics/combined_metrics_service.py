"""Service helpers for resolving combined metrics payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from django.db import DatabaseError, IntegrityError, connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from adapters.base import MetricsAdapter
from adapters.warehouse import (
    WAREHOUSE_DEFAULT_DETAIL,
    WAREHOUSE_SNAPSHOT_STATUS_DETAIL_KEY,
    WAREHOUSE_UNAVAILABLE_REASON_DEFAULT,
    WAREHOUSE_SNAPSHOT_STATUS_FETCHED,
    WAREHOUSE_SNAPSHOT_STATUS_KEY,
    WarehouseSnapshotUnavailable,
)

from .models import TenantMetricsSnapshot
from .serializers import CombinedMetricsQueryParamsSerializer
from .warehouse_metrics import (
    enrich_combined_payload_metadata,
    load_filtered_warehouse_metrics,
)


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


def _build_snapshot_result(
    *,
    snapshot: TenantMetricsSnapshot,
    source: str,
    cache_outcome: str,
    has_filters: bool,
    query_count: int,
) -> CombinedMetricsResult:
    canonical_payload = _validate_and_clean_combined_payload(
        payload=snapshot.payload,
        source=source,
    )
    cached_payload = _prepare_response_payload(
        payload=canonical_payload,
        source=source,
    )
    if "snapshot_generated_at" not in cached_payload:
        cached_payload["snapshot_generated_at"] = snapshot.generated_at.isoformat()
    return CombinedMetricsResult(
        payload=cached_payload,
        source=source,
        cache_outcome=cache_outcome,
        has_filters=has_filters,
        snapshot_written=False,
        query_count=query_count,
    )


def default_adapter_key(registry: Mapping[str, MetricsAdapter]) -> str:
    if "warehouse" in registry:
        return "warehouse"
    if "fake" in registry:
        return "fake"
    return next(iter(registry))


def parse_cache_flag(value: Any) -> bool:
    return str(value or "true").lower() != "false"


def _resolve_filter_options(query_params) -> tuple[dict[str, Any], bool, list[str]]:  # noqa: ANN001
    filter_keys = (
        "start_date",
        "end_date",
        "parish",
        "account_id",
        "channels",
        "campaign_search",
    )
    if not any(key in query_params for key in filter_keys):
        return query_params.dict(), False, []

    filters_data = query_params
    parishes = query_params.getlist("parish")
    if len(parishes) > 1:
        filters_data = query_params.copy()
        filters_data["parish"] = ",".join(parishes)
    channels = query_params.getlist("channels")
    if len(channels) > 1:
        if filters_data is query_params:
            filters_data = query_params.copy()
        filters_data["channels"] = ",".join(channels)

    filters_serializer = CombinedMetricsQueryParamsSerializer(data=filters_data)
    filters_serializer.is_valid(raise_exception=True)
    filters = filters_serializer.validated_data
    has_filters = bool(
        filters.get("start_date")
        or filters.get("end_date")
        or filters.get("parish")
        or filters.get("account_id")
        or filters.get("channels")
        or filters.get("campaign_search")
    )

    options = query_params.dict()
    if parishes:
        options["parish"] = parishes
    if channels:
        options["channels"] = channels
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


def _parse_snapshot_timestamp(candidate: Any) -> datetime | None:
    if isinstance(candidate, datetime):
        resolved = candidate
    elif isinstance(candidate, str):
        parsed = parse_datetime(candidate)
        resolved = parsed if parsed is not None else None
    else:
        resolved = None
    if resolved is None:
        return None
    if timezone.is_naive(resolved):  # pragma: no cover - depends on db backend
        resolved = timezone.make_aware(resolved)
    return resolved


def _resolve_snapshot_timestamp(candidate: Any) -> datetime:
    resolved = _parse_snapshot_timestamp(candidate)
    if resolved is None:
        resolved = timezone.now()
    return resolved


def _normalize_combined_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], datetime]:
    normalized: dict[str, Any] = dict(payload)
    metrics = normalized.get("metrics")
    if isinstance(metrics, Mapping):
        normalized.setdefault("campaign", metrics.get("campaign_metrics"))
        normalized.setdefault("creative", metrics.get("creative_metrics") or [])
        normalized.setdefault("budget", metrics.get("budget_metrics") or [])
        normalized.setdefault("parish", metrics.get("parish_metrics") or [])

    has_snapshot_key = "snapshot_generated_at" in normalized or "generated_at" in normalized
    raw_snapshot = (
        normalized.get("snapshot_generated_at")
        if "snapshot_generated_at" in normalized
        else normalized.get("generated_at")
    )
    parsed_snapshot = _parse_snapshot_timestamp(raw_snapshot)
    generated_at = parsed_snapshot or timezone.now()
    if parsed_snapshot is not None:
        normalized["snapshot_generated_at"] = parsed_snapshot.isoformat()
    elif has_snapshot_key and raw_snapshot is None:
        normalized["snapshot_generated_at"] = None
    else:
        normalized["snapshot_generated_at"] = generated_at.isoformat()
    normalized.pop("generated_at", None)
    return normalized, generated_at


def _validate_and_clean_combined_payload(
    *,
    payload: Mapping[str, Any],
    source: str,
) -> dict[str, Any]:
    cleaned = dict(payload)
    if source == "warehouse":
        snapshot_status = cleaned.pop(WAREHOUSE_SNAPSHOT_STATUS_KEY, None)
        snapshot_status_detail = cleaned.pop(WAREHOUSE_SNAPSHOT_STATUS_DETAIL_KEY, None)
        if snapshot_status and snapshot_status != WAREHOUSE_SNAPSHOT_STATUS_FETCHED:
            raise WarehouseSnapshotUnavailable(
                snapshot_status_detail or WAREHOUSE_DEFAULT_DETAIL,
                reason=WAREHOUSE_UNAVAILABLE_REASON_DEFAULT,
            )
    else:
        cleaned.pop(WAREHOUSE_SNAPSHOT_STATUS_KEY, None)
        cleaned.pop(WAREHOUSE_SNAPSHOT_STATUS_DETAIL_KEY, None)
    return cleaned


def _prepare_response_payload(
    *,
    payload: Mapping[str, Any],
    source: str,
) -> dict[str, Any]:
    response_payload = dict(payload)
    if source == "warehouse":
        response_payload = enrich_combined_payload_metadata(response_payload)
    return response_payload


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
        if source == "warehouse" and has_filters:
            try:
                payload = load_filtered_warehouse_metrics(
                    tenant=tenant,
                    tenant_id=tenant_id,
                    options=options,
                    ttl_seconds=ttl_seconds,
                )
                return CombinedMetricsResult(
                    payload=payload,
                    source=source,
                    cache_outcome="warehouse_filtered_query",
                    has_filters=has_filters,
                    snapshot_written=False,
                    query_count=query_counter.count,
                )
            except DatabaseError:
                if connection.vendor != "sqlite":
                    raise
                snapshot = TenantMetricsSnapshot.latest_for(tenant=tenant, source=source)
                if snapshot:
                    return _build_snapshot_result(
                        snapshot=snapshot,
                        source=source,
                        cache_outcome="warehouse_filtered_snapshot_fallback",
                        has_filters=has_filters,
                        query_count=query_counter.count,
                    )
                raise

        snapshot = (
            TenantMetricsSnapshot.latest_for(tenant=tenant, source=source)
            if cache_enabled and not has_filters
            else None
        )
        if snapshot and snapshot.is_fresh(ttl_seconds):
            return _build_snapshot_result(
                snapshot=snapshot,
                source=source,
                cache_outcome="hit",
                has_filters=has_filters,
                query_count=query_counter.count,
            )

        payload = adapter.fetch_metrics(
            tenant_id=tenant_id,
            options=options,
        )
        canonical_payload, generated_at = _normalize_combined_payload(payload)
        canonical_payload = _validate_and_clean_combined_payload(
            payload=canonical_payload,
            source=source,
        )
        combined = _prepare_response_payload(
            payload=canonical_payload,
            source=source,
        )
        snapshot_written = False
        if not has_filters:
            if snapshot is not None:
                if (
                    snapshot.generated_at == generated_at
                    and _payloads_equal(snapshot.payload, canonical_payload)
                ):
                    snapshot_written = False
                else:
                    snapshot.payload = canonical_payload
                    snapshot.generated_at = generated_at
                    snapshot.save(update_fields=["payload", "generated_at", "updated_at"])
                    snapshot_written = True
            elif cache_enabled:
                _create_snapshot_after_cache_miss(
                    tenant=tenant,
                    source=source,
                    payload=canonical_payload,
                    generated_at=generated_at,
                )
                snapshot_written = True
            else:
                _upsert_snapshot_without_cached_row(
                    tenant=tenant,
                    source=source,
                    payload=canonical_payload,
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
