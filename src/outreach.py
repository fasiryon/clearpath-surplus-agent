"""
Outreach trigger module: POST contact records to Zapier webhook.

The Zapier zap (configured separately in Zapier.com) handles:
  1. Creating HubSpot contact + deal
  2. Adding contact to SimpleTexting 10DLC sequence
  3. Adding contact to Mailchimp 5-email drip sequence

This module's job: pull pending contacts, fire webhooks, log results.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from models import OutreachPayload

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ZAPIER_WEBHOOK = os.environ["ZAPIER_OUTREACH_WEBHOOK"]

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def trigger_outreach(contact: dict[str, Any]) -> bool:
    """
    POST a contact's outreach payload to the Zapier webhook.

    Args:
        contact: Dict from surplus_contacts joined with surplus_cases data.

    Returns:
        True if webhook responded with 2xx, False otherwise.
    """
    payload = OutreachPayload(
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
                json=payload.model_dump(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.success(
                f"Outreach triggered: {payload.owner_name} | "
                f"case={payload.case_number} | "
                f"surplus=${payload.surplus_amount:,.0f}"
            )
            return True

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Zapier webhook error for {contact['owner_name']}: "
            f"{e.response.status_code} — {e.response.text[:200]}"
        )
        return False
    except httpx.RequestError as e:
        logger.error(f"Zapier connection error for {contact['owner_name']}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected outreach error for {contact['owner_name']}: {e}")
        return False


async def log_outreach(
    db: Any,
    contact_id: str,
    channel: str,
    template: str,
    success: bool,
) -> None:
    """
    Write an outreach event to the outreach_log table.

    Args:
        db: Supabase client.
        contact_id: surplus_contacts.id value.
        channel: "zapier_webhook" or specific channel name.
        template: Template identifier used.
        success: Whether the outreach call succeeded.
    """
    try:
        db.table("outreach_log").insert(
            {
                "contact_id": contact_id,
                "channel": channel,
                "template_used": template,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "response_received": False,
            }
        ).execute()
    except Exception as e:
        logger.error(f"Failed to log outreach for contact {contact_id}: {e}")


async def run_outreach() -> int:
    """
    Main entry point: pull all pending contacts and fire Zapier outreach webhooks.

    Returns:
        Number of contacts where outreach was successfully triggered.
    """
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    triggered = 0

    try:
        # Join surplus_contacts with surplus_cases to get full context
        result = (
            db.table("surplus_contacts")
            .select(
                "id, case_id, owner_name, phone, email, last_known_address, fee_percentage, "
                "surplus_cases(case_number, county, property_address, surplus_amount)"
            )
            .eq("outreach_status", "pending")
            .execute()
        )
        contacts = result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch pending contacts: {e}")
        return 0

    logger.info(f"Triggering outreach for {len(contacts)} pending contacts")

    for row in contacts:
        contact_id = str(row["id"])
        case_data = row.get("surplus_cases") or {}

        enriched = {
            "contact_id": contact_id,
            "owner_name": row["owner_name"],
            "phone": row.get("phone"),
            "email": row.get("email"),
            "last_known_address": row.get("last_known_address"),
            "fee_percentage": row.get("fee_percentage", 40.0),
            "case_number": case_data.get("case_number", ""),
            "county": case_data.get("county", ""),
            "property_address": case_data.get("property_address") or row.get("last_known_address"),
            "surplus_amount": case_data.get("surplus_amount", 0),
        }

        if not enriched["surplus_amount"]:
            logger.warning(f"Contact {contact_id} has no surplus amount — skipping outreach")
            continue

        success = await trigger_outreach(enriched)

        if success:
            # Update status and log
            try:
                db.table("surplus_contacts").update(
                    {"outreach_status": "mail_sent"}
                ).eq("id", contact_id).execute()

                db.table("surplus_cases").update(
                    {"status": "outreach_sent"}
                ).eq("id", row["case_id"]).execute()

            except Exception as e:
                logger.error(f"Failed to update status for contact {contact_id}: {e}")

            await log_outreach(
                db, contact_id, "zapier_webhook", "initial_outreach_v1", success=True
            )
            triggered += 1
        else:
            await log_outreach(
                db, contact_id, "zapier_webhook", "initial_outreach_v1", success=False
            )

    logger.info(f"Outreach complete: {triggered}/{len(contacts)} contacts triggered")
    return triggered


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_outreach())
