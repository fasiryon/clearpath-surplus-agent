"""
Docket analysis agent: uses Claude Haiku to determine whether a foreclosure
docket contains evidence of surplus funds, and extracts the dollar amount.

Replaces all v1 regex-based surplus detection. LLM reads the raw docket
text and returns structured JSON via tool use — no regex, no keyword lists.

Cost model: claude-haiku-4-5-20251001 input ~$0.80/M tokens.
A docket is typically 500–2,000 tokens. At 200 cases/month = ~$0.20/month.
Every token count is logged to agent_runs.tokens_used for cost tracking.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client

from src.agents.base_agent import BaseAgent
from src.models import DocketAnalysisResult
from src import task_queue as q

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MIN_SURPLUS = float(os.getenv("MIN_SURPLUS_AMOUNT", "5000"))

HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Tool definition for structured surplus analysis output
SURPLUS_TOOL = {
    "name": "report_surplus_analysis",
    "description": (
        "Report the result of analyzing a foreclosure docket for surplus funds. "
        "Call this tool with your findings after reading the docket."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "has_surplus": {
                "type": "boolean",
                "description": "True if the docket contains evidence of surplus funds owed to the former homeowner.",
            },
            "surplus_amount": {
                "type": "number",
                "description": "Dollar amount of surplus funds if found, or null if unknown or no surplus.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": (
                    "high = explicit dollar amount found in auditor's report or order ratifying sale; "
                    "medium = surplus keywords present but no specific amount; "
                    "low = ambiguous language, possible surplus"
                ),
            },
            "evidence": {
                "type": "string",
                "description": "Key quote or summary from the docket that supports your determination.",
            },
        },
        "required": ["has_surplus", "confidence", "evidence"],
    },
}

SYSTEM_PROMPT = (
    "You are a Maryland foreclosure court document analyst. "
    "Your job is to read foreclosure case dockets and determine whether "
    "surplus funds remain in the court registry for the former homeowner. "
    "Surplus arises when the foreclosure sale price exceeds the total liens. "
    "Key terms: 'auditor's report', 'report of sale', 'order ratifying sale', "
    "'excess proceeds', 'surplus funds', 'balance of proceeds'. "
    "Always call the report_surplus_analysis tool with your findings."
)


class DocketAgent(BaseAgent):
    task_type = "docket_analysis"

    def __init__(self) -> None:
        super().__init__()
        self._client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a case docket with Claude Haiku and seed skip_trace if surplus found.

        Args:
            task: agent_tasks row; payload has case_number, docket_text, county, state.

        Returns:
            {'has_surplus': bool, 'surplus_amount': float|None, 'confidence': str,
             'tokens_used': int, 'tasks_seeded': int}
        """
        payload = task.get("payload", {})
        case_number = payload.get("case_number", "")
        docket_text = payload.get("docket_text", "")
        county = payload.get("county", "")
        state = payload.get("state", "MD")

        if not docket_text.strip():
            logger.warning(f"Empty docket text for {case_number} — marking no surplus")
            return {"has_surplus": False, "tokens_used": 0, "tasks_seeded": 0}

        logger.info(f"DocketAgent analyzing {case_number} ({len(docket_text)} chars)")

        analysis, tokens_used = await self._analyze_docket(docket_text, case_number)

        if analysis is None:
            return {"has_surplus": False, "tokens_used": tokens_used, "tasks_seeded": 0}

        tasks_seeded = 0

        if analysis.has_surplus and analysis.confidence != "low":
            # Update surplus_cases with confirmed surplus amount
            await _update_case_surplus(
                case_number=case_number,
                surplus_amount=analysis.surplus_amount,
                confidence=analysis.confidence,
            )

            # Only skip-trace if surplus clears the minimum threshold
            if (analysis.surplus_amount or 0) >= MIN_SURPLUS or analysis.surplus_amount is None:
                case_id = await _get_case_id(case_number)
                if case_id:
                    task_key = f"skip_trace:{case_number}"
                    seeded = await q.seed_task(
                        task_type="skip_trace",
                        payload={"case_id": case_id, "case_number": case_number},
                        state=state,
                        county=county,
                        task_key=task_key,
                    )
                    if seeded:
                        tasks_seeded += 1
                        logger.success(
                            f"Surplus confirmed: {case_number} | "
                            f"amount=${analysis.surplus_amount:,.0f} | "
                            f"confidence={analysis.confidence}"
                        )
        else:
            logger.debug(
                f"No surplus: {case_number} | confidence={analysis.confidence} | "
                f"evidence={analysis.evidence[:80]}"
            )

        return {
            "has_surplus": analysis.has_surplus,
            "surplus_amount": analysis.surplus_amount,
            "confidence": analysis.confidence,
            "evidence": analysis.evidence,
            "tokens_used": tokens_used,
            "tasks_seeded": tasks_seeded,
        }

    async def _analyze_docket(
        self,
        docket_text: str,
        case_number: str,
    ) -> tuple[DocketAnalysisResult | None, int]:
        """
        Call Claude Haiku with forced tool use to get structured surplus analysis.

        Args:
            docket_text: Raw docket text from the court record.
            case_number: For logging.

        Returns:
            (DocketAnalysisResult | None, tokens_used)
        """
        # Truncate extremely long dockets to avoid token waste
        truncated = docket_text[:8000]
        if len(docket_text) > 8000:
            logger.debug(f"Docket truncated from {len(docket_text)} to 8000 chars for {case_number}")

        try:
            response = await self._client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                tools=[SURPLUS_TOOL],
                tool_choice={"type": "tool", "name": "report_surplus_analysis"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Analyze this Maryland foreclosure docket for case {case_number}. "
                            f"Does it contain evidence of surplus funds?\n\nDOCKET:\n{truncated}"
                        ),
                    }
                ],
            )

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Extract the tool_use block — tool_choice forces exactly one
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_surplus_analysis":
                    inp = block.input
                    return (
                        DocketAnalysisResult(
                            has_surplus=inp["has_surplus"],
                            surplus_amount=inp.get("surplus_amount"),
                            confidence=inp["confidence"],
                            evidence=inp["evidence"],
                        ),
                        tokens_used,
                    )

            logger.warning(f"No tool_use block in Haiku response for {case_number}")
            return None, tokens_used

        except anthropic.APIStatusError as e:
            logger.error(f"Anthropic API error for {case_number}: {e.status_code} — {e.message}")
            return None, 0
        except anthropic.APIConnectionError as e:
            logger.error(f"Anthropic connection error for {case_number}: {e}")
            return None, 0
        except Exception as e:
            logger.error(f"Unexpected docket analysis error for {case_number}: {e}")
            return None, 0


async def _update_case_surplus(
    case_number: str,
    surplus_amount: float | None,
    confidence: str,
) -> None:
    """Set surplus_amount on the surplus_cases row. Status stays 'new' until skip-traced."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    update = {"surplus_amount": surplus_amount}
    try:
        db.table("surplus_cases").update(update).eq("case_number", case_number).execute()
    except Exception as e:
        logger.error(f"Failed to update surplus for {case_number}: {e}")


async def _get_case_id(case_number: str) -> str | None:
    """Look up surplus_cases.id by case_number."""
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        result = (
            db.table("surplus_cases")
            .select("id")
            .eq("case_number", case_number)
            .single()
            .execute()
        )
        return str(result.data["id"]) if result.data else None
    except Exception as e:
        logger.error(f"Failed to get case_id for {case_number}: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(DocketAgent().run())
