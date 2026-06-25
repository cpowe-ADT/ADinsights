"""Edge-sourced organic engagement ingestion (no ``read_insights``).

Page/Post *insights* (reach, impressions, clicks via ``/{object}/insights``)
require the ``read_insights`` permission, which ADinsights intentionally does not
request. Public engagement counts (reactions, comments, shares) and the page
follower count are exposed on the Graph object *edges* and resolve with only
``pages_read_engagement`` / ``pages_show_list`` — which the stored Page token
already holds.

This module fetches those real values from the edges and stores them as
aggregate insight points. It never adds ``read_insights``, never bumps the Graph
version, never invents values (a measured ``0`` is kept as real data; an
unreadable metric is simply skipped, not zero-filled), and runs only during
sync/backfill — never during report preview/export.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from integrations.models import MetaPage, MetaPost
from integrations.services.insights_parser import InsightPoint
from integrations.services.meta_graph_client import (
    MetaInsightsGraphClient,
    MetaInsightsGraphClientError,
)

# Source metric keys; these resolve to product metrics via the metric registry.
PAGE_FOLLOWERS_KEY = "page_follows"
POST_REACTIONS_KEY = "post_reactions_total"
POST_COMMENTS_KEY = "post_comments_total"
POST_SHARES_KEY = "post_shares_total"

_POST_ENGAGEMENT_FIELDS = (
    "shares,reactions.summary(true).limit(0),comments.summary(true).limit(0)"
)


def _summary_total(node: Any) -> int | None:
    if not isinstance(node, dict):
        return None
    summary = node.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("total_count"), int):
        return summary["total_count"]
    return None


def fetch_page_follower_count(
    *, client: MetaInsightsGraphClient, page_id: str, token: str
) -> int | None:
    """Follower count via the page object field (``pages_read_engagement``)."""
    payload = client.request(
        "GET", f"/{page_id}", params={"fields": "followers_count,fan_count"}, token=token
    )
    for key in ("followers_count", "fan_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def fetch_post_engagement(
    *, client: MetaInsightsGraphClient, post_id: str, token: str
) -> dict[str, int]:
    """Reactions/comments/shares via post-object edges (``pages_read_engagement``)."""
    payload = client.request(
        "GET", f"/{post_id}", params={"fields": _POST_ENGAGEMENT_FIELDS}, token=token
    )
    result: dict[str, int] = {}
    reactions = _summary_total(payload.get("reactions"))
    if reactions is not None:
        result[POST_REACTIONS_KEY] = reactions
    comments = _summary_total(payload.get("comments"))
    if comments is not None:
        result[POST_COMMENTS_KEY] = comments
    shares = payload.get("shares")
    if isinstance(shares, dict) and isinstance(shares.get("count"), int):
        result[POST_SHARES_KEY] = shares["count"]
    return result


def _point(metric_key: str, period: str, end_time: datetime, value: int) -> InsightPoint:
    return InsightPoint(
        metric_key=metric_key,
        period=period,
        end_time=end_time,
        value_num=Decimal(int(value)),
        value_json=None,
        breakdown_key=None,
        breakdown_json=None,
    )


def ingest_engagement_edges(
    *,
    page: MetaPage,
    tokens: list[str],
    since: date,
    until: date,
    client: MetaInsightsGraphClient | None = None,
) -> dict[str, int]:
    """Fetch + store real follower count and post engagement for the window.

    Returns row counts. Stores only values actually read from Meta; metrics it
    cannot read are skipped (never zero-filled).
    """
    # Deferred import avoids a circular import with integrations.tasks.
    from integrations.tasks import (
        _upsert_meta_insight_points,
        _upsert_meta_post_insight_points,
    )

    if not tokens:
        return {"page_rows": 0, "post_rows": 0, "posts_processed": 0}

    own = client is None
    active = client or MetaInsightsGraphClient.from_settings()
    page_rows = 0
    post_rows = 0
    posts_processed = 0
    period_end = datetime.combine(until, time(12, 0), tzinfo=timezone.utc)

    try:
        if own:
            active.__enter__()

        # Page follower count — point-in-time snapshot at the period end.
        followers: int | None = None
        for token in tokens:
            try:
                followers = fetch_page_follower_count(
                    client=active, page_id=page.page_id, token=token
                )
                break
            except MetaInsightsGraphClientError:
                continue
        if isinstance(followers, int):
            page_rows = _upsert_meta_insight_points(
                page=page,
                points=[_point(PAGE_FOLLOWERS_KEY, "day", period_end, followers)],
            )

        # Post engagement — reactions/comments/shares per stored post in window.
        posts = MetaPost.all_objects.filter(
            page=page,
            created_time__date__gte=since,
            created_time__date__lte=until,
        ).order_by("created_time")
        for post in posts:
            engagement: dict[str, int] = {}
            for token in tokens:
                try:
                    engagement = fetch_post_engagement(
                        client=active, post_id=post.post_id, token=token
                    )
                    break
                except MetaInsightsGraphClientError:
                    continue
            if not engagement:
                continue
            end_time = post.created_time or period_end
            points = [
                _point(key, "lifetime", end_time, value)
                for key, value in engagement.items()
            ]
            post_rows += _upsert_meta_post_insight_points(post=post, points=points)
            posts_processed += 1
    finally:
        if own:
            active.__exit__(None, None, None)

    return {
        "page_rows": page_rows,
        "post_rows": post_rows,
        "posts_processed": posts_processed,
    }
