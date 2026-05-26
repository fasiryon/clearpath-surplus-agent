"""Tests for court adapters — no network calls, pure logic tests."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from src.models import CaseRecord


class TestBaseCourt:
    def test_get_date_range_format(self):
        """get_date_range should return MM/DD/YYYY strings."""
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = MarylandMJCSAdapter(county="Baltimore County")
        from_str, to_str = adapter.get_date_range(3)
        # Verify format: MM/DD/YYYY
        assert len(from_str) == 10
        assert from_str[2] == "/"
        assert from_str[5] == "/"

    def test_get_date_range_span(self):
        """from_date should be exactly lookback_days before to_date."""
        from datetime import date, timedelta
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = MarylandMJCSAdapter(county="Baltimore County")
        from_str, to_str = adapter.get_date_range(7)
        from_date = date(int(from_str[6:]), int(from_str[:2]), int(from_str[3:5]))
        to_date = date(int(to_str[6:]), int(to_str[:2]), int(to_str[3:5]))
        assert (to_date - from_date).days == 7


class TestMarylandMJCSAdapter:
    def test_adapter_county_attribute(self):
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = MarylandMJCSAdapter(county="Prince Georges")
        assert adapter.county == "Prince Georges"
        assert adapter.state == "MD"
        assert adapter.case_type == "CAEF"

    def test_get_county_code_baltimore_county(self):
        """Should find Baltimore County code from states.json."""
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = MarylandMJCSAdapter(county="Baltimore County")
        code = adapter._get_county_code()
        assert code == "03"

    def test_get_county_code_prince_georges(self):
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = MarylandMJCSAdapter(county="Prince Georges")
        code = adapter._get_county_code()
        assert code == "16"

    def test_parse_results_html_empty_table(self):
        """Parsing HTML with no results table returns empty list."""
        from src.adapters.maryland_mjcs import _parse_results_html
        html = "<html><body><p>No results found</p></body></html>"
        records = _parse_results_html(html, "Baltimore County")
        assert records == []

    def test_parse_results_html_with_rows(self):
        """Parsing a properly structured results table returns CaseRecords."""
        from src.adapters.maryland_mjcs import _parse_results_html
        html = """
        <html><body>
        <table class="resultsTable">
          <tr><th>Case No.</th><th>Title</th><th>Filing Date</th></tr>
          <tr>
            <td><a href="/casesearch/inquiryDetail.jis?caseId=C-24-001">C-24-001</a></td>
            <td>Wells Fargo v. Smith</td>
            <td>01/15/2024</td>
          </tr>
        </table>
        </body></html>
        """
        records = _parse_results_html(html, "Baltimore County")
        assert len(records) == 1
        assert records[0].case_number == "C-24-001"
        assert records[0].county == "Baltimore County"
        assert records[0].filing_date == "01/15/2024"
        assert records[0].detail_url is not None
        assert "C-24-001" in records[0].detail_url

    def test_extract_hidden_field(self):
        """_extract_hidden should find ASP.NET hidden input values."""
        from src.adapters.maryland_mjcs import _extract_hidden
        soup = BeautifulSoup(
            '<form><input name="__VIEWSTATE" value="abc123" type="hidden"/></form>',
            "html.parser",
        )
        assert _extract_hidden(soup, "__VIEWSTATE") == "abc123"
        assert _extract_hidden(soup, "__MISSINGFIELD") is None

    def test_parse_case_detail_extracts_docket(self):
        """_parse_case_detail should populate raw_docket and raw_docket_text."""
        from src.adapters.maryland_mjcs import _parse_case_detail
        case = CaseRecord(
            case_number="C-24-001",
            county="Baltimore County",
            title="Test Case",
        )
        html = """
        <html><body>
        <table class="docketTable">
          <tr><th>Date</th><th>Entry</th></tr>
          <tr><td>07/14/2024</td><td>Auditor's Report filed; surplus funds of $42,500.00</td></tr>
          <tr><td>08/01/2024</td><td>Order ratifying sale entered</td></tr>
        </table>
        </body></html>
        """
        result = _parse_case_detail(html, case)
        assert len(result.raw_docket) == 2
        assert result.raw_docket[0]["date"] == "07/14/2024"
        assert "42,500" in result.raw_docket[0]["text"]
        assert result.raw_docket_text is not None
        assert "Auditor's Report" in result.raw_docket_text


class TestCourtAdapterFactory:
    def test_get_maryland_wildcard(self):
        """MD + any county should return MarylandMJCSAdapter."""
        from src.adapters import CourtAdapterFactory
        from src.adapters.maryland_mjcs import MarylandMJCSAdapter
        adapter = CourtAdapterFactory.get("MD", "Baltimore County")
        assert isinstance(adapter, MarylandMJCSAdapter)
        assert adapter.county == "Baltimore County"

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
