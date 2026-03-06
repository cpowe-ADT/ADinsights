from __future__ import annotations

from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Tenant
from integrations.airbyte import (
    AirbyteClient,
    AirbyteClientConfigurationError,
    AirbyteClientError,
)
from integrations.airbyte.service import (
    extract_attempt_snapshot,
    extract_job_created_at,
    extract_job_error,
    extract_job_id,
    extract_job_status,
    extract_job_updated_at,
    infer_completion_time,
)
from integrations.models import AirbyteConnection, ConnectionSyncUpdate, PlatformCredential


def _normalize_connection_id(raw_value: str) -> str:
    try:
        return str(UUID(raw_value))
    except (ValueError, TypeError) as exc:
        raise CommandError(f"Invalid --connection-id value: {raw_value}") from exc


def _schedule_defaults(connection_payload: dict[str, object]) -> tuple[str, int | None, str]:
    schedule_type = str(connection_payload.get("scheduleType") or "").strip().lower()
    schedule_data = connection_payload.get("scheduleData") or {}
    if not isinstance(schedule_data, dict):
        schedule_data = {}

    if schedule_type == "cron":
        cron_data = schedule_data.get("cron") or {}
        cron_expression = ""
        if isinstance(cron_data, dict):
            cron_expression = str(cron_data.get("cronExpression") or "").strip()
        return AirbyteConnection.SCHEDULE_CRON, None, cron_expression

    if schedule_type == "basic":
        basic = schedule_data.get("basicSchedule") or {}
        if isinstance(basic, dict):
            units = basic.get("units")
            time_unit = str(basic.get("timeUnit") or "").strip().lower()
            if isinstance(units, int) and units > 0:
                multiplier = {"minutes": 1, "hours": 60, "days": 1440}.get(time_unit)
                if multiplier is not None:
                    return AirbyteConnection.SCHEDULE_INTERVAL, units * multiplier, ""
        return AirbyteConnection.SCHEDULE_INTERVAL, 60, ""

    return AirbyteConnection.SCHEDULE_MANUAL, None, ""


def _provider_from_name(name: str) -> str | None:
    lowered = name.lower()
    if "meta" in lowered or "facebook" in lowered:
        return PlatformCredential.META
    if "google" in lowered:
        return PlatformCredential.GOOGLE
    return None


class Command(BaseCommand):
    help = (
        "Backfill Airbyte sync status into backend records from live Airbyte jobs, "
        "with optional connection discovery/creation for a workspace."
    )

    def add_arguments(self, parser) -> None:  # noqa: ANN001
        parser.add_argument(
            "--tenant-id",
            default="",
            help="Optional tenant UUID filter. Required with --create-missing.",
        )
        parser.add_argument(
            "--workspace-id",
            default="",
            help="Optional Airbyte workspace UUID used for remote connection discovery.",
        )
        parser.add_argument(
            "--connection-id",
            action="append",
            default=[],
            help="Specific Airbyte connection UUID to backfill. Can be repeated.",
        )
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help="Create missing backend AirbyteConnection rows for discovered workspace connections.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist updates. Without this flag, command runs in dry-run mode.",
        )

    def handle(self, *args, **options):  # noqa: ANN001, ANN002
        tenant_id = str(options.get("tenant_id") or "").strip()
        workspace_id = str(options.get("workspace_id") or "").strip()
        create_missing = bool(options.get("create_missing"))
        apply_changes = bool(options.get("apply"))

        requested_connection_ids = {
            _normalize_connection_id(raw_value)
            for raw_value in (options.get("connection_id") or [])
            if str(raw_value).strip()
        }

        if create_missing and not tenant_id:
            raise CommandError("--tenant-id is required with --create-missing.")
        if create_missing and not workspace_id:
            raise CommandError("--workspace-id is required with --create-missing.")

        local_queryset = AirbyteConnection.all_objects.select_related("tenant")
        if tenant_id:
            local_queryset = local_queryset.filter(tenant_id=tenant_id)
        if requested_connection_ids:
            local_queryset = local_queryset.filter(connection_id__in=requested_connection_ids)

        local_connections = {
            str(connection.connection_id): connection for connection in local_queryset
        }

        discovered_payloads: list[dict[str, object]] = []
        if workspace_id:
            try:
                with AirbyteClient.from_settings() as client:
                    discovered_payloads = client.list_connections(workspace_id)
            except AirbyteClientConfigurationError as exc:
                raise CommandError(str(exc)) from exc
            except AirbyteClientError as exc:
                raise CommandError(f"Unable to list Airbyte connections: {exc}") from exc

            if requested_connection_ids:
                discovered_payloads = [
                    payload
                    for payload in discovered_payloads
                    if str(payload.get("connectionId") or "") in requested_connection_ids
                ]

        created_connections = 0
        would_create_connections = 0
        if create_missing:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant is None:
                raise CommandError(f"Tenant not found: {tenant_id}")
            for payload in discovered_payloads:
                connection_id = str(payload.get("connectionId") or "").strip()
                if not connection_id:
                    continue
                if connection_id in local_connections:
                    continue
                would_create_connections += 1
                if not apply_changes:
                    continue
                schedule_type, interval_minutes, cron_expression = _schedule_defaults(payload)
                name = str(payload.get("name") or f"Airbyte {connection_id}").strip()
                provider = _provider_from_name(name)
                status = str(payload.get("status") or "").strip().lower()
                is_active = status != "inactive"
                connection = AirbyteConnection.all_objects.create(
                    tenant=tenant,
                    name=name,
                    connection_id=connection_id,
                    workspace_id=workspace_id,
                    provider=provider,
                    schedule_type=schedule_type,
                    interval_minutes=interval_minutes,
                    cron_expression=cron_expression,
                    is_active=is_active,
                )
                local_connections[connection_id] = connection
                created_connections += 1

        if discovered_payloads and not requested_connection_ids:
            discovered_ids = {
                str(payload.get("connectionId") or "").strip()
                for payload in discovered_payloads
                if str(payload.get("connectionId") or "").strip()
            }
            local_connections = {
                connection_id: connection
                for connection_id, connection in local_connections.items()
                if connection_id in discovered_ids
            }

        if not local_connections:
            if not apply_changes and would_create_connections > 0:
                self.stdout.write(
                    "Dry-run: "
                    f"connections=0 discovered={len(discovered_payloads)} "
                    f"would_create={would_create_connections} updates=0 errors=0"
                )
                return
            raise CommandError("No Airbyte connections matched the provided filters.")

        updates: list[ConnectionSyncUpdate] = []
        errors = 0
        now = timezone.now()

        try:
            with AirbyteClient.from_settings() as client:
                for connection in local_connections.values():
                    try:
                        latest_job = client.latest_job(str(connection.connection_id))
                    except AirbyteClientError:
                        errors += 1
                        continue
                    if latest_job is None:
                        continue
                    snapshot = extract_attempt_snapshot(latest_job)
                    created_at = extract_job_created_at(latest_job) or connection.last_job_created_at or now
                    updated_at = extract_job_updated_at(latest_job) or created_at
                    completed_at = infer_completion_time(latest_job, snapshot) if snapshot else None
                    error_message = extract_job_error(latest_job)
                    updates.append(
                        ConnectionSyncUpdate(
                            connection=connection,
                            job_id=str(extract_job_id(latest_job) or "") or None,
                            status=extract_job_status(latest_job) or connection.last_job_status,
                            created_at=created_at,
                            updated_at=updated_at,
                            completed_at=completed_at,
                            duration_seconds=snapshot.duration_seconds if snapshot else None,
                            records_synced=snapshot.records_synced if snapshot else None,
                            bytes_synced=snapshot.bytes_synced if snapshot else None,
                            api_cost=snapshot.api_cost if snapshot else None,
                            error=error_message,
                        )
                    )
        except AirbyteClientConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        if not apply_changes:
            self.stdout.write(
                "Dry-run: "
                f"connections={len(local_connections)} discovered={len(discovered_payloads)} "
                f"would_create={would_create_connections} updates={len(updates)} errors={errors}"
            )
            return

        persisted = AirbyteConnection.persist_sync_updates(updates)
        self.stdout.write(
            self.style.SUCCESS(
                "Backfilled Airbyte sync status: "
                f"connections={len(local_connections)} discovered={len(discovered_payloads)} "
                f"created={created_connections} updated={len(persisted)} errors={errors}"
            )
        )
