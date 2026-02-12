"""Tests for sector ETF mapping constants."""
import pytest

from app.constants.sectors import SECTOR_TO_ETF, get_sector_etf


class TestSectorToETFMapping:
    """Test the SECTOR_TO_ETF constant."""

    def test_all_11_sectors_mapped(self):
        """Verify all 11 SPDR Select Sector ETFs are mapped."""
        expected_etfs = {"XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLC", "XLU", "XLRE"}
        actual_etfs = set(SECTOR_TO_ETF.values())
        assert actual_etfs == expected_etfs, "Missing or extra ETF mappings"

    def test_all_etfs_unique(self):
        """Verify no duplicate ETF symbols."""
        etfs = list(SECTOR_TO_ETF.values())
        assert len(etfs) == len(set(etfs)), "Duplicate ETF symbols found"

    def test_all_sectors_unique(self):
        """Verify no duplicate sector names."""
        sectors = list(SECTOR_TO_ETF.keys())
        assert len(sectors) == len(set(sectors)), "Duplicate sector names found"


class TestGetSectorETF:
    """Test the get_sector_etf function."""

    def test_exact_match_technology(self):
        """Test exact match for Technology sector."""
        assert get_sector_etf("Technology") == "XLK"

    def test_exact_match_financial_services(self):
        """Test exact match for Financial Services sector."""
        assert get_sector_etf("Financial Services") == "XLF"

    def test_exact_match_healthcare(self):
        """Test exact match for Healthcare sector."""
        assert get_sector_etf("Healthcare") == "XLV"

    def test_exact_match_energy(self):
        """Test exact match for Energy sector."""
        assert get_sector_etf("Energy") == "XLE"

    def test_exact_match_consumer_cyclical(self):
        """Test exact match for Consumer Cyclical sector."""
        assert get_sector_etf("Consumer Cyclical") == "XLY"

    def test_exact_match_consumer_defensive(self):
        """Test exact match for Consumer Defensive sector."""
        assert get_sector_etf("Consumer Defensive") == "XLP"

    def test_exact_match_industrials(self):
        """Test exact match for Industrials sector."""
        assert get_sector_etf("Industrials") == "XLI"

    def test_exact_match_basic_materials(self):
        """Test exact match for Basic Materials sector."""
        assert get_sector_etf("Basic Materials") == "XLB"

    def test_exact_match_communication_services(self):
        """Test exact match for Communication Services sector."""
        assert get_sector_etf("Communication Services") == "XLC"

    def test_exact_match_utilities(self):
        """Test exact match for Utilities sector."""
        assert get_sector_etf("Utilities") == "XLU"

    def test_exact_match_real_estate(self):
        """Test exact match for Real Estate sector."""
        assert get_sector_etf("Real Estate") == "XLRE"

    def test_case_insensitive_uppercase(self):
        """Test case-insensitive matching with uppercase."""
        assert get_sector_etf("TECHNOLOGY") == "XLK"

    def test_case_insensitive_lowercase(self):
        """Test case-insensitive matching with lowercase."""
        assert get_sector_etf("technology") == "XLK"

    def test_case_insensitive_mixed_case(self):
        """Test case-insensitive matching with mixed case."""
        assert get_sector_etf("TeChNoLoGy") == "XLK"

    def test_whitespace_trimming(self):
        """Test whitespace trimming."""
        assert get_sector_etf("  Technology  ") == "XLK"

    def test_none_input(self):
        """Test None input returns None."""
        assert get_sector_etf(None) is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert get_sector_etf("") is None

    def test_unmapped_sector(self):
        """Test unmapped sector returns None."""
        assert get_sector_etf("Unknown Sector") is None

    def test_partial_match_not_supported(self):
        """Test that partial matches don't work."""
        assert get_sector_etf("Tech") is None

    def test_whitespace_only(self):
        """Test whitespace-only string returns None."""
        assert get_sector_etf("   ") is None

    def test_all_sectors_return_correct_etf(self):
        """Test that all sectors in SECTOR_TO_ETF map correctly."""
        for sector, expected_etf in SECTOR_TO_ETF.items():
            actual_etf = get_sector_etf(sector)
            assert actual_etf == expected_etf, f"Failed for sector: {sector}"
