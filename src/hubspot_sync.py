"""
Direct HubSpot CRM integration — backup to Zapier webhook.

Use this when:
  - Zapier is down or misconfigured
  - You want direct control over CRM data without a third-party layer
  - Debugging CRM sync issues

Uses HubSpot v3 API.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
HUBSPOT_API_KEY = os.environ["HUBSPOT_API_KEY"]
HUBSPOT_PIPELINE_ID = os.getenv("HUBSPOT_PIPELINE_ID", "default")
HUBSPOT_STAGE_NEW_LEAD = os.getenv("HUBSPOT_STAGE_NEW_LEAD", "appointmentscheduled")

HS_BASE = "https://api.hubapi.com/crm/v3"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _hs_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
    }


async def create_hubspot_contact(
    first_name: str,
    last_name: str,
    phone: str | None,
    email: str | None,
    address: str | None,
) -> str | None:
    """
    Create a HubSpot contact record.

    Args:
        first_name: Contact first name.
        last_name: Contact last name.
        phone: Best phone number.
        email: Best email address.
        address: Current mailing address.

    Returns:
        HubSpot contact ID string, or None on failure.
    """
    properties: dict[str, Any] = {
        "firstname": first_name,
        "lastname": last_name,
    }
    if phone:
        properties["phone"] = phone
    if email:
        properties["email"] = email
    if address:
        properties["address"] = address

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{HS_BASE}/objects/contacts",
                json={"properties": properties},
                headers=_hs_headers(),
            )

            # 409 = contact already exists → extract existing ID
            if response.status_code == 409:
                error_data = response.json()
                existing_id = error_data.get("message", "").split("ID: ")[-1].strip()
                if existing_id:
                    logger.info(f"HubSpot contact already exists: {existing_id}")
                    return existing_id
                response.raise_for_status()

            response.raise_for_status()
            contact_id = response.json()["id"]
            logger.success(f"HubSpot contact created: {contact_id} ({first_name} {last_name})")
            return contact_id

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HubSpot contact creation failed ({first_name} {last_name}): "
            f"{e.response.status_code} — {e.response.text[:300]}"
        )
        return None
    except Exception as e:
        logger.error(f"HubSpot contact error: {e}")
        return None


async def create_hubspot_deal(
    deal_name: str,
    surplus_amount: float,
    contact_id: str,
) -> str | None:
    """
    Create a HubSpot deal and associate it to a contact.

    Args:
        deal_name: Deal title, e.g., "Surplus – 123 Main St".
        surplus_amount: Full surplus amount (agent fee computed separately).
        contact_id: HubSpot contact ID to associate.

    Returns:
        HubSpot deal ID string, or None on failure.
    """
    deal_payload = {
        "properties": {
            "dealname": deal_name,
            "amount": str(surplus_amount),
            "pipeline": HUBSPOT_PIPELINE_ID,
            "dealstage": HUBSPOT_STAGE_NEW_LEAD,
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 3,  # Contact-to-Deal association type
                    }
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{HS_BASE}/objects/deals",
                json=deal_payload,
                headers=_hs_headers(),
            )
            response.raise_for_status()
            deal_id = response.json()["id"]
            logger.success(f"HubSpot deal created: {deal_id} — {deal_name}")
            return deal_id

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HubSpot deal creation failed ({deal_name}): "
            f"{e.response.status_code} — {e.response.text[:300]}"
        )
        return None
    except Exception as e:
        logger.error(f"HubSpot deal error: {e}")
        return None


async def sync_to_hubspot(contact_db_id: str) -> str | None:
    """
    Full sync: pull contact from Supabase, create HubSpot contact + deal, store ID.

    Args:
        contact_db_id: surplus_contacts.id to sync.

    Returns:
        HubSpot contact ID on success, None on failure.
    """
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    try:
        result = (
            db.table("surplus_contacts")
            .select("*, surplus_cases(case_number, property_address, surplus_amount, county)")
            .eq("id", contact_db_id)
            .single()
            .execute()
        )
        row = result.data
    except Exception as e:
        logger.error(f"Failed to fetch contact {contact_db_id}: {e}")
        return None

    name_parts = (row.get("owner_name") or "").split()
    first_name = name_parts[0] if name_parts else "Unknown"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    case = row.get("surplus_cases") or {}
    property_address = case.get("property_address") or row.get("last_known_address") or ""
    surplus_amount = float(case.get("surplus_amount") or 0)
    case_number = case.get("case_number") or ""

    # Step 1: Create contact
    hs_contact_id = await create_hubspot_contact(
        first_name=first_name,
        last_name=last_name,
        phone=row.get("phone"),
        email=row.get("email"),
        address=row.get("current_address") or row.get("last_known_address"),
    )
    if not hs_contact_id:
        return None

    # Step 2: Create deal
    deal_name = f"Surplus – {property_address} ({case_number})"
    hs_deal_id = await create_hubspot_deal(deal_name, surplus_amount, hs_contact_id)

    # Step 3: Store HubSpot contact ID back in Supabase
    try:
        db.table("surplus_contacts").update(
            {"hubspot_contact_id": hs_contact_id}
        ).eq("id", contact_db_id).execute()
    except Exception as e:
        logger.error(f"Failed to store HubSpot ID for contact {contact_db_id}: {e}")

    logger.info(
        f"HubSpot sync complete: contact={hs_contact_id}, deal={hs_deal_id} "
        f"for {row.get('owner_name')}"
    )
    return hs_contact_id


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python hubspot_sync.py <contact_db_id>")
        sys.exit(1)

    asyncio.run(sync_to_hubspot(sys.argv[1]))
