"""Operator-only fixed-range backfill for SLB reporting evidence."""

from __future__ import annotations

from datetime import date, timedelta
import json
import uuid
from typing import Any, Iterable, Mapping

from django.core.management.base import BaseCommand, CommandError

from accounts.audit import log_audit_event
from accounts.tenant_context import tenant_context
from analytics.models import ReportDefinition
from analytics.tasks import generate_snapshots_for_tenants
from content_ops.models import (
    ContentDraft,
    ContentDraftVersion,
    ContentWorkspace,
    PublishedPost,
    PublishingIdentity,
)
from content_ops.tasks import refresh_content_published_post_metrics
from integrations.models import AirbyteConnection, MetaPage, MetaPost, PlatformCredential
from integrations.meta_page_insights.engagement_edges import ingest_engagement_edges
from integrations.tasks import (
    _candidate_page_tokens,
    sync_meta_reporting_slice,
    sync_page_insights,
    sync_page_posts,
    sync_post_insights,
)


SUPPORTED_DATASETS = {
    "paid_meta_ads",
    "organic_facebook_page",
    "organic_facebook_posts",
    "content_ops",
}
DEFAULT_DATASETS = (
    "paid_meta_ads",
    "organic_facebook_page",
    "organic_facebook_posts",
    "content_ops",
)
META_TOKEN_BLOCKING_STATUSES = {
    PlatformCredential.TOKEN_STATUS_INVALID,
    PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
}


class Command(BaseCommand):
    help = "Run tenant-scoped real sync/backfill tasks for fixed-range SLB reporting evidence."

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument("--report-id", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)
        parser.add_argument(
            "--datasets",
            default=",".join(DEFAULT_DATASETS),
            help="Comma-separated datasets: paid_meta_ads,organic_facebook_page,organic_facebook_posts,content_ops.",
        )
        parser.add_argument("--account-id", default="", help="Optional Meta ad account ID override.")
        parser.add_argument("--page-id", action="append", dest="page_ids", help="Optional Facebook Page ID. Repeatable.")
        parser.add_argument(
            "--dispatch-mode",
            choices=("queue", "inline", "dry-run"),
            default="queue",
            help="queue uses Celery, inline runs tasks in-process, dry-run reports planned work only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Alias for --dispatch-mode dry-run.",
        )
        parser.add_argument(
            "--refresh-snapshots",
            action="store_true",
            help="After inline backfill, refresh warehouse snapshots for the report tenant.",
        )
        parser.add_argument(
            "--persist-report-targets",
            action="store_true",
            help="Persist explicit --account-id/--page-id values onto ReportDefinition.filters.",
        )
        parser.add_argument(
            "--import-synced-posts-to-content-ops",
            action="store_true",
            help="Create Content Ops PublishedPost rows from already-synced MetaPost rows in the fixed range.",
        )

    def handle(self, *args: Any, **options: Any):  # noqa: ANN401
        start_date = _parse_date(options["start_date"], "start-date")
        end_date = _parse_date(options["end_date"], "end-date")
        if start_date > end_date:
            raise CommandError("start-date must be on or before end-date.")

        datasets = _parse_datasets(options["datasets"])
        dispatch_mode = "dry-run" if options.get("dry_run") else options["dispatch_mode"]
        report = (
            ReportDefinition.all_objects.select_related("tenant")
            .filter(id=options["report_id"])
            .first()
        )
        if report is None:
            raise CommandError("Report not found.")

        account_id = _first_non_empty(
            options.get("account_id"),
            _mapping_get(report.filters, "account_id"),
            _mapping_get(report.layout, "account_id"),
        )
        requested_page_ids = _clean_values(options.get("page_ids") or [])
        if not requested_page_ids:
            requested_page_ids = _clean_values(
                [
                    _mapping_get(report.filters, "page_id"),
                    _mapping_get(report.layout, "page_id"),
                ]
            )

        with tenant_context(str(report.tenant_id)):
            result = {
                "schema_version": "slb_backfill_meta_reporting.v1",
                "report": {
                    "id": str(report.id),
                    "tenant_id": str(report.tenant_id),
                    "template_key": _template_key(report),
                },
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timezone": "America/Jamaica",
                },
                "dispatch_mode": dispatch_mode,
                "datasets_requested": list(datasets),
                "guardrails": {
                    "tenant_scoped": True,
                    "aggregate_only": True,
                    "no_demo_seed_data": True,
                    "no_public_api_added": True,
                    "no_render_export_provider_calls": True,
                    "instagram_deferred": True,
                },
                "datasets": {},
                "post_backfill_commands": _post_backfill_commands(
                    report_id=str(report.id),
                    tenant_id=str(report.tenant_id),
                    start_date=start_date,
                    end_date=end_date,
                ),
            }
            persisted_targets = _persist_report_targets(
                report=report,
                account_id=account_id,
                page_ids=requested_page_ids,
                enabled=bool(options.get("persist_report_targets")),
                dispatch_mode=dispatch_mode,
            )
            if persisted_targets is not None:
                result["report_target_persistence"] = persisted_targets

            if "paid_meta_ads" in datasets:
                result["datasets"]["paid_meta_ads"] = _backfill_paid_meta_ads(
                    report=report,
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date,
                    dispatch_mode=dispatch_mode,
                )
            if "organic_facebook_page" in datasets:
                result["datasets"]["organic_facebook_page"] = _backfill_organic_facebook_page(
                    report=report,
                    page_ids=requested_page_ids,
                    start_date=start_date,
                    end_date=end_date,
                    dispatch_mode=dispatch_mode,
                )
            if "organic_facebook_posts" in datasets:
                result["datasets"]["organic_facebook_posts"] = _backfill_organic_facebook_posts(
                    report=report,
                    page_ids=requested_page_ids,
                    start_date=start_date,
                    end_date=end_date,
                    dispatch_mode=dispatch_mode,
                )
            if "content_ops" in datasets:
                result["datasets"]["content_ops"] = _refresh_content_ops(
                    report=report,
                    page_ids=requested_page_ids,
                    start_date=start_date,
                    end_date=end_date,
                    dispatch_mode=dispatch_mode,
                    import_synced_posts=bool(options.get("import_synced_posts_to_content_ops")),
                )

            if options.get("refresh_snapshots"):
                result["snapshot_refresh"] = _refresh_snapshots(
                    tenant_id=str(report.tenant_id),
                    dispatch_mode=dispatch_mode,
                )

            log_audit_event(
                tenant=report.tenant,
                user=None,
                action="slb_backfill_meta_reporting_requested",
                resource_type="report_definition",
                resource_id=report.id,
                metadata={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "datasets": list(datasets),
                    "dispatch_mode": dispatch_mode,
                    "refresh_snapshots": bool(options.get("refresh_snapshots")),
                    "redacted": True,
                },
            )

        self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))


def _backfill_paid_meta_ads(
    *,
    report: ReportDefinition,
    account_id: str,
    start_date: date,
    end_date: date,
    dispatch_mode: str,
) -> dict[str, Any]:
    credential = _select_meta_credential(tenant_id=str(report.tenant_id), account_id=account_id)
    if credential is None:
        return {
            "status": "blocked",
            "reason": "meta_ad_account_credential_missing",
            "required_action": "Reconnect Meta/Facebook and select the SLB ad account before backfill.",
        }
    if credential.token_status in META_TOKEN_BLOCKING_STATUSES:
        return {
            "status": "blocked",
            "reason": "meta_credential_reauth_required",
            "token_status": credential.token_status,
            "required_action": "Reconnect Meta/Facebook before backfill.",
        }
    if not credential.decrypt_access_token():
        return {
            "status": "blocked",
            "reason": "meta_access_token_missing",
            "required_action": "Reconnect Meta/Facebook before backfill.",
        }

    connection = (
        AirbyteConnection.all_objects.filter(
            tenant_id=report.tenant_id,
            provider=PlatformCredential.META,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    normalized_account_id = _normalize_meta_account_id(credential.account_id)
    dispatch = _dispatch_task(
        task=sync_meta_reporting_slice,
        dispatch_mode=dispatch_mode,
        kwargs={
            "tenant_id": str(report.tenant_id),
            "account_id": normalized_account_id,
            "job_id": str(uuid.uuid4()),
            "connection_pk": str(connection.id) if connection else None,
            "since": start_date.isoformat(),
            "until": end_date.isoformat(),
        },
    )
    return {
        "status": dispatch["status"],
        "source_path": "direct_meta_reporting_slice",
        "account_id": normalized_account_id,
        "task": dispatch,
    }


def _backfill_organic_facebook_page(
    *,
    report: ReportDefinition,
    page_ids: list[str],
    start_date: date,
    end_date: date,
    dispatch_mode: str,
) -> dict[str, Any]:
    pages = _select_meta_pages(report=report, page_ids=page_ids)
    if not pages:
        return {
            "status": "blocked",
            "reason": "facebook_page_missing_or_not_analyzable",
            "required_action": "Reconnect/select the SLB Facebook Page with Page Insights access.",
            "tasks": [],
        }
    token_block = _page_token_block(pages)
    if token_block is not None:
        return token_block
    tasks = []
    for page in pages:
        tasks.append(
            _dispatch_task(
                task=sync_page_insights,
                dispatch_mode=dispatch_mode,
                kwargs={
                    "page_id": page.page_id,
                    "mode": "backfill",
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat(),
                },
            )
        )
    return {
        "status": _status_from_tasks(tasks),
        "source_path": "meta_page_insights",
        "page_count": len(pages),
        "tasks": tasks,
    }


def _backfill_organic_facebook_posts(
    *,
    report: ReportDefinition,
    page_ids: list[str],
    start_date: date,
    end_date: date,
    dispatch_mode: str,
) -> dict[str, Any]:
    pages = _select_meta_pages(report=report, page_ids=page_ids)
    if not pages:
        return {
            "status": "blocked",
            "reason": "facebook_page_missing_or_not_analyzable",
            "required_action": "Reconnect/select the SLB Facebook Page with Page Insights access.",
            "tasks": [],
        }
    token_block = _page_token_block(pages)
    if token_block is not None:
        return token_block
    tasks = []
    for page in pages:
        tasks.append(
            _dispatch_task(
                task=sync_page_posts,
                dispatch_mode=dispatch_mode,
                kwargs={
                    "page_id": page.page_id,
                    "mode": "backfill",
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat(),
                },
            )
        )
        tasks.append(
            _dispatch_task(
                task=sync_post_insights,
                dispatch_mode=dispatch_mode,
                kwargs={
                    "page_id": page.page_id,
                    "mode": "backfill",
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat(),
                },
            )
        )
    # Edge-sourced engagement (reactions/comments/shares + page followers) via
    # pages_read_engagement — no read_insights, no faked values. Runs after post
    # discovery so MetaPost rows exist for the window. Best-effort: never fail
    # the backfill on an enrichment error.
    engagement_edges: dict[str, Any] = {}
    for page in pages:
        try:
            engagement_edges[page.page_id] = ingest_engagement_edges(
                page=page,
                tokens=_candidate_page_tokens(page),
                since=start_date,
                until=end_date,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort enrichment
            engagement_edges[page.page_id] = {"error": type(exc).__name__}
    return {
        "status": _status_from_tasks(tasks),
        "source_path": "meta_post_insights",
        "page_count": len(pages),
        "tasks": tasks,
        "engagement_edges": engagement_edges,
    }


def _refresh_content_ops(
    *,
    report: ReportDefinition,
    page_ids: list[str],
    start_date: date,
    end_date: date,
    dispatch_mode: str,
    import_synced_posts: bool,
) -> dict[str, Any]:
    import_result: dict[str, Any] | None = None
    post_ids = list(
        PublishedPost.all_objects.filter(
            tenant_id=report.tenant_id,
            channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
            published_at__date__gte=start_date,
            published_at__date__lte=end_date,
        )
        .order_by("published_at")
        .values_list("id", flat=True)
    )
    if not post_ids and import_synced_posts:
        import_result = _import_synced_meta_posts_to_content_ops(
            report=report,
            page_ids=page_ids,
            start_date=start_date,
            end_date=end_date,
            dispatch_mode=dispatch_mode,
        )
        post_ids = list(
            PublishedPost.all_objects.filter(
                tenant_id=report.tenant_id,
                channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
                published_at__date__gte=start_date,
                published_at__date__lte=end_date,
            )
            .order_by("published_at")
            .values_list("id", flat=True)
        )
    if not post_ids:
        result = {
            "status": "blocked",
            "reason": "content_ops_published_posts_missing",
            "required_action": "Confirm published Content Ops posts exist and are linked to Meta post IDs for the fixed range.",
            "tasks": [],
        }
        if import_result is not None:
            result["import"] = import_result
        return result
    tasks = [
        _dispatch_task(
            task=refresh_content_published_post_metrics,
            dispatch_mode=dispatch_mode,
            kwargs={
                "tenant_id": str(report.tenant_id),
                "published_post_id": str(post_id),
            },
        )
        for post_id in post_ids
    ]
    metric_result_counts = _content_ops_metric_result_counts(tasks)
    status = _status_from_tasks(tasks)
    reason = ""
    required_action = ""
    if status == "completed" and metric_result_counts:
        refreshed = int(metric_result_counts.get("refreshed") or 0)
        unavailable = int(metric_result_counts.get("unavailable") or 0)
        if unavailable and refreshed:
            status = "partial"
            reason = "content_ops_metric_snapshots_partially_unavailable"
            required_action = (
                "Review posts whose Meta post insight rows are unavailable before claiming "
                "complete Content Ops metrics."
            )
        elif unavailable and not refreshed:
            status = "partial"
            reason = "content_ops_activity_imported_metrics_unavailable"
            required_action = (
                "Meta returned no post insight rows; the report can show imported post activity, "
                "but aggregate post metrics remain unavailable."
            )
    result = {
        "status": status,
        "source_path": "content_ops_organic_metric_snapshots",
        "published_post_count": len(post_ids),
        "tasks": tasks,
    }
    if metric_result_counts:
        result["metric_refresh_counts"] = metric_result_counts
    if reason:
        result["reason"] = reason
    if required_action:
        result["required_action"] = required_action
    if import_result is not None:
        result["import"] = import_result
    return result


def _content_ops_metric_result_counts(tasks: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        result = task.get("result")
        if not isinstance(result, Mapping):
            continue
        status = str(result.get("status") or "").strip()
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return counts


def _persist_report_targets(
    *,
    report: ReportDefinition,
    account_id: str,
    page_ids: list[str],
    enabled: bool,
    dispatch_mode: str,
) -> dict[str, Any] | None:
    if not enabled:
        return None
    filters = dict(report.filters or {})
    changed_fields: list[str] = []
    if account_id:
        normalized_account_id = _normalize_meta_account_id(account_id)
        if filters.get("account_id") != normalized_account_id:
            filters["account_id"] = normalized_account_id
            changed_fields.append("account_id")
    if page_ids:
        page_id = page_ids[0]
        if filters.get("page_id") != page_id:
            filters["page_id"] = page_id
            changed_fields.append("page_id")
    if dispatch_mode == "dry-run":
        return {
            "status": "planned" if changed_fields else "unchanged",
            "fields": changed_fields,
            "account_id": filters.get("account_id") or "",
            "page_id": filters.get("page_id") or "",
        }
    if changed_fields:
        report.filters = filters
        report.save(update_fields=["filters", "updated_at"])
    return {
        "status": "persisted" if changed_fields else "unchanged",
        "fields": changed_fields,
        "account_id": filters.get("account_id") or "",
        "page_id": filters.get("page_id") or "",
    }


def _import_synced_meta_posts_to_content_ops(
    *,
    report: ReportDefinition,
    page_ids: list[str],
    start_date: date,
    end_date: date,
    dispatch_mode: str,
) -> dict[str, Any]:
    pages = _select_meta_pages(report=report, page_ids=page_ids)
    if not pages:
        return {
            "status": "blocked",
            "reason": "facebook_page_missing_or_not_analyzable",
            "imported_count": 0,
        }
    if dispatch_mode == "dry-run":
        count = MetaPost.all_objects.filter(
            tenant_id=report.tenant_id,
            page__in=pages,
            created_time__date__gte=start_date,
            created_time__date__lte=end_date,
        ).count()
        return {
            "status": "planned",
            "source_path": "synced_meta_posts",
            "candidate_post_count": count,
            "imported_count": 0,
        }

    workspace, _ = ContentWorkspace.all_objects.get_or_create(
        tenant=report.tenant,
        name="SLB imported Facebook posts",
        defaults={
            "objective": "Imported from synced Facebook Page posts for aggregate reporting.",
            "target_channels": [ContentWorkspace.CHANNEL_FACEBOOK_PAGE],
            "timezone": "America/Jamaica",
        },
    )
    imported_count = 0
    skipped_existing = 0
    for page in pages:
        identity, _ = PublishingIdentity.all_objects.get_or_create(
            tenant=report.tenant,
            platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
            meta_page_id=page.page_id,
            ig_user_id="",
            defaults={
                "display_name": page.name,
                "selection_state": PublishingIdentity.SELECTION_SELECTED,
                "publish_readiness_state": PublishingIdentity.READINESS_READY,
            },
        )
        posts = MetaPost.all_objects.filter(
            tenant=report.tenant,
            page=page,
            created_time__date__gte=start_date,
            created_time__date__lte=end_date,
        ).order_by("created_time", "post_id")
        for meta_post in posts:
            exists = PublishedPost.all_objects.filter(
                tenant=report.tenant,
                channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
                meta_post_id=meta_post.post_id,
            ).exists()
            if exists:
                skipped_existing += 1
                continue
            title = _imported_post_title(meta_post)
            draft = ContentDraft.all_objects.create(
                tenant=report.tenant,
                workspace=workspace,
                title=title,
                state=ContentDraft.STATE_PUBLISHED,
            )
            version = ContentDraftVersion.all_objects.create(
                tenant=report.tenant,
                draft=draft,
                version_number=1,
                caption=meta_post.message or "",
                change_note="Imported from synced Facebook Page post for reporting.",
            )
            draft.active_version = version
            draft.save(update_fields=["active_version", "updated_at"])
            PublishedPost.all_objects.create(
                tenant=report.tenant,
                workspace=workspace,
                draft=draft,
                version=version,
                publishing_identity=identity,
                channel=PublishedPost.CHANNEL_FACEBOOK_PAGE,
                meta_post_id=meta_post.post_id,
                permalink=meta_post.permalink_url or "",
                published_at=meta_post.created_time or report.updated_at,
                reporting_link_state=PublishedPost.REPORTING_PENDING,
            )
            imported_count += 1
    return {
        "status": "completed",
        "source_path": "synced_meta_posts",
        "page_count": len(pages),
        "imported_count": imported_count,
        "skipped_existing_count": skipped_existing,
    }


def _imported_post_title(meta_post: MetaPost) -> str:
    if meta_post.message:
        return meta_post.message.replace("\n", " ")[:80]
    if meta_post.created_time:
        return f"Imported Facebook post {meta_post.created_time.date().isoformat()}"
    return f"Imported Facebook post {meta_post.post_id[-12:]}"


def _refresh_snapshots(*, tenant_id: str, dispatch_mode: str) -> dict[str, Any]:
    if dispatch_mode == "dry-run":
        return {
            "status": "planned",
            "command": f"backend/manage.py snapshot_metrics --tenant-id {tenant_id}",
        }
    if dispatch_mode != "inline":
        return {
            "status": "deferred",
            "reason": "snapshot_refresh_requires_completed_backfill_tasks",
            "command": f"backend/manage.py snapshot_metrics --tenant-id {tenant_id}",
        }
    outcomes = generate_snapshots_for_tenants([tenant_id])
    return {
        "status": "completed",
        "outcomes": [
            {
                "tenant_id": str(outcome.tenant_id),
                "status": outcome.status,
                "generated_at": outcome.generated_at.isoformat(),
            }
            for outcome in outcomes
        ],
    }


def _dispatch_task(*, task, dispatch_mode: str, kwargs: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN001
    safe_kwargs = dict(kwargs)
    if dispatch_mode == "dry-run":
        return {
            "status": "planned",
            "task_name": task.name,
            "kwargs": safe_kwargs,
        }
    if dispatch_mode == "inline":
        result = task.run(**kwargs)
        return {
            "status": "completed",
            "task_name": task.name,
            "kwargs": safe_kwargs,
            "result": result,
        }
    apply_kwargs: dict[str, Any] = {"kwargs": kwargs}
    if kwargs.get("job_id"):
        apply_kwargs["task_id"] = kwargs["job_id"]
    task_result = task.apply_async(**apply_kwargs)
    return {
        "status": "queued",
        "task_name": task.name,
        "kwargs": safe_kwargs,
        "task_id": str(getattr(task_result, "id", "") or ""),
    }


def _select_meta_credential(*, tenant_id: str, account_id: str) -> PlatformCredential | None:
    queryset = PlatformCredential.all_objects.filter(
        tenant_id=tenant_id,
        provider=PlatformCredential.META,
    )
    if account_id:
        normalized = _normalize_meta_account_id(account_id)
        numeric = normalized[4:] if normalized.startswith("act_") else normalized
        queryset = queryset.filter(account_id__in=sorted({account_id, normalized, numeric}))
    return queryset.order_by("-updated_at").first()


def _select_meta_pages(*, report: ReportDefinition, page_ids: list[str]) -> list[MetaPage]:
    queryset = MetaPage.all_objects.filter(
        tenant_id=report.tenant_id,
        can_analyze=True,
    ).select_related("tenant")
    if page_ids:
        queryset = queryset.filter(page_id__in=page_ids)
    else:
        default_page = queryset.filter(is_default=True).order_by("name").first()
        if default_page is not None:
            return [default_page]
    return list(queryset.order_by("-is_default", "name"))


def _page_token_block(pages: list[MetaPage]) -> dict[str, Any] | None:
    missing_count = 0
    unreadable_count = 0
    for page in pages:
        try:
            token = page.decrypt_page_token()
        except Exception:
            unreadable_count += 1
            continue
        if not (isinstance(token, str) and token.strip()):
            missing_count += 1
    if not missing_count and not unreadable_count:
        return None
    return {
        "status": "blocked",
        "reason": "facebook_page_auth_reconnect_required",
        "required_action": "Reconnect/select the SLB Facebook Page before Page Insights or post backfill.",
        "page_count": len(pages),
        "missing_page_auth_count": missing_count,
        "unreadable_page_auth_count": unreadable_count,
        "tasks": [],
    }


def _status_from_tasks(tasks: list[Mapping[str, Any]]) -> str:
    statuses = {str(task.get("status") or "") for task in tasks}
    if "completed" in statuses and len(statuses) == 1:
        return "completed"
    if "queued" in statuses and statuses <= {"queued"}:
        return "queued"
    if "planned" in statuses and statuses <= {"planned"}:
        return "planned"
    return "partial"


def _post_backfill_commands(*, report_id: str, tenant_id: str, start_date: date, end_date: date) -> dict[str, str]:
    history_start_date = end_date - timedelta(days=89)
    return {
        "history_probe": (
            "backend/manage.py slb_report_history_probe "
            f"--report-id {report_id} "
            f"--primary-start-date {start_date.isoformat()} "
            f"--primary-end-date {end_date.isoformat()} "
            f"--history-start-date {history_start_date.isoformat()} "
            f"--history-end-date {end_date.isoformat()}"
        ),
        "evidence_bundle": (
            "backend/manage.py slb_report_evidence_bundle "
            f"--report-id {report_id} "
            f"--start-date {start_date.isoformat()} "
            f"--end-date {end_date.isoformat()}"
        ),
        "snapshot_refresh": f"backend/manage.py snapshot_metrics --tenant-id {tenant_id}",
    }


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"{label} must be YYYY-MM-DD.") from exc


def _parse_datasets(value: str) -> tuple[str, ...]:
    datasets = tuple(_clean_values(value.split(",")))
    unknown = sorted(set(datasets) - SUPPORTED_DATASETS)
    if unknown:
        raise CommandError(f"Unsupported dataset(s): {', '.join(unknown)}.")
    if not datasets:
        raise CommandError("At least one dataset is required.")
    return datasets


def _clean_values(values: Iterable[object]) -> list[str]:
    cleaned = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            cleaned.append(normalized)
    return cleaned


def _first_non_empty(*values: object) -> str:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _mapping_get(value: object, key: str) -> str:
    if not isinstance(value, Mapping):
        return ""
    candidate = value.get(key)
    return str(candidate).strip() if candidate is not None else ""


def _template_key(report: ReportDefinition) -> str:
    layout = report.layout if isinstance(report.layout, Mapping) else {}
    filters = report.filters if isinstance(report.filters, Mapping) else {}
    return _first_non_empty(layout.get("template_key"), filters.get("template_key"))


def _normalize_meta_account_id(account_id: str) -> str:
    value = str(account_id or "").strip()
    if not value:
        return value
    if value.startswith("act_"):
        return value
    if value.isdigit():
        return f"act_{value}"
    return value
