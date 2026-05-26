"""Shared pytest fixtures for ClearPath Surplus test suite."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure env vars are set before any imports that read them at module level
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("BATCH_SKIP_TRACE_API_KEY", "test-bst-key")
os.environ.setdefault("ZAPIER_OUTREACH_WEBHOOK", "https://hooks.zapier.com/test/123")
os.environ.setdefault("HUBSPOT_API_KEY", "test-hubspot-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("SENTRY_DSN", "")


@pytest.fixture
def mock_supabase():
    """Mock Supabase client that returns empty data for all calls."""
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "test-uuid"}]
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"id": "test-uuid"}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    mock.rpc.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def sample_case():
    """A complete CaseRecord fixture for use in multiple tests."""
    from src.models import CaseRecord
    return CaseRecord(
        case_number="C-24-001234",
        county="Baltimore County",
        title="Wells Fargo vs. Smith, John",
        filing_date="01/15/2024",
        detail_url="https://casesearch.courts.state.md.us/casesearch/inquiryDetail.jis?caseId=C-24-001234",
        property_address="123 Main St, Towson, MD 21204",
        defendant_name="John Smith",
        plaintiff_name="Wells Fargo Bank NA",
        surplus_amount=42500.00,
        raw_docket=[
            {"date": "07/14/2024", "text": "Auditor's Report filed; surplus funds of $42,500.00"},
            {"date": "08/01/2024", "text": "Order ratifying sale entered"},
        ],
        raw_docket_text=(
            "07/14/2024: Auditor's Report filed; surplus funds of $42,500.00\n"
            "08/01/2024: Order ratifying sale entered"
        ),
    )


@pytest.fixture
def sample_task():
    """A sample agent_tasks row for testing agents."""
    return {
        "id": "task-uuid-1234",
        "task_type": "scrape",
        "status": "running",
        "payload": {
            "state": "MD",
            "county": "Baltimore County",
            "county_code": "03",
            "lookback_days": 3,
        },
        "state": "MD",
        "county": "Baltimore County",
        "worker_id": "worker-uuid-5678",
        "priority": 5,
    }
