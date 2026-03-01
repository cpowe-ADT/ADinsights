from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
import logging
from typing import Any

from django.db.models import DecimalField, F, Max, OuterRef, Q, Subquery, Sum
from django.db.models.expressions import OrderBy
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from analytics.models import ReportDefinition, ReportExportJob
from analytics.phase2_serializers import ReportExportJobSerializer
from core.db_error_responses import schema_out_of_date_response
from integrations.meta_page_insights.metric_pack_loader import is_blocked_metric
from integrations.meta_page_views import MetaOAuthCallbackView
from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaMetricSupportStatus,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.page_insights_serializers import (
    DateRangeQuerySerializer,
    MetaPageExportCreateSerializer,
    MetricTimeseriesQuerySerializer,
    PageTimeseriesQuerySerializer,
    SyncTriggerSerializer,
    resolve_date_range,
)
from integrations.services.metric_registry import get_default_metric_keys, resolve_metric_key
from integrations.tasks import (
    discover_supported_metrics,
    sync_page_insights,
    sync_page_posts,
    sync_post_insights,
)
from integrations.views import MetaOAuthStartView

logger = logging.getLogger(__name__)
REQUIRED_INSIGHTS_SCOPES = {"pages_read_engagement", "read_insights"}


def _schema_response(request, exc: Exception, endpoint: str) -> Response | None:
    return schema_out_of_date_response(
        exc=exc,
        logger=logger,
        endpoint=endpoint,
        tenant_id=getattr(request.user, "tenant_id", None),
    )


class MetaConnectStartAliasView(MetaOAuthStartView):
    schema = AutoSchema(operation_id_base="MetaConnectStartAlias")


class MetaConnectCallbackAliasView(MetaOAuthCallbackView):
    schema = AutoSchema(operation_id_base="MetaConnectCallbackAlias")


class MetaPagesInsightsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPagesInsightsList")

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_pages.list")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, *args, **kwargs):  # noqa: ANN001
        pages = list(
            MetaPage.objects.filter(tenant=request.user.tenant).order_by("-is_default", "name")
        )
        payload = [
            {
                "id": str(page.pk),
                "page_id": page.page_id,
                "name": page.name,
                "category": page.category,
                "can_analyze": page.can_analyze,
                "is_default": page.is_default,
                "last_synced_at": _to_iso(page.last_synced_at),
                "last_posts_synced_at": _to_iso(page.last_posts_synced_at),
            }
            for page in pages
        ]
        return Response({"results": payload, "count": len(payload)})


class MetaPageInsightsSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPageInsightsSync")

    def post(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._post(request, page_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_pages.sync")
            if schema_response is not None:
                return schema_response
            raise

    def _post(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        serializer = SyncTriggerSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)
        if not page.can_analyze:
            return Response(
                {
                    "detail": (
                        "Selected page is not eligible: page must provide ANALYZE task "
                        "or admin capability required for Page Insights."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        missing_required_permissions = _missing_required_scopes_for_page(page)
        if missing_required_permissions:
            return Response(
                {
                    "detail": "Meta OAuth is missing required permissions for Page Insights.",
                    "missing_required_permissions": missing_required_permissions,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = serializer.validated_data["mode"]
        posts_task = sync_page_posts.delay(page_id=page.page_id, mode=mode)
        discovery_task = discover_supported_metrics.delay(page_id=page.page_id)
        page_task = sync_page_insights.delay(page_id=page.page_id, mode=mode)
        post_task = sync_post_insights.delay(page_id=page.page_id, mode=mode)
        return Response(
            {
                "page_id": page.page_id,
                "tasks": {
                    "sync_page_posts": posts_task.id,
                    "discover_supported_metrics": discovery_task.id,
                    "sync_page_insights": page_task.id,
                    "sync_post_insights": post_task.id,
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )


class MetaPageOverviewInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPageOverviewInsights")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, page_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_pages.overview")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = DateRangeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        date_preset = query.validated_data.get("date_preset", "last_28d")
        since, until = resolve_date_range(
            date_preset=date_preset,
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )

        metric_keys = [metric for metric in get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE) if not is_blocked_metric(metric)]
        availability = _metric_availability(page=page, level=MetaMetricRegistry.LEVEL_PAGE, metric_keys=metric_keys)
        supported_metrics = [metric for metric in metric_keys if availability.get(metric, {}).get("supported")]

        kpis: list[dict[str, Any]] = []
        trends: dict[str, list[dict[str, Any]]] = {}
        for metric_key in metric_keys:
            resolved_key = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, metric_key)
            base_qs = MetaInsightPoint.objects.filter(
                tenant=request.user.tenant,
                page=page,
                metric_key=resolved_key,
                period="day",
                end_time__date__gte=since,
                end_time__date__lte=until,
            )
            range_total = base_qs.aggregate(total=Sum("value_num")).get("total")
            today_total = base_qs.filter(end_time__date=until).aggregate(total=Sum("value_num")).get("total")
            kpis.append(
                {
                    "metric": metric_key,
                    "resolved_metric": resolved_key,
                    "value": _decimal_to_number(range_total),
                    "today_value": _decimal_to_number(today_total),
                }
            )

            series_rows = (
                base_qs.values("end_time__date")
                .annotate(value=Sum("value_num"))
                .order_by("end_time__date")
            )
            trends[metric_key] = [
                {
                    "date": row["end_time__date"].isoformat() if row["end_time__date"] else None,
                    "value": _decimal_to_number(row["value"]),
                }
                for row in series_rows
            ]

        last_synced_at = page.last_synced_at or MetaInsightPoint.objects.filter(
            tenant=request.user.tenant,
            page=page,
        ).aggregate(value=Max("updated_at"))["value"]
        return Response(
            {
                "page_id": page.page_id,
                "name": page.name,
                "date_preset": date_preset,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "last_synced_at": _to_iso(last_synced_at),
                "metric_availability": availability,
                "kpis": kpis,
                "daily_series": trends,
                "primary_metric": supported_metrics[0] if supported_metrics else None,
            }
        )


class MetaPagePostsInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPagePostsInsights")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, page_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_pages.posts")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = DateRangeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        date_preset = query.validated_data.get("date_preset", "last_28d")
        since, until = resolve_date_range(
            date_preset=date_preset,
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )
        limit = int(query.validated_data.get("limit") or 50)
        offset = int(query.validated_data.get("offset") or 0)
        search = str(query.validated_data.get("q") or "").strip()
        media_type = str(query.validated_data.get("media_type") or "").strip()
        sort = str(query.validated_data.get("sort") or "created_desc").strip()
        sort_metric = str(query.validated_data.get("sort_metric") or "").strip()

        posts_qs = MetaPost.objects.filter(
            tenant=request.user.tenant,
            page=page,
            created_time__date__gte=since,
            created_time__date__lte=until,
        )
        if search:
            posts_qs = posts_qs.filter(
                Q(message__icontains=search)
                | Q(post_id__icontains=search)
            )
        if media_type:
            posts_qs = posts_qs.filter(media_type__iexact=media_type)

        if sort in {"metric_desc", "metric_asc"}:
            resolved_sort_metric = resolve_metric_key(MetaMetricRegistry.LEVEL_POST, sort_metric)
            sort_value_sq = (
                MetaPostInsightPoint.objects.filter(
                    tenant=request.user.tenant,
                    post=OuterRef("pk"),
                    metric_key=resolved_sort_metric,
                )
                .order_by("-end_time")
                .values("value_num")[:1]
            )
            posts_qs = posts_qs.annotate(
                _sort_value=Subquery(sort_value_sq, output_field=DecimalField())
            ).order_by(
                OrderBy(F("_sort_value"), descending=sort == "metric_desc", nulls_last=True),
                OrderBy(F("created_time"), descending=True, nulls_last=True),
                "pk",
            )
        elif sort == "created_asc":
            posts_qs = posts_qs.order_by("created_time", "pk")
        else:
            posts_qs = posts_qs.order_by("-created_time", "pk")

        count = posts_qs.count()
        posts = list(posts_qs[offset : offset + limit])
        metric_keys = [metric for metric in get_default_metric_keys(MetaMetricRegistry.LEVEL_POST) if not is_blocked_metric(metric)]
        availability = _metric_availability(page=page, level=MetaMetricRegistry.LEVEL_POST, metric_keys=metric_keys)

        latest_values: dict[tuple[str, str], Decimal | None] = {}
        for row in (
            MetaPostInsightPoint.objects.filter(
                tenant=request.user.tenant,
                post__in=posts,
                metric_key__in=[resolve_metric_key(MetaMetricRegistry.LEVEL_POST, metric) for metric in metric_keys],
            )
            .order_by("post_id", "metric_key", "-end_time")
            .values("post_id", "metric_key", "value_num")
        ):
            key = (str(row["post_id"]), str(row["metric_key"]))
            if key in latest_values:
                continue
            latest_values[key] = row["value_num"]

        results = []
        for post in posts:
            metrics_payload: dict[str, float | None] = {}
            for metric in metric_keys:
                resolved = resolve_metric_key(MetaMetricRegistry.LEVEL_POST, metric)
                metrics_payload[metric] = _decimal_to_number(latest_values.get((str(post.pk), resolved)))
            results.append(
                {
                    "post_id": post.post_id,
                    "page_id": post.page.page_id,
                    "created_time": _to_iso(post.created_time),
                    "permalink": post.permalink_url,
                    "media_type": post.media_type,
                    "message_snippet": (post.message or "")[:180],
                    "metrics": metrics_payload,
                    "last_synced_at": _to_iso(post.last_synced_at),
                }
            )

        last_synced_at = page.last_posts_synced_at or MetaPost.objects.filter(
            tenant=request.user.tenant,
            page=page,
        ).aggregate(value=Max("last_synced_at"))["value"]
        next_offset = offset + limit if offset + limit < count else None
        prev_offset = max(offset - limit, 0) if offset > 0 else None
        return Response(
            {
                "page_id": page.page_id,
                "date_preset": date_preset,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "last_synced_at": _to_iso(last_synced_at),
                "count": count,
                "limit": limit,
                "offset": offset,
                "next_offset": next_offset,
                "prev_offset": prev_offset,
                "metric_availability": availability,
                "results": results,
            }
        )


class MetaPostDetailInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPostDetailInsights")

    def get(self, request, post_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, post_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_posts.detail")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, post_id: str, *args, **kwargs):  # noqa: ANN001
        post = (
            MetaPost.objects.filter(tenant=request.user.tenant, post_id=post_id)
            .select_related("page")
            .first()
        )
        if post is None:
            return Response({"detail": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        metric_keys = [metric for metric in get_default_metric_keys(MetaMetricRegistry.LEVEL_POST) if not is_blocked_metric(metric)]
        availability = _metric_availability(
            page=post.page,
            level=MetaMetricRegistry.LEVEL_POST,
            metric_keys=metric_keys,
        )
        latest_rows = (
            MetaPostInsightPoint.objects.filter(
                tenant=request.user.tenant,
                post=post,
                metric_key__in=[resolve_metric_key(MetaMetricRegistry.LEVEL_POST, metric) for metric in metric_keys],
            )
            .order_by("metric_key", "-end_time")
            .values("metric_key", "value_num")
        )
        latest_values: dict[str, Decimal | None] = {}
        for row in latest_rows:
            metric_key = str(row["metric_key"])
            if metric_key in latest_values:
                continue
            latest_values[metric_key] = row["value_num"]

        metrics = {
            metric: _decimal_to_number(latest_values.get(resolve_metric_key(MetaMetricRegistry.LEVEL_POST, metric)))
            for metric in metric_keys
        }
        return Response(
            {
                "post_id": post.post_id,
                "page_id": post.page.page_id,
                "created_time": _to_iso(post.created_time),
                "permalink": post.permalink_url,
                "media_type": post.media_type,
                "message": post.message,
                "last_synced_at": _to_iso(post.last_synced_at),
                "metric_availability": availability,
                "metrics": metrics,
            }
        )


class MetaPostTimeseriesInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPostTimeseriesInsights")

    def get(self, request, post_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, post_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_posts.timeseries")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, post_id: str, *args, **kwargs):  # noqa: ANN001
        query = MetricTimeseriesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        post = (
            MetaPost.objects.filter(tenant=request.user.tenant, post_id=post_id)
            .select_related("page")
            .first()
        )
        if post is None:
            return Response({"detail": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        requested_metric = query.validated_data["metric"]
        availability = _metric_availability(
            page=post.page,
            level=MetaMetricRegistry.LEVEL_POST,
            metric_keys=[requested_metric],
        )
        if not availability.get(requested_metric, {}).get("supported"):
            return Response(
                {
                    "post_id": post.post_id,
                    "page_id": post.page.page_id,
                    "metric": requested_metric,
                    "metric_availability": availability,
                    "points": [],
                }
            )

        period = query.validated_data.get("period") or "lifetime"
        resolved_metric = resolve_metric_key(MetaMetricRegistry.LEVEL_POST, requested_metric)
        filters: dict[str, Any] = {
            "tenant": request.user.tenant,
            "post": post,
            "metric_key": resolved_metric,
            "period": period,
        }
        since = query.validated_data.get("since")
        until = query.validated_data.get("until")
        if since is not None:
            filters["end_time__date__gte"] = since
        if until is not None:
            filters["end_time__date__lte"] = until

        rows = (
            MetaPostInsightPoint.objects.filter(**filters)
            .values("end_time")
            .annotate(value=Sum("value_num"))
            .order_by("end_time")
        )
        points = [
            {
                "end_time": _to_iso(row["end_time"]),
                "value": _decimal_to_number(row["value"]),
            }
            for row in rows
        ]
        return Response(
            {
                "post_id": post.post_id,
                "page_id": post.page.page_id,
                "metric": requested_metric,
                "resolved_metric": resolved_metric,
                "period": period,
                "metric_availability": availability,
                "points": points,
            }
        )


class MetaPageTimeseriesInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPageTimeseriesInsights")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        try:
            return self._get(request, page_id, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = _schema_response(request, exc, "integrations.meta_pages.timeseries")
            if schema_response is not None:
                return schema_response
            raise

    def _get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = PageTimeseriesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        requested_metric = query.validated_data["metric"]
        availability = _metric_availability(
            page=page,
            level=MetaMetricRegistry.LEVEL_PAGE,
            metric_keys=[requested_metric],
        )
        if not availability.get(requested_metric, {}).get("supported"):
            return Response(
                {
                    "page_id": page.page_id,
                    "metric": requested_metric,
                    "metric_availability": availability,
                    "points": [],
                }
            )

        date_preset = query.validated_data.get("date_preset", "last_28d")
        since, until = resolve_date_range(
            date_preset=date_preset,
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )
        period = query.validated_data.get("period") or "day"
        resolved_metric = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, requested_metric)

        rows = (
            MetaInsightPoint.objects.filter(
                tenant=request.user.tenant,
                page=page,
                metric_key=resolved_metric,
                period=period,
                end_time__date__gte=since,
                end_time__date__lte=until,
            )
            .values("end_time")
            .annotate(value=Sum("value_num"))
            .order_by("end_time")
        )
        points = [
            {
                "end_time": _to_iso(row["end_time"]),
                "value": _decimal_to_number(row["value"]),
            }
            for row in rows
        ]
        return Response(
            {
                "page_id": page.page_id,
                "metric": requested_metric,
                "resolved_metric": resolved_metric,
                "period": period,
                "date_preset": date_preset,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "metric_availability": availability,
                "points": points,
            }
        )


class MetaMetricsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaMetricsList")

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        level = str(request.query_params.get("level") or "").strip().upper()
        if level not in {"PAGE", "POST"}:
            return Response(
                {"detail": "level must be PAGE or POST."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        include_all = str(request.query_params.get("include_all") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "t",
        }

        queryset = MetaMetricRegistry.objects.filter(level=level)
        if not include_all:
            queryset = queryset.exclude(
                status__in=[MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED]
            )

        rows = list(
            queryset.order_by("metric_key").values(
                "metric_key",
                "level",
                "supported_periods",
                "supports_breakdowns",
                "status",
                "replacement_metric_key",
                "title",
                "description",
                "is_default",
            )
        )
        rows = [row for row in rows if not is_blocked_metric(str(row.get("metric_key") or ""))]
        return Response({"results": rows, "count": len(rows)})


def _get_or_create_meta_page_export_report(*, tenant_id: str, page: MetaPage) -> ReportDefinition:
    name = f"internal:meta_pages:{page.page_id}"
    report, _ = ReportDefinition.objects.update_or_create(
        tenant_id=tenant_id,
        name=name,
        defaults={
            "description": "Internal export definition for Facebook Pages dashboard.",
            "filters": {
                "internal": True,
                "source": "meta_pages",
                "page_id": page.page_id,
            },
            "layout": {
                "template": "meta_pages_v1",
            },
            "is_active": False,
        },
    )
    return report


class MetaPageExportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetaPageExports")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)
        report = _get_or_create_meta_page_export_report(tenant_id=str(request.user.tenant_id), page=page)
        jobs = list(
            ReportExportJob.objects.filter(tenant_id=request.user.tenant_id, report=report).order_by("-created_at")[:25]
        )
        return Response(ReportExportJobSerializer(jobs, many=True).data)

    def post(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        payload = MetaPageExportCreateSerializer(data=request.data or {})
        payload.is_valid(raise_exception=True)
        request_payload: dict[str, Any] = dict(payload.validated_data)
        for key in ("since", "until"):
            value = request_payload.get(key)
            if hasattr(value, "isoformat"):
                request_payload[key] = value.isoformat()

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)
        if not page.can_analyze:
            return Response(
                {"detail": "Selected page is not eligible for insights exports."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = _get_or_create_meta_page_export_report(tenant_id=str(request.user.tenant_id), page=page)
        job = ReportExportJob.objects.create(
            tenant=request.user.tenant,
            report=report,
            requested_by=request.user,
            export_format=payload.validated_data["export_format"],
            status=ReportExportJob.STATUS_QUEUED,
            metadata={
                "redacted": True,
                "source": "meta_pages",
                "page_id": page.page_id,
                "request": request_payload,
            },
        )

        log_audit_event(
            tenant=request.user.tenant,
            user=request.user,
            action="meta_pages_export_requested",
            resource_type="report_export_job",
            resource_id=job.id,
            metadata={
                "redacted": True,
                "page_id": page.page_id,
                "export_format": job.export_format,
            },
        )

        try:
            from analytics.tasks import run_report_export_job

            run_report_export_job.delay(str(job.id))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Failed to enqueue meta pages export", exc_info=exc)
            job.status = ReportExportJob.STATUS_FAILED
            job.error_message = str(exc)
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

        return Response(ReportExportJobSerializer(job).data, status=status.HTTP_201_CREATED)


def _metric_availability(
    *,
    page: MetaPage,
    level: str,
    metric_keys: list[str],
) -> dict[str, dict[str, Any]]:
    registry = {
        row.metric_key: row
        for row in MetaMetricRegistry.objects.filter(level=level, metric_key__in=metric_keys)
    }
    support_rows = {
        row.metric_key: row
        for row in MetaMetricSupportStatus.objects.filter(page=page, level=level, metric_key__in=metric_keys)
    }

    availability: dict[str, dict[str, Any]] = {}
    for metric in metric_keys:
        status_row = registry.get(metric)
        support_row = support_rows.get(metric)
        status_value = status_row.status if status_row is not None else MetaMetricRegistry.STATUS_UNKNOWN
        supported = (
            bool(support_row.supported)
            if support_row is not None
            else status_value not in {MetaMetricRegistry.STATUS_INVALID, MetaMetricRegistry.STATUS_DEPRECATED}
            and not is_blocked_metric(metric)
        )

        reason = ""
        if not supported:
            if support_row is not None and isinstance(support_row.last_error, dict):
                reason = str(support_row.last_error.get("message") or "").strip()
            if not reason:
                reason = "Not available for this Page"

        availability[metric] = {
            "supported": supported,
            "status": status_value,
            "last_checked_at": _to_iso(support_row.last_checked_at if support_row is not None else None),
            "reason": reason,
        }
    return availability


def _missing_required_scopes_for_page(page: MetaPage) -> list[str]:
    scopes: list[str] = []
    if page.connection_id:
        connection = MetaConnection.all_objects.filter(pk=page.connection_id).first()
        if connection is not None and isinstance(connection.scopes, list):
            scopes = [str(scope).strip() for scope in connection.scopes if isinstance(scope, str)]
    if not scopes:
        latest_connection = (
            MetaConnection.all_objects.filter(tenant=page.tenant, is_active=True).order_by("-updated_at").first()
        )
        if latest_connection is not None and isinstance(latest_connection.scopes, list):
            scopes = [str(scope).strip() for scope in latest_connection.scopes if isinstance(scope, str)]
    granted = {scope for scope in scopes if scope}
    return sorted(REQUIRED_INSIGHTS_SCOPES - granted)


def _decimal_to_number(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.isoformat()
