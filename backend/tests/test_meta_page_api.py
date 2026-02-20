from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import OperationalError
from django.urls import reverse

from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaMetricSupportStatus,
    MetaMetricRegistry,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)


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

    posts = api_client.get(reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}))
    assert posts.status_code == 200
    posts_payload = posts.json()
    assert "metric_availability" in posts_payload
    assert len(posts_payload["results"]) == 1

    detail = api_client.get(reverse("meta-post-insights-detail", kwargs={"post_id": post.post_id}))
    assert detail.status_code == 200
    assert "metric_availability" in detail.json()

    post_timeseries = api_client.get(
        reverse("meta-post-insights-timeseries", kwargs={"post_id": post.post_id}),
        {"metric": "post_media_view"},
    )
    assert post_timeseries.status_code == 200
    assert "metric_availability" in post_timeseries.json()


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
