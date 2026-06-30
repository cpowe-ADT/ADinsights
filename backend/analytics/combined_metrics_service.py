"""Service helpers for resolving combined metrics payloads."""

from __future__ import annotations

import logging
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

from integrations.clients.resolver import resolve_client_accounts
from integrations.models import (
    Client as IntegrationsClient,
    ClientPlatformAccount,
)

from .models import TenantMetricsSnapshot
from .platform_registry import (
    COMBINED_SUPPORTED,
    PLATFORM_GOOGLE_ADS,
    PLATFORM_META_ADS,
    PlatformRegistry,
    parse_enabled_param,
)
from .serializers import CombinedMetricsQueryParamsSerializer
from .warehouse_metrics import (
    enrich_combined_payload_metadata,
    load_filtered_warehouse_metrics,
)


logger = logging.getLogger(__name__)

# Adapters known to ignore client_scoped_* options. Remove an entry from this
# set when the adapter is patched to honour scoping.
_SCOPE_UNAWARE_ADAPTER_KEYS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CombinedMetricsResult:
    payload: dict[str, Any]
    source: str
    cache_outcome: str
    has_filters: bool
    snapshot_written: bool
    query_count: int
    # Sprint 6: populated when the caller passed ``client_id``. ``None`` for
    # the legacy path so the view can skip attaching the header/body key.
    client_resolution: dict[str, Any] | None = None


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
    client_resolution: dict[str, Any] | None = None,
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
    if client_resolution is not None:
        cached_payload = {**cached_payload, "client_resolution": client_resolution}
    return CombinedMetricsResult(
        payload=cached_payload,
        source=source,
        cache_outcome=cache_outcome,
        has_filters=has_filters,
        snapshot_written=False,
        query_count=query_count,
        client_resolution=client_resolution,
    )


def default_adapter_key(registry: Mapping[str, MetricsAdapter]) -> str:
    if "warehouse" in registry:
        return "warehouse"
    if "fake" in registry:
        return "fake"
    return next(iter(registry))


def parse_cache_flag(value: Any) -> bool:
    return str(value or "true").lower() != "false"


def _meta_account_variants(raw: str) -> list[str]:
    """Expand a Meta ad account id into both ``act_`` and bare-digit forms."""

    candidate = (raw or "").strip()
    if not candidate:
        return []
    if candidate.startswith("act_"):
        return [candidate, candidate[len("act_"):]]
    if candidate.isdigit():
        return [candidate, f"act_{candidate}"]
    return [candidate]


def _collect_tenant_platform_accounts(
    *, tenant_id: str
) -> tuple[list[str], list[str]]:
    """Return ``(meta_variants, google_customer_ids)`` for a tenant.

    Used when ``platforms=`` is sent without a ``client_id`` — we need every
    tenant-owned account id for the enabled platform(s) so the adapter can
    filter the combined payload down to that platform.

    Imports are scoped to avoid a circular module import at startup
    (``analytics.models`` and ``integrations.models`` both transitively import
    this module).
    """

    from analytics.models import AdAccount
    from integrations.models import GoogleAdsAccountMapping

    meta_externals = list(
        AdAccount.all_objects.filter(tenant_id=tenant_id).values_list(
            "external_id", flat=True
        )
    )
    meta_variants: list[str] = []
    seen: set[str] = set()
    for raw in meta_externals:
        for variant in _meta_account_variants(raw):
            if variant not in seen:
                seen.add(variant)
                meta_variants.append(variant)

    google_customer_ids = list(
        GoogleAdsAccountMapping.all_objects.filter(
            tenant_id=tenant_id, is_manager=False
        ).values_list("customer_id", flat=True)
    )
    google_customer_ids = [cid for cid in google_customer_ids if cid]
    return meta_variants, google_customer_ids


def _resolve_platform_only_scoping(
    *,
    tenant_id: str,
    enabled_override: list[str],
) -> tuple[dict[str, Any], PlatformRegistry, dict[str, Any]]:
    """Build scoping for a ``platforms=``-only request (no ``client_id``).

    The registry reports which platforms the tenant has configured (non-empty
    account sets) so the UI can still disable toggles for un-configured
    platforms, and the scoping dict zeroes out account id lists for disabled
    platforms to keep the adapter's row-level filter honest.
    """

    meta_variants, google_customer_ids = _collect_tenant_platform_accounts(
        tenant_id=tenant_id
    )

    configured_platforms: set[str] = set()
    if meta_variants:
        configured_platforms.add(PLATFORM_META_ADS)
    if google_customer_ids:
        configured_platforms.add(PLATFORM_GOOGLE_ADS)

    registry = PlatformRegistry.from_configured(
        configured=configured_platforms,
        enabled=enabled_override,
    )

    google_effective = (
        google_customer_ids if registry.is_enabled(PLATFORM_GOOGLE_ADS) else []
    )
    meta_effective = meta_variants if registry.is_enabled(PLATFORM_META_ADS) else []

    reason: str | None = None
    if not configured_platforms:
        reason = "no_platform_accounts_for_tenant"
    elif registry.enabled_platforms.isdisjoint(COMBINED_SUPPORTED):
        reason = "no_enabled_platforms"
    elif not google_effective and not meta_effective:
        reason = "all_platforms_disabled"

    resolution_meta: dict[str, Any] = {
        "client_id": None,
        "reason": reason,
        "google_customer_ids": google_customer_ids,
        "meta_ad_account_ids": meta_variants,
        "mcc_expansions": [],
        "platforms": registry.to_dict(),
        "scope": "platforms_only",
    }

    scoping = {
        "client_scoped_google_customer_ids": google_effective,
        "client_scoped_meta_ad_account_ids": meta_effective,
        "client_scope_requested": True,
    }
    return scoping, registry, resolution_meta


def resolve_client_scoping(
    *,
    tenant_id: str,
    query_params,
) -> tuple[dict[str, Any] | None, PlatformRegistry | None, dict[str, Any] | None]:  # noqa: ANN001
    """Resolve ``client_id`` into per-platform scoped id lists.

    Returns ``(scoping, registry, resolution_meta)`` where:

    * ``scoping`` — dict keyed by ``client_scoped_google_customer_ids`` and
      ``client_scoped_meta_ad_account_ids`` (with variant expansion) that the
      caller merges into the adapter options. ``None`` when no ``client_id``
      was provided (legacy path).
    * ``registry`` — :class:`PlatformRegistry` describing which platforms are
      configured / enabled for this request (honours ``platforms=`` toggles).
    * ``resolution_meta`` — body-key dict attached to the response alongside
      the ``X-Adinsights-Resolved-Via`` header. Carries a ``reason`` when the
      client resolves empty so the UI can render a helpful empty state.
    """

    client_id_raw = query_params.get("client_id") if hasattr(query_params, "get") else None
    platforms_raw = (
        query_params.get("platforms") if hasattr(query_params, "get") else None
    )
    enabled_override = parse_enabled_param(platforms_raw) if platforms_raw else None

    if not client_id_raw:
        # Sprint 10 polish: honour ``platforms=`` even when no Client is
        # selected. The Meta-only / Google-only workspaces send this to keep
        # the filter bar scoped to the route; without this branch the backend
        # silently dropped the parameter and returned the full combined
        # payload (so Meta dashboards leaked Google Ads rows, and vice versa).
        #
        # When the caller explicitly narrows to one platform we resolve the
        # tenant's accounts for that platform and fold them into the existing
        # ``client_scoped_*`` plumbing, which the warehouse + meta_direct
        # adapters already honour via ``_apply_filters``.
        if enabled_override is None:
            return None, None, None
        # If the request already carries an ``account_id`` filter we must NOT
        # inject the whole tenant's platform account set — the warehouse
        # adapter's client-scope logic is union-with-``account_id``, so adding
        # every tenant Meta account would widen the filter past the user's
        # single-account selection. In that case just leave scoping alone
        # (``account_id`` already restricts to one account, which lives on one
        # platform by nature).
        account_id_raw = (
            query_params.get("account_id") if hasattr(query_params, "get") else None
        )
        if account_id_raw and str(account_id_raw).strip():
            return None, None, None
        return _resolve_platform_only_scoping(
            tenant_id=tenant_id,
            enabled_override=enabled_override,
        )

    client_id = str(client_id_raw)
    try:
        bundle = resolve_client_accounts(
            tenant_id,
            client_id,
            platforms={
                ClientPlatformAccount.PLATFORM_META_ADS,
                ClientPlatformAccount.PLATFORM_GOOGLE_ADS,
            },
        )
    except (IntegrationsClient.DoesNotExist, ValueError):
        registry = PlatformRegistry.from_configured(
            configured=[],
            enabled=enabled_override,
        )
        return (
            {
                "client_scoped_google_customer_ids": [],
                "client_scoped_meta_ad_account_ids": [],
                # Sentinel — adapters check this to distinguish "scoping was
                # requested but returned empty" from "no scoping requested".
                "client_scope_requested": True,
            },
            registry,
            {
                "client_id": client_id,
                "reason": "client_not_found",
                "google_customer_ids": [],
                "meta_ad_account_ids": [],
                "mcc_expansions": [],
            },
        )

    meta_ids_raw = list(bundle.meta_ad_account_ids)
    google_ids = list(bundle.google_customer_ids)

    # Expand Meta ids to variants so both stored forms match ``__in`` filters.
    meta_variants: list[str] = []
    seen: set[str] = set()
    for linked in meta_ids_raw:
        for variant in _meta_account_variants(linked):
            if variant not in seen:
                seen.add(variant)
                meta_variants.append(variant)

    configured_platforms: set[str] = set()
    if meta_ids_raw:
        configured_platforms.add(PLATFORM_META_ADS)
    if google_ids:
        configured_platforms.add(PLATFORM_GOOGLE_ADS)

    registry = PlatformRegistry.from_configured(
        configured=configured_platforms,
        enabled=enabled_override,
    )

    # Honour platform toggles: when Meta is disabled the combined view should
    # not include Meta-only accounts. Same for Google Ads.
    google_effective = google_ids if registry.is_enabled(PLATFORM_GOOGLE_ADS) else []
    meta_effective = meta_variants if registry.is_enabled(PLATFORM_META_ADS) else []

    reason: str | None = None
    if not meta_ids_raw and not google_ids:
        reason = "no_platform_accounts_for_client"
    elif registry.enabled_platforms.isdisjoint(COMBINED_SUPPORTED):
        reason = "no_enabled_platforms"
    elif not google_effective and not meta_effective:
        reason = "all_platforms_disabled"

    resolution_meta: dict[str, Any] = {
        "client_id": client_id,
        "reason": reason,
        "google_customer_ids": google_ids,
        "meta_ad_account_ids": meta_ids_raw,
        "mcc_expansions": [
            {
                "manager_customer_id": exp.manager_customer_id,
                "child_customer_ids": list(exp.child_customer_ids),
            }
            for exp in bundle.mcc_expansions
        ],
        "platforms": registry.to_dict(),
    }

    scoping = {
        "client_scoped_google_customer_ids": google_effective,
        "client_scoped_meta_ad_account_ids": meta_effective,
        "client_scope_requested": True,
    }
    return scoping, registry, resolution_meta


def _resolve_filter_options(query_params) -> tuple[dict[str, Any], bool, list[str]]:  # noqa: ANN001
    filter_keys = (
        "start_date",
        "end_date",
        "parish",
        "account_id",
        "channels",
        "campaign_search",
        "client_id",
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
        or filters.get("client_id")
    )

    options = query_params.dict()
    if parishes:
        options["parish"] = parishes
    if channels:
        options["channels"] = channels
    options.update(filters)
    # UUID is not JSON-serialisable as-is; keep a stringified copy so adapters
    # can key caches on it without importing uuid.
    if "client_id" in filters and filters.get("client_id") is not None:
        options["client_id"] = str(filters["client_id"])
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

        # Sprint 6: resolve client_id BEFORE adapter dispatch so the scoping
        # reaches the adapter via the same ``options`` dict. Filtered-warehouse
        # and meta_direct both consume the injected keys.
        client_scoping, _registry, resolution_meta = resolve_client_scoping(
            tenant_id=tenant_id,
            query_params=query_params,
        )
        if client_scoping is not None:
            # Defensive: warn when scoping is injected but the selected adapter
            # is in the scope-unaware set. Non-breaking — just a log.
            if source in _SCOPE_UNAWARE_ADAPTER_KEYS:
                logger.warning(
                    "Adapter %r does not honour client_scoped_* options; "
                    "scoped request may return unscoped payload. "
                    "tenant_id=%r client_scope_requested=%r",
                    source,
                    tenant_id,
                    client_scoping.get("client_scope_requested"),
                )
            options = {**options, **client_scoping}
            has_filters = True
        if source == "warehouse" and has_filters:
            try:
                payload = load_filtered_warehouse_metrics(
                    tenant=tenant,
                    tenant_id=tenant_id,
                    options=options,
                    ttl_seconds=ttl_seconds,
                )
                if resolution_meta is not None:
                    payload = {**payload, "client_resolution": resolution_meta}
                return CombinedMetricsResult(
                    payload=payload,
                    source=source,
                    cache_outcome="warehouse_filtered_query",
                    has_filters=has_filters,
                    snapshot_written=False,
                    query_count=query_counter.count,
                    client_resolution=resolution_meta,
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
                        client_resolution=resolution_meta,
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
                client_resolution=resolution_meta,
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
        if resolution_meta is not None:
            combined = {**combined, "client_resolution": resolution_meta}
        return CombinedMetricsResult(
            payload=combined,
            source=source,
            cache_outcome=cache_outcome,
            has_filters=has_filters,
            snapshot_written=snapshot_written,
            query_count=query_counter.count,
            client_resolution=resolution_meta,
        )
