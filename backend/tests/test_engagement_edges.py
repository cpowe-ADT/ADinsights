from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

import pytest

from integrations.meta_page_insights.engagement_edges import (
    PAGE_FOLLOWERS_KEY,
    POST_COMMENTS_KEY,
    POST_REACTIONS_KEY,
    POST_SHARES_KEY,
    ingest_engagement_edges,
)
from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
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


def _create_post(user, page) -> MetaPost:
    post = MetaPost(
        tenant=user.tenant,
        page=page,
        post_id="post-1",
        created_time=datetime(2026, 5, 6, 12, 0, tzinfo=dt_timezone.utc),
    )
    post.save()
    return post


class DummyClient:
    def __init__(self, responses):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def request(self, method, path, *, params, token):  # noqa: ANN001
        return self._responses.get(path, {})


def _patch_client(monkeypatch, responses):
    monkeypatch.setattr(
        "integrations.meta_page_insights.engagement_edges.MetaInsightsGraphClient.from_settings",
        lambda: DummyClient(responses),
    )


@pytest.mark.django_db
def test_ingest_engagement_edges_stores_real_values(monkeypatch, user):
    page = _create_page(user)
    post = _create_post(user, page)
    _patch_client(
        monkeypatch,
        {
            "/page-1": {"followers_count": 6023, "fan_count": 6023},
            "/post-1": {
                "reactions": {"summary": {"total_count": 2}},
                "comments": {"summary": {"total_count": 0}},
                "shares": {"count": 1},
            },
        },
    )

    result = ingest_engagement_edges(
        page=page, tokens=["page-token"], since=date(2026, 5, 1), until=date(2026, 5, 31)
    )

    assert result == {"page_rows": 1, "post_rows": 3, "posts_processed": 1}
    assert int(
        MetaInsightPoint.all_objects.get(page=page, metric_key=PAGE_FOLLOWERS_KEY).value_num
    ) == 6023
    assert int(
        MetaPostInsightPoint.all_objects.get(post=post, metric_key=POST_REACTIONS_KEY).value_num
    ) == 2
    # A measured 0 is real data and is kept (not treated as missing).
    assert int(
        MetaPostInsightPoint.all_objects.get(post=post, metric_key=POST_COMMENTS_KEY).value_num
    ) == 0
    assert int(
        MetaPostInsightPoint.all_objects.get(post=post, metric_key=POST_SHARES_KEY).value_num
    ) == 1


@pytest.mark.django_db
def test_ingest_engagement_edges_never_fakes_unreadable_metrics(monkeypatch, user):
    page = _create_page(user)
    post = _create_post(user, page)
    # Page exposes no follower fields; post exposes no engagement edges.
    _patch_client(monkeypatch, {"/page-1": {}, "/post-1": {}})

    result = ingest_engagement_edges(
        page=page, tokens=["page-token"], since=date(2026, 5, 1), until=date(2026, 5, 31)
    )

    assert result == {"page_rows": 0, "post_rows": 0, "posts_processed": 0}
    assert not MetaInsightPoint.all_objects.filter(page=page).exists()
    assert not MetaPostInsightPoint.all_objects.filter(post=post).exists()


@pytest.mark.django_db
def test_ingest_engagement_edges_no_tokens_is_noop(monkeypatch, user):
    page = _create_page(user)
    result = ingest_engagement_edges(
        page=page, tokens=[], since=date(2026, 5, 1), until=date(2026, 5, 31)
    )
    assert result == {"page_rows": 0, "post_rows": 0, "posts_processed": 0}
