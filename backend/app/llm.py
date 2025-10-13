"""Utilities for summarising alert payloads with an LLM provider."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import httpx
from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from app.alerts import AlertRule

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
MAX_ROWS = 10
MAX_SUMMARY_LENGTH = 800
SYSTEM_PROMPT = (
    "You are an analytics assistant. Given raw alert rows from an ad performance "
    "warehouse, produce a concise (<=120 words) summary with suggested next "
    "actions. Highlight impacted campaigns, accounts, and metrics."
)


class LLMError(RuntimeError):
    """Raised when the LLM provider rejects a request."""


@dataclass
class LLMClient:
    base_url: str | None
    api_key: str | None
    model: str | None
    timeout: float = DEFAULT_TIMEOUT

    def is_enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def summarize(self, rule: "AlertRule", rows: Iterable[dict[str, Any]]) -> str:
        rows = list(rows)
        if not rows:
            return "No results matched this alert; nothing to summarise."

        if not self.is_enabled():
            logger.info("LLM client disabled; returning fallback summary for %s", rule.slug)
            return self.fallback_summary(rows)

        payload_rows = rows[:MAX_ROWS]
        prompt_payload = json.dumps(payload_rows, default=str, ensure_ascii=False)
        user_prompt = (
            f"Alert: {rule.name} (severity={rule.severity}).\n"
            f"Description: {rule.description}\n"
            "Summarise the anomalies described by these JSON rows and recommend "
            "two tactical remediation steps.\n"
            f"Rows: {prompt_payload}"
        )

        headers = {"Authorization": f"Bearer {self.api_key}"}
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 320,
            "temperature": 0.2,
        }

        try:
            response = httpx.post(
                self.base_url,
                json=request_body,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failures
            logger.warning("LLM request failed for %s: %s", rule.slug, exc)
            raise LLMError("LLM request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            logger.error("LLM provider returned invalid JSON: %s", exc)
            raise LLMError("Invalid LLM response") from exc

        summary = self._extract_summary(data)
        if not summary:
            raise LLMError("LLM response missing summary")

        summary = summary.strip()
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[: MAX_SUMMARY_LENGTH - 3].rstrip() + "..."
        return summary

    def fallback_summary(self, rows: Iterable[dict[str, Any]]) -> str:
        first = next(iter(rows))
        keys = ", ".join(sorted(first.keys())) if isinstance(first, dict) else "results"
        return (
            "Automated summary unavailable. Review the alert rows directly; "
            f"columns captured: {keys}."
        )

    @staticmethod
    def _extract_summary(payload: dict[str, Any]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        return None


def get_llm_client() -> LLMClient:
    return LLMClient(
        base_url=getattr(settings, "LLM_API_URL", None),
        api_key=getattr(settings, "LLM_API_KEY", None),
        model=getattr(settings, "LLM_MODEL", None),
        timeout=float(getattr(settings, "LLM_TIMEOUT", DEFAULT_TIMEOUT)),
    )


__all__ = ["LLMClient", "LLMError", "get_llm_client"]
