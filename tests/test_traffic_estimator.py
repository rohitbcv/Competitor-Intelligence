"""
Unit tests for Module D: Traffic Estimator
Tests: CTR curve lookup, traffic calculation, null rank handling
"""

import pytest
from collector.modules.traffic_estimator import get_ctr, estimate_traffic, CTR_CURVE


class TestCTRCurveLookup:
    """Test 1: Given rank position 1-20, return correct CTR value."""

    def test_position_1_returns_276_pct(self):
        assert get_ctr(1) == pytest.approx(0.276)

    def test_position_2_returns_158_pct(self):
        assert get_ctr(2) == pytest.approx(0.158)

    def test_position_3_returns_110_pct(self):
        assert get_ctr(3) == pytest.approx(0.110)

    def test_position_4_returns_66_pct(self):
        assert get_ctr(4) == pytest.approx(0.066)

    def test_position_5_returns_37_pct(self):
        assert get_ctr(5) == pytest.approx(0.037)

    def test_position_6_returns_26_pct(self):
        assert get_ctr(6) == pytest.approx(0.026)

    def test_position_7_returns_18_pct(self):
        assert get_ctr(7) == pytest.approx(0.018)

    def test_position_8_returns_13_pct(self):
        assert get_ctr(8) == pytest.approx(0.013)

    def test_position_9_returns_10_pct(self):
        assert get_ctr(9) == pytest.approx(0.010)

    def test_position_10_returns_7_pct(self):
        assert get_ctr(10) == pytest.approx(0.007)

    def test_positions_11_to_20_return_03_pct(self):
        for pos in range(11, 21):
            assert get_ctr(pos) == pytest.approx(0.003), f"Position {pos} should be 0.003"

    def test_all_20_positions_covered(self):
        """All 20 positions in the curve must return a non-zero CTR."""
        for pos in range(1, 21):
            assert get_ctr(pos) > 0, f"Position {pos} should have CTR > 0"


class TestTrafficCalculation:
    """Test 2: Given rank=3, volume=8100, compute estimated visits."""

    def test_worked_example_from_spec(self):
        """Spec example: rank=3, volume=8100 → 8100 × 0.110 = 891"""
        result = estimate_traffic(
            domain="competitor.com",
            serp_results=[{"keyword": "luxury hotel nyc", "rank_position": 3}],
            keyword_volumes={"luxury hotel nyc": 8100},
        )
        assert result["total_estimated_monthly_visits"] == 891
        assert len(result["keyword_breakdown"]) == 1
        assert result["keyword_breakdown"][0]["estimated_visits"] == 891
        assert result["keyword_breakdown"][0]["ctr"] == pytest.approx(0.110)

    def test_output_contract_fields_present(self):
        result = estimate_traffic(
            domain="test.com",
            serp_results=[{"keyword": "hotel", "rank_position": 1}],
            keyword_volumes={"hotel": 1000},
        )
        assert "domain" in result
        assert "total_estimated_monthly_visits" in result
        assert "keyword_breakdown" in result
        assert "accuracy" in result
        assert "estimated_at" in result
        assert result["accuracy"] == "estimate_30_50_pct_variance"

    def test_multiple_keywords_sum_correctly(self):
        result = estimate_traffic(
            domain="test.com",
            serp_results=[
                {"keyword": "kw1", "rank_position": 1},  # 1000 × 0.276 = 276
                {"keyword": "kw2", "rank_position": 3},  # 2000 × 0.110 = 220
            ],
            keyword_volumes={"kw1": 1000, "kw2": 2000},
        )
        assert result["total_estimated_monthly_visits"] == 276 + 220


class TestNullRankHandling:
    """Test 3: Domain not found in top 100 → estimated_visits = 0, rank = null, no exception."""

    def test_null_rank_returns_zero_visits(self):
        result = estimate_traffic(
            domain="test.com",
            serp_results=[{"keyword": "luxury hotel nyc", "rank_position": None}],
            keyword_volumes={"luxury hotel nyc": 8100},
        )
        assert result["total_estimated_monthly_visits"] == 0

    def test_null_rank_no_exception(self):
        """Should not raise any exception."""
        try:
            result = estimate_traffic(
                domain="test.com",
                serp_results=[{"keyword": "any keyword", "rank_position": None}],
                keyword_volumes={"any keyword": 5000},
            )
        except Exception as e:
            pytest.fail(f"estimate_traffic raised an exception with null rank: {e}")

    def test_rank_beyond_20_returns_zero(self):
        assert get_ctr(21) == 0.0
        assert get_ctr(50) == 0.0
        assert get_ctr(100) == 0.0

    def test_keyword_not_in_volumes_is_skipped(self):
        """Keywords with no volume data should be skipped (volume = 0)."""
        result = estimate_traffic(
            domain="test.com",
            serp_results=[{"keyword": "unknown keyword", "rank_position": 1}],
            keyword_volumes={},  # no volume data
        )
        assert result["total_estimated_monthly_visits"] == 0
        assert len(result["keyword_breakdown"]) == 0
