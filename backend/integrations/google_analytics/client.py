from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.conf import settings

from integrations.models import PlatformCredential

GA4_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GOOGLE_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleAnalyticsClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        classification: str = "unknown",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.retryable = retryable


@dataclass(frozen=True)
class Ga4DailyRow:
    property_id: str
    date_day: date
    source: str
    medium: str
    campaign: str
    sessions: int
    users: int
    new_users: int
    engagement_rate: float
    average_session_duration: float
    conversions: int
    event_count: int


def _import_ga4_symbols() -> tuple[type[Any], type[Any], tuple[type[Any], ...]]:
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
            OrderBy,
        )
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise GoogleAnalyticsClientError(
            "google-analytics-data package is not installed. Install backend dependencies first.",
            classification="dependency_missing",
            retryable=False,
        ) from exc
    return (
        BetaAnalyticsDataClient,
        Credentials,
        (DateRange, Dimension, Metric, RunReportRequest, OrderBy),
    )


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return 0
        return int(float(candidate))
    return int(value)


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return 0.0
        return float(candidate)
    return float(value)


class GoogleAnalyticsClient:
    def __init__(self, *, credential: PlatformCredential) -> None:
        self.credential = credential
        self._client = self._build_client()

    def _build_client(self):
        access_token = self.credential.decrypt_access_token()
        if not access_token:
            raise GoogleAnalyticsClientError(
                "Google Analytics credential is missing an access token.",
                classification="credential_missing_access_token",
                retryable=False,
            )

        refresh_token = self.credential.decrypt_refresh_token()
        if not refresh_token:
            raise GoogleAnalyticsClientError(
                "Google Analytics credential is missing a refresh token.",
                classification="credential_missing_refresh_token",
                retryable=False,
            )

        client_id = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ANALYTICS_CLIENT_SECRET", "") or "").strip()
        if not client_id or not client_secret:
            raise GoogleAnalyticsClientError(
                "Google Analytics OAuth client credentials are not configured.",
                classification="oauth_not_configured",
                retryable=False,
            )

        client_cls, credentials_cls, _ = _import_ga4_symbols()
        credentials = credentials_cls(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=GOOGLE_OAUTH_TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=[GA4_READONLY_SCOPE],
        )
        return client_cls(credentials=credentials)

    def fetch_traffic_acquisition(
        self,
        *,
        property_id: str,
        start_date: date,
        end_date: date,
    ) -> list[Ga4DailyRow]:
        _, _, (DateRange, Dimension, Metric, RunReportRequest, OrderBy) = _import_ga4_symbols()

        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium"),
                Dimension(name="sessionCampaignName"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="newUsers"),
                Metric(name="engagementRate"),
                Metric(name="averageSessionDuration"),
                Metric(name="keyEvents"),  # Formerly conversions
                Metric(name="eventCount"),
            ],
            date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
        )

        response = self._client.run_report(request)

        rows = []
        for row in response.rows:
            rows.append(
                Ga4DailyRow(
                    property_id=property_id,
                    date_day=_as_date(row.dimension_values[0].value),
                    source=row.dimension_values[1].value,
                    medium=row.dimension_values[2].value,
                    campaign=row.dimension_values[3].value,
                    sessions=_as_int(row.metric_values[0].value),
                    users=_as_int(row.metric_values[1].value),
                    new_users=_as_int(row.metric_values[2].value),
                    engagement_rate=_as_float(row.metric_values[3].value),
                    average_session_duration=_as_float(row.metric_values[4].value),
                    conversions=_as_int(row.metric_values[5].value),
                    event_count=_as_int(row.metric_values[6].value),
                )
            )
        return rows

    def fetch_daily_metrics(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
    ) -> list[Ga4DailyRow]:
        return self.fetch_traffic_acquisition(
            property_id=property_id,
            start_date=start_date,
            end_date=end_date,
        )
