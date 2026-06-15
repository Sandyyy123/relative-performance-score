"""High-level service: resolve peers, fetch returns, compute the score.

This ties the data-access layer to the pure scoring function so the FastAPI
endpoint (and any other caller) has a single entry point.
"""

from __future__ import annotations

from typing import List, Optional

from .data_access import PriceRepository
from .scoring import ScoreResult, score_relative_performance


def evaluate(
    repo: PriceRepository,
    target: str,
    start: str,
    end: str,
    peer_by: str = "sector",
    custom_group: Optional[str] = None,
    peers: Optional[List[str]] = None,
    price_type: str = "adj_close",
    method: str = "zscore",
) -> ScoreResult:
    """Resolve the peer set, compute returns, and score the target.

    peer_by : {"sector", "industry", "custom", "explicit"}
        How the peer group is determined. "explicit" uses the `peers` list.
    """
    peer_symbols = _resolve_peers(repo, target, peer_by, custom_group, peers)

    target_return = repo.window_return(target, start, end, price_type)

    peer_returns: List[Optional[float]] = [
        repo.window_return(sym, start, end, price_type) for sym in peer_symbols
    ]

    result = score_relative_performance(target_return, peer_returns, method=method)

    if not peer_symbols:
        result.warnings.append(f"peer resolution returned no peers for '{target}'")
    return result


def _resolve_peers(
    repo: PriceRepository,
    target: str,
    peer_by: str,
    custom_group: Optional[str],
    peers: Optional[List[str]],
) -> List[str]:
    if peer_by == "explicit":
        return [p for p in (peers or []) if p != target]
    if peer_by == "custom":
        if not custom_group:
            raise ValueError("custom_group is required when peer_by='custom'")
        return repo.peers_by_custom_group(custom_group, exclude=target)
    if peer_by == "sector":
        return repo.peers_by_sector(target)
    if peer_by == "industry":
        return repo.peers_by_industry(target)
    raise ValueError(f"unknown peer_by: {peer_by!r}")
