"""Per-fund screener metrics computed from adjusted-close history.

Return conventions follow the way fund tables (Morningstar/Yahoo) are usually
read:
  - YTD and 1-year are cumulative total returns.
  - 3 / 5 / 10-year and life-of-fund are *annualized* (CAGR).
A cell is None when the fund is younger than the window; the UI shows "—".

The risk-adjusted column is a Sharpe-style ratio over the trailing window (up to
5 years, so a 30-year fund is comparable to a 5-year one), using a single
risk-free assumption.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

TRADING_DAYS = 252
SHARPE_WINDOW_YEARS = 5


def _price_asof(prices: pd.Series, target: date):
    """Last price on or before `target`, or None if the history starts later."""
    ts = pd.Timestamp(target)
    if prices.index.tz is not None:
        ts = ts.tz_localize(prices.index.tz)
    window = prices.loc[:ts]
    if window.empty:
        return None
    return float(window.iloc[-1])


def _annualized(ratio: float, years: float) -> float:
    return (ratio ** (1.0 / years) - 1.0) * 100.0


def compute(prices: pd.Series, risk_free_rate: float) -> dict:
    """Return a dict of screener metrics (percentages, rounded) for one fund.

    `risk_free_rate` is a decimal (e.g. 0.04). Fields that cannot be computed
    from the available history come back as None.
    """
    out = {
        "ytd": None, "r1y": None, "r3y": None, "r5y": None, "r10y": None,
        "life": None, "vol": None, "mdd": None, "sharpe": None,
        "inception": None,
    }
    if prices is None or prices.empty or len(prices) < 2:
        return out

    prices = prices.dropna()
    if len(prices) < 2:
        return out

    last = float(prices.iloc[-1])
    last_date = prices.index[-1].date()
    first_date = prices.index[0].date()
    out["inception"] = first_date.isoformat()

    # YTD — cumulative from the first trading day of the current year.
    jan1 = date(last_date.year, 1, 1)
    prev_close = _price_asof(prices, jan1 - timedelta(days=1))
    if prev_close and prev_close > 0:
        out["ytd"] = round((last / prev_close - 1.0) * 100.0, 2)

    # Trailing windows.
    for years, key, annualize in (
        (1, "r1y", False),
        (3, "r3y", True),
        (5, "r5y", True),
        (10, "r10y", True),
    ):
        target = last_date - timedelta(days=round(365.25 * years))
        if first_date > target:
            continue  # fund younger than the window
        base = _price_asof(prices, target)
        if not base or base <= 0:
            continue
        ratio = last / base
        if ratio <= 0:
            continue
        out[key] = round(_annualized(ratio, years) if annualize else (ratio - 1.0) * 100.0, 2)

    # Life-of-fund, annualized.
    life_years = (last_date - first_date).days / 365.25
    first_price = float(prices.iloc[0])
    if life_years > 0 and first_price > 0 and last / first_price > 0:
        out["life"] = round(_annualized(last / first_price, life_years), 2)

    # Volatility & max drawdown over full history.
    log_ret = np.log(prices / prices.shift(1)).dropna()
    if not log_ret.empty:
        out["vol"] = round(float(log_ret.std(ddof=1)) * math.sqrt(TRADING_DAYS) * 100.0, 2)
    out["mdd"] = round(float((prices / prices.cummax() - 1.0).min()) * 100.0, 2)

    # Sharpe-style ratio over the trailing window (≤ 5y).
    window_start = pd.Timestamp(last_date - timedelta(days=round(365.25 * SHARPE_WINDOW_YEARS)))
    if prices.index.tz is not None:
        window_start = window_start.tz_localize(prices.index.tz)
    win = prices.loc[window_start:]
    if len(win) > 30:
        win_years = (win.index[-1] - win.index[0]).days / 365.25
        wlog = np.log(win / win.shift(1)).dropna()
        if win_years > 0 and not wlog.empty:
            ann_ret = _annualized(float(win.iloc[-1]) / float(win.iloc[0]), win_years) / 100.0
            ann_vol = float(wlog.std(ddof=1)) * math.sqrt(TRADING_DAYS)
            if ann_vol > 0:
                out["sharpe"] = round((ann_ret - risk_free_rate) / ann_vol, 2)

    return out
