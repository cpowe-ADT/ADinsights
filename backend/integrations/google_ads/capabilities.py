from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class GoogleAdsCapabilityBundle:
    key: str
    title: str
    description: str
    services: tuple[str, ...]
    resources: tuple[str, ...]


DEFAULT_CAPABILITY_BUNDLES: tuple[GoogleAdsCapabilityBundle, ...] = (
    GoogleAdsCapabilityBundle(
        key="oauth_and_discovery",
        title="OAuth and account discovery",
        description=(
            "Initial login and account graph discovery so a tenant can pick accessible "
            "Google Ads customer IDs safely."
        ),
        services=(
            "CustomerService",
            "CustomerClientLinkService",
            "CustomerManagerLinkService",
            "GoogleAdsFieldService",
        ),
        resources=(
            "Customer",
            "CustomerClient",
            "CustomerManagerLink",
        ),
    ),
    GoogleAdsCapabilityBundle(
        key="dashboard_reporting",
        title="Dashboard reporting",
        description=(
            "Read-only reporting surfaces for campaign, ad group, creative, and geo "
            "dashboard cards."
        ),
        services=(
            "GoogleAdsService",
            "CampaignService",
            "AdGroupService",
            "AdGroupAdService",
            "GeoTargetConstantService",
        ),
        resources=(
            "Campaign",
            "AdGroup",
            "AdGroupAd",
            "GeographicView",
            "CampaignSearchTermView",
        ),
    ),
    GoogleAdsCapabilityBundle(
        key="conversion_measurement",
        title="Conversion and attribution",
        description=(
            "Upload and reconcile conversions while preserving campaign-level analytics "
            "for ROI reporting."
        ),
        services=(
            "ConversionActionService",
            "ConversionUploadService",
            "ConversionAdjustmentUploadService",
            "ConversionGoalCampaignConfigService",
        ),
        resources=(
            "ConversionAction",
            "ConversionGoalCampaignConfig",
        ),
    ),
    GoogleAdsCapabilityBundle(
        key="optimization_and_recommendations",
        title="Optimization and recommendations",
        description=(
            "Optional phase for budget optimization, recommendation reviews, and "
            "automated tuning paths."
        ),
        services=(
            "CampaignBudgetService",
            "BiddingStrategyService",
            "RecommendationService",
            "RecommendationSubscriptionService",
        ),
        resources=(
            "CampaignBudget",
            "BiddingStrategy",
            "Recommendation",
            "RecommendationSubscription",
        ),
    ),
)


def required_services_for_capabilities(capability_keys: Iterable[str] | None = None) -> list[str]:
    if capability_keys is None:
        bundles = DEFAULT_CAPABILITY_BUNDLES
    else:
        selected = set(capability_keys)
        bundles = tuple(bundle for bundle in DEFAULT_CAPABILITY_BUNDLES if bundle.key in selected)

    services: set[str] = set()
    for bundle in bundles:
        services.update(bundle.services)
    return sorted(services)
