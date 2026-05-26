"""Pydantic v2 data models for ClearPath Surplus agent."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CaseStatus(str, Enum):
    NEW = "new"
    SKIP_TRACED = "skip_traced"
    OUTREACH_PENDING = "outreach_pending"
    OUTREACH_SENT = "outreach_sent"
    AGREEMENT_SIGNED = "agreement_signed"
    CLAIM_FILED = "claim_filed"
    FUNDS_RECEIVED = "funds_received"
    CLOSED_NO_CONTACT = "closed_no_contact"
    CLOSED_DECLINED = "closed_declined"
    CLOSED_NO_SURPLUS = "closed_no_surplus"


class OutreachStatus(str, Enum):
    PENDING = "pending"
    MAIL_SENT = "mail_sent"
    SMS_SENT = "sms_sent"
    EMAIL_SENT = "email_sent"
    RESPONDED = "responded"
    DO_NOT_CONTACT = "do_not_contact"


class OutreachChannel(str, Enum):
    MAIL = "mail"
    SMS = "sms"
    EMAIL = "email"
    PHONE = "phone"


class CaseRecord(BaseModel):
    case_number: str
    county: str
    title: str
    filing_date: str | None = None
    sale_date: str | None = None
    detail_url: str | None = None
    property_address: str | None = None
    defendant_name: str | None = None
    plaintiff_name: str | None = None
    surplus_amount: float | None = None
    scrape_source: str = "mjcs"
    raw_docket: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("surplus_amount", mode="before")
    @classmethod
    def parse_surplus(cls, v: Any) -> float | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


class ContactRecord(BaseModel):
    case_id: str
    owner_name: str
    phone: str | None = None
    email: str | None = None
    current_address: str | None = None
    skip_trace_source: str
    fee_percentage: float = 40.0
    outreach_status: OutreachStatus = OutreachStatus.PENDING

    @field_validator("fee_percentage")
    @classmethod
    def validate_fee(cls, v: float) -> float:
        if not 25.0 <= v <= 50.0:
            raise ValueError("Fee percentage must be between 25% and 50%")
        return v


class SurplusResult(BaseModel):
    case_number: str
    surplus_amount: float | None
    surplus_keywords_found: list[str]
    docket_entries: list[dict[str, Any]]
    confidence: str  # "high", "medium", "low"


class SkipTraceResult(BaseModel):
    owner_name: str
    best_phone: str | None
    best_email: str | None
    current_address: str | None
    provider: str
    raw_response: dict[str, Any] = Field(default_factory=dict)


class OutreachPayload(BaseModel):
    owner_name: str
    phone: str | None
    email: str | None
    property_address: str
    surplus_amount: float
    case_number: str
    county: str
    contact_db_id: str
    fee_percentage: float = 40.0
