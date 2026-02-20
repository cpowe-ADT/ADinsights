from __future__ import annotations

import pytest

from integrations.meta_page_insights.meta_client import MetaPageInsightsApiError
from integrations.models import MetaConnection, MetaInsightPoint, MetaPage
from integrations.services.meta_graph_client import MetaInsightsGraphClientError
from integrations.tasks import discover_supported_metrics, sync_meta_page_insights


def _create_page(user) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="meta-user-sync",
        scopes=["read_insights", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id="page-sync-1",
        name="Sync Page",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


@pytest.mark.django_db
def test_sync_job_handles_invalid_metric_and_still_ingests_valid_metric(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_page_insights(self, **kwargs):  # noqa: ANN003
            metrics = kwargs["metrics"]
            if "invalid_metric" in metrics:
                raise MetaInsightsGraphClientError(
                    "(#100) invalid metric",
                    error_code=100,
                    retryable=False,
                )
            return {
                "data": [
                    {
                        "name": "page_post_engagements",
                        "period": "day",
                        "values": [{"value": 20, "end_time": "2026-02-18T08:00:00+0000"}],
                    }
                ]
            }

    monkeypatch.setattr("integrations.tasks.MetaInsightsGraphClient.from_settings", lambda: DummyClient())

    result = sync_meta_page_insights.run(
        page_pk=str(page.pk),
        metrics=["invalid_metric", "page_post_engagements"],
    )
    assert result["rows_processed"] >= 1
    assert MetaInsightPoint.all_objects.filter(page=page, metric_key="page_post_engagements").exists()


@pytest.mark.django_db
def test_discover_supported_metrics_handles_missing_metric_error(monkeypatch, user):
    page = _create_page(user)

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return None

        def fetch_insights(self, **kwargs):  # noqa: ANN003
            raise MetaPageInsightsApiError(
                "No metric was specified",
                error_code=3001,
                error_subcode=1504028,
                retryable=False,
            )

    monkeypatch.setattr(
        "integrations.meta_page_insights.insights_discovery.MetaPageInsightsClient.from_settings",
        lambda: DummyClient(),
    )

    result = discover_supported_metrics.run(page_id=page.page_id)
    assert result["pages_processed"] == 1
