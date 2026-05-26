"""
Florida — Sarasota County Court adapter [STUB]

TODO Checklist (complete before activating):
  [ ] 1. Confirm Sarasota Clerk search endpoint and available API (REST vs scrape)
  [ ] 2. Map Florida foreclosure case type code (typically "CA" with "MF" subtype)
  [ ] 3. Verify "Certificate of Title" and "Surplus Funds" terminology in FL dockets
  [ ] 4. Check Sarasota's pagination and session token requirements
  [ ] 5. Test with 5 known Sarasota foreclosure cases before enabling in states.json
  [ ] 6. Confirm FL has no finder fee cap (correct as of 2025 — reverify before launch)
  [ ] 7. Set active=true for Sarasota in config/states.json when ready

Key URLs:
  Portal:       https://www.sarasotaclerk.com/
  Case search:  https://www.sarasotaclerk.com/clk_index.asp
  REST API:     Check https://www.sarasotaclerk.com/api/ — some FL counties expose JSON APIs

Florida-specific notes:
  - Foreclosure case type: "CA" (Civil Action) with subtype "MF" (Mortgage Foreclosure)
  - Surplus terminology: "Certificate of Title filed", "Clerk's certificate of surplus"
  - FL uses a different surplus claim process: Verified Motion to Claim Surplus Funds
    (Fla. Stat. §45.032) — must be filed within 1 year of foreclosure sale
  - No state fee cap for surplus recovery finders as of 2025
  - Volume: Sarasota County ~200+ foreclosure filings/month (good test market)
  - Average Sarasota surplus estimate: $25,000–$60,000 (high home values)
"""

from __future__ import annotations

from src.adapters.base_court import BaseCourt
from src.models import CaseRecord


class FloridaSarasotaAdapter(BaseCourt):
    state = "FL"
    case_type = "CA"  # VERIFY: Sarasota case type code for mortgage foreclosures

    async def search_cases(self, lookback_days: int = 3) -> list[CaseRecord]:
        """
        Search Sarasota Clerk for mortgage foreclosure cases.

        Not yet implemented — stub returns empty list.

        Implementation notes:
          - Check for a REST API at sarasotaclerk.com before building a scraper
          - If scraping: GET the search form, extract any session tokens,
            POST with case_type=CA, subtype=MF, date range
          - Parse results table — FL courts use different column layouts than MJCS
        """
        raise NotImplementedError(
            "FloridaSarasotaAdapter.search_cases() is not yet implemented. "
            "See the TODO checklist at the top of this file."
        )

    async def get_case_detail(self, case: CaseRecord) -> CaseRecord | None:
        """
        Fetch full docket for a Sarasota foreclosure case.

        Not yet implemented.

        Implementation notes:
          - Follow detail_url, parse docket entries
          - Key FL surplus phrase: 'Clerk's Certificate of Surplus Funds'
          - Populate case.raw_docket_text for DocketAgent LLM analysis
        """
        raise NotImplementedError(
            "FloridaSarasotaAdapter.get_case_detail() is not yet implemented."
        )
