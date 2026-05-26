"""
Outreach agent: claims 'outreach' tasks, POSTs each contact's full payload
to the Zapier webhook, logs results.

Refactored from src/outreach.py into v2 agent/queue pattern.
Core trigger_outreach() logic preserved from v1.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from src.agents.base_agent import BaseAgent
from src.models import OutreachPayload

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ZAPIER_WEBHOOK = os.environ["ZAPIER_OUTREACH_WEBHOOK"]

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class OutreachAgent(BaseAgent):
    task_type = "outreach"

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Fire Zapier webhook for one contact and log the result.

        Args:
            task: agent_tasks row; payload has contact_id.

        Returns:
            {'success': bool, 'channel': 'zapier', 'owner': str}
        """
        payload = task.get("payload", {})
        contact_id = payload.get("contact_id", "")

        if not contact_id:
            raise ValueError("outreach task payload missing contact_id")

        contact = await _fetch_contact(contact_id)
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")

        # Build enriched dict for webhook payload
        case_data = contact.get("surplus_cases") or {}
        enriched = {
            "contact_id": contact_id,
            "owner_name": contact["owner_name"],
            "phone": contact.get("phone"),
            "email": contact.get("email"),
            "last_known_address": contact.get("last_known_address"),
            "fee_percentage": float(contact.get("fee_percentage") or 40.0),
            "case_number": case_data.get("case_number", ""),
            "county": case_data.get("county", ""),
            "property_address": case_data.get("property_address") or contact.get("last_known_address"),
            "surplus_amount": case_data.get("surplus_amount", 0),
        }

        if not enriched["surplus_amount"]:
            logger.warning(f"Contact {contact_id} has no surplus_amount — skipping outreach")
            return {"success": False, "channel": "zapier", "owner": enriched["owner_name"]}

        success = await _fire_webhook(enriched)
        await _log_and_update(contact_id, enriched.get("case_id", ""), success)

        return {
            "success": success,
            "channel": "zapier",
            "owner": enriched["owner_name"],
        }


async def _fetch_contact(contact_id: str) -> dict[str, Any] | None:
    """Fetch contact row joined with case data."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        result = (
            db.table("surplus_contacts")
            .select(
                "id, case_id, owner_name, phone, email, last_known_address, fee_percentage, "
                "surplus_cases(case_number, county, property_address, surplus_amount)"
            )
            .eq("id", contact_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Failed to fetch contact {contact_id}: {e}")
        return None


async def _fire_webhook(contact: dict[str, Any]) -> bool:
    """POST contact payload to Zapier webhook. Returns True on 2xx."""
    webhook_payload = OutreachPayload(
        owner_name=contact["owner_name"],
        phone=contact.get("phone"),
        email=contact.get("email"),
        property_address=contact.get("property_address") or contact.get("last_known_address", ""),
        surplus_amount=contact["surplus_amount"],
        case_number=contact["case_number"],
        county=contact["county"],
        contact_db_id=str(contact["contact_id"]),
        fee_percentage=float(contact.get("fee_percentage") or 40.0),
    )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                ZAPIER_WEBHOOK,
                json=webhook_payload.model_dump(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.success(
                f"Outreach sent: {webhook_payload.owner_name} | "
                f"case={webhook_payload.case_number} | "
                f"surplus=${webhook_payload.surplus_amount:,.0f}"
            )
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Zapier {e.response.status_code} for {contact['owner_name']}: {e.response.text[:200]}")
        return False
    except httpx.RequestError as e:
        logger.error(f"Zapier connection error for {contact['owner_name']}: {e}")
        return False


async def _log_and_update(contact_id: str, case_id: str, success: bool) -> None:
    """Update contact status and write to outreach_log."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        if success:
            db.table("surplus_contacts").update({"outreach_status": "mail_sent"}).eq("id", contact_id).execute()
            if case_id:
                db.table("surplus_cases").update({"status": "outreach_sent"}).eq("id", case_id).execute()

        db.table("outreach_log").insert({
            "contact_id": contact_id,
            "channel": "zapier_webhook",
            "template_used": "initial_outreach_v2",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "response_received": False,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log/update outreach for contact {contact_id}: {e}")


if __name__ == "__main__":
    asyncio.run(OutreachAgent().run())
