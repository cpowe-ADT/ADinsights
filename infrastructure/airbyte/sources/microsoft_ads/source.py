from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional

from airbyte_cdk.models import AirbyteConnectionStatus, ConnectorSpecification, Status
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams.availability_strategy import AvailabilityStrategy
from airbyte_cdk.sources.streams.http.http import HttpStream


class _AlwaysAvailable(AvailabilityStrategy):
    def check_availability(self, stream, logger, source):  # type: ignore[override]
        return True, None


class MicrosoftAdsPerformanceStream(HttpStream):
    """Incremental stream for Microsoft Advertising ad performance reports."""

    primary_key = ["ad_id", "date"]
    cursor_field = "date"
    url_base = "https://reporting.api.bingads.microsoft.com/"

    def __init__(self, config: Mapping[str, Any]):
        self._name = "microsoft_ads_performance"
        super().__init__()
        self._config = config
        self._account_id = config["account_id"]
        self._developer_token = config["developer_token"]
        self._access_token = config["access_token"]
        self._start_date = datetime.fromisoformat(config["start_date"]).date()
        end_date = config.get("end_date")
        self._end_date = datetime.fromisoformat(end_date).date() if end_date else None
        self._lookback_days = int(config.get("lookback_window_days", 3))
        self._slice_span_days = int(config.get("slice_span_days", 7))
        self._page_size = int(config.get("page_size", 500))
        self._timezone = config.get("timezone", "America/Jamaica")

    @property
    def name(self) -> str:
        return self._name

    @property
    def http_method(self) -> str:
        return "POST"

    @property
    def availability_strategy(self) -> AvailabilityStrategy:
        return _AlwaysAvailable()

    def path(
        self,
        *,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return "Reporting/v13/GenerateReport/Submit"

    def request_headers(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "DeveloperToken": self._developer_token,
            "CustomerAccountId": self._account_id,
            "Content-Type": "application/json",
        }

    def request_body_json(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Mapping[str, Any]]:
        slice_start = stream_slice["start_date"] if stream_slice else self._start_date.isoformat()
        slice_end = stream_slice["end_date"] if stream_slice else slice_start
        body: MutableMapping[str, Any] = {
            "ReportRequest": {
                "Type": "AdPerformanceReportRequest",
                "Aggregation": "Daily",
                "Format": "Json",
                "ReturnOnlyCompleteData": False,
                "MaxRows": self._page_size,
                "Scope": {"AccountIds": [self._account_id]},
                "Time": {
                    "CustomDateRangeStart": self._date_parts(slice_start),
                    "CustomDateRangeEnd": self._date_parts(slice_end),
                    "ReportTimeZone": self._timezone,
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
        if next_page_token and next_page_token.get("continuation_token"):
            body["ContinuationToken"] = next_page_token["continuation_token"]
        return body

    def next_page_token(self, response) -> Optional[Mapping[str, Any]]:
        payload = response.json()
        token = payload.get("ContinuationToken") or payload.get("continuation_token")
        if not token:
            return None
        return {"continuation_token": token}

    def stream_slices(
        self,
        sync_mode,
        cursor_field: Optional[str] = None,
        stream_state: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        state_date = self._start_date
        if stream_state and stream_state.get(self.cursor_field):
            state_value = datetime.fromisoformat(stream_state[self.cursor_field]).date()
            state_date = max(self._start_date, state_value - timedelta(days=self._lookback_days))
        current = state_date
        end_date = self._end_date or datetime.now(timezone.utc).date()
        while current <= end_date:
            window_end = min(current + timedelta(days=self._slice_span_days - 1), end_date)
            yield {"start_date": current.isoformat(), "end_date": window_end.isoformat()}
            current = window_end + timedelta(days=1)

    def parse_response(
        self,
        response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Iterable[Mapping[str, Any]]:
        payload = response.json()
        records = payload.get("records") or payload.get("ReportRecords") or payload.get("Rows") or []
        for record in records:
            yield {
                "platform": "microsoft_ads",
                "date": self._first(record, "date", "TimePeriod"),
                "account_id": str(self._first(record, "account_id", "AccountId", default=self._account_id)),
                "campaign_id": self._string_or_none(self._first(record, "campaign_id", "CampaignId")),
                "ad_group_id": self._string_or_none(self._first(record, "ad_group_id", "AdGroupId")),
                "ad_id": self._string_or_none(self._first(record, "ad_id", "AdId")),
                "region": self._first(record, "region", "Country"),
                "device": self._first(record, "device", "DeviceType"),
                "spend": self._number_or_none(self._first(record, "spend", "Spend")),
                "impressions": self._int_or_none(self._first(record, "impressions", "Impressions")),
                "clicks": self._int_or_none(self._first(record, "clicks", "Clicks")),
                "conversions": self._number_or_none(self._first(record, "conversions", "Conversions")),
                "conversion_value": self._number_or_none(self._first(record, "conversion_value", "Revenue")),
                "currency": self._first(record, "currency", "CurrencyCode"),
            }

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "platform": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "account_id": {"type": "string"},
                "campaign_id": {"type": ["null", "string"]},
                "ad_group_id": {"type": ["null", "string"]},
                "ad_id": {"type": ["null", "string"]},
                "region": {"type": ["null", "string"]},
                "device": {"type": ["null", "string"]},
                "spend": {"type": ["null", "number"]},
                "impressions": {"type": ["null", "integer"]},
                "clicks": {"type": ["null", "integer"]},
                "conversions": {"type": ["null", "number"]},
                "conversion_value": {"type": ["null", "number"]},
                "currency": {"type": ["null", "string"]},
            },
            "required": ["platform", "date", "ad_id"],
        }

    def get_updated_state(
        self,
        current_stream_state: Mapping[str, Any],
        latest_record: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        current_value = current_stream_state.get(self.cursor_field)
        latest_value = latest_record.get(self.cursor_field)
        if not current_value:
            return {self.cursor_field: latest_value}
        if not latest_value:
            return {self.cursor_field: current_value}
        return {self.cursor_field: max(current_value, latest_value)}

    @staticmethod
    def _date_parts(value: str) -> Mapping[str, int]:
        parsed = date.fromisoformat(value)
        return {"Year": parsed.year, "Month": parsed.month, "Day": parsed.day}

    @staticmethod
    def _first(record: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in record:
                return record[key]
        return default

    @staticmethod
    def _string_or_none(value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _number_or_none(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        return int(value)


class SourceMicrosoftAds(AbstractSource):
    def check(self, logger: Any, config: Mapping[str, Any]) -> AirbyteConnectionStatus:
        missing = [
            field
            for field in ("account_id", "developer_token", "access_token", "start_date")
            if field not in config
        ]
        if missing:
            return AirbyteConnectionStatus(status=Status.FAILED, message=f"Missing required fields: {', '.join(missing)}")
        try:
            datetime.fromisoformat(config["start_date"])
        except ValueError as exc:
            return AirbyteConnectionStatus(status=Status.FAILED, message=f"Invalid start_date: {exc}")
        return AirbyteConnectionStatus(status=Status.SUCCEEDED)

    def check_connection(self, logger: Any, config: Mapping[str, Any]):
        status = self.check(logger, config)
        return status.status == Status.SUCCEEDED, status.message

    def streams(self, config: Mapping[str, Any]):
        return [MicrosoftAdsPerformanceStream(config)]

    def spec(self, logger: Any) -> ConnectorSpecification:
        spec_path = Path(__file__).with_name("spec.json")
        specification = json.loads(spec_path.read_text())
        return ConnectorSpecification(**specification)
