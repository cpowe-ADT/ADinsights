from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.views import APIView

from integrations.meta_graph import MetaGraphClient, MetaGraphClientError, MetaGraphConfigurationError
from integrations.meta_page_serializers import (
    MetaOAuthCallbackSerializer,
    MetaOverviewQuerySerializer,
    MetaPageResponseSerializer,
    MetaPostTimeseriesQuerySerializer,
    MetaPostsItemSerializer,
    MetaPostsQuerySerializer,
    MetaRefreshSerializer,
    MetaTimeseriesPointSerializer,
    MetaTimeseriesQuerySerializer,
    resolve_date_range,
)
from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.services.metric_registry import (
    get_default_metric_keys,
    resolve_metric_key,
)
from integrations.tasks import sync_meta_page_insights, sync_meta_post_insights
from integrations.tasks import (
    discover_supported_metrics,
    sync_page_insights,
    sync_page_posts,
    sync_post_insights,
)
from integrations.views import (
    META_OAUTH_FLOW_MARKETING,
    META_OAUTH_FLOW_PAGE_INSIGHTS,
    _meta_redirect_uri,
    _validate_meta_state,
)

logger = logging.getLogger(__name__)

REQUIRED_INSIGHTS_SCOPES = {"pages_read_engagement", "read_insights"}
PAGE_INSIGHTS_TASK_FALLBACK = {"ANALYZE", "MANAGE", "ADVERTISE"}
PAGE_INSIGHTS_PERMISSION_FALLBACK = {"ADMINISTER", "BASIC_ADMIN", "CREATE_ADS"}


def _missing_insights_scopes(scopes: list[str]) -> list[str]:
    granted = {scope.strip() for scope in scopes if isinstance(scope, str) and scope.strip()}
    return sorted(REQUIRED_INSIGHTS_SCOPES - granted)


def _has_page_insights_capability(*, tasks: list[str] | None, perms: list[str] | None) -> bool:
    task_set = {task.strip().upper() for task in (tasks or []) if isinstance(task, str) and task.strip()}
    if task_set.intersection(PAGE_INSIGHTS_TASK_FALLBACK):
        return True

    perm_set = {perm.strip().upper() for perm in (perms or []) if isinstance(perm, str) and perm.strip()}
    if perm_set.intersection(PAGE_INSIGHTS_PERMISSION_FALLBACK):
        return True

    return not task_set and not perm_set


def _as_aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            candidate = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return candidate if candidate.tzinfo else candidate.replace(tzinfo=dt_timezone.utc)
    return None


def _latest_connection_for_tenant(*, tenant_id: str) -> MetaConnection | None:
    return MetaConnection.objects.filter(tenant_id=tenant_id, is_active=True).order_by("-updated_at").first()


class MetaOAuthCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="IntegrationsMetaOAuthCallback")

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        serializer = MetaOAuthCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return self._complete_callback(
            request=request,
            code=serializer.validated_data["code"],
            state=serializer.validated_data["state"],
            callback_payload=serializer.validated_data,
        )

    def post(self, request, *args, **kwargs):  # noqa: ANN001
        serializer = MetaOAuthCallbackSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        return self._complete_callback(
            request=request,
            code=serializer.validated_data["code"],
            state=serializer.validated_data["state"],
            callback_payload=serializer.validated_data,
        )

    def _complete_callback(
        self,
        *,
        request,
        code: str,
        state: str,
        callback_payload=None,  # noqa: ANN001
    ) -> Response:
        payload, error_response = _validate_meta_state(
            request=request,
            state=state,
        )
        if error_response is not None:
            return error_response
        path = (getattr(request, "path", "") or "").rstrip("/")
        if path.endswith("/api/meta/connect/callback"):
            flow = str(payload.get("flow") or META_OAUTH_FLOW_MARKETING)
            if flow != META_OAUTH_FLOW_PAGE_INSIGHTS:
                return Response(
                    {
                        "detail": "OAuth state belongs to the marketing flow. Use /api/integrations/meta/oauth/exchange/.",
                        "code": "wrong_oauth_flow",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            redirect_uri = _meta_redirect_uri(request=request, payload=callback_payload)
            with MetaGraphClient.from_settings() as client:
                exchanged = client.exchange_code(
                    code=code,
                    redirect_uri=redirect_uri,
                )
                try:
                    long_lived = client.exchange_for_long_lived_user_token(
                        short_lived_user_token=exchanged.access_token
                    )
                except MetaGraphClientError:
                    long_lived = exchanged
                debug_token = client.debug_token(input_token=long_lived.access_token)
                if not bool(debug_token.get("is_valid")):
                    return Response(
                        {"detail": "Meta OAuth token failed debug_token validation."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                configured_app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
                debug_app_id_raw = debug_token.get("app_id")
                debug_app_id = str(debug_app_id_raw).strip() if debug_app_id_raw is not None else ""
                if configured_app_id and debug_app_id and debug_app_id != configured_app_id:
                    return Response(
                        {"detail": "Meta OAuth token app_id did not match META_APP_ID."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                permissions_payload = client.list_permissions(user_access_token=long_lived.access_token)
                pages = client.list_pages(user_access_token=long_lived.access_token)
        except MetaGraphConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MetaGraphClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        granted_permissions = sorted(
            {
                permission["permission"]
                for permission in permissions_payload
                if permission.get("status") == "granted"
            }
        )
        declined_permissions = sorted(
            {
                permission["permission"]
                for permission in permissions_payload
                if permission.get("status") == "declined"
            }
        )
        missing_required_permissions = _missing_insights_scopes(granted_permissions)

        now = timezone.now()
        expires_at = None
        if long_lived.expires_in is not None and long_lived.expires_in > 0:
            expires_at = now + timedelta(seconds=long_lived.expires_in)

        app_scoped_user_id = str(debug_token.get("user_id") or payload.get("user_id") or "").strip()
        if not app_scoped_user_id:
            app_scoped_user_id = str(request.user.id)

        with transaction.atomic():
            MetaConnection.objects.filter(tenant=request.user.tenant, is_active=True).update(is_active=False)
            connection, _ = MetaConnection.objects.select_for_update().get_or_create(
                tenant=request.user.tenant,
                user=request.user,
                app_scoped_user_id=app_scoped_user_id,
                defaults={
                    "token_expires_at": expires_at,
                    "scopes": granted_permissions,
                    "is_active": True,
                },
            )
            connection.token_expires_at = expires_at
            connection.scopes = granted_permissions
            connection.is_active = True
            connection.set_raw_token(long_lived.access_token)
            connection.save()

            default_page_exists = MetaPage.objects.filter(
                tenant=request.user.tenant,
                is_default=True,
            ).exists()
            saved_pages: list[MetaPage] = []
            for index, page in enumerate(pages):
                token = (page.access_token or "").strip()
                if not token:
                    continue
                tasks = [task for task in (page.tasks or []) if isinstance(task, str)]
                perms = [perm for perm in (page.perms or []) if isinstance(perm, str)]
                can_analyze = _has_page_insights_capability(tasks=tasks, perms=perms)

                meta_page, _ = MetaPage.objects.select_for_update().get_or_create(
                    tenant=request.user.tenant,
                    page_id=page.id,
                    defaults={
                        "connection": connection,
                        "name": page.name,
                        "page_token_expires_at": expires_at,
                        "can_analyze": can_analyze,
                        "tasks": tasks,
                        "perms": perms,
                        "is_default": (not default_page_exists and index == 0),
                    },
                )
                meta_page.connection = connection
                meta_page.name = page.name
                meta_page.page_token_expires_at = expires_at
                meta_page.can_analyze = can_analyze
                meta_page.tasks = tasks
                meta_page.perms = perms
                if not default_page_exists and index == 0:
                    meta_page.is_default = True
                meta_page.set_raw_page_token(token)
                meta_page.save()
                saved_pages.append(meta_page)

        default_page = next((page for page in saved_pages if page.is_default), saved_pages[0] if saved_pages else None)
        task_ids: dict[str, str] = {}
        if default_page is not None and default_page.can_analyze:
            try:
                page_posts_task = sync_page_posts.delay(page_id=default_page.page_id, mode="incremental")
                discover_task = discover_supported_metrics.delay(page_id=default_page.page_id)
                page_insights_task = sync_page_insights.delay(page_id=default_page.page_id, mode="incremental")
                post_insights_task = sync_post_insights.delay(page_id=default_page.page_id, mode="incremental")
                task_ids = {
                    "sync_page_posts": page_posts_task.id,
                    "discover_supported_metrics": discover_task.id,
                    "sync_page_insights": page_insights_task.id,
                    "sync_post_insights": post_insights_task.id,
                }
            except Exception as exc:  # pragma: no cover - async infra dependent
                logger.warning(
                    "meta.page_connect.bootstrap_tasks_failed",
                    extra={
                        "tenant_id": str(request.user.tenant_id),
                        "page_id": default_page.page_id,
                        "error": str(exc),
                    },
                )

        return Response(
            {
                "connection_id": str(connection.id),
                "token_debug_valid": bool(debug_token.get("is_valid")),
                "granted_permissions": granted_permissions,
                "declined_permissions": declined_permissions,
                "missing_required_permissions": missing_required_permissions,
                "oauth_connected_but_missing_permissions": bool(missing_required_permissions),
                "pages": MetaPageResponseSerializer(saved_pages, many=True).data,
                "default_page_id": default_page.page_id if default_page is not None else None,
                "tasks": task_ids,
            },
            status=status.HTTP_200_OK,
        )


class MetaPagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="IntegrationsMetaPages")

    def get(self, request, *args, **kwargs):  # noqa: ANN001
        pages = list(
            MetaPage.objects.filter(tenant=request.user.tenant).order_by("-is_default", "name")
        )
        connection = _latest_connection_for_tenant(tenant_id=str(request.user.tenant_id))
        missing_required_permissions = (
            _missing_insights_scopes(connection.scopes) if connection is not None else sorted(REQUIRED_INSIGHTS_SCOPES)
        )
        return Response(
            {
                "pages": MetaPageResponseSerializer(pages, many=True).data,
                "missing_required_permissions": missing_required_permissions,
            }
        )


class MetaPageSelectView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="IntegrationsMetaPageSelect")

    def post(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        connection = _latest_connection_for_tenant(tenant_id=str(request.user.tenant_id))
        if connection is None:
            return Response(
                {"detail": "Meta OAuth connection not found. Connect Meta first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing_required_permissions = _missing_insights_scopes(connection.scopes)
        if missing_required_permissions:
            return Response(
                {
                    "detail": "Meta OAuth is missing required permissions for Page Insights.",
                    "missing_required_permissions": missing_required_permissions,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        with transaction.atomic():
            MetaPage.objects.filter(tenant=request.user.tenant, is_default=True).exclude(pk=page.pk).update(
                is_default=False
            )
            page.is_default = True
            page.save(update_fields=["is_default", "updated_at"])

        return Response(
            {
                "page_id": page.page_id,
                "selected": True,
            },
            status=status.HTTP_200_OK,
        )


class MetaPageRefreshView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetricsMetaPageRefresh")

    def post(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        serializer = MetaRefreshSerializer(data=request.data or {})
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

        connection = _latest_connection_for_tenant(tenant_id=str(request.user.tenant_id))
        missing_required_permissions = (
            _missing_insights_scopes(connection.scopes) if connection is not None else sorted(REQUIRED_INSIGHTS_SCOPES)
        )
        if missing_required_permissions:
            return Response(
                {
                    "detail": "Meta OAuth is missing required permissions for Page Insights.",
                    "missing_required_permissions": missing_required_permissions,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = serializer.validated_data.get("mode", "incremental")
        metrics = serializer.validated_data.get("metrics")

        page_task = sync_meta_page_insights.delay(page_pk=str(page.pk), mode=mode, metrics=metrics)
        post_task = sync_meta_post_insights.delay(page_pk=str(page.pk), mode=mode, metrics=metrics)

        return Response(
            {
                "page_task_id": page_task.id,
                "post_task_id": post_task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class MetaPageOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetricsMetaPageOverview")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = MetaOverviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        date_preset = query.validated_data.get("date_preset", "last_28d")
        since, until = resolve_date_range(
            preset=date_preset,
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )

        default_keys = get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE)
        cards: list[dict[str, Any]] = []
        for metric_key in default_keys:
            display_metric_key = metric_key
            resolved_key = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, metric_key)
            metric = MetaMetricRegistry.objects.filter(
                level=MetaMetricRegistry.LEVEL_PAGE,
                metric_key=metric_key,
            ).first()
            replacement = (metric.replacement_metric_key if metric else "") or ""
            status_value = metric.status if metric else MetaMetricRegistry.STATUS_UNKNOWN

            queryset = MetaInsightPoint.objects.filter(
                tenant=request.user.tenant,
                page=page,
                metric_key=resolved_key,
                period="day",
                end_time__date__gte=since,
                end_time__date__lte=until,
            )
            range_value = queryset.aggregate(total=Sum("value_num")).get("total")
            today_value = queryset.filter(end_time__date=until).aggregate(total=Sum("value_num")).get("total")
            cards.append(
                {
                    "metric_key": metric_key,
                    "display_metric_key": display_metric_key,
                    "status": status_value,
                    "replacement_metric_key": replacement,
                    "value_today": today_value,
                    "value_range": range_value,
                }
            )

        metric_options = list(
            MetaMetricRegistry.objects.filter(level=MetaMetricRegistry.LEVEL_PAGE)
            .order_by("metric_key")
            .values(
                "metric_key",
                "level",
                "status",
                "replacement_metric_key",
                "title",
                "description",
            )
        )

        return Response(
            {
                "page_id": page.page_id,
                "date_preset": date_preset,
                "since": since,
                "until": until,
                "cards": cards,
                "metrics": metric_options,
            }
        )


class MetaPageTimeseriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetricsMetaPageTimeseries")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = MetaTimeseriesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        requested_metric = query.validated_data["metric"]
        metric_key = resolve_metric_key(MetaMetricRegistry.LEVEL_PAGE, requested_metric)
        period = query.validated_data.get("period") or "day"
        since, until = resolve_date_range(
            preset="last_28d",
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )

        rows = (
            MetaInsightPoint.objects.filter(
                tenant=request.user.tenant,
                page=page,
                metric_key=metric_key,
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
                "end_time": row["end_time"],
                "value": row["value"],
            }
            for row in rows
        ]

        return Response(
            {
                "page_id": page.page_id,
                "metric": requested_metric,
                "resolved_metric": metric_key,
                "period": period,
                "since": since,
                "until": until,
                "points": MetaTimeseriesPointSerializer(points, many=True).data,
            }
        )


class MetaPagePostsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetricsMetaPagePosts")

    def get(self, request, page_id: str, *args, **kwargs):  # noqa: ANN001
        query = MetaPostsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        page = MetaPage.objects.filter(tenant=request.user.tenant, page_id=page_id).first()
        if page is None:
            return Response({"detail": "Page not found."}, status=status.HTTP_404_NOT_FOUND)

        since, until = resolve_date_range(
            preset="last_28d",
            since=query.validated_data.get("since"),
            until=query.validated_data.get("until"),
        )
        limit = int(query.validated_data.get("limit") or 100)

        posts = list(
            MetaPost.objects.filter(
                tenant=request.user.tenant,
                page=page,
                created_time__date__gte=since,
                created_time__date__lte=until,
            )
            .order_by("-created_time")[:limit]
        )

        default_metrics = get_default_metric_keys(MetaMetricRegistry.LEVEL_POST)
        metric_map: dict[str, dict[str, Decimal | None]] = {}
        for point in (
            MetaPostInsightPoint.objects.filter(
                tenant=request.user.tenant,
                post__in=posts,
                metric_key__in=default_metrics,
            )
            .order_by("post_id", "metric_key", "-end_time")
            .values("post_id", "metric_key", "value_num", "end_time")
        ):
            post_pk = str(point["post_id"])
            post_metrics = metric_map.setdefault(post_pk, {})
            metric_key = str(point["metric_key"])
            if metric_key in post_metrics:
                continue
            post_metrics[metric_key] = point["value_num"]

        items = [
            {
                "post_id": post.post_id,
                "created_time": post.created_time,
                "permalink_url": post.permalink_url,
                "message": post.message,
                "metrics": metric_map.get(str(post.pk), {}),
            }
            for post in posts
        ]

        return Response(
            {
                "page_id": page.page_id,
                "since": since,
                "until": until,
                "results": MetaPostsItemSerializer(items, many=True).data,
            }
        )


class MetaPostTimeseriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = AutoSchema(operation_id_base="MetricsMetaPostTimeseries")

    def get(self, request, post_id: str, *args, **kwargs):  # noqa: ANN001
        query = MetaPostTimeseriesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        post = MetaPost.objects.filter(tenant=request.user.tenant, post_id=post_id).first()
        if post is None:
            return Response({"detail": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        requested_metric = query.validated_data["metric"]
        metric_key = resolve_metric_key(MetaMetricRegistry.LEVEL_POST, requested_metric)
        period = query.validated_data.get("period") or "lifetime"

        since = query.validated_data.get("since")
        until = query.validated_data.get("until")
        filters: dict[str, Any] = {
            "tenant": request.user.tenant,
            "post": post,
            "metric_key": metric_key,
            "period": period,
        }
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
                "end_time": row["end_time"],
                "value": row["value"],
            }
            for row in rows
        ]

        return Response(
            {
                "post_id": post.post_id,
                "page_id": post.page.page_id,
                "metric": requested_metric,
                "resolved_metric": metric_key,
                "period": period,
                "points": MetaTimeseriesPointSerializer(points, many=True).data,
            }
        )
