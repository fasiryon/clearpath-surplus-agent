"""
Maryland Judiciary Case Search (MJCS) court adapter — Odyssey JS SPA.

The portal migrated from ASP.NET Web Forms (.jis) to a React-based SPA
launched 2024-02-05 at casesearch.courts.state.md.us/casesearch/inquiry-search.

httpx CANNOT work — the portal is JavaScript-rendered. Playwright is the
only viable approach. There is no httpx fallback; this class is Playwright-only.

Flow:
  1. Navigate to inquiry-search (JS SPA loads)
  2. Accept the "I agree" disclaimer (checkbox + button)
  3. Click "Advanced Search" tab/link
  4. Select Circuit Court, county, CAEF case type, and date range
  5. Submit — page navigates to inquiry-search-results
  6. Parse case rows; follow "Next" pagination up to 20 pages
  7. For each case, navigate to case-detail-page?caseId=... and extract docket

SELECTORS:
  All selectors use aria roles and text content rather than CSS class names
  because React build hashes change on every deployment. If the portal
  restructures its layout, update the helper functions below — the main
  search_cases() and get_case_detail() methods should not need changes.

  Add "# VERIFIED [YYYY-MM-DD]" to any selector confirmed against DevTools.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from loguru import logger

from src.adapters.base_court import BaseCourt
from src.models import CaseRecord

SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "1.5"))

MJCS_BASE = "https://casesearch.courts.state.md.us/casesearch"
MJCS_SEARCH_URL = f"{MJCS_BASE}/inquiry-search"
MJCS_RESULTS_URL = f"{MJCS_BASE}/inquiry-search-results"
MJCS_DETAIL_URL = f"{MJCS_BASE}/case-detail-page"

# Realistic Chrome UA required — Cloudflare blocks generic/Python UAs
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 45_000
NAV_TIMEOUT_MS = 60_000
MAX_RESULT_PAGES = 20


class MarylandMJCSAdapter(BaseCourt):
    state = "MD"
    case_type = "CAEF"

    async def search_cases(self, lookback_days: int = 90) -> list[CaseRecord]:
        """
        Search MJCS for CAEF cases in self.county over the last N days.
        Returns list of CaseRecord objects (docket text NOT yet populated).
        """
        from_date, to_date = self.get_date_range(lookback_days)
        logger.info(f"MJCS search: {self.county} CAEF {from_date}–{to_date} (Playwright)")

        try:
            from playwright.async_api import async_playwright

            records: list[CaseRecord] = []
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    slow_mo=500,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                ctx = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                page = await ctx.new_page()
                page.set_default_timeout(PAGE_TIMEOUT_MS)

                await page.goto(MJCS_SEARCH_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                await asyncio.sleep(SCRAPE_DELAY)

                if await _is_captcha_page(page):
                    logger.error("MJCS returned CAPTCHA challenge — cannot proceed headless")
                    await browser.close()
                    return []

                await _accept_disclaimer(page)
                await _open_advanced_search(page)
                await _fill_search_form(page, self.county, from_date, to_date)
                await _submit_search(page)

                records = await _collect_all_result_pages(page, self.county)
                await browser.close()

            logger.info(f"[playwright] Found {len(records)} CAEF cases in {self.county}")
            return records

        except Exception as e:
            logger.error(f"Playwright search failed for {self.county}: {e}")
            return []

    async def get_case_detail(self, case: CaseRecord) -> CaseRecord | None:
        """
        Fetch case detail page and populate case.raw_docket_text for LLM analysis.
        Returns the enriched CaseRecord or None if the page cannot be fetched.
        """
        url = case.detail_url or f"{MJCS_DETAIL_URL}?caseId={case.case_number}"
        logger.debug(f"Fetching detail: {case.case_number} → {url}")

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    slow_mo=300,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                ctx = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
                )
                page = await ctx.new_page()
                page.set_default_timeout(PAGE_TIMEOUT_MS)

                await page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
                await asyncio.sleep(SCRAPE_DELAY)

                enriched = await _extract_case_detail(page, case)
                await browser.close()

            return enriched
        except Exception as e:
            logger.error(f"Detail fetch failed for {case.case_number}: {e}")
            return None


# ---------------------------------------------------------------------------
# Disclaimer handling
# ---------------------------------------------------------------------------

async def _accept_disclaimer(page: Any) -> None:
    """
    The MJCS portal shows a legal disclaimer that requires acceptance before
    any search is possible. The user must check "I agree" and click Continue.

    Selector strategy: try aria-role then text content, log which path worked.
    """
    try:
        # Check if we're already past the disclaimer (search form visible)
        search_visible = await page.get_by_role("button", name=re.compile(r"search", re.I)).count()
        if search_visible > 0:
            logger.debug("Disclaimer already accepted (search form visible)")
            return

        # Strategy 1: check the "I agree" checkbox (common on legacy & new portal)
        checkboxes = page.get_by_role("checkbox")
        if await checkboxes.count() > 0:
            await checkboxes.first.check()
            logger.debug("Checked disclaimer checkbox")
            await asyncio.sleep(0.5)

        # Strategy 2: click the acceptance button/link
        for btn_text in ("I Agree", "I agree", "Accept", "Continue", "Submit"):
            btn = page.get_by_role("button", name=re.compile(btn_text, re.I))
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_load_state("networkidle", timeout=30_000)
                logger.debug(f"Clicked disclaimer button: '{btn_text}'")
                await asyncio.sleep(SCRAPE_DELAY)
                return

        # Strategy 3: input[type=submit] with agree/continue value
        submit = page.locator('input[type="submit"]')
        if await submit.count() > 0:
            await submit.first.click()
            await page.wait_for_load_state("networkidle", timeout=30_000)
            await asyncio.sleep(SCRAPE_DELAY)
            logger.debug("Clicked disclaimer via input[type=submit]")
            return

        logger.debug("No disclaimer found — assuming already accepted or not present")

    except Exception as e:
        logger.warning(f"Disclaimer handling error (non-fatal, continuing): {e}")


# ---------------------------------------------------------------------------
# Navigate to Advanced Search
# ---------------------------------------------------------------------------

async def _open_advanced_search(page: Any) -> None:
    """
    The portal has at least two search modes: Name Search and Advanced Search.
    CAEF date-range searches require Advanced Search.

    Selector note: The tab might be a <button role="tab">, a plain <a>, or a
    <div> with text "Advanced Search". Try each.
    """
    try:
        # Strategy 1: tab role
        tab = page.get_by_role("tab", name=re.compile(r"advanced", re.I))
        if await tab.count() > 0:
            await tab.first.click()
            await asyncio.sleep(0.8)
            logger.debug("Clicked Advanced Search tab (role=tab)")
            return

        # Strategy 2: button or link with "Advanced" in text
        for locator in [
            page.get_by_role("button", name=re.compile(r"advanced search", re.I)),
            page.get_by_role("link", name=re.compile(r"advanced search", re.I)),
            page.get_by_text("Advanced Search", exact=True),
        ]:
            if await locator.count() > 0:
                await locator.first.click()
                await asyncio.sleep(0.8)
                logger.debug("Clicked Advanced Search (text/button/link)")
                return

        logger.debug("Advanced Search element not found — form may already be in advanced mode")

    except Exception as e:
        logger.warning(f"Advanced search navigation error (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Fill search form
# ---------------------------------------------------------------------------

async def _fill_search_form(
    page: Any,
    county: str,
    from_date: str,
    to_date: str,
) -> None:
    """
    Populate the Advanced Search form with circuit court, county, CAEF, dates.

    The portal may use native <select> elements or React custom dropdowns.
    _set_dropdown() tries both. If a field can't be set, it logs a warning
    and continues — partial form fill is better than no submission.
    """
    # Court System = Circuit Court
    await _set_dropdown(page, label="Court System", options=["Circuit Court", "Circuit", "C"])

    await asyncio.sleep(0.4)

    # County / Location
    await _set_dropdown(page, label="County", options=[county])

    await asyncio.sleep(0.4)

    # Case Type — CAEF = Civil Action Equity Foreclosure
    await _set_dropdown(
        page,
        label="Case Type",
        options=["CAEF", "Civil Action Equity Foreclosure", "Foreclosure", "Civil Equity"],
    )

    await asyncio.sleep(0.4)

    # Filing date — from
    await _fill_date(page, value=from_date, labels=["Filing Date Start", "Start Date", "From Date", "Date From"])

    # Filing date — to
    await _fill_date(page, value=to_date, labels=["Filing Date End", "End Date", "To Date", "Date To"])

    logger.debug(f"Form filled: {county} CAEF {from_date}–{to_date}")


async def _set_dropdown(page: Any, label: str, options: list[str]) -> None:
    """
    Set a dropdown/select field. Tries:
      1. Native <select> via get_by_label → select_option
      2. React combobox → click → select option by text
      3. Fallback: locator('select') → select_option if only one select visible
    """
    label_re = re.compile(label, re.I)

    # --- Native select ---
    try:
        sel = page.get_by_label(label_re)
        if await sel.count() > 0:
            for opt in options:
                try:
                    await sel.select_option(label=re.compile(opt, re.I))
                    logger.debug(f"  Set '{label}' = '{opt}' (native select, label match)")
                    return
                except Exception:
                    pass
                try:
                    await sel.select_option(value=opt)
                    logger.debug(f"  Set '{label}' = '{opt}' (native select, value match)")
                    return
                except Exception:
                    pass
    except Exception:
        pass

    # --- React combobox / custom select ---
    try:
        combo = page.get_by_role("combobox", name=label_re)
        if await combo.count() > 0:
            await combo.first.click()
            await asyncio.sleep(0.4)
            for opt in options:
                option_loc = page.get_by_role("option", name=re.compile(opt, re.I))
                if await option_loc.count() > 0:
                    await option_loc.first.click()
                    logger.debug(f"  Set '{label}' = '{opt}' (combobox)")
                    return
            # Close the dropdown if nothing matched
            await page.keyboard.press("Escape")
    except Exception:
        pass

    # --- Fallback: look for any listbox open on the page ---
    try:
        listbox = page.get_by_role("listbox")
        if await listbox.count() > 0:
            for opt in options:
                option_loc = listbox.get_by_role("option", name=re.compile(opt, re.I))
                if await option_loc.count() > 0:
                    await option_loc.first.click()
                    logger.debug(f"  Set '{label}' = '{opt}' (listbox fallback)")
                    return
    except Exception:
        pass

    logger.warning(f"  Could not set dropdown '{label}' — tried options: {options}")


async def _fill_date(page: Any, value: str, labels: list[str]) -> None:
    """Fill a date input field using aria-label or placeholder text."""
    for lbl in labels:
        try:
            field = page.get_by_label(re.compile(lbl, re.I))
            if await field.count() > 0:
                await field.first.click()
                await field.first.clear()
                await field.first.fill(value)
                logger.debug(f"  Filled date '{lbl}' = {value}")
                return
        except Exception:
            pass

    # Fallback: placeholder-based
    for lbl in labels:
        try:
            field = page.get_by_placeholder(re.compile(lbl, re.I))
            if await field.count() > 0:
                await field.first.click()
                await field.first.clear()
                await field.first.fill(value)
                logger.debug(f"  Filled date (placeholder) '{lbl}' = {value}")
                return
        except Exception:
            pass

    logger.warning(f"  Could not fill date field — tried labels: {labels}")


# ---------------------------------------------------------------------------
# Submit and collect results
# ---------------------------------------------------------------------------

async def _submit_search(page: Any) -> None:
    """Click the Search submit button and wait for results to load."""
    try:
        # Try role-based button first
        for btn_name in ("Search", "Submit", "Find"):
            btn = page.get_by_role("button", name=re.compile(f"^{btn_name}$", re.I))
            if await btn.count() > 0:
                await btn.first.click()
                logger.debug(f"Clicked submit button: '{btn_name}'")
                break
        else:
            # Fallback: input[type=submit]
            submit = page.locator('input[type="submit"]')
            if await submit.count() > 0:
                await submit.first.click()
                logger.debug("Clicked input[type=submit]")
            else:
                logger.warning("No submit button found — search may not have fired")
                return

        # Wait for navigation to results page or for results to render in-place
        try:
            await page.wait_for_url(
                f"**inquiry-search-results**",
                timeout=30_000,
            )
        except Exception:
            # Some builds render results in-place without URL change
            await page.wait_for_load_state("networkidle", timeout=30_000)

        await asyncio.sleep(SCRAPE_DELAY)
        logger.debug(f"Results page loaded: {page.url}")

    except Exception as e:
        logger.error(f"Search submission failed: {e}")
        raise


async def _collect_all_result_pages(page: Any, county: str) -> list[CaseRecord]:
    """
    Parse the results table and follow pagination until no more pages.
    Returns all CaseRecord objects across all pages (max MAX_RESULT_PAGES).
    """
    all_records: list[CaseRecord] = []
    page_num = 1

    while page_num <= MAX_RESULT_PAGES:
        records = await _parse_result_rows(page, county)
        all_records.extend(records)
        logger.debug(f"  Results page {page_num}: {len(records)} rows (total {len(all_records)})")

        if not records:
            break  # empty page = done

        # Look for a "Next" pagination button/link
        next_btn = await _find_next_page(page)
        if next_btn is None:
            break

        await next_btn.click()
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await asyncio.sleep(SCRAPE_DELAY)
        page_num += 1

    return all_records


async def _parse_result_rows(page: Any, county: str) -> list[CaseRecord]:
    """
    Extract CaseRecord objects from the results table on the current page.

    The new portal renders results in an HTML table. Column order is typically:
      Case Number | Title/Parties | Court | Filing Date
    The case number cell contains a link to the detail page.

    If the table structure changes, update the column index constants below.
    """
    records: list[CaseRecord] = []

    try:
        # Strategy 1: standard table rows
        rows = page.locator("table tbody tr")
        row_count = await rows.count()

        if row_count == 0:
            # Strategy 2: role=row (ARIA grid)
            rows = page.get_by_role("row")
            row_count = await rows.count()
            # Skip header row (index 0)
            if row_count > 1:
                rows = rows.nth(1)  # Can't slice easily; handled below
                row_count = await page.get_by_role("row").count() - 1

        if row_count == 0:
            # No rows found — check if "No results" message is shown
            no_results = page.get_by_text(re.compile(r"no\s+results|no\s+cases\s+found", re.I))
            if await no_results.count() > 0:
                logger.info("  MJCS returned: No results for this search")
            else:
                logger.warning("  Could not find result rows — selector may need updating")
            return records

        # Parse each row
        all_rows = page.locator("table tbody tr")
        count = await all_rows.count()
        for i in range(count):
            row = all_rows.nth(i)
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count < 2:
                continue

            case_number = (await cells.nth(0).inner_text()).strip()
            if not case_number:
                continue

            # Extract title from cell 1 (or whichever non-empty cell follows)
            title = (await cells.nth(1).inner_text()).strip() if cell_count > 1 else ""

            # Extract filing date — scan cells for MM/DD/YYYY pattern
            filing_date: str | None = None
            for ci in range(cell_count):
                cell_text = (await cells.nth(ci).inner_text()).strip()
                if re.match(r"\d{1,2}/\d{1,2}/\d{4}", cell_text):
                    filing_date = cell_text
                    break

            # Extract detail URL from the link in the case number cell
            detail_url: str | None = None
            link = cells.nth(0).locator("a")
            if await link.count() > 0:
                href = await link.first.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        detail_url = f"https://casesearch.courts.state.md.us{href}"
                    elif href.startswith("http"):
                        detail_url = href
                    else:
                        detail_url = f"{MJCS_BASE}/{href}"

            records.append(
                CaseRecord(
                    case_number=case_number,
                    county=county,
                    title=title,
                    filing_date=filing_date,
                    detail_url=detail_url,
                )
            )

    except Exception as e:
        logger.error(f"Error parsing result rows: {e}")

    return records


async def _find_next_page(page: Any) -> Any | None:
    """
    Return a locator for the "Next" pagination button/link, or None if on the last page.
    The button must be enabled (not aria-disabled and not greyed out).
    """
    try:
        for name_pattern in (r"next\s*(page)?", r">", r"»"):
            btn = page.get_by_role("button", name=re.compile(name_pattern, re.I))
            if await btn.count() > 0:
                disabled = await btn.first.get_attribute("disabled")
                aria_disabled = await btn.first.get_attribute("aria-disabled")
                if disabled is None and aria_disabled != "true":
                    return btn.first

            link = page.get_by_role("link", name=re.compile(name_pattern, re.I))
            if await link.count() > 0:
                return link.first

    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Case detail extraction
# ---------------------------------------------------------------------------

async def _extract_case_detail(page: Any, case: CaseRecord) -> CaseRecord:
    """
    Parse the case detail page to extract defendant name, property address,
    and the full docket entry list as both structured JSON and plain text.

    The plain text (raw_docket_text) is what the LLM docket agent receives.
    Structured entries (raw_docket) are stored in Supabase for reference.
    """
    try:
        # Party information — scan labeled table cells
        for label, attr in [
            ("Defendant", "defendant_name"),
            ("Borrower", "defendant_name"),    # foreclosure cases use "Borrower"
            ("Plaintiff", "plaintiff_name"),
            ("Lender", "plaintiff_name"),       # may be labeled as lender
            ("Property Address", "property_address"),
            ("Property", "property_address"),
        ]:
            if getattr(case, attr):
                continue  # already populated
            value = await _extract_labeled_value(page, label)
            if value:
                setattr(case, attr, value)

        # Docket entries table
        docket_entries: list[dict[str, str]] = []
        docket_lines: list[str] = []

        # Strategy 1: look for "Docket" section heading then find its table
        docket_table = page.locator("table").filter(
            has=page.get_by_role("columnheader", name=re.compile(r"date|docket|entry|description", re.I))
        )
        if await docket_table.count() == 0:
            # Strategy 2: any table that has a "Date" column header
            docket_table = page.locator("table").filter(
                has_text=re.compile(r"date", re.I)
            )

        if await docket_table.count() > 0:
            tbl = docket_table.first
            rows = tbl.locator("tbody tr")
            row_count = await rows.count()

            for i in range(row_count):
                cells = rows.nth(i).locator("td")
                cell_count = await cells.count()
                if cell_count < 2:
                    continue

                entry_date = (await cells.nth(0).inner_text()).strip()
                # Description is usually the longest cell — find the widest text
                entry_text_parts: list[str] = []
                for ci in range(1, cell_count):
                    part = (await cells.nth(ci).inner_text()).strip()
                    if part:
                        entry_text_parts.append(part)
                entry_text = " — ".join(entry_text_parts)

                docket_entries.append({"date": entry_date, "text": entry_text})
                if entry_date:
                    docket_lines.append(f"{entry_date}: {entry_text}")
                else:
                    docket_lines.append(entry_text)

        case.raw_docket = docket_entries
        case.raw_docket_text = "\n".join(docket_lines) if docket_lines else None

        if not docket_lines:
            logger.warning(f"No docket entries extracted for {case.case_number} — check detail page selector")

    except Exception as e:
        logger.error(f"Error extracting detail for {case.case_number}: {e}")

    return case


async def _extract_labeled_value(page: Any, label: str) -> str | None:
    """
    Find a cell/span/div labeled with `label` and return the adjacent value.
    Works for both <th>/<td> table layouts and definition list <dt>/<dd> layouts.
    """
    try:
        # Table layout: <th>Label</th><td>Value</td> or <td>Label</td><td>Value</td>
        for tag in ("th", "td", "dt", "span", "label"):
            elements = page.locator(tag).filter(
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*:?\s*$", re.I)
            )
            if await elements.count() > 0:
                el = elements.first
                # Try next sibling td/dd/span
                for sibling_tag in ("td", "dd", "span", "div"):
                    sibling = el.locator(f"xpath=following-sibling::{sibling_tag}[1]")
                    if await sibling.count() > 0:
                        text = (await sibling.inner_text()).strip()
                        if text:
                            return text
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

async def _is_captcha_page(page: Any) -> bool:
    """Detect Cloudflare Turnstile or similar CAPTCHA challenge."""
    try:
        title = await page.title()
        if "just a moment" in title.lower() or "checking your browser" in title.lower():
            return True
        content = await page.content()
        if "cf-turnstile" in content or "hcaptcha" in content or "recaptcha" in content:
            return True
    except Exception:
        pass
    return False
