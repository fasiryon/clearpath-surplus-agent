"""Abstract base class for all court system adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta


class BaseCourt(ABC):
    """
    Interface every state/county court adapter must implement.

    Adapters handle the mechanics of fetching case data from a specific
    court's website or API. They do NOT detect surplus — that is
    DocketAgent's job. They return raw docket text for LLM analysis.
    """

    state: str      # Two-letter state code, e.g. 'MD'
    case_type: str  # Court case type filter, e.g. 'CAEF'

    def __init__(self, county: str) -> None:
        self.county = county

    @abstractmethod
    async def search_cases(self, lookback_days: int) -> list:
        """
        Search the court for recent foreclosure case summaries.

        Args:
            lookback_days: How many days back to search from today.

        Returns:
            List of CaseRecord objects (without docket detail — just headers).
        """
        ...

    @abstractmethod
    async def get_case_detail(self, case: object) -> object | None:
        """
        Fetch full docket for one case.

        Populates case.raw_docket (structured list) and case.raw_docket_text
        (plain text for LLM analysis). Does NOT perform surplus detection.

        Args:
            case: CaseRecord from search_cases() with a detail_url.

        Returns:
            The same CaseRecord enriched with docket data,
            or None if the page cannot be fetched.
        """
        ...

    def get_date_range(self, lookback_days: int) -> tuple[str, str]:
        """
        Return (from_date, to_date) formatted as MM/DD/YYYY strings.

        Args:
            lookback_days: Days back from today.

        Returns:
            Tuple of (from_date_str, to_date_str).
        """
        today = date.today()
        from_date = today - timedelta(days=lookback_days)
        return from_date.strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")
