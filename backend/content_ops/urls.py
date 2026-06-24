"""Content Operations API routes."""

from __future__ import annotations

from django.urls import include, path

from core.routers import ADinsightsDefaultRouter

from .views import (
    ApprovalDecisionViewSet,
    ApprovalRequestViewSet,
    ContentBriefViewSet,
    ContentDraftVersionViewSet,
    ContentDraftViewSet,
    ContentExportArtifactViewSet,
    ContentOpsContentPlanExportView,
    ContentOpsPublicMediaView,
    ContentOpsReadinessView,
    ContentOpsReportOverviewView,
    ContentOpsReportPostsView,
    ContentScheduleViewSet,
    ContentWorkspaceViewSet,
    GenerationJobViewSet,
    MediaAssetViewSet,
    OrganicPostMetricSnapshotViewSet,
    PublishedPostViewSet,
    PublishingIdentityViewSet,
    PublishAttemptViewSet,
    RegionalAgentProfileViewSet,
)


router = ADinsightsDefaultRouter()
router.register(r"workspaces", ContentWorkspaceViewSet, basename="content-workspace")
router.register(
    r"regional-agents",
    RegionalAgentProfileViewSet,
    basename="content-regional-agent",
)
router.register(
    r"publishing-identities",
    PublishingIdentityViewSet,
    basename="content-publishing-identity",
)
router.register(r"briefs", ContentBriefViewSet, basename="content-brief")
router.register(
    r"generation-jobs", GenerationJobViewSet, basename="content-generation-job"
)
router.register(r"assets", MediaAssetViewSet, basename="content-asset")
router.register(r"exports", ContentExportArtifactViewSet, basename="content-export")
router.register(r"drafts", ContentDraftViewSet, basename="content-draft")
router.register(
    r"versions", ContentDraftVersionViewSet, basename="content-draft-version"
)
router.register(
    r"approval-requests",
    ApprovalRequestViewSet,
    basename="content-approval-request",
)
router.register(
    r"approval-decisions",
    ApprovalDecisionViewSet,
    basename="content-approval-decision",
)
router.register(r"schedules", ContentScheduleViewSet, basename="content-schedule")
router.register(
    r"publishing/attempts",
    PublishAttemptViewSet,
    basename="content-publish-attempt",
)
router.register(
    r"published-posts",
    PublishedPostViewSet,
    basename="content-published-post",
)
router.register(
    r"metric-snapshots",
    OrganicPostMetricSnapshotViewSet,
    basename="content-metric-snapshot",
)


urlpatterns = [
    path("readiness/", ContentOpsReadinessView.as_view(), name="content-ops-readiness"),
    path(
        "reports/overview/",
        ContentOpsReportOverviewView.as_view(),
        name="content-ops-report-overview",
    ),
    path(
        "reports/posts/",
        ContentOpsReportPostsView.as_view(),
        name="content-ops-report-posts",
    ),
    path(
        "exports/content-plan/",
        ContentOpsContentPlanExportView.as_view(),
        name="content-ops-content-plan-export",
    ),
    path(
        "public-media/<uuid:asset_id>/",
        ContentOpsPublicMediaView.as_view(),
        name="content-ops-public-media",
    ),
    path("", include(router.urls)),
]
