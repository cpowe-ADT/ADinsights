from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from accounts.tenant_context import tenant_context
from adapters.google_analytics import GoogleAnalyticsAdapter
from integrations.google_analytics.client import (
    GoogleAnalyticsClient,
    GoogleAnalyticsClientError,
    Ga4DailyRow,
)
from integrations.models import GoogleAnalyticsConnection, PlatformCredential

pytestmark = pytest.mark.django_db


def _make_credential(tenant, *, account_id: str = "ga4@example.com") -> PlatformCredential:
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id=account_id,
    )
    credential.set_raw_tokens("access-token", "refresh-token")
    credential.save()
    return credential


def test_google_analytics_client_fetch_traffic_acquisition(monkeypatch, tenant, settings):
    settings.GOOGLE_ANALYTICS_CLIENT_ID = "ga4-client-id"
    settings.GOOGLE_ANALYTICS_CLIENT_SECRET = "ga4-client-secret"
    credential = _make_credential(tenant)

    class FakeCredentials:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs

    class DateRange:
        def __init__(self, *, start_date, end_date):  # noqa: ANN003
            self.start_date = start_date
            self.end_date = end_date

    class Dimension:
        def __init__(self, *, name):  # noqa: ANN003
            self.name = name

    class Metric:
        def __init__(self, *, name):  # noqa: ANN003
            self.name = name

    class RunReportRequest:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.__dict__.update(kwargs)

    class OrderBy:
        class DimensionOrderBy:
            def __init__(self, *, dimension_name):  # noqa: ANN003
                self.dimension_name = dimension_name

        def __init__(self, *, dimension):  # noqa: ANN003
            self.dimension = dimension

    class FakeBetaAnalyticsDataClient:
        last_credentials = None
        last_request = None

        def __init__(self, *, credentials):  # noqa: ANN003
            type(self).last_credentials = credentials

        def run_report(self, request):  # noqa: ANN001
            type(self).last_request = request
            return SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        dimension_values=[
                            SimpleNamespace(value="2026-03-17"),
                            SimpleNamespace(value="google"),
                            SimpleNamespace(value="cpc"),
                            SimpleNamespace(value="spring_launch"),
                        ],
                        metric_values=[
                            SimpleNamespace(value="120"),
                            SimpleNamespace(value="100"),
                            SimpleNamespace(value="40"),
                            SimpleNamespace(value="0.42"),
                            SimpleNamespace(value="83.5"),
                            SimpleNamespace(value="5"),
                            SimpleNamespace(value="21"),
                        ],
                    )
                ]
            )

    monkeypatch.setattr(
        "integrations.google_analytics.client._import_ga4_symbols",
        lambda: (
            FakeBetaAnalyticsDataClient,
            FakeCredentials,
            (DateRange, Dimension, Metric, RunReportRequest, OrderBy),
        ),
    )

    client = GoogleAnalyticsClient(credential=credential)
    rows = client.fetch_traffic_acquisition(
        property_id="123456789",
        start_date=date(2026, 3, 17),
        end_date=date(2026, 3, 17),
    )

    request = FakeBetaAnalyticsDataClient.last_request
    assert request.property == "properties/123456789"
    assert [dimension.name for dimension in request.dimensions] == [
        "date",
        "sessionSource",
        "sessionMedium",
        "sessionCampaignName",
    ]
    assert [metric.name for metric in request.metrics] == [
        "sessions",
        "totalUsers",
        "newUsers",
        "engagementRate",
        "averageSessionDuration",
        "keyEvents",
        "eventCount",
    ]
    assert request.date_ranges[0].start_date == "2026-03-17"
    assert request.date_ranges[0].end_date == "2026-03-17"

    credentials_kwargs = FakeBetaAnalyticsDataClient.last_credentials.kwargs
    assert credentials_kwargs["token"] == "access-token"
    assert credentials_kwargs["refresh_token"] == "refresh-token"
    assert credentials_kwargs["client_id"] == "ga4-client-id"
    assert credentials_kwargs["client_secret"] == "ga4-client-secret"
    assert credentials_kwargs["scopes"] == ["https://www.googleapis.com/auth/analytics.readonly"]

    assert rows == [
        Ga4DailyRow(
            property_id="123456789",
            date_day=date(2026, 3, 17),
            source="google",
            medium="cpc",
            campaign="spring_launch",
            sessions=120,
            users=100,
            new_users=40,
            engagement_rate=0.42,
            average_session_duration=83.5,
            conversions=5,
            event_count=21,
        )
    ]


def test_google_analytics_client_raises_when_refresh_token_missing(tenant, settings):
    settings.GOOGLE_ANALYTICS_CLIENT_ID = "ga4-client-id"
    settings.GOOGLE_ANALYTICS_CLIENT_SECRET = "ga4-client-secret"
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.GOOGLE_ANALYTICS,
        account_id="ga4@example.com",
    )
    credential.set_raw_tokens("access-token", None)
    credential.save()

    with pytest.raises(GoogleAnalyticsClientError) as excinfo:
        GoogleAnalyticsClient(credential=credential)

    assert excinfo.value.classification == "credential_missing_refresh_token"


def test_google_analytics_adapter_fetch_metrics_aggregates_rows(monkeypatch, tenant):
    credential = _make_credential(tenant)
    GoogleAnalyticsConnection.objects.create(
        tenant=tenant,
        credentials=credential,
        property_id="123456789",
        property_name="Primary Property",
        is_active=True,
        sync_frequency="daily",
    )

    monkeypatch.setattr(
        "adapters.google_analytics.GoogleAnalyticsClient.fetch_traffic_acquisition",
        lambda self, *, property_id, start_date, end_date: [  # noqa: ARG005
            Ga4DailyRow(
                property_id=property_id,
                date_day=date(2026, 3, 16),
                source="google",
                medium="cpc",
                campaign="spring_launch",
                sessions=100,
                users=80,
                new_users=20,
                engagement_rate=0.5,
                average_session_duration=60.0,
                conversions=4,
                event_count=18,
            ),
            Ga4DailyRow(
                property_id=property_id,
                date_day=date(2026, 3, 17),
                source="google",
                medium="organic",
                campaign="brand",
                sessions=50,
                users=40,
                new_users=10,
                engagement_rate=0.2,
                average_session_duration=30.0,
                conversions=2,
                event_count=8,
            ),
        ],
    )
    monkeypatch.setattr(
        "adapters.google_analytics.GoogleAnalyticsClient._build_client",
        lambda self: object(),
    )

    adapter = GoogleAnalyticsAdapter()
    with tenant_context(str(tenant.id)):
        payload = adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={"start_date": date(2026, 3, 16), "end_date": date(2026, 3, 17)},
        )

    assert payload["summary"] == {
        "sessions": 150,
        "users": 120,
        "new_users": 30,
        "engagement_rate": pytest.approx(0.4),
        "average_session_duration": pytest.approx(50.0),
        "conversions": 6,
        "event_count": 26,
    }
    assert payload["rows"] == [
        {
            "date": "2026-03-16",
            "source": "google",
            "medium": "cpc",
            "campaign": "spring_launch",
            "sessions": 100,
            "users": 80,
            "new_users": 20,
            "engagement_rate": 0.5,
            "average_session_duration": 60.0,
            "conversions": 4,
            "event_count": 18,
        },
        {
            "date": "2026-03-17",
            "source": "google",
            "medium": "organic",
            "campaign": "brand",
            "sessions": 50,
            "users": 40,
            "new_users": 10,
            "engagement_rate": 0.2,
            "average_session_duration": 30.0,
            "conversions": 2,
            "event_count": 8,
        },
    ]


def test_google_analytics_adapter_prefers_latest_active_connection(monkeypatch, tenant):
    older_credential = _make_credential(tenant, account_id="older@example.com")
    latest_credential = _make_credential(tenant, account_id="latest@example.com")
    GoogleAnalyticsConnection.objects.create(
        tenant=tenant,
        credentials=older_credential,
        property_id="111111111",
        property_name="Legacy Property",
        is_active=True,
        sync_frequency="daily",
    )
    latest_connection = GoogleAnalyticsConnection.objects.create(
        tenant=tenant,
        credentials=latest_credential,
        property_id="222222222",
        property_name="Primary Property",
        is_active=True,
        sync_frequency="daily",
    )
    captured: dict[str, str] = {}

    def _fake_fetch(self, *, property_id, start_date, end_date):  # noqa: ANN001, ARG001
        captured["property_id"] = property_id
        return []

    monkeypatch.setattr(
        "adapters.google_analytics.GoogleAnalyticsClient.fetch_traffic_acquisition",
        _fake_fetch,
    )
    monkeypatch.setattr(
        "adapters.google_analytics.GoogleAnalyticsClient._build_client",
        lambda self: object(),
    )

    adapter = GoogleAnalyticsAdapter()
    with tenant_context(str(tenant.id)):
        adapter.fetch_metrics(
            tenant_id=str(tenant.id),
            options={"start_date": date(2026, 3, 16), "end_date": date(2026, 3, 17)},
        )

    assert captured["property_id"] == latest_connection.property_id
