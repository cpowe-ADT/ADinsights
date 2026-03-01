from __future__ import annotations

import json
from datetime import date

import pytest

from integrations.google_ads.catalog import ingest_reference_file, parse_reference_text
from integrations.google_ads.gaql_templates import render_gaql_template


def test_parse_reference_text_maps_sections_and_multiline_descriptions():
    raw = """
Google Ads API v23 - Reference

Overview

services
GoogleAdsService\tService to fetch data and metrics across resources.
CampaignService  Service to manage campaigns.
Mutates campaign entities.

common
Money\tRepresents a price in a particular currency.
Additional detail for Money.

resources
Campaign\tA campaign.
"""

    catalog = parse_reference_text(raw, version="v23")

    assert catalog["version"] == "v23"
    assert catalog["counts"]["services"] == 2
    assert catalog["counts"]["common"] == 1
    assert catalog["counts"]["resources"] == 1
    assert catalog["total_entries"] == 4

    services = catalog["sections"]["services"]
    campaign_row = next(row for row in services if row["name"] == "CampaignService")
    assert campaign_row["description"] == "Service to manage campaigns. Mutates campaign entities."

    money_row = catalog["sections"]["common"][0]
    assert money_row["name"] == "Money"
    assert money_row["description"] == (
        "Represents a price in a particular currency. Additional detail for Money."
    )


def test_parse_reference_text_dedupes_duplicate_entries():
    raw = """
services
GoogleAdsService\tService to fetch data.
GoogleAdsService\tService to fetch data.
"""

    catalog = parse_reference_text(raw)
    assert catalog["counts"]["services"] == 1
    assert catalog["sections"]["services"][0]["name"] == "GoogleAdsService"


def test_ingest_reference_file_writes_normalized_catalog(tmp_path):
    input_path = tmp_path / "google_ads_raw.txt"
    output_path = tmp_path / "google_ads_catalog.json"
    input_path.write_text(
        "services\nCustomerService\tService to manage customers.\n",
        encoding="utf-8",
    )

    catalog = ingest_reference_file(
        input_path=input_path,
        output_path=output_path,
        version="v23",
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert catalog["counts"]["services"] == 1
    assert written["sections"]["services"][0]["name"] == "CustomerService"
    assert written["version"] == "v23"


def test_render_gaql_template_includes_date_range():
    query = render_gaql_template(
        "campaign_daily_performance",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 7),
    )
    assert "2026-02-01" in query
    assert "2026-02-07" in query
    assert "FROM campaign" in query


def test_render_gaql_template_rejects_inverted_dates():
    with pytest.raises(ValueError):
        render_gaql_template(
            "campaign_daily_performance",
            start_date=date(2026, 2, 8),
            end_date=date(2026, 2, 1),
        )
