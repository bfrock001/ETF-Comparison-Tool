"""ETF & Mutual Fund Comparison Tool — Flask entrypoint."""

from __future__ import annotations

import os
from datetime import date

from flask import Flask, jsonify, render_template, request

from core import data_fetcher, metrics, utils


app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/terms")
def terms():
    return render_template("terms.html")


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
