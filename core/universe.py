"""Curated fund universe for the Screener tab.

There is no free screener API (yfinance can only look up funds you name), so the
candidate set for each asset class is maintained by hand here. The build pipeline
(`build_universe.py`) then resolves each ticker against Yahoo Finance, drops any
that fail, and ranks the survivors by AUM — so the ordering below is not
significant, only the membership is.

`anchor` is the user's preferred fund for the class (highlighted in the UI).
Keep families diverse (Vanguard / Fidelity / Schwab / iShares / SPDR / State
Street) so fees and returns can compete head-to-head.
"""

from __future__ import annotations

# Display groups, in dropdown order.
GROUPS = ["US Equity", "International Equity", "Fixed Income", "Alternatives"]

# Verified net expense ratios (percent) for the curated MUTUAL FUNDS and money-
# market funds. Yahoo's fee data is accurate for ETFs but unreliable for funds
# (e.g. it lists FXAIX at 0.62% when the true figure is 0.015%), so these take
# precedence when present; ETFs fall back to Yahoo's netExpenseRatio.
#
# >>> This is the place to correct any fee the tool shows. Values are public and
#     change rarely; re-check against the fund's own fact sheet if in doubt. <<<
EXPENSE_OVERRIDES: dict[str, float] = {
    # Total Market
    "VTSAX": 0.04, "FSKAX": 0.015, "SWTSX": 0.03, "FZROX": 0.00, "VTSMX": 0.14,
    # Large Cap Blend
    "VFIAX": 0.04, "FXAIX": 0.015, "SWPPX": 0.02,
    # Large Cap Value
    "VVIAX": 0.05, "DODGX": 0.51, "FLCOX": 0.035,
    # Mid Cap Value
    "VMVAX": 0.07,
    # Mid Cap Growth
    "VMGMX": 0.07, "VMGRX": 0.36,
    # Small Cap Value
    "VSIAX": 0.07,
    # Small Cap Growth
    "VSGAX": 0.07,
    # Intl Developed
    "VTMGX": 0.07, "FSPSX": 0.035, "SWISX": 0.06, "VDVIX": 0.16,
    # Emerging Markets
    "VEMAX": 0.14, "FPADX": 0.075,
    # Total International
    "VTIAX": 0.09, "FTIHX": 0.06, "VFWAX": 0.11, "VGTSX": 0.17,
    # Total Bond
    "VBTLX": 0.05, "FXNAX": 0.025, "SWAGX": 0.04,
    # Corp Bonds
    "VICSX": 0.07, "VWESX": 0.20, "FCBFX": 0.45,
    # LT Treasury
    "VLGSX": 0.07, "VUSTX": 0.20,
    # Interm Treasury
    "VSIGX": 0.07, "FUAMX": 0.03, "VFITX": 0.20,
    # TIPS
    "VAIPX": 0.10, "VIPSX": 0.20, "FIPDX": 0.05,
    # REIT
    "VGSLX": 0.13, "FSRNX": 0.07, "TRREX": 0.65,
    # Money-market (ST T-Bills)
    "VUSXX": 0.09, "VMFXX": 0.11,
}


def expense_for(ticker: str, yahoo_value: float | None) -> float | None:
    """Curated expense ratio when we have one, else Yahoo's value."""
    return EXPENSE_OVERRIDES.get(ticker.upper(), yahoo_value)

# id -> metadata. `tickers` is the full candidate universe (includes the anchor).
ASSET_CLASSES: dict[str, dict] = {
    # ---- US Equity ----------------------------------------------------------
    "total-market-us": {
        "label": "Total Market (US)",
        "group": "US Equity",
        "anchor": "VTSAX",
        "tickers": [
            "VTSAX", "VTI", "FSKAX", "ITOT", "SCHB", "SWTSX", "FZROX",
            "SPTM", "IWV", "VTSMX",
        ],
    },
    "large-cap-blend": {
        "label": "Large Cap Blend",
        "group": "US Equity",
        "anchor": "VFIAX",
        "tickers": [
            "VFIAX", "VOO", "IVV", "SPY", "FXAIX", "SWPPX", "SPLG",
            "SCHX", "VV", "IWB",
        ],
    },
    "large-cap-value": {
        "label": "Large Cap Value",
        "group": "US Equity",
        "anchor": "VVIAX",
        "tickers": [
            "VVIAX", "VTV", "IWD", "SCHV", "DODGX", "SPYV", "VONV",
            "VLUE", "FLCOX", "IVE",
        ],
    },
    "mid-cap-value": {
        "label": "Mid Cap Value",
        "group": "US Equity",
        "anchor": "VMVAX",
        "tickers": [
            "VMVAX", "VOE", "IWS", "IJJ", "IVOV", "XMVM", "FLQM",
        ],
    },
    "mid-cap-growth": {
        "label": "Mid Cap Growth",
        "group": "US Equity",
        "anchor": "VMGMX",
        "tickers": [
            "VMGMX", "VOT", "IWP", "IMCG", "VMGRX", "SPMD", "EFG",
            "XMMO", "PWB",
        ],
    },
    "small-cap-value": {
        "label": "Small Cap Value",
        "group": "US Equity",
        "anchor": "VSIAX",
        "tickers": [
            "VSIAX", "VBR", "AVUV", "IWN", "IJS", "SLYV", "DFSV", "VTWV",
        ],
    },
    "small-cap-growth": {
        "label": "Small Cap Growth",
        "group": "US Equity",
        "anchor": "VSGAX",
        "tickers": [
            "VSGAX", "VBK", "IWO", "IJT", "SLYG", "VTWG", "GSSC",
            "XSMO", "PSCG",
        ],
    },
    # ---- International Equity ------------------------------------------------
    "intl-developed": {
        "label": "Intl Developed",
        "group": "International Equity",
        "anchor": "VTMGX",
        "tickers": [
            "VTMGX", "VEA", "IEFA", "SCHF", "EFA", "FSPSX", "SWISX",
            "IDEV", "SPDW", "VDVIX",
        ],
    },
    "emerging-markets": {
        "label": "Emerging Markets",
        "group": "International Equity",
        "anchor": "VEMAX",
        "tickers": [
            "VEMAX", "VWO", "IEMG", "EEM", "SCHE", "SPEM", "FPADX",
            "DGS",
        ],
    },
    "total-international": {
        "label": "Total International",
        "group": "International Equity",
        "anchor": "VTIAX",
        "tickers": [
            "VTIAX", "VXUS", "IXUS", "VEU", "FTIHX", "ACWX", "CWI",
            "VFWAX", "VGTSX",
        ],
    },
    # ---- Fixed Income -------------------------------------------------------
    "total-bond": {
        "label": "Total Bond Market",
        "group": "Fixed Income",
        "anchor": "VBTLX",
        "tickers": [
            "VBTLX", "BND", "AGG", "FXNAX", "SCHZ", "SWAGX", "SPAB",
            "BNDW", "IUSB",
        ],
    },
    "corp-bonds": {
        "label": "Corp Bonds",
        "group": "Fixed Income",
        "anchor": "VICSX",
        "tickers": [
            "VICSX", "LQD", "VCIT", "VCSH", "IGIB", "SPIB", "USIG",
            "VWESX", "FCBFX",
        ],
    },
    "lt-treasury": {
        "label": "LT Treasury",
        "group": "Fixed Income",
        "anchor": "VLGSX",
        "tickers": [
            "VLGSX", "TLT", "VGLT", "SPTL", "EDV", "TLH", "VUSTX",
            "GOVZ",
        ],
    },
    "interm-treasury": {
        "label": "Interm Treasury",
        "group": "Fixed Income",
        "anchor": "VSIGX",
        "tickers": [
            "VSIGX", "IEF", "VGIT", "SPTI", "IEI", "SCHR", "FUAMX",
            "VFITX",
        ],
    },
    "tips": {
        "label": "TIPS",
        "group": "Fixed Income",
        "anchor": "TIP",
        "tickers": [
            "TIP", "SCHP", "VTIP", "VAIPX", "STIP", "SPIP", "FIPDX",
            "TDTT", "VIPSX",
        ],
    },
    "st-tbills": {
        "label": "ST T-Bills",
        "group": "Fixed Income",
        "anchor": "VUSXX",
        # Money-market funds (VUSXX, VMFXX) carry a flat $1.00 NAV on Yahoo, so
        # price-based returns are meaningless — flagged at build time, and the
        # T-bill ETFs (SGOV/BIL/SHV...) are what actually compute here.
        "tickers": [
            "VUSXX", "SGOV", "BIL", "SHV", "GBIL", "TBIL", "USFR",
            "SHY", "VMFXX", "SPAXX",
        ],
    },
    # ---- Alternatives -------------------------------------------------------
    "reit": {
        "label": "REIT",
        "group": "Alternatives",
        "anchor": "VGSLX",
        "tickers": [
            "VGSLX", "VNQ", "SCHH", "XLRE", "IYR", "USRT", "FSRNX",
            "ICF", "RWR", "TRREX",
        ],
    },
    "gold": {
        "label": "Gold",
        "group": "Alternatives",
        "anchor": "IAU",
        # Gold-bullion funds are almost all ETFs; "gold" mutual funds are
        # miner-equity funds (a different asset), so this class is ETF-heavy.
        "tickers": [
            "IAU", "GLD", "GLDM", "SGOL", "IAUM", "BAR", "OUNZ", "AAAU",
        ],
    },
}


def iter_all_tickers() -> list[str]:
    """Every distinct ticker across all classes (for a single bulk fetch)."""
    seen: dict[str, None] = {}
    for meta in ASSET_CLASSES.values():
        for t in meta["tickers"]:
            seen.setdefault(t.upper(), None)
    return list(seen.keys())
