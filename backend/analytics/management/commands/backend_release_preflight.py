from __future__ import annotations

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.metrics import (
    observe_airbyte_sync,
    observe_combined_metrics_request,
    observe_dbt_run,
    observe_task,
    observe_task_queue_start,
    observe_task_retry,
)

_SEED_TASK_NAME = "analytics.sync_metrics_snapshots"
_SEED_TENANT_ID = "00000000-0000-0000-0000-000000000000"
_SEED_CONNECTION_ID = "release-preflight"


def _seed_required_metrics() -> None:
    observe_task(task_name=_SEED_TASK_NAME, status="success", duration_seconds=0.1)
    observe_task_retry(task_name=_SEED_TASK_NAME, reason="airbyte_client_error")
    observe_task_queue_start(
        task_name=_SEED_TASK_NAME,
        queue_name=getattr(settings, "CELERY_QUEUE_SYNC", "sync"),
        queue_wait_seconds=0.1,
    )
    observe_task_queue_start(
        task_name=_SEED_TASK_NAME,
        queue_name=getattr(settings, "CELERY_QUEUE_SNAPSHOT", "snapshot"),
        queue_wait_seconds=0.1,
    )
    observe_task_queue_start(
        task_name=_SEED_TASK_NAME,
        queue_name=getattr(settings, "CELERY_QUEUE_SUMMARY", "summary"),
        queue_wait_seconds=0.1,
    )
    observe_combined_metrics_request(
        source="warehouse",
        cache_outcome="miss",
        status="success",
        duration_seconds=0.1,
        query_count=1,
        snapshot_written=True,
        has_filters=False,
    )
    observe_airbyte_sync(
        tenant_id=_SEED_TENANT_ID,
        provider="meta",
        connection_id=_SEED_CONNECTION_ID,
        duration_seconds=1.0,
        records_synced=1,
        status="succeeded",
    )
    observe_dbt_run("success", 1.0)


class Command(BaseCommand):
    help = (
        "Seed deterministic backend observability samples and run strict "
        "backend release smoke checks."
    )

    def add_arguments(self, parser) -> None:  # noqa: ANN001
        parser.add_argument(
            "--strict-external",
            action="store_true",
            help="Also require /api/health/airbyte and /api/health/dbt to return 200.",
        )
        parser.add_argument(
            "--no-seed-metrics",
            action="store_true",
            help="Skip deterministic metric seeding before running smoke checks.",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        if not bool(options.get("no_seed_metrics")):
            _seed_required_metrics()

        smoke_args: list[str] = ["--strict-observability"]
        if bool(options.get("strict_external")):
            smoke_args.append("--strict-external")

        call_command("backend_release_smoke", *smoke_args, stdout=self.stdout)
