"""
Unit tests for Module F: DOM Change Monitor
Test 6: Hash change detection
Test 7 (partial): CSV import tested in test_keywords.py
"""

import pytest
from unittest.mock import patch, MagicMock
from collector.modules.dom_monitor import _compute_page_hash, check_dom_changes


class TestHashChangeDetection:
    """Test 6: Same page fetched twice, second time with modified text → has_changed = true."""

    def test_same_content_same_hash(self):
        html = "<html><body><p>Hello World</p></body></html>"
        h1 = _compute_page_hash(html)
        h2 = _compute_page_hash(html)
        assert h1 == h2

    def test_different_content_different_hash(self):
        html1 = "<html><body><p>Original content</p></body></html>"
        html2 = "<html><body><p>Modified content - something changed</p></body></html>"
        h1 = _compute_page_hash(html1)
        h2 = _compute_page_hash(html2)
        assert h1 != h2

    def test_hash_is_32_char_md5(self):
        html = "<html><body>Test</body></html>"
        h = _compute_page_hash(html)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_scripts_stripped_before_hashing(self):
        """Script tags should be removed so JS changes don't cause false positives."""
        html_without_script = "<html><body><p>Content</p></body></html>"
        html_with_script = "<html><body><p>Content</p><script>var x = Date.now();</script></body></html>"
        h1 = _compute_page_hash(html_without_script)
        h2 = _compute_page_hash(html_with_script)
        assert h1 == h2

    def test_style_tags_stripped_before_hashing(self):
        html_without_style = "<html><body><p>Content</p></body></html>"
        html_with_style = "<html><body><style>.btn{color:red}</style><p>Content</p></body></html>"
        h1 = _compute_page_hash(html_without_style)
        h2 = _compute_page_hash(html_with_style)
        assert h1 == h2

    def test_check_dom_changes_detects_change(self):
        url = "https://example.com"
        old_hash = _compute_page_hash("<html><body><p>Old content</p></body></html>")
        new_html = "<html><body><p>New content after page edit</p></body></html>"

        mock_response = MagicMock()
        mock_response.text = new_html
        mock_response.raise_for_status = MagicMock()

        with patch("collector.modules.dom_monitor.requests.get", return_value=mock_response):
            results = check_dom_changes(
                domain="example.com",
                page_urls=[url],
                last_hashes={url: old_hash},
            )

        assert len(results) == 1
        assert results[0]["has_changed"] is True
        assert results[0]["url"] == url
        assert len(results[0]["current_hash"]) == 32

    def test_check_dom_changes_no_change(self):
        url = "https://example.com"
        html = "<html><body><p>Same content</p></body></html>"
        same_hash = _compute_page_hash(html)

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("collector.modules.dom_monitor.requests.get", return_value=mock_response):
            results = check_dom_changes(
                domain="example.com",
                page_urls=[url],
                last_hashes={url: same_hash},
            )

        assert results[0]["has_changed"] is False

    def test_check_dom_changes_no_previous_hash_not_marked_changed(self):
        """First scan: no previous hash → has_changed should be False."""
        url = "https://example.com"

        mock_response = MagicMock()
        mock_response.text = "<html><body><p>First scan</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("collector.modules.dom_monitor.requests.get", return_value=mock_response):
            results = check_dom_changes(
                domain="example.com",
                page_urls=[url],
                last_hashes={},  # no previous hash
            )

        assert results[0]["has_changed"] is False

    def test_check_dom_changes_timeout_does_not_crash(self):
        """Timeout should be handled gracefully, not raise an exception."""
        import requests as req
        url = "https://example.com"

        with patch("collector.modules.dom_monitor.requests.get", side_effect=req.exceptions.Timeout()):
            try:
                results = check_dom_changes(
                    domain="example.com",
                    page_urls=[url],
                    last_hashes={},
                )
                assert results[0]["error"] == "timeout"
            except Exception as e:
                pytest.fail(f"Timeout raised unexpected exception: {e}")
