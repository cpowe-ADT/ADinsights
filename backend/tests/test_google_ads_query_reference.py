from __future__ import annotations

import json

from integrations.google_ads.query_reference import (
    ingest_query_reference_file,
    parse_query_reference_text,
)


def test_parse_query_reference_text_extracts_overview_and_resources():
    raw = """
Overview
These pages serve as reference for resources that can be queried.

List of all resources
Resource types
campaign\tA campaign.
ad_group  An ad group.
Continuation sentence for ad_group.
"""
    payload = parse_query_reference_text(raw, version="v23")
    assert payload["version"] == "v23"
    assert payload["resource_count"] == 2
    assert "can be queried" in payload["overview"]
    ad_group = next(row for row in payload["resource_types"] if row["name"] == "ad_group")
    assert ad_group["description"] == "An ad group. Continuation sentence for ad_group."
    assert payload["field_attributes"]["filterable"].startswith("Whether the field can be used")


def test_ingest_query_reference_file_writes_json(tmp_path):
    input_path = tmp_path / "query_reference_raw.txt"
    output_path = tmp_path / "query_reference.json"
    input_path.write_text(
        "Overview\nRef text.\nList of all resources\nResource types\ncampaign A campaign.\n",
        encoding="utf-8",
    )

    payload = ingest_query_reference_file(
        input_path=input_path,
        output_path=output_path,
        version="v23",
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["resource_count"] == 1
    assert written["resource_types"][0]["name"] == "campaign"
