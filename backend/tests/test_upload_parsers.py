from __future__ import annotations

from io import BytesIO

from analytics.uploads import parse_budget_csv, parse_campaign_csv, parse_parish_csv


def _file(content: str) -> BytesIO:
    return BytesIO(content.encode("utf-8"))


def test_parse_campaign_csv_missing_required_columns():
    csv_text = "date,campaign_id,campaign_name,platform,spend,impressions,clicks\n"
    result = parse_campaign_csv(_file(csv_text))
    assert result.errors
    assert "Missing required column: conversions" in result.errors


def test_parse_campaign_csv_invalid_date():
    csv_text = "\n".join(
        [
            "date,campaign_id,campaign_name,platform,spend,impressions,clicks,conversions",
            "10/01/2024,cmp-1,Launch,Meta,120,12000,420,33",
        ]
    )
    result = parse_campaign_csv(_file(csv_text))
    assert result.errors
    assert "Row 2: date is invalid." in result.errors


def test_parse_campaign_csv_warns_on_missing_parish():
    csv_text = "\n".join(
        [
            "date,campaign_id,campaign_name,platform,spend,impressions,clicks,conversions",
            "2024-10-01,cmp-1,Launch,Meta,120,12000,420,33",
        ]
    )
    result = parse_campaign_csv(_file(csv_text))
    assert not result.errors
    assert result.warnings


def test_parse_parish_csv_missing_parish():
    csv_text = "\n".join(
        [
            "parish,spend,impressions,clicks,conversions",
            ",120,12000,420,33",
        ]
    )
    result = parse_parish_csv(_file(csv_text))
    assert "Row 2: parish is required." in result.errors


def test_parse_budget_csv_invalid_month():
    csv_text = "\n".join(
        [
            "month,campaign_name,planned_budget",
            "Oct-2024,Launch,1200",
        ]
    )
    result = parse_budget_csv(_file(csv_text))
    assert "Row 2: month is invalid." in result.errors
