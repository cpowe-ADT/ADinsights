from __future__ import annotations

import pytest

from integrations.meta_page_insights.insights_fetcher import retry_with_backoff
from integrations.meta_page_insights.meta_client import MetaPageInsightsApiError


def test_retry_with_backoff_retries_80001_until_success(monkeypatch):
    attempts = {"count": 0}
    sleeps: list[float] = []

    monkeypatch.setattr("integrations.meta_page_insights.insights_fetcher.random.uniform", lambda _a, _b: 0.0)

    def action():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise MetaPageInsightsApiError("rate limited", error_code=80001, retryable=True)
        return {"data": []}

    result = retry_with_backoff(
        action,
        max_attempts=5,
        base_delay_seconds=1.0,
        sleeper=lambda delay: sleeps.append(delay),
    )

    assert result == {"data": []}
    assert attempts["count"] == 3
    assert sleeps == [1.0, 2.0]


def test_retry_with_backoff_stops_after_max_attempts(monkeypatch):
    monkeypatch.setattr("integrations.meta_page_insights.insights_fetcher.random.uniform", lambda _a, _b: 0.0)

    def action():
        raise MetaPageInsightsApiError("rate limited", error_code=80001, retryable=True)

    with pytest.raises(MetaPageInsightsApiError):
        retry_with_backoff(
            action,
            max_attempts=3,
            base_delay_seconds=1.0,
            sleeper=lambda _delay: None,
        )
