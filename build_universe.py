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

from core import data_fetcher, discovery
from core.universe import ASSET_CLASSES, expense_for, iter_all_tickers

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build_universe")

RISK_FREE_RATE = 0.04  # single assumption used for the Sharpe-style column
OUT_PATH = Path(__file__).parent / "static" / "data" / "fund_tables.json"
# Composition detail (holdings/sectors/ratios) precomputed here because Yahoo's
# quoteSummary endpoint is blocked from cloud IPs (Render), so the live app
# can't fetch it — see core/data_fetcher.get_fund_detail.
DETAILS_PATH = Path(__file__).parent / "static" / "data" / "fund_details.json"

def _fetch_one(symbol: str) -> dict | None:
    """Fetch info + max history for one symbol and compute its screener row.

    Delegates to ``data_fetcher.get_fund_row`` so a precomputed row and a
    live-looked-up one (the Fund Finder's type-in feature) are computed
    identically. The returned record includes Yahoo's ``category``, which
    ``discovery.classify`` uses to slot auto-discovered ETFs into a class.
    """
    return data_fetcher.get_fund_row(symbol, RISK_FREE_RATE)


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
    ap.add_argument("--discover", type=int, default=300, metavar="N",
                    help="also pull the N largest US ETFs via the Yahoo screener "
                         "and auto-classify them (0 disables discovery)")
    args = ap.parse_args()

    cache = {} if args.refresh else _load_cache()
    curated = iter_all_tickers()
    curated_set = set(curated)

    # Auto-discovery: the N largest US ETFs from the Yahoo screener, minus
    # leveraged/inverse/tiny funds. Degrades to [] if the screener is
    # unreachable, so the build still runs on the curated universe alone.
    discovered = discovery.discover_etfs(limit=args.discover)
    log.info("Discovery: %d candidate ETFs from the screener.", len(discovered))
    disc_new = [d["symbol"] for d in discovered if d["symbol"] not in curated_set]

    all_tickers = curated + [s for s in disc_new if s not in curated_set]
    log.info("Fetching %d unique tickers (%d curated + %d discovered, %d cached)…",
             len(all_tickers), len(curated), len(disc_new), len(cache))

    funds: dict[str, dict] = dict(cache)
    for i, sym in enumerate(all_tickers, 1):
        if sym in funds and funds[sym].get("name"):
            continue
        log.info("[%d/%d] %s", i, len(all_tickers), sym)
        rec = _fetch_one(sym)
        if rec is not None:
            funds[sym] = rec
        time.sleep(args.delay)

    # Class membership = curated lists, plus each discovered ETF classified by
    # Yahoo's category (name heuristics resolve the ambiguous style boxes).
    class_members: dict[str, list[str]] = {
        cid: list(meta["tickers"]) for cid, meta in ASSET_CLASSES.items()
    }
    classified = 0
    for sym in disc_new:
        rec = funds.get(sym)
        if not rec or not rec.get("name"):
            continue
        cid = discovery.classify(rec.get("category"), rec.get("name"))
        if cid and cid not in discovery.UNRELIABLE_CLASSES and sym not in class_members[cid]:
            class_members[cid].append(sym)
            rec["discovered"] = True
            classified += 1
    log.info("Discovery: %d ETFs classified into asset classes.", classified)

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
            funds[t] for t in class_members[cid]
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


def _healthy(funds: dict) -> int:
    return sum(1 for f in funds.values() if f.get("name") and f.get("composition"))


def build_details(classes: list[dict], refresh: bool, delay: float) -> None:
    """Fetch composition detail (holdings/sectors/ratios) for every resolved
    fund and write fund_details.json.

    Yahoo's quoteSummary endpoint is blocked from datacenter IPs (CI, cloud), so
    this only succeeds from a residential connection. To stay safe when run
    somewhere it's blocked, it (a) trips a circuit breaker after a run of
    failures and (b) refuses to overwrite a healthy existing file with a thin
    result — so a scheduled CI run refreshes the tables but preserves details.
    """
    tickers = sorted({f["ticker"] for c in classes for f in c["funds"]})
    existing = _load_details_cache()
    cache = {} if refresh else existing
    log.info("Fetching detail for %d funds (%d cached)…", len(tickers), len(cache))

    details: dict[str, dict] = dict(cache)
    consecutive_fail = 0
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
            consecutive_fail = 0
        else:
            consecutive_fail += 1
            if consecutive_fail >= 12 and _healthy(details) < 5:
                log.warning("quoteSummary looks blocked (%d straight failures) — "
                            "aborting detail refresh, keeping existing file.", consecutive_fail)
                return
        time.sleep(delay)

    new_healthy = _healthy({t: details[t] for t in tickers if t in details})
    if DETAILS_PATH.exists() and new_healthy < max(0.6 * len(tickers), 0.6 * _healthy(existing)):
        log.warning("Only %d healthy details of %d — keeping existing file rather "
                    "than overwriting with a thin result.", new_healthy, len(tickers))
        return

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "funds": {t: details[t] for t in tickers if t in details and details[t].get("name")},
    }
    DETAILS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %s — %d fund details.", DETAILS_PATH, len(payload["funds"]))


if __name__ == "__main__":
    sys.exit(main())
