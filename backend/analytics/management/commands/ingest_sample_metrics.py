from __future__ import annotations

import csv
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from accounts.dev_admin import resolve_default_tenant
from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from analytics.models import Ad, AdSet, Campaign, RawPerformanceRecord


def _dev_seed_allowed() -> bool:
    allowed = str(os.environ.get("ALLOW_DEFAULT_ADMIN", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    return settings.DEBUG or allowed


def _parse_int(value: str | None) -> int:
    try:
        return int(value) if value is not None and str(value).strip() else 0
    except (TypeError, ValueError):
        return 0


def _parse_decimal(value: str | None) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None and str(value).strip() else Decimal("0")
    except (TypeError, ValueError, ArithmeticError):
        return Decimal("0")


def _default_fixture_path() -> Path:
    return Path(settings.BASE_DIR) / "fixtures" / "sample_ingest.csv"


class Command(BaseCommand):
    help = "Ingest sample analytics metrics from a CSV file for local development."

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument(
            "--file",
            help="Path to a CSV file with sample metrics.",
        )
        parser.add_argument(
            "--tenant-id",
            help="Target tenant UUID. Defaults to DJANGO_DEFAULT_TENANT_ID or first tenant.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing raw performance records for the tenant before ingesting.",
        )
        parser.add_argument(
            "--source",
            help="Fallback source/platform label when missing in the CSV.",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN001
        if not _dev_seed_allowed():
            self.stdout.write(
                self.style.WARNING(
                    "Refusing to ingest sample data outside DEBUG. Set ALLOW_DEFAULT_ADMIN=1 to override."
                )
            )
            return

        tenant_id = options.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant is None:
                self.stdout.write(self.style.ERROR(f"Tenant not found: {tenant_id}"))
                return
        else:
            tenant = resolve_default_tenant()

        path = Path(options.get("file") or _default_fixture_path())
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"Sample file not found: {path}"))
            return

        if options.get("reset"):
            RawPerformanceRecord.objects.filter(tenant=tenant).delete()

        fallback_source = (options.get("source") or "demo").strip() or "demo"
        created = 0
        updated = 0
        skipped = 0

        with tenant_context(str(tenant.id)):
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    self.stdout.write(self.style.ERROR("CSV file missing header row."))
                    return

                for row in reader:
                    row_date = (row.get("date") or row.get("date_day") or "").strip()
                    parsed_date = parse_date(row_date) if row_date else None
                    if parsed_date is None:
                        skipped += 1
                        continue

                    source = (
                        (row.get("source") or row.get("platform") or fallback_source).strip()
                        or fallback_source
                    )

                    campaign_ext = (row.get("campaign_external_id") or row.get("campaign_id") or "").strip()
                    campaign_name = (row.get("campaign_name") or campaign_ext or "Sample Campaign").strip()
                    if not campaign_ext:
                        campaign_ext = f"camp-{parsed_date.isoformat()}"

                    campaign, _ = Campaign.objects.get_or_create(
                        tenant=tenant,
                        external_id=campaign_ext,
                        defaults={"name": campaign_name, "platform": source},
                    )

                    adset_ext = (row.get("adset_external_id") or row.get("adset_id") or "").strip()
                    adset_name = (row.get("adset_name") or adset_ext or "Sample Ad Set").strip()
                    if not adset_ext:
                        adset_ext = f"{campaign_ext}-adset"

                    adset, _ = AdSet.objects.get_or_create(
                        tenant=tenant,
                        external_id=adset_ext,
                        defaults={"name": adset_name, "campaign": campaign},
                    )

                    ad_ext = (row.get("ad_external_id") or row.get("ad_id") or "").strip()
                    ad_name = (row.get("ad_name") or ad_ext or "Sample Ad").strip()
                    if not ad_ext:
                        ad_ext = f"{adset_ext}-ad"

                    ad, _ = Ad.objects.get_or_create(
                        tenant=tenant,
                        external_id=ad_ext,
                        defaults={"name": ad_name, "adset": adset},
                    )

                    record_external_id = (row.get("external_id") or "").strip()
                    if not record_external_id:
                        record_external_id = f"{ad_ext}-{parsed_date.isoformat()}"

                    record_defaults = {
                        "source": source,
                        "campaign": campaign,
                        "adset": adset,
                        "ad": ad,
                        "impressions": _parse_int(row.get("impressions")),
                        "clicks": _parse_int(row.get("clicks")),
                        "spend": _parse_decimal(row.get("spend")),
                        "currency": (row.get("currency") or "").strip(),
                        "conversions": _parse_int(row.get("conversions")),
                        "raw_payload": row,
                    }

                    _, was_created = RawPerformanceRecord.objects.update_or_create(
                        tenant=tenant,
                        external_id=record_external_id,
                        date=parsed_date,
                        defaults=record_defaults,
                    )

                    if was_created:
                        created += 1
                    else:
                        updated += 1

        summary = f"Ingested sample metrics for tenant {tenant.name}: {created} created, {updated} updated"
        if skipped:
            summary += f", {skipped} skipped"
        self.stdout.write(self.style.SUCCESS(summary))
