"""API viewsets for the Content Operations module."""

from __future__ import annotations

from typing import Any

import mimetypes

from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_audit_event

from .assets import (
    ContentOpsAssetStorageError,
    asset_has_public_fetch_approval,
    asset_file_path,
    public_media_asset_proof,
    store_uploaded_asset,
)
from .exports import (
    ContentOpsExportArtifactError,
    create_content_plan_export_artifact,
    resolve_content_export_artifact_path,
)
from .generation import CaptionGenerationQuotaError, create_caption_generation_job
from .image_generation import (
    ImageGenerationQuotaError,
    create_image_generation_job,
)
from .metrics import refresh_published_post_metrics
from .models import (
    ApprovalDecision,
    ApprovalRequest,
    ContentBrief,
    ContentDraft,
    ContentDraftVersion,
    ContentExportArtifact,
    ContentSchedule,
    ContentWorkspace,
    GenerationJob,
    MediaAsset,
    OrganicPostMetricSnapshot,
    PublishedPost,
    PublishingIdentity,
    PublishAttempt,
    RegionalAgentProfile,
)
from .permissions import (
    CONTENT_OPS_ADMIN_ROLES,
    CONTENT_OPS_CLIENT_APPROVER_ROLES,
    CONTENT_OPS_EDIT_ROLES,
    CONTENT_OPS_INTERNAL_APPROVER_ROLES,
    CONTENT_OPS_PUBLISH_ROLES,
    ContentOpsPermission,
    _user_has_any_role,
)
from .publisher import (
    PREFLIGHT_ATTEMPT_MISSING,
    PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
    requeue_failed_publish_attempt,
)
from .readiness import build_content_ops_readiness_payload
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    CaptionGenerateRequestSerializer,
    ContentBriefSerializer,
    ContentDraftSerializer,
    ContentDraftVersionSerializer,
    ContentExportArtifactSerializer,
    ContentScheduleSerializer,
    ContentWorkspaceSerializer,
    GenerationJobSerializer,
    ImageGenerateRequestSerializer,
    MediaAssetSerializer,
    OrganicPostMetricSnapshotSerializer,
    PublishedPostSerializer,
    PublishingIdentitySerializer,
    PublishAttemptSerializer,
    RegionalAgentProfileSerializer,
)


class ContentOpsTenantScopedMixin:
    """Shared tenant scoping and create/update hooks for Content Ops APIs."""

    permission_classes = [ContentOpsPermission]

    def get_content_ops_required_roles(self) -> set[str]:
        action = getattr(self, "action", "")
        if action in {"destroy"}:
            return CONTENT_OPS_ADMIN_ROLES
        if action in {"schedule", "unschedule", "publish_now", "retry", "refresh_metrics"}:
            return CONTENT_OPS_PUBLISH_ROLES
        if action == "decisions":
            return CONTENT_OPS_INTERNAL_APPROVER_ROLES | CONTENT_OPS_CLIENT_APPROVER_ROLES
        return CONTENT_OPS_EDIT_ROLES

    def _tenant(self):
        tenant = getattr(self.request.user, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Unable to resolve tenant.")
        return tenant

    def _tenant_id(self) -> str:
        tenant_id = getattr(self.request.user, "tenant_id", None)
        if tenant_id is None:
            raise PermissionDenied("Unable to resolve tenant.")
        return str(tenant_id)

    def get_queryset(self) -> QuerySet[Any]:  # type: ignore[override]
        queryset = super().get_queryset()
        return queryset.filter(tenant_id=self._tenant_id())

    def perform_create(self, serializer):  # noqa: D401 - DRF signature
        kwargs: dict[str, Any] = {"tenant": self._tenant()}
        user_fields = {
            "created_by",
            "requested_by",
            "decided_by",
            "scheduled_by",
            "owner",
        }
        model_fields = {field.name for field in serializer.Meta.model._meta.fields}
        for field_name in user_fields.intersection(model_fields):
            if field_name == "owner" and serializer.Meta.model is not ContentDraft:
                continue
            kwargs[field_name] = self.request.user
        serializer.save(**kwargs)

    def _audit(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        log_audit_event(
            tenant=self._tenant(),
            user=self.request.user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            request=self.request,
        )

    def _require_roles(self, roles: set[str], message: str) -> None:
        if not _user_has_any_role(self.request.user, roles):
            raise PermissionDenied(message)


class ContentOpsReadinessView(APIView):
    """Expose separated Content Ops readiness axes."""

    permission_classes = [ContentOpsPermission]

    def get(self, request: Request) -> Response:  # noqa: D401 - DRF API
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Unable to resolve tenant.")
        return Response(build_content_ops_readiness_payload(tenant=tenant))


class ContentOpsReportOverviewView(APIView):
    """Aggregate-only reporting summary for Content Operations."""

    permission_classes = [ContentOpsPermission]

    def get(self, request: Request) -> Response:  # noqa: D401 - DRF API
        tenant_id = _request_tenant_id(request)
        workspace_id = request.query_params.get("workspace_id") or None
        start_date, end_date = _date_range_from_request(request)

        drafts = ContentDraft.all_objects.filter(tenant_id=tenant_id)
        schedules = ContentSchedule.all_objects.filter(tenant_id=tenant_id)
        attempts = PublishAttempt.all_objects.filter(tenant_id=tenant_id)
        posts = PublishedPost.all_objects.filter(tenant_id=tenant_id)
        metrics = OrganicPostMetricSnapshot.all_objects.filter(tenant_id=tenant_id)

        if workspace_id:
            _require_workspace(tenant_id=tenant_id, workspace_id=workspace_id)
            drafts = drafts.filter(workspace_id=workspace_id)
            schedules = schedules.filter(draft__workspace_id=workspace_id)
            attempts = attempts.filter(draft__workspace_id=workspace_id)
            posts = posts.filter(workspace_id=workspace_id)
            metrics = metrics.filter(published_post__workspace_id=workspace_id)
        if start_date:
            schedules = schedules.filter(scheduled_at__date__gte=start_date)
            posts = posts.filter(published_at__date__gte=start_date)
            metrics = metrics.filter(metric_date__gte=start_date)
        if end_date:
            schedules = schedules.filter(scheduled_at__date__lte=end_date)
            posts = posts.filter(published_at__date__lte=end_date)
            metrics = metrics.filter(metric_date__lte=end_date)

        return Response(
            {
                "workspace_id": workspace_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "drafts_by_state": _counts_by(drafts, "state"),
                "schedules_by_state": _counts_by(schedules, "state"),
                "publish_attempts_by_state": _counts_by(attempts, "state"),
                "published_posts_by_channel": _counts_by(posts, "channel"),
                "metric_totals": _metric_totals(metrics),
            }
        )


class ContentOpsReportPostsView(APIView):
    """Aggregate-only post report linked to Content Operations published posts."""

    permission_classes = [ContentOpsPermission]

    def get(self, request: Request) -> Response:  # noqa: D401 - DRF API
        tenant_id = _request_tenant_id(request)
        workspace_id = request.query_params.get("workspace_id") or None
        channel = request.query_params.get("channel") or None
        start_date, end_date = _date_range_from_request(request)

        posts = PublishedPost.all_objects.filter(tenant_id=tenant_id).select_related(
            "workspace", "draft", "version", "publishing_identity"
        )
        if workspace_id:
            _require_workspace(tenant_id=tenant_id, workspace_id=workspace_id)
            posts = posts.filter(workspace_id=workspace_id)
        if channel:
            posts = posts.filter(channel=channel)
        if start_date:
            posts = posts.filter(published_at__date__gte=start_date)
        if end_date:
            posts = posts.filter(published_at__date__lte=end_date)

        results = []
        for post in posts.order_by("-published_at"):
            metrics = OrganicPostMetricSnapshot.all_objects.filter(
                tenant_id=tenant_id,
                published_post=post,
            )
            if start_date:
                metrics = metrics.filter(metric_date__gte=start_date)
            if end_date:
                metrics = metrics.filter(metric_date__lte=end_date)
            results.append(
                {
                    "id": str(post.id),
                    "workspace_id": str(post.workspace_id),
                    "draft_id": str(post.draft_id),
                    "version_id": str(post.version_id),
                    "channel": post.channel,
                    "meta_post_id": post.meta_post_id,
                    "permalink": post.permalink,
                    "published_at": post.published_at.isoformat(),
                    "reporting_link_state": post.reporting_link_state,
                    "metrics": _metric_totals(metrics),
                }
            )

        return Response({"count": len(results), "results": results})


class ContentOpsContentPlanExportView(APIView):
    """Return a client-safe content plan snapshot for approval/export."""

    permission_classes = [ContentOpsPermission]

    def post(self, request: Request) -> Response:  # noqa: D401 - DRF API
        tenant_id = _request_tenant_id(request)
        tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Unable to resolve tenant.")
        workspace_id = request.data.get("workspace_id")
        if not workspace_id:
            raise ValidationError({"workspace_id": "This field is required."})
        workspace = _require_workspace(tenant_id=tenant_id, workspace_id=str(workspace_id))
        include_states = request.data.get("states") or []
        if not isinstance(include_states, list):
            raise ValidationError({"states": "Expected a list of draft states."})
        payload = _content_plan_payload(
            tenant_id=tenant_id,
            workspace=workspace,
            states=[str(state) for state in include_states],
        )
        log_audit_event(
            tenant=tenant,
            user=request.user,
            action="content_plan_exported",
            resource_type="content_workspace",
            resource_id=str(workspace.id),
            metadata={
                "item_count": payload["item_count"],
                "states": include_states,
                "format": "json",
            },
            request=request,
        )
        return Response(
            payload,
            status=status.HTTP_201_CREATED,
        )


class ContentExportArtifactViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ContentExportArtifact.all_objects.select_related("workspace", "requested_by")
        .order_by("-created_at")
    )
    serializer_class = ContentExportArtifactSerializer

    def get_queryset(self) -> QuerySet[ContentExportArtifact]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        status_filter = self.request.query_params.get("status")
        export_type = self.request.query_params.get("export_type")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if export_type:
            queryset = queryset.filter(export_type=export_type)
        return queryset

    def create(self, request: Request, *args, **kwargs) -> Response:
        tenant = self._tenant()
        workspace_id = request.data.get("workspace_id") or request.data.get("workspace")
        if not workspace_id:
            raise ValidationError({"workspace_id": "This field is required."})
        export_type = str(
            request.data.get("export_type") or ContentExportArtifact.TYPE_CONTENT_PLAN
        )
        export_format = str(
            request.data.get("export_format")
            or request.data.get("format")
            or ContentExportArtifact.FORMAT_JSON
        )
        if export_type != ContentExportArtifact.TYPE_CONTENT_PLAN:
            raise ValidationError({"export_type": "Only content_plan exports are supported."})
        if export_format != ContentExportArtifact.FORMAT_JSON:
            raise ValidationError({"export_format": "Only json exports are supported."})

        states = request.data.get("states") or []
        if not isinstance(states, list):
            raise ValidationError({"states": "Expected a list of draft states."})
        normalized_states = [str(state) for state in states]
        workspace = _require_workspace(
            tenant_id=self._tenant_id(),
            workspace_id=str(workspace_id),
        )
        payload = _content_plan_payload(
            tenant_id=self._tenant_id(),
            workspace=workspace,
            states=normalized_states,
        )
        artifact = create_content_plan_export_artifact(
            tenant=tenant,
            workspace=workspace,
            payload=payload,
            requested_by=request.user,
            states=normalized_states,
        )
        self._audit(
            action="content_export_artifact_created",
            resource_type="content_export_artifact",
            resource_id=str(artifact.id),
            metadata={
                "workspace_id": str(workspace.id),
                "export_type": artifact.export_type,
                "export_format": artifact.export_format,
                "item_count": artifact.item_count,
                "states": normalized_states,
            },
        )
        serializer = self.get_serializer(artifact)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> FileResponse | Response:
        artifact = self.get_object()
        if artifact.status != ContentExportArtifact.STATUS_COMPLETED:
            return Response(
                {
                    "detail": "Export artifact is not complete.",
                    "reason": "export_artifact_not_complete",
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            file_path = resolve_content_export_artifact_path(artifact.artifact_path)
        except ContentOpsExportArtifactError as exc:
            reason = _safe_export_artifact_error_reason(str(exc))
            response_status = (
                status.HTTP_404_NOT_FOUND
                if reason == "export_artifact_missing"
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            return Response(
                {"detail": _export_artifact_error_detail(reason), "reason": reason},
                status=response_status,
            )
        response = FileResponse(file_path.open("rb"), content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="content-plan-{artifact.id}.json"'
        )
        return response


class ContentWorkspaceViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = ContentWorkspace.all_objects.all().order_by("name", "created_at")
    serializer_class = ContentWorkspaceSerializer

    def get_serializer_class(self):  # noqa: D401 - DRF schema/action hook
        if getattr(self, "action", "") == "generate_images":
            return ImageGenerateRequestSerializer
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet[ContentWorkspace]:  # type: ignore[override]
        queryset = super().get_queryset()
        archived = self.request.query_params.get("archived")
        client_id = self.request.query_params.get("client_id")
        if archived == "false":
            queryset = queryset.filter(archived_at__isnull=True)
        elif archived == "true":
            queryset = queryset.filter(archived_at__isnull=False)
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

    @decorators.action(
        detail=True,
        methods=["post"],
        url_path="images/generate",
        url_name="images-generate",
    )
    def generate_images(self, request: Request, pk: str | None = None) -> Response:
        workspace = self.get_object()
        serializer = ImageGenerateRequestSerializer(
            data=request.data,
            context={"request": request, "workspace": workspace},
        )
        serializer.is_valid(raise_exception=True)
        try:
            job = create_image_generation_job(
                tenant=self._tenant(),
                workspace=workspace,
                user=request.user,
                prompt=serializer.validated_data["prompt"],
                count=serializer.validated_data.get("count"),
                size=serializer.validated_data.get("size", ""),
                brief=serializer.validated_data.get("brief"),
                agent=serializer.validated_data.get("regional_agent_profile"),
            )
        except ImageGenerationQuotaError as exc:
            return Response(
                {
                    "detail": exc.detail_safe,
                    "reason": exc.code,
                    "quota": exc.quota_snapshot,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._audit(
            action="content_image_generation_requested",
            resource_type="content_workspace",
            resource_id=str(workspace.id),
            metadata={
                "generation_job_id": str(job.id),
                "count": job.prompt_policy_result.get("count"),
                "provider_configured": False,
            },
        )
        return Response(
            GenerationJobSerializer(job, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RegionalAgentProfileViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = (
        RegionalAgentProfile.all_objects.select_related("workspace")
        .all()
        .order_by("name", "created_at")
    )
    serializer_class = RegionalAgentProfileSerializer

    def get_queryset(self) -> QuerySet[RegionalAgentProfile]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        region = self.request.query_params.get("region")
        is_active = self.request.query_params.get("is_active")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if region:
            queryset = queryset.filter(region=region)
        if is_active == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active == "false":
            queryset = queryset.filter(is_active=False)
        return queryset


class PublishingIdentityViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = PublishingIdentity.all_objects.all().order_by("display_name", "platform")
    serializer_class = PublishingIdentitySerializer

    def get_content_ops_required_roles(self) -> set[str]:
        action = getattr(self, "action", "")
        if action in {"create", "update", "partial_update", "destroy"}:
            return CONTENT_OPS_PUBLISH_ROLES | CONTENT_OPS_ADMIN_ROLES
        return super().get_content_ops_required_roles()

    def get_queryset(self) -> QuerySet[PublishingIdentity]:  # type: ignore[override]
        queryset = super().get_queryset()
        platform = self.request.query_params.get("platform")
        readiness = self.request.query_params.get("publish_readiness_state")
        if platform:
            queryset = queryset.filter(platform=platform)
        if readiness:
            queryset = queryset.filter(publish_readiness_state=readiness)
        return queryset


class ContentBriefViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = ContentBrief.all_objects.select_related("workspace").order_by("-created_at")
    serializer_class = ContentBriefSerializer

    def get_serializer_class(self):  # noqa: D401 - DRF schema/action hook
        if getattr(self, "action", "") == "generate_captions":
            return CaptionGenerateRequestSerializer
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet[ContentBrief]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        status_filter = self.request.query_params.get("status")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @decorators.action(
        detail=True,
        methods=["post"],
        url_path="captions/generate",
        url_name="captions-generate",
    )
    def generate_captions(self, request: Request, pk: str | None = None) -> Response:
        brief = self.get_object()
        serializer = CaptionGenerateRequestSerializer(
            data=request.data,
            context={"request": request, "workspace": brief.workspace},
        )
        serializer.is_valid(raise_exception=True)
        try:
            job = create_caption_generation_job(
                tenant=self._tenant(),
                brief=brief,
                user=request.user,
                candidate_count=serializer.validated_data["candidate_count"],
                platforms=serializer.validated_data["platforms"],
                tone_override=serializer.validated_data.get("tone_override", ""),
                agent=serializer.validated_data.get("regional_agent_profile"),
            )
        except CaptionGenerationQuotaError as exc:
            return Response(
                {
                    "detail": exc.detail_safe,
                    "reason": exc.code,
                    "quota": exc.quota_snapshot,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._audit(
            action="content_caption_generation_requested",
            resource_type="content_brief",
            resource_id=str(brief.id),
            metadata={
                "generation_job_id": str(job.id),
                "candidate_count": job.prompt_policy_result.get("candidate_count"),
                "platforms": job.prompt_policy_result.get("platforms", []),
                "provider_configured": False,
            },
        )
        return Response(
            GenerationJobSerializer(job, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class GenerationJobViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = (
        GenerationJob.all_objects.select_related("workspace", "brief")
        .all()
        .order_by("-created_at")
    )
    serializer_class = GenerationJobSerializer

    def get_queryset(self) -> QuerySet[GenerationJob]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        status_filter = self.request.query_params.get("status")
        job_type = self.request.query_params.get("job_type")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if job_type:
            queryset = queryset.filter(job_type=job_type)
        return queryset

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        job = self.get_object()
        if job.status not in {GenerationJob.STATUS_QUEUED, GenerationJob.STATUS_RUNNING}:
            raise ValidationError({"status": "Only queued or running jobs can be cancelled."})
        job.status = GenerationJob.STATUS_CANCELLED
        job.save(update_fields=["status", "updated_at"])
        self._audit(
            action="content_generation_job_cancelled",
            resource_type="content_generation_job",
            resource_id=str(job.id),
            metadata={"job_type": job.job_type},
        )
        return Response(self.get_serializer(job).data)


class MediaAssetViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = MediaAsset.all_objects.select_related("workspace").order_by("-created_at")
    serializer_class = MediaAssetSerializer

    def get_queryset(self) -> QuerySet[MediaAsset]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        status_filter = self.request.query_params.get("status")
        source = self.request.query_params.get("source")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if source:
            queryset = queryset.filter(source=source)
        return queryset

    def create(self, request: Request, *args, **kwargs) -> Response:
        return Response(
            {
                "detail": "Upload assets with /api/content-ops/assets/upload/.",
                "reason": "asset_upload_required",
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @decorators.action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request: Request) -> Response:
        workspace_id = request.data.get("workspace")
        if not workspace_id:
            raise ValidationError({"workspace": "This field is required."})
        workspace = _require_workspace(
            tenant_id=self._tenant_id(),
            workspace_id=str(workspace_id),
        )
        upload = request.FILES.get("file")
        try:
            asset = store_uploaded_asset(
                tenant=self._tenant(),
                workspace=workspace,
                upload=upload,
                alt_text=str(request.data.get("alt_text") or ""),
            )
        except ContentOpsAssetStorageError as exc:
            reason = _safe_asset_error_reason(str(exc))
            raise ValidationError(
                {"detail": _asset_error_detail(reason), "reason": reason}
            ) from exc
        self._audit(
            action="content_asset_uploaded",
            resource_type="content_media_asset",
            resource_id=str(asset.id),
            metadata={
                "workspace_id": str(workspace.id),
                "mime_type": asset.mime_type,
                "source": asset.source,
            },
        )
        return Response(
            self.get_serializer(asset).data,
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["get"], url_path="download")
    def download(self, request: Request, pk: str | None = None) -> FileResponse | Response:
        asset = self.get_object()
        if asset.status != MediaAsset.STATUS_AVAILABLE:
            return Response(
                {"detail": "Asset is not available.", "reason": "asset_not_available"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            file_path = asset_file_path(asset.storage_key)
        except ContentOpsAssetStorageError:
            return Response(
                {"detail": "Asset storage key is unsafe.", "reason": "asset_storage_key_invalid"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not file_path.exists() or file_path.stat().st_size == 0:
            return Response(
                {"detail": "Asset file was not found or is empty.", "reason": "asset_file_missing"},
                status=status.HTTP_404_NOT_FOUND,
            )
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = asset.mime_type or content_type or "application/octet-stream"
        response = FileResponse(file_path.open("rb"), content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{file_path.name}"'
        return response

    @decorators.action(detail=True, methods=["get"], url_path="public-media-proof")
    def public_media_proof(self, request: Request, pk: str | None = None) -> Response:
        asset = self.get_object()
        return Response(public_media_asset_proof(asset))


class ContentOpsPublicMediaView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    def get(self, request: Request, asset_id: str) -> FileResponse | Response:
        asset = get_object_or_404(
            MediaAsset.all_objects.filter(status=MediaAsset.STATUS_AVAILABLE),
            id=asset_id,
        )
        if not asset_has_public_fetch_approval(asset):
            return Response(
                {"detail": "Media asset is not available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            file_path = asset_file_path(asset.storage_key)
        except ContentOpsAssetStorageError:
            return Response(
                {"detail": "Media asset is not available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not file_path.exists() or file_path.stat().st_size == 0:
            return Response(
                {"detail": "Media asset is not available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        content_type, _ = mimetypes.guess_type(str(file_path))
        response = FileResponse(
            file_path.open("rb"),
            content_type=asset.mime_type or content_type or "application/octet-stream",
        )
        response["Cache-Control"] = "public, max-age=300"
        response["Content-Length"] = str(file_path.stat().st_size)
        return response


class ContentDraftViewSet(ContentOpsTenantScopedMixin, viewsets.ModelViewSet):
    queryset = (
        ContentDraft.all_objects.select_related("workspace", "brief", "active_version")
        .prefetch_related("approval_requests", "schedules")
        .order_by("-updated_at")
    )
    serializer_class = ContentDraftSerializer

    def get_serializer_class(self):  # noqa: D401 - DRF schema/action hook
        action = getattr(self, "action", "")
        if action in {"list_versions", "create_version"}:
            return ContentDraftVersionSerializer
        if action in {"submit_internal_review", "submit_client_review"}:
            return ApprovalRequestSerializer
        if action == "schedule":
            return ContentScheduleSerializer
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet[ContentDraft]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        state_filter = self.request.query_params.get("state")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if state_filter:
            queryset = queryset.filter(state=state_filter)
        return queryset

    def perform_update(self, serializer):  # noqa: D401 - DRF signature
        previous_active_version_id = serializer.instance.active_version_id
        draft = serializer.save()
        if previous_active_version_id != draft.active_version_id:
            changed_count = draft.invalidate_approvals("active_version_changed")
            self._audit(
                action="content_draft_active_version_changed",
                resource_type="content_draft",
                resource_id=str(draft.id),
                metadata={
                    "previous_active_version_id": str(previous_active_version_id)
                    if previous_active_version_id
                    else None,
                    "active_version_id": str(draft.active_version_id)
                    if draft.active_version_id
                    else None,
                    "superseded_approval_count": changed_count,
                },
            )

    @decorators.action(
        detail=True,
        methods=["get"],
        url_path="versions",
        url_name="versions-list",
    )
    def list_versions(self, request: Request, pk: str | None = None) -> Response:
        draft = self.get_object()
        queryset = ContentDraftVersion.all_objects.filter(
            tenant_id=self._tenant_id(), draft=draft
        ).order_by("version_number")
        serializer = ContentDraftVersionSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response({"results": serializer.data})

    @decorators.action(
        detail=True,
        methods=["post"],
        url_path="versions",
        url_name="versions-create",
    )
    def create_version(self, request: Request, pk: str | None = None) -> Response:
        draft = self.get_object()
        payload = request.data.copy()
        payload["draft"] = str(draft.id)
        payload.setdefault(
            "version_number",
            self._next_version_number(draft),
        )
        serializer = ContentDraftVersionSerializer(
            data=payload, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            version = serializer.save(tenant=self._tenant(), created_by=request.user)
            draft.active_version = version
            if draft.state == ContentDraft.STATE_DRAFT:
                draft.state = ContentDraft.STATE_GENERATED
            draft.save(update_fields=["active_version", "state", "updated_at"])
            superseded_count = draft.invalidate_approvals("new_version_created")
        self._audit(
            action="content_draft_version_created",
            resource_type="content_draft",
            resource_id=str(draft.id),
            metadata={
                "version_id": str(version.id),
                "version_number": version.version_number,
                "superseded_approval_count": superseded_count,
            },
        )
        return Response(
            ContentDraftVersionSerializer(version, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"], url_path="submit-internal-review")
    def submit_internal_review(self, request: Request, pk: str | None = None) -> Response:
        draft = self.get_object()
        approval = self._create_approval_request(
            draft=draft,
            reviewer_type=ApprovalRequest.REVIEWER_INTERNAL,
            next_state=ContentDraft.STATE_INTERNAL_REVIEW,
        )
        return Response(
            ApprovalRequestSerializer(approval, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"], url_path="submit-client-review")
    def submit_client_review(self, request: Request, pk: str | None = None) -> Response:
        draft = self.get_object()
        if draft.state != ContentDraft.STATE_INTERNAL_APPROVED:
            raise ValidationError(
                {"state": "Draft must be internally approved before client review."}
            )
        approval = self._create_approval_request(
            draft=draft,
            reviewer_type=ApprovalRequest.REVIEWER_CLIENT,
            next_state=ContentDraft.STATE_CLIENT_REVIEW,
        )
        return Response(
            ApprovalRequestSerializer(approval, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"])
    def schedule(self, request: Request, pk: str | None = None) -> Response:
        self._require_roles(
            CONTENT_OPS_PUBLISH_ROLES,
            "User role cannot schedule Content Operations posts.",
        )
        draft = self.get_object()
        if draft.active_version_id is None:
            raise ValidationError({"active_version": "Draft has no active version."})
        if not draft.has_current_client_approval():
            raise ValidationError(
                {
                    "approval": (
                        "Draft requires a current client approval for its active "
                        "version before it can be scheduled."
                    )
                }
            )
        payload = request.data.copy()
        payload["draft"] = str(draft.id)
        payload["version"] = str(draft.active_version_id)
        serializer = ContentScheduleSerializer(data=payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_channels = self._schedule_targets(
            draft=draft,
            raw_channels=request.data.get("channels"),
        )
        approval_snapshot = self._approval_snapshot(
            draft,
            target_channels=target_channels,
        )
        schedule = serializer.save(
            tenant=self._tenant(),
            scheduled_by=request.user,
            approval_snapshot=approval_snapshot,
        )
        draft.state = ContentDraft.STATE_SCHEDULED
        draft.save(update_fields=["state", "updated_at"])
        self._audit(
            action="content_draft_scheduled",
            resource_type="content_draft",
            resource_id=str(draft.id),
            metadata={
                "schedule_id": str(schedule.id),
                "scheduled_at": schedule.scheduled_at.isoformat(),
                "timezone": schedule.timezone,
                "target_channels": target_channels,
            },
        )
        return Response(
            ContentScheduleSerializer(schedule, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"])
    def unschedule(self, request: Request, pk: str | None = None) -> Response:
        self._require_roles(
            CONTENT_OPS_PUBLISH_ROLES,
            "User role cannot unschedule Content Operations posts.",
        )
        draft = self.get_object()
        updated = ContentSchedule.all_objects.filter(
            tenant_id=self._tenant_id(),
            draft=draft,
            state__in=[ContentSchedule.STATE_SCHEDULED, ContentSchedule.STATE_LOCKED],
        ).update(state=ContentSchedule.STATE_CANCELLED)
        if updated:
            draft.state = ContentDraft.STATE_CLIENT_APPROVED
            draft.save(update_fields=["state", "updated_at"])
        self._audit(
            action="content_draft_unscheduled",
            resource_type="content_draft",
            resource_id=str(draft.id),
            metadata={"cancelled_schedule_count": updated},
        )
        return Response({"cancelled_schedule_count": updated})

    @decorators.action(detail=True, methods=["post"], url_path="publish-now")
    def publish_now(self, request: Request, pk: str | None = None) -> Response:
        self._require_roles(
            CONTENT_OPS_PUBLISH_ROLES,
            "User role cannot publish Content Operations posts.",
        )
        self.get_object()
        return Response(
            {
                "detail": "Publishing runtime is not implemented in this slice.",
                "reason": "not_implemented",
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    def _create_approval_request(
        self,
        *,
        draft: ContentDraft,
        reviewer_type: str,
        next_state: str,
    ) -> ApprovalRequest:
        if draft.active_version_id is None:
            raise ValidationError({"active_version": "Draft has no active version."})
        approval = ApprovalRequest.all_objects.create(
            tenant=self._tenant(),
            draft=draft,
            version=draft.active_version,
            reviewer_type=reviewer_type,
            requested_by=self.request.user,
        )
        draft.state = next_state
        draft.save(update_fields=["state", "updated_at"])
        self._audit(
            action="content_approval_requested",
            resource_type="content_draft",
            resource_id=str(draft.id),
            metadata={
                "approval_request_id": str(approval.id),
                "reviewer_type": reviewer_type,
                "version_id": str(draft.active_version_id),
            },
        )
        return approval

    def _approval_snapshot(
        self,
        draft: ContentDraft,
        *,
        target_channels: list[dict[str, str]],
    ) -> dict[str, Any]:
        approvals = ApprovalRequest.all_objects.filter(
            tenant_id=self._tenant_id(),
            draft=draft,
            version=draft.active_version,
            status=ApprovalRequest.STATUS_APPROVED,
        ).order_by("reviewer_type", "-requested_at")
        return {
            "draft_id": str(draft.id),
            "version_id": str(draft.active_version_id),
            "target_channels": target_channels,
            "approvals": [
                {
                    "approval_request_id": str(approval.id),
                    "reviewer_type": approval.reviewer_type,
                    "status": approval.status,
                    "requested_at": approval.requested_at.isoformat(),
                }
                for approval in approvals
            ],
        }

    def _schedule_targets(
        self,
        *,
        draft: ContentDraft,
        raw_channels: Any,
    ) -> list[dict[str, str]]:
        raw_targets = (
            draft.workspace.target_channels
            if raw_channels in (None, "")
            else raw_channels
        )
        if not isinstance(raw_targets, list):
            raise ValidationError({"channels": "Expected a list of publishing targets."})

        valid_channels = {
            ContentWorkspace.CHANNEL_FACEBOOK_PAGE,
            ContentWorkspace.CHANNEL_INSTAGRAM,
        }
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for raw_target in raw_targets:
            if isinstance(raw_target, str):
                target = {"type": raw_target}
            elif isinstance(raw_target, dict):
                target = {
                    str(key): str(value)
                    for key, value in raw_target.items()
                    if value not in (None, "")
                }
            else:
                raise ValidationError(
                    {"channels": "Publishing targets must be strings or objects."}
                )

            channel = str(target.get("type") or target.get("channel") or "").strip()
            if channel not in valid_channels:
                raise ValidationError(
                    {
                        "channels": (
                            f"Unsupported publishing channel: {channel or 'blank'}."
                        )
                    }
                )

            normalized_target = {"type": channel}
            if channel == ContentWorkspace.CHANNEL_FACEBOOK_PAGE and target.get("page_id"):
                normalized_target["page_id"] = str(target["page_id"]).strip()
            if channel == ContentWorkspace.CHANNEL_INSTAGRAM and target.get("ig_user_id"):
                normalized_target["ig_user_id"] = str(target["ig_user_id"]).strip()

            dedupe_key = (
                normalized_target["type"],
                normalized_target.get("page_id", ""),
                normalized_target.get("ig_user_id", ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(normalized_target)

        if not normalized:
            raise ValidationError(
                {"channels": "At least one publishing target is required."}
            )
        return normalized

    def _next_version_number(self, draft: ContentDraft) -> int:
        latest = (
            ContentDraftVersion.all_objects.filter(
                tenant_id=self._tenant_id(), draft=draft
            )
            .order_by("-version_number")
            .first()
        )
        return 1 if latest is None else latest.version_number + 1


class ContentDraftVersionViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ContentDraftVersion.all_objects.select_related("draft", "source_generation_job")
        .prefetch_related("media_assets")
        .order_by("draft_id", "version_number")
    )
    serializer_class = ContentDraftVersionSerializer

    def get_queryset(self) -> QuerySet[ContentDraftVersion]:  # type: ignore[override]
        queryset = super().get_queryset()
        draft_id = self.request.query_params.get("draft_id")
        if draft_id:
            queryset = queryset.filter(draft_id=draft_id)
        return queryset


class ApprovalRequestViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ApprovalRequest.all_objects.select_related("draft", "version")
        .all()
        .order_by("-requested_at")
    )
    serializer_class = ApprovalRequestSerializer

    def get_serializer_class(self):  # noqa: D401 - DRF schema/action hook
        if getattr(self, "action", "") == "decisions":
            return ApprovalDecisionSerializer
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet[ApprovalRequest]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        status_filter = self.request.query_params.get("status")
        reviewer_type = self.request.query_params.get("reviewer_type")
        if workspace_id:
            queryset = queryset.filter(draft__workspace_id=workspace_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if reviewer_type:
            queryset = queryset.filter(reviewer_type=reviewer_type)
        return queryset

    @decorators.action(detail=True, methods=["post"])
    def decisions(self, request: Request, pk: str | None = None) -> Response:
        approval = self.get_object()
        if approval.reviewer_type == ApprovalRequest.REVIEWER_INTERNAL:
            self._require_roles(
                CONTENT_OPS_INTERNAL_APPROVER_ROLES,
                "User role cannot decide internal Content Operations approvals.",
            )
        else:
            self._require_roles(
                CONTENT_OPS_CLIENT_APPROVER_ROLES,
                "User role cannot decide client Content Operations approvals.",
            )
        serializer = ApprovalDecisionSerializer(
            data={
                **request.data,
                "approval_request": str(approval.id),
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            approval = (
                ApprovalRequest.all_objects.select_for_update()
                .select_related("draft", "version")
                .get(tenant_id=self._tenant_id(), id=approval.id)
            )
            self._validate_decision_target(approval)
            decision = serializer.save(tenant=self._tenant(), decided_by=request.user)
            self._apply_decision(approval, decision)
        self._audit(
            action="content_approval_decided",
            resource_type="content_approval_request",
            resource_id=str(approval.id),
            metadata={
                "decision": decision.decision,
                "reviewer_type": approval.reviewer_type,
                "draft_id": str(approval.draft_id),
                "version_id": str(approval.version_id),
            },
        )
        return Response(
            ApprovalDecisionSerializer(decision, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _apply_decision(
        self, approval: ApprovalRequest, decision: ApprovalDecision
    ) -> None:
        approval.status = decision.decision
        approval.save(update_fields=["status", "updated_at"])
        draft = approval.draft
        if approval.reviewer_type == ApprovalRequest.REVIEWER_INTERNAL:
            draft.state = (
                ContentDraft.STATE_INTERNAL_APPROVED
                if decision.decision == ApprovalDecision.DECISION_APPROVED
                else ContentDraft.STATE_INTERNAL_CHANGES_REQUESTED
            )
        else:
            draft.state = (
                ContentDraft.STATE_CLIENT_APPROVED
                if decision.decision == ApprovalDecision.DECISION_APPROVED
                else ContentDraft.STATE_CLIENT_CHANGES_REQUESTED
            )
        draft.save(update_fields=["state", "updated_at"])

    def _validate_decision_target(self, approval: ApprovalRequest) -> None:
        if approval.status != ApprovalRequest.STATUS_PENDING:
            raise ValidationError(
                {"status": "Only pending approval requests can be decided."}
            )
        if approval.draft.active_version_id != approval.version_id:
            raise ValidationError(
                {"version": "Only the active draft version can be decided."}
            )
        expected_state = (
            ContentDraft.STATE_INTERNAL_REVIEW
            if approval.reviewer_type == ApprovalRequest.REVIEWER_INTERNAL
            else ContentDraft.STATE_CLIENT_REVIEW
        )
        if approval.draft.state != expected_state:
            raise ValidationError(
                {"draft": "Draft is not in the expected review state."}
            )


class ApprovalDecisionViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ApprovalDecision.all_objects.select_related("approval_request")
        .all()
        .order_by("-decided_at")
    )
    serializer_class = ApprovalDecisionSerializer

    def get_queryset(self) -> QuerySet[ApprovalDecision]:  # type: ignore[override]
        queryset = super().get_queryset()
        approval_request_id = self.request.query_params.get("approval_request_id")
        if approval_request_id:
            queryset = queryset.filter(approval_request_id=approval_request_id)
        return queryset


class ContentScheduleViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ContentSchedule.all_objects.select_related("draft", "version")
        .all()
        .order_by("scheduled_at")
    )
    serializer_class = ContentScheduleSerializer

    def get_queryset(self) -> QuerySet[ContentSchedule]:  # type: ignore[override]
        queryset = super().get_queryset()
        state_filter = self.request.query_params.get("state")
        draft_id = self.request.query_params.get("draft_id")
        if state_filter:
            queryset = queryset.filter(state=state_filter)
        if draft_id:
            queryset = queryset.filter(draft_id=draft_id)
        return queryset


class PublishAttemptViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        PublishAttempt.all_objects.select_related(
            "schedule", "draft", "version", "publishing_identity"
        )
        .all()
        .order_by("-created_at")
    )
    serializer_class = PublishAttemptSerializer

    def get_queryset(self) -> QuerySet[PublishAttempt]:  # type: ignore[override]
        queryset = super().get_queryset()
        state_filter = self.request.query_params.get("state")
        channel = self.request.query_params.get("channel")
        scheduled_from = self.request.query_params.get("scheduled_from")
        scheduled_to = self.request.query_params.get("scheduled_to")
        retry_due = self.request.query_params.get("retry_due")
        if state_filter:
            queryset = queryset.filter(state=state_filter)
        if channel:
            queryset = queryset.filter(channel=channel)
        if scheduled_from:
            queryset = queryset.filter(
                schedule__scheduled_at__gte=self._parse_query_datetime(
                    "scheduled_from", scheduled_from
                )
            )
        if scheduled_to:
            queryset = queryset.filter(
                schedule__scheduled_at__lte=self._parse_query_datetime(
                    "scheduled_to", scheduled_to
                )
            )
        if retry_due is not None:
            if retry_due.lower() not in {"1", "true", "false", "0"}:
                raise ValidationError(
                    {"retry_due": "Expected true/false or 1/0."}
                )
            if retry_due.lower() in {"1", "true"}:
                queryset = queryset.filter(
                    state=PublishAttempt.STATE_FAILED_RETRYABLE,
                    next_retry_at__isnull=False,
                    next_retry_at__lte=timezone.now(),
                )
            else:
                queryset = queryset.exclude(
                    state=PublishAttempt.STATE_FAILED_RETRYABLE,
                    next_retry_at__isnull=False,
                    next_retry_at__lte=timezone.now(),
                )
        return queryset

    def _parse_query_datetime(self, field_name: str, value: str):
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValidationError({field_name: "Expected an ISO-8601 datetime."})
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request: Request, pk: str | None = None) -> Response:
        self._require_roles(
            CONTENT_OPS_PUBLISH_ROLES,
            "User role cannot retry Content Operations publishing attempts.",
        )
        attempt = self.get_object()
        try:
            attempt = requeue_failed_publish_attempt(
                tenant=self._tenant(),
                attempt_id=attempt.id,
            )
        except ValueError as exc:
            reason = _safe_publish_retry_reason(str(exc))
            if reason == PREFLIGHT_ATTEMPT_MISSING:
                raise ValidationError(
                    {"detail": "Publish attempt does not exist.", "reason": reason}
                ) from exc
            if reason == PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE:
                raise ValidationError(
                    {
                        "detail": "Only retryable failed publish attempts can be retried.",
                        "reason": reason,
                    }
                ) from exc
            raise ValidationError(
                {"detail": "Publish attempt cannot be retried.", "reason": reason}
            ) from exc
        self._audit(
            action="content_publish_attempt_requeued",
            resource_type="content_publish_attempt",
            resource_id=str(attempt.id),
            metadata={
                "draft_id": str(attempt.draft_id),
                "schedule_id": str(attempt.schedule_id),
                "channel": attempt.channel,
            },
        )
        return Response(
            {
                "detail": "Publish attempt requeued.",
                "reason": "requeued",
                "attempt_id": str(attempt.id),
                "attempt": PublishAttemptSerializer(
                    attempt, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class PublishedPostViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        PublishedPost.all_objects.select_related(
            "workspace", "draft", "version", "publishing_identity"
        )
        .all()
        .order_by("-published_at")
    )
    serializer_class = PublishedPostSerializer

    def get_queryset(self) -> QuerySet[PublishedPost]:  # type: ignore[override]
        queryset = super().get_queryset()
        workspace_id = self.request.query_params.get("workspace_id")
        channel = self.request.query_params.get("channel")
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)
        if channel:
            queryset = queryset.filter(channel=channel)
        return queryset

    @decorators.action(detail=True, methods=["post"], url_path="refresh-metrics")
    def refresh_metrics(self, request: Request, pk: str | None = None) -> Response:
        self._require_roles(
            CONTENT_OPS_PUBLISH_ROLES,
            "User role cannot refresh Content Operations post metrics.",
        )
        post = self.get_object()
        result = refresh_published_post_metrics(
            tenant=self._tenant(),
            published_post_id=post.id,
        )
        post.refresh_from_db()
        self._audit(
            action="content_published_post_metrics_refreshed",
            resource_type="content_published_post",
            resource_id=str(post.id),
            metadata=result.as_dict(),
        )
        return Response(
            {
                "detail": (
                    "Organic metric refresh completed."
                    if result.status == "refreshed"
                    else "Organic metrics are not available for this post."
                ),
                "reason": result.reason or result.status,
                "published_post_id": str(post.id),
                "snapshot_id": result.snapshot_id,
                "reporting_link_state": post.reporting_link_state,
                "last_metrics_refresh_at": (
                    post.last_metrics_refresh_at.isoformat()
                    if post.last_metrics_refresh_at
                    else None
                ),
            },
            status=(
                status.HTTP_200_OK
                if result.status == "refreshed"
                else status.HTTP_409_CONFLICT
            ),
        )


class OrganicPostMetricSnapshotViewSet(
    ContentOpsTenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        OrganicPostMetricSnapshot.all_objects.select_related("published_post")
        .all()
        .order_by("-metric_date")
    )
    serializer_class = OrganicPostMetricSnapshotSerializer

    def get_queryset(self) -> QuerySet[OrganicPostMetricSnapshot]:  # type: ignore[override]
        queryset = super().get_queryset()
        published_post_id = self.request.query_params.get("published_post_id")
        channel = self.request.query_params.get("channel")
        if published_post_id:
            queryset = queryset.filter(published_post_id=published_post_id)
        if channel:
            queryset = queryset.filter(channel=channel)
        return queryset


def get_tenant_scoped_object(queryset: QuerySet[Any], request: Request, **kwargs: Any) -> Any:
    """Small utility for future function views that need tenant-safe lookups."""

    tenant_id = getattr(request.user, "tenant_id", None)
    if tenant_id is None:
        raise PermissionDenied("Unable to resolve tenant.")
    return get_object_or_404(queryset, tenant_id=tenant_id, **kwargs)


def _request_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.user, "tenant_id", None)
    if tenant_id is None:
        raise PermissionDenied("Unable to resolve tenant.")
    return str(tenant_id)


def _require_workspace(*, tenant_id: str, workspace_id: str) -> ContentWorkspace:
    return get_object_or_404(
        ContentWorkspace.all_objects,
        tenant_id=tenant_id,
        id=workspace_id,
    )


def _asset_error_detail(reason: str) -> str:
    details = {
        "file_required": "An uploaded file is required.",
        "asset_empty": "Uploaded asset is empty.",
        "asset_too_large": "Uploaded asset exceeds the size limit.",
        "asset_mime_type_unsupported": "Uploaded asset type is not supported.",
        "workspace_wrong_tenant": "Workspace does not belong to this tenant.",
    }
    return details.get(reason, "Asset upload failed.")


def _safe_asset_error_reason(reason: str) -> str:
    allowed = {
        "file_required",
        "asset_empty",
        "asset_too_large",
        "asset_mime_type_unsupported",
        "workspace_wrong_tenant",
    }
    return reason if reason in allowed else "asset_upload_failed"


def _export_artifact_error_detail(reason: str) -> str:
    details = {
        "export_artifact_missing": "Export artifact file was not found or is empty.",
        "export_artifact_path_invalid": "Export artifact path is invalid.",
        "export_artifact_path_unsafe": "Export artifact path is unsafe.",
    }
    return details.get(reason, "Export artifact download failed.")


def _safe_export_artifact_error_reason(reason: str) -> str:
    allowed = {
        "export_artifact_missing",
        "export_artifact_path_invalid",
        "export_artifact_path_unsafe",
    }
    return reason if reason in allowed else "export_artifact_error"


def _safe_publish_retry_reason(reason: str) -> str:
    allowed = {
        PREFLIGHT_ATTEMPT_MISSING,
        PREFLIGHT_ATTEMPT_STATE_NOT_PUBLISHABLE,
    }
    return reason if reason in allowed else "attempt_retry_failed"


def _date_range_from_request(request: Request):
    start_raw = request.query_params.get("start_date")
    end_raw = request.query_params.get("end_date")
    start_date = parse_date(start_raw) if start_raw else None
    end_date = parse_date(end_raw) if end_raw else None
    if start_raw and start_date is None:
        raise ValidationError({"start_date": "Expected YYYY-MM-DD."})
    if end_raw and end_date is None:
        raise ValidationError({"end_date": "Expected YYYY-MM-DD."})
    if start_date and end_date and start_date > end_date:
        raise ValidationError({"end_date": "Must be on or after start_date."})
    return start_date, end_date


def _counts_by(queryset: QuerySet[Any], field_name: str) -> dict[str, int]:
    return {
        str(row[field_name]): int(row["count"])
        for row in queryset.values(field_name)
        .annotate(count=Count("id"))
        .order_by(field_name)
    }


def _metric_totals(queryset: QuerySet[OrganicPostMetricSnapshot]) -> dict[str, int]:
    totals = queryset.aggregate(
        impressions=Sum("impressions"),
        reach=Sum("reach"),
        engagements=Sum("engagements"),
        clicks=Sum("clicks"),
        saves=Sum("saves"),
        shares=Sum("shares"),
        video_views=Sum("video_views"),
    )
    return {key: int(value or 0) for key, value in totals.items()}


def _content_plan_payload(
    *,
    tenant_id: str,
    workspace: ContentWorkspace,
    states: list[str],
) -> dict[str, Any]:
    drafts = (
        ContentDraft.all_objects.filter(tenant_id=tenant_id, workspace=workspace)
        .select_related("active_version", "brief")
        .prefetch_related("active_version__media_assets", "approval_requests", "schedules")
        .order_by("created_at")
    )
    if states:
        drafts = drafts.filter(state__in=states)

    items = [_content_plan_item(draft) for draft in drafts]
    return {
        "workspace": {
            "id": str(workspace.id),
            "name": workspace.name,
            "timezone": workspace.timezone,
        },
        "format": "json",
        "item_count": len(items),
        "items": items,
    }


def _content_plan_item(draft: ContentDraft) -> dict[str, Any]:
    version = draft.active_version
    schedule = draft.schedules.order_by("-created_at").first()
    approvals = draft.approval_requests.order_by("reviewer_type", "-requested_at")
    media_assets = version.media_assets.all() if version is not None else []
    return {
        "draft_id": str(draft.id),
        "title": draft.title,
        "state": draft.state,
        "brief_id": str(draft.brief_id) if draft.brief_id else None,
        "active_version": (
            {
                "id": str(version.id),
                "version_number": version.version_number,
                "caption": version.caption,
                "platform_overrides": version.platform_overrides,
                "media_assets": [
                    {
                        "id": str(asset.id),
                        "source": asset.source,
                        "mime_type": asset.mime_type,
                        "width": asset.width,
                        "height": asset.height,
                        "duration_seconds": (
                            str(asset.duration_seconds)
                            if asset.duration_seconds is not None
                            else None
                        ),
                        "alt_text": asset.alt_text,
                    }
                    for asset in media_assets
                ],
            }
            if version is not None
            else None
        ),
        "approvals": [
            {
                "id": str(approval.id),
                "reviewer_type": approval.reviewer_type,
                "status": approval.status,
                "version_id": str(approval.version_id),
                "requested_at": approval.requested_at.isoformat(),
            }
            for approval in approvals
        ],
        "schedule": (
            {
                "id": str(schedule.id),
                "scheduled_at": schedule.scheduled_at.isoformat(),
                "timezone": schedule.timezone,
                "state": schedule.state,
            }
            if schedule is not None
            else None
        ),
    }
