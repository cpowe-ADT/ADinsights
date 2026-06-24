from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

import integrations.services.metric_registry as metric_registry
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
from integrations.services.metric_registry import get_default_metric_keys, seed_default_metrics
from integrations.tasks import (
    RETRY_REASON_META_GRAPH_CLIENT_ERROR,
    RETRY_REASON_META_GRAPH_RATE_LIMITED,
    RETRY_REASON_META_GRAPH_TRANSPORT,
    RETRY_REASON_META_GRAPH_UPSTREAM_TIMEOUT,
    RETRY_REASON_META_GRAPH_UPSTREAM_5XX,
    _classify_meta_insights_retry_reason,
    sync_meta_page_insights,
    sync_meta_post_insights,
    sync_page_posts,
)


def _create_page(user) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="app-scoped-user",
        scopes=["pages_show_list", "pages_read_engagement"],
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
def test_default_metric_seed_refreshes_existing_stale_registry_rows():
    MetaMetricRegistry.objects.update_or_create(
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key="page_views_total",
        defaults={
            "supported_periods": ["day"],
            "supports_breakdowns": [],
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "is_default": True,
        },
    )

    seed_default_metrics()

    metric = MetaMetricRegistry.objects.get(
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key="page_views_total",
    )
    assert metric.status == MetaMetricRegistry.STATUS_UNKNOWN
    assert metric.is_default is False
    assert "page_views_total" not in get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE)


@pytest.mark.django_db
def test_default_metric_keys_include_governed_reporting_sources_without_legacy_impressions():
    MetaMetricRegistry.objects.all().delete()
    metric_registry._metrics_seeded = False

    page_metrics = get_default_metric_keys(MetaMetricRegistry.LEVEL_PAGE)
    post_metrics = get_default_metric_keys(MetaMetricRegistry.LEVEL_POST)

    assert "page_media_view" in page_metrics
    assert "page_total_media_view_unique" in page_metrics
    assert "page_post_engagements" in page_metrics
    assert "page_impressions" not in page_metrics
    assert "page_impressions_unique" not in page_metrics
    assert "page_views_total" not in page_metrics
    assert "post_reactions_by_type_total" in post_metrics
    assert "post_impressions" not in post_metrics
    assert "post_impressions_unique" not in post_metrics


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
def test_sync_meta_page_insights_skips_unreadable_connection_token(monkeypatch, user):
    page = _create_page(user)
    connection = page.connection
    connection.token_tag = b"0" * 16
    connection.save(update_fields=["token_tag"])

    seen_tokens: list[str] = []

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            seen_tokens.append(kwargs["token"])
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

    result = sync_meta_page_insights.run(page_pk=str(page.pk), mode="incremental", metrics=["page_post_engagements"])

    assert result["rows_processed"] == 1
    assert seen_tokens == ["page-token"]
    assert MetaInsightPoint.all_objects.filter(page=page, metric_key="page_post_engagements").exists()


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
    assert metric.replacement_metric_key == "page_total_media_view_unique"


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
def test_sync_meta_page_insights_uses_fixed_date_window(monkeypatch, user):
    page = _create_page(user)
    captured: dict[str, str] = {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            captured["since"] = kwargs["since"]
            captured["until"] = kwargs["until"]
            return {
                "data": [
                    {
                        "name": "page_post_engagements",
                        "period": "day",
                        "values": [
                            {
                                "value": 42,
                                "end_time": "2026-05-31T08:00:00+0000",
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(
        page_pk=str(page.pk),
        mode="backfill",
        metrics=["page_post_engagements"],
        since="2026-05-01",
        until="2026-05-31",
    )

    assert result["rows_processed"] == 1
    assert captured == {"since": "2026-05-01", "until": "2026-05-31"}


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
                "Missing permission: pages_read_engagement",
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


@pytest.mark.django_db
def test_sync_meta_page_insights_retries_retryable_errors_with_reason(monkeypatch, user):
    page = _create_page(user)
    captured: dict[str, object] = {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            raise MetaInsightsGraphClientError(
                "Upstream unavailable",
                status_code=503,
                retryable=True,
            )

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None, reason=None):  # noqa: ANN001
        captured["exc"] = exc
        captured["reason"] = reason
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())
    monkeypatch.setattr("integrations.tasks.BaseAdInsightsTask.retry_with_backoff", fake_retry)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        sync_meta_page_insights.run(page_pk=str(page.pk), metrics=["page_post_engagements"])

    assert isinstance(captured["exc"], MetaInsightsGraphClientError)
    assert captured["reason"] == RETRY_REASON_META_GRAPH_UPSTREAM_5XX


@pytest.mark.django_db
def test_sync_meta_post_insights_retries_retryable_errors_with_reason(monkeypatch, user):
    page = _create_page(user)
    captured: dict[str, object] = {}

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
            raise MetaInsightsGraphClientError(
                "Rate limit exceeded",
                error_code=80001,
                retryable=True,
            )

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None, reason=None):  # noqa: ANN001
        captured["exc"] = exc
        captured["reason"] = reason
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())
    monkeypatch.setattr("integrations.tasks.BaseAdInsightsTask.retry_with_backoff", fake_retry)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        sync_meta_post_insights.run(page_pk=str(page.pk), metrics=["post_reactions_like_total"])

    assert isinstance(captured["exc"], MetaInsightsGraphClientError)
    assert captured["reason"] == RETRY_REASON_META_GRAPH_RATE_LIMITED


@pytest.mark.django_db
def test_sync_page_posts_retries_retryable_errors_with_reason(monkeypatch, user):
    _create_page(user)
    captured: dict[str, object] = {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_posts(self, **kwargs):  # noqa: ANN003
            raise MetaInsightsGraphClientError(
                "Upstream unavailable",
                status_code=503,
                retryable=True,
            )

    def fake_retry(self, *, exc=None, base_delay=None, max_delay=None, reason=None):  # noqa: ANN001
        captured["exc"] = exc
        captured["reason"] = reason
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())
    monkeypatch.setattr("integrations.tasks.BaseAdInsightsTask.retry_with_backoff", fake_retry)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        sync_page_posts.run(page_id="page-1", mode="incremental")

    assert isinstance(captured["exc"], MetaInsightsGraphClientError)
    assert captured["reason"] == RETRY_REASON_META_GRAPH_UPSTREAM_5XX


@pytest.mark.parametrize(
    ("exc", "expected_reason"),
    [
        (
            MetaInsightsGraphClientError(
                "gateway timeout",
                status_code=504,
                retryable=True,
            ),
            RETRY_REASON_META_GRAPH_UPSTREAM_TIMEOUT,
        ),
        (
            MetaInsightsGraphClientError(
                "transport",
                retryable=True,
            ),
            RETRY_REASON_META_GRAPH_TRANSPORT,
        ),
        (
            MetaInsightsGraphClientError(
                "conflict",
                status_code=409,
                retryable=True,
            ),
            RETRY_REASON_META_GRAPH_CLIENT_ERROR,
        ),
    ],
)
def test_classify_meta_insights_retry_reason_prefers_explicit_reason_groups(exc, expected_reason):
    assert _classify_meta_insights_retry_reason(exc) == expected_reason
