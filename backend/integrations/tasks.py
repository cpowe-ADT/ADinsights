"""Celery tasks for integrations."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import List

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
from integrations.models import (
    APIErrorLog,
    AirbyteConnection,
    MetaAccountSyncState,
    PlatformCredential,
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
