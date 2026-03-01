from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from integrations.services.insights_parser import normalize_breakdown_key, normalize_insights_payload


@pytest.mark.django_db
def test_parser_handles_numeric_values():
    payload = {
        "data": [
            {
                "name": "page_post_engagements",
                "period": "day",
                "values": [
                    {
                        "value": 42,
                        "end_time": "2026-02-18T08:00:00+0000",
                    }
                ],
                "title": "Engagement",
                "description": "Daily engagements",
            }
        ]
    }

    points, metadata = normalize_insights_payload(payload)
    assert len(points) == 1
    assert points[0].metric_key == "page_post_engagements"
    assert points[0].value_num == Decimal("42")
    assert points[0].value_json is None
    assert points[0].breakdown_key is None
    assert metadata[0].title == "Engagement"


@pytest.mark.django_db
def test_parser_handles_object_values_and_preserves_raw():
    payload = {
        "data": [
            {
                "name": "page_media_view",
                "period": "day",
                "values": [
                    {
                        "value": {"owned": 100, "crossposted": 20},
                        "end_time": "2026-02-18T08:00:00+0000",
                    }
                ],
            }
        ]
    }

    points, _ = normalize_insights_payload(payload)
    assert len(points) == 2
    by_key = {point.breakdown_key: point for point in points}
    assert by_key["owned"].value_num == Decimal("100")
    assert by_key["crossposted"].value_num == Decimal("20")
    assert by_key["owned"].value_json == {"owned": 100, "crossposted": 20}


@pytest.mark.django_db
def test_parser_handles_empty_payload():
    points, metadata = normalize_insights_payload({"data": []})
    assert points == []
    assert metadata == []


@pytest.mark.django_db
def test_parser_uses_fallback_end_time_for_lifetime_metrics():
    fallback = datetime(2026, 2, 18, 12, 0, tzinfo=dt_timezone.utc)
    payload = {
        "data": [
            {
                "name": "post_reactions_like_total",
                "period": "lifetime",
                "values": [{"value": 226}],
            }
        ]
    }

    points, _ = normalize_insights_payload(payload, fallback_end_time=fallback)
    assert len(points) == 1
    assert points[0].end_time == fallback
    assert points[0].value_num == Decimal("226")


@pytest.mark.django_db
def test_normalize_breakdown_key_default_value():
    assert normalize_breakdown_key(None) == "__none__"
    assert normalize_breakdown_key("") == "__none__"
    assert normalize_breakdown_key("owned") == "owned"
