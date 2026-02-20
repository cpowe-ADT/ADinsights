from __future__ import annotations

import random
import time
from datetime import date, timedelta
from typing import Any, Callable, Literal

from integrations.meta_page_insights.meta_client import (
    MetaPageInsightsApiError,
    MetaPageInsightsClient,
)

ObjectType = Literal["page", "post"]


def chunk_date_window(
    *,
    since: date,
    until: date,
    max_days: int = 90,
) -> list[tuple[date, date]]:
    if since > until:
        return []
    bounded_max_days = max(int(max_days), 1)
    chunks: list[tuple[date, date]] = []
    cursor = since
    while cursor <= until:
        chunk_until = min(cursor + timedelta(days=bounded_max_days - 1), until)
        chunks.append((cursor, chunk_until))
        cursor = chunk_until + timedelta(days=1)
    return chunks


def retry_with_backoff(
    fn: Callable[[], dict[str, Any]],
    *,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    bounded_attempts = max(max_attempts, 1)
    for attempt in range(1, bounded_attempts + 1):
        try:
            return fn()
        except MetaPageInsightsApiError as exc:
            if not exc.retryable or attempt >= bounded_attempts:
                raise
            delay = (2 ** (attempt - 1)) * base_delay_seconds + random.uniform(0, 1)
            sleeper(delay)
    raise RuntimeError("retry_with_backoff exhausted unexpectedly")


def fetch_timeseries(
    *,
    client: MetaPageInsightsClient,
    object_type: ObjectType,
    object_id: str,
    metric: str,
    period: str,
    since: date,
    until: date,
    token: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk_since, chunk_until in chunk_date_window(since=since, until=until, max_days=90):
        payload = retry_with_backoff(
            lambda: client.fetch_insights(
                object_type=object_type,
                object_id=object_id,
                metrics=[metric],
                period=period,
                since=chunk_since,
                until=chunk_until,
                token=token,
            ),
            max_attempts=5,
            base_delay_seconds=1.0,
        )
        rows.extend(_flatten_paged_rows(client=client, payload=payload, token=token))
    return rows


def _flatten_paged_rows(
    *,
    client: MetaPageInsightsClient,
    payload: dict[str, Any],
    token: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current = payload
    pages = 0
    while pages < 100:
        pages += 1
        data = current.get("data")
        if isinstance(data, list):
            rows.extend([row for row in data if isinstance(row, dict)])
        paging = current.get("paging")
        next_url = paging.get("next") if isinstance(paging, dict) else None
        if not isinstance(next_url, str) or not next_url.strip():
            break
        current = retry_with_backoff(
            lambda: client.request_url(url=next_url, token=token),
            max_attempts=5,
            base_delay_seconds=1.0,
        )
    return rows

