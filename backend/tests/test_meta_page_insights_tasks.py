from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaMetricSupportStatus,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)
from integrations.services.meta_graph_client import MetaInsightsGraphClientError
from integrations.tasks import sync_meta_page_insights, sync_meta_post_insights


def _create_page(user) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="app-scoped-user",
        scopes=["read_insights", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id="page-1",
        name="Business Page",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


@pytest.mark.django_db
def test_sync_meta_page_insights_handles_empty_dataset(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            return {"data": []}

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(page_pk=str(page.pk), mode="incremental", metrics=["page_post_engagements"])
    assert result["rows_processed"] == 0
    assert MetaInsightPoint.all_objects.count() == 0


@pytest.mark.django_db
def test_sync_meta_page_insights_marks_invalid_metric_on_100(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            raise MetaInsightsGraphClientError(
                "(#100) The value must be a valid insights metric",
                error_code=100,
                retryable=False,
            )

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_impressions_unique"])
    assert result["rows_processed"] == 0

    metric = MetaMetricRegistry.objects.get(level=MetaMetricRegistry.LEVEL_PAGE, metric_key="page_impressions_unique")
    assert metric.status == MetaMetricRegistry.STATUS_INVALID
    assert metric.replacement_metric_key == "page_views_total"


@pytest.mark.django_db
def test_sync_meta_page_insights_handles_missing_metric_error_3001(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            raise MetaInsightsGraphClientError(
                "No metric was specified",
                error_code=3001,
                error_subcode=1504028,
                retryable=False,
            )

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])
    assert result["rows_processed"] == 0
    assert MetaInsightPoint.all_objects.count() == 0


@pytest.mark.django_db
def test_sync_meta_page_insights_upsert_is_idempotent(monkeypatch, user):
    page = _create_page(user)

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
                                "value": 99,
                                "end_time": "2026-02-18T08:00:00+0000",
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    first = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])
    second = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])
    assert first["rows_processed"] == 1
    assert second["rows_processed"] == 1
    assert MetaInsightPoint.all_objects.count() == 1


@pytest.mark.django_db
def test_sync_meta_page_insights_retries_with_connection_token(monkeypatch, user):
    page = _create_page(user)
    page.set_raw_page_token("expired-page-token")
    page.save(update_fields=["page_token_enc", "page_token_nonce", "page_token_tag", "updated_at"])

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            if kwargs["token"] == "expired-page-token":
                raise MetaInsightsGraphClientError(
                    "OAuth token expired",
                    error_code=190,
                    retryable=False,
                )
            return {
                "data": [
                    {
                        "name": "page_post_engagements",
                        "period": "day",
                        "values": [
                            {
                                "value": 12,
                                "end_time": "2026-02-18T08:00:00+0000",
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])
    assert result["rows_processed"] == 1
    assert MetaInsightPoint.all_objects.filter(page=page, metric_key="page_post_engagements").exists()
    support = MetaMetricSupportStatus.all_objects.get(
        tenant=page.tenant,
        page=page,
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key="page_post_engagements",
    )
    assert support.supported is True


@pytest.mark.django_db
def test_sync_meta_page_insights_marks_support_error_for_permission_failure(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            raise MetaInsightsGraphClientError(
                "Missing permission: read_insights",
                error_code=10,
                retryable=False,
            )

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])
    assert result["rows_processed"] == 0
    support = MetaMetricSupportStatus.all_objects.get(
        tenant=page.tenant,
        page=page,
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key="page_post_engagements",
    )
    assert support.supported is False
    assert support.last_error["error_code"] == 10


@pytest.mark.django_db
def test_sync_meta_post_insights_upserts_post_points(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_posts(self, **kwargs):  # noqa: ANN003
            return [
                {
                    "id": "page-1_111",
                    "message": "Hello",
                    "permalink_url": "https://example.com/post/111",
                    "created_time": "2026-02-10T08:00:00+0000",
                    "updated_time": "2026-02-10T08:00:00+0000",
                }
            ]

        def fetch_post_insights(self, **kwargs):  # noqa: ANN003
            return {
                "data": [
                    {
                        "name": "post_reactions_like_total",
                        "period": "lifetime",
                        "values": [{"value": 226}],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_post_insights.run(page_pk=str(page.pk), metrics=["post_reactions_like_total"])
    assert result["posts_processed"] == 1

    post = MetaPost.all_objects.get(page=page, post_id="page-1_111")
    point = MetaPostInsightPoint.all_objects.get(post=post, metric_key="post_reactions_like_total")
    assert point.value_num == 226
    assert point.end_time == datetime(2026, 2, 10, 8, 0, tzinfo=dt_timezone.utc)
