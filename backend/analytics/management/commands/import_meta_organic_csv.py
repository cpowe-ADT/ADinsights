"""Import operator-supplied Meta organic CSV metrics into stored reporting rows."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from accounts.audit import log_audit_event
from accounts.models import Tenant
from accounts.tenant_context import tenant_context
from integrations.models import (
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.services.metric_registry import get_reporting_metric_source_map


COMMAND_SCHEMA_VERSION = "meta_organic_csv_import.v1"
MANUAL_IMPORT_SOURCE = "manual_meta_organic_csv"
STANDARD_COLUMNS = {
    "date",
    "end_date",
    "end_time",
    "level",
    "page_id",
    "page_name",
    "post_id",
    "post_message",
    "message",
    "content",
    "permalink",
    "permalink_url",
    "created_time",
    "period",
}
MANUAL_PRODUCT_SOURCE_OVERRIDES = {
    ("page", "page_follows"): "page_follows",
    ("post", "post_reactions"): "post_reactions_total",
    ("post", "post_comments"): "post_comments_total",
    ("post", "post_shares"): "post_shares_total",
}


@dataclass
class ImportSummary:
    rows_seen: int = 0
    rows_skipped_no_metrics: int = 0
    pages_seen: set[str] = field(default_factory=set)
    posts_seen: set[str] = field(default_factory=set)
    page_points_created: int = 0
    page_points_updated: int = 0
    post_points_created: int = 0
    post_points_updated: int = 0
    posts_created: int = 0
    posts_updated: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_seen": self.rows_seen,
            "rows_skipped_no_metrics": self.rows_skipped_no_metrics,
            "page_count": len(self.pages_seen),
            "post_count": len(self.posts_seen),
            "page_points_created": self.page_points_created,
            "page_points_updated": self.page_points_updated,
            "post_points_created": self.post_points_created,
            "post_points_updated": self.post_points_updated,
            "posts_created": self.posts_created,
            "posts_updated": self.posts_updated,
        }


class Command(BaseCommand):
    help = (
        "Import a tenant-scoped Meta organic CSV export into MetaInsightPoint and "
        "MetaPostInsightPoint rows without calling live Meta APIs."
    )

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument("--tenant-id", required=True, help="Target tenant UUID.")
        parser.add_argument(
            "--file", required=True, help="Path to the Meta organic CSV file."
        )
        parser.add_argument(
            "--page-id",
            default="",
            help="Fallback Facebook Page ID when the CSV does not include a page_id column.",
        )
        parser.add_argument(
            "--default-page-period",
            default="day",
            help="Period stored for page-level rows when the CSV does not include period.",
        )
        parser.add_argument(
            "--default-post-period",
            default="lifetime",
            help="Period stored for post-level rows when the CSV does not include period.",
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

        page_metric_columns = _metric_column_map(MetaMetricRegistry.LEVEL_PAGE)
        post_metric_columns = _metric_column_map(MetaMetricRegistry.LEVEL_POST)
        imported_at = timezone.now()

        with tenant_context(str(tenant.id)), transaction.atomic():
            summary = _import_rows(
                tenant=tenant,
                path=path,
                fallback_page_id=str(options.get("page_id") or "").strip(),
                default_page_period=str(options["default_page_period"] or "day").strip()
                or "day",
                default_post_period=str(
                    options["default_post_period"] or "lifetime"
                ).strip()
                or "lifetime",
                imported_at=imported_at,
                page_metric_columns=page_metric_columns,
                post_metric_columns=post_metric_columns,
                dry_run=bool(options.get("dry_run")),
            )
            if not options.get("dry_run"):
                log_audit_event(
                    tenant=tenant,
                    user=None,
                    action="meta_organic_csv_imported",
                    resource_type="meta_page",
                    resource_id=",".join(sorted(summary.pages_seen)) or "none",
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
    fallback_page_id: str,
    default_page_period: str,
    default_post_period: str,
    imported_at: datetime,
    page_metric_columns: Mapping[str, str],
    post_metric_columns: Mapping[str, str],
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
            end_time = _row_end_time(row=row, row_number=row_number)
            page_id = str(row.get("page_id") or fallback_page_id).strip()
            if not page_id:
                raise CommandError(f"Row {row_number}: page_id is required.")
            page = _page_for_row(tenant=tenant, page_id=page_id, row_number=row_number)
            summary.pages_seen.add(page.page_id)

            imported_metrics = 0
            imported_metrics += _import_page_metrics(
                tenant=tenant,
                page=page,
                row=row,
                row_number=row_number,
                end_time=end_time,
                period=str(row.get("period") or default_page_period),
                imported_at=imported_at,
                metric_columns=page_metric_columns,
                summary=summary,
                dry_run=dry_run,
            )

            post_id = str(row.get("post_id") or "").strip()
            if post_id:
                if dry_run:
                    post = MetaPost.all_objects.filter(
                        tenant=tenant, page=page, post_id=post_id
                    ).first()
                    summary.posts_seen.add(post_id)
                    if post is None:
                        summary.posts_created += 1
                    elif _post_would_update(post=post, row=row, end_time=end_time):
                        summary.posts_updated += 1
                else:
                    post, was_created = _post_for_row(
                        tenant=tenant,
                        page=page,
                        post_id=post_id,
                        row=row,
                        end_time=end_time,
                    )
                    summary.posts_seen.add(post.post_id)
                    if was_created:
                        summary.posts_created += 1
                    elif _update_post_from_row(post=post, row=row, end_time=end_time):
                        summary.posts_updated += 1
                imported_metrics += _import_post_metrics(
                    tenant=tenant,
                    post=post,
                    row=row,
                    row_number=row_number,
                    end_time=end_time,
                    period=str(row.get("period") or default_post_period),
                    imported_at=imported_at,
                    metric_columns=post_metric_columns,
                    summary=summary,
                    dry_run=dry_run,
                )

            if imported_metrics == 0:
                summary.rows_skipped_no_metrics += 1
    return summary


def _metric_column_map(level: str) -> dict[str, str]:
    result: dict[str, str] = {}
    source_map = get_reporting_metric_source_map("organic_facebook_page", level=level)
    for product_metric, source_keys in source_map.items():
        result[_normalise_key(product_metric)] = product_metric
        for candidate in source_keys:
            result.setdefault(_normalise_key(candidate), candidate)
    for (
        metric_level,
        product_metric,
    ), source_key in MANUAL_PRODUCT_SOURCE_OVERRIDES.items():
        if metric_level == (
            "post" if level == MetaMetricRegistry.LEVEL_POST else "page"
        ):
            result.setdefault(_normalise_key(source_key), source_key)
            result.setdefault(_normalise_key(product_metric), product_metric)
    return result


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


def _row_end_time(*, row: Mapping[str, str], row_number: int) -> datetime:
    raw_datetime = str(row.get("end_time") or row.get("created_time") or "").strip()
    if raw_datetime:
        parsed_datetime = parse_datetime(raw_datetime)
        if parsed_datetime is None:
            raise CommandError(
                f"Row {row_number}: invalid end_time/created_time value."
            )
        if timezone.is_naive(parsed_datetime):
            return timezone.make_aware(parsed_datetime, dt_timezone.utc)
        return parsed_datetime

    raw_date = str(row.get("date") or row.get("end_date") or "").strip()
    parsed_date = parse_date(raw_date) if raw_date else None
    if parsed_date is None:
        raise CommandError(f"Row {row_number}: date or end_time is required.")
    return datetime.combine(parsed_date, time(hour=12), tzinfo=dt_timezone.utc)


def _page_for_row(*, tenant: Tenant, page_id: str, row_number: int) -> MetaPage:
    page = MetaPage.all_objects.filter(tenant=tenant, page_id=page_id).first()
    if page is None:
        raise CommandError(
            f"Row {row_number}: MetaPage {page_id!r} was not found for this tenant."
        )
    return page


def _post_for_row(
    *,
    tenant: Tenant,
    page: MetaPage,
    post_id: str,
    row: Mapping[str, str],
    end_time: datetime,
) -> tuple[MetaPost, bool]:
    message = str(
        row.get("post_message") or row.get("message") or row.get("content") or ""
    ).strip()
    permalink = str(row.get("permalink_url") or row.get("permalink") or "").strip()
    return MetaPost.all_objects.get_or_create(
        tenant=tenant,
        page=page,
        post_id=post_id,
        defaults={
            "message": message,
            "permalink_url": permalink,
            "created_time": end_time,
            "last_synced_at": timezone.now(),
            "metadata": {"source": MANUAL_IMPORT_SOURCE},
        },
    )


def _update_post_from_row(
    *, post: MetaPost, row: Mapping[str, str], end_time: datetime
) -> bool:
    changed_fields: list[str] = []
    message = str(
        row.get("post_message") or row.get("message") or row.get("content") or ""
    ).strip()
    permalink = str(row.get("permalink_url") or row.get("permalink") or "").strip()
    if message and post.message != message:
        post.message = message
        changed_fields.append("message")
    if permalink and post.permalink_url != permalink:
        post.permalink_url = permalink
        changed_fields.append("permalink_url")
    if post.created_time is None:
        post.created_time = end_time
        changed_fields.append("created_time")
    if changed_fields:
        changed_fields.append("updated_at")
        post.save(update_fields=changed_fields)
        return True
    return False


def _post_would_update(
    *, post: MetaPost, row: Mapping[str, str], end_time: datetime
) -> bool:
    message = str(
        row.get("post_message") or row.get("message") or row.get("content") or ""
    ).strip()
    permalink = str(row.get("permalink_url") or row.get("permalink") or "").strip()
    return any(
        [
            bool(message and post.message != message),
            bool(permalink and post.permalink_url != permalink),
            post.created_time is None and end_time is not None,
        ]
    )


def _import_page_metrics(
    *,
    tenant: Tenant,
    page: MetaPage,
    row: Mapping[str, str],
    row_number: int,
    end_time: datetime,
    period: str,
    imported_at: datetime,
    metric_columns: Mapping[str, str],
    summary: ImportSummary,
    dry_run: bool = False,
) -> int:
    imported = 0
    for column, value in row.items():
        if column in STANDARD_COLUMNS or column not in metric_columns:
            continue
        parsed_value = _parse_metric_value(
            value=value, row_number=row_number, column=column
        )
        if parsed_value is None:
            continue
        if dry_run:
            exists = MetaInsightPoint.all_objects.filter(
                tenant=tenant,
                page=page,
                metric_key=metric_columns[column],
                period=period,
                end_time=end_time,
                breakdown_key_normalized="",
            ).exists()
            if exists:
                summary.page_points_updated += 1
            else:
                summary.page_points_created += 1
            imported += 1
            continue
        _, created = MetaInsightPoint.all_objects.update_or_create(
            tenant=tenant,
            page=page,
            metric_key=metric_columns[column],
            period=period,
            end_time=end_time,
            breakdown_key_normalized="",
            defaults={
                "value_num": parsed_value,
                "value_json": _manual_value_metadata(imported_at),
                "breakdown_key": None,
                "breakdown_json": None,
            },
        )
        if created:
            summary.page_points_created += 1
        else:
            summary.page_points_updated += 1
        imported += 1
    return imported


def _import_post_metrics(
    *,
    tenant: Tenant,
    post: MetaPost | None,
    row: Mapping[str, str],
    row_number: int,
    end_time: datetime,
    period: str,
    imported_at: datetime,
    metric_columns: Mapping[str, str],
    summary: ImportSummary,
    dry_run: bool = False,
) -> int:
    imported = 0
    for column, value in row.items():
        if column in STANDARD_COLUMNS or column not in metric_columns:
            continue
        parsed_value = _parse_metric_value(
            value=value, row_number=row_number, column=column
        )
        if parsed_value is None:
            continue
        if dry_run:
            exists = (
                post is not None
                and MetaPostInsightPoint.all_objects.filter(
                    tenant=tenant,
                    post=post,
                    metric_key=metric_columns[column],
                    period=period,
                    end_time=end_time,
                    breakdown_key_normalized="",
                ).exists()
            )
            if exists:
                summary.post_points_updated += 1
            else:
                summary.post_points_created += 1
            imported += 1
            continue
        _, created = MetaPostInsightPoint.all_objects.update_or_create(
            tenant=tenant,
            post=post,
            metric_key=metric_columns[column],
            period=period,
            end_time=end_time,
            breakdown_key_normalized="",
            defaults={
                "value_num": parsed_value,
                "value_json": _manual_value_metadata(imported_at),
                "breakdown_key": None,
                "breakdown_json": None,
            },
        )
        if created:
            summary.post_points_created += 1
        else:
            summary.post_points_updated += 1
        imported += 1
    return imported


def _parse_metric_value(*, value: str, row_number: int, column: str) -> Decimal | None:
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


def _manual_value_metadata(imported_at: datetime) -> dict[str, str]:
    return {
        "source": MANUAL_IMPORT_SOURCE,
        "imported_at": imported_at.isoformat(),
    }
