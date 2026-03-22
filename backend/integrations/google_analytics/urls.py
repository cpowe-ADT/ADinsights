from django.urls import path
from integrations.google_analytics.views import (
    GoogleAnalyticsSetupView,
    GoogleAnalyticsOAuthStartView,
    GoogleAnalyticsOAuthExchangeView,
    GoogleAnalyticsPropertiesView,
    GoogleAnalyticsProvisionView,
    GoogleAnalyticsStatusView,
)

urlpatterns = [
    path("setup/", GoogleAnalyticsSetupView.as_view(), name="ga4-setup"),
    path("oauth/start/", GoogleAnalyticsOAuthStartView.as_view(), name="ga4-oauth-start"),
    path("oauth/exchange/", GoogleAnalyticsOAuthExchangeView.as_view(), name="ga4-oauth-exchange"),
    path("properties/", GoogleAnalyticsPropertiesView.as_view(), name="ga4-properties"),
    path("provision/", GoogleAnalyticsProvisionView.as_view(), name="ga4-provision"),
    path("status/", GoogleAnalyticsStatusView.as_view(), name="ga4-status"),
]
