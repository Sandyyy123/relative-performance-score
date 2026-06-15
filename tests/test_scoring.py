"""Unit tests covering positive, negative, neutral and missing-data cases."""

import math

import pytest

from relperf.scoring import (
    ScoreResult,
    score_relative_performance,
    simple_return,
)


def test_simple_return():
    assert simple_return(100, 110) == pytest.approx(0.10)
    assert simple_return(100, 90) == pytest.approx(-0.10)


def test_simple_return_invalid_start():
    with pytest.raises(ValueError):
        simple_return(0, 100)


# -- positive / outperformance -------------------------------------------

def test_positive_outperformance_scores_above_zero():
    res = score_relative_performance(0.20, [0.05, 0.04, 0.06, 0.03])
    assert res.score > 0
    assert res.target_return == pytest.approx(0.20)
    assert res.relative_return > 0
    assert res.peers_used == 4


def test_strong_outperformance_approaches_plus_one():
    res = score_relative_performance(0.50, [0.01, 0.02, 0.0, -0.01])
    assert res.score > 0.9


# -- negative / underperformance -----------------------------------------

def test_negative_underperformance_scores_below_zero():
    res = score_relative_performance(-0.15, [0.05, 0.04, 0.06, 0.03])
    assert res.score < 0
    assert res.relative_return < 0


def test_strong_underperformance_approaches_minus_one():
    res = score_relative_performance(-0.50, [0.01, 0.02, 0.0, -0.01])
    assert res.score < -0.9


# -- neutral / in line ----------------------------------------------------

def test_neutral_in_line_with_peers_scores_near_zero():
    res = score_relative_performance(0.05, [0.04, 0.05, 0.06, 0.05])
    assert abs(res.score) < 0.25
    assert res.relative_return == pytest.approx(0.05 - 0.05, abs=1e-9)


def test_exactly_at_peer_mean_is_zero():
    res = score_relative_performance(0.05, [0.04, 0.06])
    assert res.score == pytest.approx(0.0, abs=1e-9)


# -- score bounds ---------------------------------------------------------

def test_score_always_within_bounds():
    res = score_relative_performance(10.0, [0.01, 0.02, 0.03])
    assert -1.0 <= res.score <= 1.0


# -- missing / edge data --------------------------------------------------

def test_missing_target_returns_none_with_warning():
    res = score_relative_performance(None, [0.01, 0.02])
    assert res.score is None
    assert any("target" in w for w in res.warnings)


def test_no_peers_returns_none_with_warning():
    res = score_relative_performance(0.10, [])
    assert res.score is None
    assert res.peers_used == 0
    assert any("no valid peers" in w for w in res.warnings)


def test_nan_peers_are_dropped():
    res = score_relative_performance(0.10, [0.05, float("nan"), 0.04])
    assert res.peers_used == 2
    assert any("dropped" in w for w in res.warnings)


def test_zero_dispersion_falls_back_to_sign():
    res = score_relative_performance(0.10, [0.05, 0.05, 0.05])
    assert res.score == pytest.approx(1.0)
    assert any("dispersion is zero" in w for w in res.warnings)


def test_few_peers_warns():
    res = score_relative_performance(0.10, [0.05, 0.04])
    assert any("statistically weak" in w for w in res.warnings)


# -- percentile method ----------------------------------------------------

def test_percentile_method_top_of_group():
    res = score_relative_performance(0.99, [0.1, 0.2, 0.3], method="percentile")
    assert res.method == "percentile"
    assert res.score == pytest.approx(1.0)


def test_percentile_method_bottom_of_group():
    res = score_relative_performance(-0.99, [0.1, 0.2, 0.3], method="percentile")
    assert res.score == pytest.approx(-1.0)


def test_percentile_method_median():
    res = score_relative_performance(0.2, [0.1, 0.2, 0.3], method="percentile")
    assert res.score == pytest.approx(0.0, abs=1e-9)


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        score_relative_performance(0.1, [0.05], method="bogus")


def test_result_to_dict_roundtrip():
    res = score_relative_performance(0.10, [0.05, 0.04, 0.06])
    d = res.to_dict()
    assert set(d) == {
        "score", "target_return", "peer_return", "relative_return",
        "peers_used", "method", "warnings",
    }
    assert isinstance(d["warnings"], list)
