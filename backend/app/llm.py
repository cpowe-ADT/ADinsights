from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


async def generate_summary(insight_payload: dict[str, Any]) -> str:
  settings = get_settings()
  headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
  body = {
    "model": "gpt-5-codex",
    "messages": [
      {
        "role": "system",
        "content": "You are an analytics assistant that summarises campaign pacing issues."
      },
      {
        "role": "user",
        "content": (
          "Create a concise summary (max 120 words) of the anomalies below and "
          "recommend next steps for marketing operations.\n" + str(insight_payload)
        )
      }
    ]
  }

  async with httpx.AsyncClient(timeout=15.0) as client:
    response = await client.post(settings.llm_api_url, json=body, headers=headers)
    response.raise_for_status()
    data = response.json()

  try:
    return data["choices"][0]["message"]["content"].strip()
  except (KeyError, IndexError) as exc:  # pragma: no cover
    logger.exception("Unexpected response from LLM: %s", data)
    raise RuntimeError("LLM response malformed") from exc
