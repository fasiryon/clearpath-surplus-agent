"""
Scrape agent: pulls 'scrape' tasks, uses CourtAdapterFactory to fetch
CAEF case summaries + detail pages, then seeds docket_analysis tasks.

Does NOT detect surplus — that is the docket_agent's responsibility.
This agent's job is to find cases and hand off raw docket text.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from src.adapters import CourtAdapterFactory
from src.agents.base_agent import BaseAgent
from src import queue as q

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


class ScrapeAgent(BaseAgent):
    task_type = "scrape"

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Scrape a county for new CAEF cases and seed docket_analysis tasks.

        Args:
            task: agent_tasks row; payload contains state, county, county_code, lookback_days.

        Returns:
            {'cases_queued': int, 'tasks_seeded': int}
        """
        payload = task.get("payload", {})
        state = payload.get("state", "MD")
        county = payload.get("county", "")
        lookback = int(payload.get("lookback_days", os.getenv("SCRAPE_LOOKBACK_DAYS", "3")))

        logger.info(f"ScrapeAgent: {state}/{county} (lookback={lookback}d)")

        adapter = CourtAdapterFactory.get(state, county)
        cases = await adapter.search_cases(lookback_days=lookback)
        logger.info(f"Found {len(cases)} case summaries in {county}")

        cases_queued = 0
        tasks_seeded = 0

        for case in cases:
            # Fetch full docket — adapter returns None if fetch fails
            detail = await adapter.get_case_detail(case)
            if not detail:
                continue

            # Upsert skeleton case record (status='new', no surplus_amount yet)
            await _upsert_case_skeleton(detail)

            # Seed docket_analysis task — docket_agent decides if there's surplus
            task_key = f"docket_analysis:{detail.case_number}"
            seeded = await q.seed_task(
                task_type="docket_analysis",
                payload={
                    "case_number": detail.case_number,
                    "docket_text": detail.raw_docket_text or "",
                    "county": county,
                    "state": state,
                },
                state=state,
                county=county,
                priority=5,
                task_key=task_key,
            )
            cases_queued += 1
            if seeded:
                tasks_seeded += 1

        logger.info(
            f"ScrapeAgent done: {cases_queued} cases processed, "
            f"{tasks_seeded} new docket tasks seeded"
        )
        return {"cases_queued": cases_queued, "tasks_seeded": tasks_seeded}


async def _upsert_case_skeleton(case: Any) -> None:
    """Insert a bare-bones case row so docket_agent can update it later."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    payload = {
        "case_number": case.case_number,
        "county": case.county,
        "property_address": case.property_address,
        "defendant_name": case.defendant_name,
        "plaintiff_name": case.plaintiff_name,
        "filing_date": case.filing_date,
        "sale_date": case.sale_date,
        "scrape_source": case.scrape_source,
        "raw_docket": case.raw_docket,
        "status": "new",
        # surplus_amount intentionally omitted — set by docket_agent
    }

    try:
        db.table("surplus_cases").upsert(payload, on_conflict="case_number").execute()
    except Exception as e:
        logger.error(f"Failed to upsert case skeleton {case.case_number}: {e}")


if __name__ == "__main__":
    asyncio.run(ScrapeAgent().run())
