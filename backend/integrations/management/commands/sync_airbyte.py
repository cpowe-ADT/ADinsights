from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
    AirbyteSyncService,
)
from integrations.models import AirbyteConnection


class Command(BaseCommand):
    help = "Trigger due Airbyte syncs based on stored schedules."

    def handle(self, *args, **options):  # noqa: ANN001, ANN002
        try:
            with AirbyteClient.from_settings() as client:
                service = AirbyteSyncService(client)
                updates = service.sync_due_connections()
                AirbyteConnection.persist_sync_updates(updates)
                triggered = len(updates)
        except AirbyteClientConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except AirbyteClientError as exc:
            raise CommandError(f"Airbyte API call failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Triggered {triggered} Airbyte sync(s)."))
