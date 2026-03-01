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
from .google_ads_views import (
    GoogleAdsAdsView,
    GoogleAdsAdGroupsView,
    GoogleAdsAccountAssignmentViewSet,
    GoogleAdsAssetsView,
    GoogleAdsBreakdownsView,
    GoogleAdsBudgetPacingView,
    GoogleAdsCampaignDetailView,
    GoogleAdsCampaignListView,
    GoogleAdsChannelPerformanceView,
    GoogleAdsChangeEventsView,
    GoogleAdsConversionsByActionView,
    GoogleAdsExecutiveView,
    GoogleAdsExportCreateView,
    GoogleAdsExportDownloadView,
    GoogleAdsExportStatusView,
    GoogleAdsKeywordsView,
    GoogleAdsPmaxAssetGroupsView,
    GoogleAdsRecommendationsView,
    GoogleAdsSavedViewViewSet,
    GoogleAdsSearchTermInsightsView,
    GoogleAdsSearchTermsView,
    GoogleAdsWorkspaceSummaryView,
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
router.register(
    r"google-ads/saved-views",
    GoogleAdsSavedViewViewSet,
    basename="analytics-google-ads-saved-view",
)
router.register(
    r"google-ads/account-assignments",
    GoogleAdsAccountAssignmentViewSet,
    basename="analytics-google-ads-account-assignment",
)

urlpatterns = [
    path(
        "google-ads/workspace/summary/",
        GoogleAdsWorkspaceSummaryView.as_view(),
        name="google-ads-workspace-summary",
    ),
    path("google-ads/executive/", GoogleAdsExecutiveView.as_view(), name="google-ads-executive"),
    path("google-ads/campaigns/", GoogleAdsCampaignListView.as_view(), name="google-ads-campaigns"),
    path(
        "google-ads/campaigns/<str:campaign_id>/",
        GoogleAdsCampaignDetailView.as_view(),
        name="google-ads-campaign-detail",
    ),
    path("google-ads/channels/", GoogleAdsChannelPerformanceView.as_view(), name="google-ads-channels"),
    path("google-ads/ad-groups/", GoogleAdsAdGroupsView.as_view(), name="google-ads-ad-groups"),
    path("google-ads/ads/", GoogleAdsAdsView.as_view(), name="google-ads-ads"),
    path("google-ads/assets/", GoogleAdsAssetsView.as_view(), name="google-ads-assets"),
    path("google-ads/keywords/", GoogleAdsKeywordsView.as_view(), name="google-ads-keywords"),
    path("google-ads/search-terms/", GoogleAdsSearchTermsView.as_view(), name="google-ads-search-terms"),
    path(
        "google-ads/search-term-insights/",
        GoogleAdsSearchTermInsightsView.as_view(),
        name="google-ads-search-term-insights",
    ),
    path(
        "google-ads/pmax/asset-groups/",
        GoogleAdsPmaxAssetGroupsView.as_view(),
        name="google-ads-pmax-asset-groups",
    ),
    path("google-ads/breakdowns/", GoogleAdsBreakdownsView.as_view(), name="google-ads-breakdowns"),
    path(
        "google-ads/conversions/actions/",
        GoogleAdsConversionsByActionView.as_view(),
        name="google-ads-conversions-actions",
    ),
    path(
        "google-ads/budgets/pacing/",
        GoogleAdsBudgetPacingView.as_view(),
        name="google-ads-budgets-pacing",
    ),
    path(
        "google-ads/change-events/",
        GoogleAdsChangeEventsView.as_view(),
        name="google-ads-change-events",
    ),
    path(
        "google-ads/recommendations/",
        GoogleAdsRecommendationsView.as_view(),
        name="google-ads-recommendations",
    ),
    path("google-ads/exports/", GoogleAdsExportCreateView.as_view(), name="google-ads-exports"),
    path(
        "google-ads/exports/<uuid:job_id>/",
        GoogleAdsExportStatusView.as_view(),
        name="google-ads-export-status",
    ),
    path(
        "google-ads/exports/<uuid:job_id>/download/",
        GoogleAdsExportDownloadView.as_view(),
        name="google-ads-export-download",
    ),
    path("parish-geometry/", ParishGeometryView.as_view(), name="analytics-parish-geometry"),
    path("web/ga4/", GA4WebInsightsView.as_view(), name="analytics-web-ga4"),
    path(
        "web/search-console/",
        SearchConsoleInsightsView.as_view(),
        name="analytics-web-search-console",
    ),
    path("", include(router.urls)),
]
