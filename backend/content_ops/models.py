"""Tenant-scoped Content Operations models."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Tenant, TenantAwareManager


class TenantScopedModel(models.Model):
    """Shared tenant-scoped base for Content Operations records."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class ContentWorkspace(TenantScopedModel):
    """Agency/client content planning workspace."""

    CHANNEL_FACEBOOK_PAGE = "facebook_page"
    CHANNEL_INSTAGRAM = "instagram"
    CHANNEL_CHOICES = [
        (CHANNEL_FACEBOOK_PAGE, "Facebook Page"),
        (CHANNEL_INSTAGRAM, "Instagram"),
    ]

    # Governs the quick "publish now" path. ``required`` keeps the full
    # internal/client approval workflow as a precondition for publishing;
    # ``bypass`` lets a user with a publish role post immediately without a
    # recorded client approval (the workflow on the drafts board still exists
    # for teams that want client sign-off).
    APPROVAL_MODE_REQUIRED = "required"
    APPROVAL_MODE_BYPASS = "bypass"
    APPROVAL_MODE_CHOICES = [
        (APPROVAL_MODE_REQUIRED, "Require approval before publishing"),
        (APPROVAL_MODE_BYPASS, "Allow publishers to post without approval"),
    ]

    client = models.ForeignKey(
        "integrations.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_workspaces",
    )
    name = models.CharField(max_length=255)
    objective = models.TextField(blank=True)
    brand_profile = models.JSONField(default=dict, blank=True)
    target_channels = models.JSONField(default=list, blank=True)
    timezone = models.CharField(max_length=64, default="America/Jamaica")
    quick_post_approval_mode = models.CharField(
        max_length=16,
        choices=APPROVAL_MODE_CHOICES,
        default=APPROVAL_MODE_BYPASS,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_content_workspaces",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["tenant", "archived_at"], name="content_ws_archived"),
            models.Index(fields=["tenant", "client"], name="content_ws_client"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"ContentWorkspace<{self.tenant_id}:{self.name}>"


class PublishingIdentity(TenantScopedModel):
    """Publishable Meta destination, separate from reporting readiness."""

    PLATFORM_FACEBOOK_PAGE = "facebook_page"
    PLATFORM_INSTAGRAM = "instagram"
    PLATFORM_CHOICES = [
        (PLATFORM_FACEBOOK_PAGE, "Facebook Page"),
        (PLATFORM_INSTAGRAM, "Instagram"),
    ]

    SELECTION_SELECTED = "selected"
    SELECTION_REVOKED = "revoked"
    SELECTION_NOT_SELECTED = "not_selected"
    SELECTION_CHOICES = [
        (SELECTION_SELECTED, "Selected"),
        (SELECTION_REVOKED, "Revoked"),
        (SELECTION_NOT_SELECTED, "Not selected"),
    ]

    READINESS_UNKNOWN = "unknown"
    READINESS_READY = "ready"
    READINESS_BLOCKED = "blocked"
    READINESS_NEEDS_REAUTH = "needs_reauth"
    READINESS_NEEDS_REVIEW = "needs_review"
    READINESS_CHOICES = [
        (READINESS_UNKNOWN, "Unknown"),
        (READINESS_READY, "Ready"),
        (READINESS_BLOCKED, "Blocked"),
        (READINESS_NEEDS_REAUTH, "Needs reauth"),
        (READINESS_NEEDS_REVIEW, "Needs review"),
    ]

    platform = models.CharField(max_length=32, choices=PLATFORM_CHOICES)
    meta_page_id = models.CharField(max_length=128, blank=True)
    ig_user_id = models.CharField(max_length=128, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    credential_ref = models.ForeignKey(
        "integrations.PlatformCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_publishing_identities",
    )
    selection_state = models.CharField(
        max_length=32, choices=SELECTION_CHOICES, default=SELECTION_NOT_SELECTED
    )
    publish_readiness_state = models.CharField(
        max_length=32, choices=READINESS_CHOICES, default=READINESS_UNKNOWN
    )
    publish_readiness_reason = models.CharField(max_length=128, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("display_name", "platform")
        indexes = [
            models.Index(fields=["tenant", "platform"], name="content_ident_platform"),
            models.Index(fields=["tenant", "meta_page_id"], name="content_ident_page"),
            models.Index(fields=["tenant", "ig_user_id"], name="content_ident_ig"),
        ]
        unique_together = ("tenant", "platform", "meta_page_id", "ig_user_id")


class ContentBrief(TenantScopedModel):
    """Creative brief used to generate and organize content drafts."""

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="briefs"
    )
    campaign_theme = models.CharField(max_length=255, blank=True)
    audience = models.TextField(blank=True)
    offer = models.TextField(blank=True)
    tone = models.CharField(max_length=128, blank=True)
    required_terms = models.JSONField(default=list, blank=True)
    blocked_terms = models.JSONField(default=list, blank=True)
    landing_url = models.URLField(blank=True)
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "workspace"], name="content_brief_ws"),
            models.Index(fields=["tenant", "status"], name="content_brief_status"),
        ]


class GenerationJob(TenantScopedModel):
    """AI generation job metadata and safe lineage."""

    TYPE_CAPTION = "caption"
    TYPE_GRAPHIC_BATCH = "graphic_batch"
    TYPE_VARIATION = "variation"
    TYPE_RESIZE = "resize"
    TYPE_CHOICES = [
        (TYPE_CAPTION, "Caption"),
        (TYPE_GRAPHIC_BATCH, "Graphic batch"),
        (TYPE_VARIATION, "Variation"),
        (TYPE_RESIZE, "Resize"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="generation_jobs"
    )
    brief = models.ForeignKey(
        ContentBrief,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_jobs",
    )
    regional_agent_profile = models.ForeignKey(
        "RegionalAgentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generation_jobs",
    )
    job_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    provider = models.CharField(max_length=64, blank=True)
    model_name = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    input_fingerprint = models.CharField(max_length=128, blank=True)
    redacted_prompt_summary = models.TextField(blank=True)
    prompt_policy_result = models.JSONField(default=dict, blank=True)
    result_summary = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_generation_jobs",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "status"], name="content_gen_status"),
            models.Index(fields=["tenant", "job_type"], name="content_gen_type"),
        ]


class MediaAsset(TenantScopedModel):
    """Generated or uploaded media asset stored by ADinsights."""

    SOURCE_UPLOADED = "uploaded"
    SOURCE_AI_GENERATED = "ai_generated"
    SOURCE_IMPORTED = "imported"
    SOURCE_CHOICES = [
        (SOURCE_UPLOADED, "Uploaded"),
        (SOURCE_AI_GENERATED, "AI generated"),
        (SOURCE_IMPORTED, "Imported"),
    ]

    STATUS_AVAILABLE = "available"
    STATUS_QUARANTINED = "quarantined"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_QUARANTINED, "Quarantined"),
        (STATUS_DELETED, "Deleted"),
    ]

    KIND_CONTENT = "content"
    KIND_LOGO = "logo"
    KIND_REFERENCE = "reference"
    KIND_CHOICES = [
        (KIND_CONTENT, "Content"),
        (KIND_LOGO, "Logo"),
        (KIND_REFERENCE, "Reference"),
    ]

    LOGO_VARIANT_LIGHT = "light"
    LOGO_VARIANT_DARK = "dark"
    LOGO_VARIANT_FULL_COLOR = "full_color"
    LOGO_VARIANT_MONOCHROME = "monochrome"
    LOGO_VARIANT_CHOICES = [
        (LOGO_VARIANT_LIGHT, "Light (for dark backgrounds)"),
        (LOGO_VARIANT_DARK, "Dark (for light backgrounds)"),
        (LOGO_VARIANT_FULL_COLOR, "Full color"),
        (LOGO_VARIANT_MONOCHROME, "Monochrome"),
    ]

    REFERENCE_ROLE_STYLE = "style"
    REFERENCE_ROLE_SUBJECT = "subject"
    REFERENCE_ROLE_MOOD = "mood"
    REFERENCE_ROLE_CHOICES = [
        (REFERENCE_ROLE_STYLE, "Style"),
        (REFERENCE_ROLE_SUBJECT, "Subject"),
        (REFERENCE_ROLE_MOOD, "Mood"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="media_assets"
    )
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    storage_key = models.CharField(max_length=512)
    mime_type = models.CharField(max_length=128)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    alt_text = models.TextField(blank=True)
    renditions = models.JSONField(default=dict, blank=True)
    ai_lineage = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    is_approved_reference = models.BooleanField(default=False)
    reference_region = models.CharField(max_length=32, blank=True)
    reference_locale = models.CharField(max_length=16, blank=True)
    # Asset-library facets (Slice 1). ``kind`` discriminates content vs brand
    # logo vs approved reference; the rest are meaningful per-kind.
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_CONTENT)
    logo_variant = models.CharField(max_length=16, choices=LOGO_VARIANT_CHOICES, blank=True)
    reference_role = models.CharField(
        max_length=16, choices=REFERENCE_ROLE_CHOICES, blank=True
    )
    reference_weight = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    # Structured description of an uploaded reference (populated later by the
    # cheap vision "reference reader"); empty until then.
    reference_descriptor = models.JSONField(default=dict, blank=True)
    # Usage-rights attestation — gates a logo/reference becoming usable.
    usage_rights_attested = models.BooleanField(default=False)
    usage_rights_attested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_attested_assets",
    )
    usage_rights_attested_at = models.DateTimeField(null=True, blank=True)
    usage_rights_note = models.CharField(max_length=255, blank=True)
    # Content hash (sha256 hex) of the stored bytes — dedup + reproducibility
    # anchor (snapshotted into job lineage so a swapped asset can't silently
    # alter a past graphic).
    content_hash = models.CharField(max_length=64, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    # Groups multi-asset deliverables (poster + clip, N carousel slides) — a
    # forward seam for video/carousel; nullable + indexed.
    deliverable_group_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "workspace"], name="content_asset_ws"),
            models.Index(fields=["tenant", "status"], name="content_asset_status"),
            models.Index(
                fields=["tenant", "is_approved_reference"], name="content_asset_ref"
            ),
            models.Index(fields=["tenant", "kind", "status"], name="content_asset_kind"),
            models.Index(fields=["tenant", "content_hash"], name="content_asset_hash"),
            models.Index(
                fields=["tenant", "deliverable_group_id"], name="content_asset_group"
            ),
        ]


class ContentDraft(TenantScopedModel):
    """Versioned content draft with approval and publishing state."""

    STATE_DRAFT = "draft"
    STATE_GENERATED = "generated"
    STATE_INTERNAL_REVIEW = "internal_review"
    STATE_INTERNAL_CHANGES_REQUESTED = "internal_changes_requested"
    STATE_INTERNAL_APPROVED = "internal_approved"
    STATE_CLIENT_REVIEW = "client_review"
    STATE_CLIENT_CHANGES_REQUESTED = "client_changes_requested"
    STATE_CLIENT_APPROVED = "client_approved"
    STATE_SCHEDULED = "scheduled"
    STATE_PUBLISHING = "publishing"
    STATE_PUBLISHED = "published"
    STATE_PARTIALLY_PUBLISHED = "partially_published"
    STATE_FAILED = "failed"
    STATE_CANCELLED = "cancelled"
    STATE_ARCHIVED = "archived"
    STATE_CHOICES = [
        (STATE_DRAFT, "Draft"),
        (STATE_GENERATED, "Generated"),
        (STATE_INTERNAL_REVIEW, "Internal review"),
        (STATE_INTERNAL_CHANGES_REQUESTED, "Internal changes requested"),
        (STATE_INTERNAL_APPROVED, "Internal approved"),
        (STATE_CLIENT_REVIEW, "Client review"),
        (STATE_CLIENT_CHANGES_REQUESTED, "Client changes requested"),
        (STATE_CLIENT_APPROVED, "Client approved"),
        (STATE_SCHEDULED, "Scheduled"),
        (STATE_PUBLISHING, "Publishing"),
        (STATE_PUBLISHED, "Published"),
        (STATE_PARTIALLY_PUBLISHED, "Partially published"),
        (STATE_FAILED, "Failed"),
        (STATE_CANCELLED, "Cancelled"),
        (STATE_ARCHIVED, "Archived"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="drafts"
    )
    brief = models.ForeignKey(
        ContentBrief,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drafts",
    )
    title = models.CharField(max_length=255)
    state = models.CharField(max_length=40, choices=STATE_CHOICES, default=STATE_DRAFT)
    active_version = models.ForeignKey(
        "ContentDraftVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_content_drafts",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_content_drafts",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_content_drafts",
    )

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["tenant", "workspace"], name="content_draft_ws"),
            models.Index(fields=["tenant", "state"], name="content_draft_state"),
        ]

    def invalidate_approvals(self, reason: str = "version_changed") -> int:
        """Supersede non-terminal approvals after a draft edit/version change."""

        return ApprovalRequest.all_objects.filter(
            draft=self,
            status__in=[
                ApprovalRequest.STATUS_PENDING,
                ApprovalRequest.STATUS_APPROVED,
                ApprovalRequest.STATUS_CHANGES_REQUESTED,
            ],
        ).update(
            status=ApprovalRequest.STATUS_SUPERSEDED,
            superseded_at=timezone.now(),
            superseded_reason=reason,
        )

    def has_current_client_approval(self, version=None) -> bool:
        """True when the given (or active) version holds a current client approval.

        A version edit supersedes prior approvals via :meth:`invalidate_approvals`,
        so an ``approved`` client request only survives for the version it was
        granted against — making this the publish-readiness invariant.
        """

        version_id = version.id if version is not None else self.active_version_id
        if version_id is None:
            return False
        return ApprovalRequest.all_objects.filter(
            tenant_id=self.tenant_id,
            draft=self,
            version_id=version_id,
            reviewer_type=ApprovalRequest.REVIEWER_CLIENT,
            status=ApprovalRequest.STATUS_APPROVED,
        ).exists()


class ContentDraftVersion(TenantScopedModel):
    """Immutable-ish version payload for a content draft."""

    draft = models.ForeignKey(
        ContentDraft, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    caption = models.TextField(blank=True)
    platform_overrides = models.JSONField(default=dict, blank=True)
    media_assets = models.ManyToManyField(
        MediaAsset, blank=True, related_name="draft_versions"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_draft_versions",
    )
    change_note = models.TextField(blank=True)
    source_generation_job = models.ForeignKey(
        GenerationJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_versions",
    )

    class Meta:
        ordering = ("draft_id", "version_number")
        indexes = [
            models.Index(fields=["tenant", "draft"], name="content_version_draft"),
        ]
        unique_together = ("tenant", "draft", "version_number")


class ApprovalRequest(TenantScopedModel):
    """Version-bound approval request."""

    REVIEWER_INTERNAL = "internal"
    REVIEWER_CLIENT = "client"
    REVIEWER_CHOICES = [
        (REVIEWER_INTERNAL, "Internal"),
        (REVIEWER_CLIENT, "Client"),
    ]

    STATUS_NOT_REQUESTED = "not_requested"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_CHANGES_REQUESTED = "changes_requested"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_SUPERSEDED = "superseded"
    STATUS_CHOICES = [
        (STATUS_NOT_REQUESTED, "Not requested"),
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_CHANGES_REQUESTED, "Changes requested"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    draft = models.ForeignKey(
        ContentDraft, on_delete=models.CASCADE, related_name="approval_requests"
    )
    version = models.ForeignKey(
        ContentDraftVersion, on_delete=models.CASCADE, related_name="approval_requests"
    )
    reviewer_type = models.CharField(max_length=32, choices=REVIEWER_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_content_approvals",
    )
    requested_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    superseded_reason = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ("-requested_at",)
        indexes = [
            models.Index(fields=["tenant", "status"], name="content_approval_status"),
            models.Index(fields=["tenant", "reviewer_type"], name="content_approval_type"),
        ]


class ApprovalDecision(TenantScopedModel):
    """Decision made against an approval request."""

    DECISION_APPROVED = "approved"
    DECISION_CHANGES_REQUESTED = "changes_requested"
    DECISION_REJECTED = "rejected"
    DECISION_CHOICES = [
        (DECISION_APPROVED, "Approved"),
        (DECISION_CHANGES_REQUESTED, "Changes requested"),
        (DECISION_REJECTED, "Rejected"),
    ]

    approval_request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name="decisions"
    )
    decision = models.CharField(max_length=32, choices=DECISION_CHOICES)
    comment = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_approval_decisions",
    )
    decided_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-decided_at",)
        indexes = [
            models.Index(fields=["tenant", "decision"], name="content_decision"),
        ]


class ContentSchedule(TenantScopedModel):
    """Approved version scheduled by ADinsights."""

    STATE_SCHEDULED = "scheduled"
    STATE_LOCKED = "locked"
    STATE_DISPATCHING = "dispatching"
    STATE_PUBLISHED = "published"
    STATE_PARTIAL = "partial"
    STATE_FAILED = "failed"
    STATE_CANCELLED = "cancelled"
    STATE_CHOICES = [
        (STATE_SCHEDULED, "Scheduled"),
        (STATE_LOCKED, "Locked"),
        (STATE_DISPATCHING, "Dispatching"),
        (STATE_PUBLISHED, "Published"),
        (STATE_PARTIAL, "Partial"),
        (STATE_FAILED, "Failed"),
        (STATE_CANCELLED, "Cancelled"),
    ]

    draft = models.ForeignKey(
        ContentDraft, on_delete=models.CASCADE, related_name="schedules"
    )
    version = models.ForeignKey(
        ContentDraftVersion, on_delete=models.CASCADE, related_name="schedules"
    )
    scheduled_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="America/Jamaica")
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_SCHEDULED)
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_schedules",
    )
    approval_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("scheduled_at",)
        indexes = [
            models.Index(fields=["tenant", "state", "scheduled_at"], name="content_schedule_due"),
            models.Index(fields=["tenant", "draft"], name="content_schedule_draft"),
        ]


class PublishAttempt(TenantScopedModel):
    """Per-channel publishing attempt."""

    CHANNEL_FACEBOOK_PAGE = "facebook_page"
    CHANNEL_INSTAGRAM = "instagram"
    CHANNEL_CHOICES = [
        (CHANNEL_FACEBOOK_PAGE, "Facebook Page"),
        (CHANNEL_INSTAGRAM, "Instagram"),
    ]

    STATE_QUEUED = "queued"
    STATE_PREFLIGHT = "preflight"
    STATE_BLOCKED = "blocked"
    STATE_CONTAINER_CREATING = "container_creating"
    STATE_CONTAINER_PENDING = "container_pending"
    STATE_CONTAINER_READY = "container_ready"
    STATE_PUBLISHING = "publishing"
    STATE_PUBLISHED = "published"
    STATE_FAILED_RETRYABLE = "failed_retryable"
    STATE_FAILED_TERMINAL = "failed_terminal"
    STATE_CONTAINER_EXPIRED = "container_expired"
    STATE_CANCELLED = "cancelled"
    STATE_CHOICES = [
        (STATE_QUEUED, "Queued"),
        (STATE_PREFLIGHT, "Preflight"),
        (STATE_BLOCKED, "Blocked"),
        (STATE_CONTAINER_CREATING, "Container creating"),
        (STATE_CONTAINER_PENDING, "Container pending"),
        (STATE_CONTAINER_READY, "Container ready"),
        (STATE_PUBLISHING, "Publishing"),
        (STATE_PUBLISHED, "Published"),
        (STATE_FAILED_RETRYABLE, "Failed retryable"),
        (STATE_FAILED_TERMINAL, "Failed terminal"),
        (STATE_CONTAINER_EXPIRED, "Container expired"),
        (STATE_CANCELLED, "Cancelled"),
    ]

    schedule = models.ForeignKey(
        ContentSchedule, on_delete=models.CASCADE, related_name="publish_attempts"
    )
    draft = models.ForeignKey(
        ContentDraft, on_delete=models.CASCADE, related_name="publish_attempts"
    )
    version = models.ForeignKey(
        ContentDraftVersion, on_delete=models.CASCADE, related_name="publish_attempts"
    )
    publishing_identity = models.ForeignKey(
        PublishingIdentity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publish_attempts",
    )
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES)
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_QUEUED)
    attempt_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=128)
    correlation_id = models.CharField(max_length=128, blank=True)
    meta_container_id = models.CharField(max_length=128, blank=True)
    meta_container_created_at = models.DateTimeField(null=True, blank=True)
    meta_post_id = models.CharField(max_length=128, blank=True)
    failure_code = models.CharField(max_length=128, blank=True)
    failure_detail_safe = models.TextField(blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "state"], name="content_attempt_state"),
            models.Index(fields=["tenant", "channel"], name="content_attempt_channel"),
            models.Index(fields=["tenant", "next_retry_at"], name="content_attempt_retry"),
        ]
        unique_together = ("tenant", "idempotency_key")


class PublishedPost(TenantScopedModel):
    """Published organic post linked to originating draft/version."""

    CHANNEL_FACEBOOK_PAGE = "facebook_page"
    CHANNEL_INSTAGRAM = "instagram"
    CHANNEL_CHOICES = [
        (CHANNEL_FACEBOOK_PAGE, "Facebook Page"),
        (CHANNEL_INSTAGRAM, "Instagram"),
    ]

    REPORTING_PENDING = "pending"
    REPORTING_LINKED = "linked"
    REPORTING_UNAVAILABLE = "unavailable"
    REPORTING_FAILED = "failed"
    REPORTING_CHOICES = [
        (REPORTING_PENDING, "Pending"),
        (REPORTING_LINKED, "Linked"),
        (REPORTING_UNAVAILABLE, "Unavailable"),
        (REPORTING_FAILED, "Failed"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="published_posts"
    )
    draft = models.ForeignKey(
        ContentDraft, on_delete=models.CASCADE, related_name="published_posts"
    )
    version = models.ForeignKey(
        ContentDraftVersion, on_delete=models.CASCADE, related_name="published_posts"
    )
    publishing_identity = models.ForeignKey(
        PublishingIdentity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_posts",
    )
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES)
    meta_post_id = models.CharField(max_length=128)
    permalink = models.URLField(blank=True)
    published_at = models.DateTimeField()
    reporting_link_state = models.CharField(
        max_length=32, choices=REPORTING_CHOICES, default=REPORTING_PENDING
    )
    last_metrics_refresh_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-published_at",)
        indexes = [
            models.Index(fields=["tenant", "channel"], name="content_post_channel"),
            models.Index(fields=["tenant", "published_at"], name="content_post_published"),
        ]
        unique_together = ("tenant", "channel", "meta_post_id")


class OrganicPostMetricSnapshot(TenantScopedModel):
    """Aggregate-only organic post metric snapshot."""

    published_post = models.ForeignKey(
        PublishedPost, on_delete=models.CASCADE, related_name="metric_snapshots"
    )
    metric_date = models.DateField()
    channel = models.CharField(max_length=32, choices=PublishedPost.CHANNEL_CHOICES)
    impressions = models.BigIntegerField(default=0)
    reach = models.BigIntegerField(default=0)
    engagements = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    saves = models.BigIntegerField(default=0)
    shares = models.BigIntegerField(default=0)
    video_views = models.BigIntegerField(default=0)
    source = models.CharField(max_length=64)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-metric_date",)
        indexes = [
            models.Index(fields=["tenant", "metric_date"], name="content_metric_date"),
            models.Index(fields=["tenant", "channel"], name="content_metric_channel"),
        ]
        unique_together = (
            "tenant",
            "published_post",
            "metric_date",
            "channel",
            "source",
        )


class ContentExportArtifact(TenantScopedModel):
    """Persisted Content Ops export packet metadata."""

    TYPE_CONTENT_PLAN = "content_plan"
    TYPE_CHOICES = [
        (TYPE_CONTENT_PLAN, "Content plan"),
    ]

    FORMAT_JSON = "json"
    FORMAT_CHOICES = [
        (FORMAT_JSON, "JSON"),
    ]

    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="export_artifacts"
    )
    export_type = models.CharField(
        max_length=32, choices=TYPE_CHOICES, default=TYPE_CONTENT_PLAN
    )
    export_format = models.CharField(
        max_length=16, choices=FORMAT_CHOICES, default=FORMAT_JSON
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_COMPLETED
    )
    artifact_path = models.CharField(max_length=512, blank=True)
    item_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_export_artifacts",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "workspace"], name="content_export_ws"),
            models.Index(fields=["tenant", "status"], name="content_export_status"),
        ]


class AIUsageRecord(TenantScopedModel):
    """Per-generation AI provider token usage for metering and billing.

    One row is written per provider call that reports usage. Tokens are the
    billable unit; ``estimated_cost`` is a best-effort figure derived from the
    configured per-1k-token rate (0 unless a rate is set), so cost can also be
    recomputed downstream from a price table.
    """

    generation_job = models.ForeignKey(
        GenerationJob, on_delete=models.CASCADE, related_name="usage_records"
    )
    provider = models.CharField(max_length=64)
    model_name = models.CharField(max_length=128, blank=True)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    total_tokens = models.BigIntegerField(default=0)
    images = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="content_ai_usage_created"),
            models.Index(fields=["tenant", "provider"], name="content_ai_usage_provider"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"AIUsageRecord<{self.tenant_id}:{self.provider}:{self.total_tokens}>"


class RegionalAgentProfile(TenantScopedModel):
    """A regional AI content agent: locale, brand voice, and approved references.

    Each agent is scoped to a workspace and a region. Locale, language, and the
    scheduling timezone default from the region when left blank, so a Caribbean
    agent posts in en-JM/America/Jamaica and a Peru agent in es-PE/America/Lima.
    """

    REGION_CARIBBEAN = "caribbean"
    REGION_PERU_LATAM = "peru_latam"
    REGION_CHOICES = [
        (REGION_CARIBBEAN, "Caribbean"),
        (REGION_PERU_LATAM, "Peru / LATAM"),
    ]

    REGION_DEFAULTS = {
        REGION_CARIBBEAN: {
            "locale": "en-JM",
            "language": "English",
            "timezone": "America/Jamaica",
        },
        REGION_PERU_LATAM: {
            "locale": "es-PE",
            "language": "Spanish",
            "timezone": "America/Lima",
        },
    }

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="regional_agents"
    )
    name = models.CharField(max_length=255)
    region = models.CharField(max_length=32, choices=REGION_CHOICES)
    locale = models.CharField(max_length=16, blank=True)
    language = models.CharField(max_length=64, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    brand_voice = models.JSONField(default=dict, blank=True)
    required_terms = models.JSONField(default=list, blank=True)
    blocked_terms = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_regional_agents",
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["tenant", "workspace"], name="content_agent_ws"),
            models.Index(fields=["tenant", "region"], name="content_agent_region"),
        ]

    def save(self, *args, **kwargs):
        defaults = self.REGION_DEFAULTS.get(self.region, {})
        if not self.locale:
            self.locale = defaults.get("locale", "")
        if not self.language:
            self.language = defaults.get("language", "")
        if not self.timezone:
            self.timezone = defaults.get("timezone", "")
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"RegionalAgentProfile<{self.tenant_id}:{self.region}:{self.name}>"


class FooterPreset(TenantScopedModel):
    """Reusable footer content + deterministic render controls.

    The literal footer (website/contact/handles/tagline) is composited by the
    deterministic brand overlay — it is NEVER sent to the image model.
    """

    BAND_POSITION_BOTTOM = "bottom"
    BAND_POSITION_TOP = "top"
    BAND_POSITION_CHOICES = [
        (BAND_POSITION_BOTTOM, "Bottom"),
        (BAND_POSITION_TOP, "Top"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="footer_presets"
    )
    name = models.CharField(max_length=255)
    # Footer content fields.
    website = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    handles = models.JSONField(default=list, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    # Deterministic render controls (consumed by the overlay only).
    background_hex = models.CharField(max_length=7, blank=True)
    text_hex = models.CharField(max_length=7, blank=True)
    band_position = models.CharField(
        max_length=8, choices=BAND_POSITION_CHOICES, default=BAND_POSITION_BOTTOM
    )
    band_height_pct = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Band height as a fraction of canvas height (0–1).",
    )
    separator = models.CharField(max_length=8, blank=True, default=" • ")
    field_priority = models.JSONField(default=list, blank=True)
    uppercase_primary = models.BooleanField(default=False)
    locale = models.CharField(max_length=16, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_footer_presets",
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["tenant", "workspace", "is_active"], name="content_footer_ws"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"FooterPreset<{self.tenant_id}:{self.name}>"


class BrandKit(TenantScopedModel):
    """Standing brand instructions + the default logo (and light/dark variants).

    Scoped to a workspace, optionally to a client or a post type. The default
    logo is swappable; light/dark variants let the overlay pick by background
    luminance. Standing instructions compose into the prompt like brand voice;
    the logo is overlay-only and never a generation input.
    """

    SCOPE_WORKSPACE = "workspace"
    SCOPE_CLIENT = "client"
    SCOPE_POST_TYPE = "post_type"
    SCOPE_CHOICES = [
        (SCOPE_WORKSPACE, "Workspace"),
        (SCOPE_CLIENT, "Client"),
        (SCOPE_POST_TYPE, "Post type"),
    ]

    LOGO_PLACEMENT_TOP_LEFT = "top_left"
    LOGO_PLACEMENT_TOP_RIGHT = "top_right"
    LOGO_PLACEMENT_BOTTOM_LEFT = "bottom_left"
    LOGO_PLACEMENT_BOTTOM_RIGHT = "bottom_right"
    LOGO_PLACEMENT_CENTER = "center"
    LOGO_PLACEMENT_CHOICES = [
        (LOGO_PLACEMENT_TOP_LEFT, "Top left"),
        (LOGO_PLACEMENT_TOP_RIGHT, "Top right"),
        (LOGO_PLACEMENT_BOTTOM_LEFT, "Bottom left"),
        (LOGO_PLACEMENT_BOTTOM_RIGHT, "Bottom right"),
        (LOGO_PLACEMENT_CENTER, "Center"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="brand_kits"
    )
    client = models.ForeignKey(
        "integrations.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_brand_kits",
    )
    name = models.CharField(max_length=255)
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default=SCOPE_WORKSPACE)
    post_type = models.CharField(max_length=64, blank=True)
    standing_instructions = models.JSONField(default=dict, blank=True)
    visual_config = models.JSONField(default=dict, blank=True)
    required_terms = models.JSONField(default=list, blank=True)
    blocked_terms = models.JSONField(default=list, blank=True)
    # Default logo (swap target) + explicit light/dark variants.
    default_logo = models.ForeignKey(
        MediaAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_brand_kits",
    )
    logo_light = models.ForeignKey(
        MediaAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    logo_dark = models.ForeignKey(
        MediaAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    logo_placement = models.CharField(
        max_length=16,
        choices=LOGO_PLACEMENT_CHOICES,
        default=LOGO_PLACEMENT_BOTTOM_RIGHT,
    )
    default_footer_preset = models.ForeignKey(
        "FooterPreset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brand_kits",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_brand_kits",
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["tenant", "workspace", "is_active"], name="content_brandkit_ws"),
            models.Index(fields=["tenant", "client"], name="content_brandkit_client"),
            models.Index(fields=["tenant", "scope", "post_type"], name="content_brandkit_scope"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"BrandKit<{self.tenant_id}:{self.name}>"


class MediaAssetCollection(TenantScopedModel):
    """A curated, browsable library of assets (logos or references)."""

    PURPOSE_GENERAL = "general"
    PURPOSE_LOGO_LIBRARY = "logo_library"
    PURPOSE_REFERENCE_LIBRARY = "reference_library"
    PURPOSE_CHOICES = [
        (PURPOSE_GENERAL, "General"),
        (PURPOSE_LOGO_LIBRARY, "Logo library"),
        (PURPOSE_REFERENCE_LIBRARY, "Reference library"),
    ]

    workspace = models.ForeignKey(
        ContentWorkspace, on_delete=models.CASCADE, related_name="asset_collections"
    )
    name = models.CharField(max_length=255)
    purpose = models.CharField(
        max_length=24, choices=PURPOSE_CHOICES, default=PURPOSE_GENERAL
    )
    description = models.TextField(blank=True)
    region = models.CharField(max_length=32, blank=True)
    locale = models.CharField(max_length=16, blank=True)
    assets = models.ManyToManyField(
        MediaAsset,
        through="MediaAssetCollectionItem",
        related_name="collections",
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_asset_collections",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["tenant", "workspace", "purpose"], name="content_coll_ws"),
        ]
        unique_together = ("tenant", "workspace", "name")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"MediaAssetCollection<{self.tenant_id}:{self.name}>"


class MediaAssetCollectionItem(TenantScopedModel):
    """Tenant-scoped through row: an asset's membership + order in a collection."""

    collection = models.ForeignKey(
        MediaAssetCollection, on_delete=models.CASCADE, related_name="items"
    )
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="collection_items"
    )
    order = models.PositiveIntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ("collection_id", "order")
        unique_together = ("tenant", "collection", "asset")
        indexes = [
            models.Index(fields=["tenant", "collection"], name="content_coll_item"),
        ]


class MediaAssetTag(TenantScopedModel):
    """Reusable tenant-scoped tag vocabulary for assets."""

    workspace = models.ForeignKey(
        ContentWorkspace,
        on_delete=models.CASCADE,
        related_name="asset_tags",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64)
    assets = models.ManyToManyField(
        MediaAsset,
        through="MediaAssetTagAssignment",
        related_name="tags",
        blank=True,
    )

    class Meta:
        ordering = ("label",)
        unique_together = ("tenant", "workspace", "slug")
        indexes = [
            models.Index(fields=["tenant", "slug"], name="content_tag_slug"),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"MediaAssetTag<{self.tenant_id}:{self.slug}>"


class MediaAssetTagAssignment(TenantScopedModel):
    """Tenant-scoped through row linking a tag to an asset."""

    tag = models.ForeignKey(
        MediaAssetTag, on_delete=models.CASCADE, related_name="assignments"
    )
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="tag_assignments"
    )

    class Meta:
        unique_together = ("tenant", "tag", "asset")
        indexes = [
            models.Index(fields=["tenant", "asset"], name="content_tag_assign"),
        ]
