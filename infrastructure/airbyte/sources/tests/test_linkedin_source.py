from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from infrastructure.airbyte.sources.linkedin_ads import SourceLinkedinAds


LOGGER = logging.getLogger("test.linkedin_ads_source")


def _config() -> Dict[str, object]:
    return {
        "account_id": "12345",
        "access_token": "test-token",
        "start_date": "2024-07-01",
        "end_date": "2024-07-01",
        "lookback_window_days": 0,
        "slice_span_days": 1,
        "page_size": 500,
        "timezone": "America/Jamaica",
    }


@dataclass
class _JsonResponse:
    payload: Dict[str, object]

    def json(self) -> Dict[str, object]:
        return self.payload


def test_discover_publishes_expected_schema() -> None:
    source = SourceLinkedinAds()
    catalog = source.discover(LOGGER, _config())
    assert len(catalog.streams) == 1
    stream = catalog.streams[0]
    schema_props = stream.json_schema["properties"]
    for field in (
        "platform",
        "date",
        "account_id",
        "campaign_id",
        "ad_group_id",
        "ad_id",
        "region",
        "device",
        "spend",
        "impressions",
        "clicks",
        "conversions",
        "conversion_value",
        "currency",
    ):
        assert field in schema_props
    assert stream.default_cursor_field == ["date"]
    assert stream.source_defined_primary_key == [["ad_id"], ["date"]]


def test_request_body_targets_slice_window() -> None:
    source = SourceLinkedinAds()
    stream = source.streams(_config())[0]
    body = stream.request_body_json(
        stream_state=None,
        stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
    )
    assert body == {
        "q": "analytics",
        "timeGranularity": "DAILY",
        "accounts": ["urn:li:sponsoredAccount:12345"],
        "dateRange": {"start": "2024-07-01", "end": "2024-07-01"},
        "fields": [
            "impressions",
            "clicks",
            "costInLocalCurrency",
            "conversions",
            "conversionValueInLocalCurrency",
            "currencyCode",
        ],
        "pivotBy": ["CAMPAIGN", "CAMPAIGN_GROUP", "CREATIVE", "COUNTRY", "DEVICE_TYPE"],
        "sortBy": [{"field": "dateRange", "order": "ASCENDING"}],
        "timeGranularityTimezone": "America/Jamaica",
        "count": 500,
    }


def test_parse_response_normalizes_urns_and_state() -> None:
    source = SourceLinkedinAds()
    stream = source.streams(_config())[0]
    api_response = {
        "elements": [
            {
                "dateRange": {"start": "2024-07-01", "end": "2024-07-01"},
                "pivotValues": [
                    "urn:li:sponsoredAccount:12345",
                    "urn:li:sponsoredCampaign:456",
                    "urn:li:sponsoredCampaignGroup:789",
                    "urn:li:sponsoredCreative:999",
                    "US",
                    "DESKTOP",
                ],
                "metrics": {
                    "impressions": 1500,
                    "clicks": 45,
                    "costInLocalCurrency": 123.45,
                    "conversions": 6,
                    "conversionValueInLocalCurrency": 320.0,
                    "currencyCode": "USD",
                },
            }
        ],
        "paging": {"start": 0, "count": 500, "total": 1},
    }

    records = list(
        stream.parse_response(
            _JsonResponse(api_response),
            stream_state={},
            stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
        )
    )
    assert records == [
        {
            "platform": "linkedin",
            "date": "2024-07-01",
            "account_id": "12345",
            "campaign_id": "456",
            "ad_group_id": "789",
            "ad_id": "999",
            "region": "US",
            "device": "DESKTOP",
            "spend": 123.45,
            "impressions": 1500,
            "clicks": 45,
            "conversions": 6,
            "conversion_value": 320.0,
            "currency": "USD",
        }
    ]

    latest_state = stream.get_updated_state({}, records[0])
    assert latest_state == {"date": "2024-07-01"}


def test_next_page_token_stops_at_total() -> None:
    source = SourceLinkedinAds()
    stream = source.streams(_config())[0]
    more = _JsonResponse({"paging": {"start": 0, "count": 500, "total": 1200}})
    done = _JsonResponse({"paging": {"start": 1000, "count": 500, "total": 1200}})
    assert stream.next_page_token(more) == {"start": 500, "count": 500}
    assert stream.next_page_token(done) is None
