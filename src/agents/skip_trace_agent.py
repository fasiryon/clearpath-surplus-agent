"""
Skip trace agent: claims 'skip_trace' tasks, calls BatchSkipTracing API,
writes contact to surplus_contacts, seeds outreach tasks.

Refactored from src/skip_trace.py into the v2 agent/queue pattern.
Core skip_trace_owner() logic is preserved from v1.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from src.agents.base_agent import BaseAgent
from src.models import SkipTraceResult
from src import queue as q

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BST_API_KEY = os.environ["BATCH_SKIP_TRACE_API_KEY"]
BEEN_VERIFIED_API_KEY = os.getenv("BEEN_VERIFIED_API_KEY", "")
DEFAULT_FEE = float(os.getenv("DEFAULT_FEE_PERCENTAGE", "40.0"))

BST_API_URL = "https://api.batchskiptracing.com/v1/search"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SkipTraceAgent(BaseAgent):
    task_type = "skip_trace"

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Skip-trace the owner for one surplus case and seed an outreach task.

        Args:
            task: agent_tasks row; payload has case_id and case_number.

        Returns:
            {'traced': bool, 'provider': str, 'tasks_seeded': int}
        """
        payload = task.get("payload", {})
        case_id = payload.get("case_id", "")
        case_number = payload.get("case_number", "")

        # Fetch case data needed for skip trace
        case = await _fetch_case(case_id)
        if not case:
            logger.warning(f"Case {case_id} not found — skipping")
            return {"traced": False, "provider": "none", "tasks_seeded": 0}

        name = case.get("defendant_name") or ""
        address = case.get("property_address") or ""

        if not name:
            logger.warning(f"No defendant name on case {case_number}")
            return {"traced": False, "provider": "none", "tasks_seeded": 0}

        logger.info(f"Skip tracing: {name} | {address} | case={case_number}")

        # Primary: BatchSkipTracing
        result = await _skip_trace_bst(name, address)

        # Fallback: BeenVerified (if primary found nothing)
        if result is None and BEEN_VERIFIED_API_KEY:
            result = await _skip_trace_beenverified(name, address)

        if result is None:
            logger.warning(f"No contact info found for {name} ({case_number})")
            return {"traced": False, "provider": "none", "tasks_seeded": 0}

        # Write contact record
        contact_id = await _upsert_contact(case_id, result, address)
        tasks_seeded = 0

        if contact_id:
            # Update case status
            db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            try:
                db.table("surplus_cases").update({"status": "skip_traced"}).eq("id", case_id).execute()
            except Exception as e:
                logger.error(f"Failed to update case status: {e}")

            # Seed outreach task
            seeded = await q.seed_task(
                task_type="outreach",
                payload={"contact_id": contact_id},
                state=task.get("state", "MD"),
                county=task.get("county", ""),
                task_key=f"outreach:{contact_id}",
            )
            if seeded:
                tasks_seeded += 1

            logger.success(
                f"Traced: {name} → phone={result.best_phone}, email={result.best_email}"
            )

        return {
            "traced": contact_id is not None,
            "provider": result.provider,
            "tasks_seeded": tasks_seeded,
        }


async def _fetch_case(case_id: str) -> dict[str, Any] | None:
    """Fetch case row from surplus_cases by id."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        result = (
            db.table("surplus_cases")
            .select("id, case_number, defendant_name, property_address, county, surplus_amount")
            .eq("id", case_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Failed to fetch case {case_id}: {e}")
        return None


async def _upsert_contact(
    case_id: str,
    result: SkipTraceResult,
    last_known_address: str,
) -> str | None:
    """Write or update a surplus_contacts row. Returns contact UUID string."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    payload = {
        "case_id": case_id,
        "owner_name": result.owner_name,
        "phone": result.best_phone,
        "email": result.best_email,
        "last_known_address": last_known_address,
        "current_address": result.current_address,
        "skip_trace_source": result.provider,
        "outreach_status": "pending",
        "fee_percentage": DEFAULT_FEE,
    }
    try:
        r = db.table("surplus_contacts").upsert(payload, on_conflict="case_id").execute()
        if r.data:
            return str(r.data[0]["id"])
    except Exception as e:
        logger.error(f"Failed to upsert contact for case {case_id}: {e}")
    return None


async def _skip_trace_bst(name: str, address: str) -> SkipTraceResult | None:
    """Call BatchSkipTracing API. Preserved logic from v1 skip_trace.py."""
    name_parts = name.strip().split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

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
                headers={"Authorization": f"Bearer {BST_API_KEY}", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        phones = data.get("phones", [])
        emails = data.get("emails", [])
        addresses = data.get("addresses", [])

        best_phone = phones[0].get("number") if phones else None
        best_email = emails[0].get("address") if emails else None
        current_address: str | None = None
        if addresses:
            a = addresses[0]
            parts = [a.get("streetLine1", ""), a.get("city", ""), a.get("state", ""), a.get("zip", "")]
            current_address = ", ".join(p for p in parts if p) or None

        if not best_phone and not best_email and not current_address:
            return None

        return SkipTraceResult(
            owner_name=name,
            best_phone=best_phone,
            best_email=best_email,
            current_address=current_address,
            provider="batchskiptracing",
            raw_response=data,
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"BST HTTP {e.response.status_code} for '{name}': {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"BST connection error for '{name}': {e}")
        return None
    except Exception as e:
        logger.error(f"BST unexpected error for '{name}': {e}")
        return None


async def _skip_trace_beenverified(name: str, address: str) -> SkipTraceResult | None:
    """
    BeenVerified fallback stub.

    TODO: Implement when BEEN_VERIFIED_API_KEY is provisioned.
    POST https://api.beenverified.com/v2/people/search
    Headers: {"Authorization": f"Bearer {BEEN_VERIFIED_API_KEY}"}
    Body: {"name": name, "address": address}
    Response schema differs from BST — verify against live docs.
    """
    logger.warning(f"BeenVerified stub called for '{name}' — not yet implemented")
    return None


if __name__ == "__main__":
    asyncio.run(SkipTraceAgent().run())
