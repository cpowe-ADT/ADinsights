from __future__ import annotations

from django.core.management import call_command

import pytest

from integrations.models import MetaMetricRegistry
from integrations.services.meta_metric_catalog import (
    load_metric_catalog,
    metric_catalog_doc_path,
    render_metric_catalog_markdown,
)


def test_meta_metric_catalog_contains_expected_metrics():
    catalog = load_metric_catalog()
    assert len(catalog) >= 150

    assert any(
        row["level"] == MetaMetricRegistry.LEVEL_PAGE
        and row["metric_key"] == "page_post_engagements"
        for row in catalog
    )
    assert any(
        row["level"] == MetaMetricRegistry.LEVEL_POST
        and row["metric_key"] == "post_reactions_like_total"
        for row in catalog
    )
    assert any(
        row["level"] == MetaMetricRegistry.LEVEL_POST
        and row["metric_key"] == "post_video_ad_break_ad_impressions"
        for row in catalog
    )
    assert any(
        row["level"] == MetaMetricRegistry.LEVEL_PAGE
        and row["metric_key"] == "page_video_views_10s"
        and row["status"] == MetaMetricRegistry.STATUS_DEPRECATED
        for row in catalog
    )


def test_meta_metric_catalog_doc_matches_renderer():
    catalog = load_metric_catalog()
    expected = render_metric_catalog_markdown(catalog)
    current = metric_catalog_doc_path().read_text()
    assert current == expected


@pytest.mark.django_db
def test_sync_meta_metric_catalog_command_upserts_registry():
    MetaMetricRegistry.objects.all().delete()
    call_command("sync_meta_metric_catalog")

    assert MetaMetricRegistry.objects.filter(level=MetaMetricRegistry.LEVEL_PAGE).exists()
    assert MetaMetricRegistry.objects.filter(level=MetaMetricRegistry.LEVEL_POST).exists()
    assert MetaMetricRegistry.objects.filter(metric_key="page_post_engagements", level=MetaMetricRegistry.LEVEL_PAGE).exists()
    assert MetaMetricRegistry.objects.filter(metric_key="post_video_views", level=MetaMetricRegistry.LEVEL_POST).exists()
