"""Meta Page Insights service package.

Avoid eager submodule imports here to prevent circular imports during Django startup.
"""

__all__ = [
    "chunk_date_window",
    "fetch_timeseries",
    "load_metric_pack_v1",
    "sync_pages_for_connection",
    "validate_metrics",
]


def __getattr__(name: str):
    if name in {"chunk_date_window", "fetch_timeseries"}:
        from .insights_fetcher import chunk_date_window, fetch_timeseries

        mapping = {
            "chunk_date_window": chunk_date_window,
            "fetch_timeseries": fetch_timeseries,
        }
        return mapping[name]
    if name == "load_metric_pack_v1":
        from .metric_pack_loader import load_metric_pack_v1

        return load_metric_pack_v1
    if name == "sync_pages_for_connection":
        from .token_service import sync_pages_for_connection

        return sync_pages_for_connection
    if name == "validate_metrics":
        from .insights_discovery import validate_metrics

        return validate_metrics
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
