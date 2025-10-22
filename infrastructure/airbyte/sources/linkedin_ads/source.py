from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional

from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.models import AirbyteConnectionStatus, ConnectorSpecification, Status
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams.availability_strategy import AvailabilityStrategy
from airbyte_cdk.sources.streams.http.http import HttpStream


class _AlwaysAvailable(AvailabilityStrategy):
    def check_availability(self, stream, logger, source):  # type: ignore[override]
        return True, None

class LinkedinAdsStream(HttpStream):
    """Incremental stream for the LinkedIn Ads analytics endpoint."""

    primary_key = ["ad_id", "date"]
    cursor_field = "date"
    url_base = "https://api.linkedin.com/v2/"

    def __init__(self, config: Mapping[str, Any]):
        super().__init__()
        self._config = config
        self._account_id = config["account_id"]
        self._access_token = config["access_token"]
        self._start_date = datetime.fromisoformat(config["start_date"]).date()
        self._lookback_days = int(config.get("lookback_window_days", 2))
        self._slice_span_days = int(config.get("slice_span_days", 7))
        self._page_size = int(config.get("page_size", 500))
        self._time_granularity = config.get("time_granularity", "DAILY")
        self._timezone = config.get("timezone", "America/Jamaica")
        self._name = "linkedin_ads_performance"

    @property
    def name(self) -> str:
        return self._name

    def path(
        self,
        *,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return "adAnalyticsV2"

    def request_headers(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Linkedin-Version": "202312",
            "Content-Type": "application/json",
        }

    def request_params(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> MutableMapping[str, Any]:
        params: MutableMapping[str, Any] = {}
        if next_page_token and "start" in next_page_token:
            params["start"] = next_page_token["start"]
        if next_page_token and "count" in next_page_token:
            params["count"] = next_page_token["count"]
        return params

    def request_body_json(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Mapping[str, Any]]:
        slice_start = stream_slice["start_date"] if stream_slice else self._start_date.isoformat()
        slice_end = stream_slice["end_date"] if stream_slice else slice_start
        body: MutableMapping[str, Any] = {
            "q": "analytics",
            "timeGranularity": self._time_granularity,
            "accounts": [f"urn:li:sponsoredAccount:{self._account_id}"],
            "dateRange": {"start": slice_start, "end": slice_end},
            "fields": [
                "impressions",
                "clicks",
                "costInLocalCurrency",
                "conversions",
                "conversionValueInLocalCurrency",
                "currencyCode",
            ],
            "pivotBy": [
                "CAMPAIGN",
                "CAMPAIGN_GROUP",
                "CREATIVE",
                "COUNTRY",
                "DEVICE_TYPE",
            ],
            "sortBy": [
                {
                    "field": "dateRange",
                    "order": "ASCENDING",
                }
            ],
            "timeGranularityTimezone": self._timezone,
            "count": self._page_size,
        }
        if next_page_token and "start" in next_page_token:
            body["start"] = next_page_token["start"]
        return body

    def next_page_token(self, response) -> Optional[Mapping[str, Any]]:
        payload = response.json()
        paging = payload.get("paging", {})
        start = paging.get("start")
        count = paging.get("count")
        total = paging.get("total")
        if start is None or count is None or total is None:
            return None
        next_start = start + count
        if next_start >= total:
            return None
        return {"start": next_start, "count": count}

    @property
    def http_method(self) -> str:
        return "POST"

    @property
    def availability_strategy(self) -> AvailabilityStrategy:
        return _AlwaysAvailable()

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
        end_date = datetime.now(timezone.utc).date()
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
        for element in payload.get("elements", []):
            metrics = element.get("metrics", {})
            pivots = element.get("pivotValues", [])
            date_range = element.get("dateRange", {})
            yield {
                "platform": "linkedin",
                "date": date_range.get("start"),
                "account_id": self._extract_identifier(pivots, 0, default=self._account_id),
                "campaign_id": self._extract_identifier(pivots, 1),
                "ad_group_id": self._extract_identifier(pivots, 2),
                "ad_id": self._extract_identifier(pivots, 3),
                "region": pivots[4] if len(pivots) > 4 else None,
                "device": pivots[5] if len(pivots) > 5 else None,
                "spend": metrics.get("costInLocalCurrency"),
                "impressions": metrics.get("impressions"),
                "clicks": metrics.get("clicks"),
                "conversions": metrics.get("conversions"),
                "conversion_value": metrics.get("conversionValueInLocalCurrency"),
                "currency": metrics.get("currencyCode"),
            }

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "platform": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "account_id": {"type": ["null", "string"]},
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

    @staticmethod
    def _extract_identifier(values: Iterable[Any], index: int, default: Optional[str] = None) -> Optional[str]:
        try:
            raw_value = list(values)[index]
        except IndexError:
            return default
        if isinstance(raw_value, str) and raw_value.startswith("urn:"):
            return raw_value.split(":")[-1]
        return raw_value

    def get_updated_state(self, current_stream_state: Mapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        current_value = current_stream_state.get(self.cursor_field)
        latest_value = latest_record.get(self.cursor_field)
        if not current_value:
            return {self.cursor_field: latest_value}
        if not latest_value:
            return {self.cursor_field: current_value}
        return {self.cursor_field: max(current_value, latest_value)}


class SourceLinkedinAds(AbstractSource):
    def check(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> AirbyteConnectionStatus:
        missing = [field for field in ("account_id", "access_token", "start_date") if field not in config]
        if missing:
            return AirbyteConnectionStatus(status=Status.FAILED, message=f"Missing required fields: {', '.join(missing)}")
        try:
            datetime.fromisoformat(config["start_date"])
        except ValueError as exc:
            return AirbyteConnectionStatus(status=Status.FAILED, message=f"Invalid start_date: {exc}")
        return AirbyteConnectionStatus(status=Status.SUCCEEDED)

    def check_connection(self, logger: AirbyteLogger, config: Mapping[str, Any]):
        status = self.check(logger, config)
        return status.status == Status.SUCCEEDED, status.message

    def streams(self, config: Mapping[str, Any]):
        return [LinkedinAdsStream(config)]

    def spec(self, logger: AirbyteLogger) -> ConnectorSpecification:
        spec_path = Path(__file__).with_name("spec.json")
        specification = json.loads(spec_path.read_text())
        return ConnectorSpecification.parse_obj(specification)
