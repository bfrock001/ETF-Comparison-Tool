"""Yahoo Finance data access. All public functions return plain Python types."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from functools import lru_cache

import pandas as pd
import yfinance as yf


log = logging.getLogger(__name__)

_RETRY_DELAYS = (0.5, 1.5, 4.0)


def _with_retry(func, *args, **kwargs):
    last_exc: BaseException | None = None
    for delay in (*_RETRY_DELAYS, None):
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            last_exc = e
            if delay is None:
                raise
            time.sleep(delay)
    if last_exc:
        raise last_exc


# Only successful validations are cached, so a transient Yahoo failure
# (cold-start cookie/crumb miss, rate limit, etc.) cannot poison subsequent
# lookups for the same symbol.
_name_cache: dict[str, str] = {}


def _lookup_name(ticker: yf.Ticker, symbol: str) -> str:
    """Best-effort name resolution. Never raises — falls back to the symbol."""
    try:
        info = ticker.info or {}
        name = info.get("longName") or info.get("shortName")
        if name:
            return name
    except Exception as e:
        log.warning("info lookup failed for %s: %r", symbol, e)
    try:
        fast = getattr(ticker, "fast_info", None)
        if fast is not None:
            name = fast.get("longName") if hasattr(fast, "get") else None
            if name:
                return name
    except Exception as e:
        log.warning("fast_info lookup failed for %s: %r", symbol, e)
    return symbol


def validate_ticker(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    if not symbol:
        return {"valid": False, "name": None}
    if symbol in _name_cache:
        return {"valid": True, "name": _name_cache[symbol]}

    try:
        ticker = yf.Ticker(symbol)
        hist = _with_retry(lambda: ticker.history(period="5d", auto_adjust=True))
    except Exception as e:
        log.warning("validate_ticker history fetch failed for %s: %r", symbol, e)
        return {"valid": False, "name": None}

    if hist is None or hist.empty:
        return {"valid": False, "name": None}

    name = _lookup_name(ticker, symbol)
    _name_cache[symbol] = name
    return {"valid": True, "name": name}


@lru_cache(maxsize=128)
def get_inception_date(symbol: str) -> date | None:
    symbol = symbol.strip().upper()
    try:
        hist = _with_retry(lambda: yf.Ticker(symbol).history(period="max", auto_adjust=True))
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    first = hist.index[0]
    if isinstance(first, pd.Timestamp):
        return first.date()
    if isinstance(first, datetime):
        return first.date()
    return None


def fetch_adjusted_prices(symbols: list[str], start: date, end: date) -> dict[str, pd.Series]:
    if not symbols:
        return {}

    symbols = [s.strip().upper() for s in symbols if s and s.strip()]

    df = _with_retry(
        lambda: yf.download(
            symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    )

    out: dict[str, pd.Series] = {}
    if df is None or df.empty:
        return out

    if isinstance(df.columns, pd.MultiIndex):
        for sym in symbols:
            if sym in df.columns.get_level_values(0):
                series = df[sym]["Close"].dropna()
                if not series.empty:
                    out[sym] = series
    else:
        series = df["Close"].dropna() if "Close" in df.columns else df.iloc[:, 0].dropna()
        if not series.empty and len(symbols) == 1:
            out[symbols[0]] = series

    return out
