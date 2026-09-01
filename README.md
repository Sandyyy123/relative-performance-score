> **⚠️ Proprietary — All Rights Reserved.** © 2026 Sandeep Grover. This repository is licensed to Sandeep Grover and may **not** be used, run, copied, modified, distributed, or used to train models without prior written permission. Public visibility does not grant a license. See [LICENSE](LICENSE).

---

# relperf — Relative Performance Scoring for Securities

A reusable analytical component that compares the performance of one **target
security** against a **peer group** (sector, industry, or a custom list) over a
date window, and returns a normalised score in **[-1, +1]**.

```
 -1  ── strong underperformance
  0  ── in line with peers
 +1  ── strong outperformance
```

## What it computes

| Field             | Meaning                                            |
|-------------------|----------------------------------------------------|
| `target_return`   | Simple return of the target over the window        |
| `peer_return`     | Mean simple return of the peer group               |
| `relative_return` | `target_return - peer_return`                      |
| `score`           | Normalised score in [-1, +1]                       |
| `peers_used`      | Number of peers with valid data                    |
| `warnings`        | Missing data / weak-sample / degenerate-case notes |

## Architecture

```
  ┌────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
  │ FastAPI    │ ──► │ service.py   │ ──► │ data_access  │ ──► │ PostgreSQL  │
  │ /score     │     │ resolve+calc │     │ (as-of price)│     │ prices/...  │
  └────────────┘     └──────┬───────┘     └──────────────┘     └─────────────┘
                            ▼
                     ┌──────────────┐
                     │ scoring.py   │  pure, dependency-free, fully unit-tested
                     │ z-score/tanh │
                     │ + percentile │
                     └──────────────┘
```

- **`scoring.py`** — pure functions, no external deps. The normalised score is a
  cross-sectional z-score squashed with `tanh` (smooth, bounded). A
  distribution-free **percentile** method is also available.
- **`data_access.py`** — PostgreSQL layer with an **as-of** price lookup so
  weekends/holidays (non-trading dates) don't break the window. Supports
  `adj_close` (preferred) and `close`.
- **`service.py`** — resolves the peer group (sector / industry / custom /
  explicit), fetches returns, and scores.
- **`api.py`** — optional FastAPI `POST /score` endpoint.

## Quick start

```bash
pip install -r requirements.txt
pytest -q                       # run the unit tests

# scoring with precomputed returns (no DB needed):
python -c "from relperf import score_relative_performance as s; \
print(s(0.20, [0.05, 0.04, 0.06, 0.03]).to_dict())"
```

### API

```bash
export RELPERF_DSN="postgresql://user:pass@localhost:5432/markets"
uvicorn relperf.api:app --reload
```

```bash
curl -X POST localhost:8000/score -H 'content-type: application/json' -d '{
  "target": "AAPL", "start": "2024-01-02", "end": "2024-03-28",
  "peer_by": "sector", "price_type": "adj_close", "method": "zscore"
}'
```

## Scoring methods

- **`zscore`** (default): `score = tanh((target − peer_mean) / peer_std / 2)`.
  Rewards outperformance relative to how dispersed the peer group actually is.
  Falls back to the sign of the relative return when peer dispersion is zero.
- **`percentile`**: rank of the target within the peer returns, mapped to
  [-1, +1]. Robust to outliers and non-normal spreads.

## Missing data & edge cases

- Missing target price → `score = None` + warning.
- Peers with missing/NaN returns are dropped (counted in a warning).
- Non-trading dates handled via as-of (most-recent-on-or-before) lookup.
- Fewer than 3 valid peers → score still returned, flagged as statistically weak.

## Tests

`tests/test_scoring.py` covers positive, negative, neutral, bounds, missing
target, no peers, NaN peers, zero dispersion, both methods, and the dict
round-trip.
