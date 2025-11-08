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
                    "parish": "Kingston",
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
                    "parish": "St James",
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
                    "parish": "St Andrew",
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
                "parish": "Kingston",
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
                "parish": "St James",
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
