"""
v2 Scheduler — thin task seeder only.

Seeds one 'scrape' task per active county, then exits.
The agents (scrape_agent, docket_agent, skip_trace_agent, outreach_agent)
run as separate jobs in GitHub Actions and drain their own queues.

v1 behavior (run all stages in one process) is preserved in
src/scheduler_v1_compat.py for reference and local testing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

os.makedirs("logs", exist_ok=True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
logger.add("logs/scheduler.log", level="DEBUG", rotation="7 days", retention="30 days")


def _load_active_counties() -> list[dict]:
    """Read states.json and return all active county dicts with their state code injected."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "states.json")
    active: list[dict] = []
    try:
        with open(config_path) as f:
            data = json.load(f)
        for state_block in data["states"]:
            if not state_block.get("active", False):
                continue
            state_code = state_block["state"]
            for county in state_block.get("counties", []):
                if county.get("active", False):
                    active.append({**county, "state": state_code})
    except Exception as e:
        logger.error(f"Failed to load states.json: {e}")
    return active


async def seed_pipeline() -> int:
    """
    Seed scrape tasks for all active counties and report how many were inserted.

    Returns:
        Number of scrape tasks inserted into agent_tasks.
    """
    from src import queue as q

    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"ClearPath Scheduler v2 — {start.isoformat()}")
    logger.info("=" * 60)

    active_counties = _load_active_counties()
    if not active_counties:
        logger.error("No active counties found in states.json — nothing to seed")
        return 0

    logger.info(
        f"Seeding scrape tasks for: "
        + ", ".join(f"{c['state']}/{c['name']}" for c in active_counties)
    )

    seeded = await q.seed_scrape_tasks(active_counties)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"Scheduler done in {elapsed:.1f}s — {seeded} tasks seeded")
    return seeded


if __name__ == "__main__":
    asyncio.run(seed_pipeline())
