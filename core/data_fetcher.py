"""Yahoo Finance data access. All public functions return plain Python types."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from functools import lru_cache

import pandas as pd
import yfinance as yf

from core.universe import expense_for


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


# --- Fund detail (holdings / sectors / composition / ratios) ---------------

_SECTOR_LABELS = {
    "realestate": "Real Estate", "consumer_cyclical": "Consumer Cyclical",
    "basic_materials": "Basic Materials", "consumer_defensive": "Consumer Defensive",
    "technology": "Technology", "communication_services": "Communication Services",
    "financial_services": "Financial Services", "utilities": "Utilities",
    "industrials": "Industrials", "energy": "Energy", "healthcare": "Healthcare",
}
_RATING_LABELS = {
    "us_government": "US Government", "aaa": "AAA", "aa": "AA", "a": "A",
    "bbb": "BBB", "bb": "BB", "b": "B", "below_b": "Below B", "other": "Other",
}
_TYPE_MAP = {"ETF": "ETF", "MUTUALFUND": "Mutual Fund", "MONEYMARKET": "Money Market"}


def _num(x):
    """Coerce a value to float, treating NaN/NA/None as None."""
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def _ratio(v):
    """Yahoo stores fund valuation ratios as reciprocals (P/E 0.04 -> 24.7);
    invert small fractions back to a real ratio, round to 2dp."""
    v = _num(v)
    if v is None or v == 0:
        return None
    return round(1.0 / v, 2) if 0 < v < 1 else round(v, 2)


def get_live_price(symbol: str) -> dict | None:
    """Current price + day change via the history/chart endpoint, which (unlike
    quoteSummary) works from cloud IPs. Not cached — callers want it fresh."""
    symbol = symbol.strip().upper()
    try:
        hist = _with_retry(lambda: yf.Ticker(symbol).history(period="5d", auto_adjust=False))
    except Exception as e:
        log.warning("live price failed for %s: %r", symbol, e)
        return None
    if hist is None or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
    change = (last - prev) if prev else None
    pct = ((last / prev - 1.0) * 100.0) if prev else None
    return {
        "price": round(last, 4),
        "change": round(change, 4) if change is not None else None,
        "change_pct": round(pct, 4) if pct is not None else None,
    }


@lru_cache(maxsize=256)
def get_fund_detail(symbol: str) -> dict | None:
    """Composition detail for one fund. Sections absent from Yahoo come back
    empty (bond funds have no equity holdings, etc.). Cached per process."""
    symbol = symbol.strip().upper()
    tk = yf.Ticker(symbol)
    try:
        info = _with_retry(lambda: tk.info) or {}
    except Exception as e:
        log.warning("fund_detail info failed for %s: %r", symbol, e)
        info = {}

    name = info.get("longName") or info.get("shortName")
    if not name:
        return None

    expense = info.get("netExpenseRatio")
    if expense is None:
        ar = info.get("annualReportExpenseRatio")
        expense = round(ar * 100.0, 2) if isinstance(ar, (int, float)) else None
    expense = expense_for(symbol, expense)

    yld = _num(info.get("yield"))
    out: dict = {
        "ticker": symbol,
        "name": name,
        "type": _TYPE_MAP.get((info.get("quoteType") or "").upper(), "Fund"),
        "category": info.get("category"),
        "family": info.get("fundFamily"),
        "currency": info.get("currency"),
        "price": _num(info.get("regularMarketPrice")) or _num(info.get("navPrice")),
        "change": _num(info.get("regularMarketChange")),
        "change_pct": _num(info.get("regularMarketChangePercent")),
        "expense": expense,
        "aum": info.get("totalAssets"),
        "yield": round(yld * 100.0, 2) if yld is not None else None,
        "description": (info.get("longBusinessSummary") or "").strip() or None,
        "holdings": [], "sectors": [], "composition": {},
        "equity": {}, "bond_ratings": [],
    }

    try:
        fd = tk.funds_data
    except Exception:
        fd = None
    if fd is None:
        return out

    try:
        desc = fd.description
        if desc and isinstance(desc, str) and desc.strip():
            out["description"] = desc.strip()
    except Exception:
        pass

    try:
        th = fd.top_holdings
        if th is not None and len(th):
            for sym, row in th.iterrows():
                pct = _num(row.get("Holding Percent"))
                out["holdings"].append({
                    "symbol": str(sym),
                    "name": row.get("Name") if not pd.isna(row.get("Name")) else str(sym),
                    "pct": round(pct * 100.0, 2) if pct is not None else None,
                })
    except Exception as e:
        log.warning("top_holdings failed for %s: %r", symbol, e)

    try:
        for k, v in (fd.sector_weightings or {}).items():
            fv = _num(v)
            if fv:
                out["sectors"].append({"name": _SECTOR_LABELS.get(k, k), "pct": round(fv * 100.0, 2)})
        out["sectors"].sort(key=lambda s: -s["pct"])
    except Exception as e:
        log.warning("sector_weightings failed for %s: %r", symbol, e)

    try:
        ac = fd.asset_classes or {}
        other = (_num(ac.get("otherPosition")) or 0) + (_num(ac.get("preferredPosition")) or 0) \
            + (_num(ac.get("convertiblePosition")) or 0)
        out["composition"] = {
            "stock": round((_num(ac.get("stockPosition")) or 0) * 100.0, 2),
            "bond": round((_num(ac.get("bondPosition")) or 0) * 100.0, 2),
            "cash": round((_num(ac.get("cashPosition")) or 0) * 100.0, 2),
            "other": round(other * 100.0, 2),
        }
    except Exception as e:
        log.warning("asset_classes failed for %s: %r", symbol, e)

    try:
        eh = fd.equity_holdings
        if eh is not None and len(eh.columns):
            fcol = eh.columns[0]
            has_cat = "Category Average" in eh.columns

            def val(label, col):
                return eh.loc[label, col] if label in eh.index else None

            mcap = _num(val("Median Market Cap", fcol))
            g3 = _num(val("3 Year Earnings Growth", fcol))
            eq = {
                "pe": _ratio(val("Price/Earnings", fcol)),
                "pb": _ratio(val("Price/Book", fcol)),
                "ps": _ratio(val("Price/Sales", fcol)),
                "pcf": _ratio(val("Price/Cashflow", fcol)),
                "median_mktcap": round(mcap, 0) if mcap is not None else None,
                "growth3y": round(g3, 2) if g3 is not None else None,
            }
            if has_cat:
                eq["cat"] = {
                    "pe": _ratio(val("Price/Earnings", "Category Average")),
                    "pb": _ratio(val("Price/Book", "Category Average")),
                    "ps": _ratio(val("Price/Sales", "Category Average")),
                    "pcf": _ratio(val("Price/Cashflow", "Category Average")),
                }
            if any(v is not None for k, v in eq.items() if k != "cat"):
                out["equity"] = eq
    except Exception as e:
        log.warning("equity_holdings failed for %s: %r", symbol, e)

    try:
        ratings = fd.bond_ratings or {}
        # Fixed credit-quality order (matches how fund pages present it).
        for k in ("us_government", "aaa", "aa", "a", "bbb", "bb", "b", "below_b", "other"):
            fv = _num(ratings.get(k))
            if fv and fv > 0:
                out["bond_ratings"].append({"label": _RATING_LABELS[k], "pct": round(fv * 100.0, 2)})
        # An all-"Other" bucket (typical for equity funds) isn't informative.
        if len(out["bond_ratings"]) == 1 and out["bond_ratings"][0]["label"] == "Other":
            out["bond_ratings"] = []
    except Exception as e:
        log.warning("bond_ratings failed for %s: %r", symbol, e)

    return out
