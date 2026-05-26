"""
Florida — Hillsborough County (Tampa) Court adapter [STUB]

TODO Checklist (complete before activating):
  [ ] 1. Investigate Hillsborough Clerk public records API — RESEARCH THIS FIRST
         Hillsborough has published REST/JSON endpoints; may not need scraping at all
  [ ] 2. Confirm API base URL and authentication (API key vs. open access)
  [ ] 3. Map foreclosure case type in Hillsborough's system
  [ ] 4. Verify surplus terminology differs from Sarasota (both FL but portals differ)
  [ ] 5. Handle Hillsborough's higher volume (500+ foreclosures/month) — may need
         pagination handling for large result sets
  [ ] 6. Test with 10 known Hillsborough cases before enabling
  [ ] 7. Set active=true for Hillsborough in config/states.json when ready

Key URLs:
  Portal:    https://www.hillsclerk.com/
  API docs:  Investigate https://www.hillsclerk.com/PublicRecord/GetCases (check for JSON API)
  Case search: https://pubrec.hillsclerk.com/

Hillsborough-specific notes:
  - Tampa metro = largest FL market by foreclosure volume (~500+/month)
  - Hillsborough has historically made court data more accessible than other FL counties
  - If a public JSON API exists, this can be implemented as a simple httpx GET
    with no scraping needed — dramatically reduces maintenance burden
  - Same FL legal framework as Sarasota (Fla. Stat. §45.032 surplus claim process)
  - Average Hillsborough surplus estimate: $20,000–$45,000

API investigation approach:
  1. Open browser DevTools on https://pubrec.hillsclerk.com/
  2. Filter XHR requests while performing a case search
  3. If JSON responses appear, document the endpoint + params
  4. That API is your primary path — use httpx, not Playwright
"""

from __future__ import annotations

from src.adapters.base_court import BaseCourt
from src.models import CaseRecord


class FloridaHillsboroughAdapter(BaseCourt):
    state = "FL"
    case_type = "CA"  # VERIFY: Hillsborough case type code for mortgage foreclosures

    async def search_cases(self, lookback_days: int = 3) -> list[CaseRecord]:
        """
        Search Hillsborough Clerk for mortgage foreclosure cases.

        Not yet implemented — stub returns empty list.

        Implementation priority: investigate JSON API before building scraper.
        If Hillsborough exposes a public REST API, this is a 1-day implementation.
        """
        raise NotImplementedError(
            "FloridaHillsboroughAdapter.search_cases() is not yet implemented. "
            "See the TODO checklist at the top of this file."
        )

    async def get_case_detail(self, case: CaseRecord) -> CaseRecord | None:
        """
        Fetch full docket for a Hillsborough foreclosure case.

        Not yet implemented.
        """
        raise NotImplementedError(
            "FloridaHillsboroughAdapter.get_case_detail() is not yet implemented."
        )
