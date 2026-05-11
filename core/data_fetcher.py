"""Yahoo Finance data access. All public functions return plain Python types."""

from __future__ import annotations

import time
from datetime import date, datetime
from functools import lru_cache

import pandas as pd
import requests
import yfinance as yf


_RETRY_DELAYS = (0.5, 1.5, 4.0)
_RETRYABLE = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.HTTPError,
)


def _with_retry(func, *args, **kwargs):
    last_exc = None
    for delay in (*_RETRY_DELAYS, None):
        try:
            return func(*args, **kwargs)
        except _RETRYABLE as e:
            last_exc = e
            if delay is None:
                raise
            time.sleep(delay)
    if last_exc:
        raise last_exc


@lru_cache(maxsize=128)
def validate_ticker(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    if not symbol:
        return {"valid": False, "name": None}
    try:
        info = _with_retry(lambda: yf.Ticker(symbol).info) or {}
    except Exception:
        return {"valid": False, "name": None}

    name = info.get("longName") or info.get("shortName")
    if not name:
        return {"valid": False, "name": None}
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
