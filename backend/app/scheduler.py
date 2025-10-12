from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from databases import Database
from sqlalchemy.ext.asyncio import create_async_engine

from .alerts import CAMPAIGN_PACING_RULES, AlertRule, evaluate_rule
from .config import get_settings
from .llm import generate_summary

logger = logging.getLogger(__name__)


async def dispatch_alert(rule: AlertRule, records: Iterable[dict]) -> None:
  settings = get_settings()
  payload = {
    "rule": rule.name,
    "records": list(records),
    "email_recipients": settings.alert_email_recipients,
    "slack_webhook": settings.alert_slack_webhook,
  }
  summary = await generate_summary(payload)
  logger.info("Alert triggered: %s", payload)
  logger.info("LLM summary: %s", summary)
  # In production we would send email/Slack here.
  # Placeholders log the payload for infrastructure teams to connect to ESP/webhooks.


async def run_alert_cycle() -> None:
  settings = get_settings()
  engine = create_async_engine(settings.database_url)
  try:
    for rule in CAMPAIGN_PACING_RULES:
      try:
        records = await evaluate_rule(engine, rule)
      except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to evaluate rule %s", rule.name)
        continue
      if records:
        await dispatch_alert(rule, records)
  finally:
    await engine.dispose()


async def schedule_jobs() -> AsyncIOScheduler:
  scheduler = AsyncIOScheduler()
  scheduler.add_job(run_alert_cycle, "interval", minutes=get_settings().refresh_interval_minutes)
  scheduler.start()
  return scheduler


def init_sync_database(url: str) -> Database:
  return Database(url)
