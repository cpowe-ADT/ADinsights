from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view

from alerts.views import AlertRunViewSet
from analytics.phase2_views import (
    AISummaryViewSet,
    AlertsViewSet,
    DashboardLibraryView,
    HealthOverviewView,
    ReportDefinitionViewSet,
    SyncHealthView,
)
from analytics.views import (
    AdapterListView,
    UploadMetricsView,
    AggregateSnapshotView,
    CombinedMetricsView,
    DemoSeedView,
    MetricsExportView,
    MetricsView,
)
from accounts.views import (
    AuditLogViewSet,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RateLimitedTokenObtainPairView,
    RateLimitedTokenRefreshView,
    TenantSwitchView,
    RoleAssignmentView,
    TenantTokenObtainPairView,
    TenantViewSet,
    UserRoleViewSet,
    UserViewSet,
    ServiceAccountKeyViewSet,
)
from integrations.views import (
    AirbyteConnectionViewSet,
    AirbyteWebhookView,
    AlertRuleDefinitionViewSet,
    CampaignBudgetViewSet,
    IntegrationDisconnectView,
    IntegrationJobsView,
    IntegrationOAuthCallbackView,
    IntegrationReconnectView,
    IntegrationOAuthStartView,
    IntegrationProvisionView,
    IntegrationStatusView,
    IntegrationSyncView,
    MetaOAuthExchangeView,
    MetaOAuthStartView,
    MetaPageConnectView,
    PlatformCredentialViewSet,
)
from . import views as core_views
from .viewsets import AirbyteTelemetryViewSet

router = DefaultRouter()
router.register(
    r"platform-credentials",
    PlatformCredentialViewSet,
    basename="platformcredential",
)
router.register(
    r"airbyte/connections",
    AirbyteConnectionViewSet,
    basename="airbyte-connection",
)
router.register(
    r"airbyte/telemetry",
    AirbyteTelemetryViewSet,
    basename="airbyte-telemetry",
)
router.register(r"tenants", TenantViewSet, basename="tenant")
router.register(r"users", UserViewSet, basename="user")
router.register(r"user-roles", UserRoleViewSet, basename="userrole")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"alerts/runs", AlertRunViewSet, basename="alert-run")
router.register(r"alerts", AlertsViewSet, basename="alerts")
router.register(r"reports", ReportDefinitionViewSet, basename="report-definition")
router.register(r"summaries", AISummaryViewSet, basename="ai-summary")
router.register(r"service-accounts", ServiceAccountKeyViewSet, basename="service-account")

admin_router = DefaultRouter()
admin_router.register(r"budgets", CampaignBudgetViewSet, basename="campaignbudget")
admin_router.register(r"alerts", AlertRuleDefinitionViewSet, basename="alertruledefinition")

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/token/",
        RateLimitedTokenObtainPairView.as_view(),
        name="jwt_token_obtain_pair",
    ),
    path(
        "api/token/refresh/",
        RateLimitedTokenRefreshView.as_view(),
        name="jwt_token_refresh",
    ),
    path(
        "api/auth/login/", TenantTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path(
        "api/auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "api/auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "api/auth/switch-tenant/",
        TenantSwitchView.as_view(),
        name="tenant-switch",
    ),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/roles/assign/", RoleAssignmentView.as_view(), name="role-assign"),
    path("api/health/", core_views.health, name="health"),
    path("api/health/version/", core_views.health_version, name="health-version"),
    path("api/health/airbyte/", core_views.airbyte_health, name="airbyte-health"),
    path("api/health/dbt/", core_views.dbt_health, name="dbt-health"),
    path("api/timezone/", core_views.timezone_view, name="timezone"),
    path(
        "api/schema/",
        get_schema_view(
            title="ADinsights API",
            description="OpenAPI schema for the ADinsights backend",
            version="1.0.0",
            public=True,
            permission_classes=[AllowAny],
        ),
        name="api-schema",
    ),
    path("api/adapters/", AdapterListView.as_view(), name="adapter-list"),
    path(
        "api/integrations/meta/oauth/start/",
        MetaOAuthStartView.as_view(),
        name="meta-oauth-start",
    ),
    path(
        "api/integrations/meta/oauth/exchange/",
        MetaOAuthExchangeView.as_view(),
        name="meta-oauth-exchange",
    ),
    path(
        "api/integrations/meta/pages/connect/",
        MetaPageConnectView.as_view(),
        name="meta-page-connect",
    ),
    path(
        "api/integrations/<str:provider>/oauth/start/",
        IntegrationOAuthStartView.as_view(),
        name="integration-oauth-start",
    ),
    path(
        "api/integrations/<str:provider>/oauth/callback/",
        IntegrationOAuthCallbackView.as_view(),
        name="integration-oauth-callback",
    ),
    path(
        "api/integrations/<str:provider>/reconnect/",
        IntegrationReconnectView.as_view(),
        name="integration-reconnect",
    ),
    path(
        "api/integrations/<str:provider>/disconnect/",
        IntegrationDisconnectView.as_view(),
        name="integration-disconnect",
    ),
    path(
        "api/integrations/<str:provider>/provision/",
        IntegrationProvisionView.as_view(),
        name="integration-provision",
    ),
    path(
        "api/integrations/<str:provider>/sync/",
        IntegrationSyncView.as_view(),
        name="integration-sync",
    ),
    path(
        "api/integrations/<str:provider>/status/",
        IntegrationStatusView.as_view(),
        name="integration-status",
    ),
    path(
        "api/integrations/<str:provider>/jobs/",
        IntegrationJobsView.as_view(),
        name="integration-jobs",
    ),
    path(
        "api/dashboards/library/",
        DashboardLibraryView.as_view(),
        name="dashboard-library",
    ),
    path("api/uploads/metrics/", UploadMetricsView.as_view(), name="metrics-upload"),
    path("api/metrics/", MetricsView.as_view(), name="metrics"),
    path("api/metrics/combined/", CombinedMetricsView.as_view(), name="metrics-combined"),
    path("api/demo/seed/", DemoSeedView.as_view(), name="demo-seed"),
    path(
        "api/dashboards/aggregate-snapshot/",
        AggregateSnapshotView.as_view(),
        name="dashboard-aggregate-snapshot",
    ),
    path("api/export/metrics.csv", MetricsExportView.as_view(), name="metrics-export"),
    path("api/ops/sync-health/", SyncHealthView.as_view(), name="ops-sync-health"),
    path(
        "api/ops/health-overview/",
        HealthOverviewView.as_view(),
        name="ops-health-overview",
    ),
    path("api/analytics/", include("analytics.urls")),
    path("metrics/app/", core_views.prometheus_metrics, name="metrics-app"),
    path("api/", include(router.urls)),
    path("api/airbyte/webhook/", AirbyteWebhookView.as_view(), name="airbyte-webhook"),
    path("api/admin/", include(admin_router.urls)),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
