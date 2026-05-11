"""Pure performance metrics. Inputs: pd.Series of adjusted prices. Outputs: floats."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def total_return(prices: pd.Series) -> float:
    if prices is None or prices.empty or len(prices) < 2:
        return float("nan")
    return ((prices.iloc[-1] / prices.iloc[0]) - 1.0) * 100.0


def cagr(prices: pd.Series) -> float:
    if prices is None or prices.empty or len(prices) < 2:
        return float("nan")
    start_date = prices.index[0]
    end_date = prices.index[-1]
    years = (end_date - start_date).days / 365.25
    if years <= 0:
        return float("nan")
    ratio = prices.iloc[-1] / prices.iloc[0]
    if ratio <= 0:
        return float("nan")
    return (ratio ** (1.0 / years) - 1.0) * 100.0


def max_drawdown(prices: pd.Series) -> float:
    if prices is None or prices.empty or len(prices) < 2:
        return float("nan")
    return ((prices / prices.cummax()) - 1.0).min() * 100.0


def annualized_volatility(prices: pd.Series) -> float:
    if prices is None or prices.empty or len(prices) < 2:
        return float("nan")
    log_returns = np.log(prices / prices.shift(1)).dropna()
    if log_returns.empty:
        return float("nan")
    return log_returns.std(ddof=1) * math.sqrt(252) * 100.0


def growth_of_1000(prices: pd.Series) -> dict:
    if prices is None or prices.empty:
        return {"dates": [], "values": []}
    normalized = (prices / prices.iloc[0]) * 1000.0
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in normalized.index],
        "values": [round(float(v), 2) for v in normalized.values],
    }
