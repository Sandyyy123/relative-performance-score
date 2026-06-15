"""Relative performance scoring for a target security vs a peer group.

Core idea
---------
Given a target security and a peer group over a date window, compute:
  - target return
  - average peer return
  - relative return (target - peer average)
  - a normalised score in [-1, +1]

The normalised score uses a cross-sectional z-score of the target's return
against the peer-return distribution, squashed with tanh so the result is
smoothly bounded to [-1, +1]:

    z     = (target_return - peer_mean) / peer_std
    score = tanh(z / SCALE)

  -1  -> strong underperformance
   0  -> in line with peers
  +1  -> strong outperformance

A percentile-rank method is also provided for callers who prefer a
distribution-free score (robust to outliers and non-normal peer spreads).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence

# Squash scale: a target ~2 cross-sectional std devs above peers maps to ~+0.96.
DEFAULT_SCALE = 2.0


@dataclass
class ScoreResult:
    """Structured result returned by score_relative_performance."""

    score: Optional[float]                 # normalised score in [-1, +1]
    target_return: Optional[float]         # simple return of the target
    peer_return: Optional[float]           # mean simple return across peers
    relative_return: Optional[float]       # target_return - peer_return
    peers_used: int                        # number of peers with valid data
    method: str                            # "zscore" or "percentile"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


def simple_return(start_price: float, end_price: float) -> float:
    """Simple (arithmetic) return between two prices."""
    if start_price is None or end_price is None:
        raise ValueError("prices must not be None")
    if start_price <= 0:
        raise ValueError("start_price must be positive")
    return (end_price / start_price) - 1.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _std(values: Sequence[float], ddof: int = 1) -> float:
    n = len(values)
    if n - ddof <= 0:
        return 0.0
    mu = _mean(values)
    var = sum((v - mu) ** 2 for v in values) / (n - ddof)
    return math.sqrt(var)


def score_relative_performance(
    target_return: Optional[float],
    peer_returns: Sequence[Optional[float]],
    method: str = "zscore",
    scale: float = DEFAULT_SCALE,
) -> ScoreResult:
    """Compute the relative-performance score from precomputed returns.

    Parameters
    ----------
    target_return : float | None
        Simple return of the target security over the window.
    peer_returns : sequence of float | None
        Simple returns of each peer. None entries (missing data) are dropped.
    method : {"zscore", "percentile"}
        Normalisation strategy.
    scale : float
        Z-score squash scale (zscore method only).
    """
    warnings: List[str] = []

    valid_peers = [r for r in peer_returns if r is not None and not _isnan(r)]
    dropped = len(peer_returns) - len(valid_peers)
    if dropped > 0:
        warnings.append(f"{dropped} peer(s) dropped due to missing/NaN returns")

    if target_return is None or _isnan(target_return):
        warnings.append("target return is missing; cannot score")
        return ScoreResult(None, None, None, None, len(valid_peers), method, warnings)

    if not valid_peers:
        warnings.append("no valid peers; relative score undefined")
        return ScoreResult(None, target_return, None, None, 0, method, warnings)

    peer_mean = _mean(valid_peers)
    relative = target_return - peer_mean

    if method == "percentile":
        score = _percentile_score(target_return, valid_peers)
    elif method == "zscore":
        peer_std = _std(valid_peers, ddof=1)
        if peer_std < 1e-12:
            # Degenerate spread: fall back to sign of relative return.
            warnings.append("peer return dispersion is zero; using sign of relative return")
            score = _clip(math.copysign(1.0, relative) if relative != 0 else 0.0)
        else:
            z = relative / peer_std
            score = _clip(math.tanh(z / scale))
    else:
        raise ValueError(f"unknown method: {method!r}")

    if len(valid_peers) < 3:
        warnings.append(f"only {len(valid_peers)} peer(s); score is statistically weak")

    return ScoreResult(
        score=score,
        target_return=target_return,
        peer_return=peer_mean,
        relative_return=relative,
        peers_used=len(valid_peers),
        method=method,
        warnings=warnings,
    )


def _percentile_score(target: float, peers: Sequence[float]) -> float:
    """Map the target's rank within peers to [-1, +1].

    percentile in [0, 1] -> score = 2 * percentile - 1.
    Ties count as half (standard mid-rank treatment).
    """
    below = sum(1 for p in peers if p < target)
    equal = sum(1 for p in peers if p == target)
    pct = (below + 0.5 * equal) / len(peers)
    return _clip(2.0 * pct - 1.0)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _isnan(x: float) -> bool:
    return isinstance(x, float) and math.isnan(x)
