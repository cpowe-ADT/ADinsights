from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from infrastructure.airbyte.sources.tiktok_ads import SourceTiktokAds


LOGGER = logging.getLogger("test.tiktok_ads_source")


def _config() -> Dict[str, object]:
    return {
        "advertiser_id": "67890",
        "access_token": "test-token",
        "start_date": "2024-07-01",
        "end_date": "2024-07-01",
        "lookback_window_days": 0,
        "slice_span_days": 1,
        "page_size": 200,
        "timezone": "America/Jamaica",
    }


@dataclass
class _JsonResponse:
    payload: Dict[str, object]

    def json(self) -> Dict[str, object]:
        return self.payload


def test_discover_defines_incremental_cursor() -> None:
    source = SourceTiktokAds()
    catalog = source.discover(LOGGER, _config())
    assert len(catalog.streams) == 1
    stream = catalog.streams[0]
    assert stream.default_cursor_field == ["date"]
    assert stream.source_defined_primary_key == [["ad_id"], ["date"]]
    assert "spend" in stream.json_schema["properties"]


def test_request_body_targets_slice_window() -> None:
    source = SourceTiktokAds()
    stream = source.streams(_config())[0]
    body = stream.request_body_json(
        stream_state=None,
        stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
    )
    assert body == {
        "advertiser_id": "67890",
        "report_type": "BASIC",
        "data_level": "AUCTION_AD",
        "dimensions": [
            "stat_time_day",
            "campaign_id",
            "adgroup_id",
            "ad_id",
            "country",
            "placement_type",
        ],
        "metrics": [
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "total_complete_payment",
        ],
        "start_date": "2024-07-01",
        "end_date": "2024-07-01",
        "page": 1,
        "page_size": 200,
        "timezone": "America/Jamaica",
    }


def test_parse_response_normalizes_records_and_state() -> None:
    source = SourceTiktokAds()
    stream = source.streams(_config())[0]
    api_response = {
        "data": {
            "list": [
                {
                    "stat_time_day": "2024-07-01",
                    "campaign_id": "cmp123",
                    "adgroup_id": "adg456",
                    "ad_id": "ad789",
                    "country": "US",
                    "placement_type": "PLACEMENT_TYPE_A",
                    "spend": 45.5,
                    "impressions": 4200,
                    "clicks": 123,
                    "conversions": 9,
                    "total_complete_payment": 210.5,
                    "currency": "USD",
                }
            ]
        }
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
            "platform": "tiktok",
            "date": "2024-07-01",
            "account_id": "67890",
            "campaign_id": "cmp123",
            "ad_group_id": "adg456",
            "ad_id": "ad789",
            "region": "US",
            "device": "PLACEMENT_TYPE_A",
            "spend": 45.5,
            "impressions": 4200,
            "clicks": 123,
            "conversions": 9,
            "conversion_value": 210.5,
            "currency": "USD",
        }
    ]

    latest_state = stream.get_updated_state({}, records[0])
    assert latest_state == {"date": "2024-07-01"}


def test_incremental_state_replays_with_lookback() -> None:
    config = _config()
    config["lookback_window_days"] = 2
    config["slice_span_days"] = 30
    config["end_date"] = "2024-07-31"
    source = SourceTiktokAds()
    stream = source.streams(config)[0]

    slices = list(
        stream.stream_slices(
            sync_mode=None,
            stream_state={"date": "2024-07-10"},
        )
    )

    # Resume replays lookback_window_days before the checkpoint (2024-07-10 - 2d).
    assert slices[0]["start_date"] == "2024-07-08"
