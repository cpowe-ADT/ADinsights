from __future__ import annotations

import asyncio
import logging

from .scheduler import schedule_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
  await schedule_jobs()
  logger.info("Scheduler loop running")
  while True:  # pragma: no cover - long running process
    await asyncio.sleep(60)


if __name__ == "__main__":
  asyncio.run(main())
