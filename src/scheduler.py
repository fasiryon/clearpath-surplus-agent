"""
Daily orchestration script for ClearPath Surplus agent.

Runs three sequential stages:
  Stage 1: Scrape MJCS for new CAEF surplus cases
  Stage 2: Skip-trace owners for cases above minimum surplus threshold
  Stage 3: Trigger Zapier outreach webhooks for pending contacts

Designed for 6:00 AM ET daily execution via GitHub Actions.

GitHub Actions workflow YAML (for reference — actual file at .github/workflows/daily.yml):
---
name: ClearPath Daily Agent

on:
  schedule:
    - cron: '0 10 * * *'   # 10:00 UTC = 6:00 AM ET
  workflow_dispatch:        # Manual trigger from GitHub Actions UI

jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium --with-deps
      - name: Run scheduler
        run: python src/scheduler.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          BATCH_SKIP_TRACE_API_KEY: ${{ secrets.BATCH_SKIP_TRACE_API_KEY }}
          ZAPIER_OUTREACH_WEBHOOK: ${{ secrets.ZAPIER_OUTREACH_WEBHOOK }}
          HUBSPOT_API_KEY: ${{ secrets.HUBSPOT_API_KEY }}
          ACTIVE_COUNTY: ${{ vars.ACTIVE_COUNTY }}
---
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Configure loguru output
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/clearpath.log")

os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
logger.add(LOG_FILE, level="DEBUG", rotation="7 days", retention="30 days")


async def run_pipeline() -> dict[str, int]:
    """
    Execute the full three-stage daily pipeline.

    Returns:
        Dict with counts: { "cases_found", "contacts_traced", "outreach_triggered" }
    """
    # Lazy imports to ensure logging is configured first
    from outreach import run_outreach
    from scraper import run_scraper
    from skip_trace import run_skip_tracer

    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"ClearPath Surplus Agent — Daily Run @ {start.isoformat()}")
    logger.info("=" * 60)

    county = os.getenv("ACTIVE_COUNTY", "Baltimore County")
    lookback = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "3"))

    results = {
        "cases_found": 0,
        "contacts_traced": 0,
        "outreach_triggered": 0,
    }

    # -------------------------------------------------------
    # STAGE 1: Scrape
    # -------------------------------------------------------
    logger.info(f"[Stage 1] Scraping {county} (lookback={lookback} days)...")
    try:
        surplus_cases = await run_scraper(county, lookback)
        results["cases_found"] = len(surplus_cases)
        logger.info(f"[Stage 1] Complete — {results['cases_found']} surplus cases found")
    except Exception as e:
        logger.error(f"[Stage 1] FAILED: {e}")

    # -------------------------------------------------------
    # STAGE 2: Skip trace
    # -------------------------------------------------------
    logger.info("[Stage 2] Running skip tracer...")
    try:
        results["contacts_traced"] = await run_skip_tracer()
        logger.info(f"[Stage 2] Complete — {results['contacts_traced']} contacts traced")
    except Exception as e:
        logger.error(f"[Stage 2] FAILED: {e}")

    # -------------------------------------------------------
    # STAGE 3: Outreach
    # -------------------------------------------------------
    logger.info("[Stage 3] Triggering outreach...")
    try:
        results["outreach_triggered"] = await run_outreach()
        logger.info(f"[Stage 3] Complete — {results['outreach_triggered']} outreaches triggered")
    except Exception as e:
        logger.error(f"[Stage 3] FAILED: {e}")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info(
        f"Summary: cases={results['cases_found']} | "
        f"traced={results['contacts_traced']} | "
        f"outreach={results['outreach_triggered']}"
    )
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    asyncio.run(run_pipeline())
