"""Celery tasks for cross-platform Client grouping (Sprint 9).

The primary task here — ``refresh_client_suggestions`` — is fired after a
platform account sync completes for a tenant (Meta OAuth + account sync,
Google Ads SDK incremental). It runs the pure-function name-match suggester,
then persists the result as a ``ClientSuggestionSnapshot`` so the dashboard
banner can surface unclaimed accounts proactively without hitting the
suggester on every request.

Idempotency: the snapshot is a ``OneToOneField`` per tenant so re-running the
task always upserts a single row. When the new run's ``suggestion_count``
differs from the prior acknowledged snapshot's count we clear
``acknowledged_at`` so the banner re-surfaces.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from celery import shared_task
from django.utils import timezone

from accounts.tenant_context import tenant_context
from core.tasks import BaseAdInsightsTask
from integrations.clients.suggester import suggest_clients
from integrations.models import ClientSuggestionSnapshot

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION_THRESHOLD = 0.7


def _serialize_suggestions(suggestions) -> list[dict[str, Any]]:
    """Serialize dataclass suggestions to a JSON-safe snapshot payload."""

    payload: list[dict[str, Any]] = []
    for suggestion in suggestions:
        item = asdict(suggestion)
        # ``unclaimed_accounts`` contains SuggestionAccount dataclasses which
        # ``asdict`` handles recursively, but we normalize keys explicitly for
        # the snapshot contract.
        accounts = [
            {
                "platform": acct["platform"],
                "external_id": acct["external_id"],
                "display_name": acct["display_name"],
            }
            for acct in item.get("unclaimed_accounts", [])
        ]
        payload.append(
            {
                "proposed_name": item["proposed_name"],
                "normalized_name": item["normalized_name"],
                "existing_client_id": item["existing_client_id"],
                "confidence": item["confidence"],
                "unclaimed_accounts": accounts,
            }
        )
    return payload


@shared_task(bind=True, base=BaseAdInsightsTask, max_retries=3, name="integrations.clients.refresh_client_suggestions")
def refresh_client_suggestions(
    self,  # noqa: ANN001 - Celery signature
    tenant_id: str,
    *,
    trigger_reason: str = ClientSuggestionSnapshot.REASON_MANUAL,
    threshold: float = DEFAULT_SUGGESTION_THRESHOLD,
) -> dict[str, Any]:
    """Refresh the cached ``ClientSuggestionSnapshot`` for a tenant.

    Returns a small summary dict (used mainly for test introspection).
    """

    tenant_id = str(tenant_id)
    with tenant_context(tenant_id):
        try:
            suggestions = suggest_clients(tenant_id, threshold=threshold)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "client_suggestions.refresh_failed",
                extra={"tenant_id": tenant_id, "error": str(exc)},
            )
            raise self.retry(exc=exc, countdown=60)

        payload = _serialize_suggestions(suggestions)
        generated_at = timezone.now()

        existing = ClientSuggestionSnapshot.all_objects.filter(
            tenant_id=tenant_id
        ).first()
        had_prior_count = existing.suggestion_count if existing is not None else 0
        snapshot, _created = ClientSuggestionSnapshot.all_objects.update_or_create(
            tenant_id=tenant_id,
            defaults={
                "trigger_reason": trigger_reason,
                "threshold": threshold,
                "suggestion_count": len(payload),
                "payload": payload,
                "generated_at": generated_at,
                # New run of different shape → resurface the banner.
                "acknowledged_at": (
                    existing.acknowledged_at
                    if existing is not None
                    and len(payload) == had_prior_count
                    and existing.trigger_reason == trigger_reason
                    else None
                ),
            },
        )

    logger.info(
        "client_suggestions.refreshed",
        extra={
            "tenant_id": tenant_id,
            "trigger_reason": trigger_reason,
            "count": snapshot.suggestion_count,
        },
    )
    return {
        "tenant_id": tenant_id,
        "trigger_reason": trigger_reason,
        "suggestion_count": snapshot.suggestion_count,
        "generated_at": snapshot.generated_at.isoformat(),
    }


def enqueue_refresh_client_suggestions(
    tenant_id: str | None,
    *,
    trigger_reason: str = ClientSuggestionSnapshot.REASON_MANUAL,
) -> None:
    """Best-effort fire-and-forget enqueue.

    Call sites (OAuth completion, sync finalizers) should never raise because
    of a suggester hiccup, so swallow dispatch errors with a warning.
    """

    if not tenant_id:
        return
    try:
        refresh_client_suggestions.delay(
            tenant_id=str(tenant_id), trigger_reason=trigger_reason
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning(
            "client_suggestions.enqueue_failed",
            extra={"tenant_id": str(tenant_id), "trigger_reason": trigger_reason},
            exc_info=True,
        )
