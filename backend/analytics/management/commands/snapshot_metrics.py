from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from analytics.tasks import generate_snapshots_for_tenants


class Command(BaseCommand):
    help = "Generate warehouse metrics snapshots for one or more tenants."

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument(
            "--tenant-id",
            dest="tenant_ids",
            action="append",
            help="Limit generation to the specified tenant ID. Can be supplied multiple times.",
        )

    def handle(self, *args: Any, **options: Any):  # noqa: ANN001
        tenant_ids = options.get("tenant_ids")
        outcomes = generate_snapshots_for_tenants(tenant_ids)
        if not outcomes:
            self.stdout.write(self.style.WARNING("No tenants processed."))
            return
        for outcome in outcomes:
            message = (
                f"Tenant {outcome.tenant_id}: {outcome.status} snapshot at "
                f"{outcome.generated_at.isoformat()}"
            )
            self.stdout.write(self.style.SUCCESS(message))
