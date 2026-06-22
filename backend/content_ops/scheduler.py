"""Safe schedule dispatch for Content Operations.

This module creates durable publish-attempt queue records only. It does not call
Meta, create Instagram containers, or publish posts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import (
    ContentDraft,
    ContentSchedule,
    PublishingIdentity,
    PublishAttempt,
)
from .readiness import build_content_ops_readiness_payload


@dataclass(frozen=True)
class DispatchResult:
    scanned: int = 0
    schedules_dispatched: int = 0
    attempts_created: int = 0
    attempts_existing: int = 0
    attempts_blocked: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "schedules_dispatched": self.schedules_dispatched,
            "attempts_created": self.attempts_created,
            "attempts_existing": self.attempts_existing,
            "attempts_blocked": self.attempts_blocked,
        }


def dispatch_due_schedules(
    *,
    tenant,
    now=None,
    limit: int = 100,
) -> DispatchResult:
    """Create idempotent publish attempts for due, approved schedules."""

    now = now or timezone.now()
    due_schedules = list(
        ContentSchedule.all_objects.select_related(
            "draft",
            "draft__workspace",
            "version",
        )
        .filter(
            tenant=tenant,
            state=ContentSchedule.STATE_SCHEDULED,
            scheduled_at__lte=now,
            draft__state=ContentDraft.STATE_SCHEDULED,
        )
        .order_by("scheduled_at", "created_at")[:limit]
    )
    counters = DispatchResult(scanned=len(due_schedules))
    readiness = build_content_ops_readiness_payload(tenant=tenant)

    for schedule in due_schedules:
        result = _dispatch_schedule(schedule=schedule, readiness=readiness)
        counters = DispatchResult(
            scanned=counters.scanned,
            schedules_dispatched=counters.schedules_dispatched
            + result.schedules_dispatched,
            attempts_created=counters.attempts_created + result.attempts_created,
            attempts_existing=counters.attempts_existing + result.attempts_existing,
            attempts_blocked=counters.attempts_blocked + result.attempts_blocked,
        )
    return counters


@transaction.atomic
def _dispatch_schedule(
    *,
    schedule: ContentSchedule,
    readiness: dict[str, Any],
) -> DispatchResult:
    schedule = (
        ContentSchedule.all_objects.select_for_update(skip_locked=True)
        .select_related("draft", "draft__workspace", "version")
        .filter(id=schedule.id)
        .first()
    )
    if schedule is None:
        return DispatchResult()
    if schedule.state != ContentSchedule.STATE_SCHEDULED:
        return DispatchResult()
    if not _schedule_snapshot_is_current(schedule):
        schedule.state = ContentSchedule.STATE_FAILED
        schedule.save(update_fields=["state", "updated_at"])
        return DispatchResult(schedules_dispatched=1)
    targets = _schedule_targets(schedule)
    if not targets:
        schedule.state = ContentSchedule.STATE_FAILED
        schedule.save(update_fields=["state", "updated_at"])
        return DispatchResult(schedules_dispatched=1)

    created = 0
    existing = 0
    blocked = 0
    for target in targets:
        attempt, was_created = _get_or_create_attempt(
            schedule=schedule,
            target=target,
            readiness=readiness,
        )
        if was_created:
            created += 1
            if attempt.state == PublishAttempt.STATE_BLOCKED:
                blocked += 1
        else:
            existing += 1

    schedule.state = (
        ContentSchedule.STATE_FAILED
        if created and blocked == created
        else ContentSchedule.STATE_DISPATCHING
    )
    schedule.save(update_fields=["state", "updated_at"])
    return DispatchResult(
        schedules_dispatched=1,
        attempts_created=created,
        attempts_existing=existing,
        attempts_blocked=blocked,
    )


def _get_or_create_attempt(
    *,
    schedule: ContentSchedule,
    target: dict[str, str],
    readiness: dict[str, Any],
) -> tuple[PublishAttempt, bool]:
    channel = target["type"]
    idempotency_key = _attempt_idempotency_key(schedule=schedule, target=target)
    existing = PublishAttempt.all_objects.filter(
        tenant=schedule.tenant,
        idempotency_key=idempotency_key,
    ).first()
    if existing is not None:
        return existing, False

    identity = _selected_identity(
        tenant=schedule.tenant,
        target=target,
    )
    state, failure_code, failure_detail = _attempt_state_for_channel(
        channel=channel,
        readiness=readiness,
        identity=identity,
    )
    return (
        PublishAttempt.all_objects.create(
            tenant=schedule.tenant,
            schedule=schedule,
            draft=schedule.draft,
            version=schedule.version,
            publishing_identity=identity,
            channel=channel,
            state=state,
            idempotency_key=idempotency_key,
            failure_code=failure_code,
            failure_detail_safe=failure_detail,
        ),
        True,
    )


def _schedule_targets(schedule: ContentSchedule) -> list[dict[str, str]]:
    snapshot = schedule.approval_snapshot
    raw_targets = None
    if isinstance(snapshot, dict):
        raw_targets = snapshot.get("target_channels")
    if raw_targets is None:
        raw_targets = schedule.draft.workspace.target_channels
    if not isinstance(raw_targets, list):
        return []
    valid_channels = {
        PublishAttempt.CHANNEL_FACEBOOK_PAGE,
        PublishAttempt.CHANNEL_INSTAGRAM,
    }
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_target in raw_targets:
        if isinstance(raw_target, str):
            target = {"type": raw_target}
        elif isinstance(raw_target, dict):
            target = {
                str(key): str(value)
                for key, value in raw_target.items()
                if value not in (None, "")
            }
            if "type" not in target and "channel" in target:
                target["type"] = target["channel"]
        else:
            continue
        channel = str(target.get("type") or "").strip()
        if channel not in valid_channels:
            continue
        normalized = {"type": channel}
        if channel == PublishAttempt.CHANNEL_FACEBOOK_PAGE and target.get("page_id"):
            normalized["page_id"] = str(target["page_id"]).strip()
        if channel == PublishAttempt.CHANNEL_INSTAGRAM and target.get("ig_user_id"):
            normalized["ig_user_id"] = str(target["ig_user_id"]).strip()
        dedupe_key = (
            normalized["type"],
            normalized.get("page_id", ""),
            normalized.get("ig_user_id", ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        targets.append(normalized)
    return targets


def _attempt_idempotency_key(
    *,
    schedule: ContentSchedule,
    target: dict[str, str],
) -> str:
    channel = target["type"]
    if not target.get("page_id") and not target.get("ig_user_id"):
        return f"schedule:{schedule.id}:channel:{channel}"
    target_payload = json.dumps(target, sort_keys=True, separators=(",", ":"))
    target_fingerprint = hashlib.sha256(target_payload.encode("utf-8")).hexdigest()[:12]
    return f"schedule:{schedule.id}:target:{target_fingerprint}"


def _schedule_snapshot_is_current(schedule: ContentSchedule) -> bool:
    if schedule.draft.active_version_id != schedule.version_id:
        return False
    snapshot = schedule.approval_snapshot
    if not isinstance(snapshot, dict):
        return False
    if str(snapshot.get("version_id") or "") != str(schedule.version_id):
        return False
    approvals = snapshot.get("approvals")
    if not isinstance(approvals, list):
        return False
    return any(
        isinstance(approval, dict)
        and approval.get("reviewer_type") == "client"
        and approval.get("status") == "approved"
        for approval in approvals
    )


def _selected_identity(*, tenant, target: dict[str, str]) -> PublishingIdentity | None:
    queryset = PublishingIdentity.all_objects.filter(
        tenant=tenant,
        platform=target["type"],
        selection_state=PublishingIdentity.SELECTION_SELECTED,
    )
    if target.get("page_id"):
        queryset = queryset.filter(meta_page_id=target["page_id"])
    if target.get("ig_user_id"):
        queryset = queryset.filter(ig_user_id=target["ig_user_id"])
    return queryset.order_by("display_name", "created_at").first()


def _attempt_state_for_channel(
    *,
    channel: str,
    readiness: dict[str, Any],
    identity: PublishingIdentity | None,
) -> tuple[str, str, str]:
    if identity is None:
        return (
            PublishAttempt.STATE_BLOCKED,
            "publishing_identity_missing",
            "No selected publishing identity exists for this channel.",
        )
    axis_key = (
        "facebook_page_publishing"
        if channel == PublishAttempt.CHANNEL_FACEBOOK_PAGE
        else "instagram_publishing"
    )
    axis = readiness.get(axis_key)
    if not isinstance(axis, dict) or axis.get("state") != "ready":
        reason = str(axis.get("reason") or "publishing_readiness_blocked")
        return (
            PublishAttempt.STATE_BLOCKED,
            reason,
            "Publishing readiness is blocked for this channel.",
        )
    return (PublishAttempt.STATE_QUEUED, "", "")
