from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.db import OperationalError
from django.urls import reverse
from django.utils import timezone

from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaMetricSupportStatus,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.tasks import sync_meta_page_insights, sync_meta_post_insights


def _authenticate(api_client, *, username: str, password: str) -> None:
    token = api_client.post(
        reverse("token_obtain_pair"),
        {"username": username, "password": password},
        format="json",
    ).json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _create_page(user) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="meta-user-api",
        scopes=["read_insights", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id="page-api-1",
        name="API Page",
        category="Business",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


@pytest.mark.django_db
def test_meta_page_contract_endpoints_return_metric_availability(api_client, user):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)

    MetaMetricRegistry.objects.update_or_create(
        metric_key="page_post_engagements",
        level=MetaMetricRegistry.LEVEL_PAGE,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": ["day"],
            "supports_breakdowns": [],
        },
    )
    MetaMetricSupportStatus.objects.update_or_create(
        tenant=user.tenant,
        page=page,
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key="page_post_engagements",
        defaults={
            "supported": True,
            "last_checked_at": datetime(2026, 2, 19, 10, 0, tzinfo=dt_timezone.utc),
            "last_error": {},
        },
    )
    MetaInsightPoint.all_objects.create(
        tenant=user.tenant,
        page=page,
        metric_key="page_post_engagements",
        period="day",
        end_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        value_num=55,
        breakdown_key_normalized="__none__",
    )

    post = MetaPost.all_objects.create(
        tenant=user.tenant,
        page=page,
        post_id="page-api-1_1",
        created_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        message="hello world",
        media_type="PHOTO",
        permalink_url="https://example.com/post/1",
    )
    MetaMetricRegistry.objects.update_or_create(
        metric_key="post_media_view",
        level=MetaMetricRegistry.LEVEL_POST,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": ["lifetime"],
            "supports_breakdowns": [],
        },
    )
    MetaPostInsightPoint.all_objects.create(
        tenant=user.tenant,
        post=post,
        metric_key="post_media_view",
        period="lifetime",
        end_time=datetime(2026, 2, 18, 8, 0, tzinfo=dt_timezone.utc),
        value_num=12,
        breakdown_key_normalized="__none__",
    )

    pages = api_client.get(reverse("meta-pages-insights-list"))
    assert pages.status_code == 200
    assert pages.json()["count"] == 1

    overview = api_client.get(reverse("meta-page-insights-overview", kwargs={"page_id": page.page_id}))
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert "metric_availability" in overview_payload
    assert "kpis" in overview_payload
    assert overview_payload["page_id"] == page.page_id

    page_timeseries = api_client.get(
        reverse("meta-page-insights-timeseries", kwargs={"page_id": page.page_id}),
        {"metric": "page_post_engagements", "period": "day", "date_preset": "last_28d"},
    )
    assert page_timeseries.status_code == 200
    page_timeseries_payload = page_timeseries.json()
    assert page_timeseries_payload["metric"] == "page_post_engagements"
    assert "metric_availability" in page_timeseries_payload
    assert len(page_timeseries_payload["points"]) >= 1

    posts = api_client.get(reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}))
    assert posts.status_code == 200
    posts_payload = posts.json()
    assert "metric_availability" in posts_payload
    assert len(posts_payload["results"]) == 1
    assert "count" in posts_payload
    assert "limit" in posts_payload
    assert "offset" in posts_payload

    detail = api_client.get(reverse("meta-post-insights-detail", kwargs={"post_id": post.post_id}))
    assert detail.status_code == 200
    assert "metric_availability" in detail.json()

    post_timeseries = api_client.get(
        reverse("meta-post-insights-timeseries", kwargs={"post_id": post.post_id}),
        {"metric": "post_media_view"},
    )
    assert post_timeseries.status_code == 200
    assert "metric_availability" in post_timeseries.json()

    metrics_list = api_client.get(reverse("meta-metrics-list"), {"level": "PAGE"})
    assert metrics_list.status_code == 200
    assert "results" in metrics_list.json()


@pytest.mark.django_db
def test_meta_page_sync_pipeline_surfaces_graph_data_in_api(api_client, user, monkeypatch):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)

    MetaMetricRegistry.objects.update_or_create(
        metric_key="page_post_engagements",
        level=MetaMetricRegistry.LEVEL_PAGE,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": ["day"],
            "supports_breakdowns": [],
        },
    )
    MetaMetricRegistry.objects.update_or_create(
        metric_key="post_media_view",
        level=MetaMetricRegistry.LEVEL_POST,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": ["lifetime"],
            "supports_breakdowns": [],
        },
    )

    target_day = timezone.localdate() - timedelta(days=1)
    target_end_time = f"{target_day.isoformat()}T08:00:00+0000"

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            return {
                "data": [
                    {
                        "name": "page_post_engagements",
                        "period": "day",
                        "values": [
                            {
                                "value": 33,
                                "end_time": target_end_time,
                            }
                        ],
                    }
                ]
            }

        def fetch_page_posts(self, **kwargs):  # noqa: ANN003
            return [
                {
                    "id": f"{page.page_id}_post_1",
                    "message": "Fresh post from graph sync",
                    "permalink_url": "https://facebook.com/post/1",
                    "created_time": target_end_time,
                    "updated_time": target_end_time,
                    "attachments": {"data": [{"media_type": "video"}]},
                }
            ]

        def fetch_post_insights(self, **kwargs):  # noqa: ANN003
            return {
                "data": [
                    {
                        "name": "post_media_view",
                        "period": "lifetime",
                        "values": [{"value": 77}],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    page_sync = sync_meta_page_insights.run(
        page_pk=str(page.pk),
        mode="incremental",
        metrics=["page_post_engagements"],
    )
    post_sync = sync_meta_post_insights.run(
        page_pk=str(page.pk),
        mode="incremental",
        metrics=["post_media_view"],
    )
    assert page_sync["rows_processed"] >= 1
    assert post_sync["rows_processed"] >= 1

    overview = api_client.get(
        reverse("meta-page-insights-overview", kwargs={"page_id": page.page_id}),
        {"since": target_day.isoformat(), "until": target_day.isoformat()},
    )
    assert overview.status_code == 200
    overview_payload = overview.json()
    engagement_kpi = next(item for item in overview_payload["kpis"] if item["metric"] == "page_post_engagements")
    assert engagement_kpi["value"] == 33
    assert engagement_kpi["today_value"] == 33

    page_timeseries = api_client.get(
        reverse("meta-page-insights-timeseries", kwargs={"page_id": page.page_id}),
        {
            "metric": "page_post_engagements",
            "period": "day",
            "since": target_day.isoformat(),
            "until": target_day.isoformat(),
        },
    )
    assert page_timeseries.status_code == 200
    timeseries_points = page_timeseries.json()["points"]
    assert len(timeseries_points) == 1
    assert timeseries_points[0]["value"] == 33

    posts = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"since": target_day.isoformat(), "until": target_day.isoformat()},
    )
    assert posts.status_code == 200
    posts_payload = posts.json()
    assert posts_payload["count"] == 1
    assert posts_payload["results"][0]["metrics"]["post_media_view"] == 77
    assert posts_payload["results"][0]["media_type"] == "VIDEO"
    assert "Fresh post from graph sync" in posts_payload["results"][0]["message_snippet"]


@pytest.mark.django_db
def test_meta_page_posts_support_filtering_sorting_and_pagination(api_client, user):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)

    MetaMetricRegistry.objects.update_or_create(
        metric_key="post_media_view",
        level=MetaMetricRegistry.LEVEL_POST,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": ["lifetime"],
            "supports_breakdowns": [],
        },
    )

    post_a = MetaPost.all_objects.create(
        tenant=user.tenant,
        page=page,
        post_id="page-api-1_a",
        created_time=datetime(2026, 2, 18, 9, 0, tzinfo=dt_timezone.utc),
        message="hello photo",
        media_type="PHOTO",
        permalink_url="https://example.com/post/a",
    )
    post_b = MetaPost.all_objects.create(
        tenant=user.tenant,
        page=page,
        post_id="page-api-1_b",
        created_time=datetime(2026, 2, 18, 10, 0, tzinfo=dt_timezone.utc),
        message="hello video",
        media_type="VIDEO",
        permalink_url="https://example.com/post/b",
    )

    MetaPostInsightPoint.all_objects.create(
        tenant=user.tenant,
        post=post_a,
        metric_key="post_media_view",
        period="lifetime",
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=dt_timezone.utc),
        value_num=5,
        breakdown_key_normalized="__none__",
    )
    MetaPostInsightPoint.all_objects.create(
        tenant=user.tenant,
        post=post_b,
        metric_key="post_media_view",
        period="lifetime",
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=dt_timezone.utc),
        value_num=50,
        breakdown_key_normalized="__none__",
    )

    filtered = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"q": "photo"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filtered.json()["results"][0]["post_id"] == post_a.post_id

    media_type_filtered = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"media_type": "VIDEO"},
    )
    assert media_type_filtered.status_code == 200
    assert media_type_filtered.json()["count"] == 1
    assert media_type_filtered.json()["results"][0]["post_id"] == post_b.post_id

    sorted_by_metric = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"sort": "metric_desc", "sort_metric": "post_media_view"},
    )
    assert sorted_by_metric.status_code == 200
    assert sorted_by_metric.json()["results"][0]["post_id"] == post_b.post_id

    page_1 = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"limit": 1, "offset": 0},
    )
    assert page_1.status_code == 200
    assert page_1.json()["limit"] == 1
    assert page_1.json()["offset"] == 0
    assert page_1.json()["next_offset"] == 1
    assert len(page_1.json()["results"]) == 1


@pytest.mark.django_db
def test_meta_page_exports_endpoint_creates_export_job(api_client, user, monkeypatch):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)

    class DummyDelay:
        def delay(self, _job_id):  # noqa: ANN001
            return None

    monkeypatch.setattr("analytics.tasks.run_report_export_job", DummyDelay())

    create = api_client.post(
        reverse("meta-page-exports", kwargs={"page_id": page.page_id}),
        {"export_format": "csv", "date_preset": "last_28d"},
        format="json",
    )
    assert create.status_code == 201
    payload = create.json()
    assert payload["export_format"] == "csv"
    assert payload["status"] in {"queued", "running", "completed", "failed"}

    listing = api_client.get(reverse("meta-page-exports", kwargs={"page_id": page.page_id}))
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)


@pytest.mark.django_db
def test_meta_page_sync_endpoint_triggers_all_tasks(api_client, user, monkeypatch):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)

    class DummyTask:
        def __init__(self, task_id: str):
            self.id = task_id

    monkeypatch.setattr(
        "integrations.page_insights_views.sync_page_posts.delay",
        lambda **kwargs: DummyTask("posts-task"),
    )
    monkeypatch.setattr(
        "integrations.page_insights_views.discover_supported_metrics.delay",
        lambda **kwargs: DummyTask("discover-task"),
    )
    monkeypatch.setattr(
        "integrations.page_insights_views.sync_page_insights.delay",
        lambda **kwargs: DummyTask("page-task"),
    )
    monkeypatch.setattr(
        "integrations.page_insights_views.sync_post_insights.delay",
        lambda **kwargs: DummyTask("post-task"),
    )

    response = api_client.post(
        reverse("meta-page-insights-sync", kwargs={"page_id": page.page_id}),
        {"mode": "incremental"},
        format="json",
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["tasks"]["sync_page_posts"] == "posts-task"
    assert payload["tasks"]["discover_supported_metrics"] == "discover-task"
    assert payload["tasks"]["sync_page_insights"] == "page-task"
    assert payload["tasks"]["sync_post_insights"] == "post-task"


@pytest.mark.django_db
def test_meta_page_sync_endpoint_blocks_when_required_permissions_missing(api_client, user):
    _authenticate(api_client, username="user@example.com", password="password123")
    page = _create_page(user)
    page.connection.scopes = ["pages_read_engagement"]
    page.connection.save(update_fields=["scopes", "updated_at"])

    response = api_client.post(
        reverse("meta-page-insights-sync", kwargs={"page_id": page.page_id}),
        {"mode": "incremental"},
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["missing_required_permissions"] == ["read_insights"]


@pytest.mark.django_db
def test_meta_page_list_returns_schema_out_of_date_when_db_is_behind(
    api_client,
    user,
    monkeypatch,
):
    _authenticate(api_client, username="user@example.com", password="password123")

    def _raise_schema_error(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OperationalError("no such table: integrations_metapage")

    monkeypatch.setattr("integrations.page_insights_views.MetaPage.objects.filter", _raise_schema_error)

    response = api_client.get(reverse("meta-pages-insights-list"))

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "schema_out_of_date"
    assert "Run backend migrations" in payload["detail"]


@pytest.mark.django_db
def test_meta_page_overview_returns_schema_out_of_date_when_db_is_behind(
    api_client,
    user,
    monkeypatch,
):
    _authenticate(api_client, username="user@example.com", password="password123")

    def _raise_schema_error(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OperationalError("no such table: integrations_metapage")

    monkeypatch.setattr("integrations.page_insights_views.MetaPage.objects.filter", _raise_schema_error)

    response = api_client.get(
        reverse("meta-page-insights-overview", kwargs={"page_id": "page-api-1"}),
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "schema_out_of_date"
    assert "Run backend migrations" in payload["detail"]
