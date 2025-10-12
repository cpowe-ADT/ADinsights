from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .alerts import CAMPAIGN_PACING_RULES
from .config import Settings, get_settings
from .llm import generate_summary
from .scheduler import run_alert_cycle, schedule_jobs

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ADinsights Platform API")


async def get_engine(settings: Settings = Depends(get_settings)) -> AsyncEngine:
  return create_async_engine(settings.database_url)


@app.on_event("startup")
async def startup_event() -> None:
  settings = get_settings()
  app.state.scheduler = await schedule_jobs()
  logger.info("Scheduler started (interval=%s minutes)", settings.refresh_interval_minutes)


@app.on_event("shutdown")
async def shutdown_event() -> None:
  scheduler = getattr(app.state, "scheduler", None)
  if scheduler:
    await scheduler.shutdown()


@app.get("/health")
async def health() -> dict[str, str]:
  return {"status": "ok"}


@app.get("/dashboards/campaign")
async def campaign_dashboard() -> dict:
  return {
    "meta": {"title": "Campaign & Creative Pacing"},
    "widgets": [
      {"type": "metric", "label": "Active Campaigns", "value": 12},
      {"type": "metric", "label": "Budget Utilization", "value": 0.82},
    ],
  }


@app.get("/alerts/rules")
async def alert_rules() -> dict:
  return {
    "rules": [
      {
        "name": rule.name,
        "description": rule.description,
        "threshold": rule.threshold,
        "direction": rule.direction,
        "channels": rule.channels,
      }
      for rule in CAMPAIGN_PACING_RULES
    ]
  }


@app.post("/insights/summary")
async def ai_summary(payload: dict) -> dict:
  summary = await generate_summary(payload)
  return {"summary": summary}


@app.post("/alerts/run")
async def run_alerts() -> dict[str, str]:
  await run_alert_cycle()
  return {"status": "triggered"}
from fastapi import FastAPI

from .api import oauth, rbac
from .config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.include_router(rbac.router)
app.include_router(oauth.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
