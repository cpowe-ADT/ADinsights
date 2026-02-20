"""Celery tasks for integrations."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any, List

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from alerts.models import AlertRun
from accounts.tenant_context import tenant_context
from analytics.models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord
from core.metrics import observe_meta_token_refresh_attempt, observe_meta_token_validation
from core.observability import emit_observability_event

from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)
from integrations.meta_graph import MetaGraphClient, MetaGraphClientError, MetaGraphConfigurationError
from integrations.meta_page_insights.insights_discovery import validate_metrics
from integrations.meta_page_insights.metric_pack_loader import is_blocked_metric
from integrations.meta_page_insights.token_service import sync_pages_for_connection
from integrations.models import (
    APIErrorLog,
    AirbyteConnection,
    MetaAccountSyncState,
    MetaConnection,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)
from integrations.services.insights_parser import (
    normalize_breakdown_key,
    normalize_insights_payload,
)
from integrations.services.meta_graph_client import (
    MetaInsightsGraphClient,
    MetaInsightsGraphClientError,
)
from integrations.services.metric_registry import (
    get_default_metric_keys,
    mark_metric_invalid,
    seed_default_metrics,
    update_metric_metadata,
)
from core.tasks import BaseAdInsightsTask

logger = logging.getLogger(__name__)
DEFAULT_META_INSIGHTS_LOOKBACK_DAYS = 3
DEFAULT_META_INSIGHTS_LEVEL = "ad"


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def trigger_scheduled_airbyte_syncs(self):  # noqa: ANN001
    """Trigger due Airbyte syncs using the shared scheduling service."""

    triggered = 0
    with tenant_context(None):
        try:
            with AirbyteClient.from_settings() as client:
                service = AirbyteSyncService(client)
                updates = service.sync_due_connections()
                AirbyteConnection.persist_sync_updates(updates)
                triggered = len(updates)
        except AirbyteClientConfigurationError as exc:
            logger.error(
                "airbyte.sync.misconfigured",
                extra={"triggered": triggered},
                exc_info=exc,
            )
            raise self.retry_with_backoff(exc=exc, base_delay=300, max_delay=900)
        except AirbyteClientError as exc:
            logger.warning(
                "airbyte.sync.failed",
                extra={"triggered": triggered},
                exc_info=exc,
            )
            raise self.retry_with_backoff(exc=exc)
    logger.info("airbyte.sync.completed", extra={"triggered": triggered})
    return triggered


@shared_task(bind=True)
def remind_expiring_credentials(self):  # noqa: ANN001
    """Create alert runs for credentials nearing expiry."""

    window_days = getattr(settings, "CREDENTIAL_ROTATION_REMINDER_DAYS", 7)
    now = timezone.now()
    window_end = now + timedelta(days=window_days)

    with tenant_context(None):
        credentials = list(
            PlatformCredential.all_objects.filter(
                expires_at__isnull=False,
                expires_at__lte=window_end,
            ).select_related("tenant")
        )

    if not credentials:
        return {"processed": 0}

    rows: List[dict[str, object]] = []
    for credential in credentials:
        expires_at = credential.expires_at
        if expires_at is None:
            continue
        tenant_id = str(credential.tenant_id)
        with tenant_context(tenant_id):
            delta = (expires_at - now).days
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "provider": credential.provider,
                    "credential_ref": _mask_identifier(credential.account_id),
                    "expires_at": expires_at.isoformat(),
                    "days_until_expiry": delta,
                    "status": "expired" if expires_at <= now else "expiring",
                }
            )

    AlertRun.objects.create(
        rule_slug="credential_rotation_due",
        status=AlertRun.Status.SUCCESS,
        row_count=len(rows),
        raw_results=rows,
        llm_summary=f"{len(rows)} credential(s) require rotation.",
        error_message="",
    )

    return {"processed": len(rows)}


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def refresh_meta_tokens(self):  # noqa: ANN001
    """Validate and refresh Meta credentials while preserving tenant isolation."""

    now = timezone.now()
    refresh_window_days = int(getattr(settings, "META_TOKEN_REFRESH_WINDOW_DAYS", 7))
    refresh_window_end = now + timedelta(days=refresh_window_days)

    with tenant_context(None):
        credentials = list(
            PlatformCredential.all_objects.filter(
                provider=PlatformCredential.META,
            ).select_related("tenant")
        )

    if not credentials:
        return {"processed": 0, "validated": 0, "refreshed": 0}

    processed = 0
    validated = 0
    refreshed = 0
    repeated_failures: list[dict[str, object]] = []

    try:
        client = MetaGraphClient.from_settings()
    except MetaGraphConfigurationError as exc:
        logger.error("meta.credential_lifecycle.misconfigured", exc_info=exc)
        raise self.retry_with_backoff(exc=exc, base_delay=300, max_delay=900)

    with client:
        for credential in credentials:
            processed += 1
            tenant_id = str(credential.tenant_id)
            previous_status = credential.token_status
            with tenant_context(tenant_id):
                access_token = credential.decrypt_access_token()
                if not access_token:
                    _mark_reauth_required(
                        credential,
                        now=now,
                        reason="Stored Meta credential is missing an access token.",
                    )
                    observe_meta_token_validation("invalid")
                    if previous_status in {
                        PlatformCredential.TOKEN_STATUS_INVALID,
                        PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
                    }:
                        repeated_failures.append(
                            {
                                "tenant_id": tenant_id,
                                "credential_ref": _mask_identifier(credential.account_id),
                                "reason": credential.token_status_reason,
                            }
                        )
                    continue

                try:
                    token_debug = client.debug_token(input_token=access_token)
                except MetaGraphClientError as exc:
                    _mark_reauth_required(
                        credential,
                        now=now,
                        reason=f"Meta debug_token failed: {exc}",
                    )
                    observe_meta_token_validation("invalid")
                    if previous_status in {
                        PlatformCredential.TOKEN_STATUS_INVALID,
                        PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
                    }:
                        repeated_failures.append(
                            {
                                "tenant_id": tenant_id,
                                "credential_ref": _mask_identifier(credential.account_id),
                                "reason": credential.token_status_reason,
                            }
                        )
                    continue

                if not bool(token_debug.get("is_valid")):
                    _mark_reauth_required(
                        credential,
                        now=now,
                        reason="Meta debug_token returned is_valid=false.",
                    )
                    observe_meta_token_validation("invalid")
                    if previous_status in {
                        PlatformCredential.TOKEN_STATUS_INVALID,
                        PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
                    }:
                        repeated_failures.append(
                            {
                                "tenant_id": tenant_id,
                                "credential_ref": _mask_identifier(credential.account_id),
                                "reason": credential.token_status_reason,
                            }
                        )
                    continue

                expires_at = _coerce_epoch_datetime(token_debug.get("expires_at")) or credential.expires_at
                issued_at = _coerce_epoch_datetime(token_debug.get("issued_at")) or credential.issued_at or now
                scopes = token_debug.get("scopes")
                granted_scopes = (
                    sorted({str(scope).strip() for scope in scopes if isinstance(scope, str) and str(scope).strip()})
                    if isinstance(scopes, list)
                    else credential.granted_scopes
                )
                token_status, status_reason = _token_status_for_expiry(expires_at=expires_at, now=now)
                credential.expires_at = expires_at
                credential.issued_at = issued_at
                credential.granted_scopes = granted_scopes
                credential.last_validated_at = now
                credential.token_status = token_status
                credential.token_status_reason = status_reason
                credential.save(
                    update_fields=[
                        "expires_at",
                        "issued_at",
                        "granted_scopes",
                        "last_validated_at",
                        "token_status",
                        "token_status_reason",
                        "updated_at",
                    ]
                )
                validated += 1
                observe_meta_token_validation(token_status)

                if (
                    credential.auth_mode == PlatformCredential.AUTH_MODE_USER_OAUTH
                    and expires_at is not None
                    and expires_at <= refresh_window_end
                ):
                    credential.last_refresh_attempt_at = now
                    credential.save(update_fields=["last_refresh_attempt_at", "updated_at"])
                    observe_meta_token_refresh_attempt(
                        auth_mode=credential.auth_mode,
                        status="attempted",
                    )
                    try:
                        refreshed_token = client.exchange_for_long_lived_user_token(
                            short_lived_user_token=access_token
                        )
                    except MetaGraphClientError as exc:
                        _mark_reauth_required(
                            credential,
                            now=now,
                            reason=f"Meta token refresh failed: {exc}",
                            include_refresh_attempt=True,
                        )
                        observe_meta_token_refresh_attempt(
                            auth_mode=credential.auth_mode,
                            status="failed",
                        )
                        continue

                    refreshed_expires_at = expires_at
                    if refreshed_token.expires_in is not None:
                        refreshed_expires_at = now + timedelta(seconds=refreshed_token.expires_in)
                    refreshed_status, refreshed_reason = _token_status_for_expiry(
                        expires_at=refreshed_expires_at,
                        now=now,
                    )
                    credential.expires_at = refreshed_expires_at
                    credential.last_refresh_attempt_at = now
                    credential.last_refreshed_at = now
                    credential.token_status = refreshed_status
                    credential.token_status_reason = refreshed_reason
                    credential.set_raw_tokens(refreshed_token.access_token, None)
                    credential.save()
                    refreshed += 1
                    observe_meta_token_refresh_attempt(
                        auth_mode=credential.auth_mode,
                        status="success",
                    )

            emit_observability_event(
                logger,
                "meta.credential_lifecycle.processed",
                tenant_id=tenant_id,
                credential_ref=_mask_identifier(credential.account_id),
                token_status=credential.token_status,
            )

    if repeated_failures:
        AlertRun.objects.create(
            rule_slug="meta_token_validation_repeated_failures",
            status=AlertRun.Status.SUCCESS,
            row_count=len(repeated_failures),
            raw_results=repeated_failures,
            llm_summary=f"{len(repeated_failures)} Meta credential(s) still failing validation.",
            error_message="",
        )

    _create_stale_meta_sync_state_alert(now=now)
    return {
        "processed": processed,
        "validated": validated,
        "refreshed": refreshed,
        "repeated_failures": len(repeated_failures),
    }


@shared_task(
    bind=True,
    base=BaseAdInsightsTask,
    max_retries=5,
    name="integrations.tasks.refresh_meta_credentials_lifecycle",
)
def refresh_meta_credentials_lifecycle(self):  # noqa: ANN001
    """Backward-compatible alias for refresh_meta_tokens."""

    return refresh_meta_tokens.run()


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_accounts(self):  # noqa: ANN001
    """Sync /me/adaccounts into analytics.AdAccount."""

    return _sync_meta_accounts_core(task=self)


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_hierarchy(self):  # noqa: ANN001
    """Sync campaigns, adsets, and ads for each tenant Meta ad account."""

    return _sync_meta_hierarchy_core(task=self)


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_insights_incremental(
    self,  # noqa: ANN001
    level: str = DEFAULT_META_INSIGHTS_LEVEL,
    since: str | None = None,
    until: str | None = None,
):
    """Sync Meta insights using a bounded incremental date window."""

    return _sync_meta_insights_core(task=self, level=level, since=since, until=until)


def _sync_meta_accounts_core(*, task) -> dict[str, int]:
    credentials = _meta_credentials()
    if not credentials:
        return {"processed": 0, "succeeded": 0, "failed": 0, "accounts_synced": 0}

    try:
        client = MetaGraphClient.from_settings()
    except MetaGraphConfigurationError as exc:
        logger.error("meta.sync.accounts.misconfigured", exc_info=exc)
        raise task.retry_with_backoff(exc=exc, base_delay=300, max_delay=900)

    processed = succeeded = failed = accounts_synced = 0
    correlation_id = getattr(getattr(task, "request", None), "id", "") or ""
    now = timezone.now()
    with client:
        for credential in credentials:
            processed += 1
            tenant_id = str(credential.tenant_id)
            with tenant_context(tenant_id):
                access_token = credential.decrypt_access_token()
                if not access_token:
                    _mark_reauth_required(
                        credential,
                        now=now,
                        reason="Stored Meta credential is missing an access token.",
                    )
                    failed += 1
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=credential.account_id,
                        job_status="failed",
                        job_error="Missing stored Meta access token.",
                        sync_completed_at=now,
                    )
                    continue
                try:
                    rows = client.list_ad_accounts(user_access_token=access_token)
                except MetaGraphClientError as exc:
                    failed += 1
                    _log_meta_api_error(
                        tenant=credential.tenant,
                        account_id=credential.account_id,
                        endpoint="/me/adaccounts",
                        exc=exc,
                        correlation_id=correlation_id,
                    )
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=credential.account_id,
                        job_status="failed",
                        job_error=str(exc),
                        sync_completed_at=timezone.now(),
                    )
                    continue

                batch_count = 0
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    external_id = _normalize_meta_account_id(str(row.get("id") or row.get("account_id") or "").strip())
                    if not external_id:
                        continue
                    account_id = str(row.get("account_id") or "").strip()
                    status_value = row.get("account_status")
                    status_text = str(status_value) if status_value is not None else ""
                    defaults = {
                        "account_id": account_id,
                        "name": str(row.get("name") or "").strip(),
                        "currency": str(row.get("currency") or "").strip(),
                        "status": status_text,
                        "business_name": str(row.get("business_name") or "").strip(),
                        "metadata": row,
                        "updated_time": timezone.now(),
                    }
                    AdAccount.all_objects.update_or_create(
                        tenant=credential.tenant,
                        external_id=external_id,
                        defaults=defaults,
                    )
                    batch_count += 1
                accounts_synced += batch_count
                succeeded += 1
                _touch_meta_sync_state(
                    tenant=credential.tenant,
                    account_id=credential.account_id,
                    job_status="succeeded",
                    job_error="",
                    sync_completed_at=timezone.now(),
                )
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "accounts_synced": accounts_synced,
    }


def _sync_meta_hierarchy_core(*, task) -> dict[str, int]:
    credentials = _meta_credentials()
    if not credentials:
        return {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "campaigns_synced": 0,
            "adsets_synced": 0,
            "ads_synced": 0,
        }

    try:
        client = MetaGraphClient.from_settings()
    except MetaGraphConfigurationError as exc:
        logger.error("meta.sync.hierarchy.misconfigured", exc_info=exc)
        raise task.retry_with_backoff(exc=exc, base_delay=300, max_delay=900)

    processed = succeeded = failed = 0
    campaigns_synced = adsets_synced = ads_synced = 0
    correlation_id = getattr(getattr(task, "request", None), "id", "") or ""
    with client:
        for credential in credentials:
            processed += 1
            tenant_id = str(credential.tenant_id)
            with tenant_context(tenant_id):
                access_token = credential.decrypt_access_token()
                if not access_token:
                    failed += 1
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=credential.account_id,
                        job_status="failed",
                        job_error="Missing stored Meta access token.",
                        sync_completed_at=timezone.now(),
                    )
                    continue
                account_external_id = _normalize_meta_account_id(credential.account_id)
                ad_account = (
                    AdAccount.all_objects.filter(
                        tenant=credential.tenant,
                        external_id=account_external_id,
                    )
                    .order_by("-updated_at")
                    .first()
                )
                if ad_account is None:
                    ad_account = AdAccount.all_objects.create(
                        tenant=credential.tenant,
                        external_id=account_external_id,
                        account_id=account_external_id.replace("act_", ""),
                        name="",
                        currency="",
                    )
                try:
                    campaigns = client.list_campaigns(
                        account_id=account_external_id,
                        user_access_token=access_token,
                    )
                    adsets = client.list_adsets(
                        account_id=account_external_id,
                        user_access_token=access_token,
                    )
                    ads = client.list_ads(
                        account_id=account_external_id,
                        user_access_token=access_token,
                    )
                except MetaGraphClientError as exc:
                    failed += 1
                    _log_meta_api_error(
                        tenant=credential.tenant,
                        account_id=account_external_id,
                        endpoint=f"/{account_external_id}/{{campaigns,adsets,ads}}",
                        exc=exc,
                        correlation_id=correlation_id,
                    )
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=account_external_id,
                        job_status="failed",
                        job_error=str(exc),
                        sync_completed_at=timezone.now(),
                    )
                    continue

                with transaction.atomic():
                    for row in campaigns:
                        if not isinstance(row, dict):
                            continue
                        external_id = str(row.get("id") or "").strip()
                        if not external_id:
                            continue
                        Campaign.all_objects.update_or_create(
                            tenant=credential.tenant,
                            external_id=external_id,
                            defaults={
                                "ad_account": ad_account,
                                "name": str(row.get("name") or "").strip() or external_id,
                                "platform": "meta",
                                "account_external_id": account_external_id,
                                "status": str(row.get("effective_status") or row.get("status") or "").strip(),
                                "objective": str(row.get("objective") or "").strip(),
                                "currency": ad_account.currency,
                                "metadata": row,
                                "created_time": _coerce_graph_datetime(row.get("created_time")),
                                "updated_time": _coerce_graph_datetime(row.get("updated_time")),
                            },
                        )
                        campaigns_synced += 1

                    campaign_map = {
                        campaign.external_id: campaign
                        for campaign in Campaign.all_objects.filter(
                            tenant=credential.tenant,
                            account_external_id=account_external_id,
                        )
                    }
                    for row in adsets:
                        if not isinstance(row, dict):
                            continue
                        external_id = str(row.get("id") or "").strip()
                        campaign_id = str(row.get("campaign_id") or "").strip()
                        if not external_id or not campaign_id:
                            continue
                        campaign = campaign_map.get(campaign_id)
                        if campaign is None:
                            campaign = Campaign.all_objects.create(
                                tenant=credential.tenant,
                                ad_account=ad_account,
                                external_id=campaign_id,
                                name=campaign_id,
                                platform="meta",
                                account_external_id=account_external_id,
                            )
                            campaign_map[campaign.external_id] = campaign
                        AdSet.all_objects.update_or_create(
                            tenant=credential.tenant,
                            external_id=external_id,
                            defaults={
                                "campaign": campaign,
                                "name": str(row.get("name") or "").strip() or external_id,
                                "status": str(row.get("effective_status") or row.get("status") or "").strip(),
                                "bid_strategy": str(row.get("bid_strategy") or "").strip(),
                                "daily_budget": _decimal(row.get("daily_budget")),
                                "start_time": _coerce_graph_datetime(row.get("start_time")),
                                "end_time": _coerce_graph_datetime(row.get("end_time")),
                                "targeting": row.get("targeting") if isinstance(row.get("targeting"), dict) else {},
                            },
                        )
                        adsets_synced += 1

                    adset_map = {
                        adset.external_id: adset
                        for adset in AdSet.all_objects.filter(
                            tenant=credential.tenant,
                            campaign__account_external_id=account_external_id,
                        ).select_related("campaign")
                    }
                    for row in ads:
                        if not isinstance(row, dict):
                            continue
                        external_id = str(row.get("id") or "").strip()
                        adset_id = str(row.get("adset_id") or "").strip()
                        if not external_id or not adset_id:
                            continue
                        adset = adset_map.get(adset_id)
                        if adset is None:
                            continue
                        creative = row.get("creative") if isinstance(row.get("creative"), dict) else {}
                        Ad.all_objects.update_or_create(
                            tenant=credential.tenant,
                            external_id=external_id,
                            defaults={
                                "adset": adset,
                                "name": str(row.get("name") or "").strip() or external_id,
                                "status": str(row.get("effective_status") or row.get("status") or "").strip(),
                                "creative": creative,
                                "preview_url": str(creative.get("thumbnail_url") or "").strip(),
                            },
                        )
                        ads_synced += 1
                succeeded += 1
                _touch_meta_sync_state(
                    tenant=credential.tenant,
                    account_id=account_external_id,
                    job_status="succeeded",
                    job_error="",
                    sync_completed_at=timezone.now(),
                )
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "campaigns_synced": campaigns_synced,
        "adsets_synced": adsets_synced,
        "ads_synced": ads_synced,
    }


def _sync_meta_insights_core(
    *,
    task,
    level: str = DEFAULT_META_INSIGHTS_LEVEL,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, int]:
    credentials = _meta_credentials()
    if not credentials:
        return {"processed": 0, "succeeded": 0, "failed": 0, "insights_synced": 0}

    level_value = (level or DEFAULT_META_INSIGHTS_LEVEL).strip().lower()
    if level_value not in {"account", "campaign", "adset", "ad"}:
        level_value = DEFAULT_META_INSIGHTS_LEVEL

    today = timezone.localdate()
    default_until = today - timedelta(days=1)
    default_since = default_until - timedelta(days=int(getattr(settings, "META_INSIGHTS_LOOKBACK_DAYS", DEFAULT_META_INSIGHTS_LOOKBACK_DAYS)))
    since_date = _parse_iso_date(since) or default_since
    until_date = _parse_iso_date(until) or default_until
    if since_date > until_date:
        since_date, until_date = until_date, since_date

    try:
        client = MetaGraphClient.from_settings()
    except MetaGraphConfigurationError as exc:
        logger.error("meta.sync.insights.misconfigured", exc_info=exc)
        raise task.retry_with_backoff(exc=exc, base_delay=300, max_delay=900)

    processed = succeeded = failed = insights_synced = 0
    correlation_id = getattr(getattr(task, "request", None), "id", "") or ""
    with client:
        for credential in credentials:
            processed += 1
            tenant_id = str(credential.tenant_id)
            with tenant_context(tenant_id):
                access_token = credential.decrypt_access_token()
                if not access_token:
                    failed += 1
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=credential.account_id,
                        job_status="failed",
                        job_error="Missing stored Meta access token.",
                        window_start=since_date,
                        window_end=until_date,
                        sync_completed_at=timezone.now(),
                    )
                    continue
                account_external_id = _normalize_meta_account_id(credential.account_id)
                ad_account = (
                    AdAccount.all_objects.filter(
                        tenant=credential.tenant,
                        external_id=account_external_id,
                    )
                    .order_by("-updated_at")
                    .first()
                )
                if ad_account is None:
                    ad_account = AdAccount.all_objects.create(
                        tenant=credential.tenant,
                        external_id=account_external_id,
                        account_id=account_external_id.replace("act_", ""),
                    )
                try:
                    rows = client.list_insights(
                        account_id=account_external_id,
                        user_access_token=access_token,
                        level=level_value,
                        since=since_date.isoformat(),
                        until=until_date.isoformat(),
                    )
                except MetaGraphClientError as exc:
                    failed += 1
                    _log_meta_api_error(
                        tenant=credential.tenant,
                        account_id=account_external_id,
                        endpoint=f"/{account_external_id}/insights",
                        exc=exc,
                        correlation_id=correlation_id,
                    )
                    _touch_meta_sync_state(
                        tenant=credential.tenant,
                        account_id=account_external_id,
                        job_status="failed",
                        job_error=str(exc),
                        window_start=since_date,
                        window_end=until_date,
                        sync_completed_at=timezone.now(),
                    )
                    continue

                campaign_cache: dict[str, Campaign | None] = {}
                adset_cache: dict[str, AdSet | None] = {}
                ad_cache: dict[str, Ad | None] = {}
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    record_date = _parse_iso_date(str(row.get("date_start") or "")) or since_date
                    external_id = _insight_external_id(row=row, level=level_value, account_id=account_external_id)
                    if not external_id:
                        continue
                    campaign = _cached_campaign(campaign_cache, credential_tenant=credential.tenant, external_id=str(row.get("campaign_id") or ""))
                    adset = _cached_adset(adset_cache, credential_tenant=credential.tenant, external_id=str(row.get("adset_id") or ""))
                    ad = _cached_ad(ad_cache, credential_tenant=credential.tenant, external_id=str(row.get("ad_id") or ""))
                    actions = row.get("actions") if isinstance(row.get("actions"), list) else []
                    conversions = _insight_conversions(actions)
                    defaults = {
                        "ad_account": ad_account,
                        "date": record_date,
                        "level": level_value,
                        "source": "meta",
                        "campaign": campaign,
                        "adset": adset,
                        "ad": ad,
                        "impressions": _int_value(row.get("impressions")),
                        "reach": _int_value(row.get("reach")),
                        "clicks": _int_value(row.get("clicks")),
                        "spend": _decimal(row.get("spend")),
                        "cpc": _decimal(row.get("cpc")),
                        "cpm": _decimal(row.get("cpm")),
                        "currency": ad_account.currency,
                        "conversions": conversions,
                        "actions": actions,
                        "raw_payload": row,
                    }
                    RawPerformanceRecord.all_objects.update_or_create(
                        tenant=credential.tenant,
                        source="meta",
                        external_id=external_id,
                        level=level_value,
                        date=record_date,
                        defaults=defaults,
                    )
                    insights_synced += 1
                succeeded += 1
                _touch_meta_sync_state(
                    tenant=credential.tenant,
                    account_id=account_external_id,
                    job_status="succeeded",
                    job_error="",
                    window_start=since_date,
                    window_end=until_date,
                    sync_completed_at=timezone.now(),
                )
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "insights_synced": insights_synced,
    }


def _meta_credentials() -> list[PlatformCredential]:
    with tenant_context(None):
        return list(
            PlatformCredential.all_objects.filter(
                provider=PlatformCredential.META,
            ).select_related("tenant")
        )


def _normalize_meta_account_id(account_id: str) -> str:
    value = account_id.strip()
    if value.startswith("act_"):
        return value
    if value.isdigit():
        return f"act_{value}"
    return value


def _coerce_graph_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _int_value(value: object) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _parse_iso_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None


def _insight_external_id(*, row: dict[str, object], level: str, account_id: str) -> str:
    if level == "campaign":
        return str(row.get("campaign_id") or "").strip()
    if level == "adset":
        return str(row.get("adset_id") or "").strip()
    if level == "ad":
        return str(row.get("ad_id") or "").strip()
    return account_id


def _insight_conversions(actions: list[object]) -> int:
    total = 0
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("action_type") or "")
        if action_type not in {"offsite_conversion", "purchase"}:
            continue
        total += _int_value(action.get("value"))
    return total


def _cached_campaign(
    cache: dict[str, Campaign | None], *, credential_tenant, external_id: str
) -> Campaign | None:
    key = external_id.strip()
    if not key:
        return None
    if key not in cache:
        cache[key] = (
            Campaign.all_objects.filter(tenant=credential_tenant, external_id=key)
            .order_by("-updated_at")
            .first()
        )
    return cache[key]


def _cached_adset(
    cache: dict[str, AdSet | None], *, credential_tenant, external_id: str
) -> AdSet | None:
    key = external_id.strip()
    if not key:
        return None
    if key not in cache:
        cache[key] = (
            AdSet.all_objects.filter(tenant=credential_tenant, external_id=key)
            .order_by("-updated_at")
            .first()
        )
    return cache[key]


def _cached_ad(
    cache: dict[str, Ad | None], *, credential_tenant, external_id: str
) -> Ad | None:
    key = external_id.strip()
    if not key:
        return None
    if key not in cache:
        cache[key] = (
            Ad.all_objects.filter(tenant=credential_tenant, external_id=key)
            .order_by("-updated_at")
            .first()
        )
    return cache[key]


def _touch_meta_sync_state(
    *,
    tenant,
    account_id: str,
    job_status: str,
    job_error: str,
    sync_completed_at: datetime,
    window_start=None,
    window_end=None,
) -> None:
    normalized = _normalize_meta_account_id(account_id)
    state, _ = MetaAccountSyncState.all_objects.get_or_create(
        tenant=tenant,
        account_id=normalized,
    )
    state.last_job_status = job_status
    state.last_job_error = job_error
    state.last_sync_completed_at = sync_completed_at
    if window_start is not None:
        state.last_window_start = window_start
    if window_end is not None:
        state.last_window_end = window_end
    if job_status.lower() in {"succeeded", "success", "completed"}:
        state.last_success_at = sync_completed_at
    state.save()


def _log_meta_api_error(
    *,
    tenant,
    account_id: str,
    endpoint: str,
    exc: MetaGraphClientError,
    correlation_id: str,
) -> None:
    APIErrorLog.all_objects.create(
        tenant=tenant,
        provider=PlatformCredential.META,
        endpoint=endpoint,
        account_id=_normalize_meta_account_id(account_id),
        status_code=getattr(exc, "status_code", None),
        error_code=str(getattr(exc, "error_code", "") or ""),
        error_subcode=str(getattr(exc, "error_subcode", "") or ""),
        message=str(exc),
        payload=getattr(exc, "payload", {}) or {},
        correlation_id=correlation_id,
        is_retryable=bool(getattr(exc, "retryable", False)),
    )


def _mask_identifier(value: str | None) -> str:
    if not value:
        return "ref_unknown"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"ref_{digest}"


def _coerce_epoch_datetime(value: object) -> datetime | None:
    if not isinstance(value, (int, float)):
        return None
    if int(value) <= 0:
        return None
    return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)


def _token_status_for_expiry(
    *,
    expires_at: datetime | None,
    now: datetime,
) -> tuple[str, str]:
    if expires_at is None:
        return (PlatformCredential.TOKEN_STATUS_VALID, "")
    if expires_at <= now:
        return (
            PlatformCredential.TOKEN_STATUS_INVALID,
            "Token expiry timestamp is in the past.",
        )
    if expires_at <= now + timedelta(days=7):
        return (
            PlatformCredential.TOKEN_STATUS_EXPIRING,
            "Token expiry is within 7 days.",
        )
    return (PlatformCredential.TOKEN_STATUS_VALID, "")


def _mark_reauth_required(
    credential: PlatformCredential,
    *,
    now: datetime,
    reason: str,
    include_refresh_attempt: bool = False,
) -> None:
    credential.last_validated_at = now
    if include_refresh_attempt:
        credential.last_refresh_attempt_at = now
    credential.token_status = PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED
    credential.token_status_reason = reason
    update_fields = [
        "last_validated_at",
        "token_status",
        "token_status_reason",
        "updated_at",
    ]
    if include_refresh_attempt:
        update_fields.append("last_refresh_attempt_at")
    credential.save(update_fields=update_fields)


def _create_stale_meta_sync_state_alert(*, now: datetime) -> None:
    stale_hours = int(getattr(settings, "META_SYNC_STATE_STALE_HOURS", 6))
    stale_cutoff = now - timedelta(hours=stale_hours)

    with tenant_context(None):
        stale_states = list(
            MetaAccountSyncState.all_objects.filter(
                last_success_at__isnull=True
            )
            .select_related("tenant")
        )
        stale_states.extend(
            list(
                MetaAccountSyncState.all_objects.filter(
                    last_success_at__lt=stale_cutoff,
                ).select_related("tenant")
            )
        )

    if not stale_states:
        return

    deduped: dict[tuple[str, str], MetaAccountSyncState] = {}
    for state in stale_states:
        deduped[(str(state.tenant_id), state.account_id)] = state

    rows = [
        {
            "tenant_id": str(state.tenant_id),
            "account_ref": _mask_identifier(state.account_id),
            "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
            "updated_at": state.updated_at.isoformat(),
        }
        for state in deduped.values()
    ]
    AlertRun.objects.create(
        rule_slug="meta_sync_state_stale",
        status=AlertRun.Status.SUCCESS,
        row_count=len(rows),
        raw_results=rows,
        llm_summary=f"{len(rows)} Meta account sync-state record(s) are stale.",
        error_message="",
    )


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_page_insights(  # noqa: ANN001
    self,
    page_pk: str | None = None,
    mode: str = "incremental",
    metrics: list[str] | None = None,
):
    """Sync Meta Page Insights from Graph API into MetaInsightPoint."""

    if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
        return {"pages_processed": 0, "rows_processed": 0, "disabled": True}

    seed_default_metrics()
    now = timezone.now()
    task_id = getattr(getattr(self, "request", None), "id", "") or ""
    total_rows_processed = 0
    pages_processed = 0

    queryset = MetaPage.all_objects.filter(can_analyze=True).select_related("tenant")
    if page_pk:
        queryset = queryset.filter(pk=page_pk)
    pages = list(queryset)
    if not pages:
        return {"pages_processed": 0, "rows_processed": 0}

    with MetaInsightsGraphClient.from_settings() as client:
        for page in pages:
            tenant_id = str(page.tenant_id)
            with tenant_context(tenant_id):
                page_token = page.decrypt_page_token()
                if not page_token:
                    logger.warning("meta.page_insights.missing_token", extra={"tenant_id": tenant_id, "page_id": page.page_id})
                    continue

                registry_metrics = list(metrics or get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE))
                for metric in registry_metrics:
                    if is_blocked_metric(metric):
                        mark_metric_invalid(MetaMetricRegistry.LEVEL_PAGE, metric)
                registry_metrics = [metric for metric in registry_metrics if metric and not is_blocked_metric(metric)]
                if not registry_metrics:
                    continue

                since, until = _resolve_sync_window(mode=mode, now=now)
                chunk_size = max(int(getattr(settings, "META_PAGE_INSIGHTS_METRIC_CHUNK_SIZE", 10)), 1)

                for window_since, window_until in _window_chunks(since=since, until=until, max_days=90):
                    rows_processed = _sync_page_metric_window(
                        client=client,
                        page=page,
                        metrics=registry_metrics,
                        since=window_since,
                        until=window_until,
                        chunk_size=chunk_size,
                    )
                    total_rows_processed += rows_processed
                    emit_observability_event(
                        logger,
                        "meta.page_insights.synced",
                        tenant_id=tenant_id,
                        task_id=task_id,
                        correlation_id=task_id,
                        page_id=page.page_id,
                        rows_processed=rows_processed,
                        api_cost_units=None,
                    )
                page.last_synced_at = now
                page.save(update_fields=["last_synced_at", "updated_at"])
                pages_processed += 1

    return {
        "pages_processed": pages_processed,
        "rows_processed": total_rows_processed,
    }


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_post_insights(  # noqa: ANN001
    self,
    page_pk: str | None = None,
    mode: str = "incremental",
    metrics: list[str] | None = None,
):
    """Sync Meta Page Post Insights from Graph API into MetaPostInsightPoint."""

    if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
        return {"pages_processed": 0, "posts_processed": 0, "rows_processed": 0, "disabled": True}

    seed_default_metrics()
    now = timezone.now()
    task_id = getattr(getattr(self, "request", None), "id", "") or ""
    total_rows_processed = 0
    posts_processed = 0
    pages_processed = 0

    queryset = MetaPage.all_objects.filter(can_analyze=True).select_related("tenant")
    if page_pk:
        queryset = queryset.filter(pk=page_pk)
    pages = list(queryset)
    if not pages:
        return {"pages_processed": 0, "posts_processed": 0, "rows_processed": 0}

    with MetaInsightsGraphClient.from_settings() as client:
        for page in pages:
            tenant_id = str(page.tenant_id)
            with tenant_context(tenant_id):
                page_token = page.decrypt_page_token()
                if not page_token:
                    continue

                since, until = _resolve_sync_window(mode=mode, now=now)
                posts_payload = client.fetch_page_posts(
                    page_id=page.page_id,
                    since=since.isoformat(),
                    until=until.isoformat(),
                    token=page_token,
                )
                posts = _upsert_meta_posts(page=page, rows=posts_payload)
                if not posts:
                    continue

                registry_metrics = list(metrics or get_default_metric_keys(MetaMetricRegistry.LEVEL_POST))
                for metric in registry_metrics:
                    if is_blocked_metric(metric):
                        mark_metric_invalid(MetaMetricRegistry.LEVEL_POST, metric)
                registry_metrics = [metric for metric in registry_metrics if metric and not is_blocked_metric(metric)]
                if not registry_metrics:
                    continue

                chunk_size = max(int(getattr(settings, "META_PAGE_INSIGHTS_METRIC_CHUNK_SIZE", 10)), 1)
                for post in posts:
                    rows_processed = _sync_post_metric_window(
                        client=client,
                        post=post,
                        page_token=page_token,
                        metrics=registry_metrics,
                        since=since,
                        until=until,
                        chunk_size=chunk_size,
                    )
                    total_rows_processed += rows_processed
                    posts_processed += 1

                emit_observability_event(
                    logger,
                    "meta.post_insights.synced",
                    tenant_id=tenant_id,
                    task_id=task_id,
                    correlation_id=task_id,
                    page_id=page.page_id,
                    rows_processed=total_rows_processed,
                    api_cost_units=None,
                )
                page.last_posts_synced_at = now
                page.save(update_fields=["last_posts_synced_at", "updated_at"])
                pages_processed += 1

    return {
        "pages_processed": pages_processed,
        "posts_processed": posts_processed,
        "rows_processed": total_rows_processed,
    }


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_meta_pages(self, connection_id: str | None = None):  # noqa: ANN001
    """Sync ANALYZE-capable pages from Meta /me/accounts for a connection."""

    if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
        return {"connection_id": connection_id, "pages_synced": 0, "disabled": True}

    connection_ids: list[str]
    if connection_id:
        connection_ids = [connection_id]
    else:
        meta_connection_ids = list(
            MetaConnection.all_objects.filter(is_active=True).values_list("id", flat=True)
        )
        credential_ids = list(
            PlatformCredential.all_objects.filter(provider=PlatformCredential.META)
            .values_list("id", flat=True)
        )
        connection_ids = [str(value) for value in [*meta_connection_ids, *credential_ids] if value]

    total = 0
    for candidate in connection_ids:
        total += len(sync_pages_for_connection(candidate))
    return {"connection_id": connection_id, "pages_synced": total}


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def discover_supported_metrics(self, page_id: str | None = None):  # noqa: ANN001
    """Discover supported page/post metrics with binary-split fallback."""

    if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
        return {"page_id": page_id, "checked": 0, "disabled": True}

    seed_default_metrics()
    pages: list[MetaPage]
    if page_id:
        page = _resolve_page(page_id)
        pages = [page] if page is not None else []
    else:
        pages = list(MetaPage.all_objects.filter(can_analyze=True).select_related("tenant"))

    checked = 0
    supported = 0
    for page in pages:
        token = page.decrypt_page_token()
        if not token:
            continue
        page_metrics = get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE)
        page_support = validate_metrics(
            page=page,
            object_id=page.page_id,
            object_type="page",
            metrics=page_metrics,
            token=token,
            period="day",
        )
        checked += len(page_support)
        supported += sum(1 for value in page_support.values() if value)

        first_post = MetaPost.all_objects.filter(tenant=page.tenant, page=page).order_by("-created_time").first()
        if first_post is None:
            continue
        post_metrics = get_default_metric_keys(MetaMetricRegistry.LEVEL_POST)
        post_support = validate_metrics(
            page=page,
            object_id=first_post.post_id,
            object_type="post",
            metrics=post_metrics,
            token=token,
            period="lifetime",
        )
        checked += len(post_support)
        supported += sum(1 for value in post_support.values() if value)

    return {
        "page_id": page_id,
        "checked": checked,
        "supported": supported,
        "pages_processed": len(pages),
    }


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_page_insights(self, page_id: str | None = None, mode: str = "backfill"):  # noqa: ANN001
    """Compatibility task wrapper for syncing page insights by page_id."""

    if page_id:
        page = _resolve_page(page_id)
        if page is None:
            return {"page_id": page_id, "rows_processed": 0, "detail": "Page not found"}
        return sync_meta_page_insights.run(page_pk=str(page.pk), mode=mode)
    return sync_meta_page_insights.run(mode=mode)


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_page_posts(self, page_id: str | None = None, mode: str = "incremental"):  # noqa: ANN001
    """Sync recent posts for a page without post-level insight metrics."""

    if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
        return {"page_id": page_id, "posts_processed": 0, "disabled": True}

    pages: list[MetaPage]
    if page_id:
        page = _resolve_page(page_id)
        pages = [page] if page is not None else []
    else:
        pages = list(MetaPage.all_objects.filter(can_analyze=True).select_related("tenant"))

    now = timezone.now()
    if mode == "backfill":
        since, until = _resolve_sync_window(mode="backfill", now=now)
    else:
        until = now.date()
        lookback_days = max(int(getattr(settings, "META_PAGE_INSIGHTS_POST_RECENCY_DAYS", 28)), 1)
        since = until - timedelta(days=lookback_days)

    total_posts = 0
    with MetaInsightsGraphClient.from_settings() as client:
        for page in pages:
            token = page.decrypt_page_token()
            if not token:
                continue
            payload = client.fetch_page_posts(
                page_id=page.page_id,
                since=since.isoformat(),
                until=until.isoformat(),
                token=token,
            )
            posts = _upsert_meta_posts(page=page, rows=payload)
            total_posts += len(posts)
            page.last_posts_synced_at = now
            page.save(update_fields=["last_posts_synced_at", "updated_at"])
    return {"page_id": page_id, "posts_processed": total_posts, "pages_processed": len(pages)}


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def sync_post_insights(self, page_id: str | None = None, mode: str = "incremental"):  # noqa: ANN001
    """Compatibility task wrapper for syncing post insight metrics by page_id."""

    if page_id:
        page = _resolve_page(page_id)
        if page is None:
            return {"page_id": page_id, "rows_processed": 0, "detail": "Page not found"}
        return sync_meta_post_insights.run(page_pk=str(page.pk), mode=mode)
    return sync_meta_post_insights.run(mode=mode)


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=5)
def refresh_tokens(self):  # noqa: ANN001
    """Backward-compatible token refresh alias for insights workers."""

    return refresh_meta_tokens.run()


def _resolve_page(page_id: str) -> MetaPage | None:
    page = MetaPage.all_objects.filter(page_id=page_id).select_related("tenant").first()
    if page is not None:
        return page
    return MetaPage.all_objects.filter(pk=page_id).select_related("tenant").first()


def _sync_page_metric_window(
    *,
    client: MetaInsightsGraphClient,
    page: MetaPage,
    metrics: list[str],
    since: date,
    until: date,
    chunk_size: int,
) -> int:
    rows_processed = 0
    for chunk in _chunked(metrics, chunk_size):
        rows_processed += _sync_page_metric_chunk(
            client=client,
            page=page,
            metric_chunk=chunk,
            since=since,
            until=until,
        )
    return rows_processed


def _sync_page_metric_chunk(
    *,
    client: MetaInsightsGraphClient,
    page: MetaPage,
    metric_chunk: list[str],
    since: date,
    until: date,
) -> int:
    if not metric_chunk:
        return 0

    page_token = page.decrypt_page_token()
    if not page_token:
        return 0

    try:
        payload = client.fetch_page_insights(
            page_id=page.page_id,
            metrics=metric_chunk,
            period="day",
            since=since.isoformat(),
            until=until.isoformat(),
            token=page_token,
        )
    except MetaInsightsGraphClientError as exc:
        if exc.error_code == 100:
            if len(metric_chunk) == 1:
                mark_metric_invalid(MetaMetricRegistry.LEVEL_PAGE, metric_chunk[0])
                return 0
            midpoint = max(len(metric_chunk) // 2, 1)
            left = metric_chunk[:midpoint]
            right = metric_chunk[midpoint:]
            return _sync_page_metric_chunk(
                client=client,
                page=page,
                metric_chunk=left,
                since=since,
                until=until,
            ) + _sync_page_metric_chunk(
                client=client,
                page=page,
                metric_chunk=right,
                since=since,
                until=until,
            )
        if exc.error_code == 3001 and exc.error_subcode == 1504028:
            return 0
        if exc.retryable:
            raise
        logger.warning(
            "meta.page_insights.chunk_failed",
            extra={
                "tenant_id": str(page.tenant_id),
                "page_id": page.page_id,
                "metric_chunk": metric_chunk,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
            },
        )
        return 0

    points, metadata = normalize_insights_payload(payload)
    for meta in metadata:
        update_metric_metadata(
            level=MetaMetricRegistry.LEVEL_PAGE,
            metric_key=meta.metric_key,
            title=meta.title,
            description=meta.description,
            periods=[meta.period],
        )

    return _upsert_meta_insight_points(page=page, points=points)


def _sync_post_metric_window(
    *,
    client: MetaInsightsGraphClient,
    post: MetaPost,
    page_token: str,
    metrics: list[str],
    since: date,
    until: date,
    chunk_size: int,
) -> int:
    rows_processed = 0
    for chunk in _chunked(metrics, chunk_size):
        rows_processed += _sync_post_metric_chunk(
            client=client,
            post=post,
            page_token=page_token,
            metric_chunk=chunk,
            since=since,
            until=until,
        )
    return rows_processed


def _sync_post_metric_chunk(
    *,
    client: MetaInsightsGraphClient,
    post: MetaPost,
    page_token: str,
    metric_chunk: list[str],
    since: date,
    until: date,
) -> int:
    if not metric_chunk:
        return 0

    try:
        payload = client.fetch_post_insights(
            post_id=post.post_id,
            metrics=metric_chunk,
            period="lifetime",
            since=since.isoformat(),
            until=until.isoformat(),
            token=page_token,
        )
    except MetaInsightsGraphClientError as exc:
        if exc.error_code == 100:
            if len(metric_chunk) == 1:
                mark_metric_invalid(MetaMetricRegistry.LEVEL_POST, metric_chunk[0])
                return 0
            midpoint = max(len(metric_chunk) // 2, 1)
            left = metric_chunk[:midpoint]
            right = metric_chunk[midpoint:]
            return _sync_post_metric_chunk(
                client=client,
                post=post,
                page_token=page_token,
                metric_chunk=left,
                since=since,
                until=until,
            ) + _sync_post_metric_chunk(
                client=client,
                post=post,
                page_token=page_token,
                metric_chunk=right,
                since=since,
                until=until,
            )
        if exc.error_code == 3001 and exc.error_subcode == 1504028:
            return 0
        if exc.retryable:
            raise
        logger.warning(
            "meta.post_insights.chunk_failed",
            extra={
                "tenant_id": str(post.tenant_id),
                "post_id": post.post_id,
                "metric_chunk": metric_chunk,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
            },
        )
        return 0

    fallback_end_time = post.created_time or timezone.now()
    points, metadata = normalize_insights_payload(payload, fallback_end_time=fallback_end_time)
    for meta in metadata:
        update_metric_metadata(
            level=MetaMetricRegistry.LEVEL_POST,
            metric_key=meta.metric_key,
            title=meta.title,
            description=meta.description,
            periods=[meta.period],
        )

    return _upsert_meta_post_insight_points(post=post, points=points)


def _upsert_meta_insight_points(*, page: MetaPage, points) -> int:
    if not points:
        return 0
    tenant = page.tenant
    rows = [
        MetaInsightPoint(
            tenant=tenant,
            page=page,
            metric_key=point.metric_key,
            period=point.period,
            end_time=point.end_time,
            value_num=point.value_num,
            value_json=point.value_json,
            breakdown_key=point.breakdown_key,
            breakdown_key_normalized=normalize_breakdown_key(point.breakdown_key),
            breakdown_json=point.breakdown_json,
        )
        for point in points
    ]
    MetaInsightPoint.all_objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=[
            "tenant",
            "page",
            "metric_key",
            "period",
            "end_time",
            "breakdown_key_normalized",
        ],
        update_fields=[
            "value_num",
            "value_json",
            "breakdown_key",
            "breakdown_json",
            "updated_at",
        ],
    )
    return len(rows)


def _upsert_meta_post_insight_points(*, post: MetaPost, points) -> int:
    if not points:
        return 0
    tenant = post.tenant
    rows = [
        MetaPostInsightPoint(
            tenant=tenant,
            post=post,
            metric_key=point.metric_key,
            period=point.period,
            end_time=point.end_time,
            value_num=point.value_num,
            value_json=point.value_json,
            breakdown_key=point.breakdown_key,
            breakdown_key_normalized=normalize_breakdown_key(point.breakdown_key),
            breakdown_json=point.breakdown_json,
        )
        for point in points
    ]
    MetaPostInsightPoint.all_objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=[
            "tenant",
            "post",
            "metric_key",
            "period",
            "end_time",
            "breakdown_key_normalized",
        ],
        update_fields=[
            "value_num",
            "value_json",
            "breakdown_key",
            "breakdown_json",
            "updated_at",
        ],
    )
    return len(rows)


def _upsert_meta_posts(*, page: MetaPage, rows: list[dict[str, Any]]) -> list[MetaPost]:
    posts: list[MetaPost] = []
    for row in rows:
        post_id = str(row.get("id") or "").strip()
        if not post_id:
            continue
        defaults = {
            "media_type": _extract_media_type(row),
            "message": str(row.get("message") or ""),
            "permalink_url": str(row.get("permalink_url") or ""),
            "created_time": _coerce_graph_datetime(row.get("created_time")),
            "updated_time": _coerce_graph_datetime(row.get("updated_time")),
            "last_synced_at": timezone.now(),
            "metadata": row,
        }
        post, _ = MetaPost.all_objects.update_or_create(
            tenant=page.tenant,
            page=page,
            post_id=post_id,
            defaults=defaults,
        )
        posts.append(post)
    return posts


def _resolve_sync_window(*, mode: str, now: datetime) -> tuple[date, date]:
    end_date = now.date()
    if mode == "backfill":
        backfill_days = max(int(getattr(settings, "META_PAGE_INSIGHTS_BACKFILL_DAYS", 90)), 1)
        return end_date - timedelta(days=backfill_days), end_date
    incremental_days = max(int(getattr(settings, "META_PAGE_INSIGHTS_INCREMENTAL_LOOKBACK_DAYS", 3)), 1)
    return end_date - timedelta(days=incremental_days), end_date


def _window_chunks(*, since: date, until: date, max_days: int) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    cursor = since
    while cursor <= until:
        chunk_end = min(cursor + timedelta(days=max_days - 1), until)
        windows.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return windows


def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]
    return [values[index : index + size] for index in range(0, len(values), size)]


def _extract_media_type(row: dict[str, Any]) -> str:
    direct = row.get("media_type")
    if isinstance(direct, str) and direct.strip():
        return direct.strip().upper()

    attachments = row.get("attachments")
    if isinstance(attachments, dict):
        data = attachments.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                media_type = first.get("media_type") or first.get("type")
                if isinstance(media_type, str) and media_type.strip():
                    return media_type.strip().upper()
    return ""
