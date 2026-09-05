"""Curated fund universe for the Fund Finder tab.

The candidate set for each asset class is maintained by hand here. This is the
authoritative list of *mutual funds* (Yahoo's fee data for them is unreliable,
so each needs a verified fee below) and the per-class anchors, and it's the only
source for the classes where auto-classification can't be trusted (treasury
maturities, T-bills, gold — see `core/discovery.py`).

ETF coverage is then *widened automatically*: `core/discovery.py` pulls the
largest US ETFs from Yahoo's screener, filters out leveraged/inverse/thematic
funds, and slots the survivors into these same classes by Yahoo's category. So
the membership below is a floor, not the whole table.

The build pipeline (`build_universe.py`) resolves every ticker (curated +
discovered) against Yahoo Finance, drops any that fail, and ranks the survivors
by AUM — so the ordering below is not significant, only the membership is. The
UI shows the top 10 by default with a "show 25 / all" control, so the long tail
just adds browse depth.

The lists are ETF-heavy on purpose: Yahoo's expense-ratio data is accurate for
ETFs but unreliable for mutual funds, so every mutual fund included here also has
a verified fee in EXPENSE_OVERRIDES below. Narrow classes (gold, long treasury,
etc.) simply don't have 35-40 sizable funds — they list as many as genuinely
exist.

`anchor` is the user's preferred fund for the class (highlighted in the UI).
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
    "VTSAX": 0.04, "VTSMX": 0.14, "FSKAX": 0.015, "FZROX": 0.00, "SWTSX": 0.03,
    "VITSX": 0.03, "VSMPX": 0.02, "FSTMX": 0.015,
    # Large Cap Blend
    "VFIAX": 0.04, "FXAIX": 0.015, "SWPPX": 0.02, "VLCAX": 0.05, "VINIX": 0.035,
    "VFINX": 0.14, "FNILX": 0.00, "PREIX": 0.19, "FUSEX": 0.015, "SVSPX": 0.16,
    # Large Cap Value
    "VVIAX": 0.05, "DODGX": 0.51, "FLCOX": 0.035, "VIVAX": 0.17,
    # Mid Cap Value
    "VMVAX": 0.07,
    # Mid Cap Growth
    "VMGMX": 0.07, "VMGRX": 0.36, "RPMGX": 0.73,
    # Small Cap Value
    "VSIAX": 0.07, "VISVX": 0.17,
    # Small Cap Growth
    "VSGAX": 0.07, "VISGX": 0.17,
    # Intl Developed
    "VTMGX": 0.07, "FSPSX": 0.035, "SWISX": 0.06, "VDVIX": 0.16, "VTMNX": 0.06,
    # Emerging Markets
    "VEMAX": 0.14, "FPADX": 0.075, "VEIEX": 0.28,
    # Total International
    "VTIAX": 0.09, "FTIHX": 0.06, "VFWAX": 0.11, "VGTSX": 0.17, "FSGGX": 0.055,
    "FZILX": 0.00, "VTSNX": 0.08,
    # Total Bond
    "VBTLX": 0.05, "FXNAX": 0.025, "SWAGX": 0.04, "VBTIX": 0.035, "DODIX": 0.41,
    "FTBFX": 0.45,
    # Corp Bonds
    "VICSX": 0.07, "VWESX": 0.20, "FCBFX": 0.45,
    # LT Treasury
    "VLGSX": 0.07, "VUSTX": 0.20, "FNBGX": 0.03,
    # Interm Treasury
    "VSIGX": 0.07, "VFITX": 0.20, "FUAMX": 0.03,
    # TIPS
    "VAIPX": 0.10, "VIPSX": 0.20, "FIPDX": 0.05, "FINPX": 0.05, "VTAPX": 0.04,
    # REIT
    "VGSLX": 0.13, "FSRNX": 0.07, "TRREX": 0.65, "FRESX": 0.70, "CSRSX": 0.87,
    # Money-market (ST T-Bills)
    "VUSXX": 0.09, "VMFXX": 0.11,
}


# id -> metadata. `tickers` is the full candidate universe (includes the anchor).
ASSET_CLASSES: dict[str, dict] = {
    # ---- US Equity ----------------------------------------------------------
    "total-market-us": {
        "label": "Total Market (US)",
        "group": "US Equity",
        "anchor": "VTSAX",
        "tickers": [
            # ETFs
            "VTI", "ITOT", "SCHB", "SPTM", "IWV", "VTHR",
            # Mutual funds
            "VTSAX", "FSKAX", "FZROX", "SWTSX", "VTSMX", "VITSX", "VSMPX", "FSTMX",
        ],
    },
    "large-cap-blend": {
        "label": "Large Cap Blend",
        "group": "US Equity",
        "anchor": "VFIAX",
        "tickers": [
            # ETFs
            "VOO", "IVV", "SPY", "SPLG", "SCHX", "VV", "IWB", "VONE", "RSP",
            "OEF", "SCHK", "IWL", "MGC", "DIA", "SPTM",
            # Mutual funds
            "VFIAX", "FXAIX", "SWPPX", "VLCAX", "VINIX", "VFINX", "FNILX",
            "PREIX", "FUSEX", "SVSPX",
        ],
    },
    "large-cap-value": {
        "label": "Large Cap Value",
        "group": "US Equity",
        "anchor": "VVIAX",
        "tickers": [
            # ETFs
            "VTV", "IWD", "SCHV", "SPYV", "VONV", "IVE", "VLUE", "MGV", "RPV",
            "PRF", "FVD", "VYM", "DVY", "SDY", "DHS", "FTA",
            # Mutual funds
            "VVIAX", "DODGX", "FLCOX", "VIVAX",
        ],
    },
    "mid-cap-value": {
        "label": "Mid Cap Value",
        "group": "US Equity",
        "anchor": "VMVAX",
        "tickers": [
            # ETFs
            "VOE", "IWS", "IJJ", "IVOV", "MDYV", "IMCV", "XMVM", "RFV", "FLQM",
            # Mutual funds
            "VMVAX",
        ],
    },
    "mid-cap-growth": {
        "label": "Mid Cap Growth",
        "group": "US Equity",
        "anchor": "VMGMX",
        "tickers": [
            # ETFs
            "VOT", "IWP", "IMCG", "MDYG", "RFG", "XMHQ", "GGRW", "PEZ",
            # Mutual funds
            "VMGMX", "VMGRX", "RPMGX",
        ],
    },
    "small-cap-value": {
        "label": "Small Cap Value",
        "group": "US Equity",
        "anchor": "VSIAX",
        "tickers": [
            # ETFs
            "VBR", "AVUV", "IWN", "IJS", "SLYV", "DFSV", "VTWV", "VIOV", "ISCV",
            "RZV", "DES", "EES", "FNDA",
            # Mutual funds
            "VSIAX", "VISVX",
        ],
    },
    "small-cap-growth": {
        "label": "Small Cap Growth",
        "group": "US Equity",
        "anchor": "VSGAX",
        "tickers": [
            # ETFs
            "VBK", "IWO", "IJT", "SLYG", "VTWG", "GSSC", "XSMO", "VIOG", "ISCG",
            "RZG",
            # Mutual funds
            "VSGAX", "VISGX",
        ],
    },
    # ---- International Equity ------------------------------------------------
    "intl-developed": {
        "label": "Intl Developed",
        "group": "International Equity",
        "anchor": "VTMGX",
        "tickers": [
            # ETFs
            "VEA", "IEFA", "SCHF", "EFA", "IDEV", "SPDW", "EFAV", "EFG", "EFV",
            "DBEF", "HEFA", "DFIC", "IQLT", "FNDF", "GSIE",
            # Mutual funds
            "VTMGX", "FSPSX", "SWISX", "VDVIX", "VTMNX",
        ],
    },
    "emerging-markets": {
        "label": "Emerging Markets",
        "group": "International Equity",
        "anchor": "VEMAX",
        "tickers": [
            # ETFs
            "VWO", "IEMG", "EEM", "SCHE", "SPEM", "EEMV", "FNDE", "EMXC", "DEM",
            "EDIV", "XSOE", "AVEM", "DGRE", "DGS",
            # Mutual funds
            "VEMAX", "FPADX", "VEIEX",
        ],
    },
    "total-international": {
        "label": "Total International",
        "group": "International Equity",
        "anchor": "VTIAX",
        "tickers": [
            # ETFs
            "VXUS", "IXUS", "VEU", "ACWX", "CWI", "DFAX", "AVNM", "AVNV",
            # Mutual funds
            "VTIAX", "FTIHX", "VFWAX", "VGTSX", "FSGGX", "FZILX", "VTSNX",
        ],
    },
    # ---- Fixed Income -------------------------------------------------------
    "total-bond": {
        "label": "Total Bond Market",
        "group": "Fixed Income",
        "anchor": "VBTLX",
        "tickers": [
            # ETFs
            "BND", "AGG", "SCHZ", "SPAB", "BNDW", "IUSB", "BIV", "FBND", "BOND",
            "AGGY", "EAGG",
            # Mutual funds
            "VBTLX", "FXNAX", "SWAGX", "VBTIX", "DODIX", "FTBFX",
        ],
    },
    "corp-bonds": {
        "label": "Corp Bonds",
        "group": "Fixed Income",
        "anchor": "VICSX",
        "tickers": [
            # ETFs
            "LQD", "VCIT", "VCSH", "IGIB", "SPIB", "USIG", "VCLT", "SPLB",
            "IGSB", "IGLB", "SLQD", "SPSB", "CORP", "GIGB", "FLCB",
            # Mutual funds
            "VICSX", "VWESX", "FCBFX",
        ],
    },
    "lt-treasury": {
        "label": "LT Treasury",
        "group": "Fixed Income",
        "anchor": "VLGSX",
        "tickers": [
            # ETFs
            "TLT", "VGLT", "SPTL", "EDV", "TLH", "GOVZ", "ZROZ",
            # Mutual funds
            "VLGSX", "VUSTX", "FNBGX",
        ],
    },
    "interm-treasury": {
        "label": "Interm Treasury",
        "group": "Fixed Income",
        "anchor": "VSIGX",
        "tickers": [
            # ETFs
            "IEF", "VGIT", "SPTI", "IEI", "SCHR", "GOVT",
            # Mutual funds
            "VSIGX", "VFITX", "FUAMX",
        ],
    },
    "tips": {
        "label": "TIPS",
        "group": "Fixed Income",
        "anchor": "TIP",
        "tickers": [
            # ETFs
            "TIP", "SCHP", "VTIP", "STIP", "SPIP", "TDTT", "LTPZ", "STPZ", "TIPX",
            # Mutual funds
            "VAIPX", "VIPSX", "FIPDX", "FINPX", "VTAPX",
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
            # ETFs
            "SGOV", "BIL", "SHV", "GBIL", "TBIL", "USFR", "SHY", "TFLO", "TBLL",
            "OBIL", "SCHO", "VGSH", "VBIL",
            # Money-market funds
            "VUSXX", "VMFXX",
        ],
    },
    # ---- Alternatives -------------------------------------------------------
    "reit": {
        "label": "REIT",
        "group": "Alternatives",
        "anchor": "VGSLX",
        "tickers": [
            # ETFs
            "VNQ", "SCHH", "XLRE", "IYR", "USRT", "ICF", "RWR", "FREL", "REM",
            "MORT", "SRVR", "INDS", "REZ", "KBWY", "ROOF",
            # Mutual funds
            "VGSLX", "FSRNX", "TRREX", "FRESX", "CSRSX",
        ],
    },
    "gold": {
        "label": "Gold",
        "group": "Alternatives",
        "anchor": "IAU",
        # Gold-bullion funds are almost all ETFs; "gold" mutual funds are
        # miner-equity funds (a different asset), so this class is ETF-only.
        "tickers": [
            "IAU", "GLD", "GLDM", "SGOL", "IAUM", "BAR", "OUNZ", "AAAU",
            "GLTR", "DBP",
        ],
    },
}


def expense_for(ticker: str, yahoo_value: float | None) -> float | None:
    """Curated expense ratio when we have one, else Yahoo's value."""
    return EXPENSE_OVERRIDES.get(ticker.upper(), yahoo_value)


def iter_all_tickers() -> list[str]:
    """Every distinct ticker across all classes (for a single bulk fetch)."""
    seen: dict[str, None] = {}
    for meta in ASSET_CLASSES.values():
        for t in meta["tickers"]:
            seen.setdefault(t.upper(), None)
    return list(seen.keys())
