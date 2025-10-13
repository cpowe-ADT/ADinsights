from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.schemas import get_schema_view

from alerts.views import AlertRunViewSet
from analytics.views import AdapterListView, CombinedMetricsView, MetricsExportView, MetricsView
from accounts.views import (
    AuditLogViewSet,
    MeView,
    RoleAssignmentView,
    TenantTokenObtainPairView,
    TenantViewSet,
    UserRoleViewSet,
    UserViewSet,
)
from integrations.views import (
    AirbyteConnectionViewSet,
    AlertRuleDefinitionViewSet,
    CampaignBudgetViewSet,
    PlatformCredentialViewSet,
)
from . import views as core_views

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
router.register(r"tenants", TenantViewSet, basename="tenant")
router.register(r"users", UserViewSet, basename="user")
router.register(r"user-roles", UserRoleViewSet, basename="userrole")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"alerts/runs", AlertRunViewSet, basename="alert-run")

admin_router = DefaultRouter()
admin_router.register(r"budgets", CampaignBudgetViewSet, basename="campaignbudget")
admin_router.register(r"alerts", AlertRuleDefinitionViewSet, basename="alertruledefinition")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="jwt_token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="jwt_token_refresh"),
    path(
        "api/auth/login/", TenantTokenObtainPairView.as_view(), name="token_obtain_pair"
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
    path("api/metrics/", MetricsView.as_view(), name="metrics"),
    path("api/metrics/combined/", CombinedMetricsView.as_view(), name="metrics-combined"),
    path("api/export/metrics.csv", MetricsExportView.as_view(), name="metrics-export"),
    path("metrics/app/", core_views.prometheus_metrics, name="metrics-app"),
    path("api/", include(router.urls)),
    path("api/admin/", include(admin_router.urls)),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
