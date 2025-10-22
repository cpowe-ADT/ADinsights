from __future__ import annotations

import json
from typing import Dict

from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.models import ConfiguredAirbyteCatalog, ConfiguredAirbyteStream, DestinationSyncMode, SyncMode
from airbyte_cdk.test.entrypoint_wrapper import read
from airbyte_cdk.test.mock_http import HttpMocker, HttpRequest, HttpResponse

from infrastructure.airbyte.sources.tiktok_ads import SourceTiktokAds


def _config() -> Dict[str, str]:
    return {
        "advertiser_id": "67890",
        "access_token": "test-token",
        "start_date": "2024-07-01",
        "lookback_window_days": 0,
        "slice_span_days": 1,
        "page_size": 200,
        "timezone": "America/Jamaica",
    }


def _configured_catalog(source: SourceTiktokAds, config: Dict[str, str]) -> ConfiguredAirbyteCatalog:
    catalog = source.discover(AirbyteLogger(), config)
    configured_streams = [
        ConfiguredAirbyteStream(
            stream=stream,
            sync_mode=SyncMode.incremental,
            destination_sync_mode=DestinationSyncMode.append_dedup,
            cursor_field=stream.default_cursor_field or ["date"],
            primary_key=stream.source_defined_primary_key or [["ad_id"], ["date"]],
        )
        for stream in catalog.streams
    ]
    return ConfiguredAirbyteCatalog(streams=configured_streams)


def test_discover_defines_incremental_cursor() -> None:
    source = SourceTiktokAds()
    catalog = source.discover(AirbyteLogger(), _config())
    assert len(catalog.streams) == 1
    stream = catalog.streams[0]
    assert stream.default_cursor_field == ["date"]
    assert stream.source_defined_primary_key == [["ad_id"], ["date"]]
    assert "spend" in stream.json_schema["properties"]


def test_incremental_sync_uses_state_checkpoint() -> None:
    source = SourceTiktokAds()
    config = _config()
    catalog = _configured_catalog(source, config)
    expected_body = {
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

    with HttpMocker() as http_mocker:
        http_mocker.get(
            HttpRequest(
                "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/",
                headers={"Access-Token": "test-token"},
            ),
            HttpResponse(body=json.dumps(api_response)),
        )
        http_mocker.post(
            HttpRequest(
                "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/",
                    headers={"Access-Token": "test-token"},
                    body=expected_body,
                ),
                HttpResponse(body=json.dumps(api_response)),
            )
        output = read(source, config, catalog)

    records = [message.record.data for message in output.records]
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
    latest_state = output.state_messages[-1].state.stream.stream_state  # type: ignore[attr-defined]
    assert latest_state == {"date": "2024-07-01"}
