"""Tests for Pydantic v2 models — no external API calls needed."""

from __future__ import annotations

import pytest

from src.models import (
    AgentTask,
    CaseRecord,
    ContactRecord,
    DocketAnalysisResult,
    OutreachPayload,
    SkipTraceResult,
    TaskStatus,
    TaskType,
)


class TestCaseRecord:
    def test_surplus_amount_string_parsing(self):
        case = CaseRecord(
            case_number="C-24-001",
            county="Baltimore County",
            title="Test Case",
            surplus_amount="$42,500.00",
        )
        assert case.surplus_amount == 42500.0

    def test_surplus_amount_none(self):
        case = CaseRecord(
            case_number="C-24-002",
            county="Baltimore County",
            title="Test Case",
            surplus_amount=None,
        )
        assert case.surplus_amount is None

    def test_surplus_amount_invalid_string(self):
        case = CaseRecord(
            case_number="C-24-003",
            county="Baltimore County",
            title="Test Case",
            surplus_amount="not a number",
        )
        assert case.surplus_amount is None

    def test_raw_docket_text_field_exists(self):
        case = CaseRecord(
            case_number="C-24-004",
            county="Baltimore County",
            title="Test Case",
            raw_docket_text="07/14/2024: Auditor's Report filed",
        )
        assert case.raw_docket_text == "07/14/2024: Auditor's Report filed"

    def test_raw_docket_defaults_to_empty_list(self):
        case = CaseRecord(
            case_number="C-24-005",
            county="Baltimore County",
            title="Test",
        )
        assert case.raw_docket == []

    def test_defaults_populated(self):
        case = CaseRecord(
            case_number="C-24-006",
            county="Baltimore County",
            title="Test",
        )
        assert case.scrape_source == "mjcs"
        assert case.raw_docket_text is None


class TestContactRecord:
    def test_valid_fee_percentage(self):
        contact = ContactRecord(
            case_id="uuid-1",
            owner_name="John Smith",
            skip_trace_source="batchskiptracing",
            fee_percentage=35.0,
        )
        assert contact.fee_percentage == 35.0

    def test_default_fee_percentage(self):
        contact = ContactRecord(
            case_id="uuid-2",
            owner_name="Jane Doe",
            skip_trace_source="batchskiptracing",
        )
        assert contact.fee_percentage == 40.0

    def test_fee_too_high_raises(self):
        with pytest.raises(ValueError, match="Fee percentage"):
            ContactRecord(
                case_id="uuid-3",
                owner_name="Test",
                skip_trace_source="batchskiptracing",
                fee_percentage=60.0,
            )

    def test_fee_too_low_raises(self):
        with pytest.raises(ValueError, match="Fee percentage"):
            ContactRecord(
                case_id="uuid-4",
                owner_name="Test",
                skip_trace_source="batchskiptracing",
                fee_percentage=10.0,
            )


class TestDocketAnalysisResult:
    def test_high_confidence_with_amount(self):
        result = DocketAnalysisResult(
            has_surplus=True,
            surplus_amount=42500.0,
            confidence="high",
            evidence="Auditor's Report filed; surplus funds of $42,500.00",
        )
        assert result.has_surplus is True
        assert result.surplus_amount == 42500.0
        assert result.confidence == "high"

    def test_no_surplus(self):
        result = DocketAnalysisResult(
            has_surplus=False,
            surplus_amount=None,
            confidence="high",
            evidence="No surplus — full payoff of all liens from sale proceeds",
        )
        assert result.has_surplus is False
        assert result.surplus_amount is None


class TestAgentTask:
    def test_task_type_enum_values(self):
        assert TaskType.SCRAPE == "scrape"
        assert TaskType.DOCKET_ANALYSIS == "docket_analysis"
        assert TaskType.SKIP_TRACE == "skip_trace"
        assert TaskType.OUTREACH == "outreach"

    def test_task_status_enum_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.FAILED == "failed"

    def test_agent_task_construction(self):
        task = AgentTask(
            id="task-uuid",
            task_type=TaskType.SCRAPE,
            status=TaskStatus.PENDING,
            payload={"county": "Baltimore County"},
        )
        assert task.task_type == "scrape"
        assert task.payload["county"] == "Baltimore County"


class TestOutreachPayload:
    def test_valid_payload(self):
        payload = OutreachPayload(
            owner_name="John Smith",
            phone="443-555-0100",
            email="john@example.com",
            property_address="123 Main St, Towson MD",
            surplus_amount=42500.0,
            case_number="C-24-001234",
            county="Baltimore County",
            contact_db_id="contact-uuid",
            fee_percentage=40.0,
        )
        assert payload.surplus_amount == 42500.0
        assert payload.fee_percentage == 40.0

    def test_json_serialization(self):
        payload = OutreachPayload(
            owner_name="Jane Doe",
            phone=None,
            email=None,
            property_address="456 Oak Ave",
            surplus_amount=15000.0,
            case_number="C-24-999",
            county="Baltimore County",
            contact_db_id="uuid-x",
        )
        data = payload.model_dump()
        assert data["phone"] is None
        assert data["surplus_amount"] == 15000.0
