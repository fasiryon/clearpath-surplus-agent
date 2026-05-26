"""
Tests for court adapters — no network calls, no browser, pure logic/import tests.

The MarylandMJCSAdapter is Playwright-only; search_cases() and get_case_detail()
cannot be unit-tested without a live browser. Tests here cover:
  - date range formatting (inherited from BaseCourt)
  - adapter instantiation and class attributes
  - CourtAdapterFactory routing
  - CAPTCHA detection helper (using mock page objects)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBaseCourt:
    def test_get_date_range_format(self):
        """get_date_range should return MM/DD/YYYY strings."""
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        adapter = MarylandMJCSAdapter(county="Baltimore County")
        from_str, to_str = adapter.get_date_range(3)
        assert len(from_str) == 10
        assert from_str[2] == "/"
        assert from_str[5] == "/"
        assert len(to_str) == 10

    def test_get_date_range_span(self):
        """from_date should be exactly lookback_days before to_date."""
        from datetime import date

        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        adapter = MarylandMJCSAdapter(county="Baltimore County")
        from_str, to_str = adapter.get_date_range(7)
        from_date = date(int(from_str[6:]), int(from_str[:2]), int(from_str[3:5]))
        to_date = date(int(to_str[6:]), int(to_str[:2]), int(to_str[3:5]))
        assert (to_date - from_date).days == 7


class TestMarylandMJCSAdapter:
    def test_adapter_county_attribute(self):
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        adapter = MarylandMJCSAdapter(county="Baltimore County")
        assert adapter.county == "Baltimore County"
        assert adapter.state == "MD"
        assert adapter.case_type == "CAEF"

    def test_adapter_different_counties(self):
        """Adapter should accept any county string."""
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        for county in ("Prince George's", "Montgomery", "Anne Arundel"):
            a = MarylandMJCSAdapter(county=county)
            assert a.county == county

    def test_constants_point_to_new_portal(self):
        """Verify the URL constants reference the Odyssey SPA, not the old .jis URL."""
        from src.adapters import maryland_mjcs as m

        assert "inquiry-search" in m.MJCS_SEARCH_URL
        assert ".jis" not in m.MJCS_SEARCH_URL
        assert "casesearch.courts.state.md.us" in m.MJCS_SEARCH_URL

    def test_no_httpx_import(self):
        """The module must not import httpx (removed with old portal)."""
        import importlib
        import sys

        # Reload the module to get a fresh import graph
        if "src.adapters.maryland_mjcs" in sys.modules:
            mod = sys.modules["src.adapters.maryland_mjcs"]
        else:
            mod = importlib.import_module("src.adapters.maryland_mjcs")

        # httpx should not be in the module's namespace
        assert not hasattr(mod, "httpx"), "httpx must not be imported in maryland_mjcs"

    def test_no_beautifulsoup_import(self):
        """The module must not import BeautifulSoup (removed with old portal)."""
        import importlib
        import sys

        if "src.adapters.maryland_mjcs" in sys.modules:
            mod = sys.modules["src.adapters.maryland_mjcs"]
        else:
            mod = importlib.import_module("src.adapters.maryland_mjcs")

        assert not hasattr(mod, "BeautifulSoup"), "BeautifulSoup must not be imported"


@pytest.mark.asyncio
class TestCaptchaDetection:
    async def test_captcha_detected_by_title(self):
        """_is_captcha_page returns True when page title contains 'Just a moment'."""
        from src.adapters.maryland_mjcs import _is_captcha_page

        page = MagicMock()
        page.title = AsyncMock(return_value="Just a moment...")
        page.content = AsyncMock(return_value="<html></html>")

        assert await _is_captcha_page(page) is True

    async def test_captcha_detected_by_turnstile(self):
        """_is_captcha_page returns True when content contains cf-turnstile."""
        from src.adapters.maryland_mjcs import _is_captcha_page

        page = MagicMock()
        page.title = AsyncMock(return_value="Maryland Courts")
        page.content = AsyncMock(return_value='<div class="cf-turnstile"></div>')

        assert await _is_captcha_page(page) is True

    async def test_no_captcha_on_normal_page(self):
        """_is_captcha_page returns False on a normal page."""
        from src.adapters.maryland_mjcs import _is_captcha_page

        page = MagicMock()
        page.title = AsyncMock(return_value="Case Search - Maryland Courts")
        page.content = AsyncMock(return_value="<html><body>Search form here</body></html>")

        assert await _is_captcha_page(page) is False


class TestCourtAdapterFactory:
    def test_get_maryland_wildcard(self):
        """MD + any county should return MarylandMJCSAdapter."""
        from src.adapters import CourtAdapterFactory
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        adapter = CourtAdapterFactory.get("MD", "Baltimore County")
        assert isinstance(adapter, MarylandMJCSAdapter)
        assert adapter.county == "Baltimore County"

    def test_get_maryland_any_county(self):
        """The MD wildcard should match any county name."""
        from src.adapters import CourtAdapterFactory
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter

        adapter = CourtAdapterFactory.get("MD", "Montgomery")
        assert isinstance(adapter, MarylandMJCSAdapter)
        assert adapter.county == "Montgomery"

    def test_get_florida_sarasota(self):
        """FL + Sarasota should return FloridaSarasotaAdapter."""
        from src.adapters import CourtAdapterFactory
        from src.adapters.florida_sarasota import FloridaSarasotaAdapter

        adapter = CourtAdapterFactory.get("FL", "Sarasota")
        assert isinstance(adapter, FloridaSarasotaAdapter)

    def test_get_florida_hillsborough(self):
        """FL + Hillsborough should return FloridaHillsboroughAdapter."""
        from src.adapters import CourtAdapterFactory
        from src.adapters.florida_hillsborough import FloridaHillsboroughAdapter

        adapter = CourtAdapterFactory.get("FL", "Hillsborough")
        assert isinstance(adapter, FloridaHillsboroughAdapter)

    def test_unknown_state_raises(self):
        """Unknown state/county combination should raise ValueError."""
        from src.adapters import CourtAdapterFactory

        with pytest.raises(ValueError, match="No court adapter"):
            CourtAdapterFactory.get("TX", "Harris")
