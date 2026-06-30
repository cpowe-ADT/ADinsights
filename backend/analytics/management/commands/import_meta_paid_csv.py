"""Import operator-supplied Meta paid CSV metrics into stored reporting rows."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.audit import log_audit_event
from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from analytics.models import AdAccount, Campaign, RawPerformanceRecord


COMMAND_SCHEMA_VERSION = "meta_paid_csv_import.v1"
MANUAL_IMPORT_SOURCE = "manual_meta_paid_csv"
RECORD_SOURCE = "meta"
STANDARD_COLUMNS = {
    "account_id",
    "account_name",
    "ad_account_id",
    "campaign",
    "campaign_id",
    "campaign_name",
    "currency",
    "date",
    "date_start",
    "date_stop",
    "day",
    "level",
    "record_id",
    "external_id",
}
COUNT_METRIC_COLUMNS = {
    "impressions": "impressions",
    "reach": "reach",
    "clicks": "clicks",
    "conversions": "conversions",
}
DECIMAL_METRIC_COLUMNS = {
    "spend": "spend",
    "amount_spent": "spend",
    "cost": "spend",
    "cpc": "cpc",
    "cpm": "cpm",
}


@dataclass
class ImportSummary:
    rows_seen: int = 0
    rows_skipped_no_metrics: int = 0
    accounts_seen: set[str] = field(default_factory=set)
    campaigns_seen: set[str] = field(default_factory=set)
    campaigns_created: int = 0
    campaigns_updated: int = 0
    records_created: int = 0
    records_updated: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_seen": self.rows_seen,
            "rows_skipped_no_metrics": self.rows_skipped_no_metrics,
            "account_count": len(self.accounts_seen),
            "campaign_count": len(self.campaigns_seen),
            "campaigns_created": self.campaigns_created,
            "campaigns_updated": self.campaigns_updated,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
        }


class Command(BaseCommand):
    help = (
        "Import a tenant-scoped Meta paid CSV export into RawPerformanceRecord "
        "rows without calling live Meta APIs."
    )

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument("--tenant-id", required=True, help="Target tenant UUID.")
        parser.add_argument(
            "--file", required=True, help="Path to the Meta paid CSV file."
        )
        parser.add_argument(
            "--account-id",
            default="",
            help="Fallback Meta ad account ID when the CSV does not include account_id.",
        )
        parser.add_argument(
            "--currency",
            default="",
            help="Fallback currency when the CSV/account does not provide one.",
        )
        parser.add_argument(
            "--default-level",
            default="campaign",
            help="RawPerformanceRecord level when the CSV does not include level.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and summarize the import without writing reporting rows or audit events.",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN401
        tenant = Tenant.objects.filter(id=options["tenant_id"]).first()
        if tenant is None:
            raise CommandError("Tenant not found.")
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"CSV file not found: {path}")

        imported_at = timezone.now()
        with tenant_context(str(tenant.id)), transaction.atomic():
            summary = _import_rows(
                tenant=tenant,
                path=path,
                fallback_account_id=str(options.get("account_id") or "").strip(),
                fallback_currency=str(options.get("currency") or "").strip(),
                default_level=str(options["default_level"] or "campaign").strip()
                or "campaign",
                imported_at=imported_at,
                dry_run=bool(options.get("dry_run")),
            )
            if not options.get("dry_run"):
                log_audit_event(
                    tenant=tenant,
                    user=None,
                    action="meta_paid_csv_imported",
                    resource_type="ad_account",
                    resource_id="redacted",
                    metadata={
                        "redacted": True,
                        "schema_version": COMMAND_SCHEMA_VERSION,
                        "file_name": path.name,
                        **summary.as_dict(),
                    },
                )

        payload = {
            "schema_version": COMMAND_SCHEMA_VERSION,
            "tenant_id": str(tenant.id),
            "stored_aggregate_only": True,
            "no_live_provider_calls": True,
            "dry_run": bool(options.get("dry_run")),
            "source": MANUAL_IMPORT_SOURCE,
            "summary": summary.as_dict(),
        }
        self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))


def _import_rows(
    *,
    tenant: Tenant,
    path: Path,
    fallback_account_id: str,
    fallback_currency: str,
    default_level: str,
    imported_at: datetime,
    dry_run: bool = False,
) -> ImportSummary:
    summary = ImportSummary()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CommandError("CSV file missing header row.")
        for row_number, raw_row in enumerate(reader, start=2):
            row = _normalise_row(raw_row)
            summary.rows_seen += 1
            record_date = _row_date(row=row, row_number=row_number)
            account = _account_for_row(
                tenant=tenant,
                row=row,
                fallback_account_id=fallback_account_id,
                row_number=row_number,
            )
            summary.accounts_seen.add(account.external_id or account.account_id)

            metric_values = _metric_values(row=row, row_number=row_number)
            if not metric_values:
                summary.rows_skipped_no_metrics += 1
                continue

            if dry_run:
                campaign, campaign_created, campaign_updated = _campaign_for_row_dry_run(
                    tenant=tenant,
                    account=account,
                    row=row,
                    fallback_currency=fallback_currency,
                )
            else:
                campaign, campaign_created, campaign_updated = _campaign_for_row(
                    tenant=tenant,
                    account=account,
                    row=row,
                    fallback_currency=fallback_currency,
                    imported_at=imported_at,
                )
            if campaign is not None:
                summary.campaigns_seen.add(campaign.external_id)
                if campaign_created:
                    summary.campaigns_created += 1
                elif campaign_updated:
                    summary.campaigns_updated += 1

            external_id = _record_external_id(
                row=row,
                account=account,
                campaign=campaign,
                record_date=record_date,
                row_number=row_number,
            )
            level = _record_level(row=row, default_level=default_level)
            if dry_run:
                exists = RawPerformanceRecord.all_objects.filter(
                    tenant=tenant,
                    source=RECORD_SOURCE,
                    external_id=external_id,
                    date=record_date,
                    level=level,
                ).exists()
                if exists:
                    summary.records_updated += 1
                else:
                    summary.records_created += 1
                continue

            _, created = RawPerformanceRecord.all_objects.update_or_create(
                tenant=tenant,
                source=RECORD_SOURCE,
                external_id=external_id,
                date=record_date,
                level=level,
                defaults={
                    "ad_account": account,
                    "campaign": campaign,
                    "currency": _row_currency(
                        row=row,
                        account=account,
                        fallback_currency=fallback_currency,
                    ),
                    "raw_payload": _manual_raw_payload(
                        row=row,
                        imported_at=imported_at,
                    ),
                    **metric_values,
                },
            )
            if created:
                summary.records_created += 1
            else:
                summary.records_updated += 1
    return summary


def _normalise_row(row: Mapping[str, Any]) -> dict[str, str]:
    normalised: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalised[_normalise_key(str(key))] = (
            "" if value is None else str(value).strip()
        )
    return normalised


def _normalise_key(value: str) -> str:
    cleaned = value.strip().lower().lstrip("\ufeff")
    return re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")


def _row_date(*, row: Mapping[str, str], row_number: int) -> date:
    raw_date = str(
        row.get("date") or row.get("date_start") or row.get("day") or ""
    ).strip()
    parsed_date = parse_date(raw_date) if raw_date else None
    if parsed_date is None:
        raise CommandError(f"Row {row_number}: date or date_start is required.")
    raw_stop = str(row.get("date_stop") or "").strip()
    parsed_stop = parse_date(raw_stop) if raw_stop else None
    if parsed_stop is not None and parsed_stop != parsed_date:
        raise CommandError(
            f"Row {row_number}: date_start/date_stop must be daily rows, not a multi-day aggregate."
        )
    return parsed_date


def _account_for_row(
    *,
    tenant: Tenant,
    row: Mapping[str, str],
    fallback_account_id: str,
    row_number: int,
) -> AdAccount:
    account_id = str(
        row.get("account_id") or row.get("ad_account_id") or fallback_account_id or ""
    ).strip()
    if not account_id:
        raise CommandError(f"Row {row_number}: account_id is required.")
    account = (
        AdAccount.all_objects.filter(
            tenant=tenant, external_id__in=_account_aliases(account_id)
        ).first()
        or AdAccount.all_objects.filter(
            tenant=tenant, account_id__in=_account_aliases(account_id)
        ).first()
    )
    if account is None:
        raise CommandError(
            f"Row {row_number}: AdAccount {account_id!r} was not found for this tenant."
        )
    return account


def _campaign_for_row(
    *,
    tenant: Tenant,
    account: AdAccount,
    row: Mapping[str, str],
    fallback_currency: str,
    imported_at: datetime,
) -> tuple[Campaign | None, bool, bool]:
    campaign_id = str(row.get("campaign_id") or "").strip()
    campaign_name = str(row.get("campaign_name") or row.get("campaign") or "").strip()
    if not campaign_id and not campaign_name:
        return None, False, False
    if not campaign_id:
        campaign_id = f"manual-{_normalise_key(campaign_name)}"
    campaign, created = Campaign.all_objects.get_or_create(
        tenant=tenant,
        external_id=campaign_id,
        defaults={
            "ad_account": account,
            "name": campaign_name or campaign_id,
            "platform": "meta",
            "account_external_id": account.external_id,
            "currency": _row_currency(
                row=row,
                account=account,
                fallback_currency=fallback_currency,
            ),
            "metadata": _manual_raw_payload(row=row, imported_at=imported_at),
        },
    )
    changed_fields: list[str] = []
    if not created:
        if campaign.ad_account_id != account.id:
            campaign.ad_account = account
            changed_fields.append("ad_account")
        if campaign_name and campaign.name != campaign_name:
            campaign.name = campaign_name
            changed_fields.append("name")
        if campaign.account_external_id != account.external_id:
            campaign.account_external_id = account.external_id
            changed_fields.append("account_external_id")
        currency = _row_currency(
            row=row,
            account=account,
            fallback_currency=fallback_currency,
        )
        if currency and campaign.currency != currency:
            campaign.currency = currency
            changed_fields.append("currency")
        if changed_fields:
            changed_fields.append("updated_at")
            campaign.save(update_fields=changed_fields)
    return campaign, created, bool(changed_fields)


def _campaign_for_row_dry_run(
    *,
    tenant: Tenant,
    account: AdAccount,
    row: Mapping[str, str],
    fallback_currency: str,
) -> tuple[Campaign | None, bool, bool]:
    campaign_id = str(row.get("campaign_id") or "").strip()
    campaign_name = str(row.get("campaign_name") or row.get("campaign") or "").strip()
    if not campaign_id and not campaign_name:
        return None, False, False
    if not campaign_id:
        campaign_id = f"manual-{_normalise_key(campaign_name)}"
    campaign = Campaign.all_objects.filter(
        tenant=tenant,
        external_id=campaign_id,
    ).first()
    if campaign is None:
        return (
            Campaign(
                tenant=tenant,
                ad_account=account,
                external_id=campaign_id,
                name=campaign_name or campaign_id,
                platform="meta",
                account_external_id=account.external_id,
                currency=_row_currency(
                    row=row,
                    account=account,
                    fallback_currency=fallback_currency,
                ),
            ),
            True,
            False,
        )
    return (
        campaign,
        False,
        _campaign_would_update(
            campaign=campaign,
            account=account,
            row=row,
            fallback_currency=fallback_currency,
        ),
    )


def _campaign_would_update(
    *,
    campaign: Campaign,
    account: AdAccount,
    row: Mapping[str, str],
    fallback_currency: str,
) -> bool:
    campaign_name = str(row.get("campaign_name") or row.get("campaign") or "").strip()
    currency = _row_currency(
        row=row,
        account=account,
        fallback_currency=fallback_currency,
    )
    return any(
        [
            campaign.ad_account_id != account.id,
            bool(campaign_name and campaign.name != campaign_name),
            campaign.account_external_id != account.external_id,
            bool(currency and campaign.currency != currency),
        ]
    )


def _metric_values(*, row: Mapping[str, str], row_number: int) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for column, model_field in COUNT_METRIC_COLUMNS.items():
        parsed = _parse_count_metric(
            value=row.get(column, ""), row_number=row_number, column=column
        )
        if parsed is not None:
            values[model_field] = parsed
    for column, model_field in DECIMAL_METRIC_COLUMNS.items():
        parsed_decimal = _parse_decimal_metric(
            value=row.get(column, ""), row_number=row_number, column=column
        )
        if parsed_decimal is not None:
            values[model_field] = parsed_decimal
    if "cpc" not in values and values.get("clicks") and values.get("spend") is not None:
        values["cpc"] = values["spend"] / Decimal(values["clicks"])
    if (
        "cpm" not in values
        and values.get("impressions")
        and values.get("spend") is not None
    ):
        values["cpm"] = (values["spend"] / Decimal(values["impressions"])) * Decimal(
            "1000"
        )
    return values


def _parse_count_metric(*, value: str, row_number: int, column: str) -> int | None:
    parsed = _parse_decimal_metric(value=value, row_number=row_number, column=column)
    if parsed is None:
        return None
    if parsed != parsed.to_integral_value():
        raise CommandError(
            f"Row {row_number}: metric {column!r} must be a whole number."
        )
    return int(parsed)


def _parse_decimal_metric(
    *, value: str, row_number: int, column: str
) -> Decimal | None:
    stripped = str(value or "").strip()
    if not stripped:
        return None
    normalised = stripped.replace(",", "")
    try:
        parsed = Decimal(normalised)
    except (InvalidOperation, ValueError) as exc:
        raise CommandError(
            f"Row {row_number}: metric {column!r} must be numeric."
        ) from exc
    if not parsed.is_finite():
        raise CommandError(f"Row {row_number}: metric {column!r} must be numeric.")
    if parsed < 0:
        raise CommandError(f"Row {row_number}: metric {column!r} cannot be negative.")
    return parsed


def _record_external_id(
    *,
    row: Mapping[str, str],
    account: AdAccount,
    campaign: Campaign | None,
    record_date: date,
    row_number: int,
) -> str:
    provided = str(row.get("external_id") or row.get("record_id") or "").strip()
    if provided:
        return f"manual-paid:{provided}"[:128]
    identity = [
        account.external_id or account.account_id,
        str(row.get("level") or "campaign"),
        campaign.external_id if campaign is not None else "no-campaign",
        record_date.isoformat(),
        str(row_number),
    ]
    return ":".join(["manual-paid", *identity])[:128]


def _record_level(*, row: Mapping[str, str], default_level: str) -> str:
    value = str(row.get("level") or default_level or "campaign").strip().lower()
    return value[:16] or "campaign"


def _row_currency(
    *, row: Mapping[str, str], account: AdAccount, fallback_currency: str
) -> str:
    return str(
        row.get("currency") or account.currency or fallback_currency or ""
    ).strip()


def _manual_raw_payload(
    *, row: Mapping[str, str], imported_at: datetime
) -> dict[str, Any]:
    metric_columns = sorted(
        column
        for column in row
        if column not in STANDARD_COLUMNS and row.get(column) not in {"", None}
    )
    return {
        "source": MANUAL_IMPORT_SOURCE,
        "imported_at": imported_at.isoformat(),
        "metric_columns": metric_columns,
    }


def _account_aliases(account_id: str) -> set[str]:
    value = str(account_id or "").strip()
    if not value:
        return set()
    aliases = {value}
    if value.startswith("act_") and value[4:]:
        aliases.add(value[4:])
    elif value.isdigit():
        aliases.add(f"act_{value}")
    return aliases
