from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from airbyte_cdk.models import Status

from infrastructure.airbyte.sources.microsoft_ads import SourceMicrosoftAds


LOGGER = logging.getLogger("test.microsoft_ads_source")


def _config() -> Dict[str, str]:
    return {
        "account_id": "12345",
        "developer_token": "developer-token",
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


def test_check_requires_core_credentials() -> None:
    source = SourceMicrosoftAds()
    config = _config()
    del config["developer_token"]

    status = source.check(LOGGER, config)

    assert status.status == Status.FAILED
    assert "developer_token" in (status.message or "")


def test_check_rejects_invalid_start_date() -> None:
    source = SourceMicrosoftAds()
    config = _config()
    config["start_date"] = "not-a-date"

    status = source.check(LOGGER, config)

    assert status.status == Status.FAILED
    assert "Invalid start_date" in (status.message or "")


def test_discover_publishes_expected_schema() -> None:
    source = SourceMicrosoftAds()
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


def test_incremental_read_emits_state_and_records() -> None:
    source = SourceMicrosoftAds()
    config = _config()
    stream = source.streams(config)[0]
    expected_body = {
        "ReportRequest": {
            "Type": "AdPerformanceReportRequest",
            "Aggregation": "Daily",
            "Format": "Json",
            "ReturnOnlyCompleteData": False,
            "MaxRows": 200,
            "Scope": {"AccountIds": ["12345"]},
            "Time": {
                "CustomDateRangeStart": {"Year": 2024, "Month": 7, "Day": 1},
                "CustomDateRangeEnd": {"Year": 2024, "Month": 7, "Day": 1},
                "ReportTimeZone": "America/Jamaica",
            },
            "Columns": [
                "TimePeriod",
                "AccountId",
                "CampaignId",
                "AdGroupId",
                "AdId",
                "Country",
                "DeviceType",
                "Spend",
                "Impressions",
                "Clicks",
                "Conversions",
                "Revenue",
                "CurrencyCode",
            ],
        }
    }
    api_response = {
        "records": [
            {
                "TimePeriod": "2024-07-01",
                "AccountId": "12345",
                "CampaignId": "cmp123",
                "AdGroupId": "adg456",
                "AdId": "ad789",
                "Country": "US",
                "DeviceType": "Computer",
                "Spend": "45.50",
                "Impressions": "4200",
                "Clicks": "123",
                "Conversions": "9",
                "Revenue": "210.50",
                "CurrencyCode": "USD",
            }
        ]
    }
    headers = {
        "Authorization": "Bearer test-token",
        "DeveloperToken": "developer-token",
        "CustomerAccountId": "12345",
        "Content-Type": "application/json",
    }

    assert stream.path() == "Reporting/v13/GenerateReport/Submit"
    assert stream.request_headers(stream_state=None) == headers
    assert (
        stream.request_body_json(
            stream_state=None,
            stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
        )
        == expected_body
    )

    records = list(
        stream.parse_response(
            _JsonResponse(api_response),
            stream_state={},
            stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
        )
    )
    assert records == [
        {
            "platform": "microsoft_ads",
            "date": "2024-07-01",
            "account_id": "12345",
            "campaign_id": "cmp123",
            "ad_group_id": "adg456",
            "ad_id": "ad789",
            "region": "US",
            "device": "Computer",
            "spend": 45.5,
            "impressions": 4200,
            "clicks": 123,
            "conversions": 9.0,
            "conversion_value": 210.5,
            "currency": "USD",
        }
    ]
    latest_state = stream.get_updated_state({}, records[0])
    assert latest_state == {"date": "2024-07-01"}


def test_continuation_token_is_sent_on_next_page() -> None:
    source = SourceMicrosoftAds()
    stream = source.streams(_config())[0]
    body = stream.request_body_json(
        stream_state=None,
        stream_slice={"start_date": "2024-07-01", "end_date": "2024-07-01"},
        next_page_token={"continuation_token": "next-page"},
    )

    assert body is not None
    assert body["ContinuationToken"] == "next-page"


def test_stream_slices_honor_configured_end_date() -> None:
    source = SourceMicrosoftAds()
    config = _config()
    config["start_date"] = "2024-07-01"
    config["end_date"] = "2024-07-03"
    config["slice_span_days"] = 2
    stream = source.streams(config)[0]

    slices = list(stream.stream_slices(sync_mode=None))

    assert slices == [
        {"start_date": "2024-07-01", "end_date": "2024-07-02"},
        {"start_date": "2024-07-03", "end_date": "2024-07-03"},
    ]
