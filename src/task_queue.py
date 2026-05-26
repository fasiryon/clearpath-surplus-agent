"""
Supabase-backed task queue for ClearPath Surplus v2 agent pipeline.

Agents claim tasks atomically via a PostgreSQL function (`claim_task`)
that uses FOR UPDATE SKIP LOCKED — preventing two workers from claiming
the same task even if they run simultaneously.

All public functions are async; Supabase sync client calls are wrapped
in asyncio.to_thread() to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def _db() -> Client:
    """Return a fresh Supabase client. Called inside to_thread to avoid sharing."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def seed_scrape_tasks(counties: list[dict[str, Any]]) -> int:
    """
    Seed one 'scrape' task per active county for today's run.

    Uses task_key = 'scrape:{state}:{county}:{today}' for idempotency —
    re-running the scheduler on the same day will insert nothing.

    Args:
        counties: List of county dicts with keys: name, code, state (from states.json).

    Returns:
        Number of tasks newly inserted (0 if all already existed for today).
    """
    today = date.today().isoformat()
    rows = []
    for c in counties:
        state = c.get("state", "MD")
        county = c["name"]
        task_key = f"scrape:{state}:{county}:{today}"
        rows.append({
            "task_type": "scrape",
            "status": "pending",
            "priority": 5,
            "state": state,
            "county": county,
            "task_key": task_key,
            "payload": {
                "state": state,
                "county": county,
                "county_code": c.get("code", ""),
                "lookback_days": int(os.getenv("SCRAPE_LOOKBACK_DAYS", "3")),
            },
        })

    if not rows:
        return 0

    def _insert() -> Any:
        return (
            _db()
            .table("agent_tasks")
            .upsert(rows, on_conflict="task_key", ignore_duplicates=True)
            .execute()
        )

    try:
        result = await asyncio.to_thread(_insert)
        inserted = len(result.data) if result.data else 0
        logger.info(f"Seeded {inserted}/{len(rows)} scrape tasks")
        return inserted
    except Exception as e:
        logger.error(f"Failed to seed scrape tasks: {e}")
        return 0


async def seed_task(
    task_type: str,
    payload: dict[str, Any],
    state: str | None = None,
    county: str | None = None,
    priority: int = 5,
    task_key: str | None = None,
) -> bool:
    """
    Seed a single task of any type.

    Args:
        task_type: One of 'scrape', 'docket_analysis', 'skip_trace', 'outreach'.
        payload: JSON payload consumed by the corresponding agent.
        state: Optional state code for filtering/logging.
        county: Optional county name for filtering/logging.
        priority: Higher number = higher priority (default 5).
        task_key: Optional unique key for idempotency. If None, no dedup.

    Returns:
        True if task was inserted, False on error or duplicate.
    """
    row: dict[str, Any] = {
        "task_type": task_type,
        "status": "pending",
        "priority": priority,
        "payload": payload,
    }
    if state:
        row["state"] = state
    if county:
        row["county"] = county
    if task_key:
        row["task_key"] = task_key

    def _insert() -> Any:
        if task_key:
            return (
                _db()
                .table("agent_tasks")
                .upsert(row, on_conflict="task_key", ignore_duplicates=True)
                .execute()
            )
        return _db().table("agent_tasks").insert(row).execute()

    try:
        result = await asyncio.to_thread(_insert)
        inserted = bool(result.data)
        if inserted:
            logger.debug(f"Seeded {task_type} task: {task_key or payload}")
        return inserted
    except Exception as e:
        logger.error(f"Failed to seed {task_type} task: {e}")
        return False


async def claim_task(task_type: str, worker_id: str) -> dict[str, Any] | None:
    """
    Atomically claim the highest-priority pending task of a given type.

    Calls the PostgreSQL `claim_task` function (defined in migration 002)
    which uses FOR UPDATE SKIP LOCKED — safe for concurrent workers.

    Args:
        task_type: Which task queue to pull from.
        worker_id: This worker's unique ID (stored for debugging).

    Returns:
        The claimed task as a dict, or None if queue is empty.
    """
    def _claim() -> Any:
        return (
            _db()
            .rpc("claim_task", {"p_task_type": task_type, "p_worker_id": worker_id})
            .execute()
        )

    try:
        result = await asyncio.to_thread(_claim)
        tasks = result.data or []
        if tasks:
            logger.debug(f"[{worker_id[:8]}] Claimed {task_type} task: {tasks[0].get('id')}")
            return tasks[0]
        return None
    except Exception as e:
        logger.error(f"Failed to claim {task_type} task: {e}")
        return None


async def complete_task(task_id: str, result_payload: dict[str, Any]) -> None:
    """
    Mark a task as done and store its result.

    Args:
        task_id: agent_tasks.id UUID string.
        result_payload: Dict describing what the agent produced.
    """
    def _update() -> Any:
        return (
            _db()
            .rpc(
                "complete_task",
                {"p_task_id": task_id, "p_result": result_payload},
            )
            .execute()
        )

    try:
        await asyncio.to_thread(_update)
        logger.debug(f"Task {task_id} marked done")
    except Exception as e:
        logger.error(f"Failed to complete task {task_id}: {e}")


async def fail_task(task_id: str, error: str) -> None:
    """
    Mark a task as failed and record the error message.

    Args:
        task_id: agent_tasks.id UUID string.
        error: Error message or stringified exception.
    """
    def _update() -> Any:
        return (
            _db()
            .rpc("fail_task", {"p_task_id": task_id, "p_error": error[:2000]})
            .execute()
        )

    try:
        await asyncio.to_thread(_update)
        logger.debug(f"Task {task_id} marked failed")
    except Exception as e:
        logger.error(f"Failed to fail task {task_id}: {e}")


async def get_pending_count(task_type: str) -> int:
    """
    Return the number of pending tasks of a given type.

    Args:
        task_type: Task type to count.

    Returns:
        Count of pending tasks.
    """
    def _count() -> Any:
        return (
            _db()
            .table("agent_tasks")
            .select("id", count="exact")
            .eq("task_type", task_type)
            .eq("status", "pending")
            .execute()
        )

    try:
        result = await asyncio.to_thread(_count)
        return result.count or 0
    except Exception as e:
        logger.error(f"Failed to get pending count for {task_type}: {e}")
        return 0
