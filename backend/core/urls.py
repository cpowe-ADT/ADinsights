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
from analytics.meta_views import (
    MetaAccountsListView,
    MetaCampaignListView,
    MetaAdSetListView,
    MetaAdsListView,
    MetaInsightsListView,
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
    MetaOAuthExchangeView,
    MetaOAuthStartView,
    MetaSetupView,
    MetaPageConnectView,
    MetaProvisionView,
    MetaSystemTokenView,
    MetaLogoutView,
    MetaSyncStateView,
    SocialConnectionStatusView,
    MetaSyncView,
    PlatformCredentialViewSet,
)
from integrations.meta_page_views import (
    MetaOAuthCallbackView,
    MetaPagesView,
    MetaPageSelectView,
    MetaPageRefreshView,
    MetaPageOverviewView,
    MetaPageTimeseriesView,
    MetaPagePostsView,
    MetaPostTimeseriesView,
)
from integrations.page_insights_views import (
    MetaConnectCallbackAliasView,
    MetaConnectStartAliasView,
    MetaPageInsightsSyncView,
    MetaPageOverviewInsightsView,
    MetaPagePostsInsightsView,
    MetaPagesInsightsListView,
    MetaPostDetailInsightsView,
    MetaPostTimeseriesInsightsView,
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
    path("api/meta/accounts/", MetaAccountsListView.as_view(), name="meta-accounts"),
    path("api/meta/campaigns/", MetaCampaignListView.as_view(), name="meta-campaigns"),
    path("api/meta/adsets/", MetaAdSetListView.as_view(), name="meta-adsets"),
    path("api/meta/ads/", MetaAdsListView.as_view(), name="meta-ads"),
    path("api/meta/insights/", MetaInsightsListView.as_view(), name="meta-insights"),
    path(
        "api/integrations/meta/setup/",
        MetaSetupView.as_view(),
        name="meta-setup",
    ),
    path(
        "api/integrations/meta/oauth/start/",
        MetaOAuthStartView.as_view(),
        name="meta-oauth-start",
    ),
    path(
        "api/meta/connect/start/",
        MetaConnectStartAliasView.as_view(),
        name="meta-connect-start",
    ),
    path(
        "api/integrations/meta/oauth/exchange/",
        MetaOAuthExchangeView.as_view(),
        name="meta-oauth-exchange",
    ),
    path(
        "api/meta/connect/callback/",
        MetaConnectCallbackAliasView.as_view(),
        name="meta-connect-callback",
    ),
    path(
        "api/integrations/meta/oauth/callback/",
        MetaOAuthCallbackView.as_view(),
        name="meta-oauth-callback",
    ),
    path(
        "api/integrations/meta/pages/",
        MetaPagesView.as_view(),
        name="meta-pages",
    ),
    path(
        "api/integrations/meta/pages/<str:page_id>/select/",
        MetaPageSelectView.as_view(),
        name="meta-page-select",
    ),
    path(
        "api/integrations/meta/pages/connect/",
        MetaPageConnectView.as_view(),
        name="meta-page-connect",
    ),
    path(
        "api/integrations/meta/provision/",
        MetaProvisionView.as_view(),
        name="meta-provision",
    ),
    path(
        "api/integrations/meta/system-token/",
        MetaSystemTokenView.as_view(),
        name="meta-system-token",
    ),
    path(
        "api/integrations/meta/sync/",
        MetaSyncView.as_view(),
        name="meta-sync",
    ),
    path(
        "api/integrations/meta/sync-state/",
        MetaSyncStateView.as_view(),
        name="meta-sync-state",
    ),
    path(
        "api/metrics/meta/pages/<str:page_id>/refresh/",
        MetaPageRefreshView.as_view(),
        name="meta-page-refresh",
    ),
    path(
        "api/metrics/meta/pages/<str:page_id>/overview/",
        MetaPageOverviewView.as_view(),
        name="meta-page-overview",
    ),
    path(
        "api/metrics/meta/pages/<str:page_id>/timeseries/",
        MetaPageTimeseriesView.as_view(),
        name="meta-page-timeseries",
    ),
    path(
        "api/metrics/meta/pages/<str:page_id>/posts/",
        MetaPagePostsView.as_view(),
        name="meta-page-posts",
    ),
    path(
        "api/metrics/meta/posts/<str:post_id>/timeseries/",
        MetaPostTimeseriesView.as_view(),
        name="meta-post-timeseries",
    ),
    path(
        "api/meta/pages/",
        MetaPagesInsightsListView.as_view(),
        name="meta-pages-insights-list",
    ),
    path(
        "api/meta/pages/<str:page_id>/sync/",
        MetaPageInsightsSyncView.as_view(),
        name="meta-page-insights-sync",
    ),
    path(
        "api/meta/pages/<str:page_id>/overview/",
        MetaPageOverviewInsightsView.as_view(),
        name="meta-page-insights-overview",
    ),
    path(
        "api/meta/pages/<str:page_id>/posts/",
        MetaPagePostsInsightsView.as_view(),
        name="meta-page-insights-posts",
    ),
    path(
        "api/meta/posts/<str:post_id>/",
        MetaPostDetailInsightsView.as_view(),
        name="meta-post-insights-detail",
    ),
    path(
        "api/meta/posts/<str:post_id>/timeseries/",
        MetaPostTimeseriesInsightsView.as_view(),
        name="meta-post-insights-timeseries",
    ),
    path(
        "api/integrations/meta/logout/",
        MetaLogoutView.as_view(),
        name="meta-logout",
    ),
    path(
        "api/integrations/social/status/",
        SocialConnectionStatusView.as_view(),
        name="social-connection-status",
    ),
    path("metrics/app/", core_views.prometheus_metrics, name="metrics-app"),
    path("api/", include(router.urls)),
    path("api/airbyte/webhook/", AirbyteWebhookView.as_view(), name="airbyte-webhook"),
    path("api/admin/", include(admin_router.urls)),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
