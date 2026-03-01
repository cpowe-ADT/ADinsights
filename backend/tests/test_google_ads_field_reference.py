from __future__ import annotations

import json

from integrations.google_ads.field_reference import (
    ingest_fields_reference_file,
    parse_fields_reference_text,
)


def test_parse_fields_reference_text_extracts_segments_and_metrics():
    raw = """
segments.date
Field description Date to which metrics apply.
Category SEGMENT
Data Type DATE
Type URL N/A
Filterable True
Selectable True
Sortable True
Repeated False

metrics.clicks
Field description The number of clicks.
Category METRIC
Data Type INT64
Type URL N/A
Filterable True
Selectable True
Sortable True
Repeated False
Selectable with
The following fields/resources can be selected with this field:
campaign
customer
segments.date
"""
    payload = parse_fields_reference_text(raw, version="v23")
    assert payload["version"] == "v23"
    assert payload["counts"]["segments"] == 1
    assert payload["counts"]["metrics"] == 1

    segment = payload["fields"]["segments"][0]
    assert segment["name"] == "segments.date"
    assert segment["data_type"] == "DATE"
    assert segment["filterable"] is True
    assert segment["repeated"] is False

    metric = payload["fields"]["metrics"][0]
    assert metric["name"] == "metrics.clicks"
    assert metric["selectable_with"] == ["campaign", "customer", "segments.date"]


def test_ingest_fields_reference_file_writes_json(tmp_path):
    source = tmp_path / "fields_raw.txt"
    target = tmp_path / "fields_reference.json"
    source.write_text(
        "metrics.impressions\nField description Count of impressions.\nCategory METRIC\n",
        encoding="utf-8",
    )
    payload = ingest_fields_reference_file(
        input_path=source,
        output_path=target,
        version="v23",
    )
    written = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total_fields"] == 1
    assert written["fields"]["metrics"][0]["name"] == "metrics.impressions"


def test_parse_fields_reference_handles_new_field_after_selectable_with_block():
    raw = """
metrics.cost_micros
Field description Cost in micros.
Category METRIC
Selectable True
Selectable with
The following fields/resources can be selected with this field:
campaign
segments.date

metrics.clicks
Field description Click count.
Category METRIC
Selectable True
"""
    payload = parse_fields_reference_text(raw, version="v23")
    assert payload["counts"]["metrics"] == 2
    metric_names = [row["name"] for row in payload["fields"]["metrics"]]
    assert metric_names == ["metrics.clicks", "metrics.cost_micros"]
