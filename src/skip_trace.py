"""
Skip tracing module: locate current contact information for surplus case owners.

Primary provider: BatchSkipTracing (batchskiptracing.com)
Fallback provider: BeenVerified (stub — activate if BatchSkipTracing fails)

Pulls surplus_cases with status='new' and surplus_amount >= MIN_SURPLUS_AMOUNT,
enriches with phone/email/address, writes to surplus_contacts.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from models import ContactRecord, SkipTraceResult

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BST_API_KEY = os.environ["BATCH_SKIP_TRACE_API_KEY"]
BEEN_VERIFIED_API_KEY = os.getenv("BEEN_VERIFIED_API_KEY", "")
MIN_SURPLUS = float(os.getenv("MIN_SURPLUS_AMOUNT", "5000"))
DEFAULT_FEE = float(os.getenv("DEFAULT_FEE_PERCENTAGE", "40.0"))

BST_API_URL = "https://api.batchskiptracing.com/v1/search"

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def skip_trace_owner(
    name: str,
    address: str,
    provider: str = "batchskiptracing",
) -> SkipTraceResult | None:
    """
    Look up current contact info for a property owner by name + last known address.

    Args:
        name: Owner's full name (defendant name from court record).
        address: Last known address (property address from foreclosure).
        provider: Which API to use — "batchskiptracing" or "beenverified".

    Returns:
        SkipTraceResult with best phone, email, and current address, or None on failure.
    """
    if provider == "batchskiptracing":
        return await _skip_trace_bst(name, address)
    elif provider == "beenverified":
        return await _skip_trace_beenverified(name, address)
    else:
        logger.error(f"Unknown skip trace provider: {provider}")
        return None


async def _skip_trace_bst(name: str, address: str) -> SkipTraceResult | None:
    """
    Call BatchSkipTracing API for single-record lookup.

    BatchSkipTracing docs: https://batchskiptracing.com/documentation
    Single search endpoint accepts first/last name + address components.
    """
    # Parse name into first/last (best-effort split)
    name_parts = name.strip().split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Parse address components (basic split — ideally use address parser lib)
    address_parts = address.split(",")
    street = address_parts[0].strip() if address_parts else address
    city = address_parts[1].strip() if len(address_parts) > 1 else ""
    state_zip = address_parts[2].strip() if len(address_parts) > 2 else ""
    state = state_zip[:2] if state_zip else "MD"
    zip_code = state_zip[2:].strip() if len(state_zip) > 2 else ""

    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "address": street,
        "city": city,
        "state": state,
        "zip": zip_code,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                BST_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {BST_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        return _parse_bst_response(name, data)

    except httpx.HTTPStatusError as e:
        logger.error(
            f"BatchSkipTracing HTTP error for '{name}': "
            f"{e.response.status_code} — {e.response.text[:200]}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(f"BatchSkipTracing connection error for '{name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in BatchSkipTracing for '{name}': {e}")
        return None


def _parse_bst_response(owner_name: str, data: dict[str, Any]) -> SkipTraceResult | None:
    """
    Extract best phone, email, and address from BatchSkipTracing response.

    BST returns arrays of phones/emails ranked by confidence — take index 0.
    NOTE: Response schema should be verified against live BST docs.
    """
    try:
        phones: list[dict] = data.get("phones", [])
        emails: list[dict] = data.get("emails", [])
        addresses: list[dict] = data.get("addresses", [])

        best_phone = phones[0].get("number") if phones else None
        best_email = emails[0].get("address") if emails else None

        current_address: str | None = None
        if addresses:
            addr = addresses[0]
            parts = [
                addr.get("streetLine1", ""),
                addr.get("city", ""),
                addr.get("state", ""),
                addr.get("zip", ""),
            ]
            current_address = ", ".join(p for p in parts if p)

        if not best_phone and not best_email and not current_address:
            logger.warning(f"BatchSkipTracing returned no contact info for '{owner_name}'")
            return None

        return SkipTraceResult(
            owner_name=owner_name,
            best_phone=best_phone,
            best_email=best_email,
            current_address=current_address,
            provider="batchskiptracing",
            raw_response=data,
        )

    except Exception as e:
        logger.error(f"Failed to parse BST response for '{owner_name}': {e}")
        return None


async def _skip_trace_beenverified(name: str, address: str) -> SkipTraceResult | None:
    """
    BeenVerified API stub — activate as fallback if BatchSkipTracing fails.

    BeenVerified Business API: https://developer.beenverified.com
    Requires a separate enterprise/business API agreement.
    """
    if not BEEN_VERIFIED_API_KEY:
        logger.warning("BeenVerified API key not configured — skipping fallback")
        return None

    logger.info(f"BeenVerified fallback lookup for '{name}' at '{address}'")

    # TODO: Implement BeenVerified API call when key is available.
    # Their API endpoint and payload structure differ from BST.
    # Placeholder structure:
    # POST https://api.beenverified.com/v2/people/search
    # Headers: { "Authorization": f"Bearer {BEEN_VERIFIED_API_KEY}" }
    # Body: { "name": name, "address": address }

    logger.warning("BeenVerified integration is a stub — implement when key is obtained")
    return None


async def run_skip_tracer() -> int:
    """
    Main entry point: process all 'new' surplus cases above MIN_SURPLUS.

    Returns:
        Number of contacts successfully skip-traced.
    """
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    contacted = 0

    try:
        result = (
            db.table("surplus_cases")
            .select("id, case_number, defendant_name, property_address, county, surplus_amount")
            .eq("status", "new")
            .gte("surplus_amount", MIN_SURPLUS)
            .execute()
        )
        cases = result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch cases from Supabase: {e}")
        return 0

    logger.info(f"Skip tracing {len(cases)} cases (surplus >= ${MIN_SURPLUS:,.0f})")

    for case in cases:
        case_id = case["id"]
        name = case.get("defendant_name") or ""
        address = case.get("property_address") or ""
        surplus = case.get("surplus_amount", 0)

        if not name:
            logger.warning(f"Case {case['case_number']} has no defendant name — skipping")
            continue

        logger.info(
            f"Skip tracing: {name} | {address} | surplus=${surplus:,.0f}"
        )

        result_data = await skip_trace_owner(name, address)

        if result_data:
            contact_payload = {
                "case_id": str(case_id),
                "owner_name": result_data.owner_name,
                "phone": result_data.best_phone,
                "email": result_data.best_email,
                "last_known_address": address,
                "current_address": result_data.current_address,
                "skip_trace_source": result_data.provider,
                "outreach_status": "pending",
                "fee_percentage": DEFAULT_FEE,
            }

            try:
                db.table("surplus_contacts").upsert(
                    contact_payload, on_conflict="case_id"
                ).execute()

                # Update case status
                db.table("surplus_cases").update({"status": "skip_traced"}).eq(
                    "id", case_id
                ).execute()

                logger.success(
                    f"Traced: {name} → phone={result_data.best_phone}, "
                    f"email={result_data.best_email}"
                )
                contacted += 1

            except Exception as e:
                logger.error(f"Failed to save contact for case {case['case_number']}: {e}")
        else:
            logger.warning(f"No contact info found for {name} ({case['case_number']})")

    logger.info(f"Skip trace complete: {contacted}/{len(cases)} contacts found")
    return contacted


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_skip_tracer())
