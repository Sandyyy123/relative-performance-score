"""relperf - relative performance scoring for securities vs a peer group."""

from .scoring import ScoreResult, score_relative_performance, simple_return

__all__ = ["ScoreResult", "score_relative_performance", "simple_return"]
__version__ = "1.0.0"
