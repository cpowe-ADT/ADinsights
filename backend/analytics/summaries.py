"""Daily summary helpers using aggregated metrics only."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from django.utils import timezone

from analytics.snapshots import SnapshotMetrics
from app.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an analytics assistant. You receive aggregated advertising metrics "
    "only (no user-level data). Write a concise daily summary (<=120 words) and "
    "include two clear next-step recommendations."
)


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_currency(summary: dict[str, Any], parish_metrics: list[dict[str, Any]]) -> str | None:
    currency = summary.get("currency")
    if isinstance(currency, str) and currency.strip():
        return currency.strip()
    for row in parish_metrics:
        candidate = row.get("currency")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def build_daily_summary_payload(metrics: SnapshotMetrics) -> dict[str, Any]:
    campaign_summary = metrics.campaign_metrics.get("summary") or {}
    parish_metrics = list(metrics.parish_metrics or [])

    payload = {
        "tenant_id": metrics.tenant_id,
        "generated_at": timezone.localtime(metrics.generated_at).isoformat(),
        "currency": _resolve_currency(campaign_summary, parish_metrics),
        "totals": {
            "spend": _coerce_number(campaign_summary.get("totalSpend")),
            "impressions": int(_coerce_number(campaign_summary.get("totalImpressions"))),
            "clicks": int(_coerce_number(campaign_summary.get("totalClicks"))),
            "conversions": int(_coerce_number(campaign_summary.get("totalConversions"))),
            "average_roas": _coerce_number(campaign_summary.get("averageRoas")),
        },
        "top_parishes": [],
    }

    sorted_parishes = sorted(
        parish_metrics,
        key=lambda row: _coerce_number(row.get("spend")),
        reverse=True,
    )
    payload["top_parishes"] = [
        {
            "parish": row.get("parish"),
            "spend": _coerce_number(row.get("spend")),
            "impressions": int(_coerce_number(row.get("impressions"))),
            "clicks": int(_coerce_number(row.get("clicks"))),
            "conversions": int(_coerce_number(row.get("conversions"))),
            "roas": _coerce_number(row.get("roas")),
            "campaign_count": int(_coerce_number(row.get("campaignCount"))),
        }
        for row in sorted_parishes[:3]
    ]
    return payload


def _fallback_summary(payload: dict[str, Any]) -> str:
    totals = payload.get("totals", {})
    currency = payload.get("currency") or "USD"
    top_parishes = payload.get("top_parishes", [])
    parish_labels = ", ".join(
        str(item.get("parish")) for item in top_parishes if item.get("parish")
    )
    if not parish_labels:
        parish_labels = "No parish breakouts yet."
    return (
        "Daily performance summary: "
        f"Spend {totals.get('spend', 0):.2f} {currency}, "
        f"Impressions {totals.get('impressions', 0)}, "
        f"Clicks {totals.get('clicks', 0)}, "
        f"Conversions {totals.get('conversions', 0)}, "
        f"Avg ROAS {totals.get('average_roas', 0):.2f}. "
        f"Top parishes: {parish_labels}."
    )


def _build_llm_request_payload(payload: dict[str, Any], client: LLMClient) -> dict[str, Any]:
    prompt_payload = json.dumps(payload, default=str, ensure_ascii=True)
    user_prompt = (
        "Summarize the daily aggregated metrics and recommend two next steps.\n"
        f"Metrics: {prompt_payload}"
    )
    return {
        "model": client.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 320,
        "temperature": 0.2,
    }


def summarize_daily_metrics(payload: dict[str, Any]) -> str:
    client = get_llm_client()
    if not client.is_enabled():
        logger.info("LLM client disabled; using fallback daily summary")
        return _fallback_summary(payload)

    request_body = _build_llm_request_payload(payload, client)
    headers = {"Authorization": f"Bearer {client.api_key}"}

    try:
        response = httpx.post(
            client.base_url,
            json=request_body,
            headers=headers,
            timeout=client.timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failures
        logger.warning("Daily summary LLM request failed: %s", exc)
        return _fallback_summary(payload)

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - defensive
        logger.error("Daily summary LLM response invalid JSON: %s", exc)
        return _fallback_summary(payload)

    summary = LLMClient._extract_summary(data)
    if not summary:
        return _fallback_summary(payload)
    return summary.strip()


__all__ = ["build_daily_summary_payload", "summarize_daily_metrics"]
