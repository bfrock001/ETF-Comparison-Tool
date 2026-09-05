"""ETF & Mutual Fund Comparison Tool — Flask entrypoint."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from core import data_fetcher, metrics, utils


app = Flask(__name__)

SCREENER_DATA = Path(app.root_path) / "static" / "data" / "fund_tables.json"
FUND_DETAILS = Path(app.root_path) / "static" / "data" / "fund_details.json"

_details_cache: dict | None = None


def _load_details() -> dict:
    """Precomputed fund detail, loaded once. Rebuilt on each deploy/restart."""
    global _details_cache
    if _details_cache is None:
        try:
            _details_cache = json.loads(FUND_DETAILS.read_text(encoding="utf-8"))
        except Exception:
            _details_cache = {"generated": None, "funds": {}}
    return _details_cache


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/terms")
def terms():
    return render_template("terms.html")


@app.get("/api/screener")
def api_screener():
    """Serve the precomputed asset-class fund tables (built by build_universe.py)."""
    if not SCREENER_DATA.exists():
        return jsonify({"error": "Fund tables have not been generated yet."}), 503
    resp = send_file(SCREENER_DATA, mimetype="application/json")
    # Revalidate every time (ETag/Last-Modified give cheap 304s) so a rebuild is
    # picked up immediately rather than being masked by a stale cached copy.
    resp.headers["Cache-Control"] = "no-cache"
    return resp


_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,15}$")


@app.get("/api/fund/<ticker>")
def api_fund(ticker):
    """Composition detail (holdings, sectors, ratios) for one fund.

    Served from precomputed data (Yahoo's quoteSummary endpoint is blocked from
    cloud IPs, so it can't be fetched live in production). Falls back to a live
    fetch only for tickers outside the curated universe — which works locally
    but may be unavailable on hosts where quoteSummary is blocked.
    """
    ticker = (ticker or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400

    data = _load_details()
    fund = (data.get("funds") or {}).get(ticker)
    if fund:
        out = dict(fund)
        out["as_of"] = data.get("generated")
        # Composition is a snapshot, but refresh the price live (history endpoint
        # works from cloud IPs, unlike the composition source).
        live = data_fetcher.get_live_price(ticker)
        if live and live.get("price") is not None:
            out.update(live)
            out["price_live"] = True
        return jsonify(out)

    # Not in the precomputed set — attempt a live fetch (works where
    # quoteSummary is reachable).
    try:
        detail = data_fetcher.get_fund_detail(ticker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not detail:
        return jsonify({
            "error": f"Detailed data for {ticker} isn't available "
                     "(it's outside the Fund Finder's covered set).",
        }), 404
    return jsonify(detail)


@app.get("/api/fund_row/<ticker>")
def api_fund_row(ticker):
    """A screener-table row for one fund, computed live — powers the Fund
    Finder's "look up any fund" box.

    Same shape as the precomputed rows in fund_tables.json. Returns/Sharpe come
    from price history (works everywhere); expense/AUM come from `info`
    (quoteSummary), which may be blank on hosts where that endpoint is blocked.
    """
    ticker = (ticker or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400
    try:
        row = data_fetcher.get_fund_row(ticker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not row:
        return jsonify({
            "error": f"No Yahoo Finance data for {ticker}.",
        }), 404
    return jsonify(row)


@app.get("/api/validate")
def api_validate():
    ticker = request.args.get("ticker", "").strip()
    if not ticker:
        return jsonify({"valid": False, "name": None}), 400
    return jsonify(data_fetcher.validate_ticker(ticker))


@app.post("/api/compare")
def api_compare():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        tickers_raw = payload.get("tickers") or []
        tickers = [t.strip().upper() for t in tickers_raw if t and t.strip()]
        if not tickers:
            return jsonify({"error": "No tickers provided."}), 400

        req_start, req_end = utils.resolve_period(
            payload.get("period"),
            payload.get("start_date"),
            payload.get("end_date"),
        )

        validated: dict[str, dict] = {}
        skipped: list[str] = []
        for t in tickers:
            v = data_fetcher.validate_ticker(t)
            if v["valid"]:
                validated[t] = v
            else:
                skipped.append(t)

        if not validated:
            return jsonify({
                "error": "None of the supplied tickers were valid.",
                "skipped": skipped,
            }), 400

        inceptions: dict[str, date] = {}
        for t in validated:
            inc = data_fetcher.get_inception_date(t)
            if inc is not None:
                inceptions[t] = inc

        common_start, warning = utils.find_common_start(inceptions, req_start)
        if common_start >= req_end:
            return jsonify({
                "error": "Resolved start date is after end date — adjust the period.",
                "common_start": common_start.isoformat(),
                "common_end": req_end.isoformat(),
                "skipped": skipped,
            }), 400

        price_map = data_fetcher.fetch_adjusted_prices(
            list(validated.keys()), common_start, req_end
        )

        results = []
        for t, meta in validated.items():
            series = price_map.get(t)
            if series is None or series.empty:
                skipped.append(t)
                continue

            results.append({
                "ticker": t,
                "name": meta["name"],
                "total_return": round(metrics.total_return(series), 2),
                "cagr": round(metrics.cagr(series), 2),
                "max_drawdown": round(metrics.max_drawdown(series), 2),
                "volatility": round(metrics.annualized_volatility(series), 2),
                "inception_date": inceptions[t].isoformat() if t in inceptions else None,
                "data_start_used": series.index[0].strftime("%Y-%m-%d"),
                "growth_series": metrics.growth_of_1000(series),
            })

        return jsonify({
            "common_start": common_start.isoformat(),
            "common_end": req_end.isoformat(),
            "warning": warning,
            "skipped": skipped,
            "results": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
