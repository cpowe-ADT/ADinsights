"""Serializers for tenant-scoped Content Operations APIs."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from integrations.models import Client, PlatformCredential

from .assets import validate_media_assets_for_publish
from .generation import (
    MAX_CAPTION_CANDIDATE_COUNT,
    SUPPORTED_CAPTION_PLATFORMS,
    normalize_caption_candidate_count,
    normalize_caption_platforms,
    redact_secret_like_text,
)
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
)


class TenantScopedContentSerializerMixin:
    """Validate related objects against the authenticated tenant."""

    tenant_related_fields: tuple[str, ...] = ()

    def _tenant_id(self) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None) if request is not None else None
        tenant_id = getattr(user, "tenant_id", None)
        return str(tenant_id) if tenant_id is not None else None

    def _ensure_tenant_match(self, value: Any, field_name: str) -> Any:
        if value is None:
            return value
        tenant_id = self._tenant_id()
        value_tenant_id = getattr(value, "tenant_id", None)
        if tenant_id is not None and str(value_tenant_id) != tenant_id:
            raise serializers.ValidationError(
                {field_name: "Object does not belong to this tenant."}
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        for field_name in self.tenant_related_fields:
            value = attrs.get(field_name)
            if value is None:
                value = getattr(self.instance, field_name, None)
            self._ensure_tenant_match(value, field_name)
        return attrs


class ContentWorkspaceSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.all_objects.all(),
        allow_null=True,
        required=False,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("client",)

    class Meta:
        model = ContentWorkspace
        fields = [
            "id",
            "client_id",
            "name",
            "objective",
            "brand_profile",
            "target_channels",
            "timezone",
            "created_by",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class PublishingIdentitySerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    credential_ref = serializers.PrimaryKeyRelatedField(
        queryset=PlatformCredential.all_objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
    )

    tenant_related_fields = ("credential_ref",)

    class Meta:
        model = PublishingIdentity
        fields = [
            "id",
            "platform",
            "meta_page_id",
            "ig_user_id",
            "display_name",
            "credential_ref",
            "selection_state",
            "publish_readiness_state",
            "publish_readiness_reason",
            "last_checked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "publish_readiness_state",
            "publish_readiness_reason",
            "last_checked_at",
            "created_at",
            "updated_at",
        ]


class ContentBriefSerializer(TenantScopedContentSerializerMixin, serializers.ModelSerializer):
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=ContentWorkspace.all_objects.all()
    )

    tenant_related_fields = ("workspace",)

    class Meta:
        model = ContentBrief
        fields = [
            "id",
            "workspace",
            "campaign_theme",
            "audience",
            "offer",
            "tone",
            "required_terms",
            "blocked_terms",
            "landing_url",
            "date_start",
            "date_end",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GenerationJobSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=ContentWorkspace.all_objects.all()
    )
    brief = serializers.PrimaryKeyRelatedField(
        queryset=ContentBrief.all_objects.all(),
        allow_null=True,
        required=False,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("workspace", "brief")

    class Meta:
        model = GenerationJob
        fields = [
            "id",
            "workspace",
            "brief",
            "job_type",
            "provider",
            "model_name",
            "status",
            "input_fingerprint",
            "redacted_prompt_summary",
            "prompt_policy_result",
            "result_summary",
            "error_code",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "input_fingerprint",
            "prompt_policy_result",
            "result_summary",
            "error_code",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        workspace = attrs.get("workspace") or getattr(self.instance, "workspace", None)
        brief = attrs.get("brief") or getattr(self.instance, "brief", None)
        if brief is not None and workspace is not None and brief.workspace_id != workspace.id:
            raise serializers.ValidationError(
                {"brief": "Brief does not belong to the provided workspace."}
            )
        if "redacted_prompt_summary" in attrs:
            attrs["redacted_prompt_summary"] = redact_secret_like_text(
                attrs["redacted_prompt_summary"]
            )
        return attrs


class CaptionGenerateRequestSerializer(serializers.Serializer):
    candidate_count = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_CAPTION_CANDIDATE_COUNT,
    )
    platforms = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False,
    )
    tone_override = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        workspace = self.context.get("workspace")
        if workspace is None:
            raise serializers.ValidationError(
                {"workspace": "Workspace context is required."}
            )
        try:
            attrs["candidate_count"] = normalize_caption_candidate_count(
                attrs.get("candidate_count")
            )
            attrs["platforms"] = normalize_caption_platforms(
                workspace=workspace,
                platforms=attrs.get("platforms"),
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                {"detail": "Caption request is invalid."}
            ) from exc
        invalid = set(attrs["platforms"]) - SUPPORTED_CAPTION_PLATFORMS
        if invalid:
            raise serializers.ValidationError(
                {"platforms": f"Unsupported caption platforms: {sorted(invalid)}"}
            )
        attrs["tone_override"] = redact_secret_like_text(
            attrs.get("tone_override", "")
        )[:128]
        return attrs


class MediaAssetSerializer(TenantScopedContentSerializerMixin, serializers.ModelSerializer):
    storage_key = serializers.CharField(write_only=True, max_length=512)
    download_url = serializers.SerializerMethodField()
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=ContentWorkspace.all_objects.all()
    )

    tenant_related_fields = ("workspace",)
    server_owned_fields = {
        "source",
        "storage_key",
        "mime_type",
        "width",
        "height",
        "duration_seconds",
        "renditions",
        "status",
    }

    class Meta:
        model = MediaAsset
        fields = [
            "id",
            "workspace",
            "source",
            "storage_key",
            "mime_type",
            "width",
            "height",
            "duration_seconds",
            "alt_text",
            "renditions",
            "status",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "download_url", "created_at", "updated_at"]

    def get_download_url(self, obj: MediaAsset) -> str | None:
        if obj.status != MediaAsset.STATUS_AVAILABLE:
            return None
        request = self.context.get("request")
        path = f"/api/content-ops/assets/{obj.id}/download/"
        if request is not None:
            return request.build_absolute_uri(path)
        return path

    def update(self, instance: MediaAsset, validated_data: dict[str, Any]) -> MediaAsset:
        for field_name in self.server_owned_fields:
            validated_data.pop(field_name, None)
        return super().update(instance, validated_data)


class ContentDraftVersionSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    draft = serializers.PrimaryKeyRelatedField(queryset=ContentDraft.all_objects.all())
    media_assets = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.all_objects.all(),
        many=True,
        required=False,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    source_generation_job = serializers.PrimaryKeyRelatedField(
        queryset=GenerationJob.all_objects.all(),
        allow_null=True,
        required=False,
    )

    tenant_related_fields = ("draft", "source_generation_job")

    class Meta:
        model = ContentDraftVersion
        fields = [
            "id",
            "draft",
            "version_number",
            "caption",
            "platform_overrides",
            "media_assets",
            "created_by",
            "change_note",
            "source_generation_job",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_media_assets(self, value: list[MediaAsset]) -> list[MediaAsset]:
        for asset in value:
            self._ensure_tenant_match(asset, "media_assets")
            if asset.status != MediaAsset.STATUS_AVAILABLE:
                raise serializers.ValidationError(
                    "Only available assets can be attached to a draft version."
                )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        draft = attrs.get("draft") or getattr(self.instance, "draft", None)
        source_job = attrs.get("source_generation_job") or getattr(
            self.instance, "source_generation_job", None
        )
        media_assets = attrs.get("media_assets")
        if source_job is not None and draft is not None:
            if source_job.workspace_id != draft.workspace_id:
                raise serializers.ValidationError(
                    {
                        "source_generation_job": (
                            "Generation job does not belong to the draft workspace."
                        )
                    }
                )
        if draft is not None and media_assets is not None:
            for asset in media_assets:
                if asset.workspace_id != draft.workspace_id:
                    raise serializers.ValidationError(
                        {
                            "media_assets": (
                                "Media asset does not belong to the draft workspace."
                            )
                        }
                    )
            if draft.state in {
                ContentDraft.STATE_SCHEDULED,
                ContentDraft.STATE_PUBLISHING,
            }:
                media_result = validate_media_assets_for_publish(media_assets)
                if not media_result.ready:
                    raise serializers.ValidationError(
                        {
                            "media_assets": {
                                "reason": media_result.failure_code,
                                "detail": media_result.failure_detail_safe,
                            }
                        }
                    )
        return attrs


class ContentExportArtifactSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    download_url = serializers.SerializerMethodField()
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=ContentWorkspace.all_objects.all()
    )
    requested_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("workspace",)

    class Meta:
        model = ContentExportArtifact
        fields = [
            "id",
            "workspace",
            "export_type",
            "export_format",
            "status",
            "item_count",
            "metadata",
            "requested_by",
            "completed_at",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_download_url(self, obj: ContentExportArtifact) -> str | None:
        if obj.status != ContentExportArtifact.STATUS_COMPLETED or not obj.artifact_path:
            return None
        request = self.context.get("request")
        path = f"/api/content-ops/exports/{obj.id}/download/"
        if request is not None:
            return request.build_absolute_uri(path)
        return path


class ContentDraftSerializer(TenantScopedContentSerializerMixin, serializers.ModelSerializer):
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=ContentWorkspace.all_objects.all()
    )
    brief = serializers.PrimaryKeyRelatedField(
        queryset=ContentBrief.all_objects.all(),
        allow_null=True,
        required=False,
    )
    active_version = serializers.PrimaryKeyRelatedField(
        queryset=ContentDraftVersion.all_objects.all(),
        allow_null=True,
        required=False,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    locked_by = serializers.PrimaryKeyRelatedField(read_only=True)
    approval_summary = serializers.SerializerMethodField()
    schedule_summary = serializers.SerializerMethodField()

    tenant_related_fields = ("workspace", "brief", "active_version")

    class Meta:
        model = ContentDraft
        fields = [
            "id",
            "workspace",
            "brief",
            "title",
            "state",
            "active_version",
            "approval_summary",
            "schedule_summary",
            "created_by",
            "owner",
            "locked_at",
            "locked_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state",
            "approval_summary",
            "schedule_summary",
            "created_by",
            "owner",
            "locked_at",
            "locked_by",
            "created_at",
            "updated_at",
        ]

    def get_approval_summary(self, obj: ContentDraft) -> dict[str, Any]:
        approvals = obj.approval_requests.all()
        latest_by_type: dict[str, dict[str, Any]] = {}
        for approval in approvals:
            latest_by_type.setdefault(
                approval.reviewer_type,
                {
                    "id": str(approval.id),
                    "status": approval.status,
                    "version_id": str(approval.version_id),
                    "requested_at": approval.requested_at,
                },
            )
        return latest_by_type

    def get_schedule_summary(self, obj: ContentDraft) -> dict[str, Any] | None:
        schedule = obj.schedules.order_by("-created_at").first()
        if schedule is None:
            return None
        return {
            "id": str(schedule.id),
            "state": schedule.state,
            "scheduled_at": schedule.scheduled_at,
            "timezone": schedule.timezone,
        }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        workspace = attrs.get("workspace") or getattr(self.instance, "workspace", None)
        brief = attrs.get("brief") or getattr(self.instance, "brief", None)
        active_version = attrs.get("active_version") or getattr(
            self.instance, "active_version", None
        )
        if brief is not None and workspace is not None and brief.workspace_id != workspace.id:
            raise serializers.ValidationError(
                {"brief": "Brief does not belong to the provided workspace."}
            )
        if active_version is not None:
            if self.instance is None:
                raise serializers.ValidationError(
                    {"active_version": "Create a draft before assigning active_version."}
                )
            if active_version.draft_id != self.instance.id:
                raise serializers.ValidationError(
                    {"active_version": "Version does not belong to this draft."}
                )
        return attrs


class ApprovalRequestSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    draft = serializers.PrimaryKeyRelatedField(queryset=ContentDraft.all_objects.all())
    version = serializers.PrimaryKeyRelatedField(
        queryset=ContentDraftVersion.all_objects.all()
    )
    requested_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("draft", "version")

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "draft",
            "version",
            "reviewer_type",
            "status",
            "requested_by",
            "requested_at",
            "due_at",
            "superseded_at",
            "superseded_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "requested_by",
            "requested_at",
            "superseded_at",
            "superseded_reason",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        draft = attrs.get("draft") or getattr(self.instance, "draft", None)
        version = attrs.get("version") or getattr(self.instance, "version", None)
        if draft is not None and version is not None and version.draft_id != draft.id:
            raise serializers.ValidationError(
                {"version": "Version does not belong to the provided draft."}
            )
        return attrs


class ApprovalDecisionSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    approval_request = serializers.PrimaryKeyRelatedField(
        queryset=ApprovalRequest.all_objects.all()
    )
    decided_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("approval_request",)

    class Meta:
        model = ApprovalDecision
        fields = [
            "id",
            "approval_request",
            "decision",
            "comment",
            "decided_by",
            "decided_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "decided_by",
            "decided_at",
            "created_at",
            "updated_at",
        ]


class ContentScheduleSerializer(
    TenantScopedContentSerializerMixin, serializers.ModelSerializer
):
    draft = serializers.PrimaryKeyRelatedField(queryset=ContentDraft.all_objects.all())
    version = serializers.PrimaryKeyRelatedField(
        queryset=ContentDraftVersion.all_objects.all()
    )
    channels = serializers.ListField(
        child=serializers.JSONField(),
        write_only=True,
        required=False,
        allow_empty=False,
    )
    scheduled_by = serializers.PrimaryKeyRelatedField(read_only=True)

    tenant_related_fields = ("draft", "version")

    class Meta:
        model = ContentSchedule
        fields = [
            "id",
            "draft",
            "version",
            "scheduled_at",
            "timezone",
            "channels",
            "state",
            "scheduled_by",
            "approval_snapshot",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state",
            "scheduled_by",
            "approval_snapshot",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        draft = attrs.get("draft") or getattr(self.instance, "draft", None)
        version = attrs.get("version") or getattr(self.instance, "version", None)
        if draft is None or version is None:
            return attrs
        attrs.pop("channels", None)
        if version.draft_id != draft.id:
            raise serializers.ValidationError(
                {"version": "Version does not belong to the provided draft."}
            )
        if draft.active_version_id != version.id:
            raise serializers.ValidationError(
                {"version": "Only the active draft version can be scheduled."}
            )
        if draft.state != ContentDraft.STATE_CLIENT_APPROVED:
            raise serializers.ValidationError(
                {"draft": "Draft must be client-approved before scheduling."}
            )
        return attrs


class PublishAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishAttempt
        fields = [
            "id",
            "schedule",
            "draft",
            "version",
            "publishing_identity",
            "channel",
            "state",
            "attempt_count",
            "idempotency_key",
            "correlation_id",
            "meta_container_id",
            "meta_container_created_at",
            "meta_post_id",
            "failure_code",
            "failure_detail_safe",
            "next_retry_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PublishedPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishedPost
        fields = [
            "id",
            "workspace",
            "draft",
            "version",
            "publishing_identity",
            "channel",
            "meta_post_id",
            "permalink",
            "published_at",
            "reporting_link_state",
            "last_metrics_refresh_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrganicPostMetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganicPostMetricSnapshot
        fields = [
            "id",
            "published_post",
            "metric_date",
            "channel",
            "impressions",
            "reach",
            "engagements",
            "clicks",
            "saves",
            "shares",
            "video_views",
            "source",
            "fetched_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
