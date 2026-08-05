"""
Unit tests for Module C: SERP Rank Checker
Test 5: Rate limit backoff — simulate 429 response → waits then retries
"""

import pytest
import time
from unittest.mock import patch, call, MagicMock


class TestRateLimitBackoff:
    """Test 5: Simulate 429 → waits 10s, retries, waits 30s, retries, waits 90s, then skips."""

    def test_backoff_sequence_on_rate_limit(self):
        """
        Simulate 3 consecutive 429 errors.
        The backoff should follow: 10s → 30s → 90s.
        """
        from collector.modules.serp_checker import _search_with_backoff

        call_count = [0]

        def mock_search(*args, **kwargs):
            call_count[0] += 1
            raise Exception("429 too many requests")

        sleep_calls = []

        with patch("collector.modules.serp_checker.search", side_effect=mock_search):
            with patch("collector.modules.serp_checker.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                result = _search_with_backoff("test query")

        assert result == []
        assert sleep_calls == [10, 30, 90], f"Expected backoff [10, 30, 90] but got {sleep_calls}"

    def test_successful_search_no_sleep(self):
        """No backoff sleep when search succeeds on first attempt."""
        from collector.modules.serp_checker import _search_with_backoff

        with patch("collector.modules.serp_checker.search", return_value=["https://example.com"]):
            with patch("collector.modules.serp_checker.time.sleep") as mock_sleep:
                result = _search_with_backoff("test query")

        assert result == ["https://example.com"]
        mock_sleep.assert_not_called()

    def test_domain_found_returns_correct_rank(self):
        """When domain appears at position 3 in results, rank_position should be 3."""
        from collector.modules.serp_checker import check_serp_ranks

        mock_urls = [
            "https://otherdomain.com/page1",
            "https://anothersite.net/page2",
            "https://mycompetitor.com/hotel-nyc",
        ]

        with patch("collector.modules.serp_checker._search_with_backoff", return_value=mock_urls):
            with patch("collector.modules.serp_checker.time.sleep"):
                results = check_serp_ranks("mycompetitor.com", ["luxury hotel nyc"])

        assert len(results) == 1
        assert results[0]["rank_position"] == 3

    def test_domain_not_found_returns_none_rank(self):
        """Domain not found in SERP results → rank_position = None."""
        from collector.modules.serp_checker import check_serp_ranks

        mock_urls = [
            "https://marriott.com/hotel",
            "https://hilton.com/nyc",
            "https://hyatt.com/luxury",
        ]

        with patch("collector.modules.serp_checker._search_with_backoff", return_value=mock_urls):
            with patch("collector.modules.serp_checker.time.sleep"):
                results = check_serp_ranks("unknowndomain.com", ["luxury hotel nyc"])

        assert results[0]["rank_position"] is None

    def test_mandatory_delay_between_keywords(self):
        """Each keyword query must be followed by a 2-5 second sleep."""
        from collector.modules.serp_checker import check_serp_ranks

        with patch("collector.modules.serp_checker._search_with_backoff", return_value=[]):
            with patch("collector.modules.serp_checker.time.sleep") as mock_sleep:
                check_serp_ranks("example.com", ["kw1", "kw2", "kw3"])

        assert mock_sleep.call_count == 3
        for call_args in mock_sleep.call_args_list:
            delay = call_args[0][0]
            assert 2 <= delay <= 5, f"Delay {delay}s is outside the required 2-5s range"

    def test_three_consecutive_failures_skips_domain(self):
        """After 3 consecutive SERP failures, remaining keywords are skipped."""
        from collector.modules.serp_checker import check_serp_ranks

        call_count = [0]

        def failing_search(*args, **kwargs):
            call_count[0] += 1
            raise Exception("Connection error")

        with patch("collector.modules.serp_checker._search_with_backoff", side_effect=failing_search):
            with patch("collector.modules.serp_checker.time.sleep"):
                results = check_serp_ranks("example.com", ["kw1", "kw2", "kw3", "kw4", "kw5"])

        # Should have stopped after 3 consecutive failures
        assert call_count[0] == 3
        # All 5 keywords should appear in results (remaining marked as skipped/None)
        assert len(results) == 5
        for r in results:
            assert r["rank_position"] is None
