from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

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
from integrations.models import AirbyteConnection, ConnectionSyncUpdate

RUNNING_STATUSES = {"running", "pending", "incomplete"}


def _normalize_status(value: str | None) -> str:
    return (value or "").strip().lower()


def _reference_timestamp(connection: AirbyteConnection):
    reference = (
        connection.last_job_updated_at
        or connection.last_synced_at
        or connection.last_job_created_at
    )
    if reference is None:
        return None
    if timezone.is_naive(reference):  # pragma: no cover - backend dependent
        return timezone.make_aware(reference)
    return reference


class Command(BaseCommand):
    help = (
        "Reconcile stale Airbyte running/pending sync statuses against the latest Airbyte "
        "job state, with an optional force-failure fallback."
    )

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument(
            "--stale-minutes",
            type=int,
            default=120,
            help="Minimum age in minutes before a running/pending status is considered stale (default: 120).",
        )
        parser.add_argument(
            "--tenant-id",
            default="",
            help="Optional tenant UUID filter.",
        )
        parser.add_argument(
            "--connection-id",
            default="",
            help="Optional Airbyte connection UUID filter.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist reconciled updates (default is dry-run).",
        )
        parser.add_argument(
            "--force-stale-failure",
            action="store_true",
            help="When remote status is still running or unavailable, force stale jobs to failed.",
        )

    def handle(self, *args, **options):  # noqa: ANN001, ANN002
        stale_minutes = max(int(options["stale_minutes"]), 1)
        stale_threshold = timedelta(minutes=stale_minutes)
        apply_changes = bool(options.get("apply"))
        force_stale_failure = bool(options.get("force_stale_failure"))

        if force_stale_failure and not apply_changes:
            raise CommandError("--force-stale-failure requires --apply")

        queryset = AirbyteConnection.all_objects.select_related("tenant").filter(
            is_active=True
        )
        tenant_id = str(options.get("tenant_id") or "").strip()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        connection_id = str(options.get("connection_id") or "").strip()
        if connection_id:
            queryset = queryset.filter(connection_id=connection_id)

        now = timezone.now()
        candidates: list[tuple[AirbyteConnection, int]] = []
        for connection in queryset.order_by("tenant_id", "name"):
            if _normalize_status(connection.last_job_status) not in RUNNING_STATUSES:
                continue
            reference = _reference_timestamp(connection)
            if reference is None:
                continue
            age_seconds = int((now - reference).total_seconds())
            if age_seconds >= int(stale_threshold.total_seconds()):
                candidates.append((connection, age_seconds))

        if not apply_changes:
            self.stdout.write(
                f"Dry-run: stale_threshold_minutes={stale_minutes} candidates={len(candidates)}"
            )
            for connection, age_seconds in candidates:
                self.stdout.write(
                    (
                        f"- tenant={connection.tenant_id} connection={connection.connection_id} "
                        f"status={connection.last_job_status or 'unknown'} age_seconds={age_seconds}"
                    )
                )
            return

        try:
            with AirbyteClient.from_settings() as client:
                result = self._apply_reconciliation(
                    client=client,
                    candidates=candidates,
                    now=now,
                    force_stale_failure=force_stale_failure,
                )
        except AirbyteClientConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Reconciled Airbyte sync statuses: "
                f"candidates={len(candidates)} "
                f"updated={result['updated']} "
                f"forced_failed={result['forced_failed']} "
                f"skipped_remote_running={result['skipped_remote_running']} "
                f"skipped_no_remote_job={result['skipped_no_remote_job']} "
                f"errors={result['errors']}"
            )
        )

    def _apply_reconciliation(
        self,
        *,
        client: AirbyteClient,
        candidates: list[tuple[AirbyteConnection, int]],
        now,
        force_stale_failure: bool,
    ) -> dict[str, int]:
        updates: list[ConnectionSyncUpdate] = []
        stats = {
            "updated": 0,
            "forced_failed": 0,
            "skipped_remote_running": 0,
            "skipped_no_remote_job": 0,
            "errors": 0,
        }

        for connection, age_seconds in candidates:
            try:
                latest_job = client.latest_job(str(connection.connection_id))
            except AirbyteClientError:
                stats["errors"] += 1
                if force_stale_failure:
                    updates.append(self._forced_failure_update(connection, now, age_seconds))
                    stats["forced_failed"] += 1
                continue

            resolved = self._build_reconciled_update(
                connection=connection,
                latest_job=latest_job,
                now=now,
                age_seconds=age_seconds,
                force_stale_failure=force_stale_failure,
            )

            if resolved is None:
                if latest_job is None:
                    stats["skipped_no_remote_job"] += 1
                else:
                    stats["skipped_remote_running"] += 1
                continue

            updates.append(resolved)
            if _normalize_status(resolved.status) in {"failed"} and force_stale_failure:
                remote_status = _normalize_status(extract_job_status(latest_job) if latest_job else None)
                if remote_status in RUNNING_STATUSES or latest_job is None:
                    stats["forced_failed"] += 1
            else:
                stats["updated"] += 1

        if updates:
            AirbyteConnection.persist_sync_updates(updates)

        return stats

    def _build_reconciled_update(
        self,
        *,
        connection: AirbyteConnection,
        latest_job: dict[str, Any] | None,
        now,
        age_seconds: int,
        force_stale_failure: bool,
    ) -> ConnectionSyncUpdate | None:
        if latest_job is None:
            if not force_stale_failure:
                return None
            return self._forced_failure_update(connection, now, age_seconds)

        remote_status = extract_job_status(latest_job) or connection.last_job_status or "unknown"
        remote_status_normalized = _normalize_status(remote_status)
        snapshot = extract_attempt_snapshot(latest_job)
        created_at = extract_job_created_at(latest_job) or _reference_timestamp(connection) or now
        updated_at = extract_job_updated_at(latest_job)
        completed_at = infer_completion_time(latest_job, snapshot) if snapshot else None
        error_message = extract_job_error(latest_job)

        status_value = remote_status
        if remote_status_normalized in RUNNING_STATUSES:
            if not force_stale_failure:
                return None
            status_value = "failed"
            if not error_message:
                error_message = (
                    "Marked failed by reconcile_airbyte_sync_status after "
                    f"{age_seconds} seconds in running state."
                )
            if updated_at is None:
                updated_at = now
            if completed_at is None:
                completed_at = updated_at

        if updated_at is None:
            updated_at = created_at

        return ConnectionSyncUpdate(
            connection=connection,
            job_id=(
                str(extract_job_id(latest_job))
                if extract_job_id(latest_job) is not None
                else (connection.last_job_id or None)
            ),
            status=status_value,
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
            duration_seconds=snapshot.duration_seconds if snapshot else None,
            records_synced=snapshot.records_synced if snapshot else None,
            bytes_synced=snapshot.bytes_synced if snapshot else None,
            api_cost=snapshot.api_cost if snapshot else None,
            error=error_message,
        )

    def _forced_failure_update(
        self,
        connection: AirbyteConnection,
        now,
        age_seconds: int,
    ) -> ConnectionSyncUpdate:
        created_at = _reference_timestamp(connection) or now
        return ConnectionSyncUpdate(
            connection=connection,
            job_id=connection.last_job_id or None,
            status="failed",
            created_at=created_at,
            updated_at=now,
            completed_at=now,
            duration_seconds=None,
            records_synced=None,
            bytes_synced=None,
            api_cost=None,
            error=(
                "Marked failed by reconcile_airbyte_sync_status because remote status "
                f"could not be confirmed after {age_seconds} seconds."
            ),
        )
