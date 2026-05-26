"""
Maryland Judiciary Case Search (MJCS) scraper for CAEF foreclosure cases.

Searches for Civil Action–Equity–Foreclosure cases by county and date range,
identifies cases with surplus funds, and upserts results to Supabase.

IMPORTANT: All CSS selectors and form field names below are based on the known
MJCS site structure but MUST be verified against the live site before the
first production run. The site periodically changes its form field names.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv
from loguru import logger
from playwright.async_api import Browser, Page, async_playwright
from supabase import create_client

from models import CaseRecord, SurplusResult

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "1.5"))

MJCS_BASE_URL = "https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis"

SURPLUS_KEYWORDS = [
    "surplus",
    "auditor's report",
    "auditors report",
    "report of sale",
    "order ratifying sale",
    "ratification of sale",
    "excess proceeds",
    "auditor's account",
    "auditors account",
    "surplus funds",
    "balance of proceeds",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def search_court_cases(
    county: str,
    from_date: date,
    to_date: date,
    page: Page,
) -> list[CaseRecord]:
    """
    Search MJCS for CAEF cases in a county between two dates.

    Args:
        county: County short name matching counties.json (e.g., "Baltimore County").
        from_date: Start date for filing date filter.
        to_date: End date for filing date filter.
        page: Playwright Page object to use.

    Returns:
        List of CaseRecord objects parsed from search results.
    """
    logger.info(f"Searching {county} CAEF cases from {from_date} to {to_date}")

    records: list[CaseRecord] = []

    try:
        # VERIFY: Navigate to the search page and confirm it loads
        await page.goto(MJCS_BASE_URL, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(SCRAPE_DELAY)

        # VERIFY: The search form field names below. Inspect the live page.
        # As of 2024, MJCS uses these field names — confirm they haven't changed.

        # VERIFY: Select "Case Type" dropdown → value for CAEF foreclosure cases
        await page.select_option(
            'select[name="caseType"]',  # VERIFY: field name may be "caseType" or "casetype"
            value="CAEF",
        )

        # VERIFY: County/location select field name and option values
        # Load county mjcs_code from counties.json
        county_code = _get_county_code(county)
        if not county_code:
            logger.error(f"No MJCS code found for county: {county}")
            return []

        await page.select_option(
            'select[name="countyName"]',  # VERIFY: field name
            label=county,  # try by label text first
        )

        # VERIFY: Date fields — "filingStart" and "filingEnd" or similar
        await page.fill(
            'input[name="filingStart"]',  # VERIFY: field name for start date
            from_date.strftime("%m/%d/%Y"),
        )
        await page.fill(
            'input[name="filingEnd"]',  # VERIFY: field name for end date
            to_date.strftime("%m/%d/%Y"),
        )

        # VERIFY: Submit button selector
        await page.click('input[type="submit"]')  # VERIFY: may need a more specific selector
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await asyncio.sleep(SCRAPE_DELAY)

        # Parse the results table
        records = await _parse_results_page(page, county)

        # Handle pagination
        while True:
            next_btn = await page.query_selector(
                'a:has-text("Next")'  # VERIFY: pagination link text/selector
            )
            if not next_btn:
                break
            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=30_000)
            await asyncio.sleep(SCRAPE_DELAY)
            new_records = await _parse_results_page(page, county)
            records.extend(new_records)

    except Exception as e:
        logger.error(f"Error searching cases for {county}: {e}")

    logger.info(f"Found {len(records)} raw CAEF cases in {county}")
    return records


async def _parse_results_page(page: Page, county: str) -> list[CaseRecord]:
    """Parse case rows from the current MJCS results page."""
    records: list[CaseRecord] = []

    try:
        # VERIFY: Results table selector — MJCS renders a <table> with case rows
        rows = await page.query_selector_all(
            "table.resultsTable tr:not(:first-child)"  # VERIFY: table class name
        )

        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) < 4:
                continue

            case_number = (await cells[0].inner_text()).strip()  # VERIFY: column order
            title = (await cells[1].inner_text()).strip()         # VERIFY: column order
            filing_date = (await cells[2].inner_text()).strip()   # VERIFY: column order

            # VERIFY: Link to case detail page is usually on case number cell
            link_el = await cells[0].query_selector("a")
            detail_url: str | None = None
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    detail_url = (
                        f"https://casesearch.courts.state.md.us{href}"
                        if href.startswith("/")
                        else href
                    )

            records.append(
                CaseRecord(
                    case_number=case_number,
                    county=county,
                    title=title,
                    filing_date=filing_date or None,
                    detail_url=detail_url,
                )
            )
    except Exception as e:
        logger.error(f"Error parsing results page: {e}")

    return records


async def detect_surplus(
    case: CaseRecord,
    page: Page,
) -> SurplusResult | None:
    """
    Fetch a case detail page and scan the docket for surplus indicators.

    Args:
        case: CaseRecord with a valid detail_url.
        page: Playwright Page to use.

    Returns:
        SurplusResult if surplus keywords found, None otherwise.
    """
    if not case.detail_url:
        return None

    try:
        await page.goto(case.detail_url, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(SCRAPE_DELAY)

        # VERIFY: The docket entries section selector
        docket_rows = await page.query_selector_all(
            "table.docketTable tr:not(:first-child)"  # VERIFY: table class
        )

        docket_entries: list[dict[str, Any]] = []
        keywords_found: list[str] = []

        for row in docket_rows:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                continue

            entry_date = (await cells[0].inner_text()).strip()  # VERIFY: column order
            entry_text = (await cells[1].inner_text()).strip()  # VERIFY: column order
            entry_lower = entry_text.lower()

            docket_entries.append({"date": entry_date, "text": entry_text})

            for kw in SURPLUS_KEYWORDS:
                if kw in entry_lower and kw not in keywords_found:
                    keywords_found.append(kw)

        if not keywords_found:
            return None

        # Attempt to parse surplus dollar amount from docket text
        surplus_amount = _extract_surplus_amount(docket_entries)

        # Also grab defendant name from case header if not already set
        defendant = await _extract_defendant(page)
        plaintiff = await _extract_plaintiff(page)
        property_address = await _extract_property_address(page)

        if defendant:
            case.defendant_name = defendant
        if plaintiff:
            case.plaintiff_name = plaintiff
        if property_address:
            case.property_address = property_address

        case.surplus_amount = surplus_amount
        case.raw_docket = docket_entries

        confidence = "high" if surplus_amount else ("medium" if len(keywords_found) >= 2 else "low")

        return SurplusResult(
            case_number=case.case_number,
            surplus_amount=surplus_amount,
            surplus_keywords_found=keywords_found,
            docket_entries=docket_entries,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Error detecting surplus for {case.case_number}: {e}")
        return None


def _extract_surplus_amount(docket_entries: list[dict[str, Any]]) -> float | None:
    """Parse dollar amount from docket entry text using regex."""
    # Match patterns like "$12,345.67" or "12345.67" near surplus keywords
    dollar_pattern = re.compile(r"\$[\d,]+(?:\.\d{2})?")

    for entry in reversed(docket_entries):  # Most recent entries first
        text = entry.get("text", "").lower()
        if any(kw in text for kw in ["surplus", "excess proceeds", "auditor"]):
            matches = dollar_pattern.findall(entry.get("text", ""))
            if matches:
                # Take the largest dollar value found in the entry
                amounts = []
                for m in matches:
                    try:
                        amounts.append(float(m.replace("$", "").replace(",", "")))
                    except ValueError:
                        continue
                if amounts:
                    return max(amounts)

    return None


async def _extract_defendant(page: Page) -> str | None:
    """Extract defendant (original owner) name from case header."""
    try:
        # VERIFY: Defendant label/value selector on case detail page
        el = await page.query_selector(
            "td:has-text('Defendant') + td"  # VERIFY: selector
        )
        if el:
            return (await el.inner_text()).strip() or None
    except Exception:
        pass
    return None


async def _extract_plaintiff(page: Page) -> str | None:
    """Extract plaintiff (bank) name from case header."""
    try:
        # VERIFY: Plaintiff label/value selector
        el = await page.query_selector(
            "td:has-text('Plaintiff') + td"  # VERIFY: selector
        )
        if el:
            return (await el.inner_text()).strip() or None
    except Exception:
        pass
    return None


async def _extract_property_address(page: Page) -> str | None:
    """Extract property address from case header or docket."""
    try:
        # VERIFY: Address field selector — may be in case description or a dedicated cell
        el = await page.query_selector(
            "td:has-text('Address') + td"  # VERIFY: selector
        )
        if el:
            text = (await el.inner_text()).strip()
            if text:
                return text
    except Exception:
        pass
    return None


def _get_county_code(county_name: str) -> str | None:
    """Look up MJCS county code from counties.json."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "counties.json")
    try:
        with open(config_path) as f:
            data = json.load(f)
        for c in data["maryland"]["counties"]:
            if c["short"] == county_name or c["name"] == county_name:
                return c["mjcs_code"]
    except Exception as e:
        logger.error(f"Could not load county config: {e}")
    return None


async def upsert_case(case: CaseRecord) -> None:
    """
    Insert or update a surplus case in Supabase.

    Args:
        case: CaseRecord to persist.
    """
    db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    payload = {
        "case_number": case.case_number,
        "county": case.county,
        "property_address": case.property_address,
        "defendant_name": case.defendant_name,
        "plaintiff_name": case.plaintiff_name,
        "filing_date": case.filing_date,
        "sale_date": case.sale_date,
        "surplus_amount": case.surplus_amount,
        "scrape_source": case.scrape_source,
        "raw_docket": case.raw_docket,
        "status": "new",
    }

    try:
        result = (
            db.table("surplus_cases")
            .upsert(payload, on_conflict="case_number")
            .execute()
        )
        logger.debug(f"Upserted case {case.case_number}: {result.data}")
    except Exception as e:
        logger.error(f"Failed to upsert case {case.case_number}: {e}")


async def run_scraper(county: str, lookback_days: int = 3) -> list[CaseRecord]:
    """
    Main entry point: scrape CAEF cases, detect surplus, upsert to Supabase.

    Args:
        county: County name to scrape (matches counties.json "short" field).
        lookback_days: How many days back to search (default 3 for daily runs).

    Returns:
        List of CaseRecords where surplus was detected.
    """
    to_date = date.today()
    from_date = to_date - timedelta(days=lookback_days)
    surplus_cases: list[CaseRecord] = []

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()

        try:
            cases = await search_court_cases(county, from_date, to_date, page)
            logger.info(f"Processing {len(cases)} cases for surplus detection")

            for case in cases:
                result = await detect_surplus(case, page)
                if result:
                    logger.info(
                        f"SURPLUS DETECTED: {case.case_number} | "
                        f"amount={result.surplus_amount} | "
                        f"confidence={result.confidence} | "
                        f"keywords={result.surplus_keywords_found}"
                    )
                    await upsert_case(case)
                    surplus_cases.append(case)
                else:
                    # Still upsert as closed_no_surplus to avoid re-processing
                    case_no_surplus = CaseRecord(**case.model_dump())
                    # We don't upsert no-surplus cases to keep DB clean
                    # Only insert confirmed surplus cases

        finally:
            await browser.close()

    logger.info(
        f"Scraper complete: {len(surplus_cases)} surplus cases found in {county}"
    )
    return surplus_cases


if __name__ == "__main__":
    import sys

    county = os.getenv("ACTIVE_COUNTY", "Baltimore County")
    lookback = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "3"))
    asyncio.run(run_scraper(county, lookback))
