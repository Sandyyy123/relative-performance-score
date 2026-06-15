"""PostgreSQL data access layer for prices and peer groups.

Schema assumed (see sql/schema.sql):

  securities(symbol TEXT PRIMARY KEY, name TEXT, sector TEXT, industry TEXT)
  prices(symbol TEXT, trade_date DATE, close NUMERIC, adj_close NUMERIC,
         PRIMARY KEY (symbol, trade_date))
  custom_groups(group_name TEXT, symbol TEXT, PRIMARY KEY (group_name, symbol))

Non-trading dates are handled with an "as-of" lookup: for a requested date we
take the most recent available trading row on or before that date (within a
small look-back window), so weekends/holidays do not break the calculation.
"""

from __future__ import annotations

from typing import List, Optional

try:
    import psycopg2  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore
except ImportError:  # pragma: no cover - allows import without the driver
    psycopg2 = None
    RealDictCursor = None


PRICE_COLUMNS = {"adj_close", "close"}


class PriceRepository:
    """Thin repository over a psycopg2 connection."""

    def __init__(self, conn, lookback_days: int = 7):
        self.conn = conn
        self.lookback_days = lookback_days

    # -- price lookups ----------------------------------------------------

    def as_of_price(self, symbol: str, date: str, price_type: str = "adj_close") -> Optional[float]:
        """Most recent price on or before `date` within the look-back window.

        Returns None if no row exists in the window (caller treats as missing).
        """
        col = self._price_column(price_type)
        sql = f"""
            SELECT {col} AS price
            FROM prices
            WHERE symbol = %s
              AND trade_date <= %s
              AND trade_date >= %s::date - %s::int
              AND {col} IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (symbol, date, date, self.lookback_days))
            row = cur.fetchone()
        if row is None:
            return None
        return float(row[0])

    def window_return(
        self, symbol: str, start: str, end: str, price_type: str = "adj_close"
    ) -> Optional[float]:
        """Simple return between as-of(start) and as-of(end). None if missing."""
        from .scoring import simple_return

        p0 = self.as_of_price(symbol, start, price_type)
        p1 = self.as_of_price(symbol, end, price_type)
        if p0 is None or p1 is None or p0 <= 0:
            return None
        return simple_return(p0, p1)

    # -- peer-group resolution -------------------------------------------

    def peers_by_sector(self, symbol: str) -> List[str]:
        return self._peers_by_column(symbol, "sector")

    def peers_by_industry(self, symbol: str) -> List[str]:
        return self._peers_by_column(symbol, "industry")

    def peers_by_custom_group(self, group_name: str, exclude: Optional[str] = None) -> List[str]:
        sql = "SELECT symbol FROM custom_groups WHERE group_name = %s"
        params: list = [group_name]
        if exclude:
            sql += " AND symbol <> %s"
            params.append(exclude)
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [r[0] for r in cur.fetchall()]

    def _peers_by_column(self, symbol: str, column: str) -> List[str]:
        if column not in {"sector", "industry"}:
            raise ValueError(f"unsupported grouping column: {column!r}")
        sql = f"""
            SELECT symbol FROM securities
            WHERE {column} = (SELECT {column} FROM securities WHERE symbol = %s)
              AND symbol <> %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (symbol, symbol))
            return [r[0] for r in cur.fetchall()]

    @staticmethod
    def _price_column(price_type: str) -> str:
        if price_type not in PRICE_COLUMNS:
            raise ValueError(
                f"price_type must be one of {sorted(PRICE_COLUMNS)}, got {price_type!r}"
            )
        return price_type


def connect(dsn: str, lookback_days: int = 7) -> PriceRepository:
    """Open a psycopg2 connection and wrap it in a PriceRepository."""
    if psycopg2 is None:  # pragma: no cover
        raise RuntimeError("psycopg2 is not installed; `pip install psycopg2-binary`")
    conn = psycopg2.connect(dsn)
    return PriceRepository(conn, lookback_days=lookback_days)
