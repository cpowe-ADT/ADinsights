from __future__ import annotations

import pytest

from integrations.meta_page_insights.insights_discovery import validate_metrics
from integrations.meta_page_insights.meta_client import MetaPageInsightsApiError
from integrations.models import MetaConnection, MetaMetricSupportStatus, MetaPage


def _create_page(user) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="meta-user-1",
        scopes=["read_insights", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("user-token")
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id="page-1",
        name="Discovery Page",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


@pytest.mark.django_db
def test_validate_metrics_binary_split_marks_single_invalid_metric(user):
    page = _create_page(user)

    class DummyClient:
        def fetch_insights(self, **kwargs):  # noqa: ANN003
            metrics = kwargs["metrics"]
            if "invalid_metric" in metrics:
                raise MetaPageInsightsApiError(
                    "(#100) invalid metric",
                    error_code=100,
                    retryable=False,
                )
            return {"data": []}

    support = validate_metrics(
        page=page,
        object_id=page.page_id,
        object_type="page",
        metrics=["page_post_engagements", "invalid_metric", "page_total_actions"],
        token="token",
        client=DummyClient(),
    )

    assert support["invalid_metric"] is False
    assert support["page_post_engagements"] is True
    assert support["page_total_actions"] is True

    invalid_status = MetaMetricSupportStatus.objects.get(page=page, metric_key="invalid_metric")
    assert invalid_status.supported is False
    assert invalid_status.last_error["error_code"] == 100


@pytest.mark.django_db
def test_validate_metrics_binary_split_marks_multiple_invalid_metrics(user):
    page = _create_page(user)

    class DummyClient:
        def fetch_insights(self, **kwargs):  # noqa: ANN003
            metrics = kwargs["metrics"]
            if any(metric in {"bad_a", "bad_b"} for metric in metrics):
                raise MetaPageInsightsApiError(
                    "(#100) invalid metric",
                    error_code=100,
                    retryable=False,
                )
            return {"data": []}

    support = validate_metrics(
        page=page,
        object_id=page.page_id,
        object_type="page",
        metrics=["bad_a", "page_post_engagements", "bad_b", "page_views_total"],
        token="token",
        client=DummyClient(),
    )

    assert support["bad_a"] is False
    assert support["bad_b"] is False
    assert support["page_post_engagements"] is True
    assert support["page_views_total"] is True
