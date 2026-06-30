from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import Tenant

from content_ops.identity_sync import sync_publishing_identities_for_tenant


class Command(BaseCommand):
    help = (
        "Provision Content Ops Facebook Page publishing identities from "
        "connected Meta pages so they appear as composer destinations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            dest="tenant_id",
            default=None,
            help="Limit the sync to a single tenant id (defaults to all tenants).",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()

        synced_tenants = 0
        for tenant in tenants:
            result = sync_publishing_identities_for_tenant(tenant=tenant)
            synced_tenants += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{tenant.id}: pages={result.total_pages} "
                    f"created={result.created} updated={result.updated} "
                    f"selected={result.selected}"
                )
            )

        if not synced_tenants:
            self.stdout.write(self.style.WARNING("No matching tenants found."))
