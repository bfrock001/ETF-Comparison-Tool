"""Precompute the Screener tab's fund tables into static/data/fund_tables.json.

Run this locally (or on a schedule) to refresh the data the web app serves:

    python build_universe.py            # refresh only missing/failed tickers
    python build_universe.py --refresh  # refetch everything

The web app never fetches this data at request time — it just reads the JSON —
so the tab loads instantly and Yahoo rate limits stay out of the request path.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

from core import data_fetcher, screener
from core.universe import ASSET_CLASSES, expense_for, iter_all_tickers

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build_universe")

RISK_FREE_RATE = 0.04  # single assumption used for the Sharpe-style column
OUT_PATH = Path(__file__).parent / "static" / "data" / "fund_tables.json"
# Composition detail (holdings/sectors/ratios) precomputed here because Yahoo's
# quoteSummary endpoint is blocked from cloud IPs (Render), so the live app
# can't fetch it — see core/data_fetcher.get_fund_detail.
DETAILS_PATH = Path(__file__).parent / "static" / "data" / "fund_details.json"

_TYPE_MAP = {
    "ETF": "ETF",
    "MUTUALFUND": "Mutual Fund",
    "MONEYMARKET": "Money Market",
}


def _fetch_one(symbol: str) -> dict | None:
    """Fetch info + max history for one symbol and compute its metrics."""
    tk = yf.Ticker(symbol)
    try:
        info = tk.info or {}
    except Exception as e:
        log.warning("  %s: info failed (%r)", symbol, e)
        info = {}

    try:
        hist = tk.history(period="max", auto_adjust=True)
    except Exception as e:
        log.warning("  %s: history failed (%r)", symbol, e)
        return None
    if hist is None or hist.empty or "Close" not in hist:
        log.warning("  %s: no price history", symbol)
        return None
    # Yahoo occasionally serves a single stale row for a symbol mid-glitch
    # (e.g. after a share-class event). Treat too-short history as unresolved
    # rather than admitting an all-blank row.
    if len(hist["Close"].dropna()) < 5:
        log.warning("  %s: only %d price rows — skipping", symbol, len(hist))
        return None

    metrics = screener.compute(hist["Close"], RISK_FREE_RATE)

    quote_type = (info.get("quoteType") or "").upper()
    fund_type = _TYPE_MAP.get(quote_type, "Fund")
    expense = info.get("netExpenseRatio")
    if expense is None:
        ar = info.get("annualReportExpenseRatio")
        # annualReportExpenseRatio is a fraction (0.0004) — convert to percent.
        expense = round(ar * 100.0, 2) if isinstance(ar, (int, float)) else None
    expense = expense_for(symbol, expense)  # curated fee wins when we have one

    note = None
    if quote_type == "MONEYMARKET":
        note = "Money-market fund — Yahoo carries a flat $1.00 NAV, so price-based returns understate the true yield."

    return {
        "ticker": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "type": fund_type,
        "expense": expense,
        "aum": info.get("totalAssets"),
        "note": note,
        **metrics,
    }


def _load_cache() -> dict[str, dict]:
    if not OUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cache: dict[str, dict] = {}
    for cls in data.get("classes", []):
        for fund in cls.get("funds", []):
            cache[fund["ticker"]] = fund
    return cache


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="refetch every ticker")
    ap.add_argument("--delay", type=float, default=0.4, help="seconds between fetches")
    args = ap.parse_args()

    cache = {} if args.refresh else _load_cache()
    all_tickers = iter_all_tickers()
    log.info("Fetching %d unique tickers (%d cached)…", len(all_tickers), len(cache))

    funds: dict[str, dict] = dict(cache)
    for i, sym in enumerate(all_tickers, 1):
        if sym in funds and funds[sym].get("name"):
            continue
        log.info("[%d/%d] %s", i, len(all_tickers), sym)
        rec = _fetch_one(sym)
        if rec is not None:
            funds[sym] = rec
        time.sleep(args.delay)

    # A non-money-market fund with no computable return in any window is a data
    # glitch (see the min-rows guard above), so drop it. Money-market funds are
    # kept even with blank returns — they carry an explanatory note instead.
    _return_keys = ("ytd", "r1y", "r3y", "r5y", "r10y", "life")

    def _usable(rec: dict) -> bool:
        if rec.get("type") == "Money Market":
            return True
        return any(rec.get(k) is not None for k in _return_keys)

    # Assemble classes, dropping unresolved tickers and ranking by AUM.
    classes = []
    for cid, meta in ASSET_CLASSES.items():
        rows = [
            funds[t] for t in meta["tickers"]
            if t in funds and funds[t].get("name") and _usable(funds[t])
        ]
        # Re-apply curated fees so cached rows pick up override edits without a
        # full refetch.
        for r in rows:
            r["expense"] = expense_for(r["ticker"], r.get("expense"))
        rows.sort(key=lambda r: (r.get("aum") or 0), reverse=True)
        classes.append({
            "id": cid,
            "label": meta["label"],
            "group": meta["group"],
            "anchor": meta["anchor"],
            "funds": rows,
        })

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "risk_free_rate": RISK_FREE_RATE,
        "classes": classes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    resolved = sum(len(c["funds"]) for c in classes)
    log.info("Wrote %s — %d classes, %d fund rows.", OUT_PATH, len(classes), resolved)

    build_details(classes, refresh=args.refresh, delay=args.delay)
    return 0


def _load_details_cache() -> dict[str, dict]:
    if not DETAILS_PATH.exists():
        return {}
    try:
        return json.loads(DETAILS_PATH.read_text(encoding="utf-8")).get("funds", {})
    except Exception:
        return {}


def build_details(classes: list[dict], refresh: bool, delay: float) -> None:
    """Fetch composition detail (holdings/sectors/ratios) for every resolved
    fund and write fund_details.json. Runs where quoteSummary works (locally)."""
    tickers = sorted({f["ticker"] for c in classes for f in c["funds"]})
    cache = {} if refresh else _load_details_cache()
    log.info("Fetching detail for %d funds (%d cached)…", len(tickers), len(cache))

    details: dict[str, dict] = dict(cache)
    for i, sym in enumerate(tickers, 1):
        if sym in details and details[sym].get("name"):
            continue
        log.info("[detail %d/%d] %s", i, len(tickers), sym)
        try:
            d = data_fetcher.get_fund_detail(sym)
        except Exception as e:
            log.warning("  %s: detail failed (%r)", sym, e)
            d = None
        if d and d.get("name"):
            details[sym] = d
        time.sleep(delay)

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "funds": {t: details[t] for t in tickers if t in details},
    }
    DETAILS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %s — %d fund details.", DETAILS_PATH, len(payload["funds"]))


if __name__ == "__main__":
    sys.exit(main())
