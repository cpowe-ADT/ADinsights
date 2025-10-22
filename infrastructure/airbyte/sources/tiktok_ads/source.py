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


class TiktokAdsStream(HttpStream):
    """Incremental stream for TikTok Ads reports."""

    primary_key = ["ad_id", "date"]
    cursor_field = "date"
    url_base = "https://business-api.tiktok.com/open_api/v1.3/"

    def __init__(self, config: Mapping[str, Any]):
        super().__init__()
        self._config = config
        self._advertiser_id = config["advertiser_id"]
        self._access_token = config["access_token"]
        self._start_date = datetime.fromisoformat(config["start_date"]).date()
        self._lookback_days = int(config.get("lookback_window_days", 1))
        self._slice_span_days = int(config.get("slice_span_days", 7))
        self._page_size = int(config.get("page_size", 500))
        self._timezone = config.get("timezone", "America/Jamaica")
        self._name = "tiktok_ads_performance"

    @property
    def name(self) -> str:
        return self._name

    @property
    def http_method(self) -> str:
        return "POST"

    def path(
        self,
        *,
        stream_state: Optional[Mapping[str, Any]] = None,
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return "report/integrated/get/"

    def request_headers(
        self,
        stream_state: Optional[Mapping[str, Any]],
        stream_slice: Optional[Mapping[str, Any]] = None,
        next_page_token: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        return {
            "Access-Token": self._access_token,
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
        payload: MutableMapping[str, Any] = {
            "advertiser_id": self._advertiser_id,
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
            "start_date": slice_start,
            "end_date": slice_end,
            "page": next_page_token.get("page", 1) if next_page_token else 1,
            "page_size": self._page_size,
            "timezone": self._timezone,
        }
        return payload

    def next_page_token(self, response) -> Optional[Mapping[str, Any]]:
        payload = response.json().get("data", {})
        page_info = payload.get("page_info", {})
        if not page_info:
            return None
        page = page_info.get("page")
        total_page = page_info.get("total_page")
        if not page or not total_page:
            return None
        if page >= total_page:
            return None
        return {"page": page + 1}

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
        payload = response.json().get("data", {})
        for record in payload.get("list", []):
            yield {
                "platform": "tiktok",
                "date": record.get("stat_time_day"),
                "account_id": self._advertiser_id,
                "campaign_id": record.get("campaign_id"),
                "ad_group_id": record.get("adgroup_id"),
                "ad_id": record.get("ad_id"),
                "region": record.get("country"),
                "device": record.get("placement_type"),
                "spend": record.get("spend"),
                "impressions": record.get("impressions"),
                "clicks": record.get("clicks"),
                "conversions": record.get("conversions"),
                "conversion_value": record.get("total_complete_payment"),
                "currency": record.get("currency"),
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

    def get_updated_state(self, current_stream_state: Mapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        current_value = current_stream_state.get(self.cursor_field)
        latest_value = latest_record.get(self.cursor_field)
        if not current_value:
            return {self.cursor_field: latest_value}
        if not latest_value:
            return {self.cursor_field: current_value}
        return {self.cursor_field: max(current_value, latest_value)}

    @property
    def availability_strategy(self) -> AvailabilityStrategy:
        return _AlwaysAvailable()


class SourceTiktokAds(AbstractSource):
    def check(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> AirbyteConnectionStatus:
        missing = [field for field in ("advertiser_id", "access_token", "start_date") if field not in config]
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
        return [TiktokAdsStream(config)]

    def spec(self, logger: AirbyteLogger) -> ConnectorSpecification:
        spec_path = Path(__file__).with_name("spec.json")
        specification = json.loads(spec_path.read_text())
        return ConnectorSpecification.parse_obj(specification)
