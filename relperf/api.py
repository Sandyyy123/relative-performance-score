"""Optional FastAPI endpoint exposing the relative-performance score.

Run:
    uvicorn relperf.api:app --reload

Set the database DSN via the RELPERF_DSN env var, e.g.
    export RELPERF_DSN="postgresql://user:pass@localhost:5432/markets"
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    raise RuntimeError("FastAPI not installed; `pip install fastapi uvicorn`")

from .data_access import connect
from .service import evaluate

app = FastAPI(title="Relative Performance Score", version="1.0.0")


class ScoreRequest(BaseModel):
    target: str = Field(..., examples=["AAPL"])
    start: date
    end: date
    peer_by: str = Field("sector", pattern="^(sector|industry|custom|explicit)$")
    custom_group: Optional[str] = None
    peers: Optional[List[str]] = None
    price_type: str = Field("adj_close", pattern="^(adj_close|close)$")
    method: str = Field("zscore", pattern="^(zscore|percentile)$")


class ScoreResponse(BaseModel):
    score: Optional[float]
    target_return: Optional[float]
    peer_return: Optional[float]
    relative_return: Optional[float]
    peers_used: int
    method: str
    warnings: List[str]


def _dsn() -> str:
    dsn = os.environ.get("RELPERF_DSN")
    if not dsn:
        raise HTTPException(status_code=500, detail="RELPERF_DSN env var not set")
    return dsn


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    if req.end < req.start:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    repo = connect(_dsn())
    try:
        result = evaluate(
            repo,
            target=req.target,
            start=req.start.isoformat(),
            end=req.end.isoformat(),
            peer_by=req.peer_by,
            custom_group=req.custom_group,
            peers=req.peers,
            price_type=req.price_type,
            method=req.method,
        )
    finally:
        repo.conn.close()
    return ScoreResponse(**result.to_dict())
