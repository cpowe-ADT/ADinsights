"""Publishing preflight checks for Content Operations.

Preflight helpers do not call Meta or decrypt provider tokens. Processing remains
fail-closed by default and calls a live provider only when an explicit adapter is
injected or the disabled-by-default live Facebook Page flag is enabled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .assets import public_media_fetch_url, validate_media_assets_for_publish
from .models import (
    ContentDraft,
    ContentSchedule,
    PublishedPost,
    PublishAttempt,
    PublishingIdentity,
)
from .readiness import build_content_ops_readiness_payload

PREFLIGHT_ATTEMPT_MISSING = "attempt_missing"
PREFLIGHT_ATTEMPT_WRONG_TENANT = "attempt_wrong_tenant"
PREFLIGHT_UNSUPPORTED_CHANNEL = "unsupported_channel"
PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE = "attempt_state_not_publishable"
PREFLIGHT_SCHEDULE_MISSING = "schedule_missing"
PREFLIGHT_DRAFT_MISSING = "draft_missing"
PREFLIGHT_VERSION_MISSING = "version_missing"
PREFLIGHT_SCHEDULE_VERSION_STALE = "schedule_version_stale"
PREFLIGHT_APPROVAL_SNAPSHOT_MISSING = "approval_snapshot_missing"
PREFLIGHT_CLIENT_APPROVAL_MISSING = "client_approval_missing"
PREFLIGHT_PUBLISHING_IDENTITY_MISSING = "publishing_identity_missing"
PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT = "publishing_identity_wrong_tenant"
PREFLIGHT_PUBLISHING_IDENTITY_NOT_SELECTED = "publishing_identity_not_selected"
PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY = "publishing_identity_not_ready"
PREFLIGHT_FACEBOOK_PAGE_PUBLISHING_NOT_READY = "facebook_page_publishing_not_ready"
PREFLIGHT_INSTAGRAM_PUBLISHING_NOT_READY = "instagram_publishing_not_ready"
PREFLIGHT_CONTENT_MISSING = "content_missing"
PREFLIGHT_INSTAGRAM_MEDIA_REQUIRED = "instagram_media_required"
PREFLIGHT_INSTAGRAM_CAPTION_TOO_LONG = "instagram_caption_too_long"
PROVIDER_NOT_CONFIGURED = "provider_not_configured"
PROVIDER_RETRYABLE_ERROR = "provider_retryable_error"
PROVIDER_TERMINAL_ERROR = "provider_terminal_error"
PROVIDER_MAX_ATTEMPTS_EXCEEDED = "provider_max_attempts_exceeded"
PROVIDER_CONTAINER_EXPIRED = "instagram_container_expired"
PROVIDER_CONTAINER_ERROR = "instagram_container_error"
PROVIDER_CONTAINER_NOT_READY = "instagram_container_not_ready"

PROCESS_STATUS_BLOCKED = "blocked"
PROCESS_STATUS_FAILED = "failed"
PROCESS_STATUS_NOOP = "noop"
PROCESS_STATUS_PUBLISHED = "published"
PROCESS_STATUS_QUEUED = "queued"

PUBLISHABLE_ATTEMPT_STATES = {
    PublishAttempt.STATE_QUEUED,
    PublishAttempt.STATE_FAILED_RETRYABLE,
}
INSTAGRAM_PROCESSABLE_STATES = {
    PublishAttempt.STATE_QUEUED,
    PublishAttempt.STATE_FAILED_RETRYABLE,
    PublishAttempt.STATE_CONTAINER_PENDING,
    PublishAttempt.STATE_CONTAINER_READY,
}
TERMINAL_OR_BLOCKED_ATTEMPT_STATES = {
    PublishAttempt.STATE_BLOCKED,
    PublishAttempt.STATE_CANCELLED,
    PublishAttempt.STATE_CONTAINER_EXPIRED,
    PublishAttempt.STATE_FAILED_TERMINAL,
    PublishAttempt.STATE_PUBLISHED,
}
FORBIDDEN_FAILURE_DETAIL_FRAGMENTS = {
    "access_token",
    "authorization",
    "bearer",
    "meta-access-token",
    "page-token",
    "raw_response",
    "refresh_token",
    "secret",
}
MAX_PUBLISH_ATTEMPTS = 5
RETRY_BASE_DELAY = timedelta(minutes=5)
RETRY_MAX_DELAY = timedelta(hours=1)
RETRY_JITTER_MAX_SECONDS = 60
INSTAGRAM_CAPTION_MAX_LENGTH = 2200
INSTAGRAM_CONTAINER_TTL = timedelta(hours=23)
INSTAGRAM_STATUS_FINISHED = "FINISHED"
INSTAGRAM_STATUS_IN_PROGRESS = "IN_PROGRESS"
INSTAGRAM_STATUS_ERROR = "ERROR"
INSTAGRAM_STATUS_EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class PublishPreflightResult:
    ready: bool
    failure_code: str = ""
    failure_detail_safe: str = ""
    channel: str = ""
    attempt_id: str = ""
    schedule_id: str = ""
    draft_id: str = ""
    version_id: str = ""
    publishing_identity_id: str | None = None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "ready": self.ready,
            "failure_code": self.failure_code,
            "failure_detail_safe": self.failure_detail_safe,
            "channel": self.channel,
            "attempt_id": self.attempt_id,
            "schedule_id": self.schedule_id,
            "draft_id": self.draft_id,
            "version_id": self.version_id,
            "publishing_identity_id": self.publishing_identity_id,
        }


@dataclass(frozen=True)
class FacebookPagePublishPayload:
    tenant_id: str
    attempt_id: str
    draft_id: str
    version_id: str
    publishing_identity_id: str
    meta_page_id: str
    caption: str


@dataclass(frozen=True)
class FacebookPagePublishResult:
    meta_post_id: str
    permalink: str = ""


@dataclass(frozen=True)
class InstagramMediaContainerPayload:
    tenant_id: str
    attempt_id: str
    draft_id: str
    version_id: str
    publishing_identity_id: str
    meta_page_id: str
    ig_user_id: str
    media_url: str
    caption: str
    media_type: str


@dataclass(frozen=True)
class InstagramMediaContainerResult:
    container_id: str


@dataclass(frozen=True)
class InstagramMediaContainerStatusResult:
    status_code: str
    status: str = ""


@dataclass(frozen=True)
class InstagramMediaPublishResult:
    meta_media_id: str
    permalink: str = ""


@dataclass(frozen=True)
class PublishAttemptProcessResult:
    status: str
    attempt_id: str = ""
    state: str = ""
    failure_code: str = ""
    failure_detail_safe: str = ""
    published_post_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "attempt_id": self.attempt_id,
            "state": self.state,
            "failure_code": self.failure_code,
            "failure_detail_safe": self.failure_detail_safe,
            "published_post_id": self.published_post_id,
        }


@dataclass(frozen=True)
class RetryRequeueResult:
    scanned: int = 0
    requeued: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "requeued": self.requeued,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class PublishQueueProcessResult:
    scanned: int = 0
    processed: int = 0
    published: int = 0
    blocked: int = 0
    failed: int = 0
    skipped: int = 0
    requeued: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "processed": self.processed,
            "published": self.published,
            "blocked": self.blocked,
            "failed": self.failed,
            "skipped": self.skipped,
            "requeued": self.requeued,
        }


class FacebookPagePublishError(RuntimeError):
    """Client-safe provider error for a future Facebook Page adapter."""

    def __init__(
        self,
        *,
        code: str,
        detail_safe: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.detail_safe = detail_safe
        self.retryable = retryable


class InstagramPublishError(RuntimeError):
    """Client-safe provider error for a future Instagram Graph adapter."""

    def __init__(
        self,
        *,
        code: str,
        detail_safe: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.detail_safe = detail_safe
        self.retryable = retryable


class DisabledFacebookPagePublisher:
    """Default publisher boundary that prevents accidental live Graph calls."""

    def publish(
        self, payload: FacebookPagePublishPayload  # noqa: ARG002
    ) -> FacebookPagePublishResult:
        raise FacebookPagePublishError(
            code=PROVIDER_NOT_CONFIGURED,
            detail_safe="Facebook Page publisher is not configured.",
            retryable=False,
        )


class DisabledInstagramPublisher:
    """Default Instagram boundary that prevents accidental live Graph calls."""

    def create_media_container(
        self, payload: InstagramMediaContainerPayload  # noqa: ARG002
    ) -> InstagramMediaContainerResult:
        raise InstagramPublishError(
            code=PROVIDER_NOT_CONFIGURED,
            detail_safe="Instagram publisher is not configured.",
            retryable=False,
        )

    def get_media_container_status(
        self,
        *,
        tenant_id: str = "",  # noqa: ARG002
        publishing_identity_id: str = "",  # noqa: ARG002
        meta_page_id: str = "",  # noqa: ARG002
        ig_user_id: str,  # noqa: ARG002
        container_id: str,  # noqa: ARG002
    ) -> InstagramMediaContainerStatusResult:
        raise InstagramPublishError(
            code=PROVIDER_NOT_CONFIGURED,
            detail_safe="Instagram publisher is not configured.",
            retryable=False,
        )

    def publish_media_container(
        self,
        *,
        tenant_id: str = "",  # noqa: ARG002
        publishing_identity_id: str = "",  # noqa: ARG002
        meta_page_id: str = "",  # noqa: ARG002
        ig_user_id: str,  # noqa: ARG002
        container_id: str,  # noqa: ARG002
    ) -> InstagramMediaPublishResult:
        raise InstagramPublishError(
            code=PROVIDER_NOT_CONFIGURED,
            detail_safe="Instagram publisher is not configured.",
            retryable=False,
        )


def process_facebook_page_publish_attempt(
    *,
    tenant,
    attempt_id: str | UUID,
    publisher=None,
    readiness: dict[str, Any] | None = None,
    now=None,
) -> PublishAttemptProcessResult:
    """Process one Facebook Page attempt using an injected publisher boundary."""

    now = now or timezone.now()
    existing_attempt = _get_attempt(attempt_id=attempt_id)
    if existing_attempt is not None and existing_attempt.state == PublishAttempt.STATE_PUBLISHED:
        if existing_attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_WRONG_TENANT,
                failure_detail_safe="Publish attempt does not belong to this tenant.",
            )
        published_post = PublishedPost.all_objects.filter(
            tenant=tenant,
            channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
            meta_post_id=existing_attempt.meta_post_id,
        ).first()
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_NOOP,
            attempt_id=str(existing_attempt.id),
            state=existing_attempt.state,
            published_post_id=str(published_post.id) if published_post else "",
        )
    preflight = preflight_facebook_page_attempt(
        tenant=tenant,
        attempt_id=attempt_id,
        readiness=readiness,
    )
    if not preflight.ready:
        if preflight.failure_code in {
            PREFLIGHT_ATTEMPT_MISSING,
            PREFLIGHT_ATTEMPT_WRONG_TENANT,
        }:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=preflight.attempt_id,
                failure_code=preflight.failure_code,
                failure_detail_safe=preflight.failure_detail_safe,
            )
        return _mark_attempt_blocked(preflight)

    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        if attempt.state == PublishAttempt.STATE_PUBLISHED:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=str(attempt.id),
                state=attempt.state,
            )
        if attempt.state not in PUBLISHABLE_ATTEMPT_STATES:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=str(attempt.id),
                state=attempt.state,
                failure_code=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
                failure_detail_safe="Publish attempt is not in a publishable state.",
            )
        attempt.state = PublishAttempt.STATE_PUBLISHING
        attempt.started_at = now
        attempt.failure_code = ""
        attempt.failure_detail_safe = ""
        attempt.save(
            update_fields=[
                "state",
                "started_at",
                "failure_code",
                "failure_detail_safe",
                "updated_at",
            ]
        )
        payload = _facebook_payload(attempt)

    selected_publisher = publisher or _default_facebook_page_publisher()
    try:
        provider_result = selected_publisher.publish(payload)
    except FacebookPagePublishError as exc:
        return _mark_provider_failure(
            tenant=tenant,
            attempt_id=attempt_id,
            error=exc,
            now=now,
        )

    return _mark_attempt_published(
        tenant=tenant,
        attempt_id=attempt_id,
        provider_result=provider_result,
        now=now,
    )


def process_instagram_publish_attempt(
    *,
    tenant,
    attempt_id: str | UUID,
    publisher=None,
    readiness: dict[str, Any] | None = None,
    now=None,
) -> PublishAttemptProcessResult:
    """Process one Instagram attempt through container create/poll/publish states."""

    now = now or timezone.now()
    existing_attempt = _get_attempt(attempt_id=attempt_id)
    if existing_attempt is not None and existing_attempt.state == PublishAttempt.STATE_PUBLISHED:
        if existing_attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_WRONG_TENANT,
                failure_detail_safe="Publish attempt does not belong to this tenant.",
            )
        published_post = PublishedPost.all_objects.filter(
            tenant=tenant,
            channel=PublishedPost.CHANNEL_INSTAGRAM,
            meta_post_id=existing_attempt.meta_post_id,
        ).first()
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_NOOP,
            attempt_id=str(existing_attempt.id),
            state=existing_attempt.state,
            published_post_id=str(published_post.id) if published_post else "",
        )

    preflight = preflight_instagram_attempt(
        tenant=tenant,
        attempt_id=attempt_id,
        readiness=readiness,
    )
    if not preflight.ready:
        if preflight.failure_code in {
            PREFLIGHT_ATTEMPT_MISSING,
            PREFLIGHT_ATTEMPT_WRONG_TENANT,
        }:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=preflight.attempt_id,
                failure_code=preflight.failure_code,
                failure_detail_safe=preflight.failure_detail_safe,
            )
        return _mark_attempt_blocked(preflight)

    selected_publisher = publisher or _default_instagram_publisher()
    prepared = _prepare_instagram_attempt_for_container(
        tenant=tenant,
        attempt_id=attempt_id,
        now=now,
    )
    if isinstance(prepared, PublishAttemptProcessResult):
        return prepared
    if prepared is not None:
        try:
            container_result = selected_publisher.create_media_container(prepared)
        except InstagramPublishError as exc:
            return _mark_provider_failure(
                tenant=tenant,
                attempt_id=attempt_id,
                error=exc,
                now=now,
            )
        _mark_instagram_container_pending(
            tenant=tenant,
            attempt_id=attempt_id,
            container_id=container_result.container_id,
            now=now,
        )

    attempt = _get_attempt(attempt_id=attempt_id)
    if attempt is None or attempt.tenant_id != tenant.id:
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_NOOP,
            failure_code=PREFLIGHT_ATTEMPT_MISSING,
            failure_detail_safe="Publish attempt does not exist.",
        )
    if _instagram_container_is_expired(attempt, now=now):
        return _mark_instagram_container_expired(
            tenant=tenant,
            attempt_id=attempt_id,
            now=now,
        )
    identity = attempt.publishing_identity
    if attempt.state == PublishAttempt.STATE_CONTAINER_PENDING:
        try:
            status_result = selected_publisher.get_media_container_status(
                tenant_id=str(tenant.id),
                publishing_identity_id=str(identity.id) if identity else "",
                meta_page_id=identity.meta_page_id if identity else "",
                ig_user_id=identity.ig_user_id if identity else "",
                container_id=attempt.meta_container_id,
            )
        except InstagramPublishError as exc:
            return _mark_provider_failure(
                tenant=tenant,
                attempt_id=attempt_id,
                error=exc,
                now=now,
            )
        normalized_status = _normalize_instagram_container_status(
            status_result.status_code
        )
        if normalized_status == INSTAGRAM_STATUS_IN_PROGRESS:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_QUEUED,
                attempt_id=str(attempt.id),
                state=PublishAttempt.STATE_CONTAINER_PENDING,
            )
        if normalized_status == INSTAGRAM_STATUS_EXPIRED:
            return _mark_instagram_container_expired(
                tenant=tenant,
                attempt_id=attempt_id,
                now=now,
            )
        if normalized_status == INSTAGRAM_STATUS_ERROR:
            return _mark_provider_failure(
                tenant=tenant,
                attempt_id=attempt_id,
                error=InstagramPublishError(
                    code=PROVIDER_CONTAINER_ERROR,
                    detail_safe="Instagram media container failed processing.",
                    retryable=True,
                ),
                now=now,
            )
        _mark_instagram_container_ready(tenant=tenant, attempt_id=attempt_id)

    attempt = _get_attempt(attempt_id=attempt_id)
    if attempt is None or attempt.tenant_id != tenant.id:
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_NOOP,
            failure_code=PREFLIGHT_ATTEMPT_MISSING,
            failure_detail_safe="Publish attempt does not exist.",
        )
    if attempt.state != PublishAttempt.STATE_CONTAINER_READY:
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_QUEUED,
            attempt_id=str(attempt.id),
            state=attempt.state,
            failure_code=PROVIDER_CONTAINER_NOT_READY,
            failure_detail_safe="Instagram media container is not ready.",
        )
    identity = attempt.publishing_identity
    try:
        publish_result = selected_publisher.publish_media_container(
            tenant_id=str(tenant.id),
            publishing_identity_id=str(identity.id) if identity else "",
            meta_page_id=identity.meta_page_id if identity else "",
            ig_user_id=identity.ig_user_id if identity else "",
            container_id=attempt.meta_container_id,
        )
    except InstagramPublishError as exc:
        return _mark_provider_failure(
            tenant=tenant,
            attempt_id=attempt_id,
            error=exc,
            now=now,
        )

    return _mark_attempt_published(
        tenant=tenant,
        attempt_id=attempt_id,
        provider_result=publish_result,
        now=now,
    )


def requeue_failed_publish_attempt(*, tenant, attempt_id: str | UUID) -> PublishAttempt:
    """Move a retryable failed attempt back to queued without provider side effects."""

    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            raise ValueError(PREFLIGHT_ATTEMPT_MISSING)
        if attempt.state != PublishAttempt.STATE_FAILED_RETRYABLE:
            raise ValueError(PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE)
        attempt.state = PublishAttempt.STATE_QUEUED
        attempt.failure_code = ""
        attempt.failure_detail_safe = ""
        attempt.next_retry_at = None
        attempt.started_at = None
        attempt.finished_at = None
        attempt.save(
            update_fields=[
                "state",
                "failure_code",
                "failure_detail_safe",
                "next_retry_at",
                "started_at",
                "finished_at",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)
        return attempt


def requeue_due_retryable_attempts(*, tenant, now=None, limit: int = 100) -> RetryRequeueResult:
    """Requeue retryable attempts whose retry time has arrived."""

    now = now or timezone.now()
    attempt_ids = list(
        PublishAttempt.all_objects.filter(
            tenant=tenant,
            state=PublishAttempt.STATE_FAILED_RETRYABLE,
            next_retry_at__isnull=False,
            next_retry_at__lte=now,
        )
        .order_by("next_retry_at", "created_at")
        .values_list("id", flat=True)[:limit]
    )
    requeued = 0
    skipped = 0
    for attempt_id in attempt_ids:
        try:
            requeue_failed_publish_attempt(tenant=tenant, attempt_id=attempt_id)
        except ValueError:
            skipped += 1
        else:
            requeued += 1
    return RetryRequeueResult(
        scanned=len(attempt_ids),
        requeued=requeued,
        skipped=skipped,
    )


def process_due_publish_attempts(
    *,
    tenant,
    now=None,
    limit: int = 100,
    publisher=None,
    instagram_publisher=None,
    readiness: dict[str, Any] | None = None,
    requeue_retryable: bool = True,
) -> PublishQueueProcessResult:
    """Process due queued publish attempts through the supported provider boundary."""

    now = now or timezone.now()
    retry_result = (
        requeue_due_retryable_attempts(tenant=tenant, now=now, limit=limit)
        if requeue_retryable
        else RetryRequeueResult()
    )
    instagram_container_states = {
        PublishAttempt.STATE_CONTAINER_PENDING,
        PublishAttempt.STATE_CONTAINER_READY,
    }
    processable_state_filter = Q(state=PublishAttempt.STATE_QUEUED) | Q(
        channel=PublishAttempt.CHANNEL_INSTAGRAM,
        state__in=instagram_container_states,
    )
    attempt_ids = list(
        PublishAttempt.all_objects.filter(
            processable_state_filter,
            tenant=tenant,
            schedule__scheduled_at__lte=now,
        )
        .order_by("schedule__scheduled_at", "created_at")
        .values_list("id", flat=True)[:limit]
    )

    counters = PublishQueueProcessResult(
        scanned=len(attempt_ids),
        requeued=retry_result.requeued,
        skipped=retry_result.skipped,
    )
    for attempt_id in attempt_ids:
        attempt = _get_attempt(attempt_id=attempt_id)
        if attempt is not None and attempt.channel == PublishAttempt.CHANNEL_INSTAGRAM:
            result = process_instagram_publish_attempt(
                tenant=tenant,
                attempt_id=attempt_id,
                publisher=instagram_publisher,
                readiness=readiness,
                now=now,
            )
        else:
            result = process_facebook_page_publish_attempt(
                tenant=tenant,
                attempt_id=attempt_id,
                publisher=publisher,
                readiness=readiness,
                now=now,
            )
        counters = PublishQueueProcessResult(
            scanned=counters.scanned,
            processed=counters.processed
            + (0 if result.status == PROCESS_STATUS_NOOP else 1),
            published=counters.published
            + (1 if result.status == PROCESS_STATUS_PUBLISHED else 0),
            blocked=counters.blocked
            + (1 if result.status == PROCESS_STATUS_BLOCKED else 0),
            failed=counters.failed
            + (1 if result.status == PROCESS_STATUS_FAILED else 0),
            skipped=counters.skipped
            + (1 if result.status == PROCESS_STATUS_NOOP else 0),
            requeued=counters.requeued,
        )
    return counters


def preflight_facebook_page_attempt(
    *,
    tenant,
    attempt_id: str | UUID,
    readiness: dict[str, Any] | None = None,
) -> PublishPreflightResult:
    """Validate a Facebook Page publish attempt without provider side effects."""

    attempt = _get_attempt(attempt_id=attempt_id)
    if attempt is None:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_MISSING,
            detail="Publish attempt does not exist.",
        )
    context = _context(attempt)
    if attempt.tenant_id != tenant.id:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_WRONG_TENANT,
            detail="Publish attempt does not belong to this tenant.",
            **context,
        )
    if attempt.channel != PublishAttempt.CHANNEL_FACEBOOK_PAGE:
        return _blocked(
            code=PREFLIGHT_UNSUPPORTED_CHANNEL,
            detail="Only Facebook Page attempts can use Facebook Page preflight.",
            **context,
        )
    if attempt.state not in PUBLISHABLE_ATTEMPT_STATES:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
            detail="Publish attempt is not in a publishable state.",
            **context,
        )
    if attempt.schedule_id is None or attempt.schedule.tenant_id != tenant.id:
        return _blocked(
            code=PREFLIGHT_SCHEDULE_MISSING,
            detail="Publish schedule is missing or unavailable for this tenant.",
            **context,
        )
    if attempt.draft_id is None or attempt.draft.tenant_id != tenant.id:
        return _blocked(
            code=PREFLIGHT_DRAFT_MISSING,
            detail="Content draft is missing or unavailable for this tenant.",
            **context,
        )
    if attempt.version_id is None or attempt.version.tenant_id != tenant.id:
        return _blocked(
            code=PREFLIGHT_VERSION_MISSING,
            detail="Content version is missing or unavailable for this tenant.",
            **context,
        )
    if attempt.draft.state not in {
        ContentDraft.STATE_SCHEDULED,
        ContentDraft.STATE_PUBLISHING,
    }:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
            detail="Content draft is not in a publishable state.",
            **context,
        )
    if attempt.draft.active_version_id != attempt.version_id:
        return _blocked(
            code=PREFLIGHT_SCHEDULE_VERSION_STALE,
            detail="Scheduled version is no longer the active draft version.",
            **context,
        )
    if attempt.schedule.version_id != attempt.version_id:
        return _blocked(
            code=PREFLIGHT_SCHEDULE_VERSION_STALE,
            detail="Publish attempt version does not match the schedule version.",
            **context,
        )

    snapshot_result = _validate_approval_snapshot(attempt)
    if snapshot_result is not None:
        return _blocked(**snapshot_result, **context)

    identity_result = _validate_identity(attempt, tenant=tenant)
    if identity_result is not None:
        return _blocked(**identity_result, **context)

    resolved_readiness = readiness or build_content_ops_readiness_payload(tenant=tenant)
    axis = resolved_readiness.get("facebook_page_publishing")
    if not isinstance(axis, dict) or axis.get("state") != "ready":
        return _blocked(
            code=PREFLIGHT_FACEBOOK_PAGE_PUBLISHING_NOT_READY,
            detail="Facebook Page publishing readiness is not ready.",
            **context,
        )
    if not str(attempt.version.caption or "").strip():
        return _blocked(
            code=PREFLIGHT_CONTENT_MISSING,
            detail="Facebook Page publish attempt requires approved caption text.",
            **context,
        )
    media_result = validate_media_assets_for_publish(attempt.version.media_assets.all())
    if not media_result.ready:
        return _blocked(
            code=media_result.failure_code,
            detail=media_result.failure_detail_safe,
            **context,
        )
    return PublishPreflightResult(ready=True, **context)


def preflight_instagram_attempt(
    *,
    tenant,
    attempt_id: str | UUID,
    readiness: dict[str, Any] | None = None,
) -> PublishPreflightResult:
    """Validate an Instagram publish attempt without provider side effects."""

    attempt = _get_attempt(attempt_id=attempt_id)
    if attempt is None:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_MISSING,
            detail="Publish attempt does not exist.",
        )
    context = _context(attempt)
    if attempt.tenant_id != tenant.id:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_WRONG_TENANT,
            detail="Publish attempt does not belong to this tenant.",
            **context,
        )
    if attempt.channel != PublishAttempt.CHANNEL_INSTAGRAM:
        return _blocked(
            code=PREFLIGHT_UNSUPPORTED_CHANNEL,
            detail="Only Instagram attempts can use Instagram preflight.",
            **context,
        )
    if attempt.state not in INSTAGRAM_PROCESSABLE_STATES:
        return _blocked(
            code=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
            detail="Publish attempt is not in an Instagram publishable state.",
            **context,
        )
    common_result = _validate_attempt_common(attempt=attempt, tenant=tenant)
    if common_result is not None:
        return _blocked(**common_result, **context)

    identity_result = _validate_instagram_identity(attempt, tenant=tenant)
    if identity_result is not None:
        return _blocked(**identity_result, **context)

    resolved_readiness = readiness or build_content_ops_readiness_payload(tenant=tenant)
    axis = resolved_readiness.get("instagram_publishing")
    if not isinstance(axis, dict) or axis.get("state") != "ready":
        return _blocked(
            code=PREFLIGHT_INSTAGRAM_PUBLISHING_NOT_READY,
            detail="Instagram publishing readiness is not ready.",
            **context,
        )
    caption = str(attempt.version.caption or "").strip()
    if len(caption) > INSTAGRAM_CAPTION_MAX_LENGTH:
        return _blocked(
            code=PREFLIGHT_INSTAGRAM_CAPTION_TOO_LONG,
            detail="Instagram caption exceeds the supported length.",
            **context,
        )
    media_assets = list(attempt.version.media_assets.all())
    if len(media_assets) != 1:
        return _blocked(
            code=PREFLIGHT_INSTAGRAM_MEDIA_REQUIRED,
            detail="Instagram publishing requires exactly one attached media asset.",
            **context,
        )
    media_result = validate_media_assets_for_publish(media_assets)
    if not media_result.ready:
        return _blocked(
            code=media_result.failure_code,
            detail=media_result.failure_detail_safe,
            **context,
        )
    return PublishPreflightResult(ready=True, **context)


def _locked_attempt(*, attempt_id: str | UUID) -> PublishAttempt | None:
    return (
        PublishAttempt.all_objects.select_for_update(skip_locked=True)
        .select_related(
            "schedule",
            "draft",
            "draft__workspace",
            "version",
            "publishing_identity",
        )
        .filter(id=attempt_id)
        .first()
    )


def _mark_attempt_blocked(
    preflight: PublishPreflightResult,
) -> PublishAttemptProcessResult:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=preflight.attempt_id)
        if attempt is None:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        attempt.state = PublishAttempt.STATE_BLOCKED
        attempt.failure_code = preflight.failure_code
        attempt.failure_detail_safe = _sanitize_failure_detail(
            preflight.failure_detail_safe
        )
        attempt.save(
            update_fields=[
                "state",
                "failure_code",
                "failure_detail_safe",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_BLOCKED,
            attempt_id=str(attempt.id),
            state=attempt.state,
            failure_code=attempt.failure_code,
            failure_detail_safe=attempt.failure_detail_safe,
        )


def _mark_provider_failure(
    *,
    tenant,
    attempt_id: str | UUID,
    error: FacebookPagePublishError | InstagramPublishError,
    now,
) -> PublishAttemptProcessResult:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        next_attempt_count = attempt.attempt_count + 1
        max_attempts_exceeded = error.retryable and (
            next_attempt_count >= MAX_PUBLISH_ATTEMPTS
        )
        state = (
            PublishAttempt.STATE_FAILED_RETRYABLE
            if error.retryable and not max_attempts_exceeded
            else PublishAttempt.STATE_FAILED_TERMINAL
        )
        attempt.attempt_count = next_attempt_count
        attempt.state = state
        attempt.failure_code = error.code or (
            PROVIDER_RETRYABLE_ERROR if error.retryable else PROVIDER_TERMINAL_ERROR
        )
        if max_attempts_exceeded:
            attempt.failure_code = PROVIDER_MAX_ATTEMPTS_EXCEEDED
        attempt.failure_detail_safe = _sanitize_failure_detail(error.detail_safe)
        attempt.next_retry_at = (
            now + _retry_delay(attempt.attempt_count)
            if error.retryable and not max_attempts_exceeded
            else None
        )
        attempt.finished_at = now if not error.retryable or max_attempts_exceeded else None
        attempt.save(
            update_fields=[
                "attempt_count",
                "state",
                "failure_code",
                "failure_detail_safe",
                "next_retry_at",
                "finished_at",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_FAILED,
            attempt_id=str(attempt.id),
            state=attempt.state,
            failure_code=attempt.failure_code,
            failure_detail_safe=attempt.failure_detail_safe,
        )


def _mark_attempt_published(
    *,
    tenant,
    attempt_id: str | UUID,
    provider_result: FacebookPagePublishResult,
    now,
) -> PublishAttemptProcessResult:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        if attempt.state == PublishAttempt.STATE_PUBLISHED:
            published_post = PublishedPost.all_objects.filter(
                tenant=tenant,
                channel=attempt.channel,
                meta_post_id=attempt.meta_post_id,
            ).first()
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=str(attempt.id),
                state=attempt.state,
                published_post_id=str(published_post.id) if published_post else "",
            )
        meta_object_id = _published_meta_object_id(provider_result)
        published_post, _ = PublishedPost.all_objects.get_or_create(
            tenant=tenant,
            channel=attempt.channel,
            meta_post_id=meta_object_id,
            defaults={
                "workspace": attempt.draft.workspace,
                "draft": attempt.draft,
                "version": attempt.version,
                "publishing_identity": attempt.publishing_identity,
                "permalink": provider_result.permalink,
                "published_at": now,
            },
        )
        attempt.attempt_count += 1
        attempt.state = PublishAttempt.STATE_PUBLISHED
        attempt.meta_post_id = meta_object_id
        attempt.failure_code = ""
        attempt.failure_detail_safe = ""
        attempt.next_retry_at = None
        attempt.finished_at = now
        attempt.save(
            update_fields=[
                "attempt_count",
                "state",
                "meta_post_id",
                "failure_code",
                "failure_detail_safe",
                "next_retry_at",
                "finished_at",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_PUBLISHED,
            attempt_id=str(attempt.id),
            state=attempt.state,
            published_post_id=str(published_post.id),
        )


def _prepare_instagram_attempt_for_container(
    *,
    tenant,
    attempt_id: str | UUID,
    now,
) -> InstagramMediaContainerPayload | PublishAttemptProcessResult | None:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        if attempt.state == PublishAttempt.STATE_PUBLISHED:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=str(attempt.id),
                state=attempt.state,
            )
        if attempt.state in {
            PublishAttempt.STATE_CONTAINER_PENDING,
            PublishAttempt.STATE_CONTAINER_READY,
        }:
            return None
        if attempt.state not in PUBLISHABLE_ATTEMPT_STATES:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                attempt_id=str(attempt.id),
                state=attempt.state,
                failure_code=PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
                failure_detail_safe="Publish attempt is not in a publishable state.",
            )
        attempt.state = PublishAttempt.STATE_CONTAINER_CREATING
        attempt.started_at = now
        attempt.meta_container_id = ""
        attempt.meta_container_created_at = None
        attempt.failure_code = ""
        attempt.failure_detail_safe = ""
        attempt.save(
            update_fields=[
                "state",
                "started_at",
                "meta_container_id",
                "meta_container_created_at",
                "failure_code",
                "failure_detail_safe",
                "updated_at",
            ]
        )
        return _instagram_container_payload(attempt)


def _mark_instagram_container_pending(
    *,
    tenant,
    attempt_id: str | UUID,
    container_id: str,
    now,
) -> None:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return
        attempt.state = PublishAttempt.STATE_CONTAINER_PENDING
        attempt.meta_container_id = str(container_id or "").strip()
        attempt.meta_container_created_at = now
        attempt.save(
            update_fields=[
                "state",
                "meta_container_id",
                "meta_container_created_at",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)


def _mark_instagram_container_ready(*, tenant, attempt_id: str | UUID) -> None:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return
        attempt.state = PublishAttempt.STATE_CONTAINER_READY
        attempt.save(update_fields=["state", "updated_at"])
        _refresh_schedule_and_draft_state(attempt.schedule)


def _mark_instagram_container_expired(
    *,
    tenant,
    attempt_id: str | UUID,
    now,
) -> PublishAttemptProcessResult:
    with transaction.atomic():
        attempt = _locked_attempt(attempt_id=attempt_id)
        if attempt is None or attempt.tenant_id != tenant.id:
            return PublishAttemptProcessResult(
                status=PROCESS_STATUS_NOOP,
                failure_code=PREFLIGHT_ATTEMPT_MISSING,
                failure_detail_safe="Publish attempt does not exist.",
            )
        attempt.state = PublishAttempt.STATE_CONTAINER_EXPIRED
        attempt.failure_code = PROVIDER_CONTAINER_EXPIRED
        attempt.failure_detail_safe = "Instagram media container expired before publishing."
        attempt.finished_at = now
        attempt.save(
            update_fields=[
                "state",
                "failure_code",
                "failure_detail_safe",
                "finished_at",
                "updated_at",
            ]
        )
        _refresh_schedule_and_draft_state(attempt.schedule)
        return PublishAttemptProcessResult(
            status=PROCESS_STATUS_FAILED,
            attempt_id=str(attempt.id),
            state=attempt.state,
            failure_code=attempt.failure_code,
            failure_detail_safe=attempt.failure_detail_safe,
        )


def _facebook_payload(attempt: PublishAttempt) -> FacebookPagePublishPayload:
    identity = attempt.publishing_identity
    return FacebookPagePublishPayload(
        tenant_id=str(attempt.tenant_id),
        attempt_id=str(attempt.id),
        draft_id=str(attempt.draft_id),
        version_id=str(attempt.version_id),
        publishing_identity_id=str(attempt.publishing_identity_id),
        meta_page_id=identity.meta_page_id if identity else "",
        caption=str(attempt.version.caption or "").strip(),
    )


def _default_facebook_page_publisher():
    from django.conf import settings

    if not bool(getattr(settings, "CONTENT_OPS_LIVE_FACEBOOK_PUBLISHING", False)):
        return DisabledFacebookPagePublisher()

    from .facebook_graph import FacebookGraphPagePublisher

    return FacebookGraphPagePublisher.from_settings()


def _default_instagram_publisher():
    from django.conf import settings

    if not bool(getattr(settings, "CONTENT_OPS_META_INSTAGRAM_BETA", False)):
        return DisabledInstagramPublisher()

    from .instagram_graph import InstagramGraphPublisher

    return InstagramGraphPublisher.from_settings()


def _instagram_container_payload(attempt: PublishAttempt) -> InstagramMediaContainerPayload:
    identity = attempt.publishing_identity
    media_asset = attempt.version.media_assets.all()[0]
    return InstagramMediaContainerPayload(
        tenant_id=str(attempt.tenant_id),
        attempt_id=str(attempt.id),
        draft_id=str(attempt.draft_id),
        version_id=str(attempt.version_id),
        publishing_identity_id=str(attempt.publishing_identity_id),
        meta_page_id=identity.meta_page_id if identity else "",
        ig_user_id=identity.ig_user_id if identity else "",
        media_url=public_media_fetch_url(media_asset),
        caption=str(attempt.version.caption or "").strip(),
        media_type=media_asset.mime_type,
    )


def _published_meta_object_id(provider_result: Any) -> str:
    return str(
        getattr(provider_result, "meta_post_id", "")
        or getattr(provider_result, "meta_media_id", "")
    )


def _instagram_container_is_expired(attempt: PublishAttempt, *, now) -> bool:
    if not attempt.meta_container_id or attempt.meta_container_created_at is None:
        return False
    return attempt.meta_container_created_at <= now - INSTAGRAM_CONTAINER_TTL


def _normalize_instagram_container_status(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized == INSTAGRAM_STATUS_FINISHED:
        return INSTAGRAM_STATUS_FINISHED
    if normalized in {"IN_PROGRESS", "PROCESSING", "PENDING"}:
        return INSTAGRAM_STATUS_IN_PROGRESS
    if normalized in {"EXPIRED"}:
        return INSTAGRAM_STATUS_EXPIRED
    return INSTAGRAM_STATUS_ERROR


def _refresh_schedule_and_draft_state(schedule: ContentSchedule) -> None:
    attempts = list(
        PublishAttempt.all_objects.filter(schedule=schedule).only("id", "state")
    )
    if not attempts:
        return
    states = {attempt.state for attempt in attempts}
    published_count = sum(
        1 for attempt in attempts if attempt.state == PublishAttempt.STATE_PUBLISHED
    )
    terminal_or_blocked_count = sum(
        1 for attempt in attempts if attempt.state in TERMINAL_OR_BLOCKED_ATTEMPT_STATES
    )
    if published_count == len(attempts):
        schedule_state = ContentSchedule.STATE_PUBLISHED
        draft_state = ContentDraft.STATE_PUBLISHED
    elif published_count and terminal_or_blocked_count == len(attempts):
        schedule_state = ContentSchedule.STATE_PARTIAL
        draft_state = ContentDraft.STATE_PARTIALLY_PUBLISHED
    elif states.issubset(TERMINAL_OR_BLOCKED_ATTEMPT_STATES):
        schedule_state = ContentSchedule.STATE_FAILED
        draft_state = ContentDraft.STATE_FAILED
    else:
        schedule_state = ContentSchedule.STATE_DISPATCHING
        draft_state = ContentDraft.STATE_PUBLISHING
    schedule.state = schedule_state
    schedule.save(update_fields=["state", "updated_at"])
    draft = schedule.draft
    draft.state = draft_state
    draft.save(update_fields=["state", "updated_at"])


def _retry_delay(attempt_count: int) -> timedelta:
    delay = min(
        RETRY_BASE_DELAY * (2 ** max(attempt_count - 1, 0)),
        RETRY_MAX_DELAY,
    )
    jitter = timedelta(seconds=random.randint(0, RETRY_JITTER_MAX_SECONDS))
    return min(delay + jitter, RETRY_MAX_DELAY)


def _sanitize_failure_detail(value: str) -> str:
    detail = str(value or "Publishing failed.").strip() or "Publishing failed."
    lowered = detail.lower()
    if any(fragment in lowered for fragment in FORBIDDEN_FAILURE_DETAIL_FRAGMENTS):
        return "Publishing failed with a provider error."
    return detail[:500]


def _get_attempt(*, attempt_id: str | UUID) -> PublishAttempt | None:
    return (
        PublishAttempt.all_objects.select_related(
            "schedule",
            "draft",
            "version",
            "publishing_identity",
        )
        .filter(id=attempt_id)
        .first()
    )


def _context(attempt: PublishAttempt) -> dict[str, str | None]:
    return {
        "channel": attempt.channel,
        "attempt_id": str(attempt.id),
        "schedule_id": str(attempt.schedule_id) if attempt.schedule_id else "",
        "draft_id": str(attempt.draft_id) if attempt.draft_id else "",
        "version_id": str(attempt.version_id) if attempt.version_id else "",
        "publishing_identity_id": str(attempt.publishing_identity_id)
        if attempt.publishing_identity_id
        else None,
    }


def _validate_approval_snapshot(
    attempt: PublishAttempt,
) -> dict[str, str] | None:
    snapshot = attempt.schedule.approval_snapshot
    if not isinstance(snapshot, dict):
        return {
            "code": PREFLIGHT_APPROVAL_SNAPSHOT_MISSING,
            "detail": "Approval snapshot is missing for the scheduled version.",
        }
    if str(snapshot.get("version_id") or "") != str(attempt.version_id):
        return {
            "code": PREFLIGHT_SCHEDULE_VERSION_STALE,
            "detail": "Approval snapshot does not match the attempt version.",
        }
    approvals = snapshot.get("approvals")
    if not isinstance(approvals, list):
        return {
            "code": PREFLIGHT_APPROVAL_SNAPSHOT_MISSING,
            "detail": "Approval snapshot does not include approval records.",
        }
    has_client_approval = any(
        isinstance(approval, dict)
        and approval.get("reviewer_type") == "client"
        and approval.get("status") == "approved"
        for approval in approvals
    )
    if not has_client_approval:
        return {
            "code": PREFLIGHT_CLIENT_APPROVAL_MISSING,
            "detail": "Client approval is required before publishing.",
        }
    return None


def _validate_attempt_common(
    *,
    attempt: PublishAttempt,
    tenant,
) -> dict[str, str] | None:
    if attempt.schedule_id is None or attempt.schedule.tenant_id != tenant.id:
        return {
            "code": PREFLIGHT_SCHEDULE_MISSING,
            "detail": "Publish schedule is missing or unavailable for this tenant.",
        }
    if attempt.draft_id is None or attempt.draft.tenant_id != tenant.id:
        return {
            "code": PREFLIGHT_DRAFT_MISSING,
            "detail": "Content draft is missing or unavailable for this tenant.",
        }
    if attempt.version_id is None or attempt.version.tenant_id != tenant.id:
        return {
            "code": PREFLIGHT_VERSION_MISSING,
            "detail": "Content version is missing or unavailable for this tenant.",
        }
    if attempt.draft.state not in {
        ContentDraft.STATE_SCHEDULED,
        ContentDraft.STATE_PUBLISHING,
    }:
        return {
            "code": PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
            "detail": "Content draft is not in a publishable state.",
        }
    if attempt.draft.active_version_id != attempt.version_id:
        return {
            "code": PREFLIGHT_SCHEDULE_VERSION_STALE,
            "detail": "Scheduled version is no longer the active draft version.",
        }
    if attempt.schedule.version_id != attempt.version_id:
        return {
            "code": PREFLIGHT_SCHEDULE_VERSION_STALE,
            "detail": "Publish attempt version does not match the schedule version.",
        }
    return _validate_approval_snapshot(attempt)


def _validate_identity(attempt: PublishAttempt, *, tenant) -> dict[str, str] | None:
    identity = attempt.publishing_identity
    if identity is None:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_MISSING,
            "detail": "Publish attempt does not have a publishing identity.",
        }
    if identity.tenant_id != tenant.id:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT,
            "detail": "Publishing identity does not belong to this tenant.",
        }
    if identity.platform != PublishingIdentity.PLATFORM_FACEBOOK_PAGE:
        return {
            "code": PREFLIGHT_UNSUPPORTED_CHANNEL,
            "detail": "Publishing identity is not a Facebook Page identity.",
        }
    if identity.selection_state != PublishingIdentity.SELECTION_SELECTED:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_NOT_SELECTED,
            "detail": "Publishing identity is not selected for publishing.",
        }
    if identity.publish_readiness_state in {
        PublishingIdentity.READINESS_BLOCKED,
        PublishingIdentity.READINESS_NEEDS_REAUTH,
        PublishingIdentity.READINESS_NEEDS_REVIEW,
    }:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY,
            "detail": "Publishing identity is not ready for publishing.",
        }
    return None


def _validate_instagram_identity(
    attempt: PublishAttempt,
    *,
    tenant,
) -> dict[str, str] | None:
    identity = attempt.publishing_identity
    if identity is None:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_MISSING,
            "detail": "Publish attempt does not have an Instagram publishing identity.",
        }
    if identity.tenant_id != tenant.id:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT,
            "detail": "Publishing identity does not belong to this tenant.",
        }
    if identity.platform != PublishingIdentity.PLATFORM_INSTAGRAM:
        return {
            "code": PREFLIGHT_UNSUPPORTED_CHANNEL,
            "detail": "Publishing identity is not an Instagram identity.",
        }
    if not str(identity.ig_user_id or "").strip():
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_MISSING,
            "detail": "Instagram publishing identity is missing the IG user ID.",
        }
    if identity.selection_state != PublishingIdentity.SELECTION_SELECTED:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_NOT_SELECTED,
            "detail": "Publishing identity is not selected for publishing.",
        }
    if identity.publish_readiness_state in {
        PublishingIdentity.READINESS_BLOCKED,
        PublishingIdentity.READINESS_NEEDS_REAUTH,
        PublishingIdentity.READINESS_NEEDS_REVIEW,
    }:
        return {
            "code": PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY,
            "detail": "Publishing identity is not ready for publishing.",
        }
    return None


def _blocked(
    *,
    code: str,
    detail: str,
    channel: str = "",
    attempt_id: str = "",
    schedule_id: str = "",
    draft_id: str = "",
    version_id: str = "",
    publishing_identity_id: str | None = None,
) -> PublishPreflightResult:
    return PublishPreflightResult(
        ready=False,
        failure_code=code,
        failure_detail_safe=detail,
        channel=channel,
        attempt_id=attempt_id,
        schedule_id=schedule_id,
        draft_id=draft_id,
        version_id=version_id,
        publishing_identity_id=publishing_identity_id,
    )


__all__ = [
    "PREFLIGHT_APPROVAL_SNAPSHOT_MISSING",
    "PREFLIGHT_ATTEMPT_MISSING",
    "PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE",
    "PREFLIGHT_ATTEMPT_WRONG_TENANT",
    "PREFLIGHT_CLIENT_APPROVAL_MISSING",
    "PREFLIGHT_CONTENT_MISSING",
    "PREFLIGHT_DRAFT_MISSING",
    "PREFLIGHT_FACEBOOK_PAGE_PUBLISHING_NOT_READY",
    "PREFLIGHT_INSTAGRAM_CAPTION_TOO_LONG",
    "PREFLIGHT_INSTAGRAM_MEDIA_REQUIRED",
    "PREFLIGHT_INSTAGRAM_PUBLISHING_NOT_READY",
    "PREFLIGHT_PUBLISHING_IDENTITY_MISSING",
    "PREFLIGHT_PUBLISHING_IDENTITY_NOT_READY",
    "PREFLIGHT_PUBLISHING_IDENTITY_NOT_SELECTED",
    "PREFLIGHT_PUBLISHING_IDENTITY_WRONG_TENANT",
    "PREFLIGHT_SCHEDULE_MISSING",
    "PREFLIGHT_SCHEDULE_VERSION_STALE",
    "PREFLIGHT_UNSUPPORTED_CHANNEL",
    "PREFLIGHT_VERSION_MISSING",
    "PROCESS_STATUS_BLOCKED",
    "PROCESS_STATUS_FAILED",
    "PROCESS_STATUS_NOOP",
    "PROCESS_STATUS_PUBLISHED",
    "PROCESS_STATUS_QUEUED",
    "PROVIDER_NOT_CONFIGURED",
    "PROVIDER_CONTAINER_ERROR",
    "PROVIDER_CONTAINER_EXPIRED",
    "PROVIDER_CONTAINER_NOT_READY",
    "PROVIDER_RETRYABLE_ERROR",
    "PROVIDER_TERMINAL_ERROR",
    "DisabledFacebookPagePublisher",
    "DisabledInstagramPublisher",
    "FacebookPagePublishError",
    "FacebookPagePublishPayload",
    "FacebookPagePublishResult",
    "InstagramMediaContainerPayload",
    "InstagramMediaContainerResult",
    "InstagramMediaContainerStatusResult",
    "InstagramMediaPublishResult",
    "InstagramPublishError",
    "PublishAttemptProcessResult",
    "PublishQueueProcessResult",
    "PublishPreflightResult",
    "RetryRequeueResult",
    "preflight_facebook_page_attempt",
    "preflight_instagram_attempt",
    "process_due_publish_attempts",
    "process_facebook_page_publish_attempt",
    "process_instagram_publish_attempt",
    "requeue_due_retryable_attempts",
    "requeue_failed_publish_attempt",
]
