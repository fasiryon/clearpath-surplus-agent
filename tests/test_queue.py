"""Tests for src/task_queue.py — all Supabase calls are mocked."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_seed_scrape_tasks_inserts_rows():
    """seed_scrape_tasks should call Supabase upsert with one row per county."""
    counties = [
        {"name": "Baltimore County", "code": "03", "state": "MD"},
        {"name": "Prince Georges", "code": "16", "state": "MD"},
    ]

    mock_result = MagicMock()
    mock_result.data = [{"id": "uuid-1"}, {"id": "uuid-2"}]

    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_result

        from src.task_queue import seed_scrape_tasks
        count = await seed_scrape_tasks(counties)

    assert count == 2
    mock_thread.assert_called_once()


@pytest.mark.asyncio
async def test_seed_scrape_tasks_empty_list_returns_zero():
    """seed_scrape_tasks with empty list should return 0 without DB call."""
    from src.task_queue import seed_scrape_tasks
    count = await seed_scrape_tasks([])
    assert count == 0


@pytest.mark.asyncio
async def test_claim_task_returns_dict_when_task_available():
    """claim_task should return the first element of the RPC result."""
    mock_result = MagicMock()
    mock_result.data = [{"id": "task-1", "task_type": "scrape", "payload": {"county": "Baltimore County"}}]

    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_result

        from src.task_queue import claim_task
        task = await claim_task("scrape", "worker-uuid")

    assert task is not None
    assert task["id"] == "task-1"


@pytest.mark.asyncio
async def test_claim_task_returns_none_when_queue_empty():
    """claim_task should return None when no tasks are available."""
    mock_result = MagicMock()
    mock_result.data = []

    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_result

        from src.task_queue import claim_task
        task = await claim_task("scrape", "worker-uuid")

    assert task is None


@pytest.mark.asyncio
async def test_claim_task_returns_none_on_exception():
    """claim_task should return None (not raise) when Supabase errors."""
    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = Exception("DB connection refused")

        from src.task_queue import claim_task
        task = await claim_task("scrape", "worker-uuid")

    assert task is None


@pytest.mark.asyncio
async def test_complete_task_calls_rpc():
    """complete_task should call the complete_task RPC."""
    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = MagicMock()

        from src.task_queue import complete_task
        await complete_task("task-uuid", {"cases_queued": 5})

    mock_thread.assert_called_once()


@pytest.mark.asyncio
async def test_fail_task_calls_rpc():
    """fail_task should call the fail_task RPC with the error string."""
    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = MagicMock()

        from src.task_queue import fail_task
        await fail_task("task-uuid", "ValueError: something went wrong")

    mock_thread.assert_called_once()


@pytest.mark.asyncio
async def test_seed_task_with_key_uses_upsert():
    """seed_task with a task_key should use upsert for idempotency."""
    mock_result = MagicMock()
    mock_result.data = [{"id": "new-task"}]

    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_result

        from src.task_queue import seed_task
        result = await seed_task(
            task_type="docket_analysis",
            payload={"case_number": "C-24-001"},
            task_key="docket_analysis:C-24-001",
        )

    assert result is True


@pytest.mark.asyncio
async def test_get_pending_count_returns_zero_on_empty():
    """get_pending_count should return 0 when no pending tasks."""
    mock_result = MagicMock()
    mock_result.count = 0

    with patch("src.task_queue.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_result

        from src.task_queue import get_pending_count
        count = await get_pending_count("scrape")

    assert count == 0
