"""
Unit tests for Module A: Sitemap Engine
Test 4: Sitemap parse failure → { error: 'no_sitemap' }, does not crash
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Force import so mock can patch the module's adv attribute
import collector.modules.sitemap as sitemap_module
from collector.modules.sitemap import parse_sitemap


class TestSitemapParseFailure:
    """Test 4: Domain has no sitemap.xml → returns { error: 'no_sitemap' }, does not crash."""

    def test_empty_dataframe_returns_no_sitemap(self):
        with patch.object(sitemap_module, "adv") as mock_adv:
            mock_adv.sitemap_to_df.return_value = pd.DataFrame()
            result = parse_sitemap("thisisnotareal.website")
            assert "error" in result
            assert result["error"] == "no_sitemap"

    def test_none_dataframe_returns_no_sitemap(self):
        with patch.object(sitemap_module, "adv") as mock_adv:
            mock_adv.sitemap_to_df.return_value = None
            result = parse_sitemap("thisisnotareal.website")
            assert "error" in result
            assert result["error"] == "no_sitemap"

    def test_404_exception_returns_no_sitemap(self):
        with patch.object(sitemap_module, "adv") as mock_adv:
            mock_adv.sitemap_to_df.side_effect = Exception("404 not found")
            result = parse_sitemap("thisisnotareal.website")
            assert "error" in result
            assert result["error"] == "no_sitemap"

    def test_does_not_raise_exception_on_failure(self):
        with patch.object(sitemap_module, "adv") as mock_adv:
            mock_adv.sitemap_to_df.side_effect = Exception("Connection refused")
            try:
                result = parse_sitemap("thisisnotareal.website")
                assert "error" in result
            except Exception as e:
                pytest.fail(f"parse_sitemap raised an unexpected exception: {e}")

    def test_successful_sitemap_returns_total_pages(self):
        mock_df = pd.DataFrame({
            "loc": ["https://example.com/page1", "https://example.com/page2", "https://example.com/page3"],
            "lastmod": ["2026-07-01", "2026-07-10", "2026-07-15"],
        })
        with patch.object(sitemap_module, "adv") as mock_adv:
            mock_adv.sitemap_to_df.return_value = mock_df
            result = parse_sitemap("example.com")
            assert result["total_pages"] == 3
            assert "urls" in result
            assert "error" not in result
