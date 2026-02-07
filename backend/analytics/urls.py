"""Router configuration for analytics metadata APIs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdSetViewSet,
    AdViewSet,
    CampaignViewSet,
    ParishGeometryView,
    RawPerformanceRecordViewSet,
)
from .web_views import GA4WebInsightsView, SearchConsoleInsightsView

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="analytics-campaign")
router.register(r"adsets", AdSetViewSet, basename="analytics-adset")
router.register(r"ads", AdViewSet, basename="analytics-ad")
router.register(
    r"performance-records",
    RawPerformanceRecordViewSet,
    basename="analytics-performance-record",
)

urlpatterns = [
    path("parish-geometry/", ParishGeometryView.as_view(), name="analytics-parish-geometry"),
    path("web/ga4/", GA4WebInsightsView.as_view(), name="analytics-web-ga4"),
    path(
        "web/search-console/",
        SearchConsoleInsightsView.as_view(),
        name="analytics-web-search-console",
    ),
    path("", include(router.urls)),
]
