"""Celery tasks for integrations."""

from __future__ import annotations

import logging

from celery import shared_task

from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(AirbyteClientError,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def trigger_scheduled_airbyte_syncs(self):  # noqa: ANN001
    """Trigger due Airbyte syncs using the shared scheduling service."""

    try:
        with AirbyteClient.from_settings() as client:
            service = AirbyteSyncService(client)
            triggered = service.sync_due_connections()
    except AirbyteClientConfigurationError as exc:
        logger.error("Airbyte client misconfigured", exc_info=exc)
        raise self.retry(exc=exc, countdown=60)
    return triggered
