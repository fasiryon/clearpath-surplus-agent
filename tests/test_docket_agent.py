"""Tests for DocketAgent LLM response parsing — Anthropic API is mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import DocketAnalysisResult


@pytest.fixture
def mock_anthropic_surplus_response():
    """Mock Anthropic response where Claude found surplus funds."""
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "report_surplus_analysis"
    tool_use_block.input = {
        "has_surplus": True,
        "surplus_amount": 42500.0,
        "confidence": "high",
        "evidence": "Auditor's Report filed 07/14/2024; surplus funds of $42,500.00 held in registry",
    }

    usage = MagicMock()
    usage.input_tokens = 350
    usage.output_tokens = 85

    response = MagicMock()
    response.content = [tool_use_block]
    response.usage = usage
    return response


@pytest.fixture
def mock_anthropic_no_surplus_response():
    """Mock Anthropic response where Claude found no surplus."""
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "report_surplus_analysis"
    tool_use_block.input = {
        "has_surplus": False,
        "surplus_amount": None,
        "confidence": "high",
        "evidence": "Sale proceeds of $180,000 fully satisfied all liens. No surplus funds.",
    }

    usage = MagicMock()
    usage.input_tokens = 280
    usage.output_tokens = 60

    response = MagicMock()
    response.content = [tool_use_block]
    response.usage = usage
    return response


@pytest.mark.asyncio
async def test_analyze_docket_surplus_found(mock_anthropic_surplus_response):
    """DocketAgent._analyze_docket should return DocketAnalysisResult when surplus found."""
    with patch("src.agents.docket_agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_surplus_response)
        mock_cls.return_value = mock_client

        from src.agents.docket_agent import DocketAgent
        agent = DocketAgent.__new__(DocketAgent)
        agent.worker_id = "test-worker"
        agent.agent_name = "DocketAgent"
        agent._client = mock_client

        result, tokens = await agent._analyze_docket(
            "07/14/2024: Auditor's Report filed; surplus funds of $42,500.00",
            "C-24-001",
        )

    assert result is not None
    assert result.has_surplus is True
    assert result.surplus_amount == 42500.0
    assert result.confidence == "high"
    assert tokens == 435


@pytest.mark.asyncio
async def test_analyze_docket_no_surplus(mock_anthropic_no_surplus_response):
    """DocketAgent._analyze_docket should return has_surplus=False correctly."""
    with patch("src.agents.docket_agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_no_surplus_response)
        mock_cls.return_value = mock_client

        from src.agents.docket_agent import DocketAgent
        agent = DocketAgent.__new__(DocketAgent)
        agent.worker_id = "test-worker"
        agent.agent_name = "DocketAgent"
        agent._client = mock_client

        result, tokens = await agent._analyze_docket(
            "Sale proceeds of $180,000. All liens satisfied. No surplus.",
            "C-24-002",
        )

    assert result is not None
    assert result.has_surplus is False
    assert result.surplus_amount is None
    assert tokens == 340


@pytest.mark.asyncio
async def test_analyze_docket_empty_text_skipped():
    """DocketAgent.process should early-exit on empty docket text."""
    with patch("src.agents.docket_agent.anthropic.AsyncAnthropic"):
        from src.agents.docket_agent import DocketAgent
        agent = DocketAgent.__new__(DocketAgent)
        agent.worker_id = "test"
        agent.agent_name = "DocketAgent"
        agent._client = MagicMock()

        result = await agent.process({
            "payload": {
                "case_number": "C-24-003",
                "docket_text": "   ",
                "county": "Baltimore County",
                "state": "MD",
            }
        })

    assert result["has_surplus"] is False
    assert result["tokens_used"] == 0


@pytest.mark.asyncio
async def test_analyze_docket_api_error_returns_none():
    """_analyze_docket should return (None, 0) on Anthropic API error."""
    import anthropic as _anthropic

    with patch("src.agents.docket_agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=_anthropic.APIConnectionError(request=MagicMock())
        )
        mock_cls.return_value = mock_client

        from src.agents.docket_agent import DocketAgent
        agent = DocketAgent.__new__(DocketAgent)
        agent.worker_id = "test"
        agent.agent_name = "DocketAgent"
        agent._client = mock_client

        result, tokens = await agent._analyze_docket("Some docket text", "C-24-004")

    assert result is None
    assert tokens == 0
