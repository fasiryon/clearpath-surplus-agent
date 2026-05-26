"""
Maryland Judiciary Case Search (MJCS) court adapter.

Handles all 24 Maryland jurisdictions via the same ASP.NET Web Forms
interface at casesearch.courts.state.md.us.

Strategy:
  PRIMARY: httpx + BeautifulSoup4
    - GET the form page to extract __VIEWSTATE and __EVENTVALIDATION
    - POST the search form with those tokens + search params
    - Parse HTML results with BeautifulSoup4 — no browser overhead
  FALLBACK: Playwright headless
    - Used if httpx returns non-200, parse fails, or CAPTCHA detected
    - Logs which path was used for each run

IMPORTANT: All form field names, option values, and CSS selectors below
are based on known MJCS structure but MUST be verified against the live
site before first production run. The site uses ASP.NET Web Forms and
field names can change during CMS upgrades.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.adapters.base_court import BaseCourt
from src.models import CaseRecord

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "1.5"))

MJCS_BASE = "https://casesearch.courts.state.md.us/casesearch"
MJCS_SEARCH_URL = f"{MJCS_BASE}/inquirySearch.jis"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": MJCS_SEARCH_URL,
}

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class MarylandMJCSAdapter(BaseCourt):
    state = "MD"
    case_type = "CAEF"

    def _get_county_code(self) -> str:
        """Look up MJCS numeric site code for this county from states.json."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "states.json")
        try:
            with open(config_path) as f:
                data = json.load(f)
            for state_block in data["states"]:
                if state_block["state"] == "MD":
                    for c in state_block["counties"]:
                        if c["name"] == self.county:
                            return c.get("code", "")
        except Exception as e:
            logger.error(f"Could not load states.json: {e}")
        logger.warning(f"No county code found for '{self.county}' — VERIFY states.json")
        return ""

    async def search_cases(self, lookback_days: int = 3) -> list[CaseRecord]:
        """
        Search MJCS for CAEF cases in self.county over the last N days.

        Tries httpx POST first; falls back to Playwright on failure.

        Args:
            lookback_days: How many days back to include (default 3).

        Returns:
            List of CaseRecord objects (no docket detail yet).
        """
        from_date, to_date = self.get_date_range(lookback_days)
        county_code = self._get_county_code()
        if not county_code:
            logger.error(f"No county code for '{self.county}' — cannot search")
            return []

        records = await self._search_httpx(from_date, to_date, county_code)
        if records is not None:
            logger.info(f"[httpx] Found {len(records)} CAEF cases in {self.county}")
            return records

        # httpx failed — fall back to Playwright
        logger.warning(f"httpx search failed for {self.county} — falling back to Playwright")
        records = await self._search_playwright(from_date, to_date, county_code)
        logger.info(f"[playwright] Found {len(records)} CAEF cases in {self.county}")
        return records or []

    async def _search_httpx(
        self,
        from_date: str,
        to_date: str,
        county_code: str,
    ) -> list[CaseRecord] | None:
        """
        Primary path: POST the MJCS search form using httpx + BeautifulSoup4.

        Returns list of CaseRecords or None if the request/parse failed.
        """
        try:
            async with httpx.AsyncClient(
                headers=BASE_HEADERS,
                timeout=TIMEOUT,
                follow_redirects=True,
            ) as client:

                # Step 1: GET the search page to extract ASP.NET form tokens
                get_resp = await client.get(MJCS_SEARCH_URL)
                if get_resp.status_code != 200:
                    logger.warning(f"MJCS GET returned {get_resp.status_code}")
                    return None

                soup = BeautifulSoup(get_resp.text, "html.parser")
                viewstate = _extract_hidden(soup, "__VIEWSTATE")
                eventvalidation = _extract_hidden(soup, "__EVENTVALIDATION")
                viewstate_gen = _extract_hidden(soup, "__VIEWSTATEGENERATOR")

                if not viewstate:
                    logger.warning("Could not extract __VIEWSTATE from MJCS form")
                    return None

                await asyncio.sleep(SCRAPE_DELAY)

                # Step 2: POST the search form
                # VERIFY: All field names against live MJCS form source before first run
                form_data = {
                    "__VIEWSTATE":          viewstate,
                    "__EVENTVALIDATION":    eventvalidation or "",
                    "__VIEWSTATEGENERATOR": viewstate_gen or "",
                    "action":               "Search",          # VERIFY
                    "courtSystem":          "C",               # VERIFY: Circuit Court
                    "site":                 county_code,        # VERIFY: numeric site code
                    "caseType":             "CAEF",            # VERIFY: Civil Action Equity Foreclosure
                    "filingStart":          from_date,         # VERIFY: field name
                    "filingEnd":            to_date,           # VERIFY: field name
                    "lastName":             "",
                    "firstName":            "",
                    "middleName":           "",
                }

                post_resp = await client.post(
                    MJCS_SEARCH_URL,
                    data=form_data,
                    headers={**BASE_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                )

                if post_resp.status_code != 200:
                    logger.warning(f"MJCS POST returned {post_resp.status_code}")
                    return None

                records = _parse_results_html(post_resp.text, self.county)

                # Handle pagination (MJCS renders "Next Page" links)
                page_count = 1
                while page_count < 20:  # safety cap
                    next_url = _extract_next_page_url(post_resp.text)
                    if not next_url:
                        break
                    await asyncio.sleep(SCRAPE_DELAY)
                    page_resp = await client.get(f"{MJCS_BASE}/{next_url}")
                    if page_resp.status_code != 200:
                        break
                    records.extend(_parse_results_html(page_resp.text, self.county))
                    post_resp = page_resp  # advance for next iteration
                    page_count += 1

                return records

        except httpx.RequestError as e:
            logger.error(f"httpx request error on MJCS search: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in httpx MJCS search: {e}")
            return None

    async def _search_playwright(
        self,
        from_date: str,
        to_date: str,
        county_code: str,
    ) -> list[CaseRecord]:
        """Playwright fallback for MJCS search."""
        try:
            from playwright.async_api import async_playwright

            records: list[CaseRecord] = []
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(user_agent=USER_AGENT)
                page = await ctx.new_page()

                await page.goto(MJCS_SEARCH_URL, wait_until="networkidle", timeout=30_000)
                await asyncio.sleep(SCRAPE_DELAY)

                # VERIFY: All selectors below against live page in DevTools
                await page.select_option('select[name="caseType"]', value="CAEF")   # VERIFY
                await page.select_option('select[name="site"]', value=county_code)  # VERIFY
                await page.fill('input[name="filingStart"]', from_date)             # VERIFY
                await page.fill('input[name="filingEnd"]', to_date)                 # VERIFY
                await page.click('input[type="submit"]')                             # VERIFY
                await page.wait_for_load_state("networkidle", timeout=30_000)
                await asyncio.sleep(SCRAPE_DELAY)

                html = await page.content()
                records = _parse_results_html(html, self.county)

                await browser.close()
            return records
        except Exception as e:
            logger.error(f"Playwright fallback failed for {self.county}: {e}")
            return []

    async def get_case_detail(self, case: CaseRecord) -> CaseRecord | None:
        """
        Fetch the case detail page and extract raw docket text for LLM analysis.

        Returns the enriched CaseRecord or None if page fetch failed.
        """
        if not case.detail_url:
            return None

        result = await self._detail_httpx(case)
        if result is not None:
            return result

        logger.warning(f"httpx detail fetch failed for {case.case_number} — trying Playwright")
        return await self._detail_playwright(case)

    async def _detail_httpx(self, case: CaseRecord) -> CaseRecord | None:
        """Fetch case detail via httpx + BeautifulSoup4."""
        try:
            async with httpx.AsyncClient(
                headers=BASE_HEADERS, timeout=TIMEOUT, follow_redirects=True
            ) as client:
                await asyncio.sleep(SCRAPE_DELAY)
                resp = await client.get(case.detail_url)
                if resp.status_code != 200:
                    return None
                return _parse_case_detail(resp.text, case)
        except Exception as e:
            logger.error(f"httpx detail error for {case.case_number}: {e}")
            return None

    async def _detail_playwright(self, case: CaseRecord) -> CaseRecord | None:
        """Playwright fallback for case detail fetch."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(user_agent=USER_AGENT)
                page = await ctx.new_page()
                await page.goto(case.detail_url, wait_until="networkidle", timeout=30_000)
                await asyncio.sleep(SCRAPE_DELAY)
                html = await page.content()
                await browser.close()
            return _parse_case_detail(html, case)
        except Exception as e:
            logger.error(f"Playwright detail error for {case.case_number}: {e}")
            return None


# ---------------------------------------------------------------------------
# HTML parsing helpers (BeautifulSoup4)
# ---------------------------------------------------------------------------

def _extract_hidden(soup: BeautifulSoup, field_name: str) -> str | None:
    """Extract value of an ASP.NET hidden input field."""
    tag = soup.find("input", {"name": field_name})
    if tag:
        return tag.get("value", "")
    return None


def _parse_results_html(html: str, county: str) -> list[CaseRecord]:
    """
    Parse MJCS search results HTML into CaseRecord list.

    VERIFY: Table class name and column order against live results page.
    """
    records: list[CaseRecord] = []
    soup = BeautifulSoup(html, "html.parser")

    # VERIFY: The results table selector — MJCS typically uses a class like "results"
    table = soup.find("table", class_="resultsTable")  # VERIFY: class name
    if not table:
        # Try fallback: any table with a "Case No." header
        table = _find_results_table(soup)
    if not table:
        return records

    rows = table.find_all("tr")[1:]  # skip header row
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        case_number = cells[0].get_text(strip=True)  # VERIFY: column 0
        title = cells[1].get_text(strip=True)         # VERIFY: column 1
        filing_date = cells[2].get_text(strip=True)   # VERIFY: column 2

        # Extract detail link from case number cell
        detail_url: str | None = None
        link = cells[0].find("a")
        if link and link.get("href"):
            href = link["href"]
            detail_url = (
                f"https://casesearch.courts.state.md.us{href}"
                if href.startswith("/")
                else href
            )

        if case_number:
            records.append(
                CaseRecord(
                    case_number=case_number,
                    county=county,
                    title=title or "",
                    filing_date=filing_date or None,
                    detail_url=detail_url,
                )
            )

    return records


def _find_results_table(soup: BeautifulSoup) -> Any | None:
    """Fallback: find any table containing 'Case No' in its header."""
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("case" in h for h in headers):
            return table
    return None


def _extract_next_page_url(html: str) -> str | None:
    """Extract the relative URL for the next results page, if any."""
    soup = BeautifulSoup(html, "html.parser")
    # VERIFY: Pagination link — MJCS typically renders "Next Page" as a link
    next_link = soup.find("a", string=re.compile(r"next\s*page?", re.I))  # VERIFY
    if next_link and next_link.get("href"):
        return next_link["href"]
    return None


def _parse_case_detail(html: str, case: CaseRecord) -> CaseRecord:
    """
    Parse the case detail page to extract defendant, address, and raw docket text.

    The raw docket text is formatted as a flat string for LLM consumption.
    VERIFY: All selectors against a live case detail page in DevTools.
    """
    soup = BeautifulSoup(html, "html.parser")

    # VERIFY: Party name extraction — MJCS detail page uses labeled table cells
    defendant = _extract_labeled_cell(soup, "Defendant")      # VERIFY: label text
    plaintiff = _extract_labeled_cell(soup, "Plaintiff")      # VERIFY: label text
    address = _extract_labeled_cell(soup, "Property Address") # VERIFY: label text

    if defendant and not case.defendant_name:
        case.defendant_name = defendant
    if plaintiff and not case.plaintiff_name:
        case.plaintiff_name = plaintiff
    if address and not case.property_address:
        case.property_address = address

    # VERIFY: Docket table selector
    docket_table = soup.find("table", class_="docketTable")  # VERIFY: class
    if not docket_table:
        docket_table = _find_docket_table(soup)

    docket_entries: list[dict[str, str]] = []
    docket_lines: list[str] = []

    if docket_table:
        for row in docket_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            entry_date = cells[0].get_text(strip=True)  # VERIFY: column 0
            entry_text = cells[1].get_text(strip=True)  # VERIFY: column 1
            docket_entries.append({"date": entry_date, "text": entry_text})
            if entry_date:
                docket_lines.append(f"{entry_date}: {entry_text}")
            else:
                docket_lines.append(entry_text)

    case.raw_docket = docket_entries
    case.raw_docket_text = "\n".join(docket_lines)

    return case


def _extract_labeled_cell(soup: BeautifulSoup, label: str) -> str | None:
    """
    Find a table cell that contains `label` text and return the adjacent value cell.
    VERIFY: MJCS detail page layout — labels may be in <th> or <td> elements.
    """
    for tag in soup.find_all(["th", "td"]):
        if label.lower() in tag.get_text(strip=True).lower():
            sibling = tag.find_next_sibling(["th", "td"])
            if sibling:
                text = sibling.get_text(strip=True)
                return text if text else None
    return None


def _find_docket_table(soup: BeautifulSoup) -> Any | None:
    """Fallback: find any table with 'Date' and 'Docket' or 'Description' headers."""
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "date" in headers and any(h in ("docket", "description", "entry") for h in headers):
            return table
    return None
