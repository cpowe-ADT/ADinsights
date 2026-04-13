"""Static fake adapter to keep the UI unblocked during development."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from django.utils import timezone

from .base import AdapterInterface, MetricsAdapter, get_default_interfaces


class FakeAdapter(MetricsAdapter):
    """Return deterministic demo payloads that mirror the QA fixtures."""

    key = "fake"
    name = "Demo Data"
    description = "Static dataset for demos and local development."
    interfaces: tuple[AdapterInterface, ...] = get_default_interfaces()

    _PAYLOAD: Mapping[str, Any] = {
        "campaign": {
            "summary": {
                "currency": "USD",
                "totalSpend": 1190,
                "totalImpressions": 282000,
                "totalClicks": 9700,
                "totalConversions": 355,
                "averageRoas": 3.6,
            },
            "trend": [
                {
                    "date": "2024-09-01",
                    "spend": 540,
                    "conversions": 120,
                    "clicks": 3400,
                    "impressions": 120000,
                },
                {
                    "date": "2024-09-02",
                    "spend": 430,
                    "conversions": 140,
                    "clicks": 4200,
                    "impressions": 94000,
                },
                {
                    "date": "2024-09-03",
                    "spend": 220,
                    "conversions": 95,
                    "clicks": 2100,
                    "impressions": 68000,
                },
            ],
            "rows": [
                {
                    "id": "cmp_awareness",
                    "name": "Awareness Boost",
                    "platform": "Meta",
                    "status": "Active",
                    "parishes": ["Kingston"],
                    "spend": 540,
                    "impressions": 120000,
                    "clicks": 3400,
                    "conversions": 120,
                    "roas": 3.5,
                    "ctr": 0.0283,
                    "cpc": 0.16,
                    "cpm": 4.5,
                    "startDate": "2024-08-01",
                    "endDate": "2024-09-30",
                },
                {
                    "id": "cmp_search",
                    "name": "Search Capture",
                    "platform": "Google Ads",
                    "status": "Active",
                    "parishes": ["St James"],
                    "spend": 430,
                    "impressions": 94000,
                    "clicks": 4200,
                    "conversions": 140,
                    "roas": 4.1,
                    "ctr": 0.0447,
                    "cpc": 0.1,
                    "cpm": 4.57,
                    "startDate": "2024-08-05",
                    "endDate": "2024-09-28",
                },
                {
                    "id": "cmp_genz",
                    "name": "GenZ Launch",
                    "platform": "TikTok",
                    "status": "Learning",
                    "parishes": ["St Andrew"],
                    "spend": 220,
                    "impressions": 68000,
                    "clicks": 2100,
                    "conversions": 95,
                    "roas": 3.2,
                    "ctr": 0.0309,
                    "cpc": 0.1,
                    "cpm": 3.24,
                    "startDate": "2024-08-18",
                    "endDate": "2024-10-02",
                },
            ],
        },
        "creative": [
            {
                "id": "cr_awareness_video",
                "name": "Awareness Video",
                "campaignId": "cmp_awareness",
                "campaignName": "Awareness Boost",
                "platform": "Meta",
                "parishes": ["Kingston"],
                "spend": 180,
                "impressions": 58000,
                "clicks": 1500,
                "conversions": 48,
                "roas": 2.8,
                "ctr": 0.0259,
            },
            {
                "id": "cr_search_carousel",
                "name": "Search Carousel",
                "campaignId": "cmp_search",
                "campaignName": "Search Capture",
                "platform": "Google Ads",
                "parishes": ["St James"],
                "spend": 140,
                "impressions": 36000,
                "clicks": 1320,
                "conversions": 52,
                "roas": 3.6,
                "ctr": 0.0367,
            },
        ],
        "budget": [
            {
                "id": "budget_awareness",
                "campaignName": "Awareness Boost",
                "parishes": ["Kingston"],
                "monthlyBudget": 800,
                "spendToDate": 540,
                "projectedSpend": 760,
                "pacingPercent": 95,
                "startDate": "2024-08-01",
                "endDate": "2024-09-30",
            },
            {
                "id": "budget_search",
                "campaignName": "Search Capture",
                "parishes": ["St James"],
                "monthlyBudget": 700,
                "spendToDate": 430,
                "projectedSpend": 680,
                "pacingPercent": 97,
                "startDate": "2024-08-05",
                "endDate": "2024-09-28",
            },
        ],
        "parish": [
            {
                "parish": "Kingston",
                "spend": 540,
                "impressions": 120000,
                "clicks": 3400,
                "conversions": 120,
                "roas": 3.5,
                "campaignCount": 1,
                "currency": "USD",
            },
            {
                "parish": "St James",
                "spend": 430,
                "impressions": 94000,
                "clicks": 4200,
                "conversions": 140,
                "roas": 4.1,
                "campaignCount": 1,
                "currency": "USD",
            },
            {
                "parish": "St Andrew",
                "spend": 220,
                "impressions": 68000,
                "clicks": 2100,
                "conversions": 95,
                "roas": 3.2,
                "campaignCount": 1,
                "currency": "USD",
            },
        ],
        "demographics": {
            "byAge": [
                {"ageRange": "18-24", "spend": 180.0, "impressions": 42000, "clicks": 1450, "conversions": 52, "reach": 27500},
                {"ageRange": "25-34", "spend": 420.0, "impressions": 98000, "clicks": 3400, "conversions": 128, "reach": 64100},
                {"ageRange": "35-44", "spend": 310.0, "impressions": 72000, "clicks": 2500, "conversions": 94, "reach": 47000},
                {"ageRange": "45-54", "spend": 160.0, "impressions": 38000, "clicks": 1320, "conversions": 48, "reach": 24800},
                {"ageRange": "55-64", "spend": 80.0, "impressions": 22000, "clicks": 680, "conversions": 22, "reach": 14400},
                {"ageRange": "65+", "spend": 40.0, "impressions": 10000, "clicks": 350, "conversions": 11, "reach": 6500},
            ],
            "byGender": [
                {"gender": "female", "spend": 680.0, "impressions": 160000, "clicks": 5540, "conversions": 203, "reach": 104600},
                {"gender": "male", "spend": 480.0, "impressions": 112000, "clicks": 3880, "conversions": 140, "reach": 73200},
                {"gender": "unknown", "spend": 30.0, "impressions": 10000, "clicks": 280, "conversions": 12, "reach": 6500},
            ],
            "byAgeGender": [
                {"ageRange": "18-24", "gender": "female", "spend": 105.0, "impressions": 24500, "clicks": 860, "conversions": 32, "reach": 16000},
                {"ageRange": "18-24", "gender": "male", "spend": 75.0, "impressions": 17500, "clicks": 590, "conversions": 20, "reach": 11500},
                {"ageRange": "25-34", "gender": "female", "spend": 245.0, "impressions": 57000, "clicks": 2000, "conversions": 76, "reach": 37300},
                {"ageRange": "25-34", "gender": "male", "spend": 175.0, "impressions": 41000, "clicks": 1400, "conversions": 52, "reach": 26800},
                {"ageRange": "35-44", "gender": "female", "spend": 180.0, "impressions": 42000, "clicks": 1460, "conversions": 55, "reach": 27400},
                {"ageRange": "35-44", "gender": "male", "spend": 130.0, "impressions": 30000, "clicks": 1040, "conversions": 39, "reach": 19600},
                {"ageRange": "45-54", "gender": "female", "spend": 95.0, "impressions": 22000, "clicks": 780, "conversions": 28, "reach": 14400},
                {"ageRange": "45-54", "gender": "male", "spend": 65.0, "impressions": 16000, "clicks": 540, "conversions": 20, "reach": 10400},
                {"ageRange": "55-64", "gender": "female", "spend": 45.0, "impressions": 12000, "clicks": 380, "conversions": 10, "reach": 7800},
                {"ageRange": "55-64", "gender": "male", "spend": 35.0, "impressions": 10000, "clicks": 300, "conversions": 12, "reach": 6600},
                {"ageRange": "65+", "gender": "female", "spend": 10.0, "impressions": 2500, "clicks": 60, "conversions": 2, "reach": 1700},
                {"ageRange": "65+", "gender": "male", "spend": 30.0, "impressions": 7500, "clicks": 290, "conversions": 9, "reach": 4800},
            ],
        },
        "platforms": {
            "byPlatform": [
                {"platform": "facebook", "spend": 640.0, "impressions": 150000, "clicks": 5200, "conversions": 190, "reach": 98000},
                {"platform": "instagram", "spend": 430.0, "impressions": 100000, "clicks": 3500, "conversions": 128, "reach": 65400},
                {"platform": "audience_network", "spend": 80.0, "impressions": 22000, "clicks": 680, "conversions": 25, "reach": 14400},
                {"platform": "messenger", "spend": 40.0, "impressions": 10000, "clicks": 320, "conversions": 12, "reach": 6500},
            ],
            "byDevice": [
                {"device": "mobile_app", "spend": 750.0, "impressions": 176000, "clicks": 6100, "conversions": 224, "reach": 115000},
                {"device": "mobile_web", "spend": 300.0, "impressions": 70000, "clicks": 2420, "conversions": 88, "reach": 45700},
                {"device": "desktop", "spend": 140.0, "impressions": 36000, "clicks": 1180, "conversions": 43, "reach": 23500},
            ],
            "byPlatformDevice": [
                {"platform": "facebook", "device": "mobile_app", "spend": 380.0, "impressions": 89000, "clicks": 3100, "conversions": 114, "reach": 58200},
                {"platform": "facebook", "device": "mobile_web", "spend": 170.0, "impressions": 40000, "clicks": 1380, "conversions": 50, "reach": 26100},
                {"platform": "facebook", "device": "desktop", "spend": 90.0, "impressions": 21000, "clicks": 720, "conversions": 26, "reach": 13700},
                {"platform": "instagram", "device": "mobile_app", "spend": 320.0, "impressions": 75000, "clicks": 2600, "conversions": 95, "reach": 49000},
                {"platform": "instagram", "device": "mobile_web", "spend": 80.0, "impressions": 18000, "clicks": 640, "conversions": 23, "reach": 11800},
                {"platform": "instagram", "device": "desktop", "spend": 30.0, "impressions": 7000, "clicks": 260, "conversions": 10, "reach": 4600},
                {"platform": "audience_network", "device": "mobile_app", "spend": 50.0, "impressions": 12000, "clicks": 400, "conversions": 15, "reach": 7800},
                {"platform": "audience_network", "device": "mobile_web", "spend": 30.0, "impressions": 10000, "clicks": 280, "conversions": 10, "reach": 6600},
                {"platform": "messenger", "device": "mobile_app", "spend": 40.0, "impressions": 10000, "clicks": 320, "conversions": 12, "reach": 6500},
            ],
        },
    }

    def fetch_metrics(
        self,
        *,
        tenant_id: str,
        options: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:  # noqa: ARG002 - options reserved for future use
        payload = deepcopy(self._PAYLOAD)
        payload.setdefault("snapshot_generated_at", timezone.now().isoformat())
        return payload
