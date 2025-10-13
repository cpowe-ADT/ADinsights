"""Helper utilities for analytics export endpoints."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal


MetricRow = Sequence[str | int | float]


@dataclass(frozen=True)
class MetricsExportDataset:
    """Container describing the metrics export headers and rows."""

    headers: Sequence[str]
    rows: Sequence[MetricRow]


class FakeMetricsExportAdapter:
    """Return a deterministic set of rows for CSV exports."""

    _DATASET = MetricsExportDataset(
        headers=(
            "date",
            "impressions",
            "clicks",
            "spend",
            "conversions",
            "roas",
        ),
        rows=(
            (
                "2024-09-01",
                120_000,
                3_400,
                Decimal("540.00"),
                120,
                Decimal("3.5"),
            ),
            (
                "2024-09-02",
                98_500,
                2_750,
                Decimal("410.25"),
                85,
                Decimal("2.8"),
            ),
            (
                "2024-09-03",
                102_300,
                2_910,
                Decimal("430.75"),
                92,
                Decimal("3.1"),
            ),
        ),
    )

    def get_headers(self) -> Sequence[str]:
        return self._DATASET.headers

    def iter_rows(self) -> Iterable[MetricRow]:
        return iter(self._DATASET.rows)

