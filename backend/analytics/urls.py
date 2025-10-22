"""Router configuration for analytics metadata APIs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdSetViewSet,
    AdViewSet,
    CampaignViewSet,
    RawPerformanceRecordViewSet,
)

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="analytics-campaign")
router.register(r"adsets", AdSetViewSet, basename="analytics-adset")
router.register(r"ads", AdViewSet, basename="analytics-ad")
router.register(
    r"performance-records",
    RawPerformanceRecordViewSet,
    basename="analytics-performance-record",
)

urlpatterns = [path("", include(router.urls))]
