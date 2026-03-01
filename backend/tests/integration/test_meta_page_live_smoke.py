from __future__ import annotations

import os

import pytest
from django.urls import reverse

from integrations.models import MetaConnection, MetaMetricRegistry, MetaMetricSupportStatus, MetaPage
from integrations.tasks import sync_meta_page_insights, sync_meta_post_insights


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _is_truthy(name: str) -> bool:
    return _env(name).lower() in {"1", "true", "yes", "y", "on"}


def _live_smoke_config_or_skip() -> dict[str, str]:
    if not _is_truthy("META_LIVE_SMOKE_ENABLED"):
        pytest.skip(
            "Set META_LIVE_SMOKE_ENABLED=1 to run live Meta Page Insights smoke test."
        )

    required = ("META_LIVE_SMOKE_USER_TOKEN", "META_LIVE_SMOKE_PAGE_ID")
    missing = [key for key in required if not _env(key)]
    if missing:
        pytest.skip(
            "Missing required live smoke env vars: "
            f"{', '.join(missing)}. Required: META_LIVE_SMOKE_USER_TOKEN, META_LIVE_SMOKE_PAGE_ID."
        )

    return {
        "user_token": _env("META_LIVE_SMOKE_USER_TOKEN"),
        "page_id": _env("META_LIVE_SMOKE_PAGE_ID"),
        "page_token": _env("META_LIVE_SMOKE_PAGE_TOKEN"),
        "page_name": _env("META_LIVE_SMOKE_PAGE_NAME") or "Live Smoke Page",
        "page_metric": _env("META_LIVE_SMOKE_PAGE_METRIC") or "page_post_engagements",
        "post_metric": _env("META_LIVE_SMOKE_POST_METRIC") or "post_media_view",
    }


def _create_page(user, *, page_id: str, page_name: str, user_token: str, page_token: str) -> MetaPage:
    connection = MetaConnection(
        tenant=user.tenant,
        user=user,
        app_scoped_user_id="meta-live-smoke-user",
        scopes=["read_insights", "pages_read_engagement", "pages_read_user_content"],
        is_active=True,
    )
    connection.set_raw_token(user_token)
    connection.save()

    page = MetaPage(
        tenant=user.tenant,
        connection=connection,
        page_id=page_id,
        name=page_name,
        category="Live",
        can_analyze=True,
        tasks=["ANALYZE"],
        is_default=True,
    )
    page.set_raw_page_token(page_token)
    page.save()
    return page


def _seed_metric(*, metric_key: str, level: str, period: str) -> None:
    MetaMetricRegistry.objects.update_or_create(
        metric_key=metric_key,
        level=level,
        defaults={
            "is_default": True,
            "status": MetaMetricRegistry.STATUS_ACTIVE,
            "supported_periods": [period],
            "supports_breakdowns": [],
        },
    )


@pytest.mark.django_db
@pytest.mark.integration
def test_meta_live_smoke_sync_pulls_graph_data_and_surfaces_in_dashboard(api_client, user):
    config = _live_smoke_config_or_skip()
    page_metric = config["page_metric"]
    post_metric = config["post_metric"]

    api_client.force_authenticate(user=user)
    page = _create_page(
        user,
        page_id=config["page_id"],
        page_name=config["page_name"],
        user_token=config["user_token"],
        page_token=config["page_token"] or config["user_token"],
    )

    _seed_metric(metric_key=page_metric, level=MetaMetricRegistry.LEVEL_PAGE, period="day")
    _seed_metric(metric_key=post_metric, level=MetaMetricRegistry.LEVEL_POST, period="lifetime")

    page_sync = sync_meta_page_insights.run(
        page_pk=str(page.pk),
        mode="incremental",
        metrics=[page_metric],
    )
    assert page_sync["pages_processed"] == 1
    support = MetaMetricSupportStatus.all_objects.filter(
        tenant=user.tenant,
        page=page,
        level=MetaMetricRegistry.LEVEL_PAGE,
        metric_key=page_metric,
    ).first()
    assert page_sync["rows_processed"] > 0, (
        f"Live page sync returned zero rows for {page_metric}. "
        f"support={None if support is None else support.supported} "
        f"last_error={None if support is None else support.last_error}"
    )

    post_sync = sync_meta_post_insights.run(
        page_pk=str(page.pk),
        mode="incremental",
        metrics=[post_metric],
    )

    overview = api_client.get(
        reverse("meta-page-insights-overview", kwargs={"page_id": page.page_id}),
        {"date_preset": "last_90d"},
    )
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["page_id"] == page.page_id
    assert any(kpi["metric"] == page_metric for kpi in overview_payload.get("kpis", []))

    page_timeseries = api_client.get(
        reverse("meta-page-insights-timeseries", kwargs={"page_id": page.page_id}),
        {"date_preset": "last_90d", "metric": page_metric, "period": "day"},
    )
    assert page_timeseries.status_code == 200
    page_timeseries_payload = page_timeseries.json()
    assert page_timeseries_payload["metric"] == page_metric
    assert page_timeseries_payload["points"], (
        f"Expected points for {page_metric} after live sync; payload={page_timeseries_payload}"
    )

    posts = api_client.get(
        reverse("meta-page-insights-posts", kwargs={"page_id": page.page_id}),
        {"date_preset": "last_90d"},
    )
    assert posts.status_code == 200
    posts_payload = posts.json()
    if post_sync["rows_processed"] > 0:
        assert posts_payload["count"] > 0
        first_row = posts_payload["results"][0]
        assert post_metric in first_row["metrics"]
