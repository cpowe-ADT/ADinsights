from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(slots=True)
class AlertRule:
  name: str
  description: str
  sql: str
  threshold: float
  direction: str  # "above" or "below"
  channels: list[str]


CAMPAIGN_PACING_RULES: list[AlertRule] = [
  AlertRule(
    name="Campaign Budget Underdelivery",
    description="Alert when spend is below 80% of the linear pacing goal",
    sql="""
      SELECT campaign_id,
             SUM(spend) AS total_spend,
             SUM(budget) AS total_budget,
             CASE WHEN SUM(budget) = 0 THEN 0 ELSE SUM(spend) / SUM(budget) END AS pacing
      FROM mart_campaign_daily
      WHERE date >= CURRENT_DATE - INTERVAL '7 days'
      GROUP BY campaign_id
    """,
    threshold=0.8,
    direction="below",
    channels=["email", "slack"],
  ),
  AlertRule(
    name="Creative Overspend",
    description="Alert when a single creative exceeds 110% of its allocated budget",
    sql="""
      SELECT creative_id,
             SUM(spend) AS total_spend,
             SUM(budget) AS total_budget,
             CASE WHEN SUM(budget) = 0 THEN 0 ELSE SUM(spend) / SUM(budget) END AS pacing
      FROM mart_creative_daily
      WHERE date >= CURRENT_DATE - INTERVAL '7 days'
      GROUP BY creative_id
    """,
    threshold=1.1,
    direction="above",
    channels=["email"],
  ),
]


async def evaluate_rule(engine: AsyncEngine, rule: AlertRule) -> list[dict[str, Any]]:
  async with engine.connect() as conn:
    result = await conn.execute(text(rule.sql))
    rows = result.mappings().all()

  triggered: list[dict[str, Any]] = []
  for row in rows:
    pacing = float(row.get("pacing", 0))
    if rule.direction == "above" and pacing > rule.threshold:
      triggered.append(dict(row))
    elif rule.direction == "below" and pacing < rule.threshold:
      triggered.append(dict(row))
  return triggered
