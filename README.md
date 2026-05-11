# ETF & Mutual Fund Comparison Tool

A single-page web app for side-by-side comparison of up to five ETFs or mutual funds. Uses dividend-adjusted prices from Yahoo Finance and renders four interactive charts plus a summary table.

## Features

- Compare up to **5 tickers** at a time (ETF or mutual fund)
- **Live ticker validation** against Yahoo Finance with fund-name lookup
- Preset periods (**YTD, 1Y, 3Y, 5Y, 10Y**) or **custom date range**
- Automatic **common-start-date** logic with a warning banner when one ticker's history truncates the comparison
- **Four charts** (Chart.js):
  - Total Return (bar)
  - Annualized Volatility (bar)
  - Max Drawdown (bar)
  - Growth of $1,000 (line)
- **Summary table** with fund name, ticker, total return, CAGR, max drawdown, volatility, inception date, and data-start used

All performance metrics are computed from `auto_adjust=True` Yahoo Finance prices — dividends and splits are reinvested automatically.

## Local development

Requires Python 3.12+.

```powershell
python -m venv --copies .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app run
```

Then open <http://127.0.0.1:5000/>.

> On Windows: if `python -m venv` fails with `[WinError 2]`, pass `--copies` (the default symlinks need Developer Mode).

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Renders the SPA |
| `/api/validate?ticker=VOO` | GET | Returns `{valid: bool, name: string\|null}` |
| `/api/compare` | POST | Compares tickers — see schema below |

`POST /api/compare` body:

```json
{
  "tickers": ["VOO", "QQQ", "SCHD"],
  "period": "5Y",
  "start_date": null,
  "end_date": null
}
```

`period` accepts `YTD`, `1Y`, `3Y`, `5Y`, `10Y`. If `start_date` or `end_date` (ISO `YYYY-MM-DD`) is set, they override `period`.

Response:

```json
{
  "common_start": "2021-05-11",
  "common_end": "2026-05-10",
  "warning": null,
  "skipped": [],
  "results": [
    {
      "ticker": "VOO",
      "name": "Vanguard S&P 500 ETF",
      "total_return": 91.19,
      "cagr": 13.87,
      "max_drawdown": -24.52,
      "volatility": 16.84,
      "inception_date": "2010-09-09",
      "data_start_used": "2021-05-11",
      "growth_series": { "dates": ["..."], "values": [1000.0, ...] }
    }
  ]
}
```

When ticker histories differ, `common_start` shifts to the latest inception date and `warning` describes the truncation.

## Deployment (Render)

This repo is configured for one-click deploy on [Render](https://render.com):

1. Push the repo to GitHub.
2. In Render, click **New → Blueprint** and point it at the repo. Render reads `render.yaml` automatically.
3. Alternatively, **New → Web Service**, select the repo, and Render auto-detects `Procfile` and `runtime.txt`.

The free tier sleeps after 15 min of inactivity; first request after a sleep takes ~30s to wake.

For **Railway** or other Procfile-aware hosts, no extra config is needed — `Procfile` and `runtime.txt` are standard.

## Repository layout

```
app.py                 Flask entrypoint, two API routes
core/
  data_fetcher.py      Yahoo Finance access (validate, inception, prices) with retry/backoff
  metrics.py           Pure performance math (total return, CAGR, drawdown, volatility, growth-of-$1k)
  utils.py             Period resolution and common-start logic
templates/index.html   SPA shell
static/
  css/styles.css       Dashboard styles
  js/main.js           Form handling, validation, API calls
  js/charts.js         Four Chart.js renderers, shared palette
Procfile               Gunicorn start command for Render/Railway
render.yaml            Render Blueprint config
runtime.txt            Python 3.12.10 pin
requirements.txt       Pinned dependencies (Flask, yfinance, pandas, numpy, gunicorn)
```

## Disclaimer

This tool is provided for informational and educational purposes only and is offered on an "as is" and "as available" basis without warranties of any kind, either express or implied. While reasonable efforts are made to ensure accuracy, completeness, and timeliness of the information, no guarantee is made that the results will be error-free, reliable, or suitable for any particular purpose.

The provider does not assume any responsibility or liability for any errors, omissions, inaccuracies, or outcomes resulting from the use of this tool. Users assume full responsibility for any decisions made based on the information provided.

This tool does not constitute financial, investment, tax, or legal advice. Nothing contained herein should be interpreted as a recommendation to buy, sell, or hold any security or investment strategy. Users should consult a qualified financial advisor or other professional before making any investment decisions.

Past performance is not indicative of future results. All investments involve risk, including the possible loss of principal.

The tool may rely on third-party data sources, which may be delayed, incomplete, or inaccurate, and the provider is not responsible for such data.

Use of this tool does not create any fiduciary relationship between the user and the provider.
