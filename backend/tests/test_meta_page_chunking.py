from __future__ import annotations

from datetime import date, timedelta

import pytest

from integrations.meta_page_insights.insights_fetcher import chunk_date_window, fetch_timeseries


def test_chunk_date_window_covers_range_without_gaps_or_overlaps():
    since = date(2025, 1, 1)
    until = date(2025, 7, 20)

    chunks = chunk_date_window(since=since, until=until, max_days=90)
    assert chunks[0][0] == since
    assert chunks[-1][1] == until

    previous_end = None
    for start, end in chunks:
        assert start <= end
        if previous_end is not None:
            assert start == previous_end
        previous_end = end + timedelta(days=1)


@pytest.mark.django_db
def test_fetch_timeseries_merges_paged_payloads():
    class DummyClient:
        def __init__(self):
            self.calls = 0

        def fetch_insights(self, **kwargs):  # noqa: ANN003
            self.calls += 1
            return {
                "data": [{"name": kwargs["metrics"][0], "period": kwargs["period"]}],
                "paging": {"next": "https://graph.facebook.com/v24.0/next-page"},
            }

        def request_url(self, *, url: str, token: str):
            return {"data": [{"name": "page_post_engagements", "period": "day"}]}

    client = DummyClient()
    rows = fetch_timeseries(
        client=client,
        object_type="page",
        object_id="page-1",
        metric="page_post_engagements",
        period="day",
        since=date(2026, 1, 1),
        until=date(2026, 1, 2),
        token="token",
    )
    assert len(rows) == 2
    assert client.calls == 1
