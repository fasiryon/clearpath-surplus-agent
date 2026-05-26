"""
Abstract base class for all ClearPath Surplus agents.

Every agent: claims one task → processes it → marks done/failed → loops.
Exits cleanly when its task queue is empty. Sentry captures all exceptions.
"""

from __future__ import annotations

import asyncio
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sentry_sdk
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from src import queue as q

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


class BaseAgent(ABC):
    """
    Abstract agent that drains one task_type queue until empty.

    Subclasses implement process() which receives the claimed task dict
    and must return a result dict that is stored as result_payload.
    """

    task_type: str  # set by each subclass as a class variable

    def __init__(self) -> None:
        self.worker_id = str(uuid4())
        self.agent_name = self.__class__.__name__

        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN", ""),
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production"),
        )

        # Per-agent log file; stderr always on
        os.makedirs("logs", exist_ok=True)
        log_level = os.getenv("LOG_LEVEL", "INFO")
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="{time:HH:mm:ss} | {level} | {name} | {message}")
        logger.add(
            f"logs/{self.task_type}.log",
            level="DEBUG",
            rotation="1 day",
            retention="14 days",
        )
        logger.info(f"{self.agent_name} started — worker_id={self.worker_id[:8]}")

    async def run(self) -> None:
        """
        Main loop: claim → process → complete/fail → sleep → repeat.
        Exits when no tasks remain.
        """
        processed = 0

        while True:
            task = await q.claim_task(self.task_type, self.worker_id)

            if task is None:
                logger.info(
                    f"{self.agent_name} queue empty after {processed} tasks — exiting"
                )
                break

            task_id = task["id"]
            started = datetime.now(timezone.utc)

            try:
                result = await self.process(task)
                await q.complete_task(task_id, result)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                logger.info(
                    f"{self.agent_name} task done in {elapsed:.1f}s | "
                    f"id={task_id[:8]} | result={result}"
                )
                await self.log_run(task_id, "done", result)

            except Exception as e:
                sentry_sdk.capture_exception(e)
                error_msg = f"{type(e).__name__}: {e}"
                logger.error(f"{self.agent_name} task failed | id={task_id[:8]} | {error_msg}")
                await q.fail_task(task_id, error_msg)
                await self.log_run(task_id, "failed", {"error": error_msg})

            processed += 1
            await asyncio.sleep(2)

    @abstractmethod
    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single claimed task. Must be implemented by each subclass.

        Args:
            task: The full agent_tasks row as a dict (includes payload, state, county, etc.).

        Returns:
            Result dict stored in agent_tasks.result_payload and agent_runs.
        """
        ...

    async def log_run(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any],
    ) -> None:
        """
        Write one row to agent_runs for cost/performance tracking.

        Args:
            task_id: The agent_tasks.id that was processed.
            status: 'done' or 'failed'.
            result: The result dict from process().
        """
        row = {
            "agent_type": self.task_type,
            "worker_id": self.worker_id,
            "task_id": task_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "cases_found": result.get("cases_queued", result.get("cases_found", 0)),
            "tasks_seeded": result.get("tasks_seeded", 0),
            "tokens_used": result.get("tokens_used", 0),
            "error_count": 1 if status == "failed" else 0,
            "status": status,
        }
        try:
            db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            db.table("agent_runs").insert(row).execute()
        except Exception as e:
            logger.warning(f"Failed to write agent_run log: {e}")
