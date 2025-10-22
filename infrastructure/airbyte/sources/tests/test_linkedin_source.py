from __future__ import annotations

import json
from typing import Dict

from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.models import ConfiguredAirbyteCatalog, ConfiguredAirbyteStream, DestinationSyncMode, SyncMode
from airbyte_cdk.test.entrypoint_wrapper import read
from airbyte_cdk.test.mock_http import HttpMocker, HttpRequest, HttpResponse

from infrastructure.airbyte.sources.linkedin_ads import SourceLinkedinAds


def _config() -> Dict[str, str]:
    return {
        "account_id": "12345",
        "access_token": "test-token",
        "start_date": "2024-07-01",
        "lookback_window_days": 0,
        "slice_span_days": 1,
        "page_size": 500,
        "timezone": "America/Jamaica",
    }


def _configured_catalog(source: SourceLinkedinAds, config: Dict[str, str]) -> ConfiguredAirbyteCatalog:
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


def test_discover_publishes_expected_schema() -> None:
    source = SourceLinkedinAds()
    catalog = source.discover(AirbyteLogger(), _config())
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


def test_incremental_read_emits_state_and_records() -> None:
    source = SourceLinkedinAds()
    config = _config()
    catalog = _configured_catalog(source, config)
    expected_body = {
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

    with HttpMocker() as http_mocker:
        http_mocker.get(
            HttpRequest(
                "https://api.linkedin.com/v2/adAnalyticsV2",
                headers={"Authorization": "Bearer test-token"},
            ),
            HttpResponse(body=json.dumps(api_response)),
        )
        http_mocker.post(
            HttpRequest(
                "https://api.linkedin.com/v2/adAnalyticsV2",
                    headers={"Authorization": "Bearer test-token"},
                    body=expected_body,
                ),
                HttpResponse(body=json.dumps(api_response)),
            )
        output = read(source, config, catalog)

    records = [message.record.data for message in output.records]
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
    latest_state = output.state_messages[-1].state.stream.stream_state  # type: ignore[attr-defined]
    assert latest_state == {"date": "2024-07-01"}

